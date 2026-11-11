"""Second abstract trim: land inside 228-236 words."""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, '..', 'paper', 'main.tex')

EDITS = [
    ("operators answer by classifying endpoints and blocking what\n"
     "they find.",
     "operators answer by classifying endpoints and blocking them."),
    ("which CONFLUENCE then traces\n"
     "back through shared destinations.",
     "which CONFLUENCE traces through\n"
     "shared destinations."),
    ("A regime in which an endpoint declares\n"
     "what it is and pays the corresponding uplink rate yields",
     "A regime where an endpoint declares\n"
     "what it is and pays the matching uplink rate yields"),
    ("and is already the declared quantity of interconnection:",
     "and is already declared at interconnection:"),
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
