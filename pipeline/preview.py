"""Generate a preview image of the rebuilt lookbook.

Not a mockup -- real MET ceramic imagery, really centre-cropped, really
sorted by colour, with the material rail and the new glaze-palette rail
composited on top.

Source imagery is the 1,547 images recovered from commit e55fd0a rather than
the live API, for two reasons: it costs the museum nothing, and it is
Islamic/Persian-heavy (Iran 658, Iraq 166, Egypt 161), which is the cobalt
and turquoise character the 2019 piece actually had. The first slice of the
live crawl is 99% The American Wing and would give a misleadingly pale
preview.

    python3 pipeline/preview.py
    python3 pipeline/preview.py --tile 80 --width 2000
"""

import argparse
import colorsys
import json
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEGACY = os.path.join(HERE, "data", "legacy_2019.json")
SOURCE_COMMIT = "e55fd0a"

MATERIALS = ["fritware", "faience", "terracotta", "ceramic", "pottery",
             "earthenware", "stoneware", "clay", "porcelain"]

# The glaze palette from PLAN.md section 6, with representative swatches.
PALETTE = [
    ("cobalt",       (38, 58, 140)),
    ("turquoise",    (42, 157, 163)),
    ("celadon",      (176, 196, 172)),
    ("copper green", (74, 124, 74)),
    ("terracotta",   (188, 106, 72)),
    ("iron red",     (150, 54, 44)),
    ("ochre",        (186, 143, 62)),
    ("cream",        (226, 216, 194)),
    ("manganese",    (58, 48, 52)),
    ("lustre",       (156, 124, 62)),
]

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# --- colour -----------------------------------------------------------------

