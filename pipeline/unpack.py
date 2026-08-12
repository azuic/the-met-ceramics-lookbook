"""Recover the tile cache by unpacking atlas sheets back into loose tiles.

The tile cache is the expensive artefact in this pipeline -- 44,357 images
fetched one at a time from the MET's CDN. It is gitignored, which means it can
be destroyed by an ordinary git operation while every committed file survives.
That happened: `pipeline/cache` was once committed as a symlink, and checking
that branch out in the main worktree pointed the link at itself, so git removed
the directory underneath to make room.

An atlas sheet is a lossless-enough record of the tiles that went into it, so
the cache can be rebuilt from a packed atlas plus the order it was packed in,
with no network at all.

This costs one extra lossy generation: the tiles were q64, the atlas re-encoded
them, and packing the recovered tiles re-encodes once more. Tiles are written
at q92 so this step contributes almost nothing of its own, but the atlas pass
it undoes is already baked in. Prefer a real re-fetch if the tiles are destined
for a shipped atlas and the traffic is affordable.

    python3 pipeline/unpack.py --manifest pipeline/data/atlas.json \
                               --atlases /path/to/atlases
"""

import argparse
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TILES = os.path.join(HERE, "cache", "tiles")

# High enough that this pass is not the binding constraint on quality. These
# are a local cache, never shipped, so size matters less than fidelity.
QUALITY = 92


def unpack_tier(order, atlas_dir, px, per_row, per_atlas, n_atlas, force):
    out_dir = os.path.join(TILES, str(px))
    os.makedirs(out_dir, exist_ok=True)
    written = skipped = 0
    for a in range(n_atlas):
        path = os.path.join(atlas_dir, str(px), f"{a:03d}.webp")
        if not os.path.exists(path):
            print(f"    missing sheet {path}", file=sys.stderr)
            continue
        sheet = Image.open(path).convert("RGB")
        chunk = order[a * per_atlas:(a + 1) * per_atlas]
        for k, oid in enumerate(chunk):
            dest = os.path.join(out_dir, f"{oid}.webp")
            if not force and os.path.exists(dest):
                skipped += 1
                continue
            x, y = (k % per_row) * px, (k // per_row) * px
            sheet.crop((x, y, x + px, y + px)).save(
                dest, "WEBP", quality=QUALITY, method=6)
            written += 1
        sheet.close()
        print(f"    {px}px sheet {a + 1}/{n_atlas}", flush=True)
    return written, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True,
                    help="atlas.json carrying the packing order")
    ap.add_argument("--atlases", required=True,
                    help="directory holding <px>/NNN.webp sheets")
    ap.add_argument("--force", action="store_true",
                    help="overwrite tiles that are already present")
    args = ap.parse_args()

    with open(args.manifest) as f:
        man = json.load(f)
    order = man["order"]
    print(f"  {len(order):,} tiles in the manifest order")

    for key, tier in sorted(man["tiers"].items(), key=lambda kv: -int(kv[0])):
        px = tier["px"]
        w, s = unpack_tier(order, args.atlases, px, tier["per_row"],
                           tier["per_atlas"], tier["atlases"], args.force)
        have = len(os.listdir(os.path.join(TILES, str(px))))
        print(f"  {px}px: wrote {w:,}, skipped {s:,} -> {have:,} tiles on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
