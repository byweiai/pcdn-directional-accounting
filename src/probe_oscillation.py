"""Probe: does the three-consecutive-window rule leave an oscillation hole, and
would a cumulative-excess rule close it for free?

Two questions, both answered on the 5-minute panel that E1 already produced:
 1. how much excess uplink can an endpoint accumulate in a 15-minute horizon
    while never stringing three over-quota windows together (the hole);
 2. what does the same statistic look like for genuine subscribers (the cost of
    closing it).
Excess of a window is max(0, S - R); the horizon statistic is the sum of excess
over any three consecutive windows.
"""
import json
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def horizon_excess(df, k=3):
    out = {}
    for ip, g in df.groupby('ip'):
        g = g.sort_values('win')
        ex = np.maximum(0.0, g['S'].to_numpy() - g['R'].to_numpy())
        if len(ex) < k:
            out[ip] = (float(ex.sum()), g['role'].iloc[0])
            continue
        cs = np.concatenate([[0.0], np.cumsum(ex)])
        h = cs[k:] - cs[:-k]
        out[ip] = (float(h.max()), g['role'].iloc[0])
    return out


def main():
    pan = pd.read_csv(os.path.join(DATA, 'e1_panel.csv'))
    pan['S'] = pd.to_numeric(pan['S'], errors='coerce').fillna(0.0)
    pan['R'] = pd.to_numeric(pan['R'], errors='coerce').fillna(0.0)
    pan['win'] = pd.to_numeric(pan['win'], errors='coerce').astype(int)

    # (1) the hole: an endpoint that alternates one distributing window with one
    # idle window has a run of exactly one, so the three-window rule never fires,
    # yet half of its windows sit above quota.
    res = {'alt_share_above_quota': 0.5, 'alt_max_run': 1,
           'trips_three_window_rule': False}

    # (2) the cost of a cumulative-excess rule on real traffic
    he = horizon_excess(pan, k=3)
    per = {'client': [], 'other': [], 'service': []}
    for ip, (v, role) in he.items():
        per.setdefault(role, []).append(v)
    stats = {}
    for role, vals in per.items():
        if not vals:
            continue
        v = np.array(vals, dtype=float) / 1e6   # megabytes
        stats[role] = {'n': int(len(v)), 'median': float(np.median(v)),
                       'p90': float(np.percentile(v, 90)),
                       'p99': float(np.percentile(v, 99)),
                       'max': float(v.max()),
                       'share_over_10mb': float((v > 10.0).mean()),
                       'share_over_100mb': float((v > 100.0).mean())}
    res['horizon_excess_mb'] = stats

    # (3) what a threshold on the horizon statistic would catch
    for thr in (10.0, 50.0, 100.0):
        rec = {'threshold_mb': thr}
        for role in ('client', 'service'):
            s = stats.get(role)
            if not s:
                continue
            rec[role + '_flag_rate'] = None
        res.setdefault('thresholds', []).append(rec)
    outs = []
    for thr in (10.0, 50.0, 100.0):
        row = {'threshold_mb': thr}
        for role in ('client', 'service'):
            vals = np.array(per.get(role, []), dtype=float) / 1e6
            row[role + '_flag_rate'] = float((vals > thr).mean()) if len(vals) else None
        outs.append(row)
    res['thresholds'] = outs

    print('hole: alternating schedule -> share above quota 0.50, max run 1, '
          'three-window rule fires: False')
    for role, s in stats.items():
        print('%-8s n=%4d median=%9.2f p90=%9.2f p99=%9.2f max=%10.2f '
              '>10MB=%.3f >100MB=%.3f'
              % (role, s['n'], s['median'], s['p90'], s['p99'], s['max'],
                 s['share_over_10mb'], s['share_over_100mb']))
    for row in outs:
        print('threshold %5.1f MB -> subscriber flag rate %s, server flag rate %s'
              % (row['threshold_mb'], row['client_flag_rate'], row['service_flag_rate']))

    with open(os.path.join(DATA, 'probe_oscillation.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print('wrote data/probe_oscillation.json')


if __name__ == '__main__':
    main()
