"""Statistics for the companion dataset paper (IEEE BigData 2026 High School
Symposium). Describes how the dataset was assembled and what disclosure
practice does to the record. Reports nothing from the journal paper's
analysis (no centrality, no null model, no hypothesis tests).

Writes verified_findings/30_dataset_paper.csv (long format: key, value) and
verified_findings/31_dataset_by_stream.csv. Pipeline step counts are taken
from a fresh run of master_pipeline.py so they regenerate with the build.
"""
import os, re, subprocess, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw_sources")
OUT = os.path.join(ROOT, "verified_findings")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import entity_resolution as er  # noqa: E402

STREAM_LABEL = {"structured_download": "portal",
                "llm_extracted": "llm",
                "manual": "manual"}

rows = []
def put(k, v):
    rows.append({"key": k, "value": v})

# ---- 1. per-step counts from the build itself ----
proc = subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "master_pipeline.py")],
                      capture_output=True, text=True, cwd=ROOT, encoding="utf-8", errors="replace")
log = proc.stdout
def grab(pattern):
    m = re.search(pattern, log)
    return int(m.group(1)) if m else None
for name, pat in [
    ("raw_rows_merged", r"Raw merge: (\d+) rows"),
    ("known_bad_rows_removed", r"Removed (\d+) row\(s\) matching known fabricated"),
    ("non_investor_rows_removed", r"Removed (\d+) row\(s\) for non-investor"),
    ("segments_reclassified_keyword", r"Reclassified (\d+) unknown segments"),
    ("out_of_scope_companies_removed", r"Removed (\d+) out-of-scope companies"),
    ("segments_unknown_after_llm_check", r"unknowns remaining: (\d+)"),
    ("rows_outside_window_dropped", r"dropped (\d+) rows outside"),
    ("deal_id_collisions", r"collisions: (\d+)"),
    ("exact_duplicate_rows_removed", r"Removed (\d+) exact duplicate"),
    ("investor_within_deal_duplicates_removed", r"Removed (\d+) duplicate investor-within"),
]:
    put(name, grab(pat))
for f in ["ifc_clean.csv", "afdb_clean.csv", "fmo_clean.csv", "bii_clean.csv",
          "agfunder_clean.csv", "disruptafrica_clean.csv", "alexpoon_clean.csv",
          "dfi_syndication_clean.csv"]:
    m = re.search(re.escape(f) + r": (\d+) rows", log)
    put("input_rows_" + f.replace("_clean.csv", ""), int(m.group(1)) if m else None)

# running row count after each removal step, in build order
n = rows[0]["value"]
run = [("rows_after_known_bad", "known_bad_rows_removed"),
       ("rows_after_non_investor", "non_investor_rows_removed"),
       ("rows_after_out_of_scope", "out_of_scope_rows_removed"),
       ("rows_after_window", "rows_outside_window_dropped"),
       ("rows_after_exact_dedup", "exact_duplicate_rows_removed"),
       ("rows_after_within_deal_dedup", "investor_within_deal_duplicates_removed")]
vals = {r["key"]: r["value"] for r in rows}
vals["out_of_scope_rows_removed"] = vals["out_of_scope_companies_removed"]  # the build prints rows
put("out_of_scope_rows_removed", vals["out_of_scope_rows_removed"])
for name, dec in run:
    n = n - vals[dec]
    put(name, n)

# portal-stream round trip: rerun the IFC and AfDB cleaners on the raw portal
# exports and check that the cleaned inputs come back byte-identical
import hashlib
def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()
for name in ("ifc", "afdb"):
    target = os.path.join(RAW, f"{name}_clean.csv")
    before = md5(target)
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", f"{name}_cleaner.py")],
                   capture_output=True, cwd=ROOT)
    put(f"{name}_cleaner_roundtrip_identical", int(md5(target) == before))
port = df_tmp = pd.read_csv(os.path.join(RAW, "phase1_combined.csv"))
port = port[port["extraction_method"] == "structured_download"]
put("portal_rows", len(port))
put("portal_rows_ifc_afdb", int(port["source_name"].str.contains("IFC|AfDB").sum()))
put("portal_rows_pct", round(100 * len(port) / len(df_tmp), 1))
llm_n = int((df_tmp["extraction_method"] == "llm_extracted").sum())
put("llm_rows", llm_n)
put("llm_rows_pct", round(100 * llm_n / len(df_tmp), 1))

# the drawn, still-unchecked validation sample
vs = pd.read_csv(os.path.join(ROOT, "data", "validation_logs", "stage3_validation_sample.csv"))
put("validation_sample_rows", len(vs))
for m, n in vs["extraction_method"].value_counts().items():
    put(f"validation_sample_{m}", int(n))
put("validation_sample_checked", int(vs["company_name_correct"].notna().sum()))

