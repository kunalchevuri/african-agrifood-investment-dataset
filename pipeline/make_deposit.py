# -*- coding: utf-8 -*-
"""Build the Zenodo deposit from the working tree.

Version 1.0 was assembled by hand, which is why nobody noticed that the
validation sample inside it had been drawn before the pipeline's scope
removals ran. This script exists so the next version is a build, not a copy,
and so the file list is derived rather than remembered.

The manifest is taken from the previous deposit plus an explicit list of
additions, so a file that was in 1.0 cannot silently fall out of 1.1.

Usage:
    python pipeline/make_deposit.py            (build and checksum)
    python pipeline/make_deposit.py --verify   (also rebuild the dataset
                                                from the archive in an empty
                                                directory and compare bytes)
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEP = os.path.join(ROOT, "deposit")
PREV = os.path.join(DEP, "agrifood_dfi_networks_v1")
NAME = "agrifood_dfi_networks_v1_1"
OUT = os.path.join(DEP, NAME)
ZIP = OUT + ".zip"

VERSION = "1.1.0"

# New in 1.1, relative to the repository root and to the deposit root alike.
ADDED = [
    "pipeline/draw_validation_sample.py",
    "pipeline/make_deposit.py",
    "verification/source_recheck.py",
    "data/validation_logs/stage3_validation_sample_v2.csv",
    "verified_findings/34_multiround_candidates.csv",
    "verified_findings/35_source_recheck.csv",
    "verified_findings/36_source_recheck_rates.csv",
]

# The re-check writes a cache of fetched pages. It is derived, it is large,
# and it is other people's copyrighted article text. It stays out, and the
# script refetches.
EXCLUDE_DIRS = {"source_recheck_cache", "__pycache__"}

CHANGELOG = """# Changelog

## 1.1.0

**The validation sample shipped with 1.0 was stale.** It had been drawn
before the pipeline's scope removals ran, so 37 of its 100 rows (33
LLM-extracted, 4 manual) are not in the released dataset. Anyone auditing
that file would have spent a third of the effort on rows the dataset does
not contain.

- `data/validation_logs/stage3_validation_sample_v2.csv` replaces it as the
  sample to audit. It is drawn by `pipeline/draw_validation_sample.py` from
  the dataset as released, seeded and sorted, so the draw reproduces. The
  1.0 file is kept so that any audit work already done against it is not
  orphaned.
- `verification/source_recheck.py` re-reads each sampled row against the
  source URL the row records, and writes
  `verified_findings/35_source_recheck.csv` (row level) and
  `36_source_recheck_rates.csv` (rates per stream). This is not the
  independent audit: it re-reads the source a row already names, so it
  cannot catch a row pointed at the wrong article, and it is not
  independent of whoever entered the row.
- `verified_findings/34_multiround_candidates.csv` lists the five deals
  where one identifier may cover more than one financing event, since the
  deal key is company, country and year.

Known limitation recorded here because it is the next thing to fix: every
`llm_extracted` row cites AgFunder's research index rather than the report
it was extracted from, so those rows cannot be retraced from the release.

The dataset itself, `data/raw_sources/phase1_combined.csv`, is unchanged
from 1.0 and still rebuilds byte for byte from the inputs in this archive.

## 1.0.0

First release.
"""


def manifest():
    """Everything 1.0 shipped, plus the additions, minus excluded dirs."""
    files = []
    for base, dirs, names in os.walk(PREV):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for n in names:
            rel = os.path.relpath(os.path.join(base, n), PREV)
            files.append(rel.replace("\\", "/"))
    for a in ADDED:
        if a not in files:
            files.append(a)
    return sorted(set(files))


def source_for(rel):
    """Prefer the live working tree; fall back to the previous deposit.

    Generated and source files are taken from the repository so the deposit
    carries the current build. Files that only ever existed inside the
    deposit (the licences, the deposit README) come from there.
    """
    live = os.path.join(ROOT, rel)
    if os.path.exists(live):
        return live
    prev = os.path.join(PREV, rel)
    if os.path.exists(prev):
        return prev
    raise FileNotFoundError(rel)


def build():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    files = manifest()
    taken_live = taken_prev = 0
    for rel in files:
        src = source_for(rel)
        taken_live += src.startswith(ROOT) and not src.startswith(PREV)
        taken_prev += src.startswith(PREV)
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    open(os.path.join(OUT, "CHANGELOG.md"), "w", encoding="utf-8",
         newline="\n").write(CHANGELOG)

    zj = os.path.join(OUT, ".zenodo.json")
    if os.path.exists(zj):
        meta = json.load(open(zj, encoding="utf-8"))
        meta["version"] = VERSION
        for c in meta.get("creators", []):
            if c.get("name", "").startswith("Mgomezulu"):
                c["affiliation"] = "AGRA, Data and Analytics Unit, Nairobi, Kenya"
        json.dump(meta, open(zj, "w", encoding="utf-8", newline="\n"),
                  indent=2, ensure_ascii=False)

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, names in os.walk(OUT):
            for n in sorted(names):
                full = os.path.join(base, n)
                z.write(full, os.path.join(NAME,
                                           os.path.relpath(full, OUT)))

    digest = hashlib.sha256(open(ZIP, "rb").read()).hexdigest()
    open(os.path.join(DEP, "SHA256_v1_1.txt"), "w", encoding="utf-8",
         newline="\n").write(f"{digest}  {NAME}.zip\n")

    print(f"deposit -> {OUT}")
    print(f"  {len(files) + 1} files  "
          f"({taken_live} from the repository, {taken_prev} from 1.0, "
          f"1 changelog)")
    print(f"zip     -> {ZIP}  ({os.path.getsize(ZIP) / 1e6:.2f} MB)")
    print(f"sha256  -> {digest}")
    return files


def verify():
    """Rebuild the dataset inside a copy of the archive and compare bytes."""
    target = "data/raw_sources/phase1_combined.csv"
    tmp = tempfile.mkdtemp(prefix="deposit_verify_")
    try:
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(tmp)
        work = os.path.join(tmp, NAME)
        before = hashlib.md5(open(os.path.join(work, target), "rb").read()).hexdigest()
        os.remove(os.path.join(work, target))
        r = subprocess.run([sys.executable, "pipeline/master_pipeline.py"],
                           cwd=work, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        p = os.path.join(work, target)
        if not os.path.exists(p):
            print("  REBUILD FAILED")
            print(r.stdout[-1500:])
            print(r.stderr[-1500:])
            return False
        after = hashlib.md5(open(p, "rb").read()).hexdigest()
        ok = before == after
        print(f"\nclean-room rebuild: shipped {before}")
        print(f"                    rebuilt {after}")
        print("  BYTE IDENTICAL" if ok else "  DIFFERS  <-- FIX")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    build()
    if a.verify and not verify():
        sys.exit(1)
