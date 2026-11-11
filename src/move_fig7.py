"""Move the Fig. 7 float declaration earlier in Section V-G so LaTeX can place
it at the top of a page instead of breaking the column short."""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, '..', 'paper', 'sec_metering.tex')

t = io.open(PATH, encoding='utf-8').read()

m = re.search(r'\\begin\{figure\*\}\[!t\]\n\\centering\n'
              r'\\includegraphics\[width=\\textwidth\]\{fig10_closures\.pdf\}'  # noqa
              r'.*?\\end\{figure\*\}\n', t, re.S)
if not m:
    print('float block not found')
    sys.exit(1)
block = m.group(0)
rest = t[:m.start()] + t[m.end():]

anchor = '\\begin{definition}[SIEVE]'
i = rest.find(anchor)
if i < 0:
    print('anchor not found')
    sys.exit(1)
out = rest[:i] + block + '\n' + rest[i:]

# the paragraph that introduced the float must still end cleanly
io.open(PATH, 'w', encoding='utf-8', newline='\n').write(out)
print('moved %d chars earlier; file now %d chars' % (len(block), len(out)))
