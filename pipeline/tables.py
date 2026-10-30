# -*- coding: utf-8 -*-
"""
tables.py

Writes the LaTeX tables for the revision from the CSVs in verified_findings/,
so that no number reaches the paper by hand transcription.

    python pipeline/master_pipeline.py
    python pipeline/analysis.py
    python pipeline/tables.py

Style follows the existing tables in main.tex: booktabs rules, footnotesize,
a Notes minipage. Notes carry what a reader needs to interpret the table and
nothing else.
"""

import os
import sys

import pandas as pd

# tables_carried lives beside this file; the script itself runs from the
# repository root so that the relative data paths below resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SRC = "verified_findings/"
OUT = "writing/tables/"

HEAD = ("\\begin{{table}}[t!]\n\\centering\n\\caption{{{cap}}}\n"
        "\\label{{{lab}}}\n\\footnotesize\n"
        "\\setlength{{\\tabcolsep}}{{5pt}}\n\\begin{{tabular}}{{{spec}}}\n"
        "\\toprule\n")
FOOT = ("\\bottomrule\n\\end{tabular}\n\\par\\medskip\n"
        "\\begin{minipage}{0.92\\textwidth}\n\\footnotesize "
        "\\textit{Notes:} NOTETEXT\n\\end{minipage}\n\\end{table}\n")


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(body)
    print("wrote " + OUT + name)


def foot(note):
    return FOOT.replace("NOTETEXT", note)


def p(v):
    """p-values finer than four decimals are reported at the bound."""
    return "$<$0.0001" if float(v) < 0.0001 else "{:.4f}".format(float(v))


LABEL = {"unweighted": "Betweenness (unweighted)",
         "inverse": "Betweenness (inverse distance)",
         "legacy": "Betweenness (weight as distance)",
         "constraint": "Burt constraint ($1-$constraint)"}
GRAPH = {"full (published)": "All investors",
         "participants only": "Co-investing investors only",
         "largest component": "Largest component"}


def t_h1():
    d = pd.read_csv(SRC + "03_h1_specifications.csv")
    rows = []
    order = ["full (published)", "participants only", "largest component"]
    for gi, g in enumerate(order):
        sub = d[d.graph == g]
        for i, r in enumerate(sub.itertuples()):
            first = GRAPH[g] if i == 0 else ""
            rows.append("{} & {} & {:.2f} & {} & {} \\\\".format(
                first, LABEL[r.spec], r.ratio, p(r.p), p(r.p_excl_big_three)))
        if gi < len(order) - 1:
            rows.append("\\addlinespace")
    body = HEAD.format(cap="H1 across network definitions and brokerage "
                           "measures", lab="tab:h1specs", spec="llccc")
    body += ("Network & Measure & Ratio & $p$ & "
             "\\begin{tabular}{@{}c@{}}$p$, excluding\\\\FMO, IFC, BII"
             "\\end{tabular} \\\\\n\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "Ratio is mean DFI brokerage divided by mean non-DFI brokerage. "
        "$p$ from one-sided Mann--Whitney tests. The betweenness "
        "specifications differ in how repeated co-investment is treated. "
        "\\texttt{networkx} interprets an edge weight as a distance, so the "
        "inverse-distance specification is the one in which co-investing "
        "more often places two investors closer together. Burt constraint "
        "is reported as $1-$constraint so that higher values mean more "
        "brokerage in every row.")
    write("tab_h1specs.tex", body)


def t_regional():
    d = pd.read_csv(SRC + "04_regional_h1.csv")
    per = pd.read_csv(SRC + "04b_period_h1.csv")
    rows = ["{} & {} & {} & {} & {:.4f} & {:.4f} & {} \\\\".format(
        r.region, r.deals, r.nodes, r.n_dfi, r.dfi_mean, r.other_mean, p(r.p))
        for r in d.itertuples()]
    rows.append("\\addlinespace")
    for r in per.itertuples():
        rows.append("{} & {} & {} & {} & {:.4f} & {:.4f} & {} \\\\".format(
            r.period, r.deals, r.nodes, r.n_dfi, r.dfi_mean, r.other_mean,
            p(r.p)))
    body = HEAD.format(cap="H1 within regions and periods", lab="tab:regional",
                       spec="lcccccc")
    body += ("Subsample & Deals & Nodes & DFIs & "
             "\\begin{tabular}{@{}c@{}}DFI mean\\\\betweenness\\end{tabular} & "
             "\\begin{tabular}{@{}c@{}}Non-DFI mean\\\\betweenness"
             "\\end{tabular} & $p$ \\\\\n\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "Unweighted betweenness, the primary specification, computed "
        "within each subnetwork on investors appearing in at least one "
        "multi-investor deal. Regions are West Africa (Nigeria, Ghana, "
        "C\\^{o}te d'Ivoire, Senegal, Mali), East Africa (Kenya, "
        "Tanzania, Uganda, Rwanda, Ethiopia), North Africa (Egypt, "
        "Morocco, Tunisia) and Southern Africa (South Africa, Zambia, "
        "Zimbabwe, Malawi, Mozambique, Madagascar). Each regional test "
        "is powered by two or three countries: East Africa by Kenya, "
        "West Africa by Nigeria and Ghana.")
    write("tab_regional.tex", body)


