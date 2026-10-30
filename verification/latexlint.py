# -*- coding: utf-8 -*-
"""Source-level LaTeX hazards that compile cleanly but render wrong.

Both of these were introduced by re-wrapping paragraphs during editing, and
neither produces a warning from pdflatex:

  1. a line ending in "--"  -> "2015-- 2020"
  2. a line ending in "-"   -> "agriculture- linked"

Also checks the rules this project has committed to: no em-dashes, and no
duplicate labels across the assembled document.
"""
import glob
import os
import re

# Generated copies of the submission must be skipped. The Overleaf outputs
# duplicate main.tex and every draft, so scanning them reports all 47 labels
# as duplicates of themselves. They are artifacts of the sources checked
# here, not additional sources.
GENERATED = ("overleaf_single_main.tex", "overleaf_bundle")

FILES = sorted(f for f in (glob.glob("writing/*.tex")
                           + glob.glob("writing/tables/*.tex")
                           + glob.glob("world_development_submission/*.tex"))
               if not any(g in f.replace("\\", "/") for g in GENERATED))

fail = 0

print("== ranges/hyphens broken across a line ==")
hits = 0
for f in FILES:
    for i, ln in enumerate(open(f, encoding="utf-8").read().split("\n"), 1):
        # a numeric range split at the dash ("2015--" / "2020"); a bare
        # " -- " with spaces is a legitimate dash (CRediT roles) and is
        # left alone.
        r = ln.rstrip()
        if re.search(r"[0-9]--$", r) or re.search(r"[a-zA-Z]-$", r):
            print(f"  {f}:{i}  ...{ln.strip()[-58:]}")
            hits += 1
print(f"  {hits} found" + ("" if hits == 0 else "   <-- FIX"))
fail += hits

print("\n== em-dashes ==")
# Two ways to get one, and only the first was being counted. LaTeX renders
# "---" as an em-dash just as surely as U+2014 does, so a draft could break
# the project's no-em-dash rule and pass this check. Exactly three hyphens:
# "--" is a legitimate en-dash for numeric ranges and must not match.
hits = 0
LIG = re.compile(r"(?<!-)---(?!-)")
for f in FILES:
    s = open(f, encoding="utf-8").read()
    n_uni = s.count("\u2014")
    n_lig = len(LIG.findall(s))
    if n_uni or n_lig:
        detail = []
        if n_uni:
            detail.append(f"{n_uni} U+2014")
        if n_lig:
            detail.append(f"{n_lig} '---'")
        print(f"  {f}: {', '.join(detail)}")
        hits += n_uni + n_lig
print(f"  {hits} found" + ("" if hits == 0 else "   <-- FIX"))
fail += hits

print("\n== duplicate labels ==")
labels = {}
for f in FILES:
    for m in re.finditer(r"\\label\{([^}]+)\}", open(f, encoding="utf-8").read()):
        labels.setdefault(m.group(1), []).append(os.path.basename(f))
dups = {k: v for k, v in labels.items() if len(v) > 1}
for k, v in dups.items():
    print(f"  {k}: {v}")
print(f"  {len(dups)} found" + ("" if not dups else "   <-- FIX"))
fail += len(dups)

print("\n== malformed \\label (backslash eaten by sed) ==")
hits = 0
for f in FILES:
    for i, ln in enumerate(open(f, encoding="utf-8").read().split("\n"), 1):
        if re.match(r"^\s*abel\{|^\s*[a-z]+ection\{", ln):
            print(f"  {f}:{i}  {ln.strip()[:60]}")
            hits += 1
print(f"  {hits} found" + ("" if hits == 0 else "   <-- FIX"))
fail += hits

print("\n== doubled backslash before a command (prose line break + literal) ==")
# The sibling of the check above. An edit script that escapes its replacement
# text with .replace("\\", "\\\\") doubles every backslash in the passage it
# rewrites, and re.sub inserts that literally when given a function. The
# result compiles silently: "\\citep{x}" is a line break followed by the words
# "citep x", and "Section~\\ref{y}" prints the label instead of the number.
# Nine of these reached the compiled PDF before this check existed.
# A \\ inside a tabular is a real row break, so those are stripped first.
TABULAR = re.compile(r"(?s)\\begin\{tabular\}.*?\\end\{tabular\}")
hits = 0
for f in FILES:
    s = open(f, encoding="utf-8").read()
    # keep line numbers by replacing each tabular with its own newlines
    s = TABULAR.sub(lambda m: "\n" * m.group(0).count("\n"), s)
    for m in re.finditer(r"\\\\([a-zA-Z]+)", s):
        print(f"  {f}:{s[:m.start()].count(chr(10)) + 1}  \\\\{m.group(1)}")
        hits += 1
print(f"  {hits} found" + ("" if hits == 0 else "   <-- FIX"))
fail += hits

print(f"\n{'ALL CLEAN' if fail == 0 else str(fail) + ' ISSUE(S)'}")
raise SystemExit(1 if fail else 0)
