"""
master_pipeline.py

Merges all cleaned per-source CSVs (ifc_clean.csv, afdb_clean.csv,
fmo_clean.csv, bii_clean.csv, agfunder_clean.csv, disruptafrica_clean.csv)
into the single master dataset (data/raw_sources/phase1_combined.csv), then
runs entity resolution, segment reclassification, Perplexity-verified
segment overrides, deal_id regeneration, and full deduplication.

Run this any time a new *_clean.csv is added or an existing one is updated
— it always rebuilds phase1_combined.csv from scratch rather than patching
incrementally, since incremental patches were the root cause of several
bugs earlier in this project (segment reclassification silently reverting,
investor_type inconsistencies, deal_id collisions).

Usage:
    python pipeline/master_pipeline.py
"""

import pandas as pd
import glob
import hashlib
import os
import sys

sys.path.append(os.path.dirname(__file__))
from entity_resolution import (
    resolve_company_names,
    resolve_investor_names,
    standardize_investor_types,
    OUT_OF_SCOPE_INVESTORS,
)

RAW_SOURCES_DIR = "data/raw_sources/"
CLASSIFICATIONS_PATH = os.path.join(RAW_SOURCES_DIR, "classified_with_dealids.csv")

# Analysis window stated in the paper (inclusive). Override with
# STUDY_WINDOW="2010,2026" to reproduce the wider-window alternatives
# reported in the sensitivity analysis.
STUDY_WINDOW = tuple(int(x) for x in
                     os.environ.get("STUDY_WINDOW", "2015,2025").split(","))
OUTPUT_PATH = os.path.join(RAW_SOURCES_DIR, "phase1_combined.csv")

COUNTRY_STANDARDIZATION = {
    "Cote D'Ivoire": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Egypt, Arab Republic of": "Egypt",
    "Tanzania, United Republic of": "Tanzania",
    "Cape Verde": "Cabo Verde",
    # Three spellings of the DRC were splitting it into separate
    # countries in the geography table and regional networks. Note
    # "Congo" on its own is the Republic of Congo (Brazzaville), a
    # different country, and is deliberately left alone.
    "Congo, Democratic Republic of": "Democratic Republic of Congo",
    "Congo, Democratic Republic of the": "Democratic Republic of Congo",
    "Republic Democratic of Congo": "Democratic Republic of Congo",
    "DR Congo": "Democratic Republic of Congo",
}


# Which source wins when the same investor-deal appears in more than one
# input file. Lower rank wins. Manually researched rows outrank portal
# downloads only because they carry round-level detail the portals omit;
# both outrank LLM-extracted rows from the AgFunder report PDFs.
EXTRACTION_PRECEDENCE = {
    "manual": 0,
    "structured_download": 1,
    "llm_extracted": 2,
}


def make_unique_deal_id(row) -> str:
    """Hash-based deal_id from company + country + year. Prefixed with 'D'
    so Google Sheets never reinterprets an all-digit hash as a number
    (this happened once and corrupted a row — see project history)."""
    key = f"{row['company_name']}_{row['country']}_{str(row['investment_date'])[:4]}"
    return "D" + hashlib.md5(key.encode()).hexdigest()[:10]


def remove_known_bad_rows(combined: pd.DataFrame) -> pd.DataFrame:
    """Remove relationships confirmed fabricated during dataset construction
    (see known_bad_rows.csv). This step was previously undocumented in code
    and had regressed silently — added as an explicit, auditable pipeline
    step so it can never again go unenforced after a raw-source rebuild."""
    known_bad_path = os.path.join(RAW_SOURCES_DIR, "known_bad_rows.csv")
    if not os.path.exists(known_bad_path):
        print(f"  [warn] {known_bad_path} not found — skipping fabricated-row removal")
        return combined

    known_bad = pd.read_csv(known_bad_path)
    before = len(combined)
    bad_pairs = set(zip(known_bad['company_name'].str.lower(), known_bad['investor_name'].str.lower()))
    mask = combined.apply(
        lambda row: (str(row['company_name']).lower(), str(row['investor_name']).lower()) in bad_pairs,
        axis=1
    )
    combined = combined[~mask]
    print(f"  Removed {before - len(combined)} row(s) matching known fabricated relationships")
    return combined


