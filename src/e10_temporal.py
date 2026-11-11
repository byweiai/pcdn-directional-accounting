"""E10 -- temporal closure of the directional quota.

Question. The three-consecutive-window rule counts a *run*. An endpoint that
alternates one distributing window with one idle window never produces a run,
so it sits above quota half the time for free. Does an interval rule (SIEVE)
close that hole, and what does closing it cost on real subscribers?

Construction. For every sending endpoint in UNSW-NB15 take its median per-window
uplink m_S and downlink m_R, then replay the same total distribution
D = 24 * m_S over a 24-window horizon (2 h at 300 s) under four schedules:

    steady     m_S every window
    alternate  2 m_S on even windows, 0 on odd
    pulse      3 m_S every third window, 0 otherwise
    ramp       weights 0..1, normalised to D

All four deliver exactly D, so a rule that reads totals cannot separate them.
What separates them is whether the rule reads a *window* or an *interval*.

Rules compared.
    RULE3   rho > 0.5 in three consecutive windows
    SIEVE   some interval of length >= 3 windows has
              (i) interval ratio  sum S / (sum S + sum R) > 0.5, and
              (ii) interval excess sum (S - R) > B + r * length
            with B = 10 MB and r = 10/3 MB per window (10 MB per 15 min).

Because both of SIEVE's tests are functions of interval sums, its verdict is
identical under every schedule that delivers the same bytes per interval; the
experiment checks that claim rather than assuming it.
"""
import json
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
RAW = os.path.join(DATA, 'raw')

WINDOW_S = 300
HORIZON = 24
TMIN = 3
THRESH_RHO = 0.5
BUDGET_MB = 10.0
RATE_MB_PER_WIN = 10.0 / 3.0
CLIENT = '59.166.'
SERVICE = '149.171.126.'


def role(ip):
    if ip.startswith(CLIENT):
        return 'client'
    if ip.startswith(SERVICE):
        return 'service'
    return 'other'


