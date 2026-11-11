# -*- coding: utf-8 -*-
"""E1 (micro): is endpoint-level directional asymmetry measurable on real flows?

Two questions, both answerable on UNSW-NB15's original record files, which give
per-flow src/dst addresses plus sbytes/dbytes:

  Q1.1  At the level of a single flow, does the directional ratio already
        separate servers from clients? (If yes, no aggregation is needed and the
        measurement story is trivial; if no, the paper needs to say why
        aggregation is the right estimator.)
  Q1.2  After aggregating over an endpoint's flows, does the ratio separate the
        two roles cleanly, and how heavy is the tail?

The capture has a known two-sided structure: 149.171.126.0/24 is the UNSW
service side, 59.166.0.0/16 the client side. We use that only as ground truth
for *validating* the estimator, never as an input to it.
"""
import os, sys, json, glob
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e1_unsw.json')

# The published record files carry 49 positional fields, not the 47 of the
# feature-vector variant: two extra ct_* columns sit before attack_cat, and the
# label is last. Positions below were verified against the first rows.
IDX = {'srcip': 0, 'sport': 1, 'dstip': 2, 'dsport': 3, 'proto': 4,
       'dur': 6, 'sbytes': 7, 'dbytes': 8, 'Spkts': 16, 'Dpkts': 17,
       'smeansz': 22, 'dmeansz': 23, 'Sjit': 26, 'Djit': 27,
       'Stime': 28, 'Ltime': 29, 'attack_cat': 47, 'Label': 48}
NFIELDS = 49


def load(paths):
    frames = []
    keep = sorted(IDX.values())
    for p in paths:
        print('  reading', os.path.basename(p))
        raw = pd.read_csv(p, header=None, names=list(range(NFIELDS)),
                          usecols=keep, low_memory=False,
                          encoding='utf-8-sig', na_values=['-', ''])
        df = pd.DataFrame({k: raw[i] for k, i in IDX.items()})
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    return df


