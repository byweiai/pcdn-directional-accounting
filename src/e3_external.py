# -*- coding: utf-8 -*-
"""E3: robustness of the directional statistic outside the original slice.

Three independent perturbations, none of which changes the estimator:

  a. A different capture. CIC-IDS2017 flows, extracted by another team with
     another tool from another network five semesters later. Only the *shape*
     of the endpoint-level distribution is compared -- that capture contains a
     single eight-host victim subnet, so it has no population of subscriber
     endpoints from which to draw a contrast group, and pretending otherwise
     would be the circularity a referee would catch.

  b. A different time slice of UNSW-NB15. The quota is fixed on one hour and
     then applied to the rest of the 648-hour trace, which is what an operator
     who sets a policy once and walks away actually experiences.

  c. A different traffic composition. The trace is split by attack category. If
     the statistic were really an anomaly detector, its subscriber-side lobe
     would move when attacks appear. If it measures direction, the lobe stays
     where it is and only the population of high-rho endpoints grows.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e3_external.json')

IDX = {'srcip': 0, 'sport': 1, 'dstip': 2, 'dsport': 3, 'proto': 4, 'state': 5,
       'dur': 6, 'sbytes': 7, 'dbytes': 8, 'Spkts': 16, 'Dpkts': 17,
       'Stime': 28, 'Ltime': 29, 'attack_cat': 47, 'Label': 48}
NFIELDS = 49
BAD_PREFIX = ('fe80:', 'ff0', 'ff1', 'ff2', '224.', '239.', '0.', '255.')


def kde(x, grid=512, bw=None):
    x = np.asarray(x, float)
    if bw is None:
        n = len(x)
        s = float(x.std(ddof=1))
        iqr = float(np.subtract(*np.percentile(x, [75, 25]))) / 1.349
        bw = max(0.9 * min(s, iqr) * n ** (-1 / 5), 0.01)
    g = np.linspace(0, 1, grid)
    d = np.exp(-0.5 * ((g[:, None] - x[None, :]) / bw) ** 2).sum(1)
    d /= len(x) * bw * np.sqrt(2 * np.pi)
    peaks = [i for i in range(1, grid - 1) if d[i] > d[i - 1] and d[i] >= d[i + 1]]
    peaks = sorted(peaks, key=lambda i: -d[i])
    return g, d, peaks, bw


def two_lobe_summary(rho):
    """Report the two dominant lobes and the valley that separates them.

    Peaks are picked inside the two end bands rather than by raw height: a
    capture dominated by one role produces a huge spike near 1 and a smaller one
    near 0, and the interesting quantity is the gap between the *bands*, not
    between the two tallest local maxima.
    """
    g, d, peaks, bw = kde(rho)
    lo_band = (g >= 0.0) & (g <= 0.35)
    hi_band = (g >= 0.65) & (g <= 1.0)
    mid_band = (g >= 0.15) & (g <= 0.85)
    out = {'kde_bandwidth': float(bw), 'peaks': [float(g[i]) for i in peaks[:4]]}
    if not (lo_band.any() and hi_band.any() and mid_band.any()):
        return out
    i_lo = int(np.argmax(np.where(lo_band, d, -1)))
    i_hi = int(np.argmax(np.where(hi_band, d, -1)))
    seg = np.where(mid_band, d, np.inf)
    i_v = int(np.argmin(seg))
    out.update({
        'lobe_low': float(g[i_lo]), 'lobe_high': float(g[i_hi]),
        'lobe_low_density': float(d[i_lo]), 'lobe_high_density': float(d[i_hi]),
        'valley_rho': float(g[i_v]), 'valley_density': float(d[i_v]),
        'valley_over_peak': float(d[i_v] / max(1e-12, min(d[i_lo], d[i_hi]))),
        'lobe_separation': float(g[i_hi] - g[i_lo]),
    })
    return out


# ---------------------------------------------------------------- part a: CIC
def part_cic():
    p = os.path.join(DATA, 'raw', 'ids_cic_binary_head.csv')
    df = pd.read_csv(p, usecols=['SRC_IP', 'DST_IP', 'BYTES', 'BYTES_REV', 'LABEL'],
                     low_memory=False, on_bad_lines='skip').dropna(subset=['SRC_IP', 'DST_IP'])
    m = ~df['SRC_IP'].astype(str).str.startswith(BAD_PREFIX)
    m &= ~df['DST_IP'].astype(str).str.startswith(BAD_PREFIX)
    m &= (df['BYTES'] + df['BYTES_REV']) > 0
    df = df[m]
    ent = pd.DataFrame({
        'ip': np.r_[df['SRC_IP'].values, df['DST_IP'].values],
        'sent': np.r_[df['BYTES'].values, df['BYTES_REV'].values],
        'recv': np.r_[df['BYTES_REV'].values, df['BYTES'].values],
    })
    a = ent.groupby('ip').agg(sent=('sent', 'sum'), recv=('recv', 'sum'),
                              n=('sent', 'size'))
    a = a[a['n'] >= 5]
    a = a[(a['sent'] + a['recv']) > 0]
    rho = (a['sent'] / (a['sent'] + a['recv'])).values
    s = two_lobe_summary(rho)
    s.update({'n_endpoints': int(len(a)), 'n_flows': int(len(df)),
              'rho_median': float(np.median(rho)),
              'rho_quantiles': {str(q): float(np.quantile(rho, q))
                                for q in [0.05, 0.25, 0.5, 0.75, 0.95]}})
    return s


# ------------------------------------------------- part b,c: UNSW time + attack
def load_unsw(which=('1', '2', '3', '4')):
    frames = []
    for w in which:
        p = os.path.join(DATA, 'raw', 'UNSW-NB15_%s.csv' % w)
        if not os.path.exists(p):
            continue
        raw = pd.read_csv(p, header=None, names=list(range(NFIELDS)),
                          usecols=sorted(IDX.values()), low_memory=False,
                          encoding='utf-8-sig', na_values=['-', ''])
        frames.append(pd.DataFrame({k: raw[i] for k, i in IDX.items()}))
    df = pd.concat(frames, ignore_index=True)
    for c in ['sbytes', 'dbytes', 'Stime', 'Ltime']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['sbytes', 'dbytes', 'Stime'])
    df = df[(df['sbytes'] + df['dbytes']) > 0]
    m = ~df['srcip'].astype(str).str.startswith(BAD_PREFIX)
    m &= ~df['dstip'].astype(str).str.startswith(BAD_PREFIX)
    df = df[m]
    df['is_service_ip'] = df['srcip'].astype(str).str.startswith('149.171.126.')
    df['is_client_ip'] = df['srcip'].astype(str).str.startswith('59.166.')
    return df


def endpoints_in(df, min_flows=5):
    ent = pd.DataFrame({
        'ip': np.r_[df['srcip'].values, df['dstip'].values],
        'sent': np.r_[df['sbytes'].values, df['dbytes'].values],
        'recv': np.r_[df['dbytes'].values, df['sbytes'].values],
    })
    a = ent.groupby('ip').agg(sent=('sent', 'sum'), recv=('recv', 'sum'),
                              n=('sent', 'size'))
    a = a[a['n'] >= min_flows]
    a = a[(a['sent'] + a['recv']) > 0]
    a['rho'] = a['sent'] / (a['sent'] + a['recv'])
    return a


def part_time(df):
    """Fix the quota on the first hour, then apply it to the remaining trace."""
    t0 = df['Stime'].min()
    hour = ((df['Stime'] - t0) // 3600).astype(int)
    hours = sorted(hour.unique())
    if len(hours) < 3:
        return {'error': 'trace shorter than three hours'}
    calib_h = hours[0]
    calib = endpoints_in(df[hour == calib_h])
    cli = calib[calib.index.to_series().astype(str).str.startswith('59.166.')]
    if len(cli) == 0:
        return {'error': 'no client endpoints in calibration hour'}
    # the quota is the calibration-hour subscriber p95, doubled for headroom
    quota = float(np.quantile(cli['rho'], 0.95)) * 2
    rows = []
    for h in hours:
        sub = df[hour == h]
        a = endpoints_in(sub)
        if len(a) < 10:
            continue
        cli_mask = a.index.to_series().astype(str).str.startswith('59.166.')
        srv_mask = a.index.to_series().astype(str).str.startswith('149.171.126.')
        cli_r = a.loc[cli_mask.values, 'rho']
        srv_r = a.loc[srv_mask.values, 'rho']
        rows.append({
            'hour': int(h), 'n_endpoints': int(len(a)),
            'n_client': int(len(cli_r)), 'n_service': int(len(srv_r)),
            'false_positive': float((cli_r > quota).mean()) if len(cli_r) else None,
            'capture': float((srv_r > quota).mean()) if len(srv_r) else None,
            'client_median': float(cli_r.median()) if len(cli_r) else None,
        })
    return {'quota': quota, 'calibration_hour': int(calib_h), 'hours': rows}


def part_attack(df):
    """Separate sustained distribution from bursty abuse by time persistence.

    The statistic measures direction, not malice: a flooding host also sends
    more than it receives. What a flooding host does not do is keep doing it,
    window after window, while still receiving content it has to carry. So for
    every endpoint we count the fraction of five-minute windows in which its rho
    exceeds one half and the longest run of consecutive such windows. Endpoints
    are then grouped by role and, separately, by whether they appear as an
    attacker source in the trace.
    """
    W = 300
    t0 = df['Stime'].min()
    df = df.assign(win=((df['Stime'] - t0) // W).astype('int64'))
    nwin = int(df['win'].max()) + 1

    long = pd.DataFrame({
        'ip': np.r_[df['srcip'].values, df['dstip'].values],
        'win': np.r_[df['win'].values, df['win'].values],
        'sent': np.r_[df['sbytes'].values, df['dbytes'].values],
        'recv': np.r_[df['dbytes'].values, df['sbytes'].values],
    })
    cell = long.groupby(['ip', 'win']).agg(sent=('sent', 'sum'),
                                           recv=('recv', 'sum'),
                                           n=('sent', 'size')).reset_index()
    cell = cell[(cell['sent'] + cell['recv']) > 0]
    cell['rho'] = cell['sent'] / (cell['sent'] + cell['recv'])

    atk = df[df['Label'].astype(str).str.strip().isin(['1', '1.0'])]
    attackers = set(atk['srcip'].astype(str).unique())

    rows = []
    for ip, grp in cell.groupby('ip'):
        r = grp.sort_values('win')
        over = (r['rho'].values > 0.5).astype(int)
        # longest run of consecutive windows above the line
        best = cur = 0
        prev_win = None
        for w, o in zip(r['win'].values, over):
            if o and prev_win is not None and w == prev_win + 1:
                cur += 1
            elif o:
                cur = 1
            else:
                cur = 0
            best = max(best, cur)
            prev_win = w
        s = str(ip)
        role = ('service' if s.startswith('149.171.126.') else
                'client' if s.startswith('59.166.') else 'other')
        rows.append({'ip': s, 'role': role, 'windows': int(len(r)),
                     'over_share': float(over.mean()),
                     'longest_run': int(best), 'rho_median': float(r['rho'].median()),
                     'bytes': float(r['sent'].sum() + r['recv'].sum()),
                     'is_attacker': s in attackers})
    P = pd.DataFrame(rows)
    P = P[P['windows'] >= 3]

    out = {'n_windows_total': nwin, 'n_endpoints': int(len(P)),
           'window_seconds': W}
    by_role = {}
    for role, grp in P.groupby('role'):
        by_role[role] = {
            'n': int(len(grp)),
            'over_share_median': float(grp['over_share'].median()),
            'over_share_p90': float(grp['over_share'].quantile(0.90)),
            'longest_run_median': float(grp['longest_run'].median()),
            'longest_run_p90': float(grp['longest_run'].quantile(0.90)),
            'windows_median': float(grp['windows'].median()),
        }
    out['by_role'] = by_role
    # among endpoints that ever crossed, how sustained is the crossing?
    cross = P[P['over_share'] > 0]
    out['crossers'] = {
        'n': int(len(cross)),
        'service_share': float((cross['role'] == 'service').mean()),
        'attacker_share': float(cross['is_attacker'].mean()),
        'persistent_90pct': int((cross['over_share'] >= 0.9).sum()),
        'persistent_90pct_service': int(((cross['over_share'] >= 0.9) &
                                         (cross['role'] == 'service')).sum()),
        'persistent_90pct_attacker': int(((cross['over_share'] >= 0.9) &
                                          (cross['is_attacker'])).sum()),
        'attacker_over_share_median': (float(cross.loc[cross['is_attacker'], 'over_share'].median())
                                       if cross['is_attacker'].any() else None),
        'service_over_share_median': (float(cross.loc[cross['role'] == 'service', 'over_share'].median())
                                      if (cross['role'] == 'service').any() else None),
    }
    return out


def main():
    print('== E3: robustness outside the original slice ==')
    res = {}

    print('\n[a] CIC-IDS2017, independent capture (shape only)')
    res['cic'] = part_cic()
    print('    endpoints %d from %d flows' % (res['cic']['n_endpoints'], res['cic']['n_flows']))
    print('    KDE lobes at %s  bandwidth %.4f'
          % (['%.3f' % p for p in res['cic']['peaks']], res['cic']['kde_bandwidth']))
    if res['cic'].get('valley_rho') is not None:
        print('    valley at rho=%.3f, %.0f%% of the shallower lobe height'
              % (res['cic']['valley_rho'], 100 * res['cic']['valley_over_peak']))

    print('\n[b,c] UNSW-NB15, all four capture files')
    df = load_unsw()
    print('    flows %d, span %.1f h' % (len(df), (df['Stime'].max() - df['Stime'].min()) / 3600))

    res['time'] = part_time(df)
    if 'quota' in res['time']:
        print('    quota from calibration hour = %.4f' % res['time']['quota'])
        hrs = res['time']['hours']
        fp = [h['false_positive'] for h in hrs if h['false_positive'] is not None]
        cp = [h['capture'] for h in hrs if h['capture'] is not None]
        print('    applied to %d hours: false-positive %.4f [max %.4f], capture %.4f [min %.4f]'
              % (len(hrs), float(np.mean(fp)), float(np.max(fp)),
                 float(np.mean(cp)), float(np.min(cp))))

    res['attack'] = part_attack(df)
    a = res['attack']
    print('    temporal persistence over %d five-minute windows, %d endpoints'
          % (a['n_windows_total'], a['n_endpoints']))
    for role, v in a['by_role'].items():
        print('      %-8s n=%5d  over-share median %.3f  longest run median %.1f'
              % (role, v['n'], v['over_share_median'], v['longest_run_median']))
    c = a['crossers']
    print('    endpoints that ever crossed rho>0.5: %d (service %.0f%%, attacker %.0f%%)'
          % (c['n'], 100 * c['service_share'], 100 * c['attacker_share']))
    print('    of those, sustained >=90%% of windows: %d (service %d, attacker %d)'
          % (c['persistent_90pct'], c['persistent_90pct_service'],
             c['persistent_90pct_attacker']))
    if c['attacker_over_share_median'] is not None:
        print('    median over-share: service %.3f vs attacker %.3f'
              % (c['service_over_share_median'], c['attacker_over_share_median']))

    json.dump(res, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