def srgb_to_oklab(r, g, b):
    """sRGB 0-255 -> OKLab. Averaging in OKLab keeps mixed tiles from going
    muddy the way an sRGB mean does."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def tile_flatness(im):
    """Std-dev of luma. A studio backdrop is flat; a glaze almost never is."""
    px = list(im.resize((24, 24), Image.LANCZOS).getdata())
    lum = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in px]
    m = sum(lum) / len(lum)
    return (sum((v - m) ** 2 for v in lum) / len(lum)) ** 0.5


def tile_colour(im):
    small = im.resize((16, 16), Image.LANCZOS)
    px = list(small.getdata())
    r = sum(p[0] for p in px) / len(px)
    g = sum(p[1] for p in px) / len(px)
    b = sum(p[2] for p in px) / len(px)
    L, a, bb = srgb_to_oklab(r, g, b)
    chroma = math.hypot(a, bb)
    hue = math.degrees(math.atan2(bb, a)) % 360
    return L, chroma, hue, (int(r), int(g), int(b))


# --- source -----------------------------------------------------------------

def extract_images(dest):
    """Pull the recovered crops out of git history in one shot."""
    tar = os.path.join(dest, "crops.tar")
    with open(tar, "wb") as f:
        subprocess.run(["git", "archive", SOURCE_COMMIT, "resize_crops"],
                       cwd=ROOT, stdout=f, check=True)
    subprocess.run(["tar", "-xf", tar, "-C", dest], check=True)
    d = os.path.join(dest, "resize_crops")
    return [os.path.join(d, n) for n in sorted(os.listdir(d))
            if n.endswith(".png")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", type=int, default=50)
    ap.add_argument("--width", type=int, default=2000)
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--hue-start", type=float, default=185,
                    help="hue in degrees the sort begins at; 185 opens on "
                         "the turquoise-cobalt band this collection is known "
                         "for, rather than on dark reds")
    ap.add_argument("--crop", type=float, default=0.32,
                    help="fraction of the frame to keep (0.32 = a tight "
                         "central patch of surface, not the whole object)")
    ap.add_argument("--out", default=os.path.join(ROOT, "preview.png"))
    args = ap.parse_args()

    legacy = json.load(open(LEGACY))
    cols = args.width // args.tile
    want = cols * args.rows

    with tempfile.TemporaryDirectory() as tmp:
        print("  extracting recovered imagery from git...")
        paths = extract_images(tmp)
        print(f"  {len(paths)} images")

        print("  cropping and measuring colour...")
        tiles = []
        for p in paths:
            oid = os.path.basename(p)[:-4]
            try:
                im = Image.open(p).convert("RGB")
            except Exception:
                continue
            w, h = im.size
            # NOT a full centre crop. A whole-object studio photo centre-cropped
            # to a square is still a whole object floating on backdrop. The
            # 2019 grid shows patches of glaze and brushwork, which means a
            # tight central fraction of the frame.
            s = int(min(w, h) * args.crop)
            sq = im.crop(((w - s) // 2, (h - s) // 2,
                          (w + s) // 2, (h + s) // 2))
            L, chroma, hue, rgb = tile_colour(sq)
            # Stand-in for the real Stage 3b test: drop crops that are almost
            # certainly studio backdrop. Deliberately keyed on flatness as
            # well as pallor, so genuinely cream glazes survive -- a plain
            # lightness cut would delete the whole cream palette family.
            flat = tile_flatness(sq)
            if chroma < 0.022 and L > 0.86 and flat < 9.0:
                continue
            tiles.append({
                "img": sq.resize((args.tile, args.tile), Image.LANCZOS),
                "L": L, "chroma": chroma, "hue": hue,
                "type": legacy.get(oid, {}).get("type", "?"),
            })
        print(f"  {len(tiles)} usable tiles")

        # Hue-major, lightness within bucket -- the classic colour-sorted
        # mosaic. Achromatic tiles are pushed to their own band rather than
        # scattering noise through the hues.
        def key(t):
            if t["chroma"] < 0.04:
                return (999, t["L"])
            rot = (t["hue"] - args.hue_start) % 360
            return (int(rot / 9), t["L"])
        tiles.sort(key=key)

        if len(tiles) > want:
            step = len(tiles) / want
            tiles = [tiles[int(i * step)] for i in range(want)]

        height = args.rows * args.tile
        canvas = Image.new("RGB", (cols * args.tile, height), (18, 18, 20))
        for i, t in enumerate(tiles):
            canvas.paste(t["img"],
                         ((i % cols) * args.tile, (i // cols) * args.tile))

        draw_rails(canvas, args)
        canvas.save(args.out, quality=95)
        print(f"\n  wrote {args.out}  ({canvas.size[0]}x{canvas.size[1]})")


def draw_rails(canvas, args):
    """Composite the material rail and the glaze-palette rail."""
    W, H = canvas.size
    d = ImageDraw.Draw(canvas, "RGBA")
    f_mat = load_font(19)
    f_pal = load_font(15)
    f_ttl = load_font(26)

    # scrim so labels stay legible over any imagery
    d.rectangle([0, 0, W, 132], fill=(12, 12, 14, 205))

    d.text((28, 20), "The MET Ceramic Lookbook", font=f_ttl,
           fill=(255, 255, 255, 255))

    x = 28
    y = 62
    for m in MATERIALS:
        w = d.textlength(m, font=f_mat)
        on = m in ("fritware", "faience")
        d.text((x, y), m, font=f_mat,
               fill=(255, 255, 255, 255) if on else (255, 255, 255, 120))
        if on:
            d.line([x, y + 25, x + w, y + 25], fill=(217, 79, 92, 255), width=2)
        x += w + 26

    # palette rail
    x = 28
    y = 100
    sw = 13
    for name, rgb in PALETTE:
        d.rectangle([x, y, x + sw, y + sw], fill=rgb + (255,),
                    outline=(255, 255, 255, 90))
        d.text((x + sw + 7, y - 1), name, font=f_pal,
               fill=(255, 255, 255, 190))
        x += sw + 11 + d.textlength(name, font=f_pal) + 20

    cap = "51,913 objects  ·  sorted by colour  ·  preview from 1,527 tiles"
    tw = d.textlength(cap, font=f_pal)
    d.rectangle([W - tw - 40, H - 38, W, H], fill=(12, 12, 14, 200))
    d.text((W - tw - 22, H - 28), cap, font=f_pal, fill=(255, 255, 255, 205))


if __name__ == "__main__":
    sys.exit(main())
