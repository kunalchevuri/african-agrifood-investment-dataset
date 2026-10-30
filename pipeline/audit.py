"""
audit.py

Full data-quality audit of phase1_combined.csv. Checks deal_id integrity,
duplicates, date validity, country validity, funding amount sanity,
investor name near-duplicates, investor_type consistency, and scope
(agrifood relevance).

Run this after any change to master_pipeline.py or after adding new manual
research records, before treating the dataset as final.

Usage:
    python pipeline/audit.py
"""

import pandas as pd
import os

RAW_SOURCES_DIR = "data/raw_sources/"
INPUT_PATH = os.path.join(RAW_SOURCES_DIR, "phase1_combined.csv")


def run_audit():
    combined = pd.read_csv(INPUT_PATH)
    print(f"{'=' * 70}")
    print(f"FULL DEEP AUDIT — {len(combined)} TOTAL ROWS")
    print(f"{'=' * 70}\n")

    # 1. Deal_id integrity
    print("--- 1. DEAL_ID INTEGRITY ---")
    collision_check = combined.groupby("deal_id")["company_name"].nunique()
    print(f"Deal_ids shared by different companies: {(collision_check > 1).sum()}")

    # 2. Duplicates
    print("\n--- 2. DUPLICATES ---")
    exact_dupes = combined.duplicated(
        subset=["company_name", "investor_name", "investment_date"], keep=False
    )
    print(f"Exact duplicate rows remaining: {exact_dupes.sum()}")

    dupe_investor_in_deal = combined.groupby(["deal_id", "investor_name"]).size()
    print(f"Same investor 2+ times within same deal (should be 0): "
          f"{(dupe_investor_in_deal > 1).sum()}")

    # 3. Date integrity
    print("\n--- 3. DATE INTEGRITY ---")
    combined["date_parsed"] = pd.to_datetime(combined["investment_date"], errors="coerce")
    print(f"Unparseable dates: {combined['date_parsed'].isna().sum()}")
    out_of_range = combined[
        (combined["date_parsed"].dt.year < 2015)
        | (combined["date_parsed"].dt.year > 2025)
    ]
    print(f"Outside 2015-2025 window: {len(out_of_range)}")

    # 4. Country validity
    print("\n--- 4. COUNTRY VALIDITY ---")
    print(f"'Unknown' country: {(combined['country'] == 'Unknown').sum()}")
    print(f"Null country: {combined['country'].isna().sum()}")

    # 5. Funding amount sanity
    print("\n--- 5. FUNDING AMOUNT SANITY ---")
    print(f"Missing amount: {combined['funding_amount_usd'].isna().sum()}")
    print(f"Zero or negative: {(combined['funding_amount_usd'] <= 0).sum()}")
    extreme_high = combined[combined["funding_amount_usd"] > 200_000_000]
    print(f"Amounts over $200M (verify not errors): {len(extreme_high)}")
    extreme_low = combined[
        (combined["funding_amount_usd"] > 0) & (combined["funding_amount_usd"] < 1000)
    ]
    print(f"Amounts under $1,000 (likely a units bug if any appear): {len(extreme_low)}")

    # 6. Investor name near-duplicates
    print("\n--- 6. INVESTOR NAME NEAR-DUPLICATES ---")
    investors = sorted(combined["investor_name"].dropna().unique().tolist())
    print(f"Total unique investor names: {len(investors)}")
    potential_dupes = []
    for i, inv1 in enumerate(investors):
        for inv2 in investors[i + 1:]:
            c1 = inv1.lower().replace(" ", "").replace(",", "").replace(".", "")
            c2 = inv2.lower().replace(" ", "").replace(",", "").replace(".", "")
            if c1 != c2 and (c1 in c2 or c2 in c1):
                potential_dupes.append((inv1, inv2))
    print(f"Potential near-duplicate pairs (manual review recommended): "
          f"{len(potential_dupes)}")
    for pair in potential_dupes:
        print(f"  '{pair[0]}' <-> '{pair[1]}'")

    # 7. Segment / stage distribution
    print("\n--- 7. SEGMENT DISTRIBUTION ---")
    print(combined["agrifood_segment"].value_counts())

    # 8. Confidence flag / extraction method
    print("\n--- 8. CONFIDENCE & EXTRACTION METHOD ---")
    print(combined["confidence_flag"].value_counts())
    print(f"\n{combined['extraction_method'].value_counts()}")

    # 9. Investor type consistency
    print("\n--- 9. INVESTOR_TYPE CONSISTENCY ---")
    investor_type_check = combined.groupby("investor_name")["investor_type"].nunique()
    inconsistent = investor_type_check[investor_type_check > 1]
    print(f"Investors with inconsistent investor_type (should be 0): {len(inconsistent)}")

    # 10. Network composition sanity
    print("\n--- 10. DEAL COMPOSITION SANITY ---")
    deal_investor_counts = combined.groupby("deal_id")["investor_name"].nunique()
    print(f"Deals with exactly 1 investor: {(deal_investor_counts == 1).sum()}")
    print(f"Deals with 2-3 investors: "
          f"{((deal_investor_counts >= 2) & (deal_investor_counts <= 3)).sum()}")
    print(f"Deals with 4-6 investors: "
          f"{((deal_investor_counts >= 4) & (deal_investor_counts <= 6)).sum()}")
    print(f"Deals with 7+ investors: {(deal_investor_counts >= 7).sum()}")

    print(f"\n{'=' * 70}")
    print("AUDIT COMPLETE")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    run_audit()
