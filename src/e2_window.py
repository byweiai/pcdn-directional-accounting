# -*- coding: utf-8 -*-
"""E2: locate the evasion window where detection fails but metering still works.

A peer-assisted node lives on an ordinary residential line, shares the operating
system and the access technology of its neighbours, and therefore cannot be told
apart by any coordinate that a normal subscriber also fixes (TTLs, transport,
TCP state). What it *can* change for free is everything above the byte count:
ports, pacing, packet sizes, burst shape. What it cannot change for free is how
much it sends.

So the experiment asks a precise question. Let alpha be the byte share of a
node's traffic that is genuine distribution, with the remainder imitating
ordinary consumption. Sweep alpha from 1 to 0 and measure two things on the same
real flows:

  * TPR of a detector trained on packet-level coordinates at alpha = 1 vs 0;
  * the resulting rho, which is a deterministic function of alpha.

The interesting object is the *window*: values of alpha at which the detector is
already at chance while rho still sits well above the subscriber distribution.
Inside that window enforcement based on classification has lost the target, and
metering has not.
"""
import os, json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e2_window.json')
RNG = np.random.default_rng(20261106)

IDX = {'srcip': 0, 'sport': 1, 'dstip': 2, 'dsport': 3, 'proto': 4,
       'state': 5, 'dur': 6, 'sbytes': 7, 'dbytes': 8,
       'Spkts': 16, 'Dpkts': 17, 'smeansz': 22, 'dmeansz': 23,
       'Sjit': 26, 'Djit': 27, 'Label': 48}
NFIELDS = 49

# Coordinates a subscriber-side endpoint can rewrite at no byte cost. TTLs,
# transport and TCP state are deliberately excluded: a node shares them with its
# neighbours, so they carry no role information in the population we care about.
MUTABLE = ['sport', 'dsport', 'dur', 'Spkts', 'Dpkts', 'smeansz', 'dmeansz',
           'Sjit', 'Djit']


def load():
    path = os.path.join(DATA, 'raw', 'UNSW-NB15_1.csv')
    keep = sorted(IDX.values())
    raw = pd.read_csv(path, header=None, names=list(range(NFIELDS)),
                      usecols=keep, low_memory=False, encoding='utf-8-sig',
                      na_values=['-', ''])
    df = pd.DataFrame({k: raw[i] for k, i in IDX.items()})
    for c in ['dur', 'sbytes', 'dbytes', 'Spkts', 'Dpkts', 'smeansz', 'dmeansz',
              'Sjit', 'Djit', 'sport', 'dsport']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def prep(df):
    d = df.dropna(subset=['sbytes', 'dbytes', 'dur']).copy()
    d = d[(d['sbytes'] + d['dbytes']) > 0]
    srv = d[d['srcip'].astype(str).str.startswith('149.171.126.')]
    cli = d[d['srcip'].astype(str).str.startswith('59.166.')]
    n = min(len(srv), len(cli))
    srv = srv.sample(n=n, random_state=11).reset_index(drop=True)
    cli = cli.sample(n=n, random_state=12).reset_index(drop=True)
    for t in (srv, cli):
        t['dur'] = np.log1p(t['dur'].clip(lower=0))
        for c in ['Spkts', 'Dpkts', 'smeansz', 'dmeansz', 'Sjit', 'Djit',
                  'sport', 'dsport']:
            t[c] = np.log1p(t[c].clip(lower=0))
        t['rho'] = t['sbytes'] / (t['sbytes'] + t['dbytes'])
        t['grp'] = t['srcip'].astype(str) + '|' + t['dstip'].astype(str)
    return srv, cli


def mix(srv, cli, alpha, n, seed=0):
    """Build a traffic mixture whose *byte* share of distribution is alpha.

    Rows are drawn from both populations and then reweighted so that the total
    bytes contributed by distribution-type rows equals alpha of the mixture.
    """
    rng = np.random.default_rng(seed * 7919 + int(1000 * alpha))
    # draw candidate rows
    a_rows = srv.sample(n=n, replace=True, random_state=int(rng.integers(1 << 30)))
    b_rows = cli.sample(n=n, replace=True, random_state=int(rng.integers(1 << 30)))
    ab = (a_rows['sbytes'] + a_rows['dbytes']).values
    bb = (b_rows['sbytes'] + b_rows['dbytes']).values
    # choose k distribution rows whose byte total gives the target share
    tot_target = alpha / max(1e-9, (1 - alpha)) if alpha < 1 else 1e9
    order = np.argsort(-ab)
    cum = np.cumsum(ab[order])
    if alpha >= 0.999:
        k = n
    else:
        b_cum = np.cumsum(bb)
        # pick k such that cum[k-1] / b_cum[n-k-1] closest to target ratio
        k = 1
        best = None
        for cand in range(1, n):
            ratio = cum[cand - 1] / max(1.0, b_cum[n - cand - 1])
            d = abs(np.log(max(1e-9, ratio)) - np.log(max(1e-9, tot_target)))
            if best is None or d < best:
                best, k = d, cand
    sel_a = a_rows.iloc[order[:k]]
    sel_b = b_rows.iloc[:n - k]
    out = pd.concat([sel_a, sel_b], ignore_index=True)
    out['_cls'] = np.r_[np.ones(len(sel_a)), np.zeros(len(sel_b))]
    return out


