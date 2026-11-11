# -*- coding: utf-8 -*-
"""E16: the line that is both a customer and a distributor.

A PCDN node is not a kind of endpoint. The same household line watches video and
serves chunks, so "is this endpoint a node" has no answer for the interesting
cases, and a rule that needs an answer inherits the problem. This experiment
drops the label and asks what each rule can still see.

A real subscriber line's own bytes come from the corpus (client cells, 300 s).
A distribution load is laid on top, shaped by three parameters:
  m      node uplink per window, as a multiple of the household's own download
  run    how many consecutive windows a session lasts
  duty   the share of windows the node is running at all
so the monthly excess a line ships is roughly m * duty * (its own consumption).

Three rules are compared on the same synthetic line:
  window  rho > tau in a single window
  three   rho > tau in three consecutive windows (the rule the paper replaces)
  sieve   some interval of 3 to 24 windows has both rho > tau and signed excess
          above budget + rate * L (Section V-G, and E12's collapse of B and r)

The claim under test: the two window-based rules are defeated by *shape* (lower
m, or shorter runs), and SIEVE is outrun only by carrying volume. What SIEVE
guarantees under reordering is narrower: a horizon that exceeds both the quota
and the floor is still an interval of the same totals, so it still fires.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
RAW = os.path.join(DATA, 'raw')
OUT = os.path.join(DATA, 'e16_dualuse.json')

FILES = ['UNSW-NB15_1.csv', 'UNSW-NB15_2.csv', 'UNSW-NB15_3.csv', 'UNSW-NB15_4.csv']
WINDOW = 300
MIN_FLOWS = 5
TAU = 0.5
E_STAR_MB = 3.75          # per window, from E12's collapse of B and r
INTERVAL = 24             # longest interval the rule reads (2 h at 300 s)
BUDGET_MB = 10.0          # fixed part of the interval floor, E12
RATE_MB = 10.0 / 3.0      # per-window part of the interval floor, E12
MIN_INTERVAL = 3          # shortest interval the rule reads
INTENSITY = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
RUN = [1, 2, 3, 6, 12]
DUTY = [1.0, 0.5, 0.2, 0.1]
SEEDS = [1, 2, 3, 4, 5]
CONTROL_SHARE = 0.02
WINDOWS_PER_MONTH = 30 * 24 * 3600 / WINDOW


def load():
    frames = []
    for f in FILES:
        p = os.path.join(RAW, f)
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, header=None, names=range(49),
                        usecols=[0, 2, 7, 8, 28],
                        encoding='utf-8-sig', low_memory=False)
        d.columns = ['srcip', 'dstip', 'sbytes', 'dbytes', 'Stime']
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    for c in ('sbytes', 'dbytes', 'Stime'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['srcip', 'dstip', 'sbytes', 'dbytes', 'Stime'])
    df['sbytes'] = df['sbytes'].astype(np.int64)
    df['dbytes'] = df['dbytes'].astype(np.int64)
    return df.reset_index(drop=True)


def cells(df, window):
    long = pd.concat([
        pd.DataFrame({'ip': df['srcip'], 'sent': df['sbytes'], 'recv': df['dbytes'],
                      't': df['Stime']}),
        pd.DataFrame({'ip': df['dstip'], 'sent': df['dbytes'], 'recv': df['sbytes'],
                      't': df['Stime']}),
    ], ignore_index=True)
    long['w'] = (long['t'] // window).astype(np.int64)
    g = long.groupby(['ip', 'w'], sort=False).agg(
        sent=('sent', 'sum'), recv=('recv', 'sum'), n=('sent', 'size')).reset_index()
    g = g[(g['n'] >= MIN_FLOWS) & ((g['sent'] + g['recv']) > 0)].copy()
    return g


def blocks(n, run, duty, rng):
    """On-mask of contiguous runs of `run` windows covering about `duty`."""
    on = np.zeros(n, bool)
    if duty >= 1.0:
        return np.ones(n, bool)
    period = max(run, int(round(run / max(duty, 1e-9))))
    phase = int(rng.integers(0, period))
    start = (phase - run) % period
    for s in range(start, n, period):
        on[max(0, s):min(n, s + run)] = True
    return on


def _win_sum(x, L):
    """Sum of every run of L consecutive entries, without looping over runs."""
    cs = np.concatenate(([0.0], np.cumsum(x, dtype=float)))
    return cs[L:] - cs[:-L]


def rules(sent, recv, seen, tau=TAU):
    rho = sent / np.maximum(sent + recv, 1e-9)
    flags = (rho > tau) & seen
    win = float(flags[seen].mean()) if seen.any() else float('nan')
    # three consecutive windows above quota
    three = np.zeros_like(flags)
    for k in range(2, len(flags)):
        three[k] = flags[k] and flags[k - 1] and flags[k - 2]
    tri = float(three[seen].mean()) if seen.any() else float('nan')
    # SIEVE: the interval ratio and the interval excess, both, as in Section V-G.
    # Signed excess, every interval of min_int..max_int windows, floor B + rate*L.
    excess = (sent - recv) * seen
    n = len(excess)
    n_int = 0
    hit = 0
    for L in range(MIN_INTERVAL, min(INTERVAL, n) + 1):
        ss = _win_sum(sent, L)
        sr = _win_sum(recv, L)
        ee = _win_sum(excess, L) / 1e6
        ratio = ss / np.maximum(ss + sr, 1e-9)
        ok = (ratio > tau) & (ee > BUDGET_MB + RATE_MB * L)
        n_int += ok.size
        hit += int(ok.sum())
    sieve = hit / n_int if n_int else float('nan')
    # line-level decision: did this rule ever fire for this line
    any_hit = (int(flags.any()), int(three.any()), int(hit > 0))
    return win, tri, sieve, any_hit


def main():
    print('== E16: a line that consumes and distributes at once ==')
    df = load()
    g = cells(df, WINDOW)
    cli = g[(g['sent'] + g['recv']) > 0].copy()
    cli['ip_role'] = cli['ip'].map(
        lambda s: 'client' if s.startswith('59.166.') else
        ('service' if s.startswith('149.171.126.') else 'other'))
    sub = cli[cli['ip_role'] == 'client']
    own_rho = (sub['sent'] / (sub['sent'] + sub['recv'])).values
    band = np.percentile(own_rho, [5, 95])
    c_med = float(np.median(sub['recv'].values))
    print('  subscriber null: median %.4f, p95 %.4f, band [%.3f, %.3f]'
          % (np.median(own_rho), band[1], band[0], band[1]))
    print('  median household download %.1f MB per window = %.0f GB per month'
          % (c_med / 1e6, c_med * WINDOWS_PER_MONTH / 1e9))

    w0, w1 = int(g['w'].min()), int(g['w'].max())
    grid = np.arange(w0, w1 + 1)
    lines = {}
    for ip, s in sub.groupby('ip'):
        s = s.set_index('w').reindex(grid)
        lines[ip] = (s['sent'].fillna(0.0).values, s['recv'].fillna(0.0).values,
                     s['n'].fillna(0).values > 0)

    rows = []
    for m in INTENSITY:
        for run in RUN:
            for duty in DUTY:
                acc = []
                for seed in SEEDS:
                    rng = np.random.default_rng(hash((m, run, duty, seed)) % (2 ** 31))
                    for ip, (own_s, own_r, seen) in lines.items():
                        n = len(grid)
                        on = blocks(n, run, duty, rng) & seen
                        if not on.any():
                            continue
                        push = m * own_r * on
                        sent = own_s + push
                        recv = own_r + CONTROL_SHARE * push
                        w_, t_, s_, hits = rules(sent, recv, seen)
                        # volume the node ships, as a share of what the line pulls
                        pct = 100.0 * float(push.sum()) / max(1.0, float(own_r.sum()))
                        acc.append((w_, t_, s_, hits[0], hits[1], hits[2], pct))
                if not acc:
                    continue
                a = np.array(acc, dtype=float)
                rows.append({
                    'intensity': m, 'run': run, 'duty': duty,
                    'window': float(np.nanmean(a[:, 0])),
                    'three': float(np.nanmean(a[:, 1])),
                    'sieve': float(np.nanmean(a[:, 2])),
                    'hit_window': float(np.nanmean(a[:, 3])),
                    'hit_three': float(np.nanmean(a[:, 4])),
                    'hit_sieve': float(np.nanmean(a[:, 5])),
                    'push_pct': float(np.nanmean(a[:, 6])),
                })

    # compact printout: the three rules at the most evasive duty, per (m, run)
    print('\n  duty 0.10, the shape an evader would choose')
    print('  %5s %4s | %7s %7s %7s | %7s %7s' %
          ('m', 'run', 'window', 'three', 'sieve', 'hit w/t/s', 'push%'))
    for r in rows:
        if abs(r['duty'] - 0.10) < 1e-9:
            print('  %5.2f %4d | %7.3f %7.3f %7.3f | %.2f/%.2f/%.2f | %6.1f'
                  % (r['intensity'], r['run'], r['window'], r['three'],
                     r['sieve'], r['hit_window'], r['hit_three'], r['hit_sieve'],
                     r['push_pct']))

    def worst(rule):
        c = [r for r in rows if r['hit_' + rule] < 0.5]
        if not c:
            return None
        return max(c, key=lambda r: r['push_pct'])

    print('\n  largest shipped volume that still escapes a line-level decision')
    for rule in ('window', 'three', 'sieve'):
        w = worst(rule)
        print('  %-7s %s' % (rule, 'nothing escapes' if w is None else
                             '%.1f%% of consumption at m=%.2f run=%d duty=%.2f'
                             % (w['push_pct'], w['intensity'], w['run'], w['duty'])))

    # where the rules part company: same volume, different shape
    print('\n  same volume, two shapes')
    for m, run, duty in ((10.0, 1, 0.10), (1.0, 12, 0.10), (1.0, 1, 1.00), (0.5, 1, 1.00)):
        r = [x for x in rows if x['intensity'] == m and x['run'] == run
             and abs(x['duty'] - duty) < 1e-9]
        if r:
            r = r[0]
            print('  m=%5.2f run=%2d duty=%.2f -> %5.1f%% | window %.3f three %.3f sieve %.3f'
                  % (m, run, duty, r['push_pct'], r['window'], r['three'], r['sieve']))

    json.dump({
        'params': {'window_s': WINDOW, 'min_flows': MIN_FLOWS, 'tau': TAU,
                   'e_star_mb': E_STAR_MB, 'interval': INTERVAL,
                   'min_interval': MIN_INTERVAL, 'max_interval': INTERVAL,
                   'budget_mb': BUDGET_MB, 'rate_mb_per_window': RATE_MB,
                   'signed': True, 'sliding': True,
                   'intensity': INTENSITY, 'run': RUN, 'duty': DUTY,
                   'seeds': SEEDS, 'control_share': CONTROL_SHARE,
                   'windows_per_month': WINDOWS_PER_MONTH},
        'null': {'median': float(np.median(own_rho)), 'p95': float(band[1]),
                 'band': [float(band[0]), float(band[1])],
                 'n_cells': int(len(sub)), 'n_lines': int(sub['ip'].nunique()),
                 'cons_mb_per_window': c_med,
                 'cons_gb_per_month': c_med * WINDOWS_PER_MONTH / 1e9},
        'rows': rows,
    }, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
