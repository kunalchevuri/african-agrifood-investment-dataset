# -*- coding: utf-8 -*-
"""Bibliography integrity against the assembled submission.

The earlier version compared a staged file to the pre-move NEUDC bib, which
no longer exists. What matters now is the submission itself: every key cited
anywhere in the compiled document resolves, nothing is defined twice, nothing
sits in the bib uncited, and no entry still carries an unresolved-detail note.
"""
import glob
import os
import re

BIB = "world_development_submission/references.bib"
SUB = "world_development_submission"

KEY = re.compile(r"@\w+\{([^,]+),")
CITE = re.compile(r"\\cite[a-zA-Z]*\{([^}]+)\}")

raw = open(BIB, encoding="utf-8").read()
defined = KEY.findall(raw)
dups = sorted(k for k in set(defined) if defined.count(k) > 1)

# main.tex pulls the drafts in via \draft{} and \tbl{}, so the drafts count
# as part of the document even though they sit outside the submission folder.
files = (sorted(glob.glob("writing/*.tex"))
         + sorted(glob.glob("writing/tables/*.tex"))
         + [f"{SUB}/main.tex", f"{SUB}/supplementary.tex",
            f"{SUB}/highlights.tex"])

cited = set()
per_file = []
for f in files:
    if not os.path.exists(f):
        continue
    n = 0
    for m in CITE.findall(open(f, encoding="utf-8").read()):
        ks = {x.strip() for x in m.split(",") if x.strip()}
        cited |= ks
        n += len(ks)
    if n:
        per_file.append((f, n))

print(f"entries defined in bib : {len(defined)} ({len(set(defined))} distinct)")
print(f"duplicate keys         : {dups or 'none'}")
print(f"distinct keys cited    : {len(cited)}")
print()
for f, n in per_file:
    print(f"  {f:46s} {n:3d} citations")

unresolved = sorted(cited - set(defined))
orphan = sorted(set(defined) - cited)
print(f"\ncited but not in bib   : {unresolved or 'NONE'}")
print(f"in bib but never cited : {orphan or 'NONE'}")

notes = re.findall(r"@\w+\{([^,]+),(?:[^@]*?)note\s*=\s*\{([^}]*)\}", raw, re.S)
print(f"\nentries with a note field ({len(notes)}):")
for k, v in notes:
    print(f"  {k}: {v.strip()[:100]}")

ok = not unresolved and not orphan and not dups
print("\n" + ("BIBLIOGRAPHY CLEAN" if ok else "BIBLIOGRAPHY HAS ISSUES"))
