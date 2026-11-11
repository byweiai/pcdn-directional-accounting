# -*- coding: utf-8 -*-
"""E17: does a threshold calibrated on one operator's subscribers hold on another's?

The rule the paper proposes has one parameter and no fitting. A reader who has
built traffic policies will ask the obvious question: every operator would
calibrate its own threshold on its own lines, so what happens when the
distribution of household consumption differs between two operators?

Two transfers are run.
  (a) Real, within the corpus: subscriber cells are grouped by how much the line
      pulls per window (light, middle, heavy thirds) and by time block. A
      threshold is calibrated on one group at the tightest value that gives zero
      false alarms (its p95) and applied to the other group. The fixed rho0 = 1
      rule is applied the same way.
  (b) Semi-synthetic, operator profiles: household downlink is rescaled by s to
      stand for operators whose subscribers pull different volumes per window
      (an operator with more video, or faster lines). The null distribution of
      rho moves with s, so a calibrated threshold moves too. The fixed rule is
      checked on every profile.

The distinction matters because a calibrated threshold is only valid for the
population it was calibrated on, while rho0 = 1 is a statement about the
contract. If the fixed rule transfers and the calibrated one does not, then the
paper's choice of a single parameter is not a simplification: it is the reason
the rule can be written into a tariff.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
RAW = os.path.join(DATA, 'raw')
OUT = os.path.join(DATA, 'e17_transfer.json')

FILES = ['UNSW-NB15_1.csv', 'UNSW-NB15_2.csv', 'UNSW-NB15_3.csv', 'UNSW-NB15_4.csv']
WINDOW = 300
MIN_FLOWS = 5
TAU_FIXED = 0.5
SCALES = [0.25, 0.5, 1.0, 2.0, 4.0]
SEEDS = [1, 2, 3]
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
    g['rho'] = g['sent'] / (g['sent'] + g['recv'])
    return g


def fp(rho, tau):
    return float(np.mean(rho > tau)) if len(rho) else float('nan')


def main():
    print('== E17: transfer of a calibrated threshold across subscriber mixes ==')
    df = load()
    g = cells(df, WINDOW)
    sub = g[g['ip'].str.startswith('59.166.')].copy()
    print('  %d subscriber cells, %d lines, %d windows'
          % (len(sub), sub['ip'].nunique(), sub['w'].nunique()))

    # (a) groups that stand in for operators with different subscriber mixes
    q = np.percentile(sub['recv'].values, [33.3, 66.7])
    sub['mix'] = np.where(sub['recv'] <= q[0], 'light',
                          np.where(sub['recv'] <= q[1], 'mid', 'heavy'))
    wq = np.percentile(sub['w'].values, [33.3, 66.7])
    sub['block'] = np.where(sub['w'] <= wq[0], 'early',
                            np.where(sub['w'] <= wq[1], 'middle', 'late'))

    def summary(name, col):
        out = {}
        for k, s in sub.groupby(col):
            r = s['rho'].values
            out[k] = {'n': int(len(r)), 'median': float(np.median(r)),
                      'p95': float(np.percentile(r, 95)),
                      'cons_mb': float(np.median(s['recv'].values)) / 1e6}
        print('\n  %s' % name)
        for k, v in out.items():
            print('    %-7s n=%4d median %.4f p95 %.4f consumption %.1f MB/win'
                  % (k, v['n'], v['median'], v['p95'], v['cons_mb']))
        return out

    mixes = summary('by subscriber mix (stands in for operators with different mixes)',
                    'mix')
    blocks = summary('by time block', 'block')

    # transfer: calibrate at p95 of one group, apply to the other
    print('\n  transfer matrix, calibrated threshold = p95 of the source group')
    names = ['light', 'mid', 'heavy']
    print('    %-7s %-7s %8s %8s %8s' % ('from', 'to', 'tau_cal', 'FP_cal', 'FP_fixed'))
    transfer = []
    for a in names:
        ra = sub[sub['mix'] == a]['rho'].values
        tau = float(np.percentile(ra, 95))
        for b in names:
            rb = sub[sub['mix'] == b]['rho'].values
            row = {'from': a, 'to': b, 'tau_cal': tau,
                   'fp_cal': fp(rb, tau), 'fp_fixed': fp(rb, TAU_FIXED)}
            transfer.append(row)
            print('    %-7s %-7s %8.3f %8.4f %8.4f'
                  % (a, b, tau, row['fp_cal'], row['fp_fixed']))

    print('\n  transfer across time blocks')
    tblocks = []
    for a in ['early', 'middle', 'late']:
        ra = sub[sub['block'] == a]['rho'].values
        tau = float(np.percentile(ra, 95))
        for b in ['early', 'middle', 'late']:
            rb = sub[sub['block'] == b]['rho'].values
            row = {'from': a, 'to': b, 'tau_cal': tau,
                   'fp_cal': fp(rb, tau), 'fp_fixed': fp(rb, TAU_FIXED)}
            tblocks.append(row)
            print('    %-7s -> %-7s tau %.3f FP_cal %.4f FP_fixed %.4f'
                  % (a, b, tau, row['fp_cal'], row['fp_fixed']))

    # (b) operator profiles: household downlink rescaled
    print('\n  operator profiles, household downlink rescaled by s')
    profiles = []
    base_rho = sub['rho'].values
    base_s = sub['sent'].values
    base_r = sub['recv'].values
    for s in SCALES:
        rr = base_s / (base_s + s * base_r)
        tau = float(np.percentile(rr, 95))
        profiles.append({'scale': s, 'p95': tau, 'median': float(np.median(rr)),
                         'fp_fixed': fp(rr, TAU_FIXED),
                         'cons_mb': float(np.median(s * base_r)) / 1e6,
                         'cons_gb_month': float(np.median(s * base_r))
                         * WINDOWS_PER_MONTH / 1e9})
        print('    s=%.2f consumption %6.1f MB/win (%5.0f GB/mo) | median %.4f p95 %.4f'
              ' | tau_cal %.4f | FP at rho0=1 %.4f'
              % (s, profiles[-1]['cons_mb'], profiles[-1]['cons_gb_month'],
                 profiles[-1]['median'], tau, tau, profiles[-1]['fp_fixed']))

    worst_cal = max(r['fp_cal'] for r in transfer)
    worst_fixed = max(r['fp_fixed'] for r in transfer)
    spread = max(p['p95'] for p in profiles) - min(p['p95'] for p in profiles)
    print('\n  summary')
    print('    worst cross-group false alarm, calibrated threshold  %.4f' % worst_cal)
    print('    worst cross-group false alarm, fixed rho0 = 1        %.4f' % worst_fixed)
    print('    calibrated threshold moves %.3f across operator profiles' % spread)

    json.dump({
        'params': {'window_s': WINDOW, 'min_flows': MIN_FLOWS, 'tau_fixed': TAU_FIXED,
                   'scales': SCALES, 'seeds': SEEDS,
                   'windows_per_month': WINDOWS_PER_MONTH},
        'mixes': mixes, 'blocks': blocks,
        'transfer_mix': transfer, 'transfer_block': tblocks,
        'profiles': profiles,
        'summary': {'worst_calibrated_fp': worst_cal,
                    'worst_fixed_fp': worst_fixed,
                    'calibrated_spread': float(spread)},
    }, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
