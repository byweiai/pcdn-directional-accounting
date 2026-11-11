# -*- coding: utf-8 -*-
"""Insert the E16 and E17 macro block into make_numbers.py.

Kept in its own script so the LaTeX-bearing file is never edited through a shell
string, and so the insertion can be asserted to happen exactly once.
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, 'make_numbers.py')

ANCHOR = "    # LaTeX control words cannot contain digits"

BLOCK = '''    # ---- E16: a line that consumes and distributes at once, E17: transfer
    e16 = load('e16_dualuse')
    m['eSixteenCells'] = si(e16['null']['n_cells'])
    m['eSixteenLines'] = f(e16['null']['n_lines'], 0)
    m['eSixteenBandLo'] = f(e16['null']['band'][0], 3)
    m['eSixteenBandHi'] = f(e16['null']['band'][1], 3)
    m['eSixteenNullMedian'] = f(e16['null']['median'], 4)
    m['eSixteenConsGb'] = f(e16['null']['cons_gb_per_month'], 0)
    rows16 = e16['rows']

    def pick(m_, run_, duty_):
        c = [r for r in rows16 if r['intensity'] == m_ and r['run'] == run_
             and abs(r['duty'] - duty_) < 1e-9]
        return c[0] if c else None

    shortest = [r for r in rows16 if r['run'] == 1]
    m['eSixteenThreeShortest'] = f(max(r['hit_three'] for r in shortest), 3)
    escaped = [r for r in rows16 if r['hit_three'] < 0.5]
    m['eSixteenThreeEscapePct'] = f(max(r['push_pct'] for r in escaped), 0)
    r10 = pick(10.0, 1, 0.10)
    m['eSixteenSieveShort'] = f(r10['hit_sieve'], 2)
    m['eSixteenWinShort'] = f(r10['hit_window'], 2)
    rq = pick(1.0, 1, 1.00)
    m['eSixteenQuotaShipPct'] = f(rq['push_pct'], 0)
    m['eSixteenQuotaSieve'] = f(rq['hit_sieve'], 2)
    m['eSixteenWinTenth'] = f(pick(1.0, 6, 0.10)['window'], 3)

    e17 = load('e17_transfer')
    tr = {(r['from'], r['to']): r for r in e17['transfer_mix']}
    m['eSeventeenWorstCal'] = f(e17['summary']['worst_calibrated_fp'], 2)
    m['eSeventeenWorstFixed'] = f(e17['summary']['worst_fixed_fp'], 4)
    m['eSeventeenTauHeavy'] = f(tr[('heavy', 'heavy')]['tau_cal'], 3)
    m['eSeventeenTauLight'] = f(tr[('light', 'light')]['tau_cal'], 3)
    m['eSeventeenHeavyOnLight'] = f(tr[('heavy', 'light')]['fp_cal'], 2)
    m['eSeventeenMidOnLight'] = f(tr[('mid', 'light')]['fp_cal'], 2)
    tb = [r['fp_cal'] for r in e17['transfer_block'] if r['from'] != r['to']]
    m['eSeventeenBlockWorst'] = f(max(tb), 3)
    prof = sorted(e17['profiles'], key=lambda p: p['scale'])
    m['eSeventeenProfileMax'] = f(prof[0]['p95'], 3)
    m['eSeventeenProfileMin'] = f(prof[-1]['p95'], 3)
    m['eSeventeenSpread'] = f(e17['summary']['calibrated_spread'], 2)
    m['eSeventeenFpLightest'] = f(prof[0]['fp_fixed'], 4)
    m['eSeventeenLightGb'] = f(prof[0]['cons_gb_month'], 0)
    m['eSeventeenHeavyGb'] = f(prof[-1]['cons_gb_month'], 0)

'''


def main():
    src = io.open(P, encoding='utf-8').read()
    assert src.count(ANCHOR) == 1, src.count(ANCHOR)
    assert 'eSixteenCells' not in src
    src = src.replace(ANCHOR, BLOCK + ANCHOR)
    io.open(P, 'w', encoding='utf-8').write(src)
    print('inserted E16/E17 macro block')


if __name__ == '__main__':
    main()
