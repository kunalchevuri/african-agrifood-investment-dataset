# -*- coding: utf-8 -*-
"""Draw the audit sample for the manual and LLM streams.

The sample shipped as stage3_validation_sample.csv was drawn before the
pipeline's scope removals ran, so 37 of its 100 rows (33 LLM-extracted, 4
manual) are not in the released dataset at all. Auditing it would spend a
third of the effort on rows no user can see. This redraws it from the
dataset as released.

Design, stated so the result can be defended:

  - The portal stream is excluded. Those rows are the institution's own
    published values and are covered by the first validation layer; a human
    re-reading them would be re-reading the same portal.
  - The remaining two streams are sampled separately rather than in
    proportion. The LLM stream is 78 rows, 7.4 percent of the dataset, and
    is the least verified; a proportional sample would put 7 of its rows in
    front of the auditor and settle nothing about it. Oversampling it is
    the point of the exercise, and every rate computed from this sample has
    to be reported per stream, never pooled, or the pooled number means
    nothing.
  - The draw is seeded and the output sorted, so two runs give one file.

Usage:
    python pipeline/draw_validation_sample.py
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "raw_sources", "phase1_combined.csv")
OUT = os.path.join(ROOT, "data", "validation_logs",
                   "stage3_validation_sample_v2.csv")

SEED = 20261021
TAKE = {"manual": 56, "llm_extracted": 44}

# What the auditor fills in. Kept identical to the original file so a
# half-finished audit against the old one is not thrown away.
CHECK_COLS = ["company_name_correct", "country_correct",
              "investor_name_correct", "funding_amount_correct",
              "segment_correct", "overall_notes"]

CARRY = ["deal_id", "company_name", "country", "investment_date",
         "agrifood_segment", "funding_amount_usd", "investor_name",
         "source_name", "source_url", "extraction_method"]


def main():
    df = pd.read_csv(SRC)
    parts = []
    for method, n in TAKE.items():
        pool = df[df["extraction_method"] == method]
        assert len(pool) >= n, f"{method}: only {len(pool)} rows, wanted {n}"
        parts.append(pool.sample(n=n, random_state=SEED))
    s = pd.concat(parts)[CARRY].sort_values(["extraction_method", "deal_id",
                                             "investor_name"])
    for c in CHECK_COLS:
        s[c] = ""
    s.to_csv(OUT, index=False)

    print(f"drawn -> {OUT}")
    print(f"  {len(s)} rows, seed {SEED}")
    print(s["extraction_method"].value_counts().to_string())
    deep = s["source_url"].str.contains(r"https?://[^/]+/.+", regex=True,
                                        na=False).sum()
    print(f"\n  rows whose source_url identifies a document: {deep}/{len(s)}")
    print(f"  rows pointing only at a domain:               {len(s) - deep}/{len(s)}")
    print("\n  The second number is the auditable limit: those rows name a"
          "\n  publication but not the article, so the auditor has to find it.")


if __name__ == "__main__":
    main()
