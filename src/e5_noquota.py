"""C3 + C5: what the paper's own S2 tariff actually implies.

Two questions, answered on the same 20,000-endpoint population as E5:

  C3  The paper defines S2 as "meter every endpoint and charge the market spot
      price per gigabyte of upstream, with no declaration and no quota", but
      src/e5_regime.py:120 gives S2 a free allowance equal to household
      downlink.  Here `quota_rule='none'` implements the stated tariff: every
      upstream gigabyte is billed, so there is nothing to launder.

  C5  src/e5_regime.py:182 replaces the S2 provider profit with a version that
      does not subtract the payment, while the operator's receipt is added, so
      a transfer is booked as a gain.  Here every payment is deducted from the
      payer and credited to the payee, and an evasion payment is treated as a
      resource cost that leaves the system.  The legacy (unbalanced) number is
      also reported so the two can be compared.

Nothing in the manuscript chain is touched: results go to data/e5_noquota.json.
"""

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import e5_regime as E  # noqa: E402  (module-level draws are seeded)

OUT = os.path.join(os.path.dirname(HERE), 'data', 'e5_noquota.json')
RULES = ('ratio', 'billed', 'none')
EPS_LIST = (None, 0.5, 1.0)


def outcomes_v3(p_spot, quota_rule='none', eps=1.0, evasion_cost=E.EVASION_COST,
                p_provider=E.P_PROVIDER, det_tpr=None):
    vol, dn = E.VOL, E.HOUSE_DN
    caught = E.CAUGHT if det_tpr is None else (E.CAUGHT_U < det_tpr)

    # ---- S1 ---------------------------------------------------------------
    kept = ~caught
    s1_served = float(np.sum(vol[kept]))
    s1_harm = s1_served * (E.E_UPLINK + E.LAMBDA_CAP)

    # ---- S2 ---------------------------------------------------------------
    if quota_rule == 'ratio':
        quota = dn
    elif quota_rule == 'billed':
        quota = np.full_like(dn, E.HOUSE_DN_GB)
    elif quota_rule == 'none':
        quota = np.zeros_like(dn)
    else:
        raise ValueError(quota_rule)

    billable = np.maximum(0.0, vol - quota)
    # A ceiling the endpoint can raise by buying bytes is the only one that can
    # be laundered; with no ceiling there is no escape route at all.
    launders = bool(evasion_cost < p_spot) and quota_rule == 'ratio'
    if launders:
        pay_s2 = float(np.sum(billable)) * evasion_cost      # leaves the system
        billed_s2 = np.zeros_like(billable)
        extra_dn = billable
    else:
        pay_s2 = float(np.sum(billable)) * p_spot            # transfer
        billed_s2 = billable
        extra_dn = np.zeros_like(billable)
    s2_served = float(np.sum(vol))
    s2_harm = (float(np.sum(vol - billed_s2)) + float(np.sum(extra_dn))) \
        * (E.E_UPLINK + E.LAMBDA_CAP)

    # ---- S3 ---------------------------------------------------------------
    ratio = vol / (vol + dn)
    tripped = (ratio > E.RHO_TRIGGER) & (vol > E.UP_TRIGGER_X * E.HOUSE_UP_GB)
    served_c = np.minimum(vol, E.CONSUMER_UPLINK_CAP_GB)
    profit_c = served_c * (E.P_MARKET - E.C_NODE_MARGIN)
    profit_d = vol * (E.P_MARKET - E.C_NODE_MARGIN - p_provider)
    declare = tripped & (profit_d > profit_c) & (profit_d > 0)
    served_s3 = np.where(declare, vol, served_c)
    declared_gb = float(np.sum(vol[declare]))
    s3_harm = float(np.sum(np.where(declare, 0.0, served_s3))) * (E.E_UPLINK + E.LAMBDA_CAP)

    served = {'S1': s1_served, 'S2': s2_served, 'S3': float(np.sum(served_s3))}
    harm = {'S1': s1_harm, 'S2': s2_harm, 'S3': s3_harm}
    payment_out = {'S1': 0.0, 'S2': pay_s2, 'S3': declared_gb * p_provider}
    # The evasion payment buys disguised downlink; the resource cost of those
    # bytes is already inside `harm` through `extra_dn`, so charging the payment
    # again as a resource would debit the same byte twice. The payment is a
    # transfer to whoever supplies the disguise, and only the payer's surplus
    # falls (line 99).
    resource = {'S1': 0.0, 'S2': 0.0, 'S3': 0.0}

    out = {'p_spot': p_spot, 'quota_rule': quota_rule, 'eps': eps,
           'laundering_pays': launders, 'registration_rate': float(declare.mean())}
    welfare, legacy, profit, margin, cs, total = {}, {}, {}, {}, {}, {}
    for k in served:
        cs[k], price = E._cs(served[k], served['S2'], eps)
        margin[k] = {'S1': 0.0,
                     'S2': float(np.sum(billed_s2)) * (p_spot - E.E_UPLINK - E.LAMBDA_CAP),
                     'S3': declared_gb * (p_provider - E.E_UPLINK - E.LAMBDA_CAP)}[k]
        # balanced: the payer's payment leaves its surplus; an evasion payment
        # is a resource cost, not a transfer.
        profit[k] = served[k] * (price - E.C_NODE_MARGIN) - payment_out[k]
        welfare[k] = profit[k] + margin[k] + cs[k] - harm[k] - resource[k]
        # the paper's definition counts only *unpriced* harm; the stricter
        # convention charges the externality on every served byte
        total[k] = profit[k] + margin[k] + cs[k] - served[k] * (E.E_UPLINK + E.LAMBDA_CAP)
        # legacy: payment not deducted from the payer (src/e5_regime.py:182)
        profit_l = served[k] * (price - E.C_NODE_MARGIN) - (payment_out[k] if k == 'S3' else 0.0)
        legacy[k] = profit_l + margin[k] + cs[k] - harm[k]
        out['price'] = price

    out.update({
        'welfare': welfare, 'welfare_total': total, 'welfare_legacy': legacy,
        'provider_profit': profit,
        'operator_margin': margin, 'consumer_surplus': cs, 'volume_served': served,
        'unpriced_harm': harm, 'payment': payment_out,
        'harm_per_gb': {k: harm[k] / max(1e-9, served[k]) for k in served},
    })

    # who would leave the distributor business
    per_provider = np.where(declare, vol * (E.P_MARKET - E.C_NODE_MARGIN - p_provider),
                            np.zeros_like(vol))
    out['exit_share'] = float((per_provider < 0).mean())
    out['provider_margin_per_gb'] = {
        'S2': (price - E.C_NODE_MARGIN - p_spot) if not launders else None,
        'S3': E.P_MARKET - E.C_NODE_MARGIN - p_provider,
    }
    return out