def reclassify_segment(row) -> str:
    """Fallback keyword classifier for any row still marked 'unknown'
    after each source's own classifier ran. Mostly catches AfDB/IFC titles
    that didn't match the source-specific keyword lists."""
    text = str(row["company_name"]).lower()
    source = str(row["source_name"]).lower()

    if any(x in text for x in ["mill", "process", "oil", "dairy", "flour",
                                 "refin", "beverage", "soft drink", "juice",
                                 "sugar", "malt", "starch", "meat",
                                 "slaughter", "textile", "cotton", "cocoa",
                                 "coffee", "sucden", "brali", "ivoirienne"]):
        return "processing"
    if any(x in text for x in ["farm", "poultry", "livestock", "horticulture",
                                 "sugarcane", "beet", "vegetable", "fruit",
                                 "flower", "aqua", "fish", "biofuel",
                                 "oilseed", "olive", "crop", "irrigation",
                                 "agricultural productivity",
                                 "agricultural livelihoods",
                                 "resilient agricultur", "value chain",
                                 "livestock"]):
        return "production"
    if any(x in text for x in ["input", "seed", "fertiliz", "agro-pocket",
                                 "agricultural growth"]):
        return "inputs"
    if any(x in text for x in ["logistic", "transport", "storage",
                                 "distribution", "trade", "warehouse",
                                 "port", "export"]):
        return "logistics"
    if any(x in text for x in ["fintech", "digital", "tech", "agritech",
                                 "platform", "app"]):
        return "agritech"
    if any(x in text for x in ["bank", "credit", "insurance", "fund",
                                 "loan", "facility", "finance"]):
        return "financial_services"
    if "afdb" in source or "ifc" in source:
        return "production"
    return "unknown"


def apply_perplexity_classifications(combined: pd.DataFrame) -> pd.DataFrame:
    """Apply the manually-verified segment classifications (produced via
    Perplexity deep research on ambiguous AgFunder-sourced company names)
    and remove companies confirmed out-of-scope (non-African or
    non-agrifood)."""
    if not os.path.exists(CLASSIFICATIONS_PATH):
        print(f"  [warn] {CLASSIFICATIONS_PATH} not found — skipping "
              f"Perplexity classification step")
        return combined

    classifications = pd.read_csv(CLASSIFICATIONS_PATH)
    class_lookup = classifications.set_index("company_name")[
        ["agrifood_segment", "justification"]
    ].to_dict("index")

    out_of_scope = classifications[
        classifications["agrifood_segment"] == "out_of_scope"
    ]["company_name"].tolist()

    before = len(combined)
    combined = combined[~combined["company_name"].isin(out_of_scope)]
    print(f"  Removed {before - len(combined)} out-of-scope companies "
          f"(non-African or non-agrifood, confirmed via manual research)")

    def apply_override(row):
        if row["company_name"] in class_lookup:
            new_seg = class_lookup[row["company_name"]]["agrifood_segment"]
            if new_seg != "out_of_scope":
                return new_seg
        return row["agrifood_segment"]

    combined["agrifood_segment"] = combined.apply(apply_override, axis=1)
    combined["segment_justification"] = combined["company_name"].map(
        lambda x: class_lookup.get(x, {}).get("justification", "")
    )
    return combined


