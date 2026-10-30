"""
figures.py

Regenerates the paper's figures from phase1_combined.csv.

    python pipeline/master_pipeline.py
    python pipeline/analysis.py
    python pipeline/figures.py

Figure 1 (network_main.png) is the largest connected component, drawn
twice on one shared layout:

  panel (a)  node colour by investor type, the ten highest-betweenness
             investors labelled
  panel (b)  the same nodes coloured by Louvain community

Panel (b) exists because H2 is a claim about community membership, and
panel (a) cannot show it: every DFI is red there, so the figure implies
DFIs cluster together when the finding is that IFC does not. Node size is
unweighted betweenness (the paper's primary specification) in both.
"""

import os
import numpy as np
import pandas as pd
import networkx as nx
import networkx.algorithms.community as nx_comm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from adjustText import adjust_text

SRC = "data/raw_sources/phase1_combined.csv"
OUT = "world_development_submission/figures/"
LAYOUT_SEED = 42
# must match LOUVAIN_SEED in analysis.py, or panel (b) would show
# a different partition from Table 6
LOUVAIN_SEED = 4
COMM_BILATERAL = "#c0392b"
COMM_IFC = "#1f6f8b"
COMM_OTHER = "#c9ccc9"
N_LABELS = 10

TYPE_COLOR = {
    "DFI": "#e31a1c",
    "impact_fund": "#33a02c",
    "pe_vc": "#1f78b4",
    "corporate": "#ff9900",
    "commercial_bank": "#a55fc4",
    "blended_vehicle": "#8c564b",
    "unknown": "#7f7f7f",
}
TYPE_LABEL = {
    "DFI": "DFI",
    "impact_fund": "Impact fund",
    "pe_vc": "Private equity / venture capital",
    "corporate": "Corporate",
    "commercial_bank": "Commercial bank",
    "blended_vehicle": "Blended vehicle",
    "unknown": "Unknown",
}


def build_graph(df):
    n = df.groupby("deal_id")["investor_name"].nunique()
    multi = df[df.deal_id.isin(n[n >= 2].index)]
    G = nx.Graph()
    types = df.drop_duplicates("investor_name").set_index(
        "investor_name")["investor_type"].to_dict()
    for inv, t in types.items():
        G.add_node(inv, investor_type=t)
    for _, grp in multi.groupby("deal_id"):
        inv = grp["investor_name"].unique().tolist()
        for i in range(len(inv)):
            for j in range(i + 1, len(inv)):
                a, b = inv[i], inv[j]
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)
    return G


GEO = "data/raw_sources/geo/ne_110m_admin_0_countries.zip"
# Map canvas. Africa is about as tall as it is wide, so the panel is close
# to square with a strip on the right for the colourbar. Two of these stack
# on one portrait page at roughly four inches of continent each, against
# the two and a half inches they had side by side.
MAP_W, MAP_H = 9.8, 7.7
NON_COUNTRY_MAP = {"Democratic Republic of Congo":
                   "Democratic Republic of the Congo"}
NOT_A_COUNTRY = {"Multinational", "Global", "Unknown"}
LABEL_NAVY = "#16305c"