def main():
    files = sorted(glob.glob(os.path.join(DATA, 'raw', 'UNSW-NB15_*.csv')))
    files = [f for f in files if not f.endswith('.part')]
    print('files:', [os.path.basename(f) for f in files])
    df = load(files)
    print('flows:', len(df))

    for c in ('sbytes', 'dbytes', 'Spkts', 'Dpkts', 'dur'):
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    # ---- Q1.1 single-flow ratio -------------------------------------------
    tot = df['sbytes'] + df['dbytes']
    ok = tot > 0
    rho_flow = np.where(ok, df['sbytes'] / tot.replace(0, np.nan), np.nan)
    rho_flow = rho_flow[~np.isnan(rho_flow)]
    qs = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    flow_stats = {('p%d' % q): float(np.percentile(rho_flow, q)) for q in qs}
    # share of flows whose direction is ambiguous (0.4 < rho < 0.6)
    amb = float(np.mean((rho_flow > 0.4) & (rho_flow < 0.6)))
    print('flow-level rho (sent share): median=%.3f  frac in (0.4,0.6)=%.3f'
          % (flow_stats['p50'], amb))

    # ---- endpoint aggregation --------------------------------------------
    # A flow A->B carries sbytes emitted by A and dbytes emitted by B. So an
    # endpoint's *sent* volume is its sbytes when it is the source plus its
    # dbytes when it is the destination; the converse gives *received*.
    sent = (df.groupby('srcip')['sbytes'].sum()
            .add(df.groupby('dstip')['dbytes'].sum(), fill_value=0.0))
    recv = (df.groupby('srcip')['dbytes'].sum()
            .add(df.groupby('dstip')['sbytes'].sum(), fill_value=0.0))
    nflow = df.groupby('srcip').size().add(df.groupby('dstip').size(), fill_value=0)
    eps = pd.DataFrame({'S': sent, 'R': recv, 'nflows': nflow}).fillna(0.0)
    eps = eps[eps['nflows'] >= 5]
    tot_ep = eps['S'] + eps['R']
    eps['rho'] = np.where(tot_ep > 0, eps['S'] / tot_ep.replace(0, np.nan), np.nan)
    eps = eps.dropna(subset=['rho'])
    print('endpoints with >=5 flows:', len(eps))

    # role ground truth (validation only)
    def role(ip):
        ip = str(ip)
        if ip.startswith('149.171.126.'):
            return 'service'
        if ip.startswith('59.166.'):
            return 'client'
        return 'other'
    eps['role'] = [role(i) for i in eps.index]
    print(eps['role'].value_counts().to_dict())

    grp = eps.groupby('role')['rho']
    role_stats = {k: {'n': int(v.size), 'median': float(v.median()),
                      'p10': float(v.quantile(.10)), 'p90': float(v.quantile(.90))}
                  for k, v in grp}
    print('rho by role:', json.dumps(role_stats, indent=1))

    # separation: probability that a random service endpoint has rho above a
    # random client endpoint (AUC without a classifier)
    a = eps.loc[eps['role'] == 'service', 'rho'].values
    b = eps.loc[eps['role'] == 'client', 'rho'].values
    if len(a) and len(b):
        gt = (a[:, None] > b[None, :]).mean() + 0.5 * (a[:, None] == b[None, :]).mean()
    else:
        gt = float('nan')
    print('P(rho_service > rho_client) = %.4f' % gt)

    # ---- windowed panel: the granularity a real deployment meters at ------
    df['t0'] = pd.to_numeric(df['Stime'], errors='coerce')
    df = df[df['t0'].notna() & (df['t0'] > 1e9)]
    WIN = 300  # 5 minutes
    df['win'] = (df['t0'] // WIN).astype('int64')
    print('time span: %.2f h over %d windows'
          % ((df['t0'].max() - df['t0'].min()) / 3600.0, df['win'].nunique()))

    def agg_win(dframe, ipcol, bytecol):
        g = dframe.groupby(['win', ipcol])[bytecol].sum()
        g.index.names = ['win', 'ip']
        return g

    s_w = (agg_win(df, 'srcip', 'sbytes').add(agg_win(df, 'dstip', 'dbytes'), fill_value=0.0)
           .rename('S'))
    r_w = (agg_win(df, 'srcip', 'dbytes').add(agg_win(df, 'dstip', 'sbytes'), fill_value=0.0)
           .rename('R'))
    panel = pd.concat([s_w, r_w], axis=1).fillna(0.0).reset_index()
    panel['role'] = [role(i) for i in panel['ip']]
    panel = panel[(panel['S'] + panel['R']) > 0]
    panel['rho'] = panel['S'] / (panel['S'] + panel['R'])
    print('panel cells:', len(panel), panel['role'].value_counts().to_dict())
    pan_stats = {k: {'n': int(v.size), 'median': float(v['rho'].median()),
                     'p10': float(v['rho'].quantile(.10)), 'p90': float(v['rho'].quantile(.90))}
                 for k, v in panel.groupby('role')}
    print('panel rho by role:', json.dumps(pan_stats, indent=1))

    # how many client cells would a rho_0 = 1 quota wrongly flag?
    for r0 in (1.0, 3.0, 9.0):
        cli = panel.loc[panel['role'] == 'client', 'rho']
        srv = panel.loc[panel['role'] == 'service', 'rho']
        fpr = float((cli > r0 / (1 + r0)).mean()) if len(cli) else float('nan')
        tpr = float((srv > r0 / (1 + r0)).mean()) if len(srv) else float('nan')
        print('  quota rho<=%.1f -> flag thr %.3f: client false-flag %.3f, service caught %.3f'
              % (r0, r0 / (1 + r0), fpr, tpr))

    # how much does each endpoint move, i.e. heavy tail of traffic
    eps_sorted = eps.sort_values('rho')
    print('\nlowest rho:')
    for ip, row in eps_sorted.head(5).iterrows():
        print('   %-16s rho=%.4f S=%.1fMB R=%.1fMB flows=%d %s'
              % (ip, row['rho'], row['S'] / 1e6, row['R'] / 1e6, row['nflows'], row['role']))
    print('highest rho:')
    for ip, row in eps_sorted.tail(5).iterrows():
        print('   %-16s rho=%.4f S=%.1fMB R=%.1fMB flows=%d %s'
              % (ip, row['rho'], row['S'] / 1e6, row['R'] / 1e6, row['nflows'], row['role']))

    # ---- does aggregation matter? bootstrap single-flow estimator ---------
    # For endpoints that both send and receive, compare per-flow median ratio
    # with the byte-weighted aggregate. If they disagree, aggregation is not a
    # cosmetic choice.
    both = eps[(eps['S'] > 0) & (eps['R'] > 0)]
    out = {
        'n_flows': int(len(df)),
        'n_endpoints_ge5': int(len(eps)),
        'flow_rho_percentiles': flow_stats,
        'flow_rho_ambiguous_share': amb,
        'role_stats': role_stats,
        'auc_service_vs_client': float(gt),
        'n_both_directions': int(len(both)),
        'panel_cells': int(len(panel)),
        'panel_role_stats': pan_stats,
        'attack_cat_counts': df['attack_cat'].fillna('Normal').value_counts().head(12).to_dict(),
        'label_counts': df['Label'].value_counts().to_dict(),
        'rho_quantiles_endpoints': {('p%d' % q): float(eps['rho'].quantile(q / 100))
                                    for q in [1, 5, 10, 25, 50, 75, 90, 95, 99]},
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    eps.reset_index().rename(columns={'index': 'ip'}).to_csv(
        os.path.join(DATA, 'e1_endpoints.csv'), index=False)
    panel.to_csv(os.path.join(DATA, 'e1_panel.csv'), index=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
