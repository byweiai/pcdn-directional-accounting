"""C14 probe: is the CONFLUENCE recall/precision report an artefact of seeding
the union-find scan at injected member 0?

Recomputes the same semi-synthetic graph as src/e11_farm.py (same seed and
parameters) and scores every component instead of the one containing line 0:
  (a) seed at injected member 0            (what the paper reports today)
  (b) seed at a uniformly random line      (oracle-free, averaged)
  (c) union of all components holding an injected member  (best case, oracle)
  (d) the largest single component          (worst-case contamination)
Writes data/e11_farm_seedsens.json. Reads nothing, changes no existing file.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data')

rng = np.random.default_rng(20261107)
N, K, AU, POOL = 200, 10, 12, 500
shared = list(rng.choice(POOL, AU, replace=False))
dests = []
for i in range(N):
    if i < K:
        take = list(rng.choice(shared, 3, replace=False))
        dests.append(set(take) | set(rng.choice(POOL, 2, replace=False)))
    else:
        m = int(rng.integers(3, 12))
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
    comps = {}
    for i in range(N):
        comps.setdefault(find(i), []).append(i)

    def score(members):
        tp = sum(1 for i in members if i < K)
        return dict(size=len(members), recall=round(tp / K, 4),
                    precision=round(tp / len(members), 4) if members else 0.0,
                    false_members=len(members) - tp)

    seed0 = score([i for i in range(N) if find(i) == find(0)])
    rnd = rng.integers(0, N, size=2000)
    sizes, recs, precs = [], [], []
    for s in rnd:
        sc = score(comps[find(int(s))])
        sizes.append(sc['size']); recs.append(sc['recall']); precs.append(sc['precision'])
    oracle = score([i for m in comps.values() if any(x < K for x in m) for i in m])
    biggest = max(comps.values(), key=len)
    rows.append({'threshold': thr, 'n_components': len(comps),
                 'seed_at_farm_member': seed0,
                 'random_seed': {'size_mean': round(float(np.mean(sizes)), 3),
                                 'recall_mean': round(float(np.mean(recs)), 4),
                                 'precision_mean': round(float(np.mean(precs)), 4),
                                 'recall_p50': round(float(np.median(recs)), 4),
                                 'precision_p50': round(float(np.median(precs)), 4)},
                 'oracle_union': oracle,
                 'largest_component': score(biggest)})
    print('thr %.2f | farm-seed rec %.2f prec %.2f | random rec %.2f prec %.2f '
          '| oracle rec %.2f prec %.2f | largest %d'
          % (thr, seed0['recall'], seed0['precision'],
             rows[-1]['random_seed']['recall_mean'],
             rows[-1]['random_seed']['precision_mean'],
             oracle['recall'], oracle['precision'], len(biggest)))

json.dump({'lines': N, 'split_lines': K, 'audience': AU, 'row': rows},
          open(os.path.join(DATA, 'e11_farm_seedsens.json'), 'w', encoding='utf-8'),
          indent=1)
print('wrote data/e11_farm_seedsens.json')