# ---- 2. entity resolution tables ----
put("canonical_investor_name_rules", len(er.CANONICAL_INVESTOR_NAMES))
put("canonical_company_name_rules", len(er.CANONICAL_COMPANY_NAMES))
put("canonical_investor_type_rules", len(er.CANONICAL_INVESTOR_TYPES))
cls = pd.read_csv(os.path.join(RAW, "classified_with_dealids.csv"))
put("llm_checked_companies", len(cls))
put("llm_checked_out_of_scope", int((cls["agrifood_segment"] == "out_of_scope").sum()))

# ---- 3. final dataset ----
df = pd.read_csv(os.path.join(RAW, "phase1_combined.csv"))
df["year"] = pd.to_datetime(df["investment_date"], errors="coerce").dt.year
df["stream"] = df["extraction_method"].map(STREAM_LABEL)
put("rows", len(df))
put("deals", df["deal_id"].nunique())
put("companies", df["company_name"].nunique())
put("investors", df["investor_name"].nunique())
NON_COUNTRY = {"Multinational", "Global", "Unknown"}   # same rule as analysis.py
put("countries", len([c for c in df["country"].unique()
                      if c not in NON_COUNTRY and "Region" not in str(c)]))
put("rows_country_unknown", int((df["country"] == "Unknown").sum()))
put("rows_country_regional", int(df["country"].isin({"Multinational"}).sum()
                                + df["country"].str.contains("Region").sum()))
put("sources", df["source_name"].nunique())
put("domains", int(df["source_url"].str.extract(r"https?://([^/]+)")[0].nunique()))  # same rule as analysis.py
put("year_min", int(df["year"].min())); put("year_max", int(df["year"].max()))
put("flag1_rows", int((df["confidence_flag"] == 1).sum()))
put("flag2_rows", int((df["confidence_flag"] == 2).sum()))
put("flag1_pct", round(100 * (df["confidence_flag"] == 1).mean(), 1))
put("fields", len([c for c in df.columns if c not in ("year", "stream")]))

# deal-level view: a deal is assigned to the highest-precedence stream among
# its rows (manual > portal > llm), the same rule the build uses to pick
# which record survives deduplication
deal = df.groupby("deal_id").agg(
    n_inv=("investor_name", "nunique"),
    n_private=("investor_type", lambda s: int((s.str.lower() != "dfi").sum())),
    has_dfi=("investor_type", lambda s: bool((s.str.lower() == "dfi").any())),
    amt=("funding_amount_usd", "max"),
    n_streams=("stream", "nunique"),
    n_sources=("source_name", "nunique"),
    stream=("stream", lambda s: "manual" if (s == "manual").any()
            else ("portal" if (s == "portal").any() else "llm")),
)
put("deals_two_plus_investors", int((deal["n_inv"] >= 2).sum()))
put("deals_with_amount", int(deal["amt"].notna().sum()))
put("deals_with_amount_pct", round(100 * deal["amt"].notna().mean(), 1))
put("deals_in_multiple_streams", int((deal["n_streams"] > 1).sum()))
put("deals_in_multiple_sources", int((deal["n_sources"] > 1).sum()))
put("deals_with_dfi", int(deal["has_dfi"].sum()))
put("deals_without_dfi", int((~deal["has_dfi"]).sum()))
put("portal_deals_without_dfi",
    int(((deal["stream"] == "portal") & ~deal["has_dfi"]).sum()))

# ---- 4. by stream ----
by = []
for st in ["portal", "llm", "manual"]:
    r = df[df["stream"] == st]
    d = deal[deal["stream"] == st]
    by.append({
        "stream": st,
        "sources": r["source_name"].nunique(),
        "rows": len(r),
        "deals": len(d),
        "investors": r["investor_name"].nunique(),
        "deals_with_amount_pct": round(100 * d["amt"].notna().mean(), 1),
        "mean_investors_per_deal": round(d["n_inv"].mean(), 2),
        "deals_two_plus_pct": round(100 * (d["n_inv"] >= 2).mean(), 1),
        "mean_private_coinvestors": round(d["n_private"].mean(), 2),
        "deals_with_dfi_pct": round(100 * d["has_dfi"].mean(), 1),
        "flag1_pct": round(100 * (r["confidence_flag"] == 1).mean(), 1),
    })
pd.DataFrame(by).to_csv(os.path.join(OUT, "31_dataset_by_stream.csv"), index=False)

# ---- 5. cross-source agreement on deals recorded by more than one source ----
multi = deal[deal["n_sources"] > 1].index
s = df[df["deal_id"].isin(multi)]
def agree(col):
    # among multi-source deals where at least two sources give a non-null
    # value, share where all non-null values coincide
    g = s.dropna(subset=[col]).groupby("deal_id")
    src = g["source_name"].nunique()
    vals = g[col].nunique()
    ok = src[src >= 2].index
    return len(ok), round(100 * (vals.loc[ok] == 1).mean(), 1)
