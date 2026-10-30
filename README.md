# African Agrifood Investment: Deal-Level Dataset and Build Pipeline

An open, deal-level dataset of development finance and private investment in
African agrifood systems, 2015–2025, together with the pipeline that rebuilds
it from the source exports and the analysis code that regenerates every
reported number.

Release 1.1.0. Code is MIT licensed; data and derived results are CC BY 4.0.

## The dataset

`data/raw_sources/phase1_combined.csv` is the assembled dataset.

| | |
|---|---|
| Records | 1,060 |
| Unique deals | 389 |
| Companies | 313 |
| Investors | 420 (27 development finance institutions, 393 other) |
| Countries | 30 |
| Co-investment deals | 202 (183 with a disclosed amount) |
| Disclosed volume | USD 6.99 billion |
| Distinct named sources | 121, across 66 domains |
| Rows at highest confidence tier | 87.2% |

Every row records its own `source_name` and `source_url`, so any individual
deal can be traced back to the disclosure or article it came from.

## How it is built

Five stages, each re-runnable on its own:

1. **Structured downloads** — manual exports from the public disclosure
   portals of the International Finance Corporation, the African Development
   Bank, FMO and British International Investment, plus AgFunder's Africa
   reports.
2. **Per-source cleaning** — `pipeline/ifc_cleaner.py`,
   `pipeline/afdb_cleaner.py` map each portal's export onto a shared schema.
3. **Semi-structured extraction** — AgFunder report text parsed into
   investor–company links. Rows carry `extraction_method = llm_extracted`.
4. **Manual research** — named funding rounds assembled from press coverage
   where the DFI portals disclose no co-investors. Rows carry
   `extraction_method = manual`.
5. **Entity resolution and merge** — `pipeline/entity_resolution.py` and
   `pipeline/investor_origin.py` canonicalise investor names and domiciles;
   `pipeline/master_pipeline.py` merges, dedupes and audits.

```bash
pip install -r requirements.txt
python pipeline/master_pipeline.py   # rebuild the dataset from the sources
python pipeline/audit.py             # data-quality audit
python pipeline/analysis.py          # regenerate verified_findings/
```

`analysis.py` writes one CSV per finding into `verified_findings/`, so the
numbers in the papers are not transcribed by hand — they are re-derived from
the dataset on every run.

## Validation

`data/validation_logs/stage3_validation_sample_v2.csv` is a seeded, sorted
100-row sample drawn by `pipeline/draw_validation_sample.py` from the dataset
as released, intended for manual audit against the cited sources.
`verification/source_recheck.py` re-reads each sampled row against the URL
that row records and writes the row-level and per-stream agreement rates to
`verified_findings/35_source_recheck.csv` and `36_source_recheck_rates.csv`.

This re-check is deliberately **not** an independent audit: it re-reads the
source a row already names, so it cannot catch a row pointed at the wrong
article, and it is not independent of whoever entered the row.

`CHANGELOG.md` records what changed in 1.1.0, including a stale validation
sample shipped in 1.0 and a known limitation in how LLM-extracted rows cite
their source.

The scripts in `verification/` beyond `source_recheck.py` gate the manuscript
against the pipeline (number agreement, table generation, bibliography,
figure fit). They expect the paper sources, which are not part of this
release while the manuscript is under review.

## Papers

- *An Open Deal-Level Dataset of African Agrifood Investment, 2015–2025, and
  the Reproducible Pipeline That Builds It.* Accepted, High School Symposium,
  IEEE International Conference on Big Data, Phoenix, AZ, December 2026.
- *Do Development Finance Institutions Crowd In Private Capital? Network
  Evidence from African Agrifood Investment, 2015–2025.* Under review,
  *World Development*.

## Authors

Kunal Chevuri (Prosper High School), Alexander Poon (Edison Academy Magnet
School), Ron Mahabir (University of Liverpool), Wisdom Mgomezulu (AGRA, Data
and Analytics Unit, Nairobi), Maction Komwa (George Mason University), Olga
Gkountouna (University of Liverpool).

Produced through the ASSIP program at George Mason University in
collaboration with the Alliance for a Green Revolution in Africa (AGRA).

## Citation

> Chevuri, K., Poon, A., Mahabir, R., Mgomezulu, W., Komwa, M., and
> Gkountouna, O. (2026). *Deal-level dataset of African agrifood investment,
> 2015–2025.* Version 1.1.0.

## Licences

- Code (`pipeline/`, `verification/`): MIT — see `LICENSE`.
- Data (`data/`, `verified_findings/`): CC BY 4.0 — see `LICENSE-DATA.txt`.

The underlying disclosures are public records of the institutions named in
each row. Natural Earth boundary data (`data/raw_sources/geo/`) are in the
public domain.
