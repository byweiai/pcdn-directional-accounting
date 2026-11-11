# -*- coding: utf-8 -*-
"""E5: three regimes -- enforcement, spot pricing, and declared service tiers.

Revision 2 (gate response).  Three changes, all of them from the review:

  R1  welfare is now reported as a decomposition and is tested against demand
      response.  In revision 1 welfare was a fixed per-gigabyte surplus times
      served volume, so the ratio between regimes was the volume ratio by
      construction.  The decomposition below makes that visible (column
      "transfer"), and the demand block prices the extra volume through a linear
      demand curve, so the ratio a reader sees is either explicitly the volume
      ratio or explicitly a market-clearing one with its elasticity named.
  R4  the quota may count only contracted downlink.  Revision 1 tied the quota to
      observed downlink, so buying downlink raised the ceiling one for one and the
      spot price collapsed whenever it exceeded the downlink price.  Both rules
      are reported; under the billed-only rule the wash is self-defeating, and S3
      gains an explicit wash branch whose crossover volume is computed.
  R6  the non-distributor population is instantiated rather than assumed.  The
      false-alarm rate is measured on 20,000 households drawn from the measured
      ratio distribution, and the host-level bound is reported as the rule of
      three applied to the number of addresses actually available.

Parameter provenance, fixed before the run:
  DET_TPR 0.84                      a market input, below the 0.993 held-out capture
  QUOTA_FP 0.0000                   E1 quota scan at rho_0 = 1
  EVASION 1.5x extra downlink       E2 dilution to alpha = 0.4
  HOUSE_UP 12 GB, HOUSE_DN 220 GB   consumer norm used as trigger reference
  E_UPLINK 0.06, LAMBDA_CAP 0.04    congestion externality and capacity shadow
  P_MARKET 0.35                     what the platform pays per redistributed GB
  WASH_DOWN 1.0 GB per GB shipped   E18: the cheapest escape, at 1:1
  HOUSE_RHO_MED 0.0904, P95 0.1392  measured subscriber-cell ratio, E15/E16
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e5_regime.json')

N_ENDPOINTS = 20000
SHARE_PROVIDER = 0.04

CAP_UP_MBPS = 30.0
CAP_DN_MBPS = 1000.0
SLA_UP_MBPS = 2.0
GB_PER_MBPS_MONTH = 324.0
CONSUMER_UPLINK_CAP_GB = SLA_UP_MBPS * GB_PER_MBPS_MONTH   # 648 GB

HOUSE_UP_GB = 12.0
HOUSE_DN_GB = 220.0

E_UPLINK = 0.06
LAMBDA_CAP = 0.04
P_MARKET = 0.35
C_NODE_MARGIN = 0.02
P_PROVIDER = 0.12
DL_PRICE = 0.10

EVASION_ALPHA = 0.40
EVASION_EXTRA_DOWN = (1 - EVASION_ALPHA) / EVASION_ALPHA
EVASION_COST = EVASION_EXTRA_DOWN * DL_PRICE

WASH_DOWN = 1.0            # GB of genuine downlink per GB shipped (E18)
WASH_COST = WASH_DOWN * DL_PRICE

DET_TPR = 0.84
QUOTA_FP = 0.0000
RHO_TRIGGER = 0.5
UP_TRIGGER_X = 5.0
DN_TRIGGER_X = 5.0

HOUSE_RHO_MED = 0.0904     # measured, 1,420 subscriber cells (E13/E16)
HOUSE_RHO_P95 = 0.1392
HOUSE_N = 20000

EPS_GRID = [0.5, 1.0]
PRICE_FIXED = True         # the revision-1 benchmark row: price held at P_MARKET

RNG = np.random.default_rng(20261106)
_N = int(N_ENDPOINTS * SHARE_PROVIDER)
VOL = np.exp(RNG.normal(np.log(900.0), 0.9, _N))
CAUGHT_U = RNG.random(_N)
CAUGHT = CAUGHT_U < DET_TPR
HOUSE_DN = RNG.lognormal(np.log(HOUSE_DN_GB), 0.35, _N)

# non-distributor households: ratio drawn from the measured cell distribution
_RHO_SIGMA = np.log(HOUSE_RHO_P95 / HOUSE_RHO_MED) / 1.645
RHO_HOUSE = RNG.lognormal(np.log(HOUSE_RHO_MED), _RHO_SIGMA, HOUSE_N)
UP_HOUSE = RNG.lognormal(np.log(HOUSE_UP_GB), 0.5, HOUSE_N)


def _cs(q, q_ref, eps):
    """Consumer surplus at the market-clearing price for served volume q.

    Linear demand pinned to (P_MARKET, q_ref) with elasticity eps at that point:
    slope B = eps * q_ref / P_MARKET, intercept A = q_ref + B * P_MARKET.
    """
    if eps is None:
        return 0.0, P_MARKET
    B = eps * q_ref / P_MARKET
    A = q_ref + B * P_MARKET
    q_clear = min(q, A)
    p = max(0.0, (A - q_clear) / B)
    return q_clear * q_clear / (2.0 * B), p


def outcomes(p_spot, p_provider=P_PROVIDER, evasion_cost=EVASION_COST, det_tpr=None,
             quota_rule='ratio', eps=None, wash=False, wash_cost=None):
    if wash_cost is None:
        wash_cost = WASH_COST
    vol = VOL
    dn = HOUSE_DN
    caught = CAUGHT if det_tpr is None else (CAUGHT_U < det_tpr)

    # ---- S1: classify and cut off ---------------------------------------
    kept_s1 = ~caught
    s1_served = float(np.sum(vol[kept_s1]))
    s1_provider = float(np.sum(vol[kept_s1] * (P_MARKET - C_NODE_MARGIN)))
    s1_operator = 0.0
    s1_harm = s1_served * (E_UPLINK + LAMBDA_CAP)

    # ---- S2: quota tied to downlink, then bill above it ------------------
    # quota_rule 'ratio'  : observed downlink sets the ceiling (revision 1)
    # quota_rule 'billed' : only the contracted downlink sets it, so bytes the
    #                       endpoint buys do not buy it a higher ceiling
    quota = dn if quota_rule == 'ratio' else np.full_like(dn, HOUSE_DN_GB)
    billable = np.maximum(0.0, vol - quota)
    launders = (evasion_cost < p_spot) and quota_rule == 'ratio'
    if launders:
        cost_s2 = billable * evasion_cost
        billed_s2 = np.zeros_like(billable)
        extra_dn = billable
    else:
        cost_s2 = billable * p_spot
        billed_s2 = billable
        extra_dn = np.zeros_like(billable)
    s2_provider = float(np.sum(vol * (P_MARKET - C_NODE_MARGIN) - cost_s2))
    s2_operator = float(np.sum(billed_s2) * (p_spot - E_UPLINK - LAMBDA_CAP))
    s2_served = float(np.sum(vol))
    s2_harm = (float(np.sum(vol - billed_s2)) + float(np.sum(extra_dn))) * (E_UPLINK + LAMBDA_CAP)

    # ---- S3: declared tiers ---------------------------------------------
    ratio = vol / (vol + dn)
    over = ratio > RHO_TRIGGER
    material = vol > UP_TRIGGER_X * HOUSE_UP_GB
    tripped = over & material
    gross_under_quota = (dn > DN_TRIGGER_X * HOUSE_DN_GB) & ~over
    served_consumer = np.minimum(vol, CONSUMER_UPLINK_CAP_GB)

    profit_c = served_consumer * (P_MARKET - C_NODE_MARGIN)
    profit_d = vol * (P_MARKET - C_NODE_MARGIN - p_provider)

    # wash branch (R4): buy downlink to hide, at 1:1, and stay capped by the
    # consumer ceiling.  Profit per shipped GB is higher, the ceiling is lower;
    # the crossover is reported below.
    profit_wash = np.minimum(vol, CONSUMER_UPLINK_CAP_GB) * (P_MARKET - C_NODE_MARGIN - wash_cost)
    if wash:
        profit_d = np.maximum(profit_d, 0.0)
        declare = tripped & (profit_d > np.maximum(profit_c, profit_wash)) & (profit_d > 0)
        stay_c = tripped & ~declare & (profit_wash > profit_c)
        served_s3 = np.where(declare, vol, np.where(stay_c, np.minimum(vol, CONSUMER_UPLINK_CAP_GB),
                                                    served_consumer))
    else:
        declare = tripped & (profit_d > profit_c) & (profit_d > 0)
        stay_c = np.zeros_like(declare)
        served_s3 = np.where(declare, vol, served_consumer)

    s3_provider = float(np.sum(np.where(declare, profit_d,
                                        np.where(stay_c, profit_wash, profit_c))))
    s3_operator = float(np.sum(np.where(declare, vol * (p_provider - E_UPLINK - LAMBDA_CAP), 0.0)))
    s3_harm = float(np.sum(np.where(declare, 0.0, served_s3))) * (E_UPLINK + LAMBDA_CAP)

    served = {'S1': s1_served, 'S2': s2_served, 'S3': float(np.sum(served_s3))}
    margin = {'S1': s1_operator, 'S2': s2_operator, 'S3': s3_operator}
    harm = {'S1': s1_harm, 'S2': s2_harm, 'S3': s3_harm}

    # ---- market clearing -------------------------------------------------
    # Each regime's served volume is priced by the same linear demand curve.
    # Endpoints decide at the market price they observe (P_MARKET); the clearing
    # price that follows from the aggregate volume is then applied to revenue and
    # to consumer surplus, so the two sides of the ledger use one price.
    cs, price, profit, transfer, welfare = {}, {}, {}, {}, {}
    declared_gb = float(np.sum(vol[declare]))
    for k in served:
        cs[k], price[k] = _cs(served[k], served['S2'], eps)
        p = price[k]
        if k == 'S3':
            profit[k] = served[k] * (p - C_NODE_MARGIN) - declared_gb * p_provider
        else:
            profit[k] = served[k] * (p - C_NODE_MARGIN)
        transfer[k] = profit[k] + margin[k] - harm[k]
        welfare[k] = transfer[k] + cs[k]

    return {
        'p_spot': p_spot, 'p_provider': p_provider, 'evasion_cost': evasion_cost,
        'quota_rule': quota_rule, 'eps': eps, 'wash_branch': wash,
        'laundering_pays': bool(launders),
        'tripped_share_of_base': float(tripped.sum() / N_ENDPOINTS),
        'tripped_share_of_providers': float(tripped.mean()),
        'gross_downlink_under_quota': float(gross_under_quota.mean()),
        'registration_rate': float(declare.mean()),
        'wash_choosers': float(stay_c.mean()),
        'disclosed_volume_share': float(np.sum(vol[declare]) / max(1e-9, np.sum(vol))),
        'provider_profit': profit,
        'operator_margin': margin,
        'unpriced_harm': harm,
        'welfare': welfare,
        'welfare_transfer': transfer,
        'consumer_surplus': cs,
        'price': price,
        'volume_served': served,
        'harm_per_gb_served': {k: harm[k] / max(1e-9, served[k]) for k in served},
        'collateral_billing': float(N_ENDPOINTS * QUOTA_FP * HOUSE_DN_GB * 2 * p_spot),
    }


def household_block():
    """R6: instantiate the non-distributor population instead of assuming it."""
    tripped = (RHO_HOUSE > RHO_TRIGGER) & (UP_HOUSE > UP_TRIGGER_X * HOUSE_UP_GB)
    n_trip = int(tripped.sum())
    n_hosts = 30          # 10 subscriber and 20 service addresses in the panel
    return {
        'households': HOUSE_N,
        'rho_median': float(np.median(RHO_HOUSE)),
        'rho_p95': float(np.percentile(RHO_HOUSE, 95)),
        'false_alarm_cells': n_trip / HOUSE_N,
        'false_alarm_count': n_trip,
        'rule_of_three_cells': 3.0 / 1420.0,
        'rule_of_three_hosts': 3.0 / n_hosts,
        'hosts': n_hosts,
        'share_untouched': 1.0 - n_trip / HOUSE_N,
    }


def volume_trigger_block():
    """X06: the same floor, the same ceiling, no directional test.

    The trigger becomes ``volume above UP_TRIGGER_X * HOUSE_UP_GB`` alone;
    everything downstream -- declared rate, consumer ceiling, pricing -- is
    unchanged, so the two rules differ only in who is asked.  Reporting both is
    the cheapest way to show what the directional test actually buys.
    """
    floor_gb = UP_TRIGGER_X * HOUSE_UP_GB
    ratio = VOL / (VOL + HOUSE_DN)
    over = ratio > RHO_TRIGGER
    material = VOL > floor_gb
    served_consumer = np.minimum(VOL, CONSUMER_UPLINK_CAP_GB)
    profit_c = served_consumer * (P_MARKET - C_NODE_MARGIN)
    profit_d = VOL * (P_MARKET - C_NODE_MARGIN - P_PROVIDER)

    def branch(tripped):
        declare = tripped & (profit_d > profit_c) & (profit_d > 0)
        served = np.where(declare, VOL, served_consumer)
        return {
            'registration': float(declare.mean()),
            'served': float(np.sum(served)),
            'operator_margin': float(np.sum(np.where(declare, VOL * (P_PROVIDER - E_UPLINK - LAMBDA_CAP), 0.0))),
            'unpriced_harm': float(np.sum(np.where(declare, 0.0, served))) * (E_UPLINK + LAMBDA_CAP),
            'lines_asked': int(tripped.sum()),
        }

    ratio_b = branch(over & material)
    volume_b = branch(material)
    fa_ratio = float(((RHO_HOUSE > RHO_TRIGGER) & (UP_HOUSE > floor_gb)).mean())
    fa_volume = float((UP_HOUSE > floor_gb).mean())
    same = all(abs(ratio_b[k] - volume_b[k]) < 1e-9
               for k in ('registration', 'served', 'operator_margin', 'unpriced_harm'))
    return {
        'floor_gb': floor_gb,
        'ratio_trigger': ratio_b,
        'volume_trigger': volume_b,
        'same_provider_outcome': bool(same),
        'lines_asked_extra': volume_b['lines_asked'] - ratio_b['lines_asked'],
        'household_false_alarm_ratio': fa_ratio,
        'household_false_alarm_volume': fa_volume,
        'households_asked_ratio': fa_ratio * HOUSE_N,
        'households_asked_volume': fa_volume * HOUSE_N,
        'households_asked_extra': (fa_volume - fa_ratio) * HOUSE_N,
        'washers': int((material & ~over).sum()),
    }


def wash_block():
    """R4: the wash branch, priced and bounded."""
    per_gb_declare = P_MARKET - C_NODE_MARGIN - P_PROVIDER
    per_gb_wash = P_MARKET - C_NODE_MARGIN - WASH_COST
    cap = CONSUMER_UPLINK_CAP_GB
    # crossover: declaring beats washing above this monthly volume
    v_star = per_gb_wash * cap / per_gb_declare
    return {
        'per_gb_declare': per_gb_declare,
        'per_gb_wash': per_gb_wash,
        'wash_cap_gb': cap,
        'crossover_gb': float(v_star),
        'trigger_floor_gb': UP_TRIGGER_X * HOUSE_UP_GB,
        'crossover_over_floor': float(v_star / (UP_TRIGGER_X * HOUSE_UP_GB)),
        'share_above_crossover': float((VOL > v_star).mean()),
        'wash_self_defeating': bool(v_star < float(np.median(VOL)) * 3),
    }


def wash_scan():
    """X03: does any price of camouflage produce an endpoint that buys it?

    The wash branch competes with compliance at the same ceiling: a subscriber
    line caps shipped volume at CONSUMER_UPLINK_CAP_GB whether or not the node
    buys downlink to look ordinary.  Camouflage therefore cannot raise the
    ceiling, and its only effect on profit is the cost.  The scan shows that no
    price in the grid makes it worth choosing, and how far the chosen regime's
    profit would have to rise for it to appear.
    """
    rows = []
    for wc in [round(0.02 * i, 2) for i in range(1, 16)]:
        r = outcomes(0.22, eps=1.0, wash=True, wash_cost=wc)
        rows.append({
            'wash_cost': wc,
            'wash_choosers': r['wash_choosers'],
            'registration': r['registration_rate'],
            'volume_served': r['volume_served']['S3'],
            'per_gb_wash': P_MARKET - C_NODE_MARGIN - wc,
            'per_gb_compliant': P_MARKET - C_NODE_MARGIN,
        })
    return {
        'rows': rows,
        'any_chooser': bool(any(x['wash_choosers'] > 0 for x in rows)),
        'max_cost_scanned': rows[-1]['wash_cost'],
        'min_cost_scanned': rows[0]['wash_cost'],
        'ceiling_gb': CONSUMER_UPLINK_CAP_GB,
        'per_gb_compliant': P_MARKET - C_NODE_MARGIN,
        'per_gb_declare': P_MARKET - C_NODE_MARGIN - P_PROVIDER,
    }


def demand_block():
    """R1: welfare with and without a demand response."""
    rows = []
    for eps in [None] + EPS_GRID:
        r = outcomes(0.22, eps=eps)
        rows.append({
            'eps': eps,
            'welfare': r['welfare'],
            'consumer_surplus': r['consumer_surplus'],
            'price': r['price'],
            'volume_served': r['volume_served'],
            'ratio': r['welfare']['S3'] / max(1e-9, r['welfare']['S1']),
            'transfer_ratio': r['welfare_transfer']['S3'] / max(1e-9, r['welfare_transfer']['S1']),
            'volume_ratio': r['volume_served']['S3'] / max(1e-9, r['volume_served']['S1']),
            # The share of the welfare *gain* that lands on the producer side
            # (margin, profit and congestion no longer borne).  The ratio of the
            # two ratios is not that share: it divides two levels by two other
            # levels and is scale-free, so it answers no question about where the
            # gain goes.
            'gain_share': (r['welfare_transfer']['S3'] - r['welfare_transfer']['S1'])
                          / max(1e-9, r['welfare']['S3'] - r['welfare']['S1']),
            'cs_gain_share': (r['consumer_surplus']['S3'] - r['consumer_surplus']['S1'])
                             / max(1e-9, r['welfare']['S3'] - r['welfare']['S1']),
        })
    return rows


def sweep_block():
    """R13: where the ranking flips, on a grid fine enough to see the step."""
    rows = []
    for p in np.round(np.arange(0.04, 0.301, 0.02), 2):
        r = outcomes(float(p), eps=1.0)
        rows.append({'p_spot': float(p),
                     'laundering_pays': bool(r['laundering_pays']),
                     'identity_holds': bool(r['laundering_pays'] == (EVASION_COST < p)),
                     'welfare_S1': r['welfare']['S1'],
                     'welfare_S2': r['welfare']['S2'],
                     'welfare_S3': r['welfare']['S3'],
                     'margin_S2': r['operator_margin']['S2'],
                     'registration_rate': r['registration_rate']})
    flip = next((r['p_spot'] for r in rows if r['laundering_pays']), None)
    last_pay = max((r['p_spot'] for r in rows if not r['laundering_pays']), default=None)
    return {'rows': rows,
            'first_laundering_spot': flip,
            'last_paying_spot': last_pay,
            'evasion_cost': EVASION_COST,
            'identity_all': all(r['identity_holds'] for r in rows),
            'welfare_S2_below': max(r['welfare_S2'] for r in rows if r['laundering_pays']),
            'welfare_S2_above': min(r['welfare_S2'] for r in rows if not r['laundering_pays'])}


def sweep_wash_block():
    """R13, second grid: the same sweep with the cost E18 measured.

    E18 prices hiding at parity, one byte of genuine downlink per byte shipped,
    so the cost of evasion is DL_PRICE rather than the shape-based 1.5 bytes.
    The block reports where the step falls relative to the price at which the
    operator's margin is zero, because the gap between the two is the room the
    regime has to price in without being evaded.
    """
    rows = []
    for p in np.round(np.arange(0.04, 0.301, 0.02), 2):
        r = outcomes(float(p), eps=1.0, evasion_cost=WASH_COST)
        rows.append({'p_spot': float(p),
                     'laundering_pays': bool(r['laundering_pays']),
                     'identity_holds': bool(r['laundering_pays'] == (WASH_COST < p)),
                     'welfare_S2': r['welfare']['S2'],
                     'welfare_S3': r['welfare']['S3'],
                     'margin_S2': r['operator_margin']['S2']})
    flip = next((r['p_spot'] for r in rows if r['laundering_pays']), None)
    zero_margin = E_UPLINK + LAMBDA_CAP
    return {'rows': rows,
            'first_laundering_spot': flip,
            'evasion_cost': WASH_COST,
            'zero_margin_price': zero_margin,
            'headroom': (flip - zero_margin) if flip is not None else None,
            'identity_all': all(r['identity_holds'] for r in rows)}


def main():
    print('== E5: enforcement vs spot pricing vs declared tiers (rev 2) ==')
    print('  %d endpoints, %d potential providers, median volume %.0f GB/month'
          % (N_ENDPOINTS, _N, np.median(VOL)))
    print('  household: uplink %.0f GB, downlink median %.0f GB; consumer SLA uplink %.0f GB/month'
          % (HOUSE_UP_GB, np.median(HOUSE_DN), CONSUMER_UPLINK_CAP_GB))
    print('  trigger: rho>%.2f AND uplink>%.0fx household (%.0f GB/month)'
          % (RHO_TRIGGER, UP_TRIGGER_X, UP_TRIGGER_X * HOUSE_UP_GB))
    print('  disguise %.2fx extra downlink costs %.3f CNY/GB (E2); wash %.1f GB/GB costs %.3f (E18)'
          % (EVASION_EXTRA_DOWN, EVASION_COST, WASH_DOWN, WASH_COST))

    print('\n  -- R1 demand response: ratio of welfare S3/S1 --')
    dem = demand_block()
    for r in dem:
        print('    eps %-4s  welfare S1 %9.1f  S3 %9.1f  ratio %5.2f  '
              '(transfer %5.2f, volume %5.2f)  CS S3 %8.1f'
              % ('none' if r['eps'] is None else '%.1f' % r['eps'],
                 r['welfare']['S1'], r['welfare']['S3'], r['ratio'],
                 r['transfer_ratio'], r['volume_ratio'],
                 r['consumer_surplus']['S3']))

    print('\n  -- R4 quota rule: does the spot price still collapse? --')
    qrows = []
    for rule in ('ratio', 'billed'):
        for p in (0.06, 0.12, 0.16, 0.22, 0.30):
            r = outcomes(p, quota_rule=rule)
            qrows.append({'rule': rule, 'p_spot': p,
                          'laundering_pays': r['laundering_pays'],
                          'operator_margin_S2': r['operator_margin']['S2'],
                          'billed_gb': float(np.sum(np.maximum(0.0, VOL - (HOUSE_DN if rule == 'ratio'
                                                                          else HOUSE_DN_GB))))})
            print('    %-6s spot %.2f -> %-9s S2 margin %9.1f'
                  % (rule, p, 'launders' if r['laundering_pays'] else 'pays',
                     r['operator_margin']['S2']))

    wsc = wash_scan()
    print('\n  -- X03 wash scan: price of camouflage %.2f..%.2f CNY/GB, any chooser: %s'
          % (wsc['min_cost_scanned'], wsc['max_cost_scanned'], wsc['any_chooser']))
    for x in wsc['rows'][:3] + wsc['rows'][-2:]:
        print('     wash %.2f: per GB %.3f vs compliant %.3f, choosers %.4f, registration %.3f'
              % (x['wash_cost'], x['per_gb_wash'], x['per_gb_compliant'],
                 x['wash_choosers'], x['registration']))
    print('\n  -- R4 wash branch under S3 --')
    wb = wash_block()
    rw = outcomes(0.22, eps=1.0, wash=True)
    print('    per GB: declare %.3f, wash %.3f; wash capped at %.0f GB'
          % (wb['per_gb_declare'], wb['per_gb_wash'], wb['wash_cap_gb']))
    print('    crossover %.0f GB/month = %.2fx the trigger floor; %.1f%% of providers above it'
          % (wb['crossover_gb'], wb['crossover_over_floor'], 100 * wb['share_above_crossover']))
    print('    with the wash branch: registration %.1f%%, volume served %.0f, welfare %.0f'
          % (100 * rw['registration_rate'], rw['volume_served']['S3'], rw['welfare']['S3']))

    print('\n  -- R6 household population --')
    hb = household_block()
    print('    %d households, ratio median %.4f p95 %.4f' % (hb['households'], hb['rho_median'],
                                                            hb['rho_p95']))
    print('    false alarms %d (%.5f); rule of three: cells %.5f, hosts %.4f'
          % (hb['false_alarm_count'], hb['false_alarm_cells'],
             hb['rule_of_three_cells'], hb['rule_of_three_hosts']))

    print('\n  -- X06 volume-only trigger, same floor and ceiling --')
    vb = volume_trigger_block()
    print('    floor %.0f GB: ratio rule asks %.0f lines, volume rule %.0f (extra %d)'
          % (vb['floor_gb'], vb['ratio_trigger']['lines_asked'],
             vb['volume_trigger']['lines_asked'], vb['lines_asked_extra']))
    print('    provider side identical: %s  (margin %.1f vs %.1f, harm %.1f vs %.1f)'
          % (vb['same_provider_outcome'], vb['ratio_trigger']['operator_margin'],
             vb['volume_trigger']['operator_margin'], vb['ratio_trigger']['unpriced_harm'],
             vb['volume_trigger']['unpriced_harm']))
    print('    households asked: ratio %.1f, volume %.1f per %d (extra %.1f); washers in the field %d'
          % (vb['households_asked_ratio'], vb['households_asked_volume'], HOUSE_N,
             vb['households_asked_extra'], vb['washers']))

    print('\n  -- spot price sweep (ratio-tied quota, the revision-1 rule) --')
    grid = []
    for p_spot in [0.06, 0.08, 0.10, 0.12, 0.16, 0.22, 0.30]:
        r = outcomes(p_spot, eps=1.0)
        grid.append(r)
        print('    spot %.2f%s -> declare %5.1f%% welfare S1 %8.0f S3 %8.0f'
              % (p_spot, ' launders' if r['laundering_pays'] else '',
                 100 * r['registration_rate'], r['welfare']['S1'], r['welfare']['S3']))

    print('\n  -- provider rate sweep at spot 0.22 --')
    pr = []
    for p in [0.08, 0.10, 0.12, 0.14, 0.16, 0.20, 0.25]:
        r = outcomes(0.22, p_provider=p, eps=1.0)
        pr.append({'p_provider': p, 'registration_rate': r['registration_rate'],
                   'operator_margin_S3': r['operator_margin']['S3'],
                   'welfare_S3': r['welfare']['S3'],
                   'welfare_S3_transfer': r['welfare_transfer']['S3'],
                   'disclosed_volume_share': r['disclosed_volume_share'],
                   'tripped_share_of_base': r['tripped_share_of_base']})
        print('    rate %.2f -> declare %5.1f%%  S3 margin %8.0f  welfare %8.0f  disclosed %5.1f%%'
              % (p, 100 * r['registration_rate'], r['operator_margin']['S3'],
                 r['welfare']['S3'], 100 * r['disclosed_volume_share']))

    print('\n  -- evasion cost sweep --')
    ev = []
    for ec in [0.00, 0.02, 0.05, 0.10, 0.15, 0.25, 0.50]:
        r = outcomes(0.22, evasion_cost=ec, eps=1.0)
        ev.append({'evasion_cost': ec, 'laundering_pays': r['laundering_pays'],
                   'operator_margin_S2': r['operator_margin']['S2'],
                   'operator_margin_S3': r['operator_margin']['S3'],
                   'welfare_S2': r['welfare']['S2'], 'welfare_S3': r['welfare']['S3'],
                   'registration_rate': r['registration_rate']})
        print('    cost %.2f -> %-9s S2 margin %9.0f  S3 margin %8.0f | welfare S2 %8.0f S3 %8.0f'
              % (ec, 'launders' if r['laundering_pays'] else 'pays',
                 r['operator_margin']['S2'], r['operator_margin']['S3'],
                 r['welfare']['S2'], r['welfare']['S3']))

    print('\n  -- R13 spot price sweep, fine enough to see the step --')
    sw = sweep_block()
    sww = sweep_wash_block()
    for row in sw['rows']:
        print('    spot %.2f -> %-9s S1 %8.0f S2 %8.0f S3 %8.0f  margin S2 %8.0f'
              % (row['p_spot'], 'launders' if row['laundering_pays'] else 'pays',
                 row['welfare_S1'], row['welfare_S2'], row['welfare_S3'], row['margin_S2']))
    print('    the step sits between %.2f and %.2f, bracketing the evasion cost %.2f'
          ' (identity holds everywhere: %s)'
          % (sw['last_paying_spot'], sw['first_laundering_spot'],
             sw['evasion_cost'], sw['identity_all']))

    base = outcomes(0.22, eps=1.0)
    print('\n  base case, spot 0.22, provider rate 0.12, eps 1.0:')
    for k in ('provider_profit', 'operator_margin', 'unpriced_harm', 'welfare',
              'welfare_transfer', 'consumer_surplus', 'volume_served', 'harm_per_gb_served'):
        d = base[k]
        print('    %-19s S1 %10.1f   S2 %10.1f   S3 %10.1f' % (k, d['S1'], d['S2'], d['S3']))
    print('    tripped %.2f%% of the base, %.1f%% of providers; declared %.1f%%; disclosed volume %.1f%%'
          % (100 * base['tripped_share_of_base'], 100 * base['tripped_share_of_providers'],
             100 * base['registration_rate'], 100 * base['disclosed_volume_share']))

    cover = {}
    for p in (0.06, 0.08, 0.10, 0.12, 0.16, 0.20, 0.25):
        r = outcomes(0.22, p_provider=p, eps=1.0)
        cover['%.2f' % p] = {'disclosed': r['disclosed_volume_share'],
                             'served': r['volume_served']['S3'],
                             'harm': r['unpriced_harm']['S3']}
    print('\n  coverage under S3 as the provider rate rises:')
    for k, v in cover.items():
        print('    rate %s -> disclosed %5.1f%% of volume, harm %8.0f'
              % (k, 100 * v['disclosed'], v['harm']))

    out = {'params': {'N_ENDPOINTS': N_ENDPOINTS, 'SHARE_PROVIDER': SHARE_PROVIDER,
                      'CAP_UP_MBPS': CAP_UP_MBPS, 'CAP_DN_MBPS': CAP_DN_MBPS,
                      'SLA_UP_MBPS': SLA_UP_MBPS,
                      'CONSUMER_UPLINK_CAP_GB': CONSUMER_UPLINK_CAP_GB,
                      'HOUSE_UP_GB': HOUSE_UP_GB, 'HOUSE_DN_GB': HOUSE_DN_GB,
                      'E_UPLINK': E_UPLINK, 'LAMBDA_CAP': LAMBDA_CAP,
                      'P_MARKET': P_MARKET, 'C_NODE_MARGIN': C_NODE_MARGIN,
                      'P_PROVIDER': P_PROVIDER, 'DL_PRICE': DL_PRICE,
                      'EVASION_ALPHA': EVASION_ALPHA,
                      'EVASION_EXTRA_DOWN': EVASION_EXTRA_DOWN,
                      'EVASION_COST': EVASION_COST, 'DET_TPR': DET_TPR,
                      'QUOTA_FP': QUOTA_FP, 'RHO_TRIGGER': RHO_TRIGGER,
                      'UP_TRIGGER_X': UP_TRIGGER_X, 'DN_TRIGGER_X': DN_TRIGGER_X,
                      'WASH_DOWN': WASH_DOWN, 'WASH_COST': WASH_COST,
                      'HOUSE_RHO_MED': HOUSE_RHO_MED, 'HOUSE_RHO_P95': HOUSE_RHO_P95,
                      'HOUSE_N': HOUSE_N, 'EPS_GRID': EPS_GRID,
                      'BASE_EPS': 1.0, 'BASE_SPOT': 0.22},
           'base': base, 'grid': grid, 'provider_rate': pr, 'evasion': ev,
           'coverage': cover, 'demand': dem, 'quota_rule': qrows,
           'wash': wb, 'wash_run': rw, 'sweep_wash': sww, 'wash_scan': wsc, 'household': hb, 'sweep': sw,
           'volume_trigger': vb}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()

