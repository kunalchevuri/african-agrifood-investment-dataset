# -*- coding: utf-8 -*-
"""World Development highlights: 3-5 bullets, each short enough for the
Elsevier limit. Checked at 85 chars including spaces (the strict reading)."""
import re

s = open("world_development_submission/highlights.tex", encoding="utf-8").read()
items = []
for line in s.split("\n"):
    line = line.strip()
    if not line.startswith(r"\item"):
        continue
    t = line[len(r"\item"):]
    t = t.split("%")[0] if "\\%" not in t else re.sub(r"\s+%\s*\d+\s*$", "", t)
    t = t.replace("\\%", "%").strip()
    items.append(t)

print("Highlight character counts (Elsevier limit: 85 incl. spaces):")
ok = True
for i, t in enumerate(items, 1):
    n, ns = len(t), len(t.replace(" ", ""))
    if n > 85:
        ok = False
    print(f"  {i}. {'OK  ' if n <= 85 else 'OVER'} {n:3d} incl / {ns:3d} excl   {t}")
print(f"\n  count {len(items)} (must be 3-5): "
      f"{'OK' if 3 <= len(items) <= 5 else 'FAIL'}")
print(f"  all <=85 incl. spaces: {'OK' if ok else 'FAIL'}")