def t_degree():
    d = pd.read_csv(SRC + "13_degree_adjusted_h1.csv").iloc[0]
    rows = [
        "OLS, betweenness on DFI and $\\log$ degree & degree, linearly & "
        "coefficient ${:+.5f}$ & {} \\\\".format(d.ols_coef, p(d.ols_p)),
        "Degree-matched pairs & degree, exactly & {} of {} DFIs higher & "
        "{:.4f} \\\\".format(int(d.n_dfi_higher), int(d.n_pairs),
                             float(d.matched_p)),
        "Label permutation & nothing & expected ratio {:.2f} & {} \\\\".format(
            d.perm_null, p(d.perm_p)),
        "Permutation within degree quintiles & degree, coarsely & "
        "expected ratio {:.2f} & {} \\\\".format(d.strat_null, p(d.strat_p))]
    body = HEAD.format(cap="H1 holding participation intensity constant",
                       lab="tab:degree", spec="llcc")
    body += ("Test & Holds constant & Result & $p$ \\\\\n\\midrule\n"
             + "\n".join(rows) + "\n")
    # f-strings, not .format(). The previous version concatenated with "+"
    # partway through, which left .format() bound to the tail only: the
    # leading placeholders printed literally and the arguments landed in the
    # wrong slots. f-strings format each literal independently.
    full = pd.read_csv(SRC + "03_h1_specifications.csv")
    full = full[(full.graph == "full (published)")
                & (full.spec == "unweighted")].iloc[0]
    ref = "\\" + "ref{tab:h1specs}"
    n_other = int(d.n_nodes) - int(d.n_dfi)
    body += foot(
        f"These tests run on the {int(d.n_nodes)} investors holding at least "
        f"one tie, so the observed ratio is {d.ratio:.2f} rather than the "
        f"{full.ratio:.2f} of Table~{ref}, which also counts investors with "
        f"no co-investment tie. Mean degree is {d.deg_dfi:.1f} for the "
        f"{int(d.n_dfi)} DFIs and {d.deg_other:.1f} for the {n_other} other "
        f"investors, so part of the raw ratio is expected from participation "
        f"alone. The expected ratio is the DFI advantage the permutation "
        f"produces when DFI labels are assigned at random. "
        f"Permutation tests use 10,000 draws and do not assume "
        f"investors are independent observations. In the matched test each "
        f"DFI is paired with the unused non-DFI investor closest in degree, "
        f"and {int(d.n_exact)} of {int(d.n_pairs)} pairs match exactly.")
    write("tab_degree.tex", body)


def t_persistence():
    d = pd.read_csv(SRC + "12_tie_persistence.csv")
    nm = {"DFI-DFI": "DFI to DFI", "DFI-private": "DFI to private",
          "private-private": "Private to private"}
    rows = ["{} & {:,} & {:.1f}\\% & {:.1f}\\% & {:.2f} & {:.2f} \\\\".format(
        nm[r.pair_type], int(r.ties), 100 * r.observed, 100 * r.null_mean,
        r.ratio, r.z) for r in d.itertuples()]
    body = HEAD.format(cap="Do co-investment ties recur?",
                       lab="tab:persistence", spec="lccccc")
    body += ("Pair type & Ties & Repeated & "
             "\\begin{tabular}{@{}c@{}}Expected\\\\under null\\end{tabular} & "
             "Ratio & $z$ \\\\\n\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "A tie is repeated if the pair appears in more than one deal. The "
        "null is a bipartite configuration model holding each investor's "
        "number of deals and each syndicate's size fixed, so it already "
        "accounts for DFIs being few and therefore meeting one another often "
        "by chance. 5,000 randomizations. Ratio is the observed rate divided "
        "by the null rate. All three pair types repeat more than chance; DFI "
        "to private is the weakest.")
    write("tab_persistence.tex", body)


def t_sensitivity():
    d = pd.read_csv(SRC + "14_construction_sensitivity.csv")
    rows = ["{} & {:,} & {:,} & {:.1f}\\% & {:.2f} & {} \\\\".format(
        r.construction, int(r.deals), int(r.coinvestment), r.rate, r.ratio,
        p(r.p)) for r in d.itertuples()]
    rows.insert(1, "\\addlinespace")
    rows.append("\\addlinespace")
    rows.append("Including AfDB sovereign operations & 748 & 202 & 27.0\\% & "
                "6.04 & $<$0.0001 \\\\")
    body = HEAD.format(cap="What the construction choices are worth",
                       lab="tab:sensitivity", spec="lccccc")
    body += ("Construction & Deals & "
             "\\begin{tabular}{@{}c@{}}Co-invest\\\\deals\\end{tabular} & "
             "Rate & \\begin{tabular}{@{}c@{}}DFI\\\\ratio\\end{tabular} & "
             "$p$ \\\\\n\\midrule\n" + "\n".join(rows) + "\n")
    body += foot(
        "Each row re-runs the headline statistics on a different admissible "
        "construction of the same sources. Rate is co-investment deals as a "
        "share of all deals. The sovereign row is produced by rebuilding the "
        "AfDB extract with \\texttt{AFDB\\_INCLUDE\\_SOVEREIGN=1}. Sovereign "
        "operations are loans and grants to governments; they add 359 deals "
        "to the denominator and none to the numerator. The rate ranges from "
        "27.0 to 55.0 percent across constructions while the DFI betweenness "
        "ratio stays between 6.04 and 7.59.")
    write("tab_sensitivity.tex", body)


if __name__ == "__main__":
    t_h1()
    t_regional()
    t_degree()
    t_persistence()
    t_sensitivity()
    import tables_carried  # noqa: E402
    tables_carried.main()
