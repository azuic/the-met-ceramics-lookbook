"""Stage 6 -- emit the browser payload.

Joins the three pipeline artefacts into the files the lookbook actually loads:

    data/meta.json      palette, materials, departments, counts, binary layout
    data/grid.bin       one columnar record per object -- the whole grid
    data/detail/NNN.json  catalogue text, fetched only when a tile is opened

Inputs (either plain or .gz, whichever is present):

    data/colours.jsonl    stage 3 -- crop QC + OKLab colour
    data/candidates.jsonl stage 1 -- classification, department, material
    data/api_objects.jsonl stage 2 -- title, date, image URL

Only objects that passed crop QC *and* carry colour reach the grid. Run:

    python3 pipeline/emit.py
"""

from __future__ import annotations

import gzip
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "pipeline" / "data"
OUT = ROOT / "data"

# --- palette ---------------------------------------------------------------
# Ten families, named in ceramic vocabulary rather than in generic hue buckets.
# The hex is the family's representative swatch (the palette ring and the
# detail card draw it); the boundaries below are what actually assign objects.
FAMILIES = [
    ("cobalt", "#263A8C"),
    ("turquoise", "#2A9DA3"),
    ("celadon", "#B0C4AC"),
    ("copper green", "#4A7C4A"),
    ("terracotta", "#BC6A48"),
    ("iron red", "#96362C"),
    ("ochre", "#BA8F3E"),
    ("lustre", "#9C7C3E"),
    ("cream", "#E2D8C2"),
    ("manganese", "#3A3034"),
]
CO, TU, CE, CG, TE, IR, OC, LU, CR, MA = range(10)

# Surface phrasing per family, used by the detail card when the museum's own
# medium string says nothing about the glaze.
SURFACES = [
    "underglaze cobalt decoration",
    "copper-alkaline glaze",
    "celadon glaze over incised body",
    "copper-green lead glaze",
    "slip-painted body",
    "iron-red glaze",
    "amber lead glaze",
    "overglaze lustre",
    "undecorated buff body",
    "manganese-black glaze",
]


def family(L: float, C: float, h: float) -> int:
    """Assign an OKLCh colour to a glaze family.

    Boundaries are tuned against this collection's own histogram, not fixed a
    priori: the warm 40-100 degree band carries 58% of the objects, so it is
    split on lightness and chroma as well as hue. The result leaves no family
    below 2% or above 28%.
    """
    # Below this chroma the hue angle is photographic noise, so lightness --
    # not hue -- decides. This is the buff/grey body of the collection.
    if C < 0.018:
        return CR if L >= 0.58 else MA
    if h >= 300 or h < 15:
        return MA if (L < 0.42 and C < 0.055) else (IR if L < 0.55 else TE)
    if h < 40:
        return IR if L < 0.54 else TE
    # The orange body band -- the collection's centre of mass.
    if h < 56:
        if L < 0.46:
            return IR
        if C < 0.038 and L >= 0.68:
            return CR
        return TE
    # Amber and yellow-brown; the dark half of it reads as lustre.
    if h < 100:
        if C < 0.040 and L >= 0.68:
            return CR
        return LU if L < 0.50 else OC
    if h < 135:
        if L >= 0.58 and C < 0.055:
            return CE
        return OC if C < 0.045 else CG
    if h < 195:
        return CE if (L >= 0.55 and C < 0.060) else CG
    if h < 240:
        return TU
    return CO


# --- material and department vocabularies ----------------------------------
MATERIALS = [
    "terracotta", "porcelain", "earthenware", "ceramic", "faience",
    "clay", "pottery", "stoneware", "fritware", "other/unspecified",
]

# The nine departments that carry 98% of the collection, plus a tail bucket.
# Short codes are what the receipt and the detail stamp print.
DEPARTMENTS = [
    ("Greek and Roman Art", "GR"),
    ("European Sculpture and Decorative Arts", "ESDA"),
    ("Asian Art", "AS"),
    ("Egyptian Art", "EG"),
    ("Islamic Art", "IS"),
    ("The American Wing", "AW"),
    ("Ancient Near Eastern Art", "ANE"),
    ("Arts of Africa, Oceania, and the Americas", "AOA"),
    ("Medieval Art", "MED"),
]
DEPT_TAIL = ("Everything else", "MISC")
IMAGE_PREFIX = "https://images.metmuseum.org/CRDImages/"
SHARD = 1024


