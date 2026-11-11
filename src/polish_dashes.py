"""Em-dash sweep: replace dashed asides with commas, colons, semicolons.

Each entry is (file, old, new) and must match exactly once, so a silent miss or
a double match fails loudly instead of half-applying.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(HERE, '..', 'paper')

EDITS = [
    ('main.tex', 'use---roughly ten times more', 'use, roughly ten times more'),
    ('main.tex', 'downlink than uplink---and the platform',
     'downlink than uplink, and the platform'),
    ('main.tex', 'attractive---graph models', 'attractive: graph models'),
    ('main.tex', 'ambiguous---\\eOneAmbPct', 'ambiguous: \\eOneAmbPct'),
    ('main.tex', 'and $0.6$---so the quantity', 'and $0.6$, so the quantity'),
    ('main.tex', 'governance primitive---formulation',
     'governance primitive: formulation'),

    ('sec_deploy.tex', 'two additions per packet---no flow table',
     'two additions per packet: no flow table'),
    ('sec_deploy.tex', 'for throughput---it is', 'for throughput; it is'),
    ('sec_deploy.tex', 'can stage it---observe only',
     'can stage it, observe only'),

    ('sec_detection.tex', "signal---it is a different quantity",
     "signal: it is a different quantity"),
    ('sec_detection.tex', 'the clean case---the fitted model',
     'the clean case: the fitted model'),
    ('sec_detection.tex', 'in-sample data---and it is the honest',
     'in-sample data, and it is the honest'),
    ('sec_detection.tex', 'Nine grid points---', 'Nine grid points, '),
    ('sec_detection.tex', ']$---have a detector', ']$, have a detector'),
    ('sec_detection.tex', 'distinguishing it---and so has the business',
     'distinguishing it, and so has the business'),
    ('sec_detection.tex', 'We tested fan-out---the number of distinct',
     'We tested fan-out, the number of distinct'),
    ('sec_detection.tex', 'in a window---as a candidate second',
     'in a window, as a candidate second'),

    ('sec_discussion.tex', 'of the three regimes---who pays',
     'of the three regimes (who pays'),
    ('sec_discussion.tex', 'lands---and its quantitative',
     'lands), and its quantitative'),
    ('sec_discussion.tex', 'subscription as the unit---which is the unit',
     'subscription as the unit, which is the unit'),
    ('sec_discussion.tex', 'A single quota---upload may not',
     'A single quota, upload may not'),
    ('sec_discussion.tex', 'three windows---separates', 'three windows, separates'),
    ('sec_discussion.tex', 'provisioned to carry---a', 'provisioned to carry, a'),

    ('sec_eval.tex', 'S1 --- enforcement.', 'S1: enforcement.'),
    ('sec_eval.tex', 'S2 --- spot pricing.', 'S2: spot pricing.'),
    ('sec_eval.tex', 'S3 --- declared tiers.', 'S3: declared tiers.'),
    ('sec_eval.tex', 'tiers deliver---eighty-four per', 'tiers deliver, eighty-four per'),
    ('sec_eval.tex', 'out---the coincidence is the check',
     'out; the coincidence is the check'),
    ('sec_eval.tex', 'do not move---their margin is', 'do not move; their margin is'),
    ('sec_eval.tex', 'whole range---because nothing', 'whole range, because nothing'),

    ('sec_metering.tex', 'becomes expensive---\\eNineFpAtTen',
     'becomes expensive: \\eNineFpAtTen'),
    ('sec_metering.tex', 'are flagged---which locates', 'are flagged, which locates'),
    ('sec_metering.tex', 'the sustained rule---three', 'the sustained rule, three'),
    ('sec_metering.tex', 'above quota---changes the picture',
     'above quota, changes the picture'),
    ('sec_metering.tex', 'some sender cell---there is always a',
     'some sender cell; there is always a'),
    ('sec_metering.tex', 'Two regimes---the first twelve', 'Two regimes, the first twelve'),
    ('sec_metering.tex', 'the last twelve---account for',
     'the last twelve, account for'),
    ('sec_metering.tex', 'to subscribers---it is applying', 'to subscribers; it is applying'),
    ('sec_metering.tex', 'positive excess---the maximum over all windows',
     'positive excess; the maximum over all windows'),
    ('sec_metering.tex', '\\eTwelveSubMaxExcess~MB---while the median',
     '\\eTwelveSubMaxExcess~MB, while the median'),

    ('sec_policy.tex', 'endpoint can change---ports', 'endpoint can change: ports'),
    ('sec_policy.tex', 'payload---whereas the two counters',
     'payload, whereas the two counters'),
    ('sec_policy.tex', 'interpretation---consumer or distributor---is supplied',
     'interpretation, consumer or distributor, is supplied'),
    ('sec_policy.tex', 'modelling assumption---it is a measured',
     'modelling assumption; it is a measured'),
    ('sec_policy.tex', 'multiplier---and it is what makes',
     'multiplier, and it is what makes'),
    ('sec_policy.tex', 'our corpora---neither UNSW-NB15', 'our corpora: neither UNSW-NB15'),
    ('sec_policy.tex', 'merely enforced---the same logic',
     'merely enforced, the same logic'),
    ('sec_policy.tex', 'distribution behind it---a speaker', 'distribution behind it: a speaker'),
    ('sec_policy.tex', 'that is the point---a proportion', 'that is the point: a proportion'),

    ('sec_related.tex', 'literature---fourteen years of it', 'literature, fourteen years of it'),
    ('sec_related.tex', 'copyright law---establishes that', 'copyright law, establishes that'),

    ('sec_model.tex', 'instructive---it removes', 'instructive: it removes'),
]


def main():
    texts, bad = {}, []
    for fn in {e[0] for e in EDITS}:
        texts[fn] = io.open(os.path.join(PAPER, fn), encoding='utf-8').read()
    n = 0
    for fn, old, new in EDITS:
        c = texts[fn].count(old)
        if c != 1:
            bad.append((fn, old, c))
            continue
        texts[fn] = texts[fn].replace(old, new)
        n += 1
    if bad:
        for fn, old, c in bad:
            print('MISS %-18s x%d  %r' % (fn, c, old[:60]))
        print('%d applied, %d failed' % (n, len(bad)))
        sys.exit(1)
    for fn, t in texts.items():
        io.open(os.path.join(PAPER, fn), 'w', encoding='utf-8', newline='\n').write(t)
    left = sum(t.count('---') for t in texts.values())
    print('%d replacements applied; %d dashes left in the swept files' % (n, left))


if __name__ == '__main__':
    main()
