"""Trim the abstract back inside the 250-word limit (target 228-236)."""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, '..', 'paper', 'main.tex')

EDITS = [
    # the detector sentence: drop the trailing relative clause
    ("reaches AUC \\eTwoCleanAuc{} against endpoints that serve only their own\n"
     "traffic, and falls to chance",
     "separates clean distributors at AUC \\eTwoCleanAuc{}, then falls to chance"),
    ("making the ratio itself look ordinary costs",
     "making the ratio look ordinary costs"),
    # drop the Cramer's V figure, keep the claim
    ("declared direction separates access from content\n"
     "networks at Cram\\'er's $V=\\eFourCramer$.",
     "declared direction separates access from content\n"
     "networks unaided."),
    # the final sentence: two clauses are enough
    ("leaves \\eFiveCliFreePct{}\\% of subscribers untouched, and keeps\n"
     "that volume in service.",
     "leaves \\eFiveCliFreePct{}\\% of subscribers untouched, and keeps\n"
     "that traffic in service."),
    ("It needs two counters per subscriber, costs \\eSevenExact{}M\n"
     "records/s per core, and is already the declared quantity of",
     "It needs two counters per subscriber, \\eSevenExact{}M records/s per\n"
     "core, and is already the declared quantity of"),
]

t = io.open(PATH, encoding='utf-8').read()
for old, new in EDITS:
    n = t.count(old)
    if n != 1:
        print('MISS (%d): %r' % (n, old[:60]))
        sys.exit(1)
    t = t.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='\n').write(t)

a = t.split('\\begin{abstract}')[1].split('\\end{abstract}')[0]
a = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})?', ' X ', a)
a = re.sub(r'[^A-Za-z0-9.%-]+', ' ', a)
print('abstract words now:', len([w for w in a.split() if any(c.isalnum() for c in w)]))
