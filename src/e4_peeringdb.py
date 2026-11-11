# -*- coding: utf-8 -*-
"""E4: directional asymmetry is already an institutional governance variable.

The paper's rule -- a subscriber endpoint may not send more than it receives --
looks like a novel imposition on terminals. It is not. The interconnection
economy has carried exactly this quantity as a first-class, publicly reported
attribute of every network for years: PeeringDB's ``info_ratio``, where an
operator declares whether its traffic is Heavy Inbound, Mostly Inbound,
Balanced, Mostly Outbound or Heavy Outbound, and interconnection policy keys off
that declaration.

So the rule is not invented here. It is the terminal-scale image of a variable
that already governs the AS-scale. This experiment measures how entrenched the
variable is and how it covaries with what kind of network an operator is.
"""
import json, os, time, urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
RAW = os.path.join(DATA, 'peeringdb_net.json')
OUT = os.path.join(DATA, 'e4_peeringdb.json')

UA = {'User-Agent': 'Mozilla/5.0 (research; mailto:lvyue@yn.chinamobile.com)'}
BASE = 'https://www.peeringdb.com/api/net?limit=250&skip=%d&depth=0'
FIELDS = ['asn', 'name', 'info_type', 'info_ratio', 'info_traffic',
          'info_scope', 'info_prefixes4', 'info_prefixes6']

RATIO_ORDER = ['Heavy Inbound', 'Mostly Inbound', 'Balanced',
               'Mostly Outbound', 'Heavy Outbound']


def fetch_all():
    if os.path.exists(RAW):
        rows = json.load(open(RAW, encoding='utf-8'))
        print('  cached %d networks' % len(rows))
        return rows
    rows, skip = [], 0
    while True:
        url = BASE % skip
        got = None
        for a in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                            timeout=90) as r:
                    got = json.load(r)
                break
            except Exception as e:
                print('    retry %d %s' % (a, type(e).__name__), flush=True)
                time.sleep(3)
        if not got:
            print('  giving up at skip=%d' % skip)
            break
        page = got.get('data', [])
        if not page:
            break
        for rec in page:
            rows.append({k: rec.get(k) for k in FIELDS})
        skip += len(page)
        if skip % 5000 == 0 or len(page) < 250:
            print('    %d networks' % skip, flush=True)
        if len(page) < 250:
            break
    json.dump(rows, open(RAW, 'w', encoding='utf-8'), ensure_ascii=False)
    return rows


def cramers_v(table):
    """Cramer's V for a contingency table given as list of lists."""
    n = sum(sum(r) for r in table)
    if n == 0:
        return 0.0
    R, C = len(table), len(table[0])
    rs = [sum(r) for r in table]
    cs = [sum(table[i][j] for i in range(R)) for j in range(C)]
    chi2 = 0.0
    for i in range(R):
        for j in range(C):
            if rs[i] and cs[j]:
                e = rs[i] * cs[j] / n
                chi2 += (table[i][j] - e) ** 2 / e
    k = min(R, C) - 1
    return (chi2 / (n * k)) ** 0.5 if k > 0 else 0.0


def main():
    print('== E4: directional ratio as an institutional variable ==')
    rows = fetch_all()
    n = len(rows)
    print('  networks: %d' % n)

    ratio = Counter((r['info_ratio'] or 'Not Disclosed').strip() for r in rows)
    types = Counter((r['info_type'] or 'Unknown').strip() for r in rows)
    print('\n  declared traffic ratio:')
    for k in RATIO_ORDER + ['Not Disclosed']:
        v = ratio.get(k, 0)
        print('    %-16s %5d  %5.1f%%' % (k, v, 100 * v / n))

    declared = sum(ratio.get(k, 0) for k in RATIO_ORDER)
    skew = (ratio.get('Heavy Inbound', 0) + ratio.get('Mostly Inbound', 0)
            - ratio.get('Heavy Outbound', 0) - ratio.get('Mostly Outbound', 0))
    print('\n  declared: %d / %d = %.1f%% of networks state a directional ratio'
          % (declared, n, 100 * declared / n))
    print('  inbound-leaning minus outbound-leaning: %+d (%.1f%% of declared)'
          % (skew, 100 * skew / declared if declared else 0))

    # contingency: network kind x declared ratio
    kinds = [k for k, c in types.most_common() if c >= 60]
    table = []
    for k in kinds:
        row = [sum(1 for r in rows
                   if (r['info_type'] or 'Unknown').strip() == k
                   and (r['info_ratio'] or 'Not Disclosed').strip() == lab)
               for lab in RATIO_ORDER + ['Not Disclosed']]
        table.append(row)
    v = cramers_v(table)
    print('\n  Cramer V (network kind x ratio) = %.4f over %d kinds' % (v, len(kinds)))
    print('  %-22s %s' % ('kind', ' '.join('%9s' % s[:9] for s in RATIO_ORDER + ['NotDiscl'])))
    for k, row in zip(kinds, table):
        tot = sum(row) or 1
        print('  %-22s %s   n=%d' % (k, ' '.join('%8.1f%%' % (100 * x / tot) for x in row), tot))

    # does declared ratio track the kind of business a network is in?
    out = {
        'n_networks': n,
        'ratio_counts': {k: ratio.get(k, 0) for k in RATIO_ORDER + ['Not Disclosed']},
        'declared_share': declared / n if n else 0,
        'inbound_minus_outbound': skew,
        'type_counts': dict(types.most_common(12)),
        'kinds': kinds,
        'ratio_labels': RATIO_ORDER + ['Not Disclosed'],
        'table': table,
        'cramers_v': v,
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
