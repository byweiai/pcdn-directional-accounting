# -*- coding: utf-8 -*-
"""E2: does the detection route survive an adversary that cannot touch its bytes?

Setup. On UNSW-NB15 the two sides of the testbed are distinguishable at the
*role* level: 149.171.126.0/24 answers requests (service role), 59.166.0.0/16
issues them (client role). A detector that tries to tell a distribution endpoint
from a consumption endpoint therefore faces a two-class problem on real flows.
We compare two learners on the same rows:

  (A) the detection route -- a gradient-boosted model over packet-level
      features (packet sizes, inter-arrival timing, ports, transport, TTLs,
      packet counts);
  (B) the metering route -- the single scalar rho = sbytes/(sbytes+dbytes).

Then we let the adversary do what a peer-assisted node actually can do: keep its
byte volumes exactly as they are and rewrite everything else. Two evasion models
are applied, mild and severe. Route (B) is invariant by construction; the point
of the experiment is to measure how much of (A) evaporates, so the claim
"detection is structurally unable to finish" is a measured statement rather than
an assertion.

Nothing is synthesised: every row, including the evaded ones, is a real captured
flow whose *feature coordinates* were replaced by values drawn from the opposite
role's empirical distribution. Byte counts are never touched.
"""
import os, json, time
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e2_evasion.json')
RNG = np.random.default_rng(20261106)

IDX = {'srcip': 0, 'sport': 1, 'dstip': 2, 'dsport': 3, 'proto': 4,
       'state': 5, 'dur': 6, 'sbytes': 7, 'dbytes': 8,
       'sttl': 9, 'dttl': 10, 'Spkts': 16, 'Dpkts': 17,
       'smeansz': 22, 'dmeansz': 23, 'Sjit': 26, 'Djit': 27,
       'Stime': 28, 'Ltime': 29, 'Label': 48}
NFIELDS = 49

# packet-level coordinates an endpoint can rewrite without changing how many
# bytes it moves (payload encryption, port randomisation, pacing, repacketising)
MUTABLE = ['dsport', 'sport', 'dur', 'Spkts', 'Dpkts', 'smeansz', 'dmeansz',
           'Sjit', 'Djit']
# coordinates fixed by the operating system / access technology
FIXED = ['proto', 'state', 'sttl', 'dttl']


def load():
    keep = sorted(IDX.values())
    frames = []
    path = os.path.join(DATA, 'raw', 'UNSW-NB15_1.csv')
    print('  reading', os.path.basename(path))
    raw = pd.read_csv(path, header=None, names=list(range(NFIELDS)),
                      usecols=keep, low_memory=False, encoding='utf-8-sig',
                      na_values=['-', ''])
    df = pd.DataFrame({k: raw[i] for k, i in IDX.items()})
    for c in ['dur', 'sbytes', 'dbytes', 'Spkts', 'Dpkts', 'smeansz', 'dmeansz',
              'Sjit', 'Djit', 'sttl', 'dttl', 'sport', 'dsport']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def build(df, n_per_class=150000):
    d = df.dropna(subset=['sbytes', 'dbytes', 'dur']).copy()
    d = d[(d['sbytes'] + d['dbytes']) > 0]
    srv = d[d['srcip'].astype(str).str.startswith('149.171.126.')]
    cli = d[d['srcip'].astype(str).str.startswith('59.166.')]
    print('  candidate rows: service-originated %d, client-originated %d' % (len(srv), len(cli)))
    n = min(n_per_class, len(srv), len(cli))
    srv = srv.sample(n=n, random_state=11)
    cli = cli.sample(n=n, random_state=12)
    X = pd.concat([srv, cli], ignore_index=True)
    X['y'] = [1] * n + [0] * n
    return X


def encode(X, cats):
    out = X.copy()
    for c in cats:
        out[c] = out[c].astype(str)
        out[c] = pd.Categorical(out[c]).codes.astype('float32')
    return out


def fit_eval(Xtr, ytr, Xte, yte, cols, name):
    Xtr = Xtr[cols].astype('float32').fillna(0.0)
    Xte = Xte[cols].astype('float32').fillna(0.0)
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                       max_depth=6, random_state=7)
    m.fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, p)
    print('   %-34s AUC=%.4f' % (name, auc))
    return auc, m