def read_jsonl(stem: str):
    """Yield records from data/<stem>.jsonl, preferring the plain file."""
    plain, packed = DATA / f"{stem}.jsonl", DATA / f"{stem}.jsonl.gz"
    if plain.exists():
        opener = lambda: plain.open()  # noqa: E731
        src = plain
    elif packed.exists():
        opener = lambda: gzip.open(packed, "rt")  # noqa: E731
        src = packed
    else:
        sys.exit(f"emit: missing {plain} (and {packed})")
    print(f"  reading {src.name}")
    with opener() as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def clamp_u8(x: float) -> int:
    return 0 if x < 0 else (255 if x > 255 else int(x))


def main() -> None:
    print("stage 6 -- emit")

    # Colour is the gate: an object without a QC-passing colour crop is not in
    # the grid at all, because the grid has nothing to draw for it.
    colours = {}
    seen = 0
    for d in read_jsonl("colours"):
        seen += 1
        if d.get("ok") and "L" in d:
            colours[d["id"]] = d
    print(f"  {len(colours):,} of {seen:,} objects passed crop QC with colour")

    cands = {d["id"]: d for d in read_jsonl("candidates") if d["id"] in colours}
    api = {}
    for d in read_jsonl("api_objects"):
        oid = str(d["objectID"])
        if oid in colours:
            api[oid] = d

    dept_index = {name: i for i, (name, _) in enumerate(DEPARTMENTS)}
    mat_index = {name: i for i, name in enumerate(MATERIALS)}
    tail_index = len(DEPARTMENTS)

    # Base order is the palette sweep -- family, then hue, then lightness --
    # which is the interface's default sort. Two things fall out of that:
    # the default view needs no sort at all in the browser, and the atlas
    # sheets packed in this same order are contiguous on screen, so a screenful
    # of the default view pulls one or two sheets instead of twenty. The other
    # sorts are still derived from these columns client-side.
    ids = sorted(colours, key=lambda i: (
        family(colours[i]["L"], colours[i]["C"], colours[i]["h"]),
        colours[i]["h"],
        colours[i]["L"],
    ))
    n = len(ids)

    col_id = bytearray()
    col_rgb = bytearray()
    col_mat = bytearray()
    col_dep = bytearray()
    col_fam = bytearray()
    col_mono = bytearray()
    col_l = bytearray()
    col_c = bytearray()
    col_h = bytearray()
    col_year = bytearray()

    mat_counts = [0] * len(MATERIALS)
    dep_counts = [0] * (len(DEPARTMENTS) + 1)
    fam_counts = [0] * len(FAMILIES)
    mono_count = 0
    mono_rescued = 0
    tail_depts = set()
    details = []

    for oid in ids:
        col = colours[oid]
        cand = cands.get(oid, {})
        rec = api.get(oid, {})

        L, C, h = float(col["L"]), float(col["C"]), float(col["h"])
        fam = family(L, C, h)

        # Stage 3 decides "monochrome" from the 95th percentile of the whole
        # photograph's chroma, so a small coloured object on a large grey
        # backdrop reads as greyscale. Six of 6,815 do. The crop is what the
        # grid actually draws, so the crop's own chroma has the last word: if
        # it is plainly coloured, the photograph was not black and white.
        mono = 1 if col.get("mono") else 0
        if mono and C >= 0.018:
            mono = 0
            mono_rescued += 1
        r, g, b = (col.get("rgb") or [128, 128, 128])[:3]

        mat = mat_index.get(cand.get("type", ""), len(MATERIALS) - 1)
        dname = cand.get("department", "")
        if dname in dept_index:
            dep = dept_index[dname]
        else:
            dep = tail_index
            if dname:
                tail_depts.add(dname)

        try:
            year = int(cand.get("beginDate") or 0)
        except (TypeError, ValueError):
            year = 0
        year = max(-32000, min(32000, year))

        col_id += struct.pack("<I", int(oid))
        col_rgb += bytes((r & 255, g & 255, b & 255))
        col_mat.append(mat)
        col_dep.append(dep)
        col_fam.append(fam)
        col_mono.append(mono)
        col_l.append(clamp_u8(L * 255))
        col_c.append(clamp_u8(C * 1000))
        col_h += struct.pack("<H", int(h * 10) % 3600)
        col_year += struct.pack("<h", year)

        mat_counts[mat] += 1
        dep_counts[dep] += 1
        fam_counts[fam] += 1
        mono_count += mono

        image = rec.get("primaryImageSmall") or ""
        if image.startswith(IMAGE_PREFIX):
            image = image[len(IMAGE_PREFIX):]
        elif image:
            image = "!" + image  # absolute, kept verbatim
        details.append([
            cand.get("title", "") or rec.get("title", ""),
            cand.get("medium", ""),
            rec.get("objectDate", "") or cand.get("objectDate", ""),
            cand.get("culture", "") or rec.get("culture", ""),
            cand.get("country", "") or cand.get("region", ""),
            cand.get("objectName", ""),
            image,
        ])

    # --- grid.bin ----------------------------------------------------------
    # Columnar, each column 4-byte aligned so the browser can wrap it in a
    # typed array with no copying.
    columns = [
        ("id", "Uint32", col_id), ("rgb", "Uint8", col_rgb),
        ("mat", "Uint8", col_mat), ("dep", "Uint8", col_dep),
        ("fam", "Uint8", col_fam), ("mono", "Uint8", col_mono),
        ("L", "Uint8", col_l), ("C", "Uint8", col_c),
        ("h", "Uint16", col_h), ("year", "Int16", col_year),
    ]
    blob = bytearray()
    layout = {}
    for name, kind, data in columns:
        while len(blob) % 4:
            blob.append(0)
        layout[name] = {"offset": len(blob), "type": kind}
        blob += data

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "grid.bin").write_bytes(bytes(blob))

    # --- detail shards -----------------------------------------------------
    shard_dir = OUT / "detail"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for old in shard_dir.glob("*.json"):
        old.unlink()
    shards = 0
    for start in range(0, n, SHARD):
        chunk = details[start:start + SHARD]
        path = shard_dir / f"{start // SHARD:03d}.json"
        path.write_text(json.dumps(chunk, separators=(",", ":"), ensure_ascii=False))
        shards += 1

    # --- meta.json ---------------------------------------------------------
    meta = {
        "count": n,
        "scanned": seen,
        "generated": "stage 6",
        "shard": SHARD,
        "shards": shards,
        "imagePrefix": IMAGE_PREFIX,
        "layout": layout,
        "scale": {"L": 255, "C": 1000, "h": 10},
        "monoCount": mono_count,
        "families": [
            {"name": nm, "hex": hx, "surface": SURFACES[i], "count": fam_counts[i]}
            for i, (nm, hx) in enumerate(FAMILIES)
        ],
        "materials": [
            {"name": nm, "count": mat_counts[i]} for i, nm in enumerate(MATERIALS)
        ],
        "departments": [
            {"name": nm, "short": sh, "count": dep_counts[i]}
            for i, (nm, sh) in enumerate(DEPARTMENTS)
        ] + [{
            "name": DEPT_TAIL[0], "short": DEPT_TAIL[1],
            "count": dep_counts[tail_index],
            "note": f"{len(tail_depts)} depts, <400 ea.",
        }],
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))

    size = (OUT / "grid.bin").stat().st_size
    print(f"  grid.bin   {size / 1024:,.0f} KB  ({n:,} objects)")
    print(f"  detail/    {shards} shards of {SHARD}")
    print(f"  monochrome {mono_count:,} ({100 * mono_count / n:.1f}%)"
          + (f"  [{mono_rescued} reclassified as colour]" if mono_rescued else ""))
    print("  palette:")
    for i, (nm, _) in enumerate(FAMILIES):
        c = fam_counts[i]
        print(f"    {nm:14s}{c:7,}  {100 * c / n:5.1f}%")


if __name__ == "__main__":
    main()
