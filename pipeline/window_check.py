# -*- coding: utf-8 -*-
"""
window_check.py

The Methods section justifies the 2015 start date with a disclosure
comparison: of the deals recorded between 2010 and 2014, only 14.6 percent
name a second investor, against 51.9 percent inside the window. Those two
numbers cannot come from the standard run, because master_pipeline.py drops
pre-2015 rows at step 5b, so they were the one pair of figures in the paper
that the number-verifier could not reach and that had to be checked by hand.

This script removes the hand-check. It rebuilds the dataset over the wider
2010-2025 window in a subprocess, measures the co-investment disclosure rate
on either side of the cut, restores the standard-window file, and writes the
result to verified_findings/ so the claim is regenerated like every other.

The restore is unconditional: the wider window is a diagnostic and must
never be left behind as the analysis dataset.

Usage:
    python pipeline/window_check.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pandas as pd

COMBINED = "data/raw_sources/phase1_combined.csv"
OUT = "verified_findings/16_window_disclosure.csv"
MASTER = os.path.join(os.path.dirname(__file__), "master_pipeline.py")
WIDE_START = 2010


def build(window):
    """Rebuild phase1_combined.csv over `window` and return it."""
    env = dict(os.environ, STUDY_WINDOW=f"{window[0]},{window[1]}")
    subprocess.run([sys.executable, MASTER], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    return pd.read_csv(COMBINED)


INSTITUTIONS = {"ifc": "International Finance Corporation",
                "fmo": "FMO",
                "bii": "British International Investment"}


def disclosure(df, lo, hi):
    """Share of deals in [lo, hi] that name two or more investors, plus
    the number of deals in which each of the three most central DFIs
    appears and the number of distinct non-DFI investors. The latter answer
    whether the institutions that carry the results are observed at all
    before the window opens."""
    year = pd.to_datetime(df["investment_date"], errors="coerce").dt.year
    s = df[(year >= lo) & (year <= hi)]
    per_deal = s.groupby("deal_id")["investor_name"].nunique()
    inst = {k: int(s[s["investor_name"] == v]["deal_id"].nunique())
            for k, v in INSTITUTIONS.items()}
    non_dfi = int(s[s["investor_type"].str.lower() != "dfi"]
                  ["investor_name"].nunique())
    return len(per_deal), int((per_deal >= 2).sum()), inst, non_dfi


def main():
    # Preserve the standard-window dataset so an interrupted run cannot
    # leave the wider window in place as the analysis file.
    keep = os.path.join(tempfile.mkdtemp(), "phase1_combined.csv")
    shutil.copy(COMBINED, keep)
    try:
        window = (2015, 2025)
        wide = build((WIDE_START, window[1]))
        rows = []
        for lo, hi, label in [(WIDE_START, window[0] - 1, "excluded"),
                              (window[0], window[1], "study window")]:
            deals, co, inst, non_dfi = disclosure(wide, lo, hi)
            rows.append({"period": f"{lo}-{hi}", "status": label,
                         "deals": deals, "co_investment_deals": co,
                         "co_investment_pct": round(100 * co / deals, 1),
                         "ifc_deals": inst["ifc"], "fmo_deals": inst["fmo"],
                         "bii_deals": inst["bii"],
                         "non_dfi_investors": non_dfi})
    finally:
        shutil.copy(keep, COMBINED)

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False))
    print(f"\nWrote {OUT}")
    print(f"Restored standard-window {COMBINED}")


if __name__ == "__main__":
    main()
