# -*- coding: utf-8 -*-
"""
tables_carried.py

The tables carried over from the submitted version, regenerated on the
current data so they stop contradicting the rest of the paper. Called by
tables.py; shares its header, footer and file-writing helpers.
"""

import pandas as pd

from tables import SRC, HEAD, foot, write

TYPE_LABEL = {"pe_vc": "Private equity / venture capital",
              "impact_fund": "Impact funds",
              "DFI": "Development finance institutions",
              "corporate": "Corporates",
              "commercial_bank": "Commercial banks",
              "blended_vehicle": "Blended vehicles",
              "unknown": "Unclassified"}
TYPE_SHORT = {"DFI": "DFI", "pe_vc": "PE/VC", "impact_fund": "Impact",
              "corporate": "Corporate", "commercial_bank": "Bank",
              "blended_vehicle": "Blended", "unknown": "Unclassified"}
REF = "\\" + "ref"


def t_summary():
    b = pd.read_csv(SRC + "01_dataset_basics.csv").iloc[0]
    counts = pd.read_csv(SRC + "02_centrality_full.csv") \
        .investor_type.value_counts()
    L = ["\\multicolumn{2}{l}{\\textit{Panel A: Dataset characteristics}} \\\\",
         "\\midrule",
         "Investor--deal records & {:,} \\\\".format(int(b.total_records)),
         "Unique deals & {:,} \\\\".format(int(b.unique_deals)),
         "Unique companies & {:,} \\\\".format(int(b.unique_companies)),
         "Unique investors & {:,} \\\\".format(int(b.unique_investors)),
         "Countries represented & {:,} \\\\".format(int(b.countries)),
         "Co-investment deals (2+ named investors) & {:,} \\\\".format(
             int(b.coinvestment_deals)),
         "\\quad of which: with disclosed amounts & {:,} \\\\".format(
             int(b.coinvestment_with_amount)),
         "\\quad total disclosed volume & \\${:.2f}B \\\\".format(
             b.disclosed_volume_usd / 1e9),
         "\\quad mean (max) investors per deal & {:.1f} ({}) \\\\".format(
             b.mean_investors_per_deal, int(b.max_investors_per_deal)),
         "Rows verified against a primary source & {:.1f}\\% \\\\".format(
             b.pct_confidence_1),
         "\\midrule",
         "\\multicolumn{2}{l}{\\textit{Panel B: Co-investment network}} \\\\",
         "\\midrule",
         "Nodes (investors) & {:,} \\\\".format(int(b.nodes)),
         "Edges (co-investment ties) & {:,} \\\\".format(int(b.edges)),
         "Density & {:.4f} \\\\".format(b.density),
         "Connected components & {:,} \\\\".format(int(b.components)),
         "Largest connected component & {:,} nodes ({:.1f}\\%) \\\\".format(
             int(b.largest_component),
             100 * b.largest_component / b.nodes),
         "\\midrule",
         "\\multicolumn{2}{l}{\\textit{Panel C: Investors by type}} \\\\",
         "\\midrule"]
    for k in ["pe_vc", "impact_fund", "DFI", "corporate", "commercial_bank",
              "blended_vehicle", "unknown"]:
        if k in counts:
            L.append("{} & {:,} \\\\".format(TYPE_LABEL[k], int(counts[k])))
    body = HEAD.format(cap="Dataset and network summary", lab="tab:summary",
                       spec="lr") + "\n".join(L) + "\n"
    body += foot(
        "An investor--deal record is one investor's participation in one "
        "deal. Deal values are as disclosed in primary sources; undisclosed "
        "amounts are excluded from volume totals. Scope and construction "
        "rules are set out in Section~" + REF + "{subsec:scope}.")
    write("tab_summary.tex", body)