def load_windows():
    acc = {}
    t0 = None
    for fn in ['UNSW-NB15_1.csv', 'UNSW-NB15_2.csv', 'UNSW-NB15_3.csv',
               'UNSW-NB15_4.csv']:
        path = os.path.join(RAW, fn)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, header=None, names=range(49), encoding='utf-8-sig',
                         usecols=[0, 2, 7, 8, 28], low_memory=False)
        df.columns = ['src', 'dst', 'sb', 'db', 't']
        df = df.dropna(subset=['src', 'dst', 't'])
        for c in ('sb', 'db', 't'):
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        if t0 is None:
            t0 = float(df['t'].min())
        w = ((df['t'].to_numpy() - t0) // WINDOW_S).astype(np.int64)
        src = df['src'].to_numpy()
        dst = df['dst'].to_numpy()
        sb = df['sb'].to_numpy(dtype=float)
        db = df['db'].to_numpy(dtype=float)
        for ip, win, sent, recv in zip(np.concatenate([src, dst]),
                                       np.concatenate([w, w]),
                                       np.concatenate([sb, db]),
                                       np.concatenate([db, sb])):
            k = (ip, int(win))
            cur = acc.get(k)
            if cur is None:
                acc[k] = [sent, recv]
            else:
                cur[0] += sent
                cur[1] += recv
    return acc


def series(acc, ip, n_win):
    S = np.zeros(n_win)
    R = np.zeros(n_win)
    for (i, w), (s, r) in acc.items():
        if i != ip or w >= n_win:
            continue
        S[w] += s
        R[w] += r
    return S, R


def schedule(name, m_s, n):
    D = m_s * n
    S = np.zeros(n)
    if name == 'steady':
        S[:] = m_s
    elif name == 'alternate':
        S[0::2] = 2.0 * m_s
    elif name == 'pulse':
        S[0::3] = 3.0 * m_s
    elif name == 'ramp':
        w = np.arange(1, n + 1, dtype=float)
        S = D * w / w.sum()
    else:
        raise ValueError(name)
    if S.sum() > 0:
        S *= D / S.sum()
    return S


def first_run(S, R, k=TMIN, tau=THRESH_RHO):
    rho = S / np.maximum(1e-12, S + R)
    run = 0
    for i, v in enumerate(rho):
        run = run + 1 if v > tau else 0
        if run >= k:
            return i - k + 1
    return None


def first_interval(S, R, tmin=TMIN, tau=THRESH_RHO,
                   budget=BUDGET_MB, rate=RATE_MB_PER_WIN, use_budget=True):
    """Earliest end window of an interval satisfying the SIEVE tests."""
    n = len(S)
    hit = None
    for a in range(n):
        ss = sr = 0.0
        for b in range(a, n):
            ss += S[b]
            sr += R[b]
            L = b - a + 1
            if L < tmin:
                continue
            if ss <= tau * (ss + sr):
                continue
            if use_budget:
                ex_mb = (ss - sr) / 1e6
                if ex_mb <= budget + rate * L:
                    continue
            hit = b if hit is None else min(hit, b)
            break
    return hit


def main():
    acc = load_windows()
    n_win = max(w for (_, w) in acc) + 1
    print('windows:', n_win, 'endpoints:', len({ip for (ip, _) in acc}))

    names = ['steady', 'alternate', 'pulse', 'ramp']
    out = {'window_s': WINDOW_S, 'horizon': HORIZON, 'min_interval': TMIN,
           'threshold_rho': THRESH_RHO,
           'sieve': {'budget_mb': BUDGET_MB, 'rate_mb_per_window': RATE_MB_PER_WIN},
           'schedules': {}, 'endpoints': {}, 'subscriber': {}}

    ips = sorted({ip for (ip, _) in acc if role(ip) == 'service'})
    for name in names:
        t3, tR, tS, exp3, expR, expS = [], [], [], [], [], []
        for ip in ips:
            S, R = series(acc, ip, n_win)
            act = S > 0
            if act.sum() < 5:
                continue
            m_s = float(np.median(S[act]))
            m_r = float(np.median(R[act]))
            if m_s <= 0:
                continue
            Sx = schedule(name, m_s, HORIZON)
            Rx = np.full(HORIZON, m_r)
            a3 = first_run(Sx, Rx)
            aR = first_interval(Sx, Rx, use_budget=False)
            aS = first_interval(Sx, Rx, use_budget=True)
            t3.append(a3 is not None)
            tR.append(aR is not None)
            tS.append(aS is not None)
            exp3.append(HORIZON if a3 is None else a3)
            expR.append(HORIZON if aR is None else aR)
            expS.append(HORIZON if aS is None else aS)
            out['endpoints'].setdefault(ip, {})[name] = {
                'm_s_mb': m_s / 1e6, 'm_r_mb': m_r / 1e6,
                'rule3': a3, 'interval_ratio': aR, 'sieve': aS}
        out['schedules'][name] = {
            'n': len(t3),
            'rule3_rate': float(np.mean(t3)),
            'interval_ratio_rate': float(np.mean(tR)),
            'sieve_rate': float(np.mean(tS)),
            'rule3_median_exposure': float(np.median(exp3)),
            'interval_ratio_median_exposure': float(np.median(expR)),
            'sieve_median_exposure': float(np.median(expS)),
        }
        r = out['schedules'][name]
        print('%-10s n=%2d rule3=%.3f interval=%.3f sieve=%.3f  exposure '
              'rule3=%.1f interval=%.1f sieve=%.1f'
              % (name, r['n'], r['rule3_rate'], r['interval_ratio_rate'],
                 r['sieve_rate'], r['rule3_median_exposure'],
                 r['interval_ratio_median_exposure'],
                 r['sieve_median_exposure']))

    fa3 = faR = faS = 0
    nsub = 0
    worst = 0.0
    for ip in sorted({ip for (ip, _) in acc if role(ip) == 'client'}):
        S, R = series(acc, ip, n_win)
        if S.sum() <= 0:
            continue
        nsub += 1
        fa3 += 1 if first_run(S, R) is not None else 0
        faR += 1 if first_interval(S, R, use_budget=False) is not None else 0
        faS += 1 if first_interval(S, R, use_budget=True) is not None else 0
        ex = (S - R) / 1e6
        for a in range(len(ex)):
            s = 0.0
            for b in range(a, len(ex)):
                s += ex[b]
                worst = max(worst, s - RATE_MB_PER_WIN * (b - a + 1))
    out['subscriber'] = {'n': nsub,
                         'rule3_false_alarm': fa3 / nsub,
                         'interval_ratio_false_alarm': faR / nsub,
                         'sieve_false_alarm': faS / nsub,
                         'worst_excess_over_rate_mb': worst}
    print('subscribers n=%d rule3=%.3f interval=%.3f sieve=%.3f worst_margin=%.2f MB'
          % (nsub, fa3 / nsub, faR / nsub, faS / nsub, worst))

    with open(os.path.join(DATA, 'e10_temporal.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print('wrote data/e10_temporal.json')


if __name__ == '__main__':
    main()
