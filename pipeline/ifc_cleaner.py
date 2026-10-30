"""
ifc_cleaner.py

Cleans and consolidates IFC Project Disclosure Portal exports into the
master schema. Handles multiple export batches (Agribusiness/Forestry sector
+ Financial Markets sector with "agri" keyword filter) and deduplicates
across them by Project Number.

Input:  Raw IFC portal exports (SPI.xlsx, SPI_1.xlsx, SPI_2.xlsx, SPI_3.xlsx, SPI_4.xlsx)
        placed in data/raw_sources/
Output: data/raw_sources/ifc_clean.csv

Usage:
    python pipeline/ifc_cleaner.py
"""

import pandas as pd
import re
import os

RAW_SOURCES_DIR = "data/raw_sources/"
OUTPUT_PATH = os.path.join(RAW_SOURCES_DIR, "ifc_clean.csv")

SCHEMA_COLS = [
    "deal_id", "company_name", "country", "investment_date",
    "agrifood_segment", "funding_stage", "funding_amount_usd",
    "investor_name", "investor_type", "is_lead_investor",
    "source_name", "source_url", "extraction_method", "confidence_flag",
]

# All raw IFC export files to merge. Add new export filenames here as
# additional IFC searches are run (e.g. new sector/keyword combinations).
IFC_EXPORT_FILES = [
    "SPI.xlsx",     # Agribusiness and Forestry sector, Africa region
    "SPI_1.xlsx",   # Financial Markets sector, "agri" keyword
    "SPI_2.xlsx",   # Financial Markets sector, broader search
    "SPI_3.xlsx",   # Food/Agriculture sector codes (grain, poultry, dairy, etc.)
    "SPI_4.xlsx",   # Additional Agriculture sector codes
]


def make_deal_id(company: str, year: str) -> str:
    """Generate a short deal_id from company name + year. Prefixed with a
    letter to guarantee Google Sheets never reinterprets it as a number."""
    clean = re.sub(r"[^a-zA-Z0-9]", "", str(company))[:8]
    return f"D{clean}_{str(year)[:4]}"


def map_segment_from_sector(sector, product_area) -> str:
    """Classify agrifood_segment from IFC's raw Sector text field."""
    s = str(sector).lower()
    if any(x in s for x in ["commercial banking", "microfinance", "nbfi",
                             "insurance", "lending", "payment",
                             "private equity"]):
        return "financial_services"
    if any(x in s for x in ["grain processing", "milling", "dairy",
                             "soft drink", "oils", "confectionery",
                             "slaughter"]):
        return "processing"
    if any(x in s for x in ["poultry", "grains and beans",
                             "fruits and vegetables", "coffee", "cocoa",
                             "tea", "sugarcane", "animal production",
                             "edible agricultural"]):
        return "production"
    if "fiber" in s or "cotton" in s:
        return "inputs"
    if "other food" in s:
        return "processing"
    return "unknown"


def map_stage(product_area) -> str:
    """Classify funding_stage from IFC's Product Area Description field."""
    if pd.isna(product_area):
        return "unknown"
    p = str(product_area).lower()
    if "loan" in p:
        return "debt"
    if "equity" in p:
        return "equity"
    if "guarantee" in p or "risk" in p:
        return "blended"
    if "grant" in p:
        return "grant"
    return "other"


def extract_amount(text):
    """Pull a USD amount (in millions) out of IFC's free-text investment
    description field, e.g. 'US$ 25 million'."""
    if pd.isna(text):
        return None
    matches = re.findall(
        r"(?:US\$|USD|\$)\s*(\d+(?:\.\d+)?)\s*(?:million|mn|m\b)",
        str(text), re.IGNORECASE,
    )
    if matches:
        return float(matches[0]) * 1_000_000
    return None


def clean_ifc_exports() -> pd.DataFrame:
    all_raw = []
    for fname in IFC_EXPORT_FILES:
        path = os.path.join(RAW_SOURCES_DIR, fname)
        if not os.path.exists(path):
            print(f"  [skip] {fname} not found in {RAW_SOURCES_DIR}")
            continue
        df = pd.read_excel(path)
        df["_source_file"] = fname
        all_raw.append(df)
        print(f"  {fname}: {len(df)} rows, "
              f"{df['Project Number'].nunique()} unique project numbers")

    if not all_raw:
        raise FileNotFoundError(
            f"No IFC export files found in {RAW_SOURCES_DIR}. "
            f"Expected one or more of: {IFC_EXPORT_FILES}"
        )

    combined_raw = pd.concat(all_raw, ignore_index=True)
    print(f"\nTotal raw rows across all IFC files: {len(combined_raw)}")

    # Dedup: prefer "Summary of Investment Information" (verified/final)
    # over "Summary of Proposed Investment" (pre-approval draft) when the
    # same Project Number appears in multiple exports.
    combined_raw["doc_priority"] = combined_raw["Document Type Description"].apply(
        lambda x: 0 if "Summary of Investment" in str(x) and "Proposed" not in str(x) else 1
    )
    combined_raw = (
        combined_raw.sort_values("doc_priority")
        .drop_duplicates("Project Number", keep="first")
    )
    print(f"After dedup by Project Number: {len(combined_raw)} unique projects")

    records = []
    for _, row in combined_raw.iterrows():
        company = str(row.get("Company Name", "")).strip()
        project_name = str(row.get("Project Name", "")).strip()
        country = str(row.get("Country Description", "")).strip()

        date_raw = row.get("Disclosed Date")
        date = pd.Timestamp(date_raw).strftime("%Y-%m-%d") if pd.notna(date_raw) else None
        year = date[:4] if date else ""

        sector = row.get("Sector", "")
        product_area = row.get("Product Area Description", "")
        amount_text = row.get("Total Project Cost and Amount and Nature of IFC's Investment", "")
        amount = extract_amount(amount_text)
        if amount is None:
            # The portal's "Estimated Total Budget" column is denominated in
            # millions of USD (median 14, max 320 across the SPI exports), so
            # it has to be scaled before it can sit alongside the free-text
            # amounts, which extract_amount() already returns in dollars.
            budget = row.get("Estimated Total Budget", None)
            amount = (float(budget) * 1_000_000
                      if budget is not None and pd.notna(budget) else None)

        display_name = company if company and company != "nan" else project_name

        records.append({
            "deal_id": make_deal_id(display_name, year),
            "company_name": display_name,
            "country": country,
            "investment_date": date,
            "agrifood_segment": map_segment_from_sector(sector, product_area),
            "funding_stage": map_stage(product_area),
            "funding_amount_usd": amount,
            "investor_name": "International Finance Corporation",
            "investor_type": "DFI",
            "is_lead_investor": True,
            "source_name": "IFC Project Disclosure Portal - Consolidated",
            "source_url": "https://disclosures.ifc.org/search",
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

    # Final safety dedup on company+country+year (catches cross-file overlaps
    # missed by Project Number matching, e.g. same deal disclosed under two
    # different project IDs).
    before = len(df_final)
    df_final = df_final.drop_duplicates(
        subset=["company_name", "country", "investment_date"], keep="first"
    )
    print(f"Removed {before - len(df_final)} cross-file duplicates")

    return df_final


if __name__ == "__main__":
    print("=== IFC Cleaner ===\n")
    df = clean_ifc_exports()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} IFC records to {OUTPUT_PATH}")
    print(f"Countries: {df['country'].nunique()}")
    print(f"Segment breakdown:\n{df['agrifood_segment'].value_counts()}")