def t_central():
    d = pd.read_csv(SRC + "02_centrality_full.csv").head(10)
    rows = ["{} & {} & {} & {:.3f} & {:.3f} & {:.3f} \\\\".format(
        r.investor, TYPE_SHORT.get(r.investor_type, r.investor_type),
        int(r.degree), r.betweenness_unweighted, r.betweenness_inverse,
        r.eigenvector) for r in d.itertuples()]
    body = HEAD.format(cap="Ten most central investors by betweenness",
                       lab="tab:central", spec="llcccc")
    body += ("Investor & Type & Degree & "
             "\\begin{tabular}{@{}c@{}}Betweenness\\\\(unweighted)"
             "\\end{tabular} & "
             "\\begin{tabular}{@{}c@{}}Betweenness\\\\(inverse distance)"
             "\\end{tabular} & Eigenvector \\\\\n\\midrule\n"
             + "\n".join(rows) + "\n")
    body += foot(
        "Centrality computed on the full investor network; betweenness "
        "normalized. Degree is the count of distinct co-investors. Ranked by "
        "unweighted betweenness, the primary specification.")
    write("tab_central.tex", body)


def t_communities():
    d = pd.read_csv(SRC + "05_communities.csv")
    rows = ["{} & {} & {} & {:.1f} \\\\".format(
        r.anchors.replace("; ", ", "), int(r.members),
        int(r.single_community_deals), r.pct_of_tracked)
        for r in d.itertuples()]
    body = HEAD.format(cap="Investor communities in the largest component",
                       lab="tab:communities",
                       spec=">{\\raggedright\\arraybackslash}p{2.9in}ccc")
    body += ("Community (anchor investors, by degree) & Members & "
             "\\begin{tabular}{@{}c@{}}Single-community\\\\deals"
             "\\end{tabular} & "
             "\\begin{tabular}{@{}c@{}}Volume\\\\(\\% of disclosed)"
             "\\end{tabular} \\\\\n\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "Louvain communities on the largest connected component with a fixed "
        "seed. Communities are named by their three highest-degree members. "
        "Membership is the stable object; the numeric labels are "
        "algorithm-dependent. Volume shares cover deals whose investors all "
        "sit in one community.")
    write("tab_communities.tex", body)


def t_geography():
    d = pd.read_csv(SRC + "06_geographic_concentration.csv").head(8)
    fix = {"Cote d'Ivoire": "C\\^{o}te d'Ivoire",
           "C\u00f4te d'Ivoire": "C\\^{o}te d'Ivoire"}
    rows = ["{} & {} & {:,.1f} \\\\".format(
        fix.get(r.country, r.country), int(r.deals), r.volume_usd / 1e6)
        for r in d.itertuples()]
    body = HEAD.format(cap="Countries by co-investment deals and volume",
                       lab="tab:geography", spec="lcc")
    body += ("Country & Co-investment deals & Disclosed volume (\\$M) \\\\\n"
             "\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "Deals recorded at multi-country or global level are excluded, since "
        "they cannot be attributed to a single country. Volume covers deals "
        "with a disclosed amount only.")
    write("tab_geography.tex", body)


def t_segments():
    d = pd.read_csv(SRC + "11_segment_analysis.csv")
    d = d[d.segment != "unknown"]
    nm = {"logistics": "Logistics", "inputs": "Inputs",
          "agritech": "Agritech", "financial_services": "Financial services",
          "processing": "Processing", "production": "Production"}
    rows = ["{} & {:.2f} & {:.0f} & {} \\\\".format(
        nm.get(r.segment, r.segment), r.mean, r.median, int(r.count))
        for r in d.itertuples()]
    body = HEAD.format(cap="Syndicate size by agrifood segment",
                       lab="tab:segments", spec="lccc")
    body += ("Segment & Mean investors per company & Median & Companies \\\\\n"
             "\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "Segment is the modal label across a company's records, since the "
        "field is stored per row although it is a company attribute. Mean "
        "and median are over companies, not deals.")
    write("tab_segments.tex", body)


def main():
    t_summary()
    t_central()
    t_communities()
    t_geography()
    t_segments()