def run_pipeline() -> pd.DataFrame:
    # STEP 1: Load and merge all per-source clean files
    all_dfs = []
    # sorted() so the merge order (and therefore every keep="first"
    # decision below) is identical on every machine.
    for f in sorted(glob.glob(f"{RAW_SOURCES_DIR}*_clean.csv")):
        df = pd.read_csv(f)
        all_dfs.append(df)
        print(f"  {f}: {len(df)} rows")
    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\nStep 1 — Raw merge: {len(combined)} rows")

    # NEW STEP: Remove known-fabricated relationships (previously undocumented in code)
    combined = remove_known_bad_rows(combined)

    # STEP 2: Entity resolution — merge name variants BEFORE anything else,
    # since later steps (dedup, type standardization) depend on names
    # already being unified.
    combined["investor_name"] = combined["investor_name"].replace(
        resolve_investor_names()
    )
    # Company names too: deal_id is derived from the company name, so an
    # unmerged variant splits one financing across two deals.
    combined["company_name"] = combined["company_name"].replace(
        resolve_company_names()
    )
    print("Step 2 — Entity resolution applied (investors and companies)")

    # STEP 2b: Drop entities that are not investors (prize competitions and
    # similar), the investor-side counterpart of the out-of-scope company
    # removal in Step 4.
    before = len(combined)
    combined = combined[~combined["investor_name"].isin(OUT_OF_SCOPE_INVESTORS)]
    print(f"Step 2b — Removed {before - len(combined)} row(s) for "
          f"non-investor entities")

    # STEP 3: Fallback keyword segment classification for remaining unknowns
    mask = combined["agrifood_segment"] == "unknown"
    n_before = mask.sum()
    combined.loc[mask, "agrifood_segment"] = combined.loc[mask].apply(
        reclassify_segment, axis=1
    )
    print(f"Step 3 — Reclassified {n_before} unknown segments via keyword matching")

    # STEP 4: Apply manually-verified Perplexity classifications + remove
    # out-of-scope companies
    combined = apply_perplexity_classifications(combined)
    print(f"Step 4 — Perplexity classifications applied, "
          f"unknowns remaining: {(combined['agrifood_segment'] == 'unknown').sum()}")

    # STEP 5: Standardize country names
    combined["country"] = combined["country"].replace(COUNTRY_STANDARDIZATION)
    print("Step 5 — Countries standardized")

    # STEP 5b: Enforce the study window. The individual cleaners pull a wider
    # range so that pre-window records are available when researching a
    # syndicate, but the analysis window is the one the paper states. 2026 is
    # excluded because it is an incomplete year: the few deals disclosed so
    # far are overwhelmingly the large syndicated ones, which biases the
    # co-investment rate upward. Pre-2015 years are excluded because
    # disclosure coverage is visibly thinner there (single-digit deal counts
    # against 15-86 per year afterwards), so including them would put a
    # coverage artifact into the temporal analysis.
    _dt = pd.to_datetime(combined["investment_date"], errors="coerce")
    before = len(combined)
    combined = combined[(_dt.dt.year >= STUDY_WINDOW[0])
                        & (_dt.dt.year <= STUDY_WINDOW[1])]
    print(f"Step 5b — Study window {STUDY_WINDOW[0]}-{STUDY_WINDOW[1]}: "
          f"dropped {before - len(combined)} rows outside it")

    # STEP 6: Regenerate deal_ids (hash-based, collision-free, 'D'-prefixed)
    combined["deal_id"] = combined.apply(make_unique_deal_id, axis=1)
    collisions = combined.groupby("deal_id")["company_name"].nunique()
    print(f"Step 6 — Deal IDs regenerated, collisions: {(collisions > 1).sum()}")

    # STEP 6b: Provenance precedence. Steps 7 and 8 both use keep="first",
    # so whichever row happens to sort first decides which source's
    # funding_amount_usd, funding_stage and source_url survive. Left to
    # concat order that is decided by the filesystem, which silently
    # produced different datasets on different machines (manually verified
    # rows losing to LLM-extracted ones, including a case where a real
    # $850,000 amount was replaced by a null). Rank explicitly instead.
    combined["_prov"] = combined["extraction_method"].map(
        EXTRACTION_PRECEDENCE
    ).fillna(99)
    combined["_amt_missing"] = combined["funding_amount_usd"].isna().astype(int)
    combined = combined.sort_values(
        ["_prov", "confidence_flag", "_amt_missing", "source_name"],
        kind="mergesort",   # stable: never reorders equal keys
    )
    print("Step 6b — Provenance precedence applied "
          "(manual > structured_download > llm_extracted)")

    # STEP 7: Remove exact duplicate rows (same company+investor+date)
    before = len(combined)
    combined = combined.drop_duplicates(
        subset=["company_name", "investor_name", "investment_date"],
        keep="first",
    )
    print(f"Step 7 — Removed {before - len(combined)} exact duplicate rows")

    # STEP 8: Remove duplicate investor within the same deal (same investor
    # disclosed multiple times for one deal via separate documents/dates)
    before = len(combined)
    # Earliest disclosed date wins, as before; provenance breaks ties that
    # were previously broken arbitrarily by an unstable quicksort.
    combined = combined.sort_values(
        ["investment_date", "_prov", "confidence_flag", "_amt_missing", "source_name"],
        kind="mergesort",
    )
    combined = combined.drop_duplicates(subset=["deal_id", "investor_name"], keep="first")
    print(f"Step 8 — Removed {before - len(combined)} duplicate "
          f"investor-within-same-deal rows")

    # STEP 9: Standardize investor_type per investor (must run AFTER entity
    # resolution and dedup, so every row for a given canonical investor name
    # gets the same type)
    combined = standardize_investor_types(combined)
    print("Step 9 — Investor types standardized")

    combined = combined.drop(columns=["_prov", "_amt_missing"])
    # Canonical row order so the written file is byte-reproducible.
    combined = combined.sort_values(
        ["deal_id", "investor_name"], kind="mergesort"
    ).reset_index(drop=True)
    print("Step 10 — Canonical row order applied")

    return combined


def print_summary(combined: pd.DataFrame):
    print(f"\n{'=' * 60}")
    print("FINAL STATE")
    print(f"{'=' * 60}")
    print(f"Total records: {len(combined)}")
    print(f"Unique investors: {combined['investor_name'].nunique()}")

    deal_counts = combined.groupby("deal_id")["investor_name"].count()
    print(f"Deals with 2+ investors: {(deal_counts >= 2).sum()}")
    print(f"Unknown segments remaining: {(combined['agrifood_segment'] == 'unknown').sum()}")

    # Sanity checks — these should always print 0
    dupe_investor_in_deal = combined.groupby(["deal_id", "investor_name"]).size()
    print(f"Duplicate investor-in-deal (should be 0): "
          f"{(dupe_investor_in_deal > 1).sum()}")

    type_check = combined.groupby("investor_name")["investor_type"].nunique()
    print(f"Investors with inconsistent type (should be 0): "
          f"{(type_check > 1).sum()}")


if __name__ == "__main__":
    print("=== Master Pipeline ===\n")
    combined = run_pipeline()
    combined.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved to {OUTPUT_PATH}")
    print_summary(combined)
