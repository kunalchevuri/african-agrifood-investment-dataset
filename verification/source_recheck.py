# -*- coding: utf-8 -*-
"""Re-check each sampled row against the source it cites.

What this is: for every row in the drawn sample, fetch the recorded
source_url and test whether the page still states the company, the investor,
the year and the amount the dataset records.

What this is NOT: the independent random audit the paper says is missing.
That requires a person who did not enter the row to find the source and read
it. This script only re-reads the source the row already names, so it cannot
catch a row pointed at the wrong article, and it cannot judge a segment.
Reporting it as the audit would claim an independence it does not have.

Reading the result. "Confirmed" means the page contains the value. "Not
confirmed" means this script did not find it, which is weaker than wrong:
the value may sit in an image, a table this crude text extraction drops, or
behind a consent wall. Every not-confirmed row is listed so a person can
look. Rates are reported per stream and never pooled, because the sample
deliberately oversamples the LLM stream.

Usage:
    python verification/source_recheck.py            (fetches; needs network)
    python verification/source_recheck.py --offline  (re-reads the cache)
"""
import os
import re
import sys
import time
import json
import urllib.parse
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import entity_resolution as er  # noqa: E402

SAMPLE = os.path.join(ROOT, "data", "validation_logs",
                      "stage3_validation_sample_v2.csv")
CACHE = os.path.join(ROOT, "data", "validation_logs", "source_recheck_cache")
OUT = os.path.join(ROOT, "verified_findings", "35_source_recheck.csv")
SUMMARY = os.path.join(ROOT, "verified_findings", "36_source_recheck_rates.csv")

UA = "Mozilla/5.0 (compatible; agrifood-dataset-citation-check/1.0)"
DEEP = re.compile(r"https?://[^/]+/.+")

# Paths that are a listing or a search form, not the document a row cites.
# These matter more than they look: every llm_extracted row in the dataset
# points at agfunder.com/research/, which is the index AgFunder publishes
# its reports from, not a report. A first run treated it as a document and
# reported that 0 percent of LLM rows were confirmed, which is a fact about
# the URL and not about the rows. Naming them explicitly, rather than
# guessing from the shape of the path, keeps a long article slug such as
# globalaginvesting.com/findev-canada-commits-... on the document side.
INDEX_PATHS = {"research", "search", "our-portfolio", "project-list",
               "worldmap", "en/our-impact/search-our-portfolio", "portfolio",
               "projects", "news"}


def is_document(url):
    """False when the URL names a publication or a listing, not a document."""
    if not isinstance(url, str) or not DEEP.match(url):
        return False
    path = urllib.parse.urlparse(url).path.strip("/").lower()
    return path not in INDEX_PATHS


def aliases(canonical, table):
    """Every spelling that resolves to this canonical name, plus itself."""
    out = {canonical}
    for variant, target in table.items():
        if target == canonical:
            out.add(variant)
    return out


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())


def tokens_present(name, text, table):
    """True if any alias of `name` appears in `text`.

    Falls back to the distinctive leading words of the name, because an
    article writes "Aerobotics" where the dataset says "Aerobotics (Pty)
    Ltd". Stop-words are dropped so "Ltd" alone can never match.
    """
    STOP = {"ltd", "limited", "plc", "inc", "llc", "pty", "the", "group",
            "holdings", "company", "co", "sa", "nv", "bv", "gmbh", "sas",
            "international", "investment", "investments", "capital",
            "ventures", "venture", "partners", "fund", "funds"}
    t = norm(text)
    for a in aliases(name, table):
        if norm(a) and norm(a) in t:
            return True
    words = [w for w in norm(name).split() if w not in STOP and len(w) > 2]
    if not words:
        return False
    # the first distinctive word is usually the brand
    return words[0] in t


def amount_present(usd, text):
    """Look for the amount written the several ways a report writes it."""
    if pd.isna(usd):
        return None
    v = float(usd)
    t = norm(text).replace(",", "")
    cands = {f"{int(v)}"}
    for unit, div in (("million", 1e6), ("m", 1e6), ("billion", 1e9)):
        q = v / div
        if q >= 0.1:
            for q_s in ({f"{q:.0f}", f"{q:.1f}", f"{q:.2f}"}
                        if q != int(q) else {f"{int(q)}"}):
                q_s = q_s.rstrip("0").rstrip(".") if "." in q_s else q_s
                cands.add(f"{q_s} {unit}")
                cands.add(f"{q_s}{unit}")
    return any(c in t for c in cands)


