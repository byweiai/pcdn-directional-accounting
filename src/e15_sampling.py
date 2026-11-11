# -*- coding: utf-8 -*-
"""E15: what happens when the counters are fed sampled flows?

Operational measurement of this kind starts from sampled flow records, not from
a complete packet trace.  The primitive divides two byte counters, so sampling
is unbiased at the *cell* level; what it costs is coverage, because a light
subscriber's five-minute cell may contain no sampled flows at all.  This script
measures both effects on the UNSW capture: for each sampling rate, keep each
flow independently, recompute the endpoint-window ratio, and report

    coverage  - share of full-data cells (>= 5 flows) that still exist
    fp, tpr   - error rates at tau = 0.5 on the cells that survive
    p95, p05  - the two tail statistics the threshold is set against
"""
import glob
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e15_sampling.json')

IDX = {'srcip': 0, 'dstip': 2, 'sbytes': 7, 'dbytes': 8, 'Stime': 28}
NFIELDS = 49
RATES = [1.0, 0.5, 0.2, 0.1, 0.05, 0.01, 0.005, 0.001]
MIN_FLOWS = 5
TAU = 0.5
WINDOW = 300


def load():
    frames = []
    for p in sorted(glob.glob(os.path.join(DATA, 'raw', 'UNSW-NB15_*.csv'))):
        raw = pd.read_csv(p, header=None, names=list(range(NFIELDS)),
                          usecols=sorted(IDX.values()), low_memory=False,
                          encoding='utf-8-sig', na_values=['-', ''])
        frames.append(pd.DataFrame({k: raw[i] for k, i in IDX.items()}))
    df = pd.concat(frames, ignore_index=True)
    for c in ('sbytes', 'dbytes', 'Stime'):
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    df['win'] = ((df['Stime'] - df['Stime'].min()) // WINDOW).astype(int)
    return df


def role(ip):
    if ip.startswith('59.166.'):
        return 'client'
    if ip.startswith('149.171.126.'):
        return 'service'
    return 'other'


def cells(df):
    """One row per (endpoint, window) with the two directional counters.

    A flow A->B carries sbytes emitted by A and dbytes emitted by B, so an
    endpoint's emitted bytes are sbytes when it is the source and dbytes when it
    is the destination.  Both halves have to be summed; taking only the source
    side inverts the ratio for endpoints that mostly receive.
    """
    sent_a = df.groupby(['srcip', 'win'], sort=False)['sbytes'].sum()
    sent_b = df.groupby(['dstip', 'win'], sort=False)['dbytes'].sum()
    recv_a = df.groupby(['srcip', 'win'], sort=False)['dbytes'].sum()
    recv_b = df.groupby(['dstip', 'win'], sort=False)['sbytes'].sum()
    for frame in (sent_a, sent_b, recv_a, recv_b):
        frame.index.names = ['ip', 'win']
    g = pd.concat([sent_a.rename('S1'), sent_b.rename('S2'),
                   recv_a.rename('R1'), recv_b.rename('R2')], axis=1).fillna(0.0)
    g = g.reset_index()
    g['ip'] = g['ip'].astype(str)
    S = g['S1'] + g['S2']
    R = g['R1'] + g['R2']
    g['rho'] = S / np.maximum(1e-9, S + R)
    g['bytes'] = S + R
    g['role'] = g['ip'].map(role)
    return g[['ip', 'win', 'rho', 'bytes', 'role']]


def score(g, ref_keys):
    cli = g.loc[g['role'] == 'client', 'rho']
    srv = g.loc[g['role'] == 'service', 'rho']
    keys = set(zip(g['ip'], g['win']))
    return {
        'coverage': round(len(ref_keys & keys) / max(1, len(ref_keys)), 4),
        'cells': int(len(g)),
        'fp': round(float((cli > TAU).mean()), 4) if len(cli) else None,
        'tpr': round(float((srv > TAU).mean()), 4) if len(srv) else None,
        'client_p95': round(float(np.percentile(cli, 95)), 4) if len(cli) else None,
        'service_p05': round(float(np.percentile(srv, 5)), 4) if len(srv) else None,
    }


def main():
    df = load()
    print('flows', len(df))

    counts = pd.concat([
        df[['srcip', 'win']].rename(columns={'srcip': 'ip'}),
        df[['dstip', 'win']].rename(columns={'dstip': 'ip'}),
    ], ignore_index=True).groupby(['ip', 'win']).size().rename('nflows')
    ref = counts[counts >= MIN_FLOWS].reset_index()
    ref_keys = set(zip(ref['ip'].astype(str), ref['win'].astype(int)))
    print('reference cells', len(ref_keys))

    rng = np.random.default_rng(20261108)
    rows = []
    for p in RATES:
        sub = df if p >= 1.0 else df.loc[rng.random(len(df)) < p]
        g = cells(sub)
        g = g[g['bytes'] > 0]
        g = g.join(counts.rename('n'), on=['ip', 'win'])
        r = score(g, ref_keys)
        r['median_flows_per_cell'] = round(float(g['n'].median()), 2)
        r['rate'] = p
        rows.append(r)
        print('rate %-6.3f cells %7d coverage %.3f fp %s tpr %s p95 %s p05 %s'
              % (p, r['cells'], r['coverage'], r['fp'], r['tpr'],
                 r['client_p95'], r['service_p05']))

    out = {'tau': TAU, 'min_flows_reference': MIN_FLOWS, 'window_s': WINDOW,
           'total_flows': int(len(df)), 'reference_cells': len(ref_keys),
           'rows': rows}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
