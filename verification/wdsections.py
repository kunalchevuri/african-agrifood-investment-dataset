# -*- coding: utf-8 -*-
"""Per-section WD-countable word budget, so trimming targets the right place."""
import os
import re

MAIN = "world_development_submission/main.tex"
INC = re.compile(r"\\(draft|tbl)\{([^}]+)\}")
STRIP_ENV = re.compile(
    r"(?s)\\begin\{(table\*?|figure\*?|tabular|landscape|subfigure|equation|abstract)\}"
    r".*?\\end\{\1\}")
COMMENT = re.compile(r"(?m)^\s*%.*$")
FOOTNOTE = re.compile(r"(?s)\\footnote\{.*?\}")
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


def count(t):
    t = COMMENT.sub(" ", t)
    t = STRIP_ENV.sub(" ", t)
    t = FOOTNOTE.sub(" ", t)
    t = CMD.sub(" ", t)
    t = JUNK.sub(" ", t)
    return len(re.findall(r"[A-Za-z][A-Za-z'\-]*", t))


full = resolve(MAIN)
full = re.sub(r"(?s)\\bibliography\{.*", " ", full)
full = re.sub(r"(?s)^.*?(\\section\{Introduction\})", r"\1", full, count=1)

parts = re.split(r"(?m)^(\\section\*?\{[^}]*\})", full)
rows = []
for i in range(1, len(parts), 2):
    name = re.sub(r"\\section\*?\{|\}", "", parts[i])
    rows.append((name, count(parts[i + 1])))

tot = sum(n for _, n in rows)
print(f"{'section':44s} {'words':>6s}  {'share':>6s}")
print("-" * 60)
for name, n in rows:
    print(f"{name[:44]:44s} {n:6,d}  {100*n/tot:5.1f}%")
print("-" * 60)
print(f"{'TOTAL (WD-countable body)':44s} {tot:6,d}")
print(f"{'ceiling':44s} {10000:6,d}")
print(f"{'headroom':44s} {10000-tot:6,d}")
