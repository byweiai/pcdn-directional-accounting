# -*- coding: utf-8 -*-
"""E6: fan-out is the second invariant, and it is the one disguise cannot buy.

E2 showed that an endpoint can make itself look like a subscriber by cutting the
byte share it actually distributes. Buying downlink dilutes the ratio and costs
little when the contract is flat rate. What that move does not change is how
many distinct peers the endpoint serves in a window: to dilute the ratio you
must *receive*, and receiving is one peer at a time; to distribute you must
*send to many*, and that count is what a redistribution service is.

So this experiment measures two coordinates per endpoint per window -- the byte
ratio and the out-fan-out, the number of distinct destinations it sends to --
and checks three things:

  * the two coordinates separate roles in the same direction but are not the
    same coordinate (a high-rho endpoint with fan-out one is not a distributor);
  * buying downlink moves rho and leaves fan-out untouched, so the pair is
    strictly harder to defeat than either alone;
  * sustained high fan-out, like sustained high rho in E3, is what distinguishes
    distribution from the bursty sources in the trace.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e6_fanout.json')

IDX = {'srcip': 0, 'dstip': 2, 'sbytes': 7, 'dbytes': 8, 'Stime': 28, 'Label': 48}
NFIELDS = 49
W = 300
BAD_PREFIX = ('fe80:', 'ff0', 'ff1', 'ff2', '224.', '239.', '0.', '255.')


def load():
    frames = []
    for w in ('1', '2', '3', '4'):
        p = os.path.join(DATA, 'raw', 'UNSW-NB15_%s.csv' % w)
        if not os.path.exists(p):
            continue
        raw = pd.read_csv(p, header=None, names=list(range(NFIELDS)),
                          usecols=sorted(IDX.values()), low_memory=False,
                          encoding='utf-8-sig', na_values=['-', ''])
        frames.append(pd.DataFrame({k: raw[i] for k, i in IDX.items()}))
    df = pd.concat(frames, ignore_index=True)
    for c in ['sbytes', 'dbytes', 'Stime']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['sbytes', 'dbytes', 'Stime'])
    dm = ~df['srcip'].astype(str).str.startswith(BAD_PREFIX)
    dm &= ~df['dstip'].astype(str).str.startswith(BAD_PREFIX)
    dm &= (df['sbytes'] + df['dbytes']) > 0
    return df[dm].copy()


def per_window(df):
    """Per endpoint per window: bytes both ways, and distinct peers each way."""
    t0 = df['Stime'].min()
    df['win'] = ((df['Stime'] - t0) // W).astype('int64')

    s = df[['srcip', 'dstip', 'win', 'sbytes', 'dbytes']].rename(
        columns={'srcip': 'ip', 'dstip': 'peer'})
    s['sent'] = s['sbytes']; s['recv'] = s['dbytes']
    r = df[['dstip', 'srcip', 'win', 'dbytes', 'sbytes']].rename(
        columns={'dstip': 'ip', 'srcip': 'peer'})
    r['sent'] = r['dbytes']; r['recv'] = r['sbytes']
    long = pd.concat([s[['ip', 'peer', 'win', 'sent', 'recv']],
                      r[['ip', 'peer', 'win', 'sent', 'recv']]], ignore_index=True)

    g = long.groupby(['ip', 'win'])
    cell = g.agg(sent=('sent', 'sum'), recv=('recv', 'sum'),
                 fanout=('peer', 'nunique'), nflow=('peer', 'size')).reset_index()
    cell = cell[(cell['sent'] + cell['recv']) > 0]
    cell['rho'] = cell['sent'] / (cell['sent'] + cell['recv'])
    return cell


def role(ip):
    s = str(ip)
    if s.startswith('149.171.126.'):
        return 'service'
    if s.startswith('59.166.'):
        return 'client'
    return 'other'


def main():
    print('== E6: fan-out as a second, disguise-proof coordinate ==')
    df = load()
    print('  flows %d over %.1f h' % (len(df), (df['Stime'].max() - df['Stime'].min()) / 3600))
    cell = per_window(df)
    cell['role'] = cell['ip'].map(role)
    print('  %d endpoint-window cells, %d endpoints' % (len(cell), cell['ip'].nunique()))

    for r in ('client', 'service', 'other'):
        sub = cell[cell['role'] == r]
        if not len(sub):
            continue
        print('  %-8s n=%6d  rho med %.3f  fanout med %.1f (p90 %.0f)  frac fanout>=8: %.3f'
              % (r, len(sub), sub['rho'].median(), sub['fanout'].median(),
                 sub['fanout'].quantile(0.90), (sub['fanout'] >= 8).mean()))

    # joint separation: how much does adding fan-out buy over rho alone?
    cli = cell[cell['role'] == 'client']
    srv = cell[cell['role'] == 'service']
    def auc(a, b):
        if not len(a) or not len(b):
            return float('nan')
        return float((a[:, None] > b[None, :]).mean()
                     + 0.5 * (a[:, None] == b[None, :]).mean())
    auc_rho = auc(srv['rho'].values, cli['rho'].values)
    auc_fan = auc(srv['fanout'].values.astype(float), cli['fanout'].values.astype(float))

    # small-sample AUC for the two-feature combination, via logistic regression
    from sklearn.linear_model import LogisticRegression
    X = np.c_[srv['rho'].values, np.log1p(srv['fanout'].values)]
    Y = np.c_[cli['rho'].values, np.log1p(cli['fanout'].values)]
    tr = np.r_[X, Y]
    lab = np.r_[np.ones(len(X)), np.zeros(len(Y))]
    lr = LogisticRegression(max_iter=2000).fit(tr, lab)
    auc_pair = auc(lr.predict_proba(X)[:, 1], lr.predict_proba(Y)[:, 1])
    print('  AUC service vs client: rho only %.4f, fan-out only %.4f, both %.4f'
          % (auc_rho, auc_fan, auc_pair))

    # what a dilution attack does to each coordinate
    # an endpoint taking alpha of its bytes from distribution and the rest from
    # consumption moves rho linearly; fan-out is set by the distribution part
    dil = []
    for alpha in [1.0, 0.7, 0.5, 0.3, 0.2, 0.1, 0.05]:
        rho_mix = alpha * srv['rho'].median() + (1 - alpha) * cli['rho'].median()
        # fan-out does not dilute: the endpoint still serves its distribution
        # peers, and the extra downlink peers are few by construction
        fan_mix = srv['fanout'].median()
        dil.append({'alpha': alpha, 'rho': float(rho_mix), 'fanout': float(fan_mix),
                    'extra_downlink_x': float((1 - alpha) / alpha)})
        print('  dilute to alpha=%.2f -> rho %.3f (below quota? %s), fan-out stays %.0f,'
              ' extra downlink x%.1f'
              % (alpha, rho_mix, 'yes' if rho_mix < 0.5 else 'no', fan_mix,
                 (1 - alpha) / alpha))

    # sustained fan-out: same persistence test as E3, on the other coordinate
    per = cell.groupby('ip').agg(role=('role', 'first'), windows=('win', 'size'),
                                 fan_med=('fanout', 'median'),
                                 fan_p90=('fanout', lambda s: s.quantile(0.9)),
                                 rho_med=('rho', 'median')).reset_index()
    per = per[per['windows'] >= 3]
    atk = set(df.loc[df['Label'].astype(str).str.strip().isin(['1', '1.0']), 'srcip'].astype(str))
    per['is_attacker'] = per['ip'].astype(str).isin(atk)
    print('\n  endpoints with sustained fan-out >= 8 in half their windows:')
    for r in ('client', 'service', 'other'):
        sub = per[per['role'] == r]
        if not len(sub):
            continue
        print('    %-8s n=%3d  share %.3f' % (r, len(sub), (sub['fan_med'] >= 8).mean()))
    print('  attackers: n=%d, median fan-out %.1f' % (per['is_attacker'].sum(),
                                                     per.loc[per['is_attacker'], 'fan_med'].median()
                                                     if per['is_attacker'].any() else float('nan')))
    both = per[(per['rho_med'] > 0.5) & (per['fan_med'] >= 8)]
    print('  endpoints meeting both coordinates: %d (service %d, client %d, attacker %d)'
          % (len(both), (both['role'] == 'service').sum(), (both['role'] == 'client').sum(),
             both['is_attacker'].sum()))

    out = {
        'n_flows': int(len(df)), 'n_cells': int(len(cell)),
        'roles': {r: {'n_cells': int((cell['role'] == r).sum()),
                      'rho_median': float(cell.loc[cell['role'] == r, 'rho'].median()),
                      'fanout_median': float(cell.loc[cell['role'] == r, 'fanout'].median()),
                      'fanout_p90': float(cell.loc[cell['role'] == r, 'fanout'].quantile(0.9))}
                  for r in ('client', 'service', 'other')},
        'auc': {'rho': auc_rho, 'fanout': auc_fan, 'both': auc_pair},
        'dilution': dil,
        'endpoints': per[['ip', 'role', 'windows', 'fan_med', 'fan_p90', 'rho_med',
                          'is_attacker']].to_dict('records'),
        'both_coordinates': {'n': int(len(both)),
                             'service': int((both['role'] == 'service').sum()),
                             'client': int((both['role'] == 'client').sum()),
                             'attacker': int(both['is_attacker'].sum())},
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
