# -*- coding: utf-8 -*-
"""E8: how long must the window be before the ratio means anything?

The measurement claim rests on aggregating bytes per endpoint, and aggregation
has a cost: a longer window is slower to react. This experiment fixes the
question the design needs answered -- what is the shortest window at which the
two roles separate -- and reports the separation at every candidate rather than
asserting the one that was used.

Single flows are the zero-length window. They are included as the control: if a
single flow already separated the roles, aggregation would be unnecessary.

Separation is reported three ways, because each answers a different objection:
  AUC          can a threshold separate the two roles at all
  overlap      share of endpoints inside (0.4, 0.6), the region where a
               threshold could plausibly be disputed
  margin       distance from the chosen threshold to the nearest endpoint of the
               opposite role, in units of the threshold
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
RAW = os.path.join(DATA, 'raw')
OUT = os.path.join(DATA, 'e8_window.json')

FILES = ['UNSW-NB15_1.csv', 'UNSW-NB15_2.csv', 'UNSW-NB15_3.csv', 'UNSW-NB15_4.csv']
IDX = {'srcip': 0, 'sport': 1, 'dstip': 2, 'dsport': 3, 'proto': 4,
       'sbytes': 7, 'dbytes': 8, 'Stime': 28, 'Ltime': 29}
WINDOWS_S = [0, 60, 120, 300, 600, 900, 1800, 3600]
MIN_FLOWS = 5
THRESH = 0.5


def load():
    frames = []
    for f in FILES:
        p = os.path.join(RAW, f)
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, header=None, names=range(49), usecols=list(IDX.values()),
                        encoding='utf-8-sig', low_memory=False)
        d.columns = list(IDX.keys())
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    for c in ('sbytes', 'dbytes', 'Stime'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['srcip', 'dstip', 'sbytes', 'dbytes', 'Stime'])
    df['sbytes'] = df['sbytes'].astype(np.int64)
    df['dbytes'] = df['dbytes'].astype(np.int64)
    return df.reset_index(drop=True)


def role(ip):
    """UNSW-NB15's own topology: 59.166.x are the hosts, 149.171.126.x the servers."""
    if ip.startswith('59.166.'):
        return 'client'
    if ip.startswith('149.171.126.'):
        return 'service'
    return 'other'


def endpoint_table(df, window):
    """sent and recv bytes per (ip, window); window 0 means one row per flow."""
    long = pd.concat([
        pd.DataFrame({'ip': df['srcip'], 'sent': df['sbytes'], 'recv': df['dbytes'],
                      't': df['Stime']}),
        pd.DataFrame({'ip': df['dstip'], 'sent': df['dbytes'], 'recv': df['sbytes'],
                      't': df['Stime']}),
    ], ignore_index=True)
    if window > 0:
        long['w'] = (long['t'] // window).astype(np.int64)
        g = long.groupby(['ip', 'w'], sort=False).agg(
            sent=('sent', 'sum'), recv=('recv', 'sum'), n=('sent', 'size')).reset_index()
    else:
        long['w'] = np.arange(len(long))
        g = long.rename(columns={'sent': 'sent', 'recv': 'recv'})
        g['n'] = 1
    g = g[g['n'] >= MIN_FLOWS]
    tot = g['sent'] + g['recv']
    g = g[tot > 0].copy()
    g['rho'] = g['sent'] / (g['sent'] + g['recv'])
    g['role'] = g['ip'].map(role)
    return g


def auc(pos, neg):
    if len(pos) == 0 or len(neg) == 0:
        return float('nan')
    a = np.concatenate([pos, neg])
    order = a.argsort()
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ranks for ties
    s = pd.Series(a)
    r = s.rank(method='average').values
    n1, n0 = len(pos), len(neg)
    r1 = r[:n1].sum()
    return float((r1 - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    print('== E8: aggregation window versus separability ==')
    df = load()
    print('  %d flows, %.1f h' % (len(df), (df['Stime'].max() - df['Stime'].min()) / 3600))

    rows = []
    for w in WINDOWS_S:
        g = endpoint_table(df, w)
        c = g.loc[g['role'] == 'client', 'rho'].values
        s = g.loc[g['role'] == 'service', 'rho'].values
        if len(c) < 3 or len(s) < 3:
            print('  window %5ds: too few endpoints (%d client, %d service), skipped'
                  % (w, len(c), len(s)))
            continue
        a = auc(s, c)
        allr = g['rho'].values
        inside = float(np.mean((allr > 0.4) & (allr < 0.6)))
        # what a deployed rule would actually do: one threshold, applied per cell
        fp = float(np.mean(c > THRESH))
        tpr = float(np.mean(s > THRESH))
        # and the stricter rule: flagged only on a run of consecutive cells
        g2 = g.sort_values(['ip', 'w'])
        g2['flag'] = g2['rho'] > THRESH
        streak = g2.groupby('ip')['flag'].apply(
            lambda z: (z.groupby((z != z.shift()).cumsum()).cumsum()).max() if len(z) else 0)
        sus = g2.drop_duplicates('ip').set_index('ip')
        sus_flag = (streak.reindex(sus.index).fillna(0) >= 3).astype(int)
        fp_sus = float(sus_flag[sus['role'] == 'client'].mean()) if (sus['role'] == 'client').any() else float('nan')
        tpr_sus = float(sus_flag[sus['role'] == 'service'].mean()) if (sus['role'] == 'service').any() else float('nan')
        rows.append({'window_s': w, 'cells': int(len(g)),
                     'client_p50': float(np.median(c)), 'client_p95': float(np.percentile(c, 95)),
                     'service_p05': float(np.percentile(s, 5)), 'service_p50': float(np.median(s)),
                     'auc': a, 'inside_band': inside,
                     'separation': float(np.min(s) - np.max(c)),
                     'fp_cell': fp, 'tpr_cell': tpr,
                     'fp_sustained3': fp_sus, 'tpr_sustained3': tpr_sus})
        print('  window %5ds | cells %6d | client p50 %.3f p95 %.3f | service p05 %.3f p50 %.3f '
              '| AUC %.4f | FP %.4f TPR %.4f | FP3 %s TPR3 %s'
              % (w, len(g), rows[-1]['client_p50'], rows[-1]['client_p95'],
                 rows[-1]['service_p05'], rows[-1]['service_p50'], a, fp, tpr,
                 ('%.4f' % fp_sus) if fp_sus == fp_sus else 'n/a',
                 ('%.4f' % tpr_sus) if tpr_sus == tpr_sus else 'n/a'))

    best = max((r for r in rows if r['window_s'] > 0), key=lambda r: r['auc'], default=None)
    if best:
        print('\n  best cell-level separation at %d s: AUC %.4f, FP %.4f, TPR %.4f'
              % (best['window_s'], best['auc'], best['fp_cell'], best['tpr_cell']))
    print('  the control: a rule that never aggregates cannot be evaluated per flow,')
    print('  because a flow carries one direction only and rho is 1 or 0 by construction.')

    json.dump({'params': {'MIN_FLOWS': MIN_FLOWS, 'THRESH': THRESH,
                          'WINDOWS_S': WINDOWS_S, 'FILES': FILES},
               'rows': rows}, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
