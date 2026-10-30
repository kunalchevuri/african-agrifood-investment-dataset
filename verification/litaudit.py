# -*- coding: utf-8 -*-
"""Where is the paper thin on literature, and how much room is there to fix it?

Per section: WD-countable words, distinct citations, and citation density.
Density is the diagnostic -- a Results section legitimately cites less than a
Background, but a claim-heavy passage with no citation is where a World
Development referee pushes back.
"""
import os
import re

MAIN = "world_development_submission/main.tex"
INC = re.compile(r"\\(draft|tbl)\{([^}]+)\}")
STRIP_ENV = re.compile(
    r"(?s)\\begin\{(table\*?|figure\*?|tabular|landscape|subfigure|equation|abstract)\}"
    r".*?\\end\{\1\}")
COMMENT = re.compile(r"(?m)^\s*%.*$")
FOOTNOTE = re.compile(r"(?s)\\footnote\{.*?\}")
CITE = re.compile(r"\\cite[a-zA-Z]*\{([^}]+)\}")
CMD = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?")
JUNK = re.compile(r"[{}$&\\~^_#]")


def resolve(path, seen=None):
    seen = seen or set()
    if path in seen:
        return ""
    seen.add(path)
    txt = open(path, encoding="utf-8").read()

    def sub(m):
        kind, name = m.group(1), m.group(2)
        p = ("writing/tables/" if kind == "tbl" else "writing/") + name
        if not p.endswith(".tex"):
            p += ".tex"
        return "\n" + resolve(p, seen) + "\n" if os.path.exists(p) else ""
    return INC.sub(sub, txt)


def words(t):
    t = COMMENT.sub(" ", t)
    t = STRIP_ENV.sub(" ", t)
    t = FOOTNOTE.sub(" ", t)
    t = CMD.sub(" ", t)
    t = JUNK.sub(" ", t)
    return len(re.findall(r"[A-Za-z][A-Za-z'\-]*", t))


def cites(t):
    out = set()
    for m in CITE.findall(t):
        out |= {x.strip() for x in m.split(",")}
    return out


full = resolve(MAIN)
full = re.sub(r"(?s)\\bibliography\{.*", " ", full)
full = re.sub(r"(?s)^.*?(\\section\{Introduction\})", r"\1", full, count=1)

# split on section AND subsection so thin passages are visible
parts = re.split(r"(?m)^(\\(?:sub)?section\*?\{[^}]*\})", full)
rows = []
sec = "(front)"
for i in range(1, len(parts), 2):
    head = parts[i]
    name = re.sub(r"\\(?:sub)?section\*?\{|\}", "", head)
    is_sub = head.startswith("\\subsection")
    if not is_sub:
        sec = name
    body = parts[i + 1]
    w, c = words(body), cites(body)
    rows.append((("  " if is_sub else "") + name, w, len(c), sec))

print(f"{'section':52s} {'words':>6s} {'cites':>6s} {'per 1k':>7s}")
print("-" * 76)
allc = set()
for name, w, nc, sec in rows:
    dens = 1000 * nc / w if w else 0
    flag = ""
    if w >= 250 and dens < 2.0:
        flag = "  <-- THIN"
    print(f"{name[:52]:52s} {w:6,d} {nc:6d} {dens:7.1f}{flag}")
print("-" * 76)
tot_w = sum(r[1] for r in rows)
for name, w, nc, sec in rows:
    pass
allc = cites(full)
print(f"{'TOTAL':52s} {tot_w:6,d} {len(allc):6d} {1000*len(allc)/tot_w:7.1f}")
print(f"\n  ceiling 10,000 -> headroom {10000-tot_w:,} words")
print(f"  distinct references cited: {len(allc)}")
