"""Stage 5 -- pack the 96px crops into atlas sheets.

Stage 3 wrote one WebP per object into `cache/tiles/96/`. 44,171 separate
requests is not a thing a browser will do, so they are packed into a handful of
large sheets and the grid blits from them.

The packing order is `data/grid.bin`'s own order, which `emit.py` sorts as the
palette sweep. That is the whole trick: the default view is contiguous in the
sheets, so a screenful pulls one or two of them rather than twenty. Other sorts
and filters scatter across sheets and load progressively, drawing each object's
flat colour until its sheet arrives.

Run after `emit.py`:

    python3 pipeline/emit.py
    python3 pipeline/atlas.py
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TILES = ROOT / "pipeline" / "cache" / "tiles" / "96"
OUT = ROOT / "data"
SHEETS = OUT / "atlas"

# 2016x2016 sheets rather than a few huge ones. A sheet costs width*height*4
# bytes once decoded, so 4032px sheets are 65 MB of live memory each and the
# browser cannot hold enough of them to matter; at 2016px a sheet is 16 MB and
# the resident set can be evicted at a useful granularity.
TILE = 96
COLS = 21
ROWS = 21
PER_SHEET = COLS * ROWS          # 441 tiles in a 2016x2016 sheet
QUALITY = 82
PAPER = (243, 241, 236)          # the field's own background


def build_preview(index: dict) -> None:
    """Downsample each crop separately so neighbours never bleed into it.

    Uses the published sheets, so the small tier can also be rebuilt without
    the original crop cache: python3 pipeline/atlas.py --preview-only.
    """
    tile, cols = 16, 64
    per = cols * cols
    n = index["count"]
    folder = OUT / "atlas-preview"
    folder.mkdir(parents=True, exist_ok=True)
    sheet = None
    source_number = -1
    source = None
    total_bytes = 0
    decoded_bytes = 0
    for i in range(n):
        k = i % per
        if k == 0:
            rows = (min(per, n - i) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * tile, rows * tile), PAPER)
            decoded_bytes += sheet.width * sheet.height * 4
        src_n, src_k = divmod(i, index["perSheet"])
        if src_n != source_number:
            if source is not None:
                source.close()
            source = Image.open(SHEETS / f"{src_n:03d}.webp").convert("RGB")
            source_number = src_n
        size = index["tile"]
        x, y = (src_k % index["cols"]) * size, (src_k // index["cols"]) * size
        thumb = source.crop((x, y, x + size, y + size)).resize((tile, tile), Image.Resampling.LANCZOS)
        sheet.paste(thumb, ((k % cols) * tile, (k // cols) * tile))
        if k == per - 1 or i == n - 1:
            out = folder / f"{i // per:03d}.webp"
            sheet.save(out, "WEBP", quality=65, method=6)
            total_bytes += out.stat().st_size
            print(f"  preview {out.name}: {out.stat().st_size / 1024:.0f} KB", flush=True)
    if source is not None:
        source.close()
    index["preview"] = {
        "tile": tile, "cols": cols, "perSheet": per,
        "sheets": (n + per - 1) // per,
        "bytes": total_bytes, "decodedBytes": decoded_bytes,
    }
    (OUT / "atlas.json").write_text(json.dumps(index, indent=1))
    print(f"  preview total: {total_bytes / 1e6:.2f} MB transfer, {decoded_bytes / 1048576:.1f} MiB decoded")


def main() -> None:
    print("stage 5 -- atlas")
    if "--preview-only" in sys.argv:
        index = json.loads((OUT / "atlas.json").read_text())
        meta = json.loads((OUT / "meta.json").read_text())
        ids = struct.unpack_from("<%dI" % meta["count"], (OUT / "grid.bin").read_bytes(), meta["layout"]["id"]["offset"])
        if (index["count"], index["firstId"], index["lastId"]) != (len(ids), ids[0], ids[-1]):
            sys.exit("atlas: stale source sheets — rebuild the full atlas first")
        build_preview(index)
        return
    meta_path = OUT / "meta.json"
    grid_path = OUT / "grid.bin"
    if not meta_path.exists() or not grid_path.exists():
        sys.exit("atlas: run pipeline/emit.py first")
    if not TILES.is_dir():
        sys.exit(f"atlas: no crops at {TILES} -- run pipeline/tiles.py")

    meta = json.loads(meta_path.read_text())
    n = meta["count"]
    blob = grid_path.read_bytes()
    off = meta["layout"]["id"]["offset"]
    ids = struct.unpack_from("<%dI" % n, blob, off)

    sheets = (n + PER_SHEET - 1) // PER_SHEET
    print(f"  {n:,} tiles -> {sheets} sheets of {PER_SHEET} ({COLS}x{ROWS} at {TILE}px)")

    SHEETS.mkdir(parents=True, exist_ok=True)
    for old in SHEETS.glob("*.webp"):
        old.unlink()

    missing = 0
    total_bytes = 0
    for s in range(sheets):
        start = s * PER_SHEET
        chunk = ids[start:start + PER_SHEET]
        sheet = Image.new("RGB", (COLS * TILE, ROWS * TILE), PAPER)
        for k, oid in enumerate(chunk):
            path = TILES / f"{oid}.webp"
            if not path.exists():
                missing += 1
                continue
            with Image.open(path) as im:
                im = im.convert("RGB")
                if im.size != (TILE, TILE):
                    im = im.resize((TILE, TILE), Image.LANCZOS)
                sheet.paste(im, ((k % COLS) * TILE, (k // COLS) * TILE))
        out = SHEETS / f"{s:03d}.webp"
        sheet.save(out, "WEBP", quality=QUALITY, method=6)
        total_bytes += out.stat().st_size
        print(f"  {out.name}  {len(chunk):>5} tiles  {out.stat().st_size / 1e6:5.2f} MB")

    index = {
        "tile": TILE,
        "cols": COLS,
        "rows": ROWS,
        "perSheet": PER_SHEET,
        "sheets": sheets,
        # Guards against a stale atlas after emit.py reorders: the browser
        # checks these against grid.bin and falls back to flat colour if the
        # packing no longer matches.
        "count": n,
        "firstId": ids[0],
        "lastId": ids[-1],
    }
    (OUT / "atlas.json").write_text(json.dumps(index, indent=1))

    print(f"  total {total_bytes / 1e6:.1f} MB across {sheets} sheets")
    if missing:
        print(f"  WARNING: {missing:,} crops missing from {TILES}")
    build_preview(index)


if __name__ == "__main__":
    main()