def fetch(url, path):
    if os.path.exists(path):
        return open(path, encoding="utf-8", errors="replace").read(), "cache"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as f:
        body = f.read(600000).decode("utf-8", "replace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(body)
    return body, "net"


def main():
    offline = "--offline" in sys.argv
    s = pd.read_csv(SAMPLE)
    os.makedirs(CACHE, exist_ok=True)
    recs = []

    for i, r in s.iterrows():
        url = r["source_url"]
        rec = {"deal_id": r["deal_id"], "company_name": r["company_name"],
               "investor_name": r["investor_name"],
               "stream": r["extraction_method"],
               "year": str(pd.to_datetime(r["investment_date"]).year),
               "source_url": url, "status": "", "company": "", "investor": "",
               "year_on_page": "", "amount": ""}

        if not is_document(url):
            rec["status"] = "url names a publication, not a document"
            recs.append(rec)
            continue

        key = re.sub(r"[^A-Za-z0-9]+", "_", url)[:120] + ".html"
        path = os.path.join(CACHE, key)
        if offline and not os.path.exists(path):
            rec["status"] = "not cached"
            recs.append(rec)
            continue
        try:
            body, how = fetch(url, path)
            if how == "net":
                time.sleep(1.0)
        except Exception as e:
            rec["status"] = f"unreachable: {type(e).__name__}"
            recs.append(rec)
            continue

        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body,
                      flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        rec["status"] = "fetched"
        rec["company"] = tokens_present(r["company_name"], text,
                                        er.CANONICAL_COMPANY_NAMES)
        rec["investor"] = tokens_present(r["investor_name"], text,
                                         er.CANONICAL_INVESTOR_NAMES)
        rec["year_on_page"] = rec["year"] in text
        rec["amount"] = amount_present(r["funding_amount_usd"], text)
        recs.append(rec)
        print(f"  [{i + 1:3d}/{len(s)}] {rec['status'][:22]:22s} "
              f"c={rec['company']!s:5s} i={rec['investor']!s:5s} "
              f"y={rec['year_on_page']!s:5s} a={rec['amount']!s:5s} "
              f"{urllib.parse.urlparse(url).netloc[:28]}")

    d = pd.DataFrame(recs)
    d.to_csv(OUT, index=False)

    # ---- rates, per stream, never pooled ----
    out = []
    for stream, sub in d.groupby("stream"):
        got = sub[sub.status == "fetched"]
        row = {"stream": stream, "sampled": len(sub),
               "fetched": len(got),
               "url_not_a_document": int((sub.status.str.startswith("url names")).sum()),
               "unreachable": int((sub.status.str.startswith("unreachable")).sum())}
        # every sampled row lands in exactly one bucket, or the table lies
        row["other"] = (len(sub) - row["fetched"] - row["url_not_a_document"]
                        - row["unreachable"])
        assert row["other"] >= 0, row
        for f in ("company", "investor", "year_on_page", "amount"):
            vals = got[f].replace("", pd.NA).dropna()
            vals = vals[vals.astype(str) != "None"]
            n = len(vals)
            k = int(vals.astype(str).eq("True").sum())
            row[f"{f}_checked"] = n
            row[f"{f}_confirmed"] = k
            row[f"{f}_confirmed_pct"] = round(100 * k / n, 1) if n else None
        out.append(row)
    rates = pd.DataFrame(out)
    rates.to_csv(SUMMARY, index=False)

    print("\n" + "=" * 72)
    print(rates.to_string(index=False))
    print("=" * 72)
    nc = d[(d.status == "fetched") &
           ((d.company.astype(str) == "False") |
            (d.investor.astype(str) == "False"))]
    print(f"\nrows where the page did not confirm the company or the investor: "
          f"{len(nc)}")
    for _, r in nc.iterrows():
        miss = [f for f in ("company", "investor")
                if str(r[f]) == "False"]
        print(f"  {r.company_name[:26]:26s} / {r.investor_name[:24]:24s} "
              f"[{r.stream[:6]}]  not found: {', '.join(miss)}")
    print("\nNot found is not the same as wrong. Each line above needs a "
          "person\nto open the page before it counts as an error.")
    print(f"\nrow-level results -> {OUT}")
    print(f"rates             -> {SUMMARY}")


if __name__ == "__main__":
    main()