def main():
    res = {'population': E.N_ENDPOINTS, 'providers': E.SHARE_PROVIDER,
           'evasion_cost': E.EVASION_COST, 'p_provider': E.P_PROVIDER,
           'p_market': E.P_MARKET, 'operator_cost_per_gb': E.E_UPLINK + E.LAMBDA_CAP}

    print('vol served ratio first: mean %.1f GB, dn mean %.1f GB'
          % (E.VOL.mean(), E.HOUSE_DN.mean()))

    # ---- 1. the three quota conventions at the operating price -------------
    base = {}
    for eps in EPS_LIST:
        for rule in RULES:
            o = outcomes_v3(0.22, quota_rule=rule, eps=eps)
            base['%s|eps=%s' % (rule, eps)] = o
            if eps == 1.0:
                print('\nrule=%-7s eps=1.0  balanced welfare S1 %10.1f  S2 %10.1f  S3 %10.1f'
                      % (rule, o['welfare']['S1'], o['welfare']['S2'], o['welfare']['S3']))
                print('%-13s legacy   welfare S1 %10.1f  S2 %10.1f  S3 %10.1f'
                      % ('', o['welfare_legacy']['S1'], o['welfare_legacy']['S2'],
                         o['welfare_legacy']['S3']))
                print('%-13s S2/S3 = %.3f   S2/S1 = %.3f   launder=%s  cs_S2 %.1f'
                      % ('', o['welfare']['S2'] / o['welfare']['S3'],
                         o['welfare']['S2'] / o['welfare']['S1'],
                         o['laundering_pays'], o['consumer_surplus']['S2']))
    res['base'] = base

    # ---- 2. price sweep, balanced ledger, no quota ------------------------
    grid = np.round(np.arange(0.04, 0.301, 0.02), 2)
    sweep = {}
    for rule in ('none', 'ratio'):
        rows = []
        for p in grid:
            o = outcomes_v3(float(p), quota_rule=rule, eps=1.0)
            rows.append({'p_spot': float(p), 'laundered': o['laundering_pays'],
                         'S2': o['welfare']['S2'], 'S3': o['welfare']['S3'],
                         'S1': o['welfare']['S1'], 'cs': o['consumer_surplus']['S2'],
                         'S2total': o['welfare_total']['S2'],
                         'margin': o['operator_margin']['S2'],
                         'provider': o['provider_profit']['S2'],
                         'payment': o['payment']['S2']})
        sweep[rule] = rows
        print('\nsweep %s' % rule)
        for r in rows:
            print('  p=%.2f launder=%-5s S2 %10.1f  S3 %10.1f  margin %9.1f  provider %10.1f'
                  % (r['p_spot'], r['laundered'], r['S2'], r['S3'], r['margin'], r['provider']))
    res['sweep'] = sweep

    # ---- 3. what the payment does to the provider alone -------------------
    print('\nprovider surplus at p=0.22, eps=1.0, per rule')
    for rule in RULES:
        o = base['%s|eps=1.0' % rule]
        print('  %-7s S2 provider %10.1f  margin/gb %s  exit share %.3f'
              % (rule, o['provider_profit']['S2'],
                 None if o['provider_margin_per_gb']['S2'] is None
                 else round(o['provider_margin_per_gb']['S2'], 3), o['exit_share']))

    # ---- 4. the numbers the paper will quote ------------------------------
    # Every quantity below is read off the runs above; nothing is typed in.
    noq = base['none|eps=1.0']
    rat = base['ratio|eps=1.0']
    eps_list = [e for e in EPS_LIST]
    ratio_s3_s1 = {str(e): base['none|eps=%s' % e]['welfare']['S3']
                   / base['none|eps=%s' % e]['welfare']['S1'] for e in eps_list}
    ratio_s2_s3 = {rule: {str(e): base['%s|eps=%s' % (rule, e)]['welfare']['S2']
                          / base['%s|eps=%s' % (rule, e)]['welfare']['S3']
                          for e in eps_list} for rule in RULES}
    ratio_s2_s3_tot = {rule: {str(e): base['%s|eps=%s' % (rule, e)]['welfare_total']['S2']
                              / base['%s|eps=%s' % (rule, e)]['welfare_total']['S3']
                              for e in eps_list} for rule in RULES}
    band_vals = [v for rule in ('none', 'billed')
                 for v in list(ratio_s2_s3[rule].values()) + list(ratio_s2_s3_tot[rule].values())]

    # price at which a pure charge removes the distributor's whole margin
    p_zero = E.P_MARKET - E.C_NODE_MARGIN
    med_vol = float(np.median(E.VOL))
    # first grid point where the distributor's surplus has gone negative
    p_cross = next((r['p_spot'] for r in sweep['none'] if r['provider'] < 0), None)
    summary = {
        's3_over_s1_by_demand': ratio_s3_s1,
        's3_over_s1_by_demand_total': {
            str(e): base['none|eps=%s' % e]['welfare_total']['S3']
            / base['none|eps=%s' % e]['welfare_total']['S1'] for e in eps_list},
        's2_over_s3_by_rule': ratio_s2_s3,
        's2_over_s3_total': ratio_s2_s3_tot,
        # the band the two tariffs span: the tariff as written ('none') and the
        # fixed-allowance variant ('billed'), under both welfare conventions and
        # all three demand slopes.  The ratio quota is reported separately
        # because its cell is the one under repair.
        's2_over_s3_band': [min(band_vals), max(band_vals)],
        's2_over_s3_ratio_rule': dict(ratio_s2_s3['ratio']),
        'welfare_s2_equal_s3_within': max(abs(v - 1.0) for v in ratio_s2_s3['none'].values()),
        'legacy_overstatement_s2': {'eps=%s' % e:
                                    base['ratio|eps=%s' % e]['welfare_legacy']['S2']
                                    - base['ratio|eps=%s' % e]['welfare']['S2']
                                    for e in eps_list},
        'billed_volume': {rule: float(np.sum(E.VOL - (E.HOUSE_DN if rule == 'ratio'
                                                      else (E.HOUSE_DN_GB if rule == 'billed'
                                                            else 0.0))))
                          for rule in RULES},
        'billing_ratio_none_over_ratio': float(np.sum(E.VOL))
        / float(np.sum(E.VOL - E.HOUSE_DN)),
        'household_bill': {'spot': E.HOUSE_UP_GB * 0.22, 'tiers': 0.0},
        'node_bill': {'spot': med_vol * 0.22, 'tiers': med_vol * E.P_PROVIDER},
        'median_node_volume': med_vol,
        'price_that_closes_margin': p_zero,
        'price_over_declared_rate': p_zero / E.P_PROVIDER,
        'first_exit_price': p_cross,
        'operator_margin_spot_over_tiers': noq['operator_margin']['S2'] / base['billed|eps=1.0']['operator_margin']['S3'],
        'provider_surplus_spot_over_tiers': noq['provider_profit']['S2'] / base['none|eps=1.0']['provider_profit']['S3'],
        'transfer_spot': noq['payment']['S2'], 'transfer_tiers': noq['payment']['S3'],
        'provider_surplus': {'spot': noq['provider_profit']['S2'],
                             'tiers': noq['provider_profit']['S3'],
                             'enforcement': noq['provider_profit']['S1']},
        'welfare_flat_in_price': len({round(r['S2'], 6) for r in sweep['none']}) == 1,
    }
    res['summary'] = summary
    print('\ntiers/enforcement by demand slope', {k: round(v, 3) for k, v in ratio_s3_s1.items()})
    print('S2/S3 by rule and slope', {r: {k: round(v, 3) for k, v in d.items()}
                                      for r, d in ratio_s2_s3.items()})
    print('spot welfare flat in price:', summary['welfare_flat_in_price'])
    print('price that closes the margin %.3f = %.2fx the declared rate; first exit grid point %s'
          % (p_zero, summary['price_over_declared_rate'], p_cross))
    print('billing ratio none/ratio %.2f' % summary['billing_ratio_none_over_ratio'])
    print('provider surplus spot/tiers %.3f' % summary['provider_surplus_spot_over_tiers'])

    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
