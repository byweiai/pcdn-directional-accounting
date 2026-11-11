"""Land the abstract at 233 words (line wrapping as in the source)."""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, '..', 'paper', 'main.tex')

EDITS = [
    ("stays above the subscriber tail\nof every window.",
     "stays above the subscriber tail."),
    ("are fixed by the\nservice it sells.", "are fixed by what it\nsells."),
]

t = io.open(PATH, encoding='utf-8').read()
for old, new in EDITS:
    n = t.count(old)
    if n != 1:
        print('MISS (%d): %r' % (n, old[:70]))
        sys.exit(1)
    t = t.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='\n').write(t)

a = t.split('\\begin{abstract}')[1].split('\\end{abstract}')[0]
a = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})?', ' X ', a)
a = re.sub(r'[^A-Za-z0-9.%-]+', ' ', a)
print('abstract words now:', len([w for w in a.split() if any(c.isalnum() for c in w)]))
