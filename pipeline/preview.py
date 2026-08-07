"""Generate a preview image of the rebuilt lookbook.

Not a mockup -- real MET ceramic imagery, really cropped, really sorted by
colour in OKLab, with the navigation and filters drawn in the project's
design language (PLAN.md 7c).

Source imagery is the 1,547 images recovered from commit e55fd0a rather than
the live API: it costs the museum nothing while the crawl runs, and it is
Islamic/Persian-heavy (Iran 658, Iraq 166, Egypt 161), which is the cobalt
and turquoise character the 2019 piece had. The first slice of the live
crawl is 1,766/1,767 The American Wing and would read misleadingly pale.

    python3 pipeline/preview.py
    python3 pipeline/preview.py --crop 0.25 --tile 44
"""

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEGACY = os.path.join(HERE, "data", "legacy_2019.json")
SOURCE_COMMIT = "e55fd0a"

# --- design tokens -----------------------------------------------------------
# Printed-ephemera vocabulary: bone paper, ink, one warm accent. The interface
# palette IS the glaze palette -- cream, ochre, terracotta, celadon and
# manganese are simultaneously UI colours and real ceramic glaze families.

BONE = (243, 241, 236)
PAPER_EDGE = (216, 212, 203)
INK = (38, 38, 35)
MUTED = (146, 143, 134)
FAINT = (186, 182, 172)
ACCENT = (192, 90, 56)      # terracotta

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

MATERIALS = ["fritware", "faience", "terracotta", "ceramic", "pottery",
             "earthenware", "stoneware", "clay", "porcelain"]

SUP = "/System/Library/Fonts/Supplemental/"


# The detail view's subject. Real MET record, fetched once and inlined so
# preview.py stays offline and reproducible.
SUBJECT = {
    "id": "446207",
    "accession": "12.49.4",
    "title": "Tile with Image of Phoenix",
    "objectName": "Tile from a frieze",
    "medium": ("Stonepaste; modeled, underglaze painted in blue and "
               "turquoise, luster-painted on opaque white ground"),
    "date": "late 13th century",
    "place": "Iran, probably Takht-i Sulayman",
    "department": "Islamic Art",
    "dimensions": "H. 14 3/4 in. (37.5 cm)",
    "credit": "Rogers Fund, 1912",
    "type": "fritware",
    "surface": "underglaze · luster",
    "family": "turquoise",
    "familyRGB": (42, 157, 163),
}


def font(kind, size):
    try:
        if kind == "serif":
            return ImageFont.truetype(SUP + "Baskerville.ttc", size)
        if kind == "serif-italic":
            return ImageFont.truetype(SUP + "Baskerville.ttc", size, index=1)
        if kind == "display":
            return ImageFont.truetype(SUP + "Didot.ttc", size)
        if kind == "display-italic":
            return ImageFont.truetype(SUP + "Didot.ttc", size, index=1)
        return ImageFont.truetype(SUP + "Andale Mono.ttf", size)
    except Exception:
        return ImageFont.load_default()


# --- letterspacing -----------------------------------------------------------
# Every label is tracked-out uppercase monospace. PIL has no tracking, so
# glyphs are drawn one at a time.

def tracked(d, xy, s, f, fill, track=2.0):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + track
    return x - track


def tracked_w(d, s, f, track=2.0):
    return sum(d.textlength(c, font=f) for c in s) + track * max(len(s) - 1, 0)


def dashed_circle(d, cx, cy, r, fill, segments=64, on=3, width=1):
    for i in range(segments):
        if i % (on + 1) >= on:
            continue
        d.arc([cx - r, cy - r, cx + r, cy + r],
              360 * i / segments, 360 * (i + 1) / segments,
              fill=fill, width=width)


# --- colour ------------------------------------------------------------------

