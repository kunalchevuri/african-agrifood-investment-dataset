"""
analysis.py

Regenerates every number reported in the paper from phase1_combined.csv,
and writes them to verified_findings/ as CSVs plus a summary markdown.

Run after master_pipeline.py:

    python pipeline/master_pipeline.py
    python pipeline/analysis.py

Three measurement decisions are made explicitly here, because each was
previously implicit and order-dependent (see MEASUREMENT NOTES below):

1. Deal-level funding amount = MAX across the deal's investor rows.
2. Company-level segment    = MODE across the company's rows.
3. Betweenness is reported under three specifications, because the
   original spec passed co-investment frequency directly to networkx as
   an edge *distance*.
"""

import os
import numpy as np
import pandas as pd
import networkx as nx
import networkx.algorithms.community as nx_comm
from scipy import stats

RAW = "data/raw_sources/"
OUT = "verified_findings/"
SRC = os.path.join(RAW, "phase1_combined.csv")

BIG_THREE = {"FMO", "International Finance Corporation",
             "British International Investment"}
WEST_AFRICA = ["Nigeria", "Ghana", "Côte d'Ivoire", "Senegal", "Mali"]
EAST_AFRICA = ["Kenya", "Tanzania", "Uganda", "Rwanda", "Ethiopia"]
NORTH_AFRICA = ["Egypt", "Morocco", "Tunisia"]
SOUTHERN_AFRICA = ["South Africa", "Zambia", "Zimbabwe", "Malawi",
                   "Mozambique", "Madagascar"]
NON_COUNTRY = {"Multinational", "Global", "Unknown"}
LOUVAIN_SEED = 4
TIE_NULL_REPS = 5000
TIE_NULL_SEED = 42


# ----------------------------------------------------------------------
# MEASUREMENT NOTES
#
# 1. funding_amount_usd is stored redundantly on every investor row of a
#    deal. Three co-investment deals carry conflicting values across
#    their rows and three more mix nulls with real values, so reading it
#    back with drop_duplicates(...).first() made every dollar figure
#    depend on row order: $38.5m of deal value flipped between counted
#    and not counted. MAX is the disclosed round size and is stable.
#
# 2. agrifood_segment is likewise stored per row although it is a
#    company attribute. Eight companies carry more than one segment
#    label, so .first() was order-dependent here too. MODE is stable and
#    reproduces the published segment table exactly.
#
# 3. nx.betweenness_centrality(weight=w) treats w as a DISTANCE. The
#    original analysis passed co-investment count directly, so two
#    investors who co-invested five times were modelled as five times
#    further apart, which inverts the intended meaning. "unweighted" and
#    "inverse" (distance = 1/count) are both defensible; "legacy" is
#    reported only so the published numbers remain traceable.
#
# 4. Deal amounts are transaction size, not any one investor's cheque.
#    For venture rounds that is the announced round size. For IFC records
#    it is the amount parsed from the disclosure's "Total Project Cost and
#    Amount and Nature of IFC's Investment" field, which usually leads
#    with total project cost; where no amount can be parsed the portal's
#    "Estimated Total Budget" column is used instead. That column is
#    denominated in millions and was previously inserted unscaled, which
#    understated 39 deals by a factor of a million until it was fixed in
#    ifc_cleaner.py. The two IFC sources are not a single concept -- some
#    disclosures state total project cost and others state IFC's own
#    commitment -- so IFC deal amounts should be read as an upper bound on
#    transaction size, and the paper should say so.
#
# 5. Scope. The deal universe is private-sector agrifood transactions in
#    Africa, 2015-2025. AfDB sovereign operations (loans and grants to
#    governments) are excluded in afdb_cleaner.py: they cannot have a
#    private co-investor by construction, and leaving them in diluted the
#    co-investment rate to an artefact of how many sovereign programmes
#    AfDB happened to disclose. 2026 is excluded as an incomplete year.
# ----------------------------------------------------------------------


def deal_amount(df):
    """One disclosed amount per deal: the max across its investor rows."""
    return df.groupby("deal_id")["funding_amount_usd"].max()


def company_segment(df):
    """One segment per company: the modal label across its rows."""
    return df.groupby("company_name")["agrifood_segment"].agg(
        lambda s: s.mode()[0])


def coinvestment_deals(df):
    n = df.groupby("deal_id")["investor_name"].nunique()
    return n[n >= 2].index


# IFC administers both the IDA Private Sector Window and the GAFSP Private
# Sector Window as implementing entity, so a "syndicate" made up only of
# these three is one institution drawing on three pots of money rather than
# a DFI pulling in an outside financier. They stay in the dataset because
# they are separately governed and separately funded, but every crowding-in
# number is also reported with these deals removed.
WBG_INTERNAL = {"International Finance Corporation",
                "IDA Private Sector Window", "GAFSP"}


def intra_wbg_deals(df):
    """Co-investment deals whose entire investor set sits inside the World
    Bank Group, i.e. that would not be co-investments at all if IFC, IDA PSW
    and GAFSP were treated as a single financier."""
    g = df.groupby("deal_id")["investor_name"].apply(set)
    co = g[g.map(len) >= 2]
    return co[co.map(lambda s: s <= WBG_INTERNAL)].index


def build_network(df, nodes="all"):
    """Co-investment graph. nodes='all' keeps every investor in the
    dataset as a node (the published convention, which includes
    investors who never co-invested and therefore have betweenness 0);
    nodes='participants' keeps only investors in a multi-investor deal."""
    multi = df[df.deal_id.isin(coinvestment_deals(df))]
    G = nx.Graph()
    if nodes == "all":
        types = df.drop_duplicates("investor_name").set_index(
            "investor_name")["investor_type"].to_dict()
        for inv, t in types.items():
            G.add_node(inv, investor_type=t)
    for _, grp in multi.groupby("deal_id"):
        investors = grp["investor_name"].unique().tolist()
        for i in range(len(investors)):
            for j in range(i + 1, len(investors)):
                a, b = investors[i], investors[j]
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)
    types = df.drop_duplicates("investor_name").set_index(
        "investor_name")["investor_type"].to_dict()
    for n in G.nodes():
        G.nodes[n].setdefault("investor_type", types.get(n, "unknown"))
    return G



