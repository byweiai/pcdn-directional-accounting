"""E12 -- sensitivity of the SIEVE floor.

SIEVE accepts an interval [t, t+L) when the interval ratio clears tau and the
excess inside the interval clears a floor

    sum (S - R)  >  B + r L .

Dividing by L, the floor is a condition on the *mean* excess over the interval:

    mean(S - R)  >  r + B / L .

So the two design parameters are not independent: any (B, r) pair is equivalent
to a single per-window excess threshold e* = r + B/L. This script measures what
that single parameter has to be, on the 300 s panel, for the floor to separate
send-side endpoints from receive-side ones.
"""
import json
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')

MIN_FLOWS = 5
FLOORS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]


def main():
    df = pd.read_csv(os.path.join(DATA, 'e1_panel.csv'))
    df = df[df['n'] >= MIN_FLOWS] if 'n' in df.columns else df
    df['ex'] = (df['S'] - df['R']).clip(lower=0.0) / 1e6      # MB of excess

    per_ip = df.groupby(['ip', 'role'])['ex'].mean().reset_index()
    out = {'n_windows': int(df['win'].nunique()),
           'n_endpoints': int(per_ip.shape[0]),
           'floors': [], 'roles': {}}

    for role, g in per_ip.groupby('role'):
        out['roles'][role] = {'n': int(g.shape[0]),
                              'median': float(g['ex'].median()),
                              'p90': float(g['ex'].quantile(0.90)),
                              'max': float(g['ex'].max())}
        print('%-8s n=%2d  median %8.2f  p90 %8.2f  max %8.2f MB/win'
              % (role, g.shape[0], g['ex'].median(),
                 g['ex'].quantile(0.90), g['ex'].max()))

    for f in FLOORS:
        row = {'floor': f}
        for role in ('client', 'other', 'service'):
            g = per_ip[per_ip['role'] == role]
            if len(g) == 0:
                row[role] = None
                continue
            row[role] = float((g['ex'] > f).mean())
        out['floors'].append(row)
        print('e* = %5.1f MB/win -> subscriber %.3f  other %.3f  service %.3f'
              % (f, row['client'], row['other'], row['service']))

    # the floor that separates the two populations on this panel
    lo = per_ip[per_ip['role'] == 'client']['ex']
    hi = per_ip[per_ip['role'] == 'service']['ex']
    out['separating_floor'] = float(max(lo.max(), 0.0))
    out['service_above_subscriber_max'] = float((hi > lo.max()).mean())
    out['service_median_over_subscriber_max'] = (
        float(hi.median() / lo.max()) if lo.max() > 0 else None)
    out['subscriber_max_excess'] = float(lo.max())
    print('subscriber max %.3f MB/win, service median %.2f -> ratio %s'
          % (lo.max(), hi.median(),
             ('%.1fx' % out['service_median_over_subscriber_max'])
             if out['service_median_over_subscriber_max'] else 'unbounded'))

    # what the two published parameter settings collapse to
    out['collapse'] = []
    for B, r, L in ((10.0, 3.33, 24), (10.0, 3.33, 12), (10.0, 3.33, 48),
                    (0.0, 3.33, 24), (100.0, 3.33, 24)):
        out['collapse'].append({'B': B, 'r': r, 'L': L,
                                'e_star': r + B / L})
        print('B=%6.1f r=%5.2f L=%2d -> e* = %.2f MB/win'
              % (B, r, L, r + B / L))

    with open(os.path.join(DATA, 'e12_floor.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    print('wrote data/e12_floor.json')


if __name__ == '__main__':
    main()
