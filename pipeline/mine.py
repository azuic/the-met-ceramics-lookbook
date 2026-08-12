"""Stage 1 -- mine the MET Open Access CSV for ceramic objects.

Streams the CSV (317 MB, ~485k rows), applies the classification rules from
classify.py, and writes one JSON record per surviving object.

    python3 pipeline/mine.py                    # download to cache, mine all
    python3 pipeline/mine.py --csv path.csv     # use a local CSV
    python3 pipeline/mine.py --cap-per-type 10000

Does not touch the network beyond fetching the CSV, and never keeps the CSV
in memory. See PLAN.md section 5.
"""

import argparse
import collections
import csv
import gzip
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import classify_type, classify_surface, tokenize  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
DATA = os.path.join(HERE, "data")

CSV_URL = ("https://media.githubusercontent.com/media/metmuseum/openaccess/"
           "master/MetObjects.csv")

csv.field_size_limit(10 ** 9)

# Columns we carry forward. Everything else is dropped here.
KEEP = {
    "Object ID": "id",
    "Medium": "medium",
    "Title": "title",
    "Object Name": "objectName",
    "Culture": "culture",
    "Object Date": "objectDate",
    "Object Begin Date": "beginDate",
    "Department": "department",
    "Classification": "classification",
    "Country": "country",
    "Region": "region",
    "Link Resource": "objectURL",
}


def ensure_csv(path=None):
    """Return a path to the CSV, downloading to cache/ if needed."""
    if path:
        return path
    os.makedirs(CACHE, exist_ok=True)
    local = os.path.join(CACHE, "MetObjects.csv")
    if os.path.exists(local) and os.path.getsize(local) > 100_000_000:
        print(f"  using cached CSV ({os.path.getsize(local)/1e6:.0f} MB)")
        return local
    print(f"  downloading {CSV_URL}")
    tmp = local + ".part"
    with urllib.request.urlopen(CSV_URL, timeout=120) as r, open(tmp, "wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            if total % (50 << 20) < (1 << 20):
                print(f"    {total/1e6:.0f} MB")
    os.replace(tmp, local)
    print(f"  downloaded {total/1e6:.0f} MB")
    return local


def mine(csv_path, public_domain_only=True):
    """Yield one record per ceramic object."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if public_domain_only and (
                    row.get("Is Public Domain") or "").strip().lower() != "true":
                continue
            medium = (row.get("Medium") or "").strip()
            t = classify_type(medium)
            if t is None:
                continue
            rec = {out: (row.get(col) or "").strip()
                   for col, out in KEEP.items()}
            rec["type"] = t
            rec["surface"] = classify_surface(medium)
            rec["tokened"] = tokenize(medium)
            yield rec


def apply_cap(records, cap):
    """Thin each type down to `cap`, spreading the loss across departments.

    Round-robins over departments rather than truncating, so a cap thins every
    region evenly instead of amputating whichever one sorts last. Colour-bucket
    stratification is not possible here -- colour is not known until Stage 4 --
    so this is department-stratified only.
    """
    by_type = collections.defaultdict(list)
    for r in records:
        by_type[r["type"]].append(r)

    out = []
    for t, rows in by_type.items():
        if len(rows) <= cap:
            out.extend(rows)
            continue
        by_dept = collections.defaultdict(list)
        for r in rows:
            by_dept[r["department"] or "?"].append(r)
        queues = sorted(by_dept.values(), key=len, reverse=True)
        kept, i = [], 0
        while len(kept) < cap:
            progressed = False
            for q in queues:
                if i < len(q):
                    kept.append(q[i])
                    progressed = True
                    if len(kept) == cap:
                        break
            if not progressed:
                break
            i += 1
        out.extend(kept)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="local MetObjects.csv (default: download)")
    ap.add_argument("--cap-per-type", type=int, default=0,
                    help="max objects per type; 0 = no cap (default)")
    ap.add_argument("--out", default=os.path.join(DATA, "candidates.jsonl"))
    ap.add_argument("--include-non-public-domain", action="store_true")
    args = ap.parse_args()

    os.makedirs(DATA, exist_ok=True)
    path = ensure_csv(args.csv)

    print("  mining...")
    records = list(mine(path, not args.include_non_public_domain))
    print(f"  {len(records):,} ceramic objects found")

    if args.cap_per_type:
        before = len(records)
        records = apply_cap(records, args.cap_per_type)
        print(f"  cap {args.cap_per_type:,}/type: {before:,} -> {len(records):,}")

    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n"
                      for r in records)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(payload)
    # Committed alongside the code: ~1 MB gzipped, which lets CI run stage 2
    # without ever downloading the 318 MB CSV.
    with gzip.open(args.out + ".gz", "wt", encoding="utf-8",
                   compresslevel=9) as f:
        f.write(payload)

    by_type = collections.Counter(r["type"] for r in records)
    by_dept = collections.Counter(r["department"] for r in records)
    summary = {
        "total": len(records),
        "by_type": dict(by_type.most_common()),
        "by_department": dict(by_dept.most_common()),
        "cap_per_type": args.cap_per_type,
    }
    with open(os.path.join(DATA, "mine_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  wrote {args.out}")
    print(f"  {'type':<20} {'n':>7}")
    print("  " + "-" * 28)
    for t, c in by_type.most_common():
        print(f"  {t:<20} {c:>7,}")
    print(f"  {'TOTAL':<20} {len(records):>7,}")


if __name__ == "__main__":
    main()
