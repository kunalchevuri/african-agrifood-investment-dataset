# -*- coding: utf-8 -*-
"""List every sentence that states a magnitude and cites a source.

Numbers produced by our own pipeline are checked by nums.py against
regenerated output. Numbers taken from someone else's publication cannot be
checked that way, and several of them sit in nums.py's context list, where
they were being skipped rather than verified. This finds them so each one
can be checked against the cited source by hand and recorded.
"""
import glob
import re

CITE = re.compile(r"\\cite[a-zA-Z]*\{([^}]*)\}")
MAG = re.compile(r"\$?([0-9]+(?:[.,][0-9]+)*)\$?\s*"
                 r"(?:percent|billion|million|\\%)")

files = (sorted(glob.glob("writing/*.tex"))
         + ["world_development_submission/main.tex",
            "world_development_submission/supplementary.tex"])

n = 0
for f in files:
    t = re.sub(r"(?m)^%.*", "", open(f, encoding="utf-8").read())
    t = " ".join(t.split())
    for sent in re.split(r"(?<=\.)\s+", t):
        if "cite" not in sent:
            continue
        nums = MAG.findall(sent)
        if not nums:
            continue
        n += 1
        keys = sorted({k.strip() for m in CITE.findall(sent)
                       for k in m.split(",")})
        name = f.replace("\\", "/").split("/")[-1]
        print(f"{n:2d}. [{name}] {nums}  <- {', '.join(keys)}")
        print(f"    {sent[:290].strip()}")
        print()
print(f"{n} cited numeric claims found")
