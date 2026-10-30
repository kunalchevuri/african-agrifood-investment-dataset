"""Figures for the companion dataset paper. Reads only the outputs of
dataset_stats.py so every plotted value is one the tracer can find."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VF = os.path.join(ROOT, "verified_findings")
OUT = os.path.join(ROOT, "ieee_bigdata_hss")   # the paper folder, when present
if not os.path.isdir(OUT):
    OUT = os.path.join(ROOT, "verified_findings")
plt.rcParams.update({"font.family": "serif", "font.size": 8,
                     "pdf.fonttype": 42,   # embed as TrueType, not Type 3 (IEEE PDF eXpress)
                     "axes.spines.top": False, "axes.spines.right": False})

kv = pd.read_csv(os.path.join(VF, "30_dataset_paper.csv")).set_index("key")["value"]
by = pd.read_csv(os.path.join(VF, "31_dataset_by_stream.csv")).set_index("stream")
yr = pd.read_csv(os.path.join(VF, "32_dataset_deals_by_year_stream.csv")).set_index("year")

# ---- Figure 1: rows remaining after each build step ----
steps = [
    ("Inputs merged", kv["raw_rows_merged"]),
    ("Known-bad pairs out", kv["rows_after_known_bad"]),
    ("Non-investors out", kv["rows_after_non_investor"]),
    ("Out-of-scope companies out", kv["rows_after_out_of_scope"]),
    ("Pre-2015 rows out", kv["rows_after_window"]),
    ("Exact duplicates out", kv["rows_after_exact_dedup"]),
    ("Same investor, same deal out", kv["rows"]),
]
fig, ax = plt.subplots(figsize=(3.5, 1.8))
labels = [s for s, _ in steps][::-1]
vals = [int(v) for _, v in steps][::-1]
ax.barh(labels, vals, color="#4a6b8a", height=0.7)
for i, v in enumerate(vals):
    ax.text(v - 20, i, f"{v:,}", va="center", ha="right", fontsize=7, color="white")
ax.set_xlim(0, max(vals) * 1.02)
ax.set_xlabel("rows")
ax.tick_params(axis="y", length=0)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_pipeline.pdf"))

# ---- Figure 2: deals by year, stacked by stream ----
fig, ax = plt.subplots(figsize=(3.5, 1.7))
cols = [("portal", "#4a6b8a", "Portal"), ("llm", "#c8873a", "LLM"),
        ("manual", "#8aa07a", "Manual")]
bottom = pd.Series(0, index=yr.index)
for c, colour, lab in cols:
    ax.bar(yr.index, yr[c], bottom=bottom, color=colour, label=lab, width=0.7)
    bottom = bottom + yr[c]
ax.set_ylabel("deals")
ax.set_xticks(yr.index)
ax.set_xticklabels([str(y)[2:] for y in yr.index])
ax.set_xlabel("year (20xx)")
ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_years.pdf"))

# ---- Figure 3: what a deal looks like, by stream ----
metrics = [("deals_two_plus_pct", "Names 2+\ninvestors"),
           ("deals_with_amount_pct", "Has an\namount"),
           ("deals_with_dfi_pct", "Includes\na DFI"),
           ("flag1_pct", "Verified at\nsource (rows)")]
fig, ax = plt.subplots(figsize=(3.5, 1.9))
x = range(len(metrics))
w = 0.26
for j, (c, colour, lab) in enumerate(cols):
    ax.bar([i + (j - 1) * w for i in x], [by.loc[c, m] for m, _ in metrics],
           width=w, color=colour, label=lab)
ax.set_xticks(list(x))
ax.set_xticklabels([l for _, l in metrics], fontsize=7)
ax.set_ylabel("percent of deals")
ax.set_ylim(0, 125)
ax.set_yticks([0, 25, 50, 75, 100])
ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper center")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_streams.pdf"))
print("figures written")