def srgb_to_oklab(r, g, b):
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
    px = list(im.resize((24, 24), Image.LANCZOS).getdata())
    lum = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in px]
    m = sum(lum) / len(lum)
    return (sum((v - m) ** 2 for v in lum) / len(lum)) ** 0.5


def tile_colour(im):
    px = list(im.resize((16, 16), Image.LANCZOS).getdata())
    r = sum(p[0] for p in px) / len(px)
    g = sum(p[1] for p in px) / len(px)
    b = sum(p[2] for p in px) / len(px)
    L, a, bb = srgb_to_oklab(r, g, b)
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def extract_images(dest):
    tar = os.path.join(dest, "crops.tar")
    with open(tar, "wb") as f:
        subprocess.run(["git", "archive", SOURCE_COMMIT, "resize_crops"],
                       cwd=ROOT, stdout=f, check=True)
    subprocess.run(["tar", "-xf", tar, "-C", dest], check=True)
    d = os.path.join(dest, "resize_crops")
    return [os.path.join(d, n) for n in sorted(os.listdir(d))
            if n.endswith(".png")]


# --- chrome ------------------------------------------------------------------

def draw_sidebar(canvas, x0, H, detail=False):
    """Left paper plane. The chrome never floats over the imagery -- that is
    what makes a delicate interface survive a 51,913-tile colour field."""
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle([0, 0, x0, H], fill=BONE)
    d.line([x0, 0, x0, H], fill=PAPER_EDGE, width=1)

    m = 52
    f_nav, f_meta = font("mono", 12), font("mono", 13)
    f_lbl, f_item = font("mono", 11), font("mono", 13)

    # back affordance: outlined circle + tracked caps
    d.ellipse([m, 46, m + 34, 80], outline=(120, 117, 110), width=1)
    d.line([m + 11, 63, m + 24, 63], fill=INK, width=1)
    d.line([m + 11, 63, m + 16, 58], fill=INK, width=1)
    d.line([m + 11, 63, m + 16, 68], fill=INK, width=1)
    tracked(d, (m + 50, 57), "BACK TO THE GRID" if detail else "ALL OBJECTS",
            f_nav, INK, 2.4)

    # wordmark: roman over italic
    d.text((m - 4, 128), "Ceramic", font=font("display", 60), fill=INK)
    d.text((m - 2, 194), "Lookbook", font=font("display-italic", 60), fill=INK)

    y = 296
    for line in ("Est. 1870", "The Metropolitan Museum", "New York"):
        tracked(d, (m, y), line, f_meta, MUTED, 1.5)
        y += 25

    def section(y, label):
        tracked(d, (m, y), label, f_lbl, FAINT, 3.0)
        w = tracked_w(d, label, f_lbl, 3.0)
        d.line([m + w + 14, y + 6, x0 - 44, y + 6], fill=PAPER_EDGE, width=1)
        return y + 30

    y = section(384, "PALETTE")
    for i, (name, rgb) in enumerate(PALETTE):
        on = i in (0, 1)
        d.ellipse([m, y + 3, m + 12, y + 15], fill=rgb, outline=(0, 0, 0, 45))
        tracked(d, (m + 24, y + 1), name.upper(), f_item,
                INK if on else MUTED, 1.8)
        if on:
            w = tracked_w(d, name.upper(), f_item, 1.8)
            d.line([m + 24, y + 20, m + 24 + w, y + 20], fill=ACCENT, width=1)
        y += 25

    y = section(y + 18, "MATERIAL")
    for mat in MATERIALS:
        on = mat == "fritware"
        if on:
            d.ellipse([m + 2, y + 5, m + 10, y + 13], fill=ACCENT)
        tracked(d, (m + 24, y + 1), mat.upper(), f_item,
                INK if on else MUTED, 1.8)
        y += 25

    y = section(y + 20, "LAYOUT")
    draw_layout_dial(d, m + 4, y - 2, active=1)

    # perforation, the way a receipt tears off
    yy = H - 74
    for xx in range(m, x0 - 44, 6):
        d.line([xx, yy, xx + 3, yy], fill=FAINT, width=1)
    tracked(d, (m, H - 56), "51,913 OBJECTS", font("mono", 11), MUTED, 2.6)


