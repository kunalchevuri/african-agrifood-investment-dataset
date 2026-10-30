# -*- coding: utf-8 -*-
"""World Development counts body text EXCLUSIVE of abstract, title page,
references, endnotes, figures and tables. Regular Paper: 4,500 min,
~10,000 max. This resolves \draft{} / \tbl{} includes the way the assembled
document does, then strips everything the journal excludes."""
import os
import re

ROOT = "."
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
        sub_path = ("writing/tables/" if kind == "tbl" else "writing/") + name
        if not sub_path.endswith(".tex"):
            sub_path += ".tex"
        if os.path.exists(sub_path):
            return "\n" + resolve(sub_path, seen) + "\n"
        return ""
    return INC.sub(sub, txt)


full = resolve(MAIN)

# what World Development excludes
body = COMMENT.sub(" ", full)
body = STRIP_ENV.sub(" ", body)          # tables, figures, abstract
body = FOOTNOTE.sub(" ", body)           # endnotes
body = re.sub(r"(?s)\\bibliography\{.*", " ", body)   # references
body = re.sub(r"(?s)^.*?\\section\{Introduction\}", " ", body, count=1)  # title page
body = CMD.sub(" ", body)
body = JUNK.sub(" ", body)

words = re.findall(r"[A-Za-z][A-Za-z'\-]*", body)
n = len(words)

print(f"  body words (WD-countable): {n:,}")
print(f"  Regular Paper window     : 4,500 min / ~10,000 max")
if n < 4500:
    print(f"  -> UNDER by {4500-n:,}")
elif n > 10000:
    print(f"  -> OVER by {n-10000:,}")
else:
    print(f"  -> WITHIN RANGE ({10000-n:,} words of headroom)")

# abstract separately
ab = re.search(r"(?s)\\begin\{abstract\}(.*?)\\end\{abstract\}", full)
if ab:
    a = CMD.sub(" ", COMMENT.sub(" ", ab.group(1)))
    a = JUNK.sub(" ", a)
    aw = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", a))
    print(f"\n  abstract: {aw} words (limit 250) -> "
          f"{'OK' if aw <= 250 else 'OVER'}")
