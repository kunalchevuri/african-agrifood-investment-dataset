"""
afdb_cleaner.py

Cleans the AfDB MapAfrica portal export (Agriculture and Rural Development
sector, all countries, full history) into the master schema and restricts
to the 2010-2025 study window.

Note: the MapAfrica export includes AfDB's entire agriculture project
history back to 1968. We confirmed the 2015-2025 filtered count (390 rows)
exactly matches the year-by-year distribution of the raw file, so no
additional AfDB data exists to extract beyond this single export.

Input:  data/raw_sources/afdb_raw_full.xlsx
Output: data/raw_sources/afdb_clean.csv

Usage:
    python pipeline/afdb_cleaner.py
"""

import pandas as pd
import re
import os

RAW_SOURCES_DIR = "data/raw_sources/"
INPUT_PATH = os.path.join(RAW_SOURCES_DIR, "afdb_raw_full.xlsx")
OUTPUT_PATH = os.path.join(RAW_SOURCES_DIR, "afdb_clean.csv")

SCHEMA_COLS = [
    "deal_id", "company_name", "country", "investment_date",
    "agrifood_segment", "funding_stage", "funding_amount_usd",
    "investor_name", "investor_type", "is_lead_investor",
    "source_name", "source_url", "extraction_method", "confidence_flag",
]

# AfDB reports commitments in Units of Account (UA). Fixed conversion rate
# used for this dataset — update if a more precise historical rate per
# transaction date is later required.
UA_TO_USD = 1.37


def make_deal_id(company: str, year: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]", "", str(company))[:8]
    return f"D{clean}_{str(year)[:4]}"


def map_segment_afdb(title) -> str:
    """Classify agrifood_segment from the AfDB project title text. AfDB
    titles are descriptive project names (not sector codes like IFC), so
    this uses keyword matching on the free-text title."""
    if pd.isna(title):
        return "unknown"
    t = str(title).lower()
    if any(x in t for x in ["fish", "blue economy", "aqua"]):
        return "production"
    if any(x in t for x in ["value chain", "agro-industrial", "processing", "mill"]):
        return "processing"
    if any(x in t for x in ["irrigation", "water management", "input", "seed", "fertiliz"]):
        return "inputs"
    if any(x in t for x in ["transport", "storage", "logistics", "trade"]):
        return "logistics"
    if any(x in t for x in ["farm", "crop", "rice", "wheat", "livestock",
                             "poultry", "agriculture", "agrifood", "food"]):
        return "production"
    return "unknown"


def is_sovereign(row) -> bool:
    """AfDB's export flags each operation as sovereign (a loan or grant to a
    government) or non-sovereign (a transaction with a private borrower).
    The column is named 'sovereign' and holds a boolean."""
    return str(row.get("sovereign", "")).strip().upper() != "FALSE"


def map_stage_afdb(row) -> str:
    """AfDB portal only distinguishes sovereign vs. non-sovereign lending,
    not detailed funding stage. Non-sovereign treated as equity-like,
    everything else as debt (AfDB sovereign operations are loans)."""
    return "debt" if is_sovereign(row) else "equity"


def clean_afdb_export() -> pd.DataFrame:
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"AfDB export not found at {INPUT_PATH}. "
            f"Download from mapafrica.afdb.org with sector = "
            f"'Agriculture and Rural Development' and export as XLSX."
        )

    df_raw = pd.read_excel(INPUT_PATH)
    print(f"Raw rows: {len(df_raw)}")

    # Scope: this study measures whether DFIs draw private co-investors into
    # a transaction, so the deal universe is private-sector operations. AfDB
    # sovereign operations are loans and grants to governments and cannot
    # have a private co-investor by construction, so they are excluded here
    # rather than left to dilute the denominator. The count is reported so
    # the paper can state how much AfDB agrifood lending is sovereign.
    # Set AFDB_INCLUDE_SOVEREIGN=1 to keep sovereign operations, which is how
    # the sensitivity analysis reports what this scope choice is worth.
    include_sov = os.environ.get("AFDB_INCLUDE_SOVEREIGN") == "1"
    n_sovereign = sum(is_sovereign(r) for _, r in df_raw.iterrows())
    if not include_sov:
        df_raw = df_raw[[not is_sovereign(r) for _, r in df_raw.iterrows()]]
    print(f"{'Retained' if include_sov else 'Excluded'} {n_sovereign} sovereign "
          f"operations; {len(df_raw)} rows retained")

    records = []
    for _, row in df_raw.iterrows():
        title = str(row.get("title", "")).strip()
        country = str(row.get("country", "")).strip()

        date_raw = row.get("Approval Date")
        date = pd.Timestamp(date_raw).strftime("%Y-%m-%d") if pd.notna(date_raw) else None
        year = date[:4] if date else ""

        amount = row.get("total_commitments (UA)", None)
        amount_usd = float(amount) * UA_TO_USD if pd.notna(amount) and amount > 0 else None

        records.append({
            "deal_id": make_deal_id(title, year),
            "company_name": title,
            "country": country,
            "investment_date": date,
            "agrifood_segment": map_segment_afdb(title),
            "funding_stage": map_stage_afdb(row),
            "funding_amount_usd": amount_usd,
            "investor_name": "African Development Bank",
            "investor_type": "DFI",
            "is_lead_investor": True,
            "source_name": "AfDB MapAfrica Portal",
            "source_url": "https://mapafrica.afdb.org",
            "extraction_method": "structured_download",
            "confidence_flag": 1,
        })

    df_final = pd.DataFrame(records)[SCHEMA_COLS]

    # Restrict to study window 2010-2025
    df_final["investment_date"] = pd.to_datetime(df_final["investment_date"])
    df_final = df_final[
        (df_final["investment_date"].dt.year >= 2010)
        & (df_final["investment_date"].dt.year <= 2025)
    ]

    return df_final


if __name__ == "__main__":
    print("=== AfDB Cleaner ===\n")
    df = clean_afdb_export()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} AfDB records to {OUTPUT_PATH}")
    print(f"Countries: {df['country'].nunique()}")
    print(f"Segment breakdown:\n{df['agrifood_segment'].value_counts()}")