for col, name in [("country", "country"), ("investment_date", "date"),
                  ("funding_amount_usd", "amount"), ("agrifood_segment", "segment")]:
    n, pct = agree(col)
    put(f"agree_{name}_deals", n); put(f"agree_{name}_pct", pct)

# year-level agreement and the size of amount disagreements
sy = s.assign(year=s["investment_date"].astype(str).str[:4])
gy = sy.groupby("deal_id")
put("agree_year_pct", round(100 * (gy["year"].nunique() == 1).mean(), 1))
put("rows_date_year_only_pct",
    round(100 * df["investment_date"].astype(str).str.endswith("-01-01").mean(), 1))
am = s.dropna(subset=["funding_amount_usd"]).groupby("deal_id")["funding_amount_usd"]       .agg(["min", "max", "nunique"])
am = am[am["nunique"] > 1]
put("amount_disagree_deals", len(am))
put("amount_disagree_median_ratio", round((am["max"] / am["min"]).median(), 2))

# ---- 5b. vocabularies and the LLM extraction sheet ----
for seg, n in df["agrifood_segment"].value_counts().items():
    put(f"segment_rows_{seg}", int(n))
for t, n in df["investor_type"].value_counts().items():
    put(f"investor_type_rows_{t}", int(n))
put("investors_dfi", int(df[df["investor_type"] == "DFI"]["investor_name"].nunique()))
put("investors_non_dfi", int(df[df["investor_type"] != "DFI"]["investor_name"].nunique()))
xl = pd.read_excel(os.path.join(RAW, "assip_agfunder_investor_deals_extraction.xlsx"), sheet_name=None)
put("llm_sheet_investor_company_links", len(xl["Investor-Company Links"]))
put("llm_sheet_deal_records", len(xl["Deal Records"]))
for rep, n in xl["Deal Records"]["Source_Report"].value_counts().items():
    put("llm_sheet_deal_records_" + rep.split()[0], int(n))
put("ifc_export_files", 5)
# attrition of the LLM stream: cleaned AgFunder pairs (after the same name
# resolution the build applies) that reach the final file, and why not
ag = pd.read_csv(os.path.join(RAW, "agfunder_clean.csv"))
ag["investor_name"] = ag["investor_name"].replace(er.resolve_investor_names())
ag["company_name"] = ag["company_name"].replace(er.resolve_company_names())
pairs = lambda d: set(zip(d["company_name"].str.lower().str.strip(),
                          d["investor_name"].str.lower().str.strip()))
ag_pairs, missing = pairs(ag), pairs(ag) - pairs(df)
oos = set(cls[cls["agrifood_segment"] == "out_of_scope"]["company_name"].str.lower())
bad = pd.read_csv(os.path.join(RAW, "known_bad_rows.csv"))
bad_pairs = set(zip(bad["company_name"].str.lower(), bad["investor_name"].str.lower()))
put("agfunder_clean_pairs", len(ag_pairs))
put("agfunder_pairs_out_of_scope", sum(c in oos for c, _ in missing))
put("agfunder_pairs_known_bad", sum(p in bad_pairs for p in missing))
put("agfunder_pairs_non_investor", sum(p not in bad_pairs and p[0] not in oos for p in missing))
put("known_bad_pairs_from_agfunder", sum(p in ag_pairs for p in bad_pairs))
put("agfunder_pairs_in_final", len(ag_pairs) - len(missing))
put("agfunder_pairs_dropped", len(missing))
# precision of the model's links: a link is wrong if it named a relationship
# no source supports or an entity that is not an investor; out-of-scope
# companies are a scoping decision, not an extraction error
wrong = sum(p in bad_pairs or (p not in bad_pairs and p[0] not in oos) for p in missing)
put("agfunder_links_wrong", wrong)
put("agfunder_links_real", len(ag_pairs) - wrong)
put("agfunder_links_wrong_pct", round(100 * wrong / len(ag_pairs), 1))
put("agfunder_links_real_pct", round(100 * (len(ag_pairs) - wrong) / len(ag_pairs), 1))   # SPI.xlsx .. SPI_4.xlsx, listed in ifc_cleaner.py

# ---- 6. deals by year and stream (coverage) ----
yr = deal.join(df.groupby("deal_id")["year"].first())
tab = yr.pivot_table(index="year", columns="stream", values="n_inv", aggfunc="size", fill_value=0)
tab["total"] = tab.sum(axis=1)
tab.to_csv(os.path.join(OUT, "32_dataset_deals_by_year_stream.csv"))