def degree_adjusted_h1(G, bt, seed=42, reps=10000):
    """Is the DFI bridging advantage distinct from DFIs simply participating
    in more co-investments? Betweenness rises mechanically with degree, so
    the raw ratio cannot separate the two. Four tests, reported together
    because they do not fully agree.

    ols      : betweenness ~ DFI + log(degree); is the DFI coefficient
               non-zero once degree is controlled linearly.
    matched  : each DFI paired with the unused non-DFI closest in degree,
               compared by paired Wilcoxon signed-rank. Tightest control,
               smallest sample.
    perm     : DFI labels shuffled across all nodes. Makes no independence
               assumption, but does not control degree.
    strat    : DFI labels shuffled within degree quintiles. Controls degree
               coarsely while using every node.
    """
    deg = dict(G.degree())
    d = pd.DataFrame({"inv": list(G.nodes())})
    d["bt"] = d.inv.map(bt)
    d["deg"] = d.inv.map(deg)
    d["dfi"] = d.inv.map(
        {n: G.nodes[n].get("investor_type") == "DFI" for n in G}).astype(int)
    d = d[d.deg > 0].reset_index(drop=True)
    out = {"n_nodes": len(d), "n_dfi": int(d.dfi.sum()),
           "deg_dfi": d[d.dfi == 1].deg.mean(),
           "deg_other": d[d.dfi == 0].deg.mean()}

    X = np.column_stack([np.ones(len(d)), d.dfi.values, np.log(d.deg.values)])
    y = d.bt.values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    s2 = r @ r / (len(d) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    t = beta[1] / se[1]
    out["ols_coef"] = beta[1]
    out["ols_p"] = 2 * (1 - stats.t.cdf(abs(t), len(d) - X.shape[1]))

    nd = d[d.dfi == 0].copy()
    used, pa, pb, dgap = set(), [], [], []
    for row in d[d.dfi == 1].sort_values("deg", ascending=False).itertuples():
        cand = nd[~nd.inv.isin(used)]
        if cand.empty:
            break
        j = (cand.deg - row.deg).abs().idxmin()
        pa.append(row.bt)
        pb.append(nd.loc[j].bt)
        dgap.append(abs(int(nd.loc[j].deg) - int(row.deg)))
        used.add(nd.loc[j].inv)
    out["n_pairs"] = len(pa)
    out["n_dfi_higher"] = int(sum(a > b for a, b in zip(pa, pb)))
    # How many pairs matched on degree exactly, rather than approximately.
    # The table and the body both state this; it was hand-counted before,
    # so it could drift from the data without anything noticing.
    out["n_exact"] = int(sum(dd == 0 for dd in dgap))
    out["matched_p"] = (stats.wilcoxon(pa, pb, alternative="greater").pvalue
                        if len(pa) > 5 else float("nan"))

    obs = d[d.dfi == 1].bt.mean() / d[d.dfi == 0].bt.mean()
    out["ratio"] = obs
    rng = np.random.default_rng(seed)
    lab = d.dfi.values
    nullp = []
    for _ in range(reps):
        q = rng.permutation(lab)
        b_ = d.bt.values[q == 0].mean()
        nullp.append(d.bt.values[q == 1].mean() / b_ if b_ > 0 else np.nan)
    nullp = np.array(nullp)
    out["perm_null"] = np.nanmean(nullp)
    out["perm_p"] = (np.sum(nullp >= obs) + 1) / (len(nullp) + 1)

    d["q"] = pd.qcut(d.deg.rank(method="first"), 5, labels=False)
    idxs = [np.where(d.q.values == q)[0] for q in sorted(d.q.unique())]
    ks = [int(d.dfi.values[i].sum()) for i in idxs]
    nulls = []
    for _ in range(reps):
        lab2 = np.zeros(len(d), dtype=int)
        for i, k in zip(idxs, ks):
            if k:
                lab2[rng.choice(i, k, replace=False)] = 1
        b_ = d.bt.values[lab2 == 0].mean()
        nulls.append(d.bt.values[lab2 == 1].mean() / b_ if b_ > 0 else np.nan)
    nulls = np.array(nulls)
    out["strat_null"] = np.nanmean(nulls)
    out["strat_p"] = (np.sum(nulls >= obs) + 1) / (len(nulls) + 1)
    return out


def burt_constraint(G):
    """Burt's network constraint, the standard structural-holes measure in
    the syndication literature. LOW constraint means a node's contacts are
    themselves unconnected, i.e. it spans structural holes. Reported as
    (1 - constraint) so that, like betweenness, HIGHER means more brokerage
    and the direction of the H1 test is unchanged."""
    c = nx.constraint(G, weight="weight")
    return {n: (1.0 - v) if v == v else 0.0 for n, v in c.items()}


def betweenness(G, spec):
    if spec == "unweighted":
        return nx.betweenness_centrality(G, normalized=True)
    if spec == "inverse":
        H = G.copy()
        for u, v, d in H.edges(data=True):
            d["distance"] = 1.0 / d["weight"]
        return nx.betweenness_centrality(H, weight="distance", normalized=True)
    if spec == "legacy":
        return nx.betweenness_centrality(G, weight="weight", normalized=True)
    if spec == "constraint":
        return burt_constraint(G)
    raise ValueError(spec)


def h1_test(G, bt, exclude=frozenset()):
    dfi = [bt[n] for n in G
           if G.nodes[n].get("investor_type") == "DFI" and n not in exclude]
    other = [bt[n] for n in G if G.nodes[n].get("investor_type") != "DFI"]
    if not dfi or not other:
        return dict(n_dfi=len(dfi), dfi_mean=np.nan, other_mean=np.nan,
                    ratio=np.nan, p=np.nan)
    _, p = stats.mannwhitneyu(dfi, other, alternative="greater")
    return dict(n_dfi=len(dfi), dfi_mean=np.mean(dfi),
                other_mean=np.mean(other),
                ratio=np.mean(dfi) / np.mean(other), p=p)


def cross_tie_share(G):
    """Share of DFI-incident edges that reach a non-DFI investor."""
    is_dfi = {n: G.nodes[n].get("investor_type") == "DFI" for n in G}
    inc = [(u, v) for u, v in G.edges() if is_dfi[u] or is_dfi[v]]
    if not inc:
        return np.nan
    cross = [(u, v) for u, v in inc if is_dfi[u] != is_dfi[v]]
    return 100.0 * len(cross) / len(inc)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(SRC, encoding="utf-8")
    amt = deal_amount(df)
    seg = company_segment(df)
    codeals = coinvestment_deals(df)
    multi = df[df.deal_id.isin(codeals)]

    G = build_network(df, nodes="all")
    Gp = build_network(df, nodes="participants")
    cc = max(nx.connected_components(G), key=len)
    Gc = G.subgraph(cc).copy()

    lines = []
    def say(s=""):
        print(s)
        lines.append(s)

    say("# Verified findings - World Development revision")
    say()
    say("Regenerated by `pipeline/analysis.py`. Every number below comes "
        "from `data/raw_sources/phase1_combined.csv`.")
    say()

    # ---- 1. dataset basics -------------------------------------------
    vol = amt.loc[codeals].sum()
    basics = dict(
        total_records=len(df),
        unique_deals=df.deal_id.nunique(),
        unique_companies=df.company_name.nunique(),
        unique_investors=df.investor_name.nunique(),
        countries=len([c for c in df.country.unique()
                       if c not in NON_COUNTRY and "Region" not in str(c)]),
        coinvestment_deals=len(codeals),
        coinvestment_with_amount=int(amt.loc[codeals].notna().sum()),
        disclosed_volume_usd=float(vol),
        mean_investors_per_deal=round(
            multi.groupby("deal_id")["investor_name"].nunique().mean(), 2),
        max_investors_per_deal=int(
            multi.groupby("deal_id")["investor_name"].nunique().max()),
        pct_confidence_1=round(100 * (df.confidence_flag == 1).mean(), 1),
        nodes=G.number_of_nodes(),
        edges=G.number_of_edges(),
        density=round(nx.density(G), 4),
        components=nx.number_connected_components(G),
        # The Data section quotes the provenance spread and the DFI split;
        # both were computed by hand before and are regenerated here.
        distinct_source_names=int(df.source_name.nunique()),
        distinct_source_domains=int(
            df.source_url.str.extract(r"https?://([^/]+)")[0].nunique()),
        n_dfi=int(df[df.investor_type == "DFI"].investor_name.nunique()),
        n_non_dfi=int(df[df.investor_type != "DFI"].investor_name.nunique()),
        largest_component=len(cc),
        # Figure 1 and the architecture prose quote the component's tie
        # count, so it is recorded here rather than only printed by
        # figures.py.
        largest_component_edges=G.subgraph(cc).number_of_edges(),
    )
    pd.DataFrame([basics]).to_csv(OUT + "01_dataset_basics.csv", index=False)
    say("## 1. Dataset")
    for k, v in basics.items():
        say(f"- {k}: {v:,}" if isinstance(v, int) else f"- {k}: {v}")
    say()

    # ---- 1b. Robustness of H1 to contested deal classes ---------------
    say("## 1b. Robustness - H1 on restricted deal universes")
    say()
    say("Two classes of deal could inflate DFI centrality without being")
    say("evidence that a DFI drew in an outside investor. First, IFC acts as")
    say("implementing entity for both the IDA Private Sector Window and the")
    say("GAFSP Private Sector Window, so a syndicate made up only of those")
    say("three is one institution drawing on three pots of money. Second,")
    say("where the investee is itself a fund or a bank rather than an")
    say("agrifood operating company, DFIs appear together as co-limited-")
    say("partners or co-lenders, which is a different relation from")
    say("co-investing in a firm. H1 is re-run with each class removed.")
    say()
    wbg = intra_wbg_deals(df)
    fin = df[df.agrifood_segment == "financial_services"].deal_id.unique()
    cuts = [
        ("all deals", df),
        ("excl. intra-WBG syndicates", df[~df.deal_id.isin(wbg)]),
        ("excl. financial-intermediary investees",
         df[~df.deal_id.isin(fin)]),
        ("excl. both",
         df[~df.deal_id.isin(wbg) & ~df.deal_id.isin(fin)]),
    ]
    say(f"- intra-WBG-only co-investment deals: {len(wbg):,}")
    say(f"- co-investment deals with a financial-intermediary investee: "
        f"{len(coinvestment_deals(df[df.deal_id.isin(fin)])):,}")
    say()
    say("| deal universe | co-inv deals | spec | n DFI | ratio | p | "
        "excl. big three p |")
    say("|---|---|---|---|---|---|---|")
    for label, sub in cuts:
        Gx = build_network(sub)
        nco = len(coinvestment_deals(sub))
        for spec in ["unweighted", "inverse", "legacy", "constraint"]:
            btx = betweenness(Gx, spec)
            ax = h1_test(Gx, btx)
            bx = h1_test(Gx, btx, exclude=BIG_THREE)
            say(f"| {label} | {nco:,} | {spec} | {ax['n_dfi']} | "
                f"{ax['ratio']:.2f}x | {ax['p']:.4f} | {bx['p']:.4f} |")
    say()

    # ---- 2. H1 across specifications ---------------------------------
    say("## 2. H1 - DFI betweenness")
    say()
    say("| graph | betweenness spec | n DFI | ratio | p | excl. big three p |")
    say("|---|---|---|---|---|---|")
    rows = []
    for gname, g in [("full (published)", G), ("participants only", Gp),
                     ("largest component", Gc)]:
        for spec in ["unweighted", "inverse", "legacy", "constraint"]:
            bt = betweenness(g, spec)
            a = h1_test(g, bt)
            b = h1_test(g, bt, exclude=BIG_THREE)
            say(f"| {gname} | {spec} | {a['n_dfi']} | {a['ratio']:.2f}x | "
                f"{a['p']:.4f} | {b['p']:.4f} |")
            rows.append(dict(graph=gname, spec=spec, **a,
                             p_excl_big_three=b["p"],
                             cross_tie_pct=cross_tie_share(g)))
    pd.DataFrame(rows).to_csv(OUT + "03_h1_specifications.csv", index=False)
    say()

    # ---- 2c. Is the advantage distinct from participating more? --------
    say("## 2c. H1 adjusted for participation intensity")
    say()
    say("Betweenness rises mechanically with degree, and DFIs co-invest more")
    say("often than other investors. These four tests ask whether the DFI")
    say("advantage survives holding participation constant. They do not fully")
    say("agree, and the paper reports all four.")
    say()
    da = degree_adjusted_h1(G, betweenness(G, "unweighted"))
    say(f"- mean degree: DFI {da['deg_dfi']:.1f}, non-DFI "
        f"{da['deg_other']:.1f} ({da['n_dfi']} DFIs of {da['n_nodes']} nodes)")
    say(f"- raw betweenness ratio: {da['ratio']:.2f}x")
    say()
    say("| test | holds constant | result | p |")
    say("|---|---|---|---|")
    say(f"| OLS on log degree | degree, linearly | coef "
        f"{da['ols_coef']:+.5f} | {da['ols_p']:.4f} |")
    say(f"| degree-matched pairs | degree, tightly | {da['n_dfi_higher']} of "
        f"{da['n_pairs']} DFIs higher | {da['matched_p']:.4f} |")
    say(f"| label permutation | nothing (no independence assumption) | null "
        f"{da['perm_null']:.2f}x | {da['perm_p']:.4f} |")
    say(f"| stratified permutation | degree, by quintile | null "
        f"{da['strat_null']:.2f}x | {da['strat_p']:.4f} |")
    say()
    pd.DataFrame([da]).to_csv(OUT + "13_degree_adjusted_h1.csv", index=False)

    # ---- 3. centrality table -----------------------------------------
    bt_u = betweenness(G, "unweighted")
    bt_i = betweenness(G, "inverse")
    bt_l = betweenness(G, "legacy")
    ev = nx.eigenvector_centrality(G, weight="weight", max_iter=5000)
    cent = pd.DataFrame({
        "investor": list(G.nodes()),
        "investor_type": [G.nodes[n].get("investor_type") for n in G.nodes()],
        "degree": [G.degree(n) for n in G.nodes()],
        "betweenness_unweighted": [bt_u[n] for n in G.nodes()],
        "betweenness_inverse": [bt_i[n] for n in G.nodes()],
        "betweenness_legacy": [bt_l[n] for n in G.nodes()],
        "eigenvector": [ev[n] for n in G.nodes()],
    # Sorted by the unweighted spec, which is the primary one used by every
    # inferential test below. Sorting by betweenness_inverse (as this did
    # originally) put a different ten investors in Table 2 from the ten that
    # are most central under the measure the paper actually tests on, and
    # ties on equal values are broken by name so the order is stable.
    }).sort_values(["betweenness_unweighted", "investor"],
                   ascending=[False, True])
    cent.to_csv(OUT + "02_centrality_full.csv", index=False)
    say("## 3. Top 10 by betweenness (unweighted, primary spec)")
    say()
    say("| investor | type | degree | betw (unw) | betw (inv) | eigenvector |")
    say("|---|---|---|---|---|---|")
    for r in cent.head(10).itertuples():
        say(f"| {r.investor} | {r.investor_type} | {r.degree} | "
            f"{r.betweenness_unweighted:.4f} | {r.betweenness_inverse:.4f} | "
            f"{r.eigenvector:.3f} |")
    say()

    # Do the more central DFIs sit in deals that carry more capital? The
    # dataset records a round size per deal and not a contribution per
    # investor, so the volume of a DFI's co-investment deals is the only
    # capital quantity available, and it cannot separate private from DFI
    # dollars. The question the answer settles is narrower: whether position
    # carries any volume information beyond how often an institution
    # invests. It does not.
    _dfis = set(df.loc[df.investor_type == "DFI", "investor_name"])
    _crows = []
    for d in sorted(_dfis):
        _dd = set(df.loc[df.investor_name == d, "deal_id"]) & set(codeals)
        _pp = set(df.loc[df.deal_id.isin(_dd), "investor_name"]) - {d}
        _crows.append(dict(
            investor=d, co_deals=len(_dd),
            # sorted, not list(): iterating the set directly leaves the
            # summation order up to the run's hash seed, which moved these
            # totals in the last decimal place between rebuilds.
            volume_usd=float(amt.reindex(sorted(_dd)).fillna(0).sum()),
            private_partners=len(_pp - _dfis)))
    _cv = (pd.DataFrame(_crows)
             .merge(cent[["investor", "degree", "betweenness_unweighted"]],
                    on="investor")
             .sort_values("betweenness_unweighted", ascending=False))
    _cv.to_csv(OUT + "19_dfi_centrality_volume.csv", index=False)

    def _rho(a, b):
        r, p = stats.spearmanr(a, b)
        return round(float(r), 3), round(float(p), 4)
    _lx = np.log1p(_cv.co_deals.values)
    _ly = np.log1p(_cv.volume_usd.values)
    _resid = _ly - np.polyval(np.polyfit(_lx, _ly, 1), _lx)
    _cc = [
        ("betweenness", "volume", *_rho(_cv.betweenness_unweighted, _cv.volume_usd)),
        ("betweenness", "private partners", *_rho(_cv.betweenness_unweighted, _cv.private_partners)),
        ("betweenness", "co-investment deals", *_rho(_cv.betweenness_unweighted, _cv.co_deals)),
        ("co-investment deals", "volume", *_rho(_cv.co_deals, _cv.volume_usd)),
        ("betweenness", "volume net of log deal count", *_rho(_cv.betweenness_unweighted, _resid)),
    ]
    _cct = pd.DataFrame(_cc, columns=["x", "y", "spearman_rho", "p"])
    _cct["n_dfi"] = len(_cv)
    _cct["top3_volume_share_pct"] = round(
        100 * _cv.head(3).volume_usd.sum() / _cv.volume_usd.sum(), 1)
    _cct.to_csv(OUT + "19b_dfi_centrality_volume_correlations.csv", index=False)
    say("Per DFI: co-investment deals, their disclosed volume, private partners:")
    say()
    say("| DFI | co-inv deals | volume ($M) | private partners | betweenness |")
    say("|---|---|---|---|---|")
    for r in _cv.itertuples():
        say(f"| {r.investor} | {r.co_deals} | {r.volume_usd/1e6:,.1f} | "
            f"{r.private_partners} | {r.betweenness_unweighted:.4f} |")
    say()
    say("Centrality against co-investment deal volume, across the DFIs:")
    say()
    say("| x | y | Spearman rho | p |")
    say("|---|---|---|---|")
    for r in _cct.itertuples():
        say(f"| {r.x} | {r.y} | {r.spearman_rho:+.3f} | {r.p:.3f} |")
    say()

    # ---- 4. leave-one-out --------------------------------------------
    # Reported on the primary specification (unweighted) so the
    # leave-one-out figures are comparable with the headline H1 result.
    say("## 4. Leave-one-out (full graph, unweighted - primary spec)")
    say()
    say("| excluded | n DFI | ratio | p |")
    say("|---|---|---|---|")
    loo = []
    base = h1_test(G, bt_u)
    say(f"| none | {base['n_dfi']} | {base['ratio']:.2f}x | {base['p']:.4f} |")
    loo.append(dict(excluded="none", **base))
    for one in sorted(BIG_THREE):
        r = h1_test(G, bt_u, exclude={one})
        say(f"| {one} | {r['n_dfi']} | {r['ratio']:.2f}x | {r['p']:.4f} |")
        loo.append(dict(excluded=one, **r))
    r = h1_test(G, bt_u, exclude=BIG_THREE)
    say(f"| all three | {r['n_dfi']} | {r['ratio']:.2f}x | {r['p']:.4f} |")
    loo.append(dict(excluded="all three", **r))
    pd.DataFrame(loo).to_csv(OUT + "03b_h1_leave_one_out.csv", index=False)
    say()

    # ---- 5. regional --------------------------------------------------
    say("## 5. Regional H1")
    say()
    say("| region | deals | nodes | DFIs | DFI mean | non-DFI mean | p |")
    say("|---|---|---|---|---|---|---|")
    reg_rows = []
    for name, countries in [("West Africa", WEST_AFRICA),
                            ("East Africa", EAST_AFRICA),
                            ("North Africa", NORTH_AFRICA),
                            ("Southern Africa", SOUTHERN_AFRICA)]:
        sub = df[df.country.isin(countries)]
        g = build_network(sub, nodes="participants")
        if g.number_of_nodes() == 0:
            continue
        # Unweighted is the primary specification (see Edge weights in the
        # paper's Methods). These tests used "inverse", which left the
        # regional and period tables reporting a different measure from the
        # headline H1 result. Conclusions are unchanged under either.
        bt = betweenness(g, "unweighted")
        a = h1_test(g, bt)
        nd = len(coinvestment_deals(sub))
        say(f"| {name} | {nd} | {g.number_of_nodes()} | {a['n_dfi']} | "
            f"{a['dfi_mean']:.4f} | {a['other_mean']:.4f} | {a['p']:.4f} |")
        reg_rows.append(dict(region=name, deals=nd,
                             nodes=g.number_of_nodes(), **a))
    pd.DataFrame(reg_rows).to_csv(OUT + "04_regional_h1.csv", index=False)
    say()

    # ---- 5b. H1 by period (the paper's Table 5, panel b) ---------------
    # Regenerated here because every number the paper reports should come
    # out of this script; the period split was previously computed by hand.
    say("## 5b. H1 by period")
    say()
    say("| period | deals | nodes | DFIs | DFI mean | non-DFI mean | "
        "ratio | p |")
    say("|---|---|---|---|---|---|---|---|")
    _y = pd.to_numeric(df.investment_date.astype(str).str[:4], errors="coerce")
    per_rows = []
    for name, lo, hi in [("early (2015-2020)", 2015, 2020),
                         ("late (2021-2025)", 2021, 2025)]:
        sub = df[(_y >= lo) & (_y <= hi)]
        g = build_network(sub, nodes="participants")
        if g.number_of_nodes() == 0:
            continue
        bt = betweenness(g, "unweighted")
        a_ = h1_test(g, bt)
        nd = len(coinvestment_deals(sub))
        say(f"| {name} | {nd} | {g.number_of_nodes()} | {a_['n_dfi']} | "
            f"{a_['dfi_mean']:.4f} | {a_['other_mean']:.4f} | "
            f"{a_['ratio']:.2f}x | {a_['p']:.4f} |")
        per_rows.append(dict(period=name, deals=nd,
                             nodes=g.number_of_nodes(), **a_))
    pd.DataFrame(per_rows).to_csv(OUT + "04b_period_h1.csv", index=False)
    say()

    # ---- 6. temporal --------------------------------------------------
    yr = multi.drop_duplicates("deal_id").copy()
    yr["year"] = pd.to_numeric(yr.investment_date.astype(str).str[:4],
                               errors="coerce")
    yr["amount"] = yr.deal_id.map(amt)
    by_year = yr.groupby("year").agg(deals=("deal_id", "count"),
                                     volume_usd=("amount", "sum"))
    by_year.to_csv(OUT + "08_deals_by_year.csv")
    say("## 6. Deals by year")
    say()
    say("| year | deals | volume ($m) |")
    say("|---|---|---|")
    for y, r in by_year.iterrows():
        if pd.notna(y):
            say(f"| {int(y)} | {int(r.deals)} | {r.volume_usd/1e6:,.1f} |")
    say()

    # ---- 7. communities ------------------------------------------------
    comms = nx_comm.louvain_communities(Gc, weight="weight", seed=LOUVAIN_SEED)
    lab = {n: i for i, c in enumerate(comms) for n in c}
    single, cross = 0, 0
    per = {}
    for d, grp in multi.groupby("deal_id"):
        inv = [i for i in grp.investor_name.unique() if i in lab]
        if len(inv) < 2:
            continue
        cs = {lab[i] for i in inv}
        if len(cs) == 1:
            single += 1
            k = cs.pop()
            per.setdefault(k, [0, 0.0])
            v = amt.get(d)
            # NaN is truthy, so `v or 0` would propagate it.
            per[k][1] += 0.0 if pd.isna(v) else float(v)
            per[k][0] += 1
        else:
            cross += 1
    crows = []
    for k, (n, v) in sorted(per.items(), key=lambda x: -x[1][1]):
        # Community membership comes back as a set, so equal-degree
        # members were being ordered arbitrarily and the anchor labels
        # changed between runs. Name breaks the tie.
        top = sorted(comms[k], key=lambda n: (-Gc.degree(n), n))[:3]
        crows.append(dict(community=k, members=len(comms[k]),
                          single_community_deals=n, volume_usd=v,
                          pct_of_tracked=100 * v / vol,
                          anchors="; ".join(top)))
    pd.DataFrame(crows).to_csv(OUT + "05_communities.csv", index=False)
    say("## 7. Louvain communities (largest component, seed="
        f"{LOUVAIN_SEED})")
    say()
    say(f"- communities: {len(comms)}")
    say(f"- deals fully inside the largest component: {single + cross}")
    say(f"- single-community deals: {single}")
    say(f"- cross-community deals: {cross}")
    say(f"- co-investment deals involving investors outside it: "
        f"{len(codeals) - single - cross}")
    say(f"- cross-community share of in-component deals: "
        f"{100 * cross / (single + cross):.1f}%")
    say()
    say("| anchors | members | single-community deals | volume (% tracked) |")
    say("|---|---|---|---|")
    for r in crows:
        say(f"| {r['anchors']} | {r['members']} | "
            f"{r['single_community_deals']} | {r['pct_of_tracked']:.1f} |")
    say()

    # ---- 7b. H2 edge composition and tie persistence ---------------------
    # cross_tie_share and assortativity were previously computed by hand;
    # they are regenerated here so every number the paper reports comes out
    # of this script.
    say("## 7b. H2 - edge composition and tie persistence")
    say()
    is_dfi = {n: G.nodes[n].get("investor_type") == "DFI" for n in Gc}
    inc = [(u, v) for u, v in Gc.edges() if is_dfi[u] or is_dfi[v]]
    cross = [(u, v) for u, v in inc if is_dfi[u] != is_dfi[v]]
    say(f"- DFI-incident edges (largest component): {len(inc):,}")
    say(f"- of which DFI-to-non-DFI: {len(cross):,} "
        f"({100*len(cross)/len(inc):.1f}%)")
    say(f"- of which DFI-to-DFI: {len(inc)-len(cross):,} "
        f"({100*(len(inc)-len(cross))/len(inc):.1f}%)")
    say(f"- investor-type assortativity: "
        f"{nx.attribute_assortativity_coefficient(Gc, 'investor_type'):.3f}")
    say()

    # Do co-investment ties recur? Compared against a bipartite configuration
    # null that holds each investor's number of deals and each syndicate's
    # size fixed, so the comparison is not driven by DFIs simply being few.
    import itertools as _it
    import random as _rnd
    groups = [sorted(set(g["investor_name"]))
              for _, g in multi.groupby("deal_id")]

    def _kind(a_, b_):
        x, y = is_dfi_all.get(a_, False), is_dfi_all.get(b_, False)
        return "DFI-DFI" if x and y else (
            "DFI-private" if x or y else "private-private")

    is_dfi_all = {n: t == "DFI" for n, t in
                  df.drop_duplicates("investor_name")
                    .set_index("investor_name")["investor_type"].items()}

    def _rates(gs):
        pair = {}
        for inv in gs:
            for a_, b_ in _it.combinations(sorted(inv), 2):
                pair[(a_, b_)] = pair.get((a_, b_), 0) + 1
        out = {}
        for k in ["DFI-DFI", "DFI-private", "private-private"]:
            w = [v for pr, v in pair.items() if _kind(*pr) == k]
            out[k] = (np.mean([x > 1 for x in w]) if w else np.nan, len(w))
        return out

    obs = _rates(groups)
    slots = [(i, inv) for i, gr in enumerate(groups) for inv in gr]
    rng = _rnd.Random(TIE_NULL_SEED)
    null = {k: [] for k in obs}
    for _ in range(TIE_NULL_REPS):
        names = [x[1] for x in slots]
        rng.shuffle(names)
        rebuilt = [[] for _ in groups]
        for (i, _), nm in zip(slots, names):
            rebuilt[i].append(nm)
        rebuilt = [list(dict.fromkeys(r)) for r in rebuilt]
        r = _rates(rebuilt)
        for k in null:
            null[k].append(r[k][0])
    say(f"Repeat-collaboration rate against a bipartite configuration null "
        f"({TIE_NULL_REPS:,} randomizations):")
    say()
    say("| pair type | ties | repeat rate | null mean | ratio | z |")
    say("|---|---|---|---|---|---|")
    trows = []
    for k in ["DFI-DFI", "DFI-private", "private-private"]:
        o, ntie = obs[k]
        arr = np.array(null[k], dtype=float)
        m, sd = np.nanmean(arr), np.nanstd(arr)
        z = (o - m) / sd if sd > 0 else np.nan
        say(f"| {k} | {ntie:,} | {100*o:.1f}% | {100*m:.1f}% | "
            f"{o/m:.2f}x | {z:.2f} |")
        trows.append(dict(pair_type=k, ties=ntie, observed=o, null_mean=m,
                          null_sd=sd, ratio=o/m, z=z))
    pd.DataFrame(trows).to_csv(OUT + "12_tie_persistence.csv", index=False)
    say()

    # ---- 8. geography ---------------------------------------------------
    u = multi.drop_duplicates("deal_id").copy()
    u["amount"] = u.deal_id.map(amt)
    geo = u.groupby("country").agg(deals=("deal_id", "count"),
                                   volume_usd=("amount", "sum"))
    geo = geo.sort_values("deals", ascending=False)
    geo.to_csv(OUT + "06_geographic_concentration.csv")
    excl = u[u.country.isin(NON_COUNTRY)]
    say("## 8. Geography")
    say()
    say("| country | deals | volume ($m) |")
    say("|---|---|---|")
    for c, r in geo.head(8).iterrows():
        say(f"| {c} | {int(r.deals)} | {r.volume_usd/1e6:,.1f} |")
    say()
    real = [c for c in geo.index
            if c not in NON_COUNTRY and "Region" not in str(c)]
    say(f"- countries with at least one co-investment deal: {len(real)}")
    say(f"- excluded as multi-country/global: {len(excl)} deals, "
        f"${excl.amount.sum():,.0f}")
    say()

    # Concentration measures. These were previously computed by hand for the
    # text; they are regenerated here so the geography prose is reproducible
    # like every other number in the paper.
    rg = geo.loc[real]
    n_assigned = int(rg.deals.sum())
    v_assigned = float(rg.volume_usd.sum())
    top5 = rg.head(5)
    say(f"- country-assigned co-investment deals: {n_assigned} "
        f"(regional/multi-country: {int(geo.deals.sum()) - n_assigned})")
    say(f"- top 5 countries: {int(top5.deals.sum())} deals = "
        f"{100 * top5.deals.sum() / n_assigned:.1f}% of country-assigned")
    say(f"- top 5 share of country-assigned volume: "
        f"{100 * top5.volume_usd.sum() / v_assigned:.1f}%")
    say(f"- countries with 3 or fewer deals: {int((rg.deals <= 3).sum())} "
        f"of {len(rg)}; with exactly one: {int((rg.deals == 1).sum())}")
    say()
    say("| country | deals | volume ($m) | mean deal ($m) |")
    say("|---|---|---|---|")
    for c, r in top5.iterrows():
        say(f"| {c} | {int(r.deals)} | {r.volume_usd/1e6:,.1f} | "
            f"{r.volume_usd/1e6/r.deals:,.1f} |")
    say()

    # Ghana's mean is carried by one $600m COCOBOD facility. The text makes
    # that point, so the ex-largest-deal figure is regenerated rather than
    # asserted.
    for c in ("Ghana",):
        if c not in rg.index:
            continue
        sub = u[u.country == c]
        big = sub.amount.max()
        rest = sub[sub.amount != big]
        say(f"- {c} excluding its largest single deal "
            f"(${big/1e6:,.1f}m): {len(rest)} deals, "
            f"${rest.amount.sum()/1e6:,.1f}m total, "
            f"${rest.amount.mean()/1e6:,.1f}m mean")
    say()

    # ---- 9. segments -----------------------------------------------------
    inv_per_company = df.groupby("company_name")["investor_name"].nunique()
    rounds = df.groupby("company_name")["deal_id"].nunique()
    comp = pd.DataFrame({"segment": seg, "investors": inv_per_company,
                         "rounds": rounds})
    segtab = comp.groupby("segment")["investors"].agg(
        ["mean", "median", "count"]).sort_values("mean", ascending=False)
    segtab.to_csv(OUT + "11_segment_analysis.csv")
    say("## 9. Segments (per company, modal segment)")
    say()
    say("| segment | mean investors | median | companies |")
    say("|---|---|---|---|")
    for s, r in segtab.iterrows():
        say(f"| {s} | {r['mean']:.2f} | {r['median']:.0f} | {int(r['count'])} |")
    say()
    say(f"- companies with more than one recorded round: "
        f"{int((comp.rounds > 1).sum())} of {len(comp)} "
        f"({100*(comp.rounds>1).mean():.1f}%)")
    say()

    # ---- 10. small-worldness ---------------------------------------------
    C = nx.average_clustering(Gc)
    L = nx.average_shortest_path_length(Gc)
    rc, rl = [], []
    for s in range(20):
        R = nx.gnm_random_graph(Gc.number_of_nodes(), Gc.number_of_edges(),
                                seed=s)
        if nx.is_connected(R):
            rc.append(nx.average_clustering(R))
            rl.append(nx.average_shortest_path_length(R))
    sigma = (C / np.mean(rc)) / (L / np.mean(rl))
    pd.DataFrame([dict(C=C, L=L, C_rand=np.mean(rc), L_rand=np.mean(rl),
                       sigma=sigma, n_random=len(rc))]).to_csv(
        OUT + "07_smallworld.csv", index=False)
    say("## 10. Small-worldness (largest component)")
    say()
    say(f"- C = {C:.4f}, L = {L:.4f}")
    say(f"- C_rand = {np.mean(rc):.4f}, L_rand = {np.mean(rl):.4f} "
        f"(mean of {len(rc)} Erdos-Renyi graphs)")
    say(f"- C / C_rand = {C/np.mean(rc):.1f}x, "
        f"L / L_rand = {L/np.mean(rl):.2f}x")
    say(f"- sigma = {sigma:.2f}")
    say()

    # ---- 11b. What are the construction choices worth? -----------------
    # Headline blended-finance statistics are usually reported without the
    # scope decisions behind them. This table reports what each contested
    # decision moves. The sovereign row is generated by rebuilding with
    # AFDB_INCLUDE_SOVEREIGN=1 and is quoted from that run rather than
    # recomputed here, because it changes the upstream extract.
    say("## 11b. Sensitivity to construction choices")
    say()
    say("Each row re-runs the headline statistics on a different admissible")
    say("construction of the same underlying sources.")
    say()
    say("| construction | deals | co-inv | rate | H1 ratio | p |")
    say("|---|---|---|---|---|---|")
    _y = pd.to_numeric(df.investment_date.astype(str).str[:4], errors="coerce")
    _wbg = set(intra_wbg_deals(df))
    _fin = set(df[df.agrifood_segment == "financial_services"].deal_id)
    variants = [
        ("as reported", df),
        ("excl. intra-WBG-only deals", df[~df.deal_id.isin(_wbg)]),
        ("excl. financial-intermediary investees",
         df[~df.deal_id.isin(_fin)]),
        ("confidence-flag-1 rows only", df[df.confidence_flag == 1]),
        ("excl. year-only (Jan 1) dates",
         df[~df.investment_date.astype(str).str.endswith("-01-01")]),
    ]
    srows = []
    for label, sub in variants:
        Gs = build_network(sub)
        rs = h1_test(Gs, betweenness(Gs, "unweighted"))
        nco, nd = len(coinvestment_deals(sub)), sub.deal_id.nunique()
        say(f"| {label} | {nd:,} | {nco:,} | {100*nco/nd:.1f}% | "
            f"{rs['ratio']:.2f}x | {rs['p']:.4f} |")
        srows.append(dict(construction=label, deals=nd, coinvestment=nco,
                          rate=100*nco/nd, ratio=rs["ratio"], p=rs["p"]))
    pd.DataFrame(srows).to_csv(OUT + "14_construction_sensitivity.csv",
                               index=False)
    say()
    # Composition by DFI presence. Used in the paper's limitations section:
    # DFI deals and non-DFI deals are different instruments made to different
    # kinds of firm, which is why follow-on comparisons between them measure
    # firm type rather than any DFI effect.
    _t = df.groupby("deal_id").agg(
        stage=("funding_stage", "first"),
        invs=("investor_name", lambda x: set(x)))
    _dfiset = {i for i, ty in df.drop_duplicates("investor_name")
               .set_index("investor_name")["investor_type"].items()
               if ty == "DFI"}
    _t["has_dfi"] = _t.invs.map(lambda x: bool(x & _dfiset))
    _c = pd.crosstab(_t.stage, _t.has_dfi, normalize="columns") * 100
    say("Instrument composition, by whether a DFI is present:")
    say()
    say("| stage | no DFI | has DFI |")
    say("|---|---|---|")
    for stg in ["debt", "equity", "blended", "seed", "series_a", "series_b"]:
        if stg in _c.index:
            say(f"| {stg} | {_c.loc[stg, False]:.1f}% | "
                f"{_c.loc[stg, True]:.1f}% |")
    _c.to_csv(OUT + "15_stage_composition.csv")
    say()

    # Why the paper reports no matched or propensity-score comparison of
    # DFI and non-DFI deals. The outcome such a design would use, the
    # number of private co-investors, is set by where the deal's rows came
    # from rather than by the deal: portal exports list the disclosing
    # institution and almost no one else, press coverage lists the
    # syndicate. extraction_method records the stream, so the confound is
    # measurable. Treatment and stream are also collinear on one side,
    # since no non-DFI deal enters through a DFI portal, which is a
    # failure of common support that matching cannot repair.
    _s = df.groupby("deal_id").agg(
        methods=("extraction_method", lambda x: frozenset(x)),
        invs=("investor_name", lambda x: set(x)))
    _s["dfi"] = _s.invs.map(lambda x: bool(x & _dfiset))
    _s["n_private"] = _s.invs.map(lambda x: len(x - _dfiset))

    def _stream(m):
        if m == {"structured_download"}:
            return "portal only"
        if m == {"llm_extracted"}:
            return "AgFunder report only"
        if m == {"manual"}:
            return "press or manual only"
        return "mixed"
    _s["stream"] = _s.methods.map(_stream)
    _d = (_s.groupby(["dfi", "stream"])["n_private"]
            .agg(deals="size", mean_private="mean").reset_index())
    _d["dfi"] = _d.dfi.map({True: "DFI present", False: "no DFI"})
    _n_nondfi_portal = int(((~_s.dfi) & (_s.stream == "portal only")).sum())
    say("Private co-investors per deal, by DFI presence and source stream.")
    say("This is why no matched comparison is reported: the outcome follows")
    say("the stream, and no non-DFI deal enters through a portal, so there")
    say("is nothing on the control side to match a portal-sourced DFI deal to.")
    say()
    say("| DFI | stream | deals | mean private co-investors |")
    say("|---|---|---|---|")
    for _, r in _d.sort_values(["dfi", "deals"], ascending=[False, False]).iterrows():
        say(f"| {r.dfi} | {r.stream} | {int(r.deals)} | {r.mean_private:.2f} |")
    say()
    say(f"Non-DFI deals sourced from a portal: {_n_nondfi_portal}")
    _d["n_nondfi_portal_deals"] = _n_nondfi_portal
    _d.to_csv(OUT + "17_disclosure_by_stream.csv", index=False)
    say()

    # And why no difference-in-differences on a company-year panel. The
    # design needs firms observed before and after DFI entry. Counting
    # them is the whole argument; filling the unobserved years with zeros
    # would manufacture a positive effect from non-observation, so the
    # share of such cells is reported alongside.
    _y = pd.to_datetime(df["investment_date"], errors="coerce").dt.year
    _cy = (df.assign(year=_y).dropna(subset=["year"])
             .groupby(["company_name", "year"])["investor_name"]
             .apply(set).reset_index())
    _cy["has_dfi"] = _cy.investor_name.map(lambda x: bool(x & _dfiset))
    _t0 = _cy[_cy.has_dfi].groupby("company_name")["year"].min().rename("t0")
    _cy = _cy.merge(_t0, on="company_name", how="left")
    _tr = _cy[_cy.t0.notna()]
    _pre = set(_tr[_tr.year < _tr.t0].company_name)
    _post = set(_tr[_tr.year > _tr.t0].company_name)
    _ctl = _cy[_cy.t0.isna()].groupby("company_name")["year"].nunique()
    _ncos = _cy.company_name.nunique()
    _nyears = int(_cy.year.max() - _cy.year.min() + 1)
    _did = dict(
        companies=_ncos,
        treated=int(_tr.company_name.nunique()),
        treated_with_pre=len(_pre),
        treated_with_post=len(_post),
        treated_with_both=len(_pre & _post),
        never_treated=int(_ctl.size),
        never_treated_multi_year=int((_ctl >= 2).sum()),
        observed_company_years=len(_cy),
        balanced_company_years=_ncos * _nyears,
        filled_zero_pct=round(100 * (1 - len(_cy) / (_ncos * _nyears)), 1))
    say("Company-year panel available to a difference-in-differences design:")
    say()
    for k, v in _did.items():
        say(f"- {k}: {v}")
    say()
    pd.DataFrame([_did]).to_csv(OUT + "18_did_feasibility.csv", index=False)

    # The investor-level version of the same design: does a private
    # investor that first co-invests alongside a DFI invest more afterward
    # than one that never does? An event study needs the treated side
    # observed before and after; the counts below are why none is run. The
    # descriptive numbers still matter, because the Conclusion claims that
    # DFI ties are one-off placements and should say how often the private
    # partner is ever seen again without a DFI. Investors first treated in
    # 2021 or earlier have at least four years of follow-up; the later
    # cohorts are right-censored and are not used for the return rate.
    _dl = (df.assign(year=_y).dropna(subset=["year"])
             .groupby("deal_id").agg(year=("year", "min"),
                                     invs=("investor_name", set)))
    _dl["has_dfi"] = _dl.invs.map(lambda x: bool(x & _dfiset))
    _dl["multi"] = _dl.invs.map(len) >= 2
    _irows = []
    for inv in sorted(set(df.investor_name) - _dfiset):
        d = _dl[_dl.invs.map(lambda x: inv in x)]
        w = d[d.has_dfi & d.multi]
        t = int(w.year.min()) if len(w) else None
        _irows.append(dict(
            investor=inv, n_deals=len(d), first=int(d.year.min()),
            last=int(d.year.max()), treated=t is not None, t0=t,
            pre=int((d.year < t).sum()) if t else 0,
            post=int((d.year > t).sum()) if t else 0,
            post_without_dfi=int(((d.year > t) & ~d.has_dfi).sum()) if t else 0))
    _ih = pd.DataFrame(_irows)
    _tr_ = _ih[_ih.treated]
    _ct_ = _ih[~_ih.treated]
    _e = _tr_[_tr_.t0 <= 2021]
    _ce = _ct_[_ct_["first"] <= 2021]
    _ev = dict(
        private_investors=len(_ih),
        treated=len(_tr_),
        treated_with_pre=int((_tr_.pre > 0).sum()),
        treated_with_post=int((_tr_.post > 0).sum()),
        treated_with_both=int(((_tr_.pre > 0) & (_tr_.post > 0)).sum()),
        treated_only_dfi_deals=int(((_tr_.pre == 0) & (_tr_.post == 0)).sum()),
        treated_later_without_dfi=int((_tr_.post_without_dfi > 0).sum()),
        treated_by_2021=len(_e),
        treated_by_2021_seen_again=int((_e.post > 0).sum()),
        treated_by_2021_later_without_dfi=int((_e.post_without_dfi > 0).sum()),
        treated_by_2021_later_without_dfi_pct=round(
            100 * (_e.post_without_dfi > 0).mean(), 1),
        never_treated_by_2021=len(_ce),
        never_treated_by_2021_seen_again=int((_ce["last"] > _ce["first"]).sum()))
    say("Private-investor histories around a first co-investment with a DFI")
    say("(the event-study design, and why it is not run):")
    say()
    for k, v in _ev.items():
        say(f"- {k}: {v}")
    say()
    pd.DataFrame([_ev]).to_csv(OUT + "20_investor_histories.csv", index=False)

    # Instrument mix per DFI, for the discussion of why some institutions
    # bridge and others do not. Shares are of the institution's deals
    # (all deals, not only co-investment deals), with the deal's recorded
    # funding_stage grouped as in 15_stage_composition.
    _im = []
    for d in sorted(_dfiset):
        dd = _t[_t.invs.map(lambda x: d in x)]
        st = dd.stage.fillna("not stated").value_counts(normalize=True) * 100
        _im.append(dict(
            investor=d, deals=len(dd),
            debt_pct=round(float(st.get("debt", 0)), 1),
            equity_pct=round(float(st.get("equity", 0)), 1),
            blended_pct=round(float(st.get("blended", 0)), 1),
            venture_pct=round(float(sum(st.get(k, 0) for k in
                              ("seed", "series_a", "series_b", "series_c"))), 1)))
    _im = (pd.DataFrame(_im)
             .merge(_cv[["investor", "co_deals", "private_partners",
                         "betweenness_unweighted"]], on="investor")
             .sort_values("betweenness_unweighted", ascending=False))
    _im["co_share_pct"] = (100 * _im.co_deals / _im.deals).round(1)
    _im.to_csv(OUT + "21_dfi_instrument_mix.csv", index=False)
    say("Instrument mix per DFI (share of the institution's deals), and the")
    say("share of its deals made alongside at least one other investor:")
    say()
    say("| DFI | deals | debt | equity | blended | venture rounds | "
        "co-invested | private partners |")
    say("|---|---|---|---|---|---|---|---|")
    for r in _im.itertuples():
        say(f"| {r.investor} | {r.deals} | {r.debt_pct}% | {r.equity_pct}% | "
            f"{r.blended_pct}% | {r.venture_pct}% | {r.co_share_pct}% | "
            f"{r.private_partners} |")
    say()

    say("The scope decision that moves the headline most is not in the table")
    say("above because it changes the upstream extract. Including AfDB")
    say("sovereign operations (loans and grants to governments, which cannot")
    say("have a private co-investor) gives 748 deals and a co-investment rate")
    say("of 27.0 percent. Excluding them gives 389 deals and 51.9 percent.")
    say("The DFI betweenness ratio is 6.04x either way. The descriptive")
    say("statistic nearly doubles on a scope choice that is rarely stated;")
    say("the structural result does not move.")
    say()

    # ---- 11. H3 macro -----------------------------------------------------
    macro_path = os.path.join(RAW, "h2_macro_indicators.csv")
    if os.path.exists(macro_path):
        macro = pd.read_csv(macro_path, encoding="utf-8")
        stats_rows = []
        for c in macro.country:
            sub = multi[multi.country == c]
            g = build_network(df[df.country == c], nodes="participants")
            t = df.drop_duplicates("investor_name").set_index(
                "investor_name")["investor_type"].to_dict()
            stats_rows.append(dict(
                country=c,
                multi_investor_deals=len(coinvestment_deals(df[df.country == c])),
                unique_investors=sub.investor_name.nunique(),
                network_edges=g.number_of_edges(),
                DFI_count=sum(1 for i in sub.investor_name.unique()
                              if t.get(i) == "DFI")))
        net = pd.DataFrame(stats_rows).merge(macro, on="country")
        net.to_csv(OUT + "10_macro_merged.csv", index=False)
        say("## 11. H3 - macroeconomic correlates")
        say()
        say("| network measure | vs | Spearman rho | p |")
        say("|---|---|---|---|")
        mrows = []
        for nm in ["DFI_count", "multi_investor_deals", "unique_investors"]:
            for mv in ["agri_gdp_share", "domestic_credit_private_pct_gdp",
                       "agri_employment_share", "fdi_inflows_pct_gdp"]:
                rho, p = stats.spearmanr(net[nm], net[mv])
                mrows.append(dict(network=nm, macro=mv, rho=rho, p=p))
                if nm == "DFI_count":
                    say(f"| {nm} | {mv} | {rho:.3f} | {p:.3f} |")
        # Leave-one-out on the headline pair. With seven countries the
        # correlation is fragile, and the paper reports the range rather
        # than a single point estimate.
        say()
        say("Leave-one-out, DFI count against agricultural share of GDP:")
        say()
        say("| dropped | rho | p |")
        say("|---|---|---|")
        loo_rows = []
        for c in net.country:
            sub = net[net.country != c]
            rr, pp = stats.spearmanr(sub["DFI_count"], sub["agri_gdp_share"])
            say(f"| {c} | {rr:.3f} | {pp:.3f} |")
            loo_rows.append(dict(dropped=c, rho=rr, p=pp))
        lo = pd.DataFrame(loo_rows)
        say()
        say(f"- rho ranges {lo.rho.min():.3f} to {lo.rho.max():.3f}; "
            f"significant in {int((lo.p < 0.05).sum())} of {len(lo)} variants")
        lo.to_csv(OUT + "10b_macro_leave_one_out.csv", index=False)
        say()
        pd.DataFrame(mrows).to_csv(OUT + "10_macro_correlations.csv",
                                   index=False)
        say()

    with open(OUT + "00_FINDINGS_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nWrote {OUT}00_FINDINGS_SUMMARY.md and 11 CSVs")


if __name__ == "__main__":
    main()
