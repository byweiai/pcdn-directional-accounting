"""Probe: does rho survive sampled flow records?

Reads one UNSW-NB15 raw CSV, keeps a random fraction of the flow records, and
recomputes the endpoint direction ratio with the same accounting as E1:
    sent = sum(sbytes | srcip) + sum(dbytes | dstip)
    recv = sum(dbytes | srcip) + sum(sbytes | dstip)
Then reports how the subscriber p90, the server median and the two error rates
at the quota threshold move as the sampling rate falls.

Purpose: decide whether a sampling-tolerant estimator is a real problem worth a
section, or a non-issue.
"""
import json
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
RAW = os.path.join(DATA, 'raw')

IDX = dict(src=0, dst=2, sb=7, db=8)
CLIENT = '59.166.'
SERVICE = '149.171.126.'

RATES = [1.0, 0.5, 0.25, 0.1, 0.05, 0.01]
MIN_FLOWS = 5


def role(ip):
    if ip.startswith(CLIENT):
        return 'client'
    if ip.startswith(SERVICE):
        return 'service'
    return 'other'


def main():
    path = os.path.join(RAW, 'UNSW-NB15_1.csv')
    df = pd.read_csv(path, header=None, names=range(49), encoding='utf-8-sig',
                     usecols=[IDX['src'], IDX['dst'], IDX['sb'], IDX['db']],
                     low_memory=False)
    df.columns = ['src', 'dst', 'sb', 'db']
    df = df.dropna(subset=['src', 'dst'])
    for c in ('sb', 'db'):
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    n = len(df)
    src = df['src'].to_numpy()
    dst = df['dst'].to_numpy()
    sb = df['sb'].to_numpy(dtype=float)
    db = df['db'].to_numpy(dtype=float)

    rng = np.random.default_rng(20261107)
    out = {'file': os.path.basename(path), 'flows_in_file': int(n),
           'min_flows_per_endpoint': MIN_FLOWS, 'rates': []}

    for p in RATES:
        keep = np.ones(n, dtype=bool) if p >= 1.0 else (rng.random(n) < p)
        s = {}
        for a, b, x, y in zip(src[keep], dst[keep], sb[keep], db[keep]):
            sa = s.get(a)
            if sa is None:
                sa = s[a] = [0.0, 0.0, 0]
            sa[0] += x
            sa[1] += y
            sa[2] += 1
            sb_ = s.get(b)
            if sb_ is None:
                sb_ = s[b] = [0.0, 0.0, 0]
            sb_[0] += y
            sb_[1] += x
            sb_[2] += 1

        rows = []
        for ip, (sent, recv, nf) in s.items():
            if nf < MIN_FLOWS or sent + recv <= 0:
                continue
            rows.append((ip, sent / (sent + recv), role(ip), nf))
        if not rows:
            continue
        rho = np.array([r[1] for r in rows])
        rl = np.array([r[2] for r in rows])
        nf = np.array([r[3] for r in rows])
        cli = rho[rl == 'client']
        svc = rho[rl == 'service']
        tau = 0.5
        rec = {
            'rate': p,
            'flows_kept': int(keep.sum()),
            'endpoints': int(len(rows)),
            'client_n': int(len(cli)),
            'service_n': int(len(svc)),
            'median_flows_per_endpoint': float(np.median(nf)),
            'client_p90': float(np.percentile(cli, 90)) if len(cli) else None,
            'client_median': float(np.median(cli)) if len(cli) else None,
            'service_median': float(np.median(svc)) if len(svc) else None,
            'client_max': float(cli.max()) if len(cli) else None,
            'service_min': float(svc.min()) if len(svc) else None,
            'false_alarm': float((cli > tau).mean()) if len(cli) else None,
            'capture': float((svc > tau).mean()) if len(svc) else None,
        }
        out['rates'].append(rec)
        print('p=%.2f flows=%7d endpoints=%4d client_n=%3d svc_n=%3d '
              'cli_p90=%.4f svc_med=%.4f cli_max=%.4f FA=%.3f cap=%.3f'
              % (p, rec['flows_kept'], rec['endpoints'], rec['client_n'],
                 rec['service_n'], rec['client_p90'] or -1,
                 rec['service_median'] or -1, rec['client_max'] or -1,
                 rec['false_alarm'] or -1, rec['capture'] or -1))

    with open(os.path.join(DATA, 'probe_sampling.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print('wrote data/probe_sampling.json')


if __name__ == '__main__':
    main()
