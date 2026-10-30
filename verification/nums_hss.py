# -*- coding: utf-8 -*-
"""Every numeric claim in ieee_bigdata_hss/paper.tex must appear in the
outputs of pipeline/dataset_stats.py (verified_findings/30_*, 31_*, 32_*)
Same rounding rule as nums.py."""
import re
import sys

paper = open("ieee_bigdata_hss/paper.tex", encoding="utf-8").read()
pool = "".join(open(f"verified_findings/{n}", encoding="utf-8").read()
               for n in ("30_dataset_paper.csv", "31_dataset_by_stream.csv",
                         "32_dataset_deals_by_year_stream.csv",
                         "33_example_deal.csv",
                         "34_multiround_candidates.csv",
                         "35_source_recheck.csv",
                         "36_source_recheck_rates.csv"))
POOL = set(re.findall(r"[0-9]+(?:\.[0-9]+)?", pool.replace(",", " ")))


def num(t):
    try:
        return float(t)
    except ValueError:
        return None


def accounted(c):
    if c in POOL:
        return True
    v = num(c)
    if v is None:
        return False
    if "." in c:
        dp = len(c.split(".")[1])
        return any(abs(round(num(p), dp) - v) < 1e-9
                   for p in POOL if num(p) is not None)
    return any(abs(round(num(p)) - v) < 1e-9
               for p in POOL if num(p) is not None)


# body only: no preamble, author block or bibliography commands
body = paper[paper.index("\\begin{abstract}"):paper.index("\\bibliographystyle")]
body = re.sub(r"\\(?:url|cite|ref|label)\{[^}]*\}", "", body)
body = re.sub(r"\\footnote\{.*?\}", "", body, flags=re.S)
body = body.replace(",", "")

# years of the window, flag values, "2+ investors", the 100-row sample
ALLOW = {str(y) for y in range(2015, 2027)} | {"1", "2", "100"}
bad = []
for m in re.finditer(r"(?<![A-Za-z_\\])[0-9]+(?:\.[0-9]+)?", body):
    c = m.group(0)
    if c in ALLOW or accounted(c):
        continue
    ctx = body[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
    bad.append((c, ctx))
for c, ctx in bad:
    print(f"UNACCOUNTED {c}: ...{ctx}...")
print(f"nums_hss: {len(bad)} unaccounted numeric claims")
sys.exit(1 if bad else 0)