def draw_layout_dial(d, x, y, active=1):
    """The four tessellations, drawn as a row of specimen marks.

    The wheel is the one control that is a *shape* choice, so it is shown as
    shapes rather than words -- and rendered in the same hairline-outline
    idiom as the stamp and the perforation rather than as UI iconography.
    """
    size = 15
    for i in range(4):
        cx = x + i * 42
        cy = y + 8
        col = INK if i == active else FAINT
        w = 2 if i == active else 1
        if i == 0:                                    # rectangle, 3:4
            d.rectangle([cx - 5, cy - size // 2, cx + 5, cy + size // 2],
                        outline=col, width=w)
        elif i == 1:                                  # square
            d.rectangle([cx - 7, cy - 7, cx + 7, cy + 7], outline=col, width=w)
        elif i == 2:                                  # diamond
            d.polygon([(cx, cy - 9), (cx + 9, cy), (cx, cy + 9),
                       (cx - 9, cy)], outline=col)
        else:                                         # hexagon
            pts = [(cx + 8 * math.cos(math.radians(a)),
                    cy + 8 * math.sin(math.radians(a)))
                   for a in range(-90, 270, 60)]
            d.polygon(pts, outline=col)
        if i == active:
            d.line([cx - 10, cy + 16, cx + 10, cy + 16], fill=ACCENT, width=1)


def draw_stamp(canvas, x, y):
    """Rubber-stamp mark -- the reference's OFFICIAL RECEIPT device."""
    d = ImageDraw.Draw(canvas, "RGBA")
    r = 52
    d.ellipse([x - r - 10, y - r - 10, x + r + 10, y + r + 10],
              fill=(243, 241, 236, 236))
    dashed_circle(d, x, y, r, (150, 74, 48, 235))
    f = font("mono", 11)
    for i, line in enumerate(("OPEN", "ACCESS", "· 2026 ·")):
        w = tracked_w(d, line, f, 2.2)
        tracked(d, (x - w / 2, y - 21 + i * 15), line, f,
                (150, 74, 48, 235), 2.2)


def scissors(d, x, y, col):
    """Andale Mono has no U+2702, and a tofu box in the corner of a receipt
    is worse than no mark at all -- so draw it."""
    d.line([x - 9, y - 7, x + 6, y + 5], fill=col, width=1)
    d.line([x - 9, y + 7, x + 6, y - 5], fill=col, width=1)
    d.ellipse([x + 5, y - 9, x + 12, y - 2], outline=col, width=1)
    d.ellipse([x + 5, y + 2, x + 12, y + 9], outline=col, width=1)


def rounded(size, radius, fill):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                                         radius, fill=fill)
    return im


