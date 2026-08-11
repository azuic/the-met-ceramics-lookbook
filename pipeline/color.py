"""Stage 4 -- colour measurement and glaze-family assignment.

Reads the TILES OFF DISK. Never the network. The 96px tiles are the archive,
so re-measuring all 44k costs minutes and no downloads, and the palette
boundaries in `families` can be re-tuned indefinitely. See PLAN.md 4c, 5, 6.

Two steps, deliberately separate:

    measure   tiles -> data/palette.jsonl   (raw 6-cluster palette per tile)
    families  palette.jsonl -> data/families.json + a distribution report

`measure` stores only RAW clusters -- rgb and mass, nothing derived. Every
judgement (which cluster speaks for the tile, where cobalt ends and turquoise
begins) lives in `families`, which runs in seconds. That means a bad boundary
costs a re-run of the cheap step, never of the expensive one.

    python3 pipeline/color.py measure
    python3 pipeline/color.py families --report
"""

import argparse
import collections
import json
import math
import multiprocessing as mp
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qc import oklab                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TILES = os.path.join(HERE, "cache", "tiles", "96")
COLOURS = os.path.join(DATA, "colours.jsonl")
PALETTE = os.path.join(DATA, "palette.jsonl")
FAMILIES = os.path.join(DATA, "families.json")

K = 6                       # clusters kept per tile


# ---------------------------------------------------------------------------
# measure
# ---------------------------------------------------------------------------

def measure_tile(oid):
    path = os.path.join(TILES, oid + ".webp")
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    small = im.resize((48, 48), Image.LANCZOS)
    q = small.quantize(colors=K, method=Image.FASTOCTREE)
    pal = q.getpalette()[:K * 3]
    counts = collections.Counter(q.getdata())
    tot = 48 * 48
    clusters = [[pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2], round(n / tot, 4)]
                for i, n in counts.most_common()]
    px = list(small.getdata())
    avg = tuple(sum(p[c] for p in px) / len(px) for c in range(3))
    L, a, b = oklab(avg)
    return {
        "id": oid,
        "avg": [round(L, 4), round(math.hypot(a, b), 4),
                round(math.degrees(math.atan2(b, a)) % 360, 1)],
        "pal": clusters,
    }


def load_tiles():
    """Accepted tile IDs, with their mono flag. colours.jsonl is last-wins."""
    last = {}
    with open(COLOURS) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            last[r["id"]] = r
    return {r["id"]: bool(r.get("mono"))
            for r in last.values() if "error" not in r and r.get("ok")}


def do_measure(args):
    mono = load_tiles()
    ids = sorted(mono)
    print(f"  {len(ids):,} accepted tiles")
    done = set()
    if os.path.exists(PALETTE) and not args.force:
        with open(PALETTE) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    continue
    todo = [i for i in ids if i not in done]
    if not todo:
        print("  nothing to do (pass --force to re-measure)")
        return 0
    print(f"  measuring {len(todo):,} on {args.workers} workers")

    mode = "w" if args.force else "a"
    n = miss = 0
    with open(PALETTE, mode) as out, mp.Pool(args.workers) as pool:
        for rec in pool.imap_unordered(measure_tile, todo, chunksize=256):
            n += 1
            if rec is None:
                miss += 1
                continue
            rec["mono"] = 1 if mono[rec["id"]] else 0
            out.write(json.dumps(rec, separators=(",", ":")) + "\n")
            if n % 5000 == 0:
                print(f"    {n:,}/{len(todo):,}", flush=True)
    print(f"  wrote {PALETTE}  ({n - miss:,} tiles, {miss} unreadable)")
    print(f"  {os.path.getsize(PALETTE)/1048576:.1f} MB")
    return 0


# ---------------------------------------------------------------------------
# families
# ---------------------------------------------------------------------------
# The tile's colour is the most CHROMATIC cluster that still carries real area,
# not the most massive one. On famille rose, faience and blue-and-white the
# most massive cluster is the pale ground, which measures the tile as
# colourless and drops it out of the colour navigation entirely -- the exact
# failure the "dominant not average" rule was written to prevent. Measured over
# 6,000 tiles, mass-picking misfiles 27.6%. See PLAN.md 5.

MIN_MASS = 0.10             # a cluster must hold this much of the tile to speak
CHROMA_FLOOR = 0.035        # ...and be this colourful to outvote sheer area
MASS_WEIGHT = 0.30          # gentle tiebreak toward the larger of two colours


def signature(pal):
    """(L, C, h, rgb) of the cluster a person would name as the tile's colour."""
    if not pal:
        return None
    scored = []
    for r, g, b, m in pal:
        L, a, bb = oklab((r, g, b))
        scored.append((L, math.hypot(a, bb),
                       math.degrees(math.atan2(bb, a)) % 360, (r, g, b), m))
    big = [c for c in scored if c[4] >= MIN_MASS] or scored[:1]
    cand = [c for c in big if c[1] >= CHROMA_FLOOR]
    if not cand:
        return scored[0][:4]
    best = max(cand, key=lambda c: c[1] * (c[4] ** MASS_WEIGHT))
    return best[:4]


