# -*- coding: utf-8 -*-
"""Figures must fit: nothing clipped inside the image, nothing overflowing
the page it is placed on.

Two independent failures are possible and both happened here. Inside the
image, matplotlib will happily draw a tick label past the canvas edge and
save it half cut off, which is how "$750M" became "$750N". On the page,
an image whose aspect does not match the space reserved for it either
overflows or leaves a third of the page blank.

This checks both: the rendered PNG's ink must stop short of its own border,
and the placed size must fit the text block it goes in.
"""
import re

import numpy as np
from PIL import Image

FIG = "world_development_submission/figures/"
INK = 250          # below this grey value counts as ink, not paper
PAD = 4            # ink must stop this many pixels short of the border

# Text block available to each figure, in inches. Portrait pages are
# 8.5x11 with 1in margins; the landscape environment swaps the two.
PORTRAIT = (6.5, 9.0)
LANDSCAPE = (9.0, 6.5)

PLACED = {
    # file: (page block, placed height in inches, caption lines, label)
    "network_main.png": (LANDSCAPE, 5.35, 4, "Figure 1 (landscape page)"),
    "map_deal_count_v2.png": (PORTRAIT, 3.65, 0, "Figure 2a"),
    "map_dollar_volume_v2.png": (PORTRAIT, 3.65, 0, "Figure 2b"),
}
CAPTION_LINE = 0.25   # 12pt at onehalfspacing, inches
SUBCAP = 0.30

fail = 0
print("== ink clear of the image border ==")
for name in PLACED:
    a = np.array(Image.open(FIG + name).convert("L"))
    h, w = a.shape
    cols = np.where((a < INK).any(axis=0))[0]
    rows = np.where((a < INK).any(axis=1))[0]
    ok = (cols.min() >= PAD and cols.max() < w - PAD
          and rows.min() >= PAD and rows.max() < h - PAD)
    fail += not ok
    print(f"  {name:26s} {w}x{h}  ink x[{cols.min()},{cols.max()}] "
          f"y[{rows.min()},{rows.max()}]  {'OK' if ok else 'CLIPPED'}")

print("\n== placed size fits the page ==")
for name, (block, hin, caplines, label) in PLACED.items():
    im = Image.open(FIG + name)
    aspect = im.size[0] / im.size[1]
    bw, bh = block
    win = hin * aspect
    if win > bw:                      # width-limited instead
        win, hin = bw, bw / aspect
    used = hin + caplines * CAPTION_LINE
    ok = win <= bw + 1e-6 and used <= bh + 1e-6
    fail += not ok
    print(f"  {label:26s} placed {win:.2f} x {hin:.2f}in "
          f"(+{caplines} caption lines = {used:.2f}in) "
          f"in {bw}x{bh}  {'OK' if ok else 'OVERFLOWS'}")

# Figure 2 stacks two maps plus two subcaptions plus the caption.
m = Image.open(FIG + "map_deal_count_v2.png")
asp = m.size[0] / m.size[1]
one_h, one_w = 3.65, 3.65 * (m.size[0] / m.size[1])
stack = 2 * one_h + 2 * SUBCAP + 3 * CAPTION_LINE + 0.15
ok = one_w <= PORTRAIT[0] and stack <= PORTRAIT[1]
fail += not ok
print(f"\n  Figure 2 stacked total  2 x {one_h}in maps ({one_w:.2f}in wide) "
      f"+ subcaptions + caption = {stack:.2f}in of {PORTRAIT[1]}in  "
      f"{'OK' if ok else 'OVERFLOWS'}")

print("\n" + ("ALL FIGURES FIT" if not fail else f"{fail} PROBLEM(S)"))