# ---- 7. does one identifier ever hide two financing events? ----
# The key is company, country and year, so a company that raised twice in
# one year collapses into a single deal. Asserting "no collisions" answers
# the other question (two companies sharing an identifier), so measure this
# one directly and publish the candidates rather than claim their absence.
#
# Named equity rounds are evidence of a distinct financing event. The
# instrument labels (debt, equity, blended, other, unknown) are not: a DFI
# facility routinely carries two of them for the same transaction.
ROUNDS = {"seed", "series_a", "series_b", "series_c"}
dt = pd.to_datetime(df["investment_date"], errors="coerce")
day_known = ~((dt.dt.month == 1) & (dt.dt.day == 1))

cand, testable = [], 0
for did, sub in df.groupby("deal_id"):
    named = {x for x in sub["funding_stage"].dropna() if x in ROUNDS}
    dates = sorted(dt[sub.index][day_known[sub.index]].dropna().unique())
    span = (pd.Timestamp(max(dates)) - pd.Timestamp(min(dates))).days if len(dates) > 1 else 0
    if named or len(dates):
        testable += 1
    why = []
    if len(named) >= 2:
        why.append("two named rounds: " + ", ".join(sorted(named)))
    if span > 30:
        why.append(f"day-level dates {span} days apart")
    if why:
        cand.append({"deal_id": did, "company_name": sub["company_name"].iloc[0],
                     "country": sub["country"].iloc[0],
                     "year": int(sub["year"].iloc[0]), "rows": len(sub),
                     "evidence": "; ".join(why)})

cand = pd.DataFrame(cand).sort_values("company_name")
cand.to_csv(os.path.join(OUT, "34_multiround_candidates.csv"), index=False)
put("deals_testable_for_multiround", testable)
put("deals_multiround_candidates", len(cand))
put("deals_multiround_candidates_pct", round(100 * len(cand) / df["deal_id"].nunique(), 1))
put("rows_in_multiround_candidates", int(cand["rows"].sum()))
put("rows_in_multiround_candidates_pct", round(100 * int(cand["rows"].sum()) / len(df), 1))

# What a finer key would cost. Most of the extra deals a stage-aware key
# creates are not second rounds; they are one round that one source
# labelled and another did not.
base = df.groupby(["company_name", "country", "year"], dropna=False).ngroups
for fld, key in [("funding_stage", "stage"), ("investment_date", "date")]:
    n = df.groupby(["company_name", "country", "year", fld], dropna=False).ngroups
    put(f"extra_deals_if_key_adds_{key}", n - base)

genuine = spurious = 0
for _, sub in df.groupby(["company_name", "country", "year"]):
    st = set(sub["funding_stage"].dropna())
    if len(st) < 2:
        continue
    if len(st & ROUNDS) >= 2:
        genuine += 1
    else:
        spurious += 1
put("stage_splits_genuine", genuine)
put("stage_splits_spurious", spurious)

# ---- 8. the sample shipped with v1.0 is stale ----
# It was drawn before the scope removals ran, so part of it is not in the
# released dataset. Measure it rather than describe it, because the number
# is what justifies redrawing.
old = pd.read_csv(os.path.join(ROOT, "data", "validation_logs",
                               "stage3_validation_sample.csv"))
k = ["deal_id", "investor_name"]
gone = old.merge(df[k], on=k, how="left", indicator=True)
gone = gone[gone["_merge"] == "left_only"]
put("v1_sample_rows", len(old))
put("v1_sample_rows_not_in_dataset", len(gone))
put("v1_sample_rows_not_in_dataset_llm",
    int((gone["extraction_method"] == "llm_extracted").sum()))
put("v1_sample_rows_not_in_dataset_manual",
    int((gone["extraction_method"] == "manual").sum()))

final = [r["value"] for r in rows if r["key"] == "rows_after_within_deal_dedup"][0]
assert final == len(df), (final, len(df))
# one deal as two streams record it, for the paper's example table
EXAMPLE_DEAL = "D040f135c2c"   # TradeDepot, Nigeria, 2021
ex = df[df["deal_id"] == EXAMPLE_DEAL][["investor_name", "investor_type", "investment_date",
                                        "funding_amount_usd", "source_name",
                                        "extraction_method", "confidence_flag"]].copy()
ex["amount_musd"] = (ex["funding_amount_usd"] / 1e6).round(1)
ex.to_csv(os.path.join(OUT, "33_example_deal.csv"), index=False)
put("example_deal_rows", len(ex))
put("example_deal_streams", ex["extraction_method"].nunique())

pd.DataFrame(rows).to_csv(os.path.join(OUT, "30_dataset_paper.csv"), index=False)
print(pd.DataFrame(rows).to_string(index=False))
print(pd.DataFrame(by).to_string(index=False))
print(tab.to_string())