# Hue bands in OKLab degrees, tuned against the measured distribution rather
# than chosen a priori -- run `--report` after changing anything here.
#
# Fired clay is orange, so the warm band holds 21,335 tiles and a naive hue
# split hands 40% of the collection to a single terracotta bucket. The measured
# warm band is one tight natural cluster at h~48, L~0.58 -- that spike IS
# terracotta. Slicing through it to hit a size quota would put visually
# identical tiles in different families, which is worse than an uneven rail.
#
# So the warm band is divided where real ceramic distinctions already sit:
#   dark, any warm hue  -> iron red   (oxblood, deep iron slip)
#   yellow-brown hues   -> ochre      (amber, buff, honey glaze)
#   the orange cluster  -> terracotta
# Ochre is a HUE judgement, not a lightness one: amber is amber whether it is
# a pale buff body or a deep honey glaze.

CHROMA_MIN = 0.035          # below this the tile is achromatic
CREAM_L = 0.62              # achromatic: lighter than this is cream

WARM_LO, WARM_HI = 18.0, 95.0
IRON_RED_L = 0.47           # warm + darker than this -> iron red
OCHRE_H = 62.0              # warm + yellower than this -> ochre
CELADON_C = 0.062           # green + less saturated than this -> celadon
                            # (the green band's own median, so the split falls
                            #  where the population actually divides)

FAMILY_ORDER = [
    "cobalt", "turquoise", "celadon", "copper green", "terracotta",
    "iron red", "ochre", "cream", "manganese", "lustre",
]

FAMILY_INK = {
    "cobalt": "#2A4A87", "turquoise": "#2E8C8C", "celadon": "#9DAE96",
    "copper green": "#4C7A3F", "terracotta": "#B4623C", "iron red": "#8A3324",
    "ochre": "#C08A2E", "cream": "#E4DCCB", "manganese": "#3A3238",
    "lustre": "#B08D57",
}


def family(L, C, h, lustrous):
    """Assign one tile to a glaze family. Order is load-bearing."""
    # Lustre is a FINISH, not a hue -- a gold-lustred tile measures as ochre.
    # It is claimed from the medium string (surface == "luster") and only when
    # the tile is actually in the warm metallic range, so a lustred cobalt
    # ground still files under cobalt.
    if lustrous and C >= CHROMA_MIN and WARM_LO <= h < WARM_HI:
        return "lustre"
    if C < CHROMA_MIN:
        return "cream" if L >= CREAM_L else "manganese"
    if 230.0 <= h < 300.0:
        return "cobalt"
    if 175.0 <= h < 230.0:
        return "turquoise"
    if 100.0 <= h < 175.0:
        return "celadon" if C < CELADON_C else "copper green"
    if WARM_LO <= h < WARM_HI:
        if L < IRON_RED_L:
            return "iron red"
        return "ochre" if h >= OCHRE_H else "terracotta"
    # magenta through crimson: the deep reds of the collection
    return "iron red" if L < CREAM_L else "terracotta"


def load_lustre():
    """Object IDs whose medium string names a lustre finish."""
    from classify import classify_surface
    out = set()
    path = os.path.join(DATA, "candidates.jsonl")
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if "luster" in classify_surface(r.get("medium", "")):
                out.add(r["id"])
    return out


def do_families(args):
    lustre = load_lustre()
    print(f"  {len(lustre):,} objects carry a lustre finish in their medium")

    rows = []
    with open(PALETTE) as f:
        for line in f:
            r = json.loads(line)
            s = signature(r["pal"])
            if s is None:
                continue
            L, C, h, rgb = s
            rows.append({
                "id": r["id"], "mono": r["mono"],
                "L": round(L, 4), "C": round(C, 4), "h": round(h, 1),
                "rgb": list(rgb), "avg": r["avg"],
            })
    print(f"  {len(rows):,} tiles measured")

    colour = [r for r in rows if not r["mono"]]
    mono = [r for r in rows if r["mono"]]
    for r in rows:
        r["family"] = (None if r["mono"] else
                       family(r["L"], r["C"], r["h"], r["id"] in lustre))

    counts = collections.Counter(r["family"] for r in colour)
    n = len(colour)

    print(f"\n  {n:,} tiles in the colour navigation "
          f"({len(mono):,} monochrome, held out -- PLAN.md 4e)")
    print(f"  {'family':<14}{'tiles':>8}  share")
    biggest = 0
    for fam in FAMILY_ORDER:
        c = counts.get(fam, 0)
        biggest = max(biggest, c)
        bar = "#" * int(52 * c / max(n, 1))
        print(f"  {fam:<14}{c:>8,}  {100*c/max(n,1):5.1f}%  {bar}")

    print(f"\n  largest family holds {100*biggest/max(n,1):.1f}% "
          f"(target: no family above ~33%, none near-empty)")
    empty = [f for f in FAMILY_ORDER if counts.get(f, 0) < 0.005 * n]
    if empty:
        print(f"  WARNING near-empty: {', '.join(empty)}")

    if args.report:
        return 0

    payload = {
        "families": FAMILY_ORDER,
        "ink": FAMILY_INK,
        "counts": {f: counts.get(f, 0) for f in FAMILY_ORDER},
        "mono": len(mono),
        "tiles": {r["id"]: {"f": r["family"], "L": r["L"], "C": r["C"],
                            "h": r["h"], "rgb": r["rgb"], "m": r["mono"]}
                  for r in rows},
    }
    with open(FAMILIES, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\n  wrote {FAMILIES}  "
          f"({os.path.getsize(FAMILIES)/1048576:.1f} MB)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--workers", type=int, default=max(mp.cpu_count() - 2, 2))
    m.add_argument("--force", action="store_true")
    m.set_defaults(fn=do_measure)
    fa = sub.add_parser("families")
    fa.add_argument("--report", action="store_true",
                    help="print the distribution without writing families.json")
    fa.set_defaults(fn=do_families)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
