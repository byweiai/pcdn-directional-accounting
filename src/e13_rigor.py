# -*- coding: utf-8 -*-
"""E13: how much of the separation is sampling luck?

Three checks that a reviewer will ask for and that cost nothing to report:

  (a) a permutation test on the endpoint-level statistic, because 47 endpoints
      is a small sample and "P(service > client) = 1.0000" is a statement about
      an ordering that could in principle arise by chance;
  (b) bootstrap intervals for the four numbers the paper quotes as headline
      results (subscriber tail, server floor, capture, false alarm);
  (c) a split-half calibration: set the threshold on half the endpoints and
      read out the error rates on the other half, in both directions.  If the
      threshold only works on the endpoints it was set on, the whole criterion
      is a fit to one capture.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e13_rigor.json')

RNG = np.random.default_rng(20261107)


def load():
    ep = pd.read_csv(os.path.join(DATA, 'e1_endpoints.csv'))
    pan = pd.read_csv(os.path.join(DATA, 'e1_panel.csv'))
    return ep, pan


def perm_test(ep, n_perm=20000):
    """Shuffle the role labels; how often does the gap look this large?"""
    rho = ep['rho'].to_numpy()
    is_srv = (ep['role'].to_numpy() == 'service')
    obs = float(np.median(rho[is_srv]) - np.median(rho[~is_srv]))
    # 'other' endpoints are neither role; the test compares the two named ones
    named = (ep['role'].to_numpy() == 'service') | (ep['role'].to_numpy() == 'client')
    rho_n = rho[named]
    k = int(is_srv[named].sum())
    hits = 0
    for _ in range(n_perm):
        idx = RNG.permutation(len(rho_n))
        stat = float(np.median(rho_n[idx[:k]]) - np.median(rho_n[idx[k:]]))
        if stat >= obs:
            hits += 1
    p = (hits + 1.0) / (n_perm + 1.0)
    return {'statistic': obs, 'p_value': p, 'n_named': int(len(rho_n)),
            'n_service': k, 'n_perm': n_perm}


def boot(x, stat, n_boot=4000):
    x = np.asarray(x, dtype=float)
    vals = np.empty(n_boot)
    n = len(x)
    for i in range(n_boot):
        vals[i] = stat(x[RNG.integers(0, n, n)])
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def boot_cluster(pan, stat, n_boot=4000):
    """Resample addresses, not cells (R6).

    Cells from one address are not independent draws, so a cell bootstrap
    understates the interval by the square root of the cells per address. The
    cluster bootstrap resamples the 10 client and 20 service addresses with
    replacement and keeps every cell of a sampled address.
    """
    out = {}
    for role, key, stat in (('client', 'client', lambda v: float(np.percentile(v, 95))),
                            ('service', 'service', lambda v: float(np.percentile(v, 5)))):
        sub = pan.loc[pan['role'] == role]
        ips = sorted(sub['ip'].unique())
        by_ip = {ip: sub.loc[sub['ip'] == ip, 'rho'].to_numpy() for ip in ips}
        vals = []
        for _ in range(n_boot):
            pick = [ips[i] for i in RNG.integers(0, len(ips), len(ips))]
            pooled = np.concatenate([by_ip[p] for p in pick])
            vals.append(stat(pooled))
        out[key] = {'hosts': len(ips), 'ci': [float(np.percentile(vals, 2.5)),
                                              float(np.percentile(vals, 97.5))]}
    # separation: the gap between the subscriber tail and the server floor
    cli_sub = pan.loc[pan['role'] == 'client']
    srv_sub = pan.loc[pan['role'] == 'service']
    cli_ips = sorted(cli_sub['ip'].unique())
    srv_ips = sorted(srv_sub['ip'].unique())
    cli_by = {ip: cli_sub.loc[cli_sub['ip'] == ip, 'rho'].to_numpy() for ip in cli_ips}
    srv_by = {ip: srv_sub.loc[srv_sub['ip'] == ip, 'rho'].to_numpy() for ip in srv_ips}
    gaps = []
    for _ in range(n_boot):
        c = np.concatenate([cli_by[cli_ips[i]] for i in RNG.integers(0, len(cli_ips), len(cli_ips))])
        s = np.concatenate([srv_by[srv_ips[i]] for i in RNG.integers(0, len(srv_ips), len(srv_ips))])
        gaps.append(float(np.percentile(s, 5) - np.percentile(c, 95)))
    out['gap'] = {'estimate': float(np.percentile(srv_sub['rho'], 5)
                                    - np.percentile(cli_sub['rho'], 95)),
                  'ci': [float(np.percentile(gaps, 2.5)), float(np.percentile(gaps, 97.5))],
                  'share_positive': float(np.mean(np.array(gaps) > 0)),
                  'n_boot': n_boot}
    out['rule_of_three_hosts'] = 3.0 / (len(cli_ips) + len(srv_ips))
    out['rule_of_three_cells'] = 3.0 / 1420.0
    return out


def bootstrap(pan):
    cli = pan.loc[pan['role'] == 'client', 'rho'].to_numpy()
    srv = pan.loc[pan['role'] == 'service', 'rho'].to_numpy()
    out = {
        'n_boot': 4000,
        'n_client_cells': int(len(cli)),
        'n_service_cells': int(len(srv)),
        'client_p95': float(np.percentile(cli, 95)),
        'client_p95_ci': boot(cli, lambda v: float(np.percentile(v, 95))),
        'service_p05': float(np.percentile(srv, 5)),
        'service_p05_ci': boot(srv, lambda v: float(np.percentile(v, 5))),
        'tpr_at_half': float((srv > 0.5).mean()),
        'tpr_at_half_ci': boot(srv, lambda v: float((v > 0.5).mean())),
        'fp_at_half': float((cli > 0.5).mean()),
        'fp_at_half_ci': boot(cli, lambda v: float((v > 0.5).mean())),
        'host_level': boot_cluster(pan, lambda v: float(np.percentile(v, 95))),
    }
    return out


def split_half(pan):
    """Calibrate on one half of the endpoints, read out on the other."""
    rows = []
    for direction in (0, 1):
        cli = sorted(pan.loc[pan['role'] == 'client', 'ip'].unique())
        srv = sorted(pan.loc[pan['role'] == 'service', 'ip'].unique())
        cal_c = set(cli[direction::2])
        cal_s = set(srv[direction::2])
        pan['_cal'] = pan['ip'].isin(cal_c) | pan['ip'].isin(cal_s)
        # threshold: the tightest value with zero false alarm on the calibration half
        cal = pan.loc[pan['_cal']]
        tau = 0.5
        for cand in np.arange(0.10, 0.951, 0.01):
            fp = ((cal['role'] == 'client') & (cal['rho'] > cand)).mean()
            if fp == 0.0:
                tau = float(cand)
                break
        ev = pan.loc[~pan['_cal']]
        ev_c = ev.loc[ev['role'] == 'client', 'rho'].to_numpy()
        ev_s = ev.loc[ev['role'] == 'service', 'rho'].to_numpy()
        fp = float((ev_c > tau).mean()) if len(ev_c) else float('nan')
        tp = float((ev_s > tau).mean()) if len(ev_s) else float('nan')
        rows.append({'direction': direction, 'tau_calibrated': tau,
                     'n_cal_client': len(cal_c), 'n_cal_service': len(cal_s),
                     'fp_held_out': fp, 'tpr_held_out': tp,
                     'n_eval_client_cells': int(len(ev_c)),
                     'n_eval_service_cells': int(len(ev_s))})
    pan.drop(columns=['_cal'], inplace=True)
    return rows


def main():
    ep, pan = load()
    res = {
        'permutation': perm_test(ep),
        'bootstrap': bootstrap(pan),
        'split_half': split_half(pan),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
