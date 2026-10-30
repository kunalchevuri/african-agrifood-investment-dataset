# -*- coding: utf-8 -*-
r"""Catch generated tables that shipped without being formatted.

This exists because nums.py could not catch the bug that motivated it, and
could not have.

nums.py validates numbers in the drafts against a pool built from the
regenerated outputs, and the tables ARE part of that pool. So a wrong number
inside a table validates itself: it is in the pool by definition. When
tab_degree.tex went out reading

    "the {} investors ... the observed ratio is {:.2f} ... Mean degree is
     416.0 for the 5.975804323081047 DFIs and 6.0 for the
     17.037037037037038 other investors"

every check passed. The document compiled, the bibliography was closed, the
word count was fine, and the numbers "verified" against themselves.

A pool-based check cannot audit the pool. These are the signatures that a
table was written without being formatted, checked directly against the
generated files:

1. Python format specs that survived into the output. "{:.2f}" and friends
   are never valid LaTeX, so any occurrence is a bug.
2. Bare "{}" inside the notes text. LaTeX uses empty groups legitimately in
   column specifications like "{@{}c@{}}", so this is checked only inside
   the notes block, where it is always a stray placeholder.
3. Floats printed to more decimals than any table legitimately shows. A
   figure like 5.975804323081047 in prose is a formatting failure, not a
   value anyone chose to report.
"""
import glob
import re

TABLES = sorted(glob.glob("writing/tables/*.tex"))

SPEC = re.compile(r"\{:[^}]*\}")           # {:.2f}, {:,}, {:+.5f}
LONG = re.compile(r"\d+\.\d{7,}")          # unrounded float in output
NOTES = re.compile(r"\\textit\{Notes:\}(.*?)\\end\{minipage\}", re.S)
BARE = re.compile(r"\{\}")

fail = 0
print("== generated tables: formatting survived? ==")
for f in TABLES:
    s = open(f, encoding="utf-8").read()
    bad = []
    for m in SPEC.findall(s):
        bad.append(f"unsubstituted format spec {m}")
    for m in LONG.findall(s):
        bad.append(f"unrounded float {m}")
    note = NOTES.search(s)
    if note and BARE.search(note.group(1)):
        n = len(BARE.findall(note.group(1)))
        bad.append(f"{n} bare '{{}}' placeholder(s) in the notes")
    name = f.replace("\\", "/").split("/")[-1]
    if bad:
        fail += len(bad)
        print(f"  {name}")
        for b in bad:
            print(f"      {b}")
    else:
        print(f"  {name:26s} ok")

print("\n" + ("TABLES CLEAN" if not fail else f"{fail} FORMATTING FAULT(S)"))
raise SystemExit(1 if fail else 0)