def grouped_cv(srv, cli, feats, k=5):
    """Leave-address-pair-out AUC, with per-class rates.

    The in-sample number this replaced (revision 1) was a training-set score. An
    address pair never appears in both halves, so a detector that memorised its
    endpoints cannot score well here.
    """
    both = pd.concat([srv, cli], ignore_index=True)
    X = both[feats].astype('float32').fillna(0.0)
    y = np.r_[np.ones(len(srv)), np.zeros(len(cli))]
    grp = (both['srcip'].astype(str) + '|' + both['dstip'].astype(str)).values
    oof = np.zeros(len(y))
    gkf = GroupKFold(n_splits=k)
    for tr, te in gkf.split(X, y, groups=grp):
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                           max_depth=6, random_state=7)
        m.fit(X.iloc[tr], y[tr])
        oof[te] = m.predict_proba(X.iloc[te])[:, 1]
    flag = oof >= 0.5
    return {
        'auc': float(roc_auc_score(y, oof)),
        'tpr': float(flag[y == 1].mean()),
        'fpr': float(flag[y == 0].mean()),
        'groups': int(len(np.unique(grp))),
        'n': int(len(y)),
        'features': list(feats),
    }


def main():
    print('== E2: the evasion window ==')
    df = load()
    srv, cli = prep(df)
    # A handful of address pairs contribute most of the rows (one server pair
    # holds a third of the distribution side), so an uncapped split lets a single
    # pair decide the held-out rate. Cap every pair at CAP rows: clustering is
    # what the group split is for, and the cap keeps it from dominating.
    CAP = 50
    def cap(frame, seed):
        parts = []
        for g, blk in frame.groupby('grp', sort=True):
            parts.append(blk.sample(n=min(CAP, len(blk)), random_state=seed))
        return pd.concat(parts, ignore_index=True)
    srv = cap(srv, 7)
    cli = cap(cli, 8)
    print('  distribution-side rows: %d   consumption-side rows: %d  (paired capped at %d)'
          % (len(srv), len(cli), CAP))

    feats = MUTABLE
    # detector trained exactly where it would be trained in practice: clean
    # distribution traffic vs clean consumption traffic
    Xtr = pd.concat([srv, cli], ignore_index=True)[feats].astype('float32').fillna(0.0)
    ytr = np.r_[np.ones(len(srv)), np.zeros(len(cli))]
    det = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                         max_depth=6, random_state=7)
    det.fit(Xtr, ytr)
    auc_clean = roc_auc_score(ytr, det.predict_proba(Xtr)[:, 1])
    print('  detector in-sample AUC (alpha=1 vs 0): %.4f' % auc_clean)

    # R5: the number the paper quotes must be out of sample. Address pairs are
    # held out; the port-free row shows how much of the score is port identity.
    ho = grouped_cv(srv, cli, feats)
    ho_noport = grouped_cv(srv, cli, [f for f in feats if f not in ('sport', 'dsport')])
    print('  held-out AUC %.4f (TPR %.3f, FPR %.3f, %d address pairs)'
          % (ho['auc'], ho['tpr'], ho['fpr'], ho['groups']))
    print('  held-out AUC without ports %.4f (TPR %.3f, FPR %.3f)'
          % (ho_noport['auc'], ho_noport['tpr'], ho_noport['fpr']))

    # X01/C10: every mixture is scored out of sample at the level of the unit
    # being classified. Address pairs are partitioned five ways; each fold is
    # scored by a detector that never saw it, and the numbers below are means
    # over the five folds, so the sweep and the cross-validated rates above come
    # from the same estimator.
    # The reference point is the endpoint-level subscriber distribution, not the
    # flow-level one: alpha describes a node's whole traffic, so the statistic it
    # is compared against must be aggregated the same way.
    def means(a):
        """Per-class directional means behind the two multiples, stored for audit."""
        r = acc[a]
        return {k: (float(np.mean(r[k])) if len(r[k]) else 0.0)
                for k in ('dist_up', 'dist_dn', 'cons_up', 'cons_dn')}

    def volume_up_x(a):
        """Household bytes of either direction carried per byte sent."""
        m = means(a)
        if not m['dist_up']:
            return 0.0
        return (m['cons_up'] + m['cons_dn']) / max(1e-9, m['dist_up'])

    def downlink_x(a):
        """Household downlink carried per byte sent, on the same base."""
        r = acc[a]
        if not r['cons_dn'] or not r['dist_up']:
            return 0.0
        du = float(np.mean(r['dist_up']))
        cd = float(np.mean(r['cons_dn']))
        return cd / max(1e-9, du)

    sub_rho_p90 = 0.1255803867012085   # client p90 of the 5-minute panel, from E1
    grp_all = np.r_[srv['grp'].values, cli['grp'].values]
    uniq = np.unique(grp_all)
    rng_split = np.random.default_rng(20261110)
    folds = np.array_split(rng_split.permutation(len(uniq)), 5)

    alphas = [1.0, 0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15,
              0.1, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02]
    N = 2000
    acc = {a: {'all': [], 'dist': [], 'cons': [], 'ratio': [], 'rho': [],
               'dist_up': [], 'dist_dn': [], 'cons_up': [], 'cons_dn': []}
           for a in alphas}
    dacc = {d: {'all': [], 'bad': [], 'gen': []} for d in
            [0.0, 0.25, 0.5, 0.75, 1.0]}
    clean_dist, clean_cons, n_test_rows = [], [], []
    for fx in folds:
        held = set(uniq[fx].tolist())
        srv_te = srv[srv['grp'].isin(held)].reset_index(drop=True)
        cli_te = cli[cli['grp'].isin(held)].reset_index(drop=True)
        srv_tr = srv[~srv['grp'].isin(held)].reset_index(drop=True)
        cli_tr = cli[~cli['grp'].isin(held)].reset_index(drop=True)
        Xtr_ho = pd.concat([srv_tr, cli_tr], ignore_index=True)[feats] \
            .astype('float32').fillna(0.0)
        ytr_ho = np.r_[np.ones(len(srv_tr)), np.zeros(len(cli_tr))]
        det_ho = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                                max_depth=6, random_state=7)
        det_ho.fit(Xtr_ho, ytr_ho)
        cf = det_ho.predict_proba(
            pd.concat([srv_te, cli_te], ignore_index=True)[feats]
            .astype('float32').fillna(0.0))[:, 1] >= 0.5
        clean_dist.append(float(cf[:len(srv_te)].mean()))
        clean_cons.append(float(cf[len(srv_te):].mean()))
        n_test_rows.append(int(len(cf)))

        for a in alphas:
            for rep in range(3):
                m = mix(srv_te, cli_te, a, N, seed=rep)
                flag = det_ho.predict_proba(
                    m[feats].astype('float32').fillna(0.0))[:, 1] >= 0.5
                cls = m['_cls'].values
                acc[a]['all'].append(float(flag.mean()))
                acc[a]['dist'].append(float(flag[cls == 1].mean())
                                      if (cls == 1).any() else float('nan'))
                acc[a]['cons'].append(float(flag[cls == 0].mean())
                                      if (cls == 0).any() else float('nan'))
                acc[a]['ratio'].append(float((m['sbytes'] > m['dbytes']).values.mean()))
                acc[a]['rho'].append(float(m['sbytes'].sum() /
                                           (m['sbytes'].sum() + m['dbytes'].sum())))
                dd = m[cls == 1]
                cc = m[cls == 0]
                acc[a]['dist_up'].append(float(dd['sbytes'].sum()))
                acc[a]['dist_dn'].append(float(dd['dbytes'].sum()))
                acc[a]['cons_up'].append(float(cc['sbytes'].sum()))
                acc[a]['cons_dn'].append(float(cc['dbytes'].sum()))

        # X01: the free move is m, not the volume mix. A share delta of the
        # distribution flows adopts a household's mutable coordinates outright
        # and keeps its bytes, so rho is untouched by construction.
        for delta in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for rep in range(3):
                rng = np.random.default_rng(int(1000 * delta) + 37 * rep)
                rows_d = srv_te.sample(n=N, replace=True,
                                       random_state=int(rng.integers(1 << 30)))
                n_bad = int(round(delta * N))
                bad = set(rng.choice(N, size=n_bad, replace=False).tolist())
                recs = []
                for i in range(N):
                    r = rows_d.iloc[i]
                    if i in bad:
                        r = r.copy()
                        j = int(rng.integers(len(cli_te)))
                        for c in feats:
                            r[c] = cli_te.iloc[j][c]
                    recs.append(r)
                md = pd.DataFrame(recs).reset_index(drop=True)
                flag = det_ho.predict_proba(
                    md[feats].astype('float32').fillna(0.0))[:, 1] >= 0.5
                mb = np.zeros(N, dtype=bool)
                mb[list(bad)] = True
                dacc[delta]['all'].append(float(flag.mean()))
                if mb.any():
                    dacc[delta]['bad'].append(float(flag[mb].mean()))
                if (~mb).any():
                    dacc[delta]['gen'].append(float(flag[~mb].mean()))

    rows = []
    for a in alphas:
        r = acc[a]
        byte_share = float(np.mean(r['rho']))
        rows.append({'alpha': a,
                     'tpr': float(np.mean(r['all'])),
                     'tpr_sd': float(np.std(r['all'])),
                     'dist_flag_rate': float(np.nanmean(r['dist'])),
                     'cons_flag_rate': float(np.nanmean(r['cons'])),
                     'ratio_rule_rate': float(np.mean(r['ratio'])),
                     'rho': byte_share,
                     'mix_x': float((1 - a) / a) if a > 0 else None,
                     'volume_up_x': volume_up_x(a),
                     'downlink_x': downlink_x(a),
                     'means': means(a),
                     'n_rows': N, 'n_folds': len(folds),
                     'above_client_p90': bool(byte_share > sub_rho_p90)})
        print('   alpha=%.2f  flags %5.1f%%+-%4.1f (dist %5.1f%% cons %5.1f%%)'
              '   ratio rule %5.1f%%   rho=%.4f   extra x%6.2f  %s'
              % (a, 100 * np.mean(r['all']),
                 100 * np.std(r['all']), 100 * np.nanmean(r['dist']),
                 100 * np.nanmean(r['cons']), 100 * np.mean(r['ratio']),
                 byte_share, (1 - a) / a,
                 'ABOVE p90' if byte_share > sub_rho_p90 else ''))

    dis = []
    for delta in [0.0, 0.25, 0.5, 0.75, 1.0]:
        r = dacc[delta]
        dis.append({'delta': delta,
                    'flag_all': float(np.mean(r['all'])),
                    'flag_disguised': float(np.mean(r['bad'])) if r['bad'] else None,
                    'flag_genuine': float(np.mean(r['gen'])) if r['gen'] else None})
        print('   disguise delta=%.2f  flags all %5.1f%%  disguised %s  genuine %s'
              % (delta, 100 * np.mean(r['all']),
                 ('%5.1f%%' % (100 * np.mean(r['bad']))) if r['bad'] else '   -   ',
                 ('%5.1f%%' % (100 * np.mean(r['gen']))) if r['gen'] else '   -   '))
    cons_flag = float(np.mean(clean_cons))
    dist_flag = float(np.mean(clean_dist))
    print('   held-out clean flags: distribution %.3f  consumption %.3f  '
          '(%d pairs, %d rows, %d folds)'
          % (dist_flag, cons_flag, len(uniq),
             int(np.mean(n_test_rows)), len(folds)))

    win = [r['alpha'] for r in rows if r['tpr'] <= 0.60 and r['above_client_p90']]
    if win:
        print('\n  evasion window: alpha in [%.3f, %.3f] (%d grid points)'
              % (min(win), max(win), len(win)))
        print('  inside this window a node keeps %.0f-%.0f%% of its distribution'
              ' revenue while the trained detector reads it as an ordinary subscriber'
              % (100 * min(win), 100 * max(win)))
    else:
        print('\n  evasion window: empty')
    # cost of hiding, in units of genuine downlink the node must also carry
    if win:
        rw = [r for r in rows if abs(r['alpha'] - min(win)) < 1e-9]
        if rw:
            print('  cost of reaching alpha=%.3f: x%.2f household bytes per byte sent,'
                  ' of which x%.2f is downlink'
                  % (min(win), rw[0]['volume_up_x'], rw[0]['downlink_x']))

    out = {
        'n_srv': int(len(srv)), 'n_cli': int(len(cli)),
        'detector_auc_clean': float(auc_clean),
        'heldout': ho, 'heldout_noport': ho_noport,
        'sweep_split': {'folds': int(len(folds)),
                        'pairs': int(len(uniq)),
                        'test_rows_mean': float(np.mean(n_test_rows)),
                        'clean_flag_dist': dist_flag,
                        'clean_flag_cons': cons_flag,
                        'seed': 20261110},
        'sweep_oos': True,
        'disguise': dis,
        'household_flag_rate': cons_flag,
        'distributor_flag_rate': dist_flag,
        'client_rho_p90': sub_rho_p90,
        'srv_rho_median': float(srv['rho'].median()),
        'cli_rho_median': float(cli['rho'].median()),
        'sweep': rows,
        'evasion_window': win,
        'features': feats,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
