"""E18: adversarial dual use.

E16 laid a distribution load on a household's own bytes but let the node choose
its own duty cycle.  A node that knows the mechanism does the opposite: it ships
whenever the household is online, so its sessions look exactly like the
household's, and it buys itself downlink ("wash") to dilute the ratio.

Two parameters:
  m     shipped volume per active window, as a multiple of what the line pulls
  wash  genuine downlink added per unit shipped

The question is not whether such a node exists but what the cheapest escape
costs, and whether shape mimicry buys anything at all.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'data', 'e18_adaptive.json')

COLS = ['srcip', 'dstip', 'sbytes', 'dbytes', 'Stime']
WINDOW = 300
INTERVAL = 24
TAU = 0.5
E_STAR_MB = 3.75
MIN_FLOWS = 5

M_GRID = [1, 2, 5, 10, 20, 40]
WASH_GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]


def load():
    frames = []
    for i in (1, 3, 4):
        p = os.path.join(RAW, 'UNSW-NB15_%d.csv' % i)
        df = pd.read_csv(p, names=range(49), usecols=[0, 2, 7, 8, 28],
                         encoding='utf-8-sig', header=None)
        df.columns = COLS
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=COLS)
    df = df[df['Stime'] > 0]
    df['w'] = ((df['Stime'] - df['Stime'].min()) // WINDOW).astype(int)
    return df


def subscriber_cells(df):
    """Per-window sent/recv for the subscriber lines.

    Lines are the ones the topology fixes as subscribers (59.166.0.0/16), the
    same convention as every other experiment, so the null band here is the
    one quoted in Section V and not a statistic re-estimated on this grid.
    """
    fwd = df[['srcip', 'w', 'sbytes', 'dbytes']].rename(
        columns={'srcip': 'ip', 'sbytes': 's_out', 'dbytes': 'r_out'})
    rev = df[['dstip', 'w', 'sbytes', 'dbytes']].rename(
        columns={'dstip': 'ip', 'dbytes': 's_out', 'sbytes': 'r_out'})
    both = pd.concat([fwd, rev], ignore_index=True)
    g = both.groupby(['ip', 'w'], as_index=False).agg(
        sent=('s_out', 'sum'), recv=('r_out', 'sum'), n=('s_out', 'size'))
    g = g[g['n'] >= MIN_FLOWS]

    subs = g[g['ip'].str.startswith('59.166.')]
    tot = subs.groupby('ip', as_index=False).agg(S=('sent', 'sum'),
                                                 R=('recv', 'sum'))
    tot['rho'] = tot['S'] / (tot['S'] + tot['R'])
    return subs, tot


def decide(sent, recv, idx):
    """Line-level decision of the three rules on one synthetic line."""
    rho = sent / np.maximum(sent + recv, 1e-9)
    over = rho[idx] > TAU

    # single window / three consecutive windows, anywhere in the trace
    hit_window = bool(over.any())
    run = 0
    hit_three = False
    for v in over:
        run = run + 1 if v else 0
        if run >= 3:
            hit_three = True
            break

    # SIEVE: ratio and excess over an interval of INTERVAL windows
    hit_sieve = False
    n = len(sent)
    for a in range(0, max(n - INTERVAL + 1, 1), INTERVAL):
        b = a + INTERVAL
        if b > n:
            break
        s = sent[a:b].sum()
        r = recv[a:b].sum()
        if s + r <= 0:
            continue
        if s / (s + r) > TAU and (s - r) / 1e6 > E_STAR_MB * INTERVAL:
            hit_sieve = True
            break
    return hit_window, hit_three, hit_sieve


def main():
    df = load()
    cells, subs = subscriber_cells(df)

    per_line = []
    for ip, g in cells.groupby('ip'):
        g = g.sort_values('w')
        w = g['w'].to_numpy()
        span = int(w.max()) + 1
        own_s = np.zeros(span)
        own_r = np.zeros(span)
        np.add.at(own_s, w, g['sent'].to_numpy())
        np.add.at(own_r, w, g['recv'].to_numpy())
        per_line.append((ip, own_s, own_r))

    cells_per_line = [int((s + r > 0).sum()) for _, s, r in per_line]
    true_cells = int((cells['sent'] + cells['recv'] > 0).sum())

    grid = {}
    escape = {}
    for m in M_GRID:
        rows = []
        for wash in WASH_GRID:
            hw = ht = hs = 0
            bw = []
            for ip, own_s, own_r in per_line:
                active = own_r > 0                     # mimic the household
                ship = m * own_r * active
                sent = own_s + ship
                recv = own_r + wash * ship
                a, b, c = decide(sent, recv, active)
                hw += a
                ht += b
                hs += c
                bw.append((ship.sum() / max(own_r.sum(), 1.0)))
            n = len(per_line)
            rows.append({'wash': wash,
                         'window': hw / n, 'three': ht / n, 'sieve': hs / n,
                         'push_pct_med': float(np.median(bw))})
        grid[str(m)] = rows
        esc_w = next((r['wash'] for r in rows if r['three'] < 0.5), None)
        esc_s = next((r['wash'] for r in rows if r['sieve'] < 0.5), None)
        escape[str(m)] = {'wash_to_escape_three': esc_w,
                          'wash_to_escape_sieve': esc_s}

    out = {
        'params': {'WINDOW': WINDOW, 'INTERVAL': INTERVAL, 'TAU': TAU,
                   'E_STAR_MB': E_STAR_MB, 'MIN_FLOWS': MIN_FLOWS,
                   'M_GRID': M_GRID, 'WASH_GRID': WASH_GRID},
        'lines': len(per_line),
        'subscriber_cells': true_cells,
        'null_band': {
            'median': float(np.median(subs['rho'])),
            'p95': float(np.percentile(subs['rho'], 95)),
        },
        'grid': grid,
        'escape': escape,
    }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)

    print('lines %d  subscriber cells %d' % (out['lines'], true_cells))
    print('null band median %.4f  p95 %.4f' % (out['null_band']['median'],
                                               out['null_band']['p95']))
    print('%-5s %-6s %-7s %-7s %-7s %-8s' % ('m', 'wash', 'window', 'three',
                                             'sieve', 'push%'))
    for m in M_GRID:
        for r in grid[str(m)]:
            print('%-5d %-6.2f %-7.3f %-7.3f %-7.3f %-8.1f'
                  % (m, r['wash'], r['window'], r['three'], r['sieve'],
                     100 * r['push_pct_med']))
    print('escape (wash at which the rule stops deciding against the line):')
    for m in M_GRID:
        e = escape[str(m)]
        print('  m=%-3d three needs wash=%-5s  sieve needs wash=%s'
              % (m, e['wash_to_escape_three'], e['wash_to_escape_sieve']))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
