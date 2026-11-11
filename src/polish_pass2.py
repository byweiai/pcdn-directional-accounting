"""Second polish pass: prose fixes flagged by the anti-defensive and humanizer
checks (residual dashes, a strawman contrast, a self-audit tail, and an abstract
sentence whose range was ambiguous)."""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(HERE, '..', 'paper')

EDITS = [
    ('main.tex',
     'plus the shadow price of capacity (Theorem~\\ref{thm:price})---and the',
     'plus the shadow price of capacity (Theorem~\\ref{thm:price}), and the'),
    ('sec_deploy.tex',
     'enforce---which is what makes', 'enforce, which is what makes'),

    ('main.tex',
     'Two closures make it enforceable: SIEVE slides the interval so\n'
     'rhythm cannot hide volume, and TRIBUTARY prices a split delivery at one\n'
     'recruited household per unit of hidden excess, CONFLUENCE recovering only part\n'
     'of the pool.',
     'Two closures make it enforceable. SIEVE tests the interval rather than the\n'
     'window, so rhythm cannot hide volume, and TRIBUTARY prices a split delivery at\n'
     'one recruited household per unit of hidden excess, which CONFLUENCE then traces\n'
     'back through shared destinations.'),

    ('main.tex',
     'and falls to chance while the endpoint keeps \\eTwoLo--\\eTwoHi{} of its\n'
     'distribution revenue; making the ratio itself look ordinary costs',
     'and falls to chance while the endpoint still sends \\eTwoLo--\\eTwoHi{} of its\n'
     'bytes as distribution; making the ratio itself look ordinary costs'),

    ('main.tex',
     'The endpoint is not\n'
     'confused about what it is doing, and it is not a security incident to be\n'
     'blocked at the edge. It is a customer reselling a resource it bought under a\n'
     'tariff that did not anticipate resale.',
     'The endpoint knows\n'
     'what it is doing: a customer reselling a resource it bought under a tariff\n'
     'that did not anticipate resale, rather than a security incident to be stopped\n'
     'at the edge.'),

    ('sec_discussion.tex',
     'is a question for contract data, which we do not\nhave.',
     'is a question for contract data, which these corpora cannot\nanswer.'),
]


def main():
    texts, bad = {}, []
    for fn in {e[0] for e in EDITS}:
        texts[fn] = io.open(os.path.join(PAPER, fn), encoding='utf-8').read()
    for fn, old, new in EDITS:
        c = texts[fn].count(old)
        if c != 1:
            bad.append((fn, old[:60], c))
            continue
        texts[fn] = texts[fn].replace(old, new)
    if bad:
        for fn, old, c in bad:
            print('MISS %-18s x%d  %r' % (fn, c, old))
        sys.exit(1)
    for fn, t in texts.items():
        io.open(os.path.join(PAPER, fn), 'w', encoding='utf-8', newline='\n').write(t)
    dashes = sum(t.count('---') for t in texts.values())
    print('%d edits applied; %d dashes remain' % (len(EDITS), dashes))


if __name__ == '__main__':
    main()
