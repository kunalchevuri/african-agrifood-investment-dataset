# Changelog

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
