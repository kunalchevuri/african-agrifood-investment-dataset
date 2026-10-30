# -*- coding: utf-8 -*-
"""
run_all.py

Runs every verification check and reports one verdict.

    python verification/run_all.py        (from the repository root)

These checks assume the pipeline has already been run, since most of them
compare what the paper claims against what the pipeline produced. Rebuild
first if the data or drafts have changed:

    python pipeline/master_pipeline.py
    python pipeline/analysis.py
    python pipeline/tables.py && python pipeline/tables_carried.py
    python pipeline/window_check.py
    python pipeline/figures.py

A check passes only if it exits zero AND prints every marker below. Requiring
the success markers rather than listing failure strings is deliberate: the
first version of this file looked for failure text that latexlint never
emits, so that check could only ever pass. Absence of a success marker now
fails the check, which also catches a script that crashes or has its output
reworded.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# script -> (markers that must ALL appear, what the check establishes)
CHECKS = [
    ("nums.py", ["0 unaccounted for"],
     "numeric claims trace to regenerated output"),
    ("gentables.py", ["TABLES CLEAN"],
     "generated tables actually got formatted"),
    ("refcheck.py", ["BIBLIOGRAPHY CLEAN"],
     "bibliography is closed"),
    ("latexlint.py", ["ALL CLEAN"],
     "no em-dashes, duplicate labels or break hazards"),
    ("figfit.py", ["ALL FIGURES FIT"],
     "figures are unclipped and fit their pages"),
    ("wdcount.py", ["WITHIN RANGE", "abstract:"],
     "body words inside the World Development window"),
    ("hl.py", ["(must be 3-5): OK", "all <=85 incl. spaces: OK"],
     "highlights within count and character limits"),
    ("suppxref.py", ["0 unresolved"],
     "supplementary's hand-typed main-text refs resolve"),
]

width = max(len(d) for _, _, d in CHECKS)
failed = []
for script, need, desc in CHECKS:
    r = subprocess.run([sys.executable, os.path.join(HERE, script)],
                       cwd=ROOT, capture_output=True, text=True)
    out = r.stdout + r.stderr
    missing = [m for m in need if m not in out]
    ok = r.returncode == 0 and not missing
    print(f"  {'PASS' if ok else 'FAIL'}  {desc:{width}}  ({script})")
    if not ok:
        why = (f"exit {r.returncode}" if r.returncode
               else "missing marker: " + "; ".join(missing))
        failed.append((script, why, out))

print()
if failed:
    for script, why, out in failed:
        print("=" * 70)
        print(f"{script}  --  {why}")
        print("=" * 70)
        print(out.strip()[-2500:])
        print()
    print(f"{len(failed)} CHECK(S) FAILED")
    sys.exit(1)

print("ALL CHECKS PASS")
print("\nNot covered here, and still to be done by hand before submission:")
print("  - the data repository DOI (Elsevier research-data Option C)")
print("  - numbers taken from cited sources: see")
print("    world_development_submission/EXTERNAL_CLAIMS.md")
