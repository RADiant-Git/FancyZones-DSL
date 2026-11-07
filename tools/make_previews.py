#!/usr/bin/env python3
"""Regenerate Images/preview.png from the real compiler output.

Every rectangle in the picture comes from ``FZCompiler.compile()``, so the README
illustration can never drift away from what the plugin actually produces.

Usage, from the repository root::

    python tools/make_previews.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fz_compiler import FZCompiler  # noqa: E402

# (formula, caption tag). Compiled with spacing 0; the visual gap between zones
# is added at draw time, so the geometry below is exactly the layout geometry.
FORMULAS = [
    ("1+2+1", "columns"),
    ("1(3)+2(2)", "weights"),
    ("2x3", "grid"),
    ("A A B | C . B | D D D", "matrix + void"),
    ("0(1) + {0(1):2:0(1)}(2) + 0(1)", "floating centre"),
    ("1+2 > 1", "layers"),
]

BG = (13, 17, 23)
PANEL = (22, 27, 34)
FRAME = (48, 54, 61)
CODE = (121, 192, 255)
MUTED = (139, 148, 158)
LABEL = (13, 17, 23)

PALETTE = [
    (121, 192, 255),  # blue
    (86, 211, 100),   # green
    (227, 179, 65),   # yellow
    (255, 123, 114),  # red
    (210, 168, 255),  # purple
    (57, 197, 207),   # teal
    (240, 136, 62),   # orange
    (219, 97, 162),   # pink
]

MON_W, MON_H = 344, 194
PAD = 18
CAPTION_H = 40
GAP_X, GAP_Y = 26, 26
MARGIN = 34
COLS = 3
ZONE_GAP = 3
SOLID = 232
OVERLAP = 96

FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def rects_of(layout):
    """Normalized (x0, y0, x1, y1) rectangles, in zone order."""
    info = layout["info"]

    if layout["type"] == "canvas":
        rw = info.get("ref-width", 10000) or 10000
        rh = info.get("ref-height", 10000) or 10000
        return [
            (
                z["X"] / rw,
                z["Y"] / rh,
                (z["X"] + z["width"]) / rw,
                (z["Y"] + z["height"]) / rh,
            )
            for z in info["zones"]
        ]

    rows_pct = info["rows-percentage"]
    cols_pct = info["columns-percentage"]
    cell_map = info["cell-child-map"]

    def edges(pcts):
        out, acc = [0.0], 0
        for p in pcts:
            acc += p
            out.append(acc / 10000.0)
        return out

    ry, cx = edges(rows_pct), edges(cols_pct)

    bounds = {}
    for r, row in enumerate(cell_map):
        for c, zid in enumerate(row):
            if zid < 0:
                continue
            b = bounds.setdefault(zid, [r, r, c, c])
            b[0], b[1] = min(b[0], r), max(b[1], r)
            b[2], b[3] = min(b[2], c), max(b[3], c)

    return [
        (cx[b[2]], ry[b[0]], cx[b[3] + 1], ry[b[1] + 1])
        for b in (bounds[k] for k in sorted(bounds))
    ]


def fits(draw, text, size, limit):
    """Largest Consolas size, no bigger than `size`, that keeps text under `limit`."""
    for s in range(size, 11, -1):
        if draw.textlength(text, font=font("consola.ttf", s)) <= limit:
            return s
    return 12


def draw_panel(img, origin, formula, tag, f_tag, f_label):
    x0, y0 = origin
    x0 += PAD
    y0 += CAPTION_H

    d = ImageDraw.Draw(img)
    d.text((x0 + MON_W, y0 - CAPTION_H + 12), tag, font=f_tag, fill=MUTED, anchor="ra")
    tag_w = d.textlength(tag, font=f_tag)
    size = fits(d, formula, 16, MON_W - tag_w - 14)
    d.text((x0, y0 - CAPTION_H + 8), formula, font=font("consola.ttf", size), fill=CODE)

    d.rounded_rectangle(
        (x0 - 2, y0 - 2, x0 + MON_W + 2, y0 + MON_H + 2),
        radius=10,
        fill=PANEL,
        outline=FRAME,
        width=2,
    )

    zones = Image.new("RGBA", img.size, (0, 0, 0, 0))
    zd = ImageDraw.Draw(zones)

    placed = []
    for i, (rx0, ry0, rx1, ry1) in enumerate(rects_of(compile(formula))):
        color = PALETTE[i % len(PALETTE)]
        zx0 = x0 + rx0 * MON_W + ZONE_GAP
        zy0 = y0 + ry0 * MON_H + ZONE_GAP
        zx1 = x0 + rx1 * MON_W - ZONE_GAP
        zy1 = y0 + ry1 * MON_H - ZONE_GAP
        if zx1 <= zx0 or zy1 <= zy0:
            continue

        # A zone drawn on top of an earlier one is the point of the '>' operator,
        # so it stays translucent and gets a bright outline instead of hiding them.
        overlaps = any(
            zx0 < px1 and px0 < zx1 and zy0 < py1 and py0 < zy1
            for px0, py0, px1, py1 in placed
        )
        zd.rounded_rectangle(
            (zx0, zy0, zx1, zy1),
            radius=5,
            fill=color + (OVERLAP if overlaps else SOLID,),
            outline=color + (255,) if overlaps else None,
            width=2 if overlaps else 0,
        )
        zd.text(
            ((zx0 + zx1) / 2, (zy0 + zy1) / 2),
            str(i),
            font=f_label,
            fill=LABEL,
            anchor="mm",
        )
        placed.append((zx0, zy0, zx1, zy1))

    img.alpha_composite(zones)


def compile(formula):
    parsed, err = FZCompiler.parse_command(f"{formula} -s 0")
    if err:
        raise SystemExit(f"parse failed for {formula!r}: {err}")
    layout, err = FZCompiler.compile(parsed)
    if err:
        raise SystemExit(f"compile failed for {formula!r}: {err}")
    return layout


def main():
    rows = (len(FORMULAS) + COLS - 1) // COLS
    cell_w, cell_h = MON_W + PAD * 2, MON_H + PAD * 2 + CAPTION_H
    width = MARGIN * 2 + COLS * cell_w + (COLS - 1) * GAP_X
    height = MARGIN * 2 + rows * cell_h + (rows - 1) * GAP_Y

    img = Image.new("RGBA", (width, height), BG + (255,))
    f_tag = font("segoeui.ttf", 14)
    f_label = font("seguisb.ttf", 16)

    for n, (formula, tag) in enumerate(FORMULAS):
        r, c = divmod(n, COLS)
        draw_panel(
            img,
            (MARGIN + c * (cell_w + GAP_X), MARGIN + r * (cell_h + GAP_Y)),
            formula,
            tag,
            f_tag,
            f_label,
        )

    out = os.path.join(ROOT, "Images", "preview.png")
    img.convert("RGB").save(out, optimize=True)
    print(f"wrote {out}  {width}x{height}  {os.path.getsize(out)} bytes")


if __name__ == "__main__":
    main()
