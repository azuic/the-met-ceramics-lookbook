"""Stage 3 + 3b + 4 -- crop tiles, quality-control them, measure their colour.

Runs as one pass because the expensive part is the download, and the source
image is worth nothing once the tile and the colour are extracted. So:

    fetch one image  ->  QC + crop  ->  two tile sizes  ->  colour  ->  discard

Peak disk is a single source image, not 6.3 GB. See PLAN.md stage 3.

Colour is stored RAW -- OKLab lightness, chroma, hue, plus a dominant colour.
Palette *family* is deliberately NOT assigned here: family boundaries want
tuning against the finished distribution, and keeping assignment out of this
stage means re-tuning them never costs another download.

Monochrome sources are tiled and measured like anything else but flagged
`mono`, because their colour is film exposure rather than glaze (PLAN.md 4e).

    python3 pipeline/tiles.py --limit 400        # try it
    python3 pipeline/tiles.py --max-runtime 17400
"""

import argparse
import collections
import concurrent.futures as cf
import gzip
import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageFile

# Some MET images are served with a Content-Length the CDN cannot deliver --
# the response is a genuinely truncated JPEG, not a throttle, and retrying
# returns the same short read forever. Decoding what did arrive recovers the
# object, but only when the undecoded tail stays clear of the crop; see
# decode_partial().
ImageFile.LOAD_TRUNCATED_IMAGES = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qc import (crop_with_qc, is_monochrome, oklab,  # noqa: E402
                CROP_LADDER, MAX_BACKDROP)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "cache")
TILES = os.path.join(CACHE, "tiles")
COLOURS = os.path.join(DATA, "colours.jsonl")

UA = ("the-met-ceramics-lookbook/1.0 "
      "(+https://github.com/azuic/the-met-ceramics-lookbook)")

# Measured on 243 real QC-passed crops, extrapolated to 51,521:
#   112px q72 -> 133 MB     96px q64 ->  92 MB     40px q64 -> 23 MB
#   112px q64 -> 122 MB     88px q64 ->  82 MB
# The plan specified 112px, sized for retina sharpness. These are texture
# crops though, where softness costs far less than 40 MB of permanent git
# history does. 96px it is.
SIZES = (96, 40)            # grid tier, fast-scroll tier
WEBP_Q = 64


def encode_url(u):
    """Percent-encode the path so exotic filenames survive urlopen().

    173 of the MET's image filenames contain a literal space ("RRP Table
    68.207 Ret.jpg") or an en-dash ("61_200_13a-c_O1_sf.jpg", with U+2013).
    urlopen rejects the first as InvalidURL and the second as
    UnicodeEncodeError. Both files exist and fetch fine once quoted.
    """
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path, safe="/%"),
         p.query, p.fragment))


def flat_tail(im, step=17):
    """Rows at the bottom that decoded to a uniform fill, i.e. never arrived."""
    w, h = im.size
    px = im.load()
    n = 0
    for y in range(h - 1, -1, -1):
        if len({px[x, y] for x in range(0, w, step)}) > 2:
            break
        n += 1
    return n


def decode_partial(raw, ladder_top=CROP_LADDER[0]):
    """Decode a truncated JPEG, but only if the crop lands on real pixels.

    PIL fills the undecoded tail with flat grey. That grey reads as studio
    backdrop, so a half-decoded frame would sail through quality control and
    put a blank slab in the grid. Accept the salvage only when the fill stays
    entirely below the widest crop the ladder can take.
    """
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    tail = flat_tail(im)
    if not tail:
        return im
    crop_bottom = (h + int(min(w, h) * ladder_top)) // 2
    return im if crop_bottom <= h - tail else None


def dominant(im, k=5):
    """Most massive colour cluster, via an octree quantiser.

    A mean muddies a two-tone tile -- cobalt on white averages to pale grey,
    which belongs to neither family. The dominant cluster keeps the tile in
    the family a person would actually name.
    """
    q = im.resize((48, 48), Image.LANCZOS).quantize(
        colors=k, method=Image.FASTOCTREE)
    pal = q.getpalette()[:k * 3]
    counts = collections.Counter(q.getdata())
    idx, n = counts.most_common(1)[0]
    return (pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]), n / (48 * 48)


def measure(crop):
    small = crop.resize((24, 24), Image.LANCZOS)
    px = list(small.getdata())
    r = sum(p[0] for p in px) / len(px)
    g = sum(p[1] for p in px) / len(px)
    b = sum(p[2] for p in px) / len(px)
    L, a, bb = oklab((r, g, b))
    dom, mass = dominant(crop)
    dL, da, dbb = oklab(dom)
    return {
        "L": round(L, 4),
        "C": round(math.hypot(a, bb), 4),
        "h": round(math.degrees(math.atan2(bb, a)) % 360, 1),
        "rgb": [int(r), int(g), int(b)],
        "dom": list(dom),
        "domL": round(dL, 4),
        "domC": round(math.hypot(da, dbb), 4),
        "domh": round(math.degrees(math.atan2(dbb, da)) % 360, 1),
        "domMass": round(mass, 3),
    }