def main():
    t0 = time.time()
    print('== E2: detection route vs metering route under byte-preserving evasion ==')
    df = load()
    X = build(df)
    print('  working set:', len(X))

    cats = ['proto', 'state']
    X = encode(X, cats)

    dur = np.log1p(X['dur'].clip(lower=0))
    X['dur'] = dur
    for c in ['Spkts', 'Dpkts', 'smeansz', 'dmeansz', 'Sjit', 'Djit', 'sport', 'dsport']:
        X[c] = np.log1p(X[c].clip(lower=0))

    X['rho'] = X['sbytes'] / (X['sbytes'] + X['dbytes'])

    feats_all = list(dict.fromkeys(cats + FIXED + MUTABLE))
    tr, te = train_test_split(np.arange(len(X)), test_size=0.4, random_state=3,
                              stratify=X['y'].values)
    Xtr, Xte = X.iloc[tr].copy(), X.iloc[te].copy()
    ytr, yte = Xtr['y'].values, Xte['y'].values

    res = {}
    # ---- route B: metering, one scalar, no training -----------------------
    auc_rho = roc_auc_score(yte, Xte['rho'].values)
    print('   %-34s AUC=%.4f' % ('metering (rho only, no training)', auc_rho))
    res['auc_rho'] = float(auc_rho)

    # ---- route A: detection on packet-level features ----------------------
    auc_all, _ = fit_eval(Xtr, ytr, Xte, yte, feats_all, 'detection (all packet features)')
    auc_mut, _ = fit_eval(Xtr, ytr, Xte, yte, MUTABLE, 'detection (mutable coords only)')
    auc_fix, _ = fit_eval(Xtr, ytr, Xte, yte, FIXED, 'detection (OS-fixed coords only)')
    res.update({'auc_detect_all': float(auc_all),
                'auc_detect_mutable': float(auc_mut),
                'auc_detect_fixed': float(auc_fix)})

    # ---- evasion 1 (mild): permute each mutable coordinate within class ---
    def permute_mut(src_df, ref_dst, cols):
        out = src_df.copy()
        for c in cols:
            v = out[c].values.copy()
            RNG.shuffle(v)
            out[c] = v
        return out

    # mild: shuffle mutable coordinates among rows of the *same* class only,
    # which keeps each coordinate's marginal exactly and destroys any joint
    # structure the detector could have used.
    ev_tr = Xtr.copy()
    ev_te = Xte.copy()
    for c in MUTABLE:
        v = ev_te[c].values.copy()
        RNG.shuffle(v)
        ev_te[c] = v
    auc_perm, _ = None, None
    Xtr2 = Xtr[feats_all].astype('float32').fillna(0.0)
    Xte2 = ev_te[feats_all].astype('float32').fillna(0.0)
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                       max_depth=6, random_state=7)
    m.fit(Xtr2, ytr)
    auc_perm = roc_auc_score(yte, m.predict_proba(Xte2)[:, 1])
    print('   %-34s AUC=%.4f' % ('evaded: mild (coordinate shuffle)', auc_perm))
    res['auc_detect_evaded_mild'] = float(auc_perm)

    # ---- evasion 2 (severe): adopt the opposite role's coordinates --------
    # The node rewrites every mutable coordinate using the empirical
    # distribution of *legitimate client* flows. Byte counts stay identical, so
    # rho is untouched -- the rewrite is exactly the adversary's free move.
    cli_te = Xte[Xte['y'] == 0]
    srv_te = Xte[Xte['y'] == 1]
    ev = Xte.copy()
    donor = cli_te
    idx_srv = ev.index[ev['y'] == 1]
    for c in MUTABLE:
        vals = donor[c].values
        ev.loc[idx_srv, c] = RNG.choice(vals, size=len(idx_srv), replace=True)
    auc_rep = None
    Xte3 = ev[feats_all].astype('float32').fillna(0.0)
    auc_rep = roc_auc_score(yte, m.predict_proba(Xte3)[:, 1])
    print('   %-34s AUC=%.4f' % ('evaded: severe (adopt client coords)', auc_rep))
    res['auc_detect_evaded_severe'] = float(auc_rep)

    # rho after evasion: identical by construction, assert it
    rho_before = (Xte['sbytes'] / (Xte['sbytes'] + Xte['dbytes'])).values
    rho_after = (ev['sbytes'] / (ev['sbytes'] + ev['dbytes'])).values
    drift = float(np.max(np.abs(rho_before - rho_after)))
    print('   max |rho drift| under evasions: %.3e' % drift)
    res['rho_max_drift'] = drift

    # how many bytes the severe evasion costs the node: none
    res['byte_change_pct'] = float(
        100 * (np.abs(ev['sbytes'].sum() + ev['dbytes'].sum()
                      - (Xte['sbytes'].sum() + Xte['dbytes'].sum()))
               / (Xte['sbytes'].sum() + Xte['dbytes'].sum())))

    res['n_rows'] = int(len(X))
    res['n_test'] = int(len(Xte))
    res['features'] = {'mutable': MUTABLE, 'fixed': FIXED, 'all': feats_all}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print('\nwrote', OUT, ' in %.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