def draw_map(df, value, cbar_label, fname, cmap, fmt):
    """Choropleth of African countries by `value`.

    Holds the map and its colourbar only. The title and the excluded-deals
    note now live in the LaTeX caption: they duplicated each other across
    the two panels and cost the continent about a fifth of its height.
    """
    import geopandas as gpd

    n = df.groupby("deal_id")["investor_name"].nunique()
    multi = df[df.deal_id.isin(n[n >= 2].index)]
    u = multi.drop_duplicates("deal_id").copy()
    u["amount"] = u.deal_id.map(
        multi.groupby("deal_id")["funding_amount_usd"].max())
    u = u[~u.country.isin(NOT_A_COUNTRY)]
    u = u[~u.country.astype(str).str.contains("Region")]
    agg = (u.groupby("country")
             .agg(deals=("deal_id", "count"), volume=("amount", "sum"))
             .reset_index())
    agg["geo_name"] = agg.country.replace(NON_COUNTRY_MAP)

    world = gpd.read_file(GEO)
    africa = world[world.CONTINENT == "Africa"].copy()
    africa["val"] = africa.NAME.map(
        dict(zip(agg.geo_name, agg[value]))).astype(float)
    # Natural Earth spells a few names differently from NAME
    fallback = dict(zip(agg.geo_name, agg[value]))
    africa["val"] = africa["val"].fillna(
        africa.ADMIN.map(fallback)).astype(float)

    # Explicit axes rectangles rather than a tight crop, so the deals map
    # and the volume map come out byte-for-byte the same shape and line up
    # when stacked. A tight crop would size each to its own tick labels.
    fig = plt.figure(figsize=(MAP_W, MAP_H), dpi=150)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.005, 0.005, 0.755, 0.99])
    # The right margin has to hold the widest tick label ("$1,750M" at 17pt,
    # about 0.9in) plus the rotated axis title. At the previous 0.095 of a
    # 9in canvas it held neither and the labels were being cut off mid-glyph.
    cax = fig.add_axes([0.775, 0.16, 0.024, 0.68])
    africa.plot(ax=ax, color="#ececec", edgecolor="#cfcfcf", linewidth=0.7)
    have = africa[africa.val.notna()]
    have.plot(ax=ax, column="val", cmap=cmap, edgecolor="white",
              linewidth=0.8, legend=True, cax=cax,
              legend_kwds={"label": cbar_label})

    texts = []
    for r in have.itertuples():
        c = r.geometry.representative_point()
        texts.append(ax.text(
            c.x, c.y, r.NAME, fontsize=18, fontweight="bold",
            color=LABEL_NAVY, ha="center", va="center", zorder=6,
            bbox=dict(boxstyle="round,pad=0.20", facecolor="white",
                      edgecolor="none", alpha=0.85)))
    anchors = [(r.geometry.representative_point().x,
                r.geometry.representative_point().y)
               for r in have.itertuples()]
    adjust_text(texts, ax=ax, expand=(1.15, 1.3), force_text=(0.35, 0.45),
                force_static=(0.1, 0.12), time_lim=12)
    for (ax0, ay0), t in zip(anchors, texts):
        tx, ty = t.get_position()
        if (tx - ax0) ** 2 + (ty - ay0) ** 2 > 1.6 ** 2:
            ax.annotate("", xy=(ax0, ay0), xytext=(tx, ty), zorder=5,
                        arrowprops=dict(arrowstyle="-", color=LABEL_NAVY,
                                        linewidth=1.3, shrinkA=1, shrinkB=1))

    # colourbar ticks in readable units rather than a 1e9 offset
    cax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    cax.tick_params(labelsize=17)
    cax.yaxis.label.set_size(19)

    ax.set_axis_off()
    ax.set_aspect("equal")
    path = os.path.join(OUT, fname)
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"wrote {path}  ({len(have)} countries shaded, "
          f"{fmt(have.val.max())} max)")


