"""Stage 3b -- crop quality control.

MET photographs are whole-object studio shots. Stage 3 keeps a tight central
patch of the frame, which lands on glaze for a vessel that fills its frame and
lands on empty backdrop for a 1cm scarab. This module decides which happened.

The test is BACKDROP DOMINANCE, not a saturation floor. White porcelain,
cream earthenware and celadon are legitimately desaturated and belong in the
grid -- a naive "too pale, drop it" rule would delete precisely the objects
the `cream` palette family is made of. Instead:

  1. Sample the border ring of the *full* image. On a studio shot that ring
     is the backdrop, by construction.
  2. Measure what fraction of the crop sits within a small OKLab distance of
     that colour.
  3. If too much of it is backdrop, retry with a TIGHTER crop -- small
     objects are centred, so tightening moves onto the object.
  4. Only reject if even the tightest crop is mostly backdrop.

A white bowl filling the frame passes (low backdrop fraction despite low
saturation). A scarab adrift in grey fails. That is the intended behaviour.

    python3 pipeline/qc.py --tune --sample 900
"""

import argparse
import collections
import concurrent.futures as cf
import io
import json
import gzip
import math
import os
import random
import sys
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "cache", "images")

UA = ("the-met-ceramics-lookbook/1.0 "
      "(+https://github.com/azuic/the-met-ceramics-lookbook)")

# Tuned on a stratified sample of 890 real images; see `--tune`.
CROP_LADDER = (0.32, 0.24, 0.17)
MAX_BACKDROP = 0.40         # 0.60 was too slack -- the ladder never engaged
BACKDROP_TOL = 0.055        # OKLab distance counted as "same as backdrop"
MONO_CHROMA = 0.006         # p95 whole-image chroma below this = greyscale


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklab(rgb):
    r, g, b = (_lin(v) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def backdrop_colour(im):
    """Median colour of the border ring of the full frame.

    Median rather than mean: a mean is dragged around by any object that
    happens to touch the edge, while a median ignores it.
    """
    small = im.resize((64, 64), Image.LANCZOS)
    px = small.load()
    ring = []
    for i in range(64):
        for x, y in ((i, 0), (i, 63), (0, i), (63, i), (i, 2), (2, i)):
            ring.append(px[x, y])
    ring.sort(key=lambda c: c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114)
    return ring[len(ring) // 2]


def backdrop_fraction(crop, bg_lab, tol=BACKDROP_TOL):
    small = crop.resize((32, 32), Image.LANCZOS)
    n = hit = 0
    for p in small.getdata():
        lab = oklab(p)
        d = math.sqrt((lab[0] - bg_lab[0]) ** 2 +
                      (lab[1] - bg_lab[1]) ** 2 +
                      (lab[2] - bg_lab[2]) ** 2)
        n += 1
        if d < tol:
            hit += 1
    return hit / n


def is_monochrome(im, thresh=MONO_CHROMA):
    """True when the SOURCE PHOTOGRAPH carries no colour at all.

    Roughly a sixth of the MET's ceramic imagery is old black-and-white
    record photography -- and a handful are placeholder cards reading
    "CONSULT PRIMARY RECORD". Colour-sorting those is sorting by film
    exposure, not by glaze, so they have to be identified rather than
    quietly folded into the greys.

    Keyed on the 95th percentile of whole-image chroma, not the mean: a
    genuinely white porcelain bowl shot in colour still has *some* coloured
    pixels (backdrop cast, shadows, a label), while a greyscale scan has
    literally none.
    """
    small = im.resize((40, 40), Image.LANCZOS)
    ch = sorted(math.hypot(*oklab(px)[1:]) for px in small.getdata())
    return ch[int(0.95 * len(ch))] < thresh


def centre_crop(im, frac):
    w, h = im.size
    s = int(min(w, h) * frac)
    return im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))


def crop_with_qc(im, ladder=CROP_LADDER, max_backdrop=MAX_BACKDROP,
                 tol=BACKDROP_TOL):
    """Return (crop, frac_used, backdrop_fraction, accepted, mono)."""
    mono = is_monochrome(im)
    bg = oklab(backdrop_colour(im))
    last = None
    for frac in ladder:
        c = centre_crop(im, frac)
        bd = backdrop_fraction(c, bg, tol)
        last = (c, frac, bd)
        if bd <= max_backdrop:
            return c, frac, bd, True, mono
    return last[0], last[1], last[2], False, mono


# --- tuning harness ----------------------------------------------------------

