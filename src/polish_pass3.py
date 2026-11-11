"""Third polish pass: page-1 fixes (title break, percent form in the abstract,
word order) plus percent macros for the mixing band."""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(HERE, '..', 'paper')

EDITS = [
    ('main.tex',
     '\\title{Upload May Not Exceed Download: Directional Accounting for '
     'Peer-Assisted Delivery in Operator Networks}',
     '\\title{Upload May Not Exceed Download:\\\\(0.6em)\n'
     'Directional Accounting for Peer-Assisted Delivery\\\\\n'
     'in Operator Networks}'),
    ('main.tex',
     'traffic, and falls to chance while the endpoint still sends \\eTwoLo--\\eTwoHi{} of its\n'
     'bytes as distribution;',
     'traffic, and falls to chance while the endpoint still sends \\eTwoLoPct--\\eTwoHiPct\\% of\n'
     'its bytes as distribution;'),
    ('main.tex',
     'endpoint keeps only \\eTwoLo--\\eTwoHi{} of its distribution traffic, serves the',
     'endpoint keeps only \\eTwoLoPct--\\eTwoHiPct\\% of its distribution traffic, serves the'),
    ('main.tex',
     'It is therefore invariant under the\n'
     'entire evasion set above, computable at any observation point without\n'
     'knowledge of network boundaries, and cheap: two counters per subscriber.',
     'It is therefore invariant under every evasion\n'
     'available to the endpoint, computable at any observation point without\n'
     'knowledge of network boundaries, and cheap: two counters per\n'
     'subscriber.'),
]


def main():
    texts, bad = {}, []
    for fn in {e[0] for e in EDITS}:
        texts[fn] = io.open(os.path.join(PAPER, fn), encoding='utf-8').read()
    for fn, old, new in EDITS:
        c = texts[fn].count(old)
        if c != 1:
            bad.append((fn, old[:70], c))
            continue
        texts[fn] = texts[fn].replace(old, new)
    if bad:
        for fn, old, c in bad:
            print('MISS %-14s x%d  %r' % (fn, c, old))
        sys.exit(1)
    for fn, t in texts.items():
        io.open(os.path.join(PAPER, fn), 'w', encoding='utf-8', newline='\n').write(t)
    print('%d edits applied' % len(EDITS))


if __name__ == '__main__':
    main()