def excluded_deals(df):
    """Deals the maps cannot place, for the figure caption."""
    n = df.groupby("deal_id")["investor_name"].nunique()
    multi = df[df.deal_id.isin(n[n >= 2].index)]
    excl = multi.drop_duplicates("deal_id")
    excl = excl[excl.country.isin(NOT_A_COUNTRY)]
    ev = multi[multi.deal_id.isin(excl.deal_id)].groupby(
        "deal_id")["funding_amount_usd"].max().sum()
    return len(excl), ev


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(SRC, encoding="utf-8")
    G = build_graph(df)
    Gc = G.subgraph(max(nx.connected_components(G), key=len)).copy()

    # Unweighted betweenness: the primary specification, the one every
    # inferential test in the paper uses, and therefore the one Table 2 is
    # ranked by.
    bt = nx.betweenness_centrality(Gc, normalized=True)

    # One layout, drawn twice. Re-running spring_layout per panel would move
    # the nodes and destroy the comparison the second panel exists to make.
    pos = nx.spring_layout(Gc, weight="weight", seed=LAYOUT_SEED,
                           k=0.85, iterations=600)

    comms = nx_comm.louvain_communities(Gc, weight="weight",
                                        seed=LOUVAIN_SEED)
    # Identify the two communities of interest by who is in them, not by
    # list position, which Louvain does not guarantee across versions.
    def home(name):
        return next((i for i, c in enumerate(comms) if name in c), None)

    c_bilateral = home("FMO")
    c_ifc = home("International Finance Corporation")

    bmax = max(bt.values()) or 1.0
    nodes = list(Gc.nodes())
    # Floor raised so the smallest nodes survive the reduction to page size.
    sizes = [110 + 2600 * np.sqrt(bt[n] / bmax) for n in nodes]

    # name tiebreak so equal betweenness cannot reorder labels between runs
    top = sorted(bt, key=lambda n: (-bt[n], n))[:N_LABELS]
    top_dfi = [n for n in top if Gc.nodes[n].get("investor_type") == "DFI"]

    # Aspect matched to the landscape text block (about 9.7 by 6.0
    # inches once the caption is allowed for) so the image fills the page
    # instead of stopping a third of the way up it.
    fig, axes = plt.subplots(1, 2, figsize=(26, 15.2), dpi=200)
    fig.patch.set_facecolor("white")

    def draw_edges(ax):
        nx.draw_networkx_edges(
            Gc, pos, ax=ax, edge_color="#b0b0b0", alpha=0.22,
            width=[0.30 + 0.42 * (Gc[u][v]["weight"] - 1)
                   for u, v in Gc.edges()])

    def label(ax, names, colour_of):
        texts = []
        for n in names:
            x, y = pos[n]
            c = colour_of(n)
            texts.append(ax.text(
                x, y, n, fontsize=23, fontweight="bold", color=c, zorder=6,
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.34", facecolor="white",
                          edgecolor=c, linewidth=2.0, alpha=0.94)))
        # Feeding the 353 node coordinates in as static points was tried
        # and is worse: the repulsion from a dense blob sums to a field
        # that pins every label to the panel border. Repel labels from
        # each other only, and cap how far one may travel from its node so
        # the leader lines stay short enough to follow.
        adjust_text(texts, ax=ax, expand=(1.25, 1.5),
                    force_text=(0.55, 0.65),
                    max_move=220, time_lim=30)
        for n, t in zip(names, texts):
            ax.annotate("", xy=pos[n], xytext=t.get_position(), zorder=4,
                        arrowprops=dict(arrowstyle="-", color=colour_of(n),
                                        linewidth=1.8, shrinkA=2, shrinkB=3,
                                        alpha=0.85))

    # ---------------- panel (a): investor type ------------------------
    ax = axes[0]
    draw_edges(ax)
    type_of = lambda n: TYPE_COLOR.get(Gc.nodes[n].get("investor_type"),
                                       "#7f7f7f")
    nx.draw_networkx_nodes(Gc, pos, ax=ax, nodelist=nodes, node_size=sizes,
                           node_color=[type_of(n) for n in nodes],
                           linewidths=0.6, edgecolors="white",
                           alpha=0.95)
    label(ax, top, type_of)
    ax.set_axis_off()
    ax.margins(0.04)
    ax.set_title("(a) by investor type", fontsize=31, pad=20)

    present = [t for t in TYPE_COLOR
               if any(Gc.nodes[n].get("investor_type") == t for n in Gc)]
    ax.legend(
        handles=[Line2D([0], [0], marker="o", linestyle="",
                        markerfacecolor=TYPE_COLOR[t], markeredgecolor="none",
                        markersize=22, label=TYPE_LABEL[t])
                 for t in present],
        loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3,
        frameon=False, fontsize=24, columnspacing=2.4,
        labelspacing=0.7, handletextpad=0.8)

    # ---------------- panel (b): Louvain community --------------------
    ax = axes[1]
    draw_edges(ax)

    def comm_of(n):
        i = home(n)
        if i == c_bilateral:
            return COMM_BILATERAL
        if i == c_ifc:
            return COMM_IFC
        return COMM_OTHER

    nx.draw_networkx_nodes(Gc, pos, ax=ax, nodelist=nodes, node_size=sizes,
                           node_color=[comm_of(n) for n in nodes],
                           linewidths=0.6, edgecolors="white",
                           alpha=0.95)
    label(ax, top_dfi, comm_of)
    ax.set_axis_off()
    ax.margins(0.04)
    ax.set_title("(b) by co-investment community", fontsize=31, pad=20)

    n_bil = len(comms[c_bilateral])
    n_ifc = len(comms[c_ifc])
    dfi = {n for n in Gc if Gc.nodes[n].get("investor_type") == "DFI"}
    d_bil = len(comms[c_bilateral] & dfi)
    d_ifc = len(comms[c_ifc] & dfi)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", linestyle="",
                   markerfacecolor=COMM_BILATERAL, markeredgecolor="none",
                   markersize=22,
                   label=f"Bilateral DFI community ({n_bil} members, "
                         f"{d_bil} DFIs)"),
            Line2D([0], [0], marker="o", linestyle="",
                   markerfacecolor=COMM_IFC, markeredgecolor="none",
                   markersize=22,
                   label=f"IFC's community ({n_ifc} members, {d_ifc} DFIs)"),
            Line2D([0], [0], marker="o", linestyle="",
                   markerfacecolor=COMM_OTHER, markeredgecolor="none",
                   markersize=22,
                   label=f"Other communities ({len(comms) - 2})"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=1,
        frameon=False, fontsize=24, labelspacing=0.7, handletextpad=0.8)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.12)
    path = os.path.join(OUT, "network_main.png")
    fig.savefig(path, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)

    print(f"wrote {path}")
    print(f"  largest connected component: {Gc.number_of_nodes()} investors, "
          f"{Gc.number_of_edges()} ties")
    print(f"  communities: {len(comms)}; bilateral bloc = {n_bil} members "
          f"({d_bil} DFIs); IFC's = {n_ifc} members ({d_ifc} DFIs)")
    print(f"  panel (a) labels {len(top)}, panel (b) labels "
          f"{len(top_dfi)} DFIs: {', '.join(top_dfi)}")

    draw_map(df, "deals", "Co-investment deals",
             "map_deal_count_v2.png", "YlOrBr", lambda v: f"{v:,.0f}")
    draw_map(df, "volume", "Disclosed volume (US$)",
             "map_dollar_volume_v2.png", "YlGnBu",
             lambda v: f"${v/1e6:,.0f}M")
    k, ev = excluded_deals(df)
    print(f"  maps exclude {k} deals (${ev/1e6:,.0f}M) tagged "
          f'"Multinational" or "Global" -- state this in the caption')


if __name__ == "__main__":
    main()