def drop(canvas, card, xy, angle=0, blur=18, alpha=58, offset=(6, 14)):
    """Composite a card with a soft shadow, optionally rotated -- the
    reference stacks its postcard, ticket and receipt at slight angles."""
    if angle:
        card = card.rotate(angle, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    mask = card.split()[-1].point(lambda a: min(a, alpha))
    blk = Image.new("RGBA", card.size, (30, 26, 20, 255))
    blk.putalpha(mask)
    sh.paste(blk, (xy[0] + offset[0], xy[1] + offset[1]), blk)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(sh)
    canvas.alpha_composite(card.convert("RGBA"), xy)


def draw_detail(args):
    """The object page as a catalogue card."""
    W, H = 2100, 1155
    canvas = Image.new("RGBA", (W, H), BONE + (255,))

    with tempfile.TemporaryDirectory() as tmp:
        paths = extract_images(tmp)
        src = next((p for p in paths
                    if os.path.basename(p) == SUBJECT["id"] + ".png"), None)
        plate_src = Image.open(src).convert("RGB") if src else None
        if plate_src is None:
            raise SystemExit("subject image not found in recovered set")
        iw, ih = plate_src.size
        c = int(min(iw, ih) * args.crop)
        swatch = plate_src.crop(((iw - c) // 2, (ih - c) // 2,
                                 (iw + c) // 2, (ih + c) // 2))

        # --- warm card peeking behind, the reference's layered stack ---
        back = rounded((430, 560), 10, (196, 104, 66, 255))
        bd = ImageDraw.Draw(back)
        f_v = font("mono", 12)
        tracked(bd, (26, 500), "THE METROPOLITAN MUSEUM OF ART", f_v,
                (255, 236, 220, 210), 2.2)
        drop(canvas, back, (742, 96), angle=-2.5)

        # --- the plate: image tipped onto a paper mount ---
        pw = 520
        img = plate_src.resize((pw, int(pw * ih / iw)), Image.LANCZOS)
        mount = rounded((pw + 56, img.size[1] + 104), 8, (252, 251, 248, 255))
        mount.paste(img, (28, 28))
        md = ImageDraw.Draw(mount)
        tracked(md, (28, img.size[1] + 50), SUBJECT["accession"],
                font("mono", 13), MUTED, 2.2)
        # No "OPEN ACCESS" here: the stamp on the catalogue card already
        # says it, and the crop chip overlaps this corner.
        drop(canvas, mount, (524, 128), angle=1.2, blur=22, alpha=64)

        # --- the crop tile: what you clicked in the grid ---
        sw = swatch.resize((150, 150), Image.LANCZOS)
        chip = rounded((174, 208), 8, (247, 245, 240, 255))
        chip.paste(sw, (12, 12))
        cd = ImageDraw.Draw(chip)
        tracked(cd, (12, 172), "THE CROP", font("mono", 10), MUTED, 2.4)
        drop(canvas, chip, (1006, 636), angle=-5, blur=16, alpha=54)

    # --- catalogue card ---
    cw, ch = 700, 690
    card = rounded((cw, ch), 10, (206, 208, 205, 255))
    d = ImageDraw.Draw(card, "RGBA")
    f_lbl, f_val = font("mono", 12), font("serif", 23)

    dashed_circle(d, cw - 92, 92, 46, (92, 90, 84, 200))
    for i, line in enumerate(("CERAMICS", "TILES", "· 446207 ·")):
        w = tracked_w(d, line, font("mono", 10), 2.0)
        tracked(d, (cw - 92 - w / 2, 74 + i * 14), line, font("mono", 10),
                (92, 90, 84, 220), 2.0)

    tracked(d, (44, 62), "1912", font("mono", 13), (120, 118, 112), 3.0)

    y = 168
    rows = [("OBJECT", SUBJECT["title"]),
            ("MEDIUM", None),
            ("PLACE", SUBJECT["place"]),
            ("DATE", SUBJECT["date"]),
            ("DEPARTMENT", SUBJECT["department"]),
            ("CREDIT", SUBJECT["credit"])]
    for label, val in rows:
        tracked(d, (44, y), label, f_lbl, (110, 108, 102), 2.6)
        if label == "MEDIUM":
            words, line, ly = SUBJECT["medium"].split(), "", y + 22
            for wd in words:
                t = (line + " " + wd).strip()
                if d.textlength(t, font=font("serif", 20)) > cw - 96:
                    d.text((44, ly), line, font=font("serif", 20), fill=INK)
                    ly += 27
                    line = wd
                else:
                    line = t
            d.text((44, ly), line, font=font("serif", 20), fill=INK)
            y = ly + 46
        else:
            d.text((44, y + 20), val, font=f_val, fill=INK)
            y += 64
        d.line([44, y - 16, cw - 44, y - 16], fill=(176, 178, 174), width=1)

    for xx in range(30, cw - 30, 8):
        d.line([xx, ch - 54, xx + 4, ch - 54], fill=(150, 152, 148), width=1)
    tracked(d, (44, ch - 40), "TEAR HERE FOR THE FULL RECORD",
            font("mono", 10), (120, 118, 112), 2.2)
    scissors(d, cw - 60, ch - 54, (120, 118, 112))
    drop(canvas, card, (1290, 118), angle=-1.2, blur=22, alpha=60)

    # --- three attribute blocks, the reference's info row ---
    d2 = ImageDraw.Draw(canvas, "RGBA")
    blocks = [(SUBJECT["familyRGB"], "Palette", SUBJECT["family"].upper(),
               "dominant glaze family"),
              (ACCENT, "Material", SUBJECT["type"].upper(),
               "stonepaste body"),
              ((60, 58, 54), "Surface", SUBJECT["surface"].upper(),
               "painted, then glazed")]
    bx = 524
    for rgb, head, val, note in blocks:
        d2.ellipse([bx, 920, bx + 34, 954], fill=rgb)
        d2.ellipse([bx + 13, 933, bx + 21, 941], fill=(243, 241, 236))
        d2.text((bx, 980), head, font=font("serif", 25), fill=INK)
        tracked(d2, (bx, 1022), val, font("mono", 13), INK, 2.2)
        tracked(d2, (bx, 1046), note, font("mono", 12), MUTED, 1.6)
        bx += 400

    draw_sidebar(canvas, args.sidebar, H, detail=True)
    canvas.convert("RGB").save(args.out, quality=95)
    print(f"\n  wrote {args.out}  ({W}x{H})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", choices=("grid", "detail"), default="grid")
    ap.add_argument("--tile", type=int, default=55)
    ap.add_argument("--cols", type=int, default=30)
    ap.add_argument("--rows", type=int, default=21)
    ap.add_argument("--sidebar", type=int, default=450)
    ap.add_argument("--hue-start", type=float, default=185)
    ap.add_argument("--crop", type=float, default=0.32)
    ap.add_argument("--out", default=os.path.join(ROOT, "preview.png"))
    args = ap.parse_args()

    if args.view == "detail":
        return draw_detail(args)

    legacy = json.load(open(LEGACY))
    want = args.cols * args.rows

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
            # A tight central patch, NOT a full centre crop: a square centre
            # crop of a whole-object studio shot is still a whole object on
            # backdrop. See PLAN.md stage 3.
            s = int(min(w, h) * args.crop)
            sq = im.crop(((w - s) // 2, (h - s) // 2,
                          (w + s) // 2, (h + s) // 2))
            L, chroma, hue = tile_colour(sq)
            if chroma < 0.022 and L > 0.86 and tile_flatness(sq) < 9.0:
                continue
            tiles.append({"img": sq.resize((args.tile, args.tile),
                                           Image.LANCZOS),
                          "L": L, "chroma": chroma, "hue": hue,
                          "type": legacy.get(oid, {}).get("type", "?")})
        print(f"  {len(tiles)} usable tiles")

        def key(t):
            if t["chroma"] < 0.04:
                return (999, t["L"])
            return (int(((t["hue"] - args.hue_start) % 360) / 9), t["L"])
        tiles.sort(key=key)

        if len(tiles) > want:
            step = len(tiles) / want
            tiles = [tiles[int(i * step)] for i in range(want)]

        W = args.sidebar + args.cols * args.tile
        H = args.rows * args.tile
        canvas = Image.new("RGB", (W, H), BONE)
        for i, t in enumerate(tiles):
            canvas.paste(t["img"], (args.sidebar + (i % args.cols) * args.tile,
                                    (i // args.cols) * args.tile))

        draw_sidebar(canvas, args.sidebar, H)
        draw_stamp(canvas, W - 128, H - 118)
        canvas.save(args.out, quality=95)
        print(f"\n  wrote {args.out}  ({W}x{H})")


if __name__ == "__main__":
    sys.exit(main())