def load_joined():
    api = {}
    with gzip.open(os.path.join(DATA, "api_objects.jsonl.gz"), "rt") as f:
        for line in f:
            d = json.loads(line)
            if d.get("primaryImageSmall"):
                api[str(d["objectID"])] = d["primaryImageSmall"]
    out = []
    with open(os.path.join(DATA, "candidates.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in api:
                r["url"] = api[r["id"]]
                out.append(r)
    return out


def stratified(rows, n, seed=11):
    """Spread the sample across departments AND object kinds.

    Object kind matters more than department here: the failure mode is small
    objects, and 'Scarab' or 'Bead' predicts that far better than 'Egyptian
    Art' does.
    """
    def kind(r):
        nm = (r.get("objectName") or "?").lower()
        for k in ("scarab", "seal", "bead", "amulet", "fragment", "sherd",
                  "tile", "figure", "bowl", "jar", "vase", "plate", "dish"):
            if k in nm:
                return k
        return "other"

    buckets = collections.defaultdict(list)
    for r in rows:
        buckets[(r["department"], kind(r))].append(r)
    rnd = random.Random(seed)
    for v in buckets.values():
        rnd.shuffle(v)
    out, i = [], 0
    keys = sorted(buckets)
    while len(out) < n:
        progressed = False
        for k in keys:
            if i < len(buckets[k]):
                out.append(buckets[k][i])
                progressed = True
                if len(out) >= n:
                    break
        if not progressed:
            break
        i += 1
    return out


def fetch_image(row):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, row["id"] + ".jpg")
    if os.path.exists(path):
        return path
    try:
        req = urllib.request.Request(row["url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception:
        return None


def tune(args):
    rows = load_joined()
    print(f"  {len(rows):,} objects with imagery")
    sample = stratified(rows, args.sample)
    print(f"  sampling {len(sample):,}, stratified by department x object kind")

    # images.metmuseum.org is a CDN, not the Imperva-fronted API, so this can
    # actually parallelise -- unlike stage 2.
    paths = {}
    with cf.ThreadPoolExecutor(args.concurrency) as ex:
        for row, p in zip(sample, ex.map(fetch_image, sample)):
            if p:
                paths[row["id"]] = p
    print(f"  {len(paths):,} images cached in {CACHE}")

    results = []
    for row in sample:
        p = paths.get(row["id"])
        if not p:
            continue
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        crop, frac, bd, ok, mono = crop_with_qc(im, args.ladder,
                                                args.max_backdrop)
        results.append((row, crop, frac, bd, ok, mono))

    acc = [r for r in results if r[4]]
    rej = [r for r in results if not r[4]]
    mono = [r for r in results if r[5]]
    print(f"\n  accepted {len(acc):,}  ({100*len(acc)/max(len(results),1):.1f}%)")
    print(f"  rejected {len(rej):,}  ({100*len(rej)/max(len(results),1):.1f}%)")

    print(f"  greyscale source photo: {len(mono):,}  "
          f"({100*len(mono)/max(len(results),1):.1f}%)  -- no colour record")

    print("\n  crop fraction actually used:")
    for f, c in sorted(collections.Counter(r[2] for r in acc).items()):
        print(f"     {f:.2f}  {c:,}")

    print("\n  rejection rate by object kind:")
    byk = collections.defaultdict(lambda: [0, 0])
    for row, _, _, _, ok, _ in results:
        nm = (row.get("objectName") or "?").strip()[:26] or "?"
        byk[nm][0] += 1
        byk[nm][1] += 0 if ok else 1
    worst = sorted(byk.items(), key=lambda kv: -kv[1][1])[:12]
    for nm, (tot, bad) in worst:
        if bad:
            print(f"     {bad:>4}/{tot:<5} {100*bad/tot:5.1f}%  {nm}")

    colour_acc = [r for r in acc if not r[5]]
    contact(colour_acc[:180], os.path.join(HERE, "qc_accepted.png"))
    contact(rej[:180], os.path.join(HERE, "qc_rejected.png"))
    contact(mono[:180], os.path.join(HERE, "qc_monochrome.png"))
    print("\n  wrote qc_accepted.png / qc_rejected.png / qc_monochrome.png")


def contact(items, path, tile=90, cols=18):
    if not items:
        print(f"  (nothing to write for {os.path.basename(path)})")
        return
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * tile), (243, 241, 236))
    for i, it in enumerate(items):
        crop = it[1]
        sheet.paste(crop.resize((tile, tile), Image.LANCZOS),
                    ((i % cols) * tile, (i // cols) * tile))
    sheet.save(path, quality=92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--sample", type=int, default=900)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--max-backdrop", type=float, default=MAX_BACKDROP)
    ap.add_argument("--ladder", type=float, nargs="+", default=CROP_LADDER)
    args = ap.parse_args()
    if not args.tune:
        ap.error("nothing to do; pass --tune")
    tune(args)


if __name__ == "__main__":
    sys.exit(main())