def load_done(require_tiles=False):
    """IDs already measured.

    Error records deliberately do NOT count as done, so re-running retries
    them -- a timeout is a fact about the network that evening, not about the
    object. A retry that succeeds appends a second record for the same ID, so
    everything downstream must read this file LAST-WINS.

    With require_tiles, an accepted object whose tile files are missing is not
    done either. The measurement log and the tile cache are separate artefacts
    and CAN diverge: colours.jsonl is committed, cache/ is gitignored, so an
    ordinary git operation can destroy every tile while the log survives
    intact. Without this the pipeline reports STAGE 3 COMPLETE over an empty
    cache and stage 5 packs 44,357 blank squares.
    """
    last = {}
    if os.path.exists(COLOURS):
        with open(COLOURS) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                last[r["id"]] = r

    done = {oid for oid, r in last.items() if "error" not in r}
    if not require_tiles:
        return done

    # Only objects that PASSED QC are expected on disk -- a rejected one
    # legitimately has no tile, so absence proves nothing about it.
    return {oid for oid in done
            if not last[oid].get("ok") or has_tiles(oid)}


def has_tiles(oid):
    return all(os.path.exists(os.path.join(TILES, str(s), f"{oid}.webp"))
               for s in SIZES)


def load_targets():
    api = {}
    with gzip.open(os.path.join(DATA, "api_objects.jsonl.gz"), "rt") as f:
        for line in f:
            d = json.loads(line)
            if d.get("primaryImageSmall"):
                api[str(d["objectID"])] = d["primaryImageSmall"]
    out = []
    path = os.path.join(DATA, "candidates.jsonl")
    opener, mode = (open, "r")
    if not os.path.exists(path):
        path, opener, mode = path + ".gz", gzip.open, "rt"
    with opener(path, mode) as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in api:
                out.append((r["id"], api[r["id"]], r["type"]))
    return out


def process(job):
    oid, url, _ = job
    req = urllib.request.Request(encode_url(url), headers={"User-Agent": UA})
    im = err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read()
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            break
        except Exception as e:
            err = type(e).__name__
            partial = getattr(e, "partial", None)
            if partial:                        # short read: salvage if usable
                try:
                    im = decode_partial(partial)
                except Exception:
                    im = None
                if im is not None:
                    break
                err = "TruncatedPastCrop"
                break                          # retrying returns the same bytes
            time.sleep(1.5 * (attempt + 1))    # CDN throttle, not a dead file
    if im is None:
        return oid, {"id": oid, "error": err}

    crop, frac, bd, ok, mono = crop_with_qc(im)
    rec = {"id": oid, "crop": frac, "backdrop": round(bd, 3),
           "ok": ok, "mono": mono}
    if not ok:
        return oid, rec                       # rejected: no tile written
    rec.update(measure(crop))
    for s in SIZES:
        d = os.path.join(TILES, str(s))
        os.makedirs(d, exist_ok=True)
        crop.resize((s, s), Image.LANCZOS).save(
            os.path.join(d, f"{oid}.webp"), "WEBP",
            quality=WEBP_Q, method=6)
    return oid, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--max-runtime", type=float, default=0)
    ap.add_argument("--heal", action="store_true",
                    help="also re-fetch accepted objects whose tiles are "
                         "missing from the cache")
    args = ap.parse_args()

    os.makedirs(DATA, exist_ok=True)
    os.makedirs(TILES, exist_ok=True)

    targets = load_targets()
    done = load_done(require_tiles=args.heal)
    todo = [t for t in targets if t[0] not in done]
    print(f"  {len(targets):,} objects with imagery, {len(done):,} done, "
          f"{len(todo):,} to go")
    if args.heal:
        gaps = len(load_done()) - len(done)
        print(f"  --heal: {gaps:,} of those are measured but untiled")
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("  STAGE 3 COMPLETE")
        return 0

    started = time.time()
    stats = collections.Counter()
    n = 0
    with open(COLOURS, "a") as out, \
            cf.ThreadPoolExecutor(args.concurrency) as ex:
        for oid, rec in ex.map(process, todo):
            out.write(json.dumps(rec) + "\n")
            n += 1
            stats["error" if "error" in rec else
                  ("rejected" if not rec["ok"] else
                   ("mono" if rec["mono"] else "colour"))] += 1
            if n % 500 == 0:
                out.flush()
                rate = n / (time.time() - started)
                left = (len(todo) - n) / max(rate, .01) / 3600
                print(f"    {n:,}/{len(todo):,}  {rate:.1f}/s  "
                      f"~{left:.1f}h left  {dict(stats)}", flush=True)
            if args.max_runtime and time.time() - started > args.max_runtime:
                print("\n  hit --max-runtime; stopping cleanly")
                break

    el = max(time.time() - started, 1)
    print(f"\n  processed {n:,} in {el/60:.1f} min ({n/el:.1f}/s)")
    for k, v in stats.most_common():
        print(f"    {k:<10} {v:,}")
    have = len(load_done())
    print(f"  colours.jsonl now holds {have:,} of {len(targets):,}")
    if have >= len(targets):
        print("  STAGE 3 COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
