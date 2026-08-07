"""Stage 2 -- fetch image URLs and metadata from the MET Collection API.

The API sits behind Imperva, which is aggressive. Measured behaviour:

    concurrency 4  ->  ~12 req/s, occasional 403
    concurrency 8  ->  403 on EVERY request
    after a burst  ->  the IP is soft-banned; even sequential requests 403

So this stage is deliberately slow and serial. It is not a bug that it takes
hours. Bursting does not make it faster, it makes it stop.

Resumable by design: every response is appended to a cache keyed by object ID,
and a re-run skips whatever is already there. Killing this process, closing a
laptop, or hitting a CI time limit costs only the in-flight request.

    python3 pipeline/fetch.py                      # resume until done
    python3 pipeline/fetch.py --limit 200          # smoke test
    python3 pipeline/fetch.py --max-runtime 18000  # stop cleanly after 5h
"""

import argparse
import gzip
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "cache")
CACHE_FILE = os.path.join(CACHE, "api_objects.jsonl")
# The durable copy. State lives in the repo, not in a CI cache that expires --
# same principle that the rest of this rebuild is built on. A run seeds itself
# from this file and writes it back, so runs chain across machines.
GZ_FILE = os.path.join(DATA, "api_objects.jsonl.gz")

API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/"
UA = ("the-met-ceramics-lookbook/1.0 "
      "(+https://github.com/azuic/the-met-ceramics-lookbook)")

# Fields worth keeping. The CSV already gave us department, country and
# classification, so this is only what the CSV does not carry.
KEEP = (
    "objectID", "title", "primaryImage", "primaryImageSmall", "objectDate",
    "culture", "period", "artistDisplayName", "objectURL", "isPublicDomain",
    "additionalImages",
)


class Backoff:
    """Long backoff on 403. Imperva bans for minutes, not milliseconds."""

    STEPS = (60, 120, 300, 600, 900, 1800)

    def __init__(self):
        self.n = 0

    def hit(self):
        wait = self.STEPS[min(self.n, len(self.STEPS) - 1)]
        self.n += 1
        wait *= 0.75 + random.random() * 0.5  # jitter
        print(f"    403 -- backing off {wait:.0f}s "
              f"(strike {self.n})", flush=True)
        time.sleep(wait)

    def ok(self):
        self.n = 0


def seed_from_gz():
    """Populate the working cache from the committed .gz, if needed."""
    if os.path.exists(CACHE_FILE) or not os.path.exists(GZ_FILE):
        return
    os.makedirs(CACHE, exist_ok=True)
    with gzip.open(GZ_FILE, "rt", encoding="utf-8") as src, \
            open(CACHE_FILE, "w", encoding="utf-8") as dst:
        dst.write(src.read())
    print(f"  seeded working cache from {os.path.basename(GZ_FILE)}")


def write_gz():
    """Write the durable copy back."""
    if not os.path.exists(CACHE_FILE):
        return
    with open(CACHE_FILE, encoding="utf-8") as src, \
            gzip.open(GZ_FILE, "wt", encoding="utf-8", compresslevel=9) as dst:
        dst.write(src.read())
    print(f"  wrote {os.path.basename(GZ_FILE)} "
          f"({os.path.getsize(GZ_FILE)/1e6:.1f} MB)")


def load_done():
    """Object IDs already fetched."""
    done = set()
    if not os.path.exists(CACHE_FILE):
        return done
    with open(CACHE_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                done.add(str(json.loads(line)["objectID"]))
            except Exception:
                continue
    return done


def fetch_one(oid, timeout=30):
    req = urllib.request.Request(API + str(oid), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates",
                    default=os.path.join(DATA, "candidates.jsonl"))
    ap.add_argument("--delay", type=float, default=0.18,
                    help="seconds between requests (default 0.18 ~ 5.5/s)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N new")
    ap.add_argument("--max-runtime", type=float, default=0,
                    help="seconds; exit cleanly before a CI timeout")
    args = ap.parse_args()

    os.makedirs(CACHE, exist_ok=True)
    seed_from_gz()

    cand = args.candidates
    if not os.path.exists(cand) and os.path.exists(cand + ".gz"):
        cand += ".gz"
    opener = gzip.open if cand.endswith(".gz") else open
    with opener(cand, "rt", encoding="utf-8") as f:
        want = [json.loads(line)["id"] for line in f]

    done = load_done()
    todo = [o for o in want if o not in done]
    print(f"  {len(want):,} candidates, {len(done):,} cached, "
          f"{len(todo):,} to fetch")
    if args.limit:
        todo = todo[:args.limit]
        print(f"  limited to {len(todo):,}")
    if not todo:
        print("  nothing to do -- stage 2 complete")
        write_gz()
        return 0

    est = len(todo) * args.delay / 3600
    print(f"  at {1/args.delay:.1f} req/s this is ~{est:.1f} h\n")

    started = time.time()
    backoff = Backoff()
    ok = err = 0

    with open(CACHE_FILE, "a", encoding="utf-8") as out:
        for i, oid in enumerate(todo):
            if args.max_runtime and time.time() - started > args.max_runtime:
                print(f"\n  hit --max-runtime; stopping cleanly at {i:,}")
                break
            while True:
                try:
                    d = fetch_one(oid)
                    rec = {k: d.get(k) for k in KEEP}
                    rec["additionalImages"] = len(d.get("additionalImages") or [])
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    backoff.ok()
                    ok += 1
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 403 or e.code == 429:
                        backoff.hit()
                        continue
                    if e.code == 404:
                        err += 1
                        break
                    backoff.hit()
                    continue
                except Exception:
                    time.sleep(5)
                    err += 1
                    break
            if i and i % 250 == 0:
                rate = (i + 1) / (time.time() - started)
                left = (len(todo) - i) / max(rate, 0.01) / 3600
                print(f"    {i:,}/{len(todo):,}  {rate:.1f}/s  "
                      f"~{left:.1f}h left", flush=True)
            time.sleep(args.delay)

    print(f"\n  fetched {ok:,}, errors {err:,}")
    have = len(load_done())
    print(f"  cache now holds {have:,} of {len(want):,} objects")
    write_gz()
    if have < len(want):
        print(f"  INCOMPLETE -- {len(want)-have:,} remain; re-run to resume")
    return 0


if __name__ == "__main__":
    sys.exit(main())
