# -*- coding: utf-8 -*-
"""E14: two questions a policy reviewer asks about the regime comparison.

  (a) The comparison prices congestion at e+lambda = 0.10 CNY/GB.  How far can
      that price move before the ordering changes?  The recorded harm volumes
      make this an exact rescaling, no re-run needed.
  (b) Enforcement is only as good as its detector.  Welfare under S1 is a
      function of the detection rate; under S3 it is not, because S3 acts on a
      declaration rather than on a classification.  The sweep gives the shape
      of that curve and its ceiling.

Both are computed on the frozen E5 population, so the baseline rows must match
e5_regime.json exactly; the script asserts that before writing anything.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import e5_regime as m  # noqa: E402
import e5_noquota as N  # noqa: E402

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e14_policy.json')
BASE = os.path.join(DATA, 'e5_regime.json')

P_SPOT = 0.22
HARM_UNIT = m.E_UPLINK + m.LAMBDA_CAP
EPS = 1.0


def assert_baseline(r):
    with open(BASE, encoding='utf-8') as f:
        b = json.load(f)['base']
    for k in ('S1', 'S2', 'S3'):
        for field in ('welfare', 'unpriced_harm', 'provider_profit', 'operator_margin'):
            if abs(r[field][k] - b[field][k]) > 1e-6:
                print('BASELINE DRIFT', field, k, r[field][k], b[field][k])
                sys.exit(1)


def harm_sweep(base):
    """welfare_k(h) = W_k - (h - e - lambda) * served_volume_k, one ledger.

    The level W_k is the same object Table 2 reports: provider profit plus
    operator margin plus consumer surplus less the harm each regime leaves
    unpaid.  The sweep asks what happens when the operator's own valuation of a
    delivered byte, h, moves away from the value e + lambda that the level W_k
    charges it.  The operator carries a delivered byte in every regime -- under
    enforcement it serves the line, under a price it collects the fee -- so the
    slope is the volume each regime serves, not the volume it leaves unbilled.
    No regime's volume responds to h, so each curve is the reported level minus
    (h - e - lambda) times the volume served.  Laissez-faire (S0) is the fourth
    reference point: every provider serves, nobody charges, and the operator
    carries every byte of congestion.
    """
    r = N.outcomes_v3(P_SPOT, 'none', eps=EPS)
    r0 = N.outcomes_v3(0.0, 'none', eps=EPS)
    W = {k: r['welfare'][k] for k in ('S1', 'S2', 'S3')}
    vol = {k: r['volume_served'][k] for k in ('S1', 'S2', 'S3')}
    r_vol = {k: r['unpriced_harm'][k] / HARM_UNIT for k in ('S1', 'S2', 'S3')}
    prof = {k: r['provider_profit'][k] for k in ('S1', 'S2', 'S3')}
    marg = {k: r['operator_margin'][k] for k in ('S1', 'S2', 'S3')}
    W['S0'] = r0['welfare']['S2']
    vol['S0'] = r0['volume_served']['S2']
    r_vol['S0'] = r0['volume_served']['S2']
    prof['S0'] = r0['provider_profit']['S2']
    marg['S0'] = r0['operator_margin']['S2']
    keys = ('S0', 'S1', 'S2', 'S3')
    grid = np.linspace(0.0, 0.5, 26)
    w = {}
    for k in keys:
        w[k] = np.asarray([W[k] - (h - HARM_UNIT) * vol[k] for h in grid])

    def crossing(a, b):
        d = w[b] - w[a]
        for i in range(len(grid) - 1):
            if d[i] > 0 >= d[i + 1] or d[i] < 0 <= d[i + 1]:
                x0, x1, y0, y1 = grid[i], grid[i + 1], d[i], d[i + 1]
                return float(x0 + (x1 - x0) * y0 / (y0 - y1))
        return None

    def at_operating(k):
        return round(float(W[k]), 1)

    return {
        'harm_price': [round(float(x), 4) for x in grid],
        'welfare': {k: [round(float(x), 1) for x in v] for k, v in w.items()},
        'welfare_at_operating': {k: at_operating(k) for k in keys},
        'harm_volume_gb': {k: round(float(vol[k]), 1) for k in keys},
        'provider_profit_at_zero': {k: round(float(prof[k]), 1) for k in keys},
        'operator_margin': {k: round(float(marg[k]), 1) for k in keys},
        'breakeven_tiers_vs_laissez': crossing('S0', 'S3'),
        'breakeven_spot_vs_laissez': crossing('S0', 'S2'),
        'breakeven_enforcement_vs_laissez': crossing('S0', 'S1'),
        'breakeven_tiers_vs_enforcement': crossing('S1', 'S3'),
        'breakeven_spot_vs_enforcement': crossing('S1', 'S2'),
        'tiers_minus_laissez_at_operating': round(at_operating('S3') - at_operating('S0'), 1),
        'spot_minus_laissez_at_operating': round(at_operating('S2') - at_operating('S0'), 1),
        'harm_paid_by_operator': {k: round(float(r_vol[k] * HARM_UNIT), 1) for k in keys},
        'served_volume_gb': {k: round(float(vol[k]), 1) for k in keys},
    }


def tpr_sweep():
    grid = np.linspace(0.0, 1.0, 21)
    w1, w3 = [], []
    prof1, harm1 = [], []
    for t in grid:
        r = N.outcomes_v3(P_SPOT, 'none', eps=EPS, det_tpr=float(t))
        w1.append(r['welfare']['S1'])
        w3.append(r['welfare']['S3'])
        prof1.append(r['provider_profit']['S1'])
        harm1.append(r['unpriced_harm']['S1'])
    w1 = np.asarray(w1)
    i = int(np.argmax(w1))
    return {
        'tpr': [round(float(x), 4) for x in grid],
        'welfare_S1': [round(float(x), 1) for x in w1],
        'welfare_S3': [round(float(x), 1) for x in w3],
        'provider_profit_S1': [round(float(x), 1) for x in prof1],
        'harm_S1': [round(float(x), 1) for x in harm1],
        'peak_tpr': float(grid[i]),
        'peak_welfare_S1': round(float(w1[i]), 1),
        'welfare_S1_at_full': round(float(w1[-1]), 1),
        'welfare_S3_flat_spread': round(float(max(w3) - min(w3)), 6),
    }


def main():
    # the same demand slope as Table 2 and the sections that read it, so the
    # sensitivity panels and the headline comparison share one ledger
    base = m.outcomes(P_SPOT, eps=1.0)
    assert_baseline(base)
    res = {
        'p_spot': P_SPOT,
        'harm_unit': HARM_UNIT,
        'harm': harm_sweep(base),
        'detection': tpr_sweep(),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print('harm volume by regime', res['harm']['harm_volume_gb'])
    print('tiers vs laissez-faire crossover', res['harm']['breakeven_tiers_vs_laissez'])
    print('tiers vs enforcement crossover', res['harm']['breakeven_tiers_vs_enforcement'])
    print('S3 minus S0 at the operating price', res['harm']['tiers_minus_laissez_at_operating'])
    print('S1 peak at tpr', res['detection']['peak_tpr'],
          'welfare', res['detection']['peak_welfare_S1'])
    print('S1 at tpr=1', res['detection']['welfare_S1_at_full'])
    print('tiers spread over tpr', res['detection']['welfare_S3_flat_spread'])


if __name__ == '__main__':
    main()
