"""E11 -- split delivery across subscriber lines and the CONFLUENCE test.

Part 1 is analytic and checked against the real lines: a distributor that moves
U bytes over k lines shows U/k on each, against that line's own consumption
C_i. Every line stays under a quota tau exactly when

    k >= U (1 - tau) / (tau * C_i)

so the number of lines needed to hide is linear in the excess the distributor
wants to carry. The check replays this on the measured UNSW lines.

Part 2 asks whether the group can be recovered from packet headers alone. Split
fragments of one delivery go to an overlapping audience, so the k lines share
destinations. CONFLUENCE clusters lines by the Jaccard overlap of their
destination sets; the audience structure is injected, so this is a
recoverability check on a semi-synthetic field, not a live measurement.
"""
import json
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
RAW = os.path.join(DATA, 'raw')

CLIENT = '59.166.'
SERVICE = '149.171.126.'
TAUS = [0.50, 0.25]


def load_pairs():
    acc = {}
    for fn in ['UNSW-NB15_1.csv', 'UNSW-NB15_3.csv', 'UNSW-NB15_4.csv']:
        path = os.path.join(RAW, fn)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, header=None, names=range(49), encoding='utf-8-sig',
                         usecols=[0, 2, 7, 8], low_memory=False)
        df.columns = ['src', 'dst', 'sb', 'db']
        df = df.dropna(subset=['src', 'dst'])
        for c in ('sb', 'db'):
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        for s, d, x, y in zip(df['src'], df['dst'], df['sb'], df['db']):
            k = (s, d)
            cur = acc.get(k)
            if cur is None:
                acc[k] = [x, y]
            else:
                cur[0] += x
                cur[1] += y
    return acc


def lines_from(pairs):
    up, dn = {}, {}
    for (s, d), (sb, db) in pairs.items():
        if s.startswith(CLIENT):
            up[s] = up.get(s, 0.0) + sb
            dn[s] = dn.get(s, 0.0) + db
        if d.startswith(CLIENT):
            up[d] = up.get(d, 0.0) + db
            dn[d] = dn.get(d, 0.0) + sb
    subs = sorted(k for k in up if up[k] + dn[k] > 0)
    U = np.array([up[k] for k in subs], dtype=float)
    C = np.array([dn[k] for k in subs], dtype=float)
    return subs, U, C


def min_lines(U_total, C, tau):
    """Smallest k such that every line stays at or under tau."""
    for k in range(1, 201):
        per = (U_total / k) / (U_total / k + C)
        if np.all(per <= tau):
            return k, float(per.max())
    return None, None


def main():
    pairs = load_pairs()
    subs, U, C = lines_from(pairs)
    c_med = float(np.median(C))
    print('subscriber lines: %d, consumption median %.2f MB'
          % (len(subs), c_med / 1e6))

    out = {'subscriber_lines': len(subs),
           'consumption_median_mb': c_med / 1e6,
           'uplink_median_mb': float(np.median(U)) / 1e6,
           'law': [], 'replay': [], 'confluence': {}}

    # ---- part 1a: the law, in units of household consumption
    for tau in TAUS:
        for m in (1.0, 2.0, 5.0, 10.0, 20.0):
            U_total = m * c_med
            k_law = int(np.ceil(U_total * (1.0 - tau) / (tau * c_med)))
            k_rep, worst = min_lines(U_total, C, tau)
            out['law'].append({'tau': tau, 'volume_x_household': m,
                               'k_law': k_law, 'k_replay': k_rep,
                               'worst_per_line_rho': worst})
            print('tau=%.2f volume=%4.1fx household -> k_law=%3d  replay k=%3s  '
                  'worst rho=%.3f' % (tau, m, k_law, k_rep, worst or -1))

    # ---- part 1b: what the group shows while every line passes
    for tau in TAUS:
        U_total = 10.0 * c_med
        k, _ = min_lines(U_total, C, tau)
        grp = U_total / (U_total + C[:k].sum() * (len(subs) / k) / (len(subs) / k))
        grp = U_total / (U_total + float(np.mean(C)) * k)
        # The per-line ratio is largest on the line with the smallest downlink,
        # so this is the best case from the hider's point of view, not a maximum
        # over lines of downlink.
        out['replay'].append({'tau': tau, 'k': k,
                              'group_rho': float(grp),
                              'line_rho_best_case': float(
                                  (U_total / k) / (U_total / k + C).max())})
        print('tau=%.2f: hiding takes %d lines, group rho %.3f'
              % (tau, k, grp))

    # ---- part 2: CONFLUENCE recoverability, semi-synthetic
    rng = np.random.default_rng(20261107)
    N, K, AU, POOL = 200, 10, 12, 500
    # The audience of the split delivery is the nodes a farm line has in common:
    # a line that carries fragments for the same delivery reaches *more*
    # destinations than a household, not fewer.  An earlier version of this
    # generator gave the farm five destinations and households up to eleven,
    # which inverted the premise; the numbers below are the corrected field.
    SHARED = 8
    shared = list(rng.choice(POOL, AU, replace=False))
    dests = []
    for i in range(N):
        if i < K:
            take = list(rng.choice(shared, SHARED, replace=False))
            dests.append(set(take) | set(rng.choice(POOL, 3, replace=False)))
        else:
            m = int(rng.integers(3, 13))
            dests.append(set(rng.choice(POOL, m, replace=False)))

    def jac(a, b):
        return len(a & b) / len(a | b) if (a or b) else 0.0

    rows = []
    for thr in (0.10, 0.15, 0.20, 0.25, 0.30, 0.40):
        parent = list(range(N))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i in range(N):
            for j in range(i + 1, N):
                if jac(dests[i], dests[j]) >= thr:
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[rj] = ri
        # The seed is the line whose destinations are the most widely shared,
        # not a member we injected: picking index 0 would use the label we are
        # trying to recover.
        freq = {}
        for d in dests:
            for x in d:
                freq[x] = freq.get(x, 0) + 1
        seed = int(np.argmax([sum(freq[x] for x in d) for d in dests]))
        comp = [i for i in range(N) if find(i) == find(seed)]
        tp = len([i for i in comp if i < K])
        fp = len(comp) - tp
        rows.append({'threshold': thr, 'component': len(comp),
                     'recall': tp / K, 'precision': tp / max(1, len(comp)),
                     'false_members': fp})
        print('CONFLUENCE thr=%.2f -> component %3d, recall %.2f, precision %.2f'
              % (thr, len(comp), tp / K, tp / max(1, len(comp))))

    out['confluence'] = {'lines': N, 'split_lines': K, 'audience': AU,
                         'shared_per_line': SHARED, 'unique_per_line': 3,
                         'seed_rule': 'largest shared-destination weight',
                         'scan': rows}
    with open(os.path.join(DATA, 'e11_farm.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print('wrote data/e11_farm.json')


if __name__ == '__main__':
    main()
