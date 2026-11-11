# -*- coding: utf-8 -*-
"""Figure 12: what each rule can still see when the line is a customer and a
distributor at once, and what happens to a fitted threshold across operators.

Rendered on its own canvas so the width is exactly FULL inches and the figure is
inserted at 1:1 without a tight bounding box.
"""
import os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import gridspec

from make_figs import (FIG, FULL, INK, BLUE, BLUE3, BLUE4, WARM, load, tidy, tag)


def main():
    e16 = load('e16_dualuse.json')
    e17 = load('e17_transfer.json')
    rows = e16['rows']

    fig = plt.figure(figsize=(FULL, 2.46))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1.30, 1.00, 1.12], wspace=0.44,
                           left=0.058, right=0.988, top=0.845, bottom=0.255)

    # (a) each rule is defeated by something different
    axa = fig.add_subplot(gs[0, 0])
    series = [('hit_window', 'window', 'o', BLUE3, 9),
              ('hit_three', 'three windows', 's', BLUE, 9),
              ('hit_sieve', 'SIEVE', '^', WARM, 12)]
    for key, lab, mk, col, s in series:
        x = np.array([max(r['push_pct'], 0.4) for r in rows])
        y = np.array([r[key] for r in rows])
        axa.scatter(x, y, marker=mk, s=s, facecolor=col, edgecolor='white',
                    linewidth=0.4, alpha=0.85, label=lab, zorder=3)
    axa.set_xscale('log')
    axa.set_xlim(0.35, 420)
    axa.set_ylim(-0.07, 1.14)
    axa.set_xlabel("volume shipped, % of the line's own download", fontsize=6.9)
    axa.set_ylabel('lines decided against', fontsize=6.9)
    axa.set_yticks([0, 0.5, 1.0])
    axa.set_xticks([1, 10, 100])
    axa.set_xticklabels(['1', '10', '100'], fontsize=6.2)
    axa.tick_params(labelsize=6.2)
    axa.grid(axis='y', color=BLUE4, linewidth=0.4, linestyle=(0, (1, 2)))
    axa.set_axisbelow(True)
    legg = axa.legend(loc='center right', bbox_to_anchor=(0.99, 0.45), frameon=True,
                      facecolor='white', edgecolor='none', framealpha=0.92,
                      fontsize=6.1, handletextpad=0.3, borderpad=0.18,
                      labelspacing=0.25)
    for t in legg.get_texts():
        t.set_color(INK)
    tidy(axa)
    tag(axa, 'a', dx=-0.17)
    axa.set_title('one quantity, three rules', loc='left', pad=4, fontsize=7.0)

    # (b) a fitted threshold does not travel between subscriber mixes
    axb = fig.add_subplot(gs[0, 1])
    names = ['light', 'mid', 'heavy']
    for r in e17['transfer_mix']:
        i, j = names.index(r['from']), names.index(r['to'])
        v = r['fp_cal']
        axb.scatter(j, i, s=5 + 480 * v, facecolor=WARM if v > 0.02 else BLUE4,
                    edgecolor=INK, linewidth=0.4, alpha=0.9, zorder=3)
        if v > 0.45:
            axb.text(j, i, '%.2f' % v, ha='center', va='center', fontsize=5.9,
                     color='white', zorder=4)
        else:
            axb.text(j + 0.26, i, '%.2f' % v, ha='left', va='center', fontsize=5.9,
                     color=INK, zorder=4)
    axb.set_xlim(-0.62, 2.62)
    axb.set_ylim(-0.62, 2.62)
    axb.set_xticks(range(3))
    axb.set_yticks(range(3))
    axb.set_xticklabels(names, fontsize=6.2)
    axb.set_yticklabels(names, fontsize=6.2)
    axb.set_xlabel('applied to', fontsize=6.9)
    axb.set_ylabel('calibrated on', fontsize=6.9)
    for k in range(3):
        axb.plot([k - 0.5, k + 0.5], [k - 0.5, k + 0.5], color=BLUE3, linewidth=0.7,
                 linestyle=(0, (2, 2)), zorder=1)
    axb.text(0.97, 0.975, 'the fixed rule: zero in all nine',
             transform=axb.transAxes, fontsize=5.9, color=INK, style='italic',
             ha='right', va='top')
    tidy(axb)
    tag(axb, 'b', dx=-0.26)
    axb.set_title('false alarms, fitted threshold', loc='left', pad=4, fontsize=7.0)

    # (c) the fitted threshold moves with the operator, the rule does not
    axc = fig.add_subplot(gs[0, 2])
    prof = e17['profiles']
    x = np.array([p['cons_gb_month'] for p in prof])
    y = np.array([p['p95'] for p in prof])
    axc.scatter(x, y, s=26, facecolor=BLUE, edgecolor='white', linewidth=0.6, zorder=3)
    offs = {0.25: (6, -2), 0.5: (6, 2), 1.0: (6, 3), 2.0: (-2, 7), 4.0: (-14, 7)}
    for p in prof:
        axc.annotate('s=%.2f' % p['scale'], (p['cons_gb_month'], p['p95']),
                     textcoords='offset points',
                     xytext=offs.get(p['scale'], (5, 4)),
                     fontsize=5.9, color=INK)
    axc.axhline(0.5, color=WARM, linewidth=1.0, linestyle=(0, (5, 2)), zorder=2)
    axc.text(74, 0.516, 'the rule', fontsize=6.2, color=WARM, va='bottom')
    axc.set_xscale('log')
    axc.set_xlim(50, 1500)
    axc.set_ylim(0, 0.585)
    axc.set_xlabel('household download, GB/month', fontsize=6.9)
    axc.set_ylabel('threshold giving zero false alarms', fontsize=6.9)
    axc.set_xticks([60, 120, 250, 500, 1000])
    axc.set_xticklabels(['60', '120', '250', '500', '1000'], fontsize=6.2)
    axc.set_yticks([0, 0.2, 0.4, 0.5])
    axc.tick_params(labelsize=6.2)
    tidy(axc)
    tag(axc, 'c', dx=-0.26)
    axc.set_title('a fitted threshold moves tenfold', loc='left', pad=4, fontsize=7.0)

    for ax in (axa, axb, axc):
        ax.spines['left'].set_linewidth(0.6)
        ax.spines['bottom'].set_linewidth(0.6)
    for ext in ('pdf', 'png'):
        fig.savefig(os.path.join(FIG, 'fig12_dualuse.' + ext),
                    dpi=300 if ext == 'png' else None, facecolor='white')
    plt.close(fig)
    print('  wrote fig/fig12_dualuse.pdf and .png')
    print('  canvas width %.2f in, height %.2f in' % (FULL, 2.42))


if __name__ == '__main__':
    main()
