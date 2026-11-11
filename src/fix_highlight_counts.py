"""Recompute the bracketed character count on each highlight.

The bracket is a check a submitting author reads before pasting, so it has to be
the number the portal will compute: the text alone, without the "1. " prefix and
without the bracket itself.  CMS caps highlights at 85 characters including
spaces.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(os.path.dirname(HERE), 'paper', 'submission', 'highlights.txt')
CAP = 85

lines = io.open(P, encoding='utf-8').read().split('\n')
out = []
for ln in lines:
    m = re.match(r'^(\d\.\s)(.*?)\s*\[\d+\]\s*$', ln)
    if not m:
        out.append(ln)
        continue
    body = m.group(2).rstrip()
    n = len(body)
    if n > CAP:
        raise SystemExit('highlight over %d chars: %d  %s' % (CAP, n, body))
    out.append('%s%s   [%d]' % (m.group(1), body, n))
io.open(P, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
for ln in out:
    if ln.strip():
        print(len(ln), ln)
