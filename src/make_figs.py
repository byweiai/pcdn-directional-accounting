# -*- coding: utf-8 -*-
"""All main-text figures. One canvas per figure, real data only.

Every panel reads a result JSON written by the experiment scripts; nothing here
invents a number. Style follows the project rules: slate-blue for the method,
warm accent only for thresholds and the harm quantity, no bars, no connecting
lines, panel letters aligned, text never allowed to sit on top of a marker.
"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
FIG = os.path.join(ROOT, 'fig')
os.makedirs(FIG, exist_ok=True)

INK = '#28485F'
BLUE = '#4A8CB5'
BLUE2 = '#5FA0C6'
BLUE3 = '#8FBEDA'
BLUE4 = '#C6DFEE'
WASH = '#E9F3FA'
WARM = '#B5651D'
MAGENTA = '#B8287A'
GREY = '#8A9AA8'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 7.5,
    'axes.labelsize': 7.5,
    'axes.titlesize': 8,
    'xtick.labelsize': 6.8,
    'ytick.labelsize': 6.8,
    'legend.fontsize': 6.8,
    'axes.edgecolor': INK,
    'axes.labelcolor': INK,
    'text.color': INK,
    'xtick.color': INK,
    'ytick.color': INK,
    'axes.linewidth': 0.6,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'xtick.major.size': 2.2,
    'ytick.major.size': 2.2,
    'savefig.dpi': 300,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

FULL = 7.16
HALF = 3.50


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding='utf-8'))


def tidy(ax, left_only=False):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if left_only:
        ax.spines['bottom'].set_visible(False)
    ax.set_facecolor('white')


def tag(ax, s, dx=-0.085, dy=1.02):
    ax.text(dx, dy, s, transform=ax.transAxes, fontsize=8.2, fontweight='bold',
            va='bottom', ha='left', color=INK)


def save(fig, name):
    for ext in ('pdf', 'png'):
        fig.savefig(os.path.join(FIG, name + '.' + ext), bbox_inches='tight',
                    pad_inches=0.02, facecolor='white')
    plt.close(fig)
    print('  wrote fig/%s.pdf' % name)


# ---------------------------------------------------------------- figure 1
def fig1_mechanism():
    e2 = load('e2_window.json')
    e1 = load('e1_unsw.json')
    e5 = load('e5_regime.json')

    fig = plt.figure(figsize=(FULL, 3.55))
    gs = gridspec.GridSpec(2, 2, height_ratios=[1.30, 1.00],
                           left=0.055, right=0.985, top=0.93, bottom=0.045,
                           hspace=0.42, wspace=0.20)

    # (a) detection decays under dilution
    axa = fig.add_subplot(gs[0, 0])
    sw = e2['sweep']
    a = np.array([r['alpha'] for r in sw])
    t = np.array([r['tpr'] for r in sw])
    sd = np.array([r['tpr_sd'] for r in sw])
    win = e2['evasion_window']
    lo, hi = min(win), max(win)
    axa.axvspan(lo, hi, color=WASH, zorder=0)
    inwin = (a >= lo) & (a <= hi)
    axa.errorbar(a[inwin], t[inwin], yerr=sd[inwin], fmt='o', ms=3.4, lw=0.7,
                 color=WARM, ecolor=WARM, capsize=1.4, zorder=3)
    axa.plot(a[~inwin], t[~inwin], 'o', ms=3.4, color=BLUE, zorder=3)
    axa.axhline(0.5, color=GREY, lw=0.6, ls=(0, (3, 2)), zorder=1)
    axa.text(0.985, 0.545, 'chance', fontsize=6.2, color=GREY, ha='right', va='bottom',
             transform=axa.get_yaxis_transform())
    axa.set_xlabel("distributed share $\\alpha$ of a node's own bytes")
    axa.set_ylabel('classifier TPR')
    axa.set_xlim(0, 1.04)
    axa.set_ylim(0, 1.06)
    axa.annotate('the window where a trained\nclassifier reads a distributor\nas an ordinary subscriber',
                 xy=(0.24, 0.09), xytext=(0.53, 0.15), fontsize=6.2, color=WARM,
                 ha='left', va='center',
                 arrowprops=dict(arrowstyle='-|>', lw=0.7, color=WARM,
                                 shrinkA=1, shrinkB=2, mutation_scale=8))
    tidy(axa)
    tag(axa, 'a', dx=-0.13)
    axa.set_title('detection loses the signal it was trained on', loc='left', pad=4.5)

    # (b) metering keeps it
    axb = fig.add_subplot(gs[0, 1])
    e1e = e1
    roles = e1e['panel_role_stats']
    ys = {'service': 2, 'client': 0, 'other': 1}
    cols = {'service': BLUE, 'client': BLUE3, 'other': BLUE4}
    for r in ('client', 'other', 'service'):
        d = roles[r]
        p50, p10, p90 = d['median'], d['p10'], d['p90']
        y = ys[r]
        axb.plot([p10, p90], [y, y], lw=4.2, color=cols[r], alpha=0.55,
                 solid_capstyle='round', zorder=2)
        axb.plot([p50], [y], 'o', ms=4.6, color=cols[r], mec='white', mew=0.7, zorder=3)
        axb.text(1.02, y, '%s\nn=%s' % (r, format(d['n'], ',')), fontsize=6.3,
                 va='center', ha='left', color=INK)
    axb.axvline(0.5, color=WARM, lw=0.8, ls=(0, (3, 2)), zorder=1)
    axb.text(0.505, 2.62, 'quota at 0.5', fontsize=6.2, color=WARM, ha='left', va='center')
    axb.set_yticks([])
    axb.set_xlim(0, 1.0)
    axb.set_ylim(-0.6, 2.75)
    axb.set_xlabel(r'byte ratio $\rho = S/(S+R)$, endpoint aggregate')
    axb.set_title('metering keeps it, because it never looks at content', loc='left', pad=4.5)
    tag(axb, 'b', dx=-0.10)
    tidy(axb, left_only=True)
    axb.spines['left'].set_visible(False)
    axb.tick_params(axis='y', length=0)

    # (c) the spine: measure -> trigger -> declare -> tier
    axc = fig.add_subplot(gs[1, :])
    axc.set_xlim(0, 1)
    axc.set_ylim(0, 1)
    axc.axis('off')
    base = e5['base']
    e7s = load('e7_meter.json')['summary']
    gbps = e7s['gbps_at_mean_packet']
    mpkt = e7s['mean_packet_bytes']
    stages = [
        ('meter', 'two counters per subscriber',
         '16 B both, %.1f Gbps per core' % gbps),
        ('trigger', 'a ratio backed by volume', '%.2f%% of the base' % (100 * base['tripped_share_of_base'])),
        ('declare', 'the endpoint states what it is',
         '%.1f%% take the contract' % (100 * base['registration_rate'])),
        ('tier', 'consumer SLA or provider rate',
         'welfare %.1f× enforcement' % (base['welfare']['S3'] / base['welfare']['S1'])),
    ]
    xs = [0.105, 0.365, 0.625, 0.885]
    yline = 0.50
    axc.annotate('', xy=(0.985, yline), xytext=(0.015, yline),
                 arrowprops=dict(arrowstyle='-|>', lw=1.1, color=BLUE4,
                                 mutation_scale=12, shrinkA=0, shrinkB=0))
    for i, (name, what, num) in enumerate(stages):
        cx = xs[i]
        axc.plot([cx], [yline], 'o', ms=9.5, color=WASH, mec=BLUE3, mew=0.9, zorder=4)
        axc.text(cx, yline, str(i + 1), ha='center', va='center', fontsize=6.6,
                 color=BLUE, fontweight='bold', zorder=5)
        axc.text(cx, 0.80, name, ha='center', va='center', fontsize=8.0,
                 fontweight='bold', color=INK)
        axc.text(cx, 0.24, what, ha='center', va='center', fontsize=6.5, color=INK)
        axc.text(cx, 0.09, num, ha='center', va='center', fontsize=6.3, color=BLUE)
    axc.text(0.015, 0.99, 'the same adversary defeats (a) and cannot touch (b), '
             'so the control loop is built on (b)',
             fontsize=6.9, color=INK, va='top', ha='left', style='italic')
    save(fig, 'fig1_mechanism')


# ---------------------------------------------------------------- figure 2
def fig2_separation():
    import pandas as pd
    ep = pd.read_csv(os.path.join(DATA, 'e1_endpoints.csv'))
    pan = pd.read_csv(os.path.join(DATA, 'e1_panel.csv'))
    e1 = load('e1_unsw.json')

    fig = plt.figure(figsize=(FULL, 2.55))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.45, 1.0], left=0.075, right=0.985,
                           top=0.86, bottom=0.19, wspace=0.26)

    # (a) half violin of the panel
    axa = fig.add_subplot(gs[0, 0])
    order = ['client', 'other', 'service']
    cols = {'client': BLUE3, 'other': BLUE4, 'service': BLUE}
    bins = np.linspace(0, 1, 41)
    for i, r in enumerate(order):
        v = pan.loc[pan['role'] == r, 'rho'].values
        if len(v) < 5:
            continue
        h, edges = np.histogram(v, bins=bins, density=True)
        k = np.ones(5) / 5.0
        h = np.convolve(h, k, mode='same')
        h = h / max(1e-9, h.max()) * 0.80
        c = (edges[:-1] + edges[1:]) / 2
        axa.fill_between(c, i, i + h, color=cols[r], lw=0,
                         alpha=0.55 if r == 'service' else 0.75, zorder=3)
        hi = h > 0.02
        axa.plot(c[hi], (i + h)[hi], lw=0.55, color=cols[r], zorder=3)
        q = np.percentile(v, [5, 50, 95])
        for qq in (q[0], q[2]):
            axa.plot([qq, qq], [i - 0.055, i + 0.055], lw=0.7, color=INK,
                     alpha=0.45, zorder=4, solid_capstyle='butt')
        axa.plot([q[1]], [i], 'o', ms=3.8, color='white', mec=cols[r], mew=1.0, zorder=5)
    axa.axvline(0.5, color=WARM, lw=0.8, ls=(0, (3, 2)), zorder=2)
    axa.text(0.508, 2.62, 'quota at 0.5', fontsize=6.2, color=WARM, ha='left', va='center')
    axa.set_yticks(range(3))
    axa.set_yticklabels(['%s\nn=%s' % (r, format(len(pan.loc[pan['role'] == r]), ','))
                         for r in order], fontsize=6.6)
    axa.set_ylim(-0.55, 2.95)
    axa.set_xlim(0, 1)
    axa.set_xlabel(r'$\rho$ for one endpoint in one five-minute window')
    tidy(axa, left_only=True)
    axa.spines['left'].set_visible(False)
    tag(axa, 'a', dx=-0.11)
    axa.set_title('two lobes, one threshold, no overlap at the decision point',
                  loc='left', pad=4)

    # (b) quota scan as a bubble matrix (values come from data/e9_threshold.json)
    axb = fig.add_subplot(gs[0, 1])
    scan = load('e9_threshold.json')['scan']
    taus = [r['tau'] for r in scan]
    fp = [r['false_alarm'] for r in scan]
    cap = [r['capture'] for r in scan]
    cols2 = ['false alarm on\nsubscribers', 'capture of\nservers']
    vals = np.array([fp, cap]).T
    for i, tau in enumerate(taus):
        for j in range(2):
            v = vals[i, j]
            if v > 0:
                size = 6 + 250 * v
                axb.scatter([j], [i], s=size, color=BLUE if j else BLUE3, alpha=0.80,
                            lw=0.6, edgecolor='white', zorder=3)
                axb.text(j + 0.22, i, '%.3f' % v, ha='left', va='center',
                         fontsize=6.2, color=INK, zorder=4)
            else:
                axb.text(j + 0.22, i, '0', ha='left', va='center', fontsize=6.2,
                         color=GREY, zorder=4)
    axb.set_xticks([0, 1])
    axb.set_xticklabels(cols2, fontsize=6.4)
    axb.set_yticks(range(len(taus)))
    axb.set_yticklabels(['%.2f' % t for t in taus], fontsize=6.4)
    axb.set_ylabel('decision threshold on $\\rho$', fontsize=6.6)
    axb.set_xlim(-0.62, 1.62)
    axb.set_ylim(-0.60, len(taus) - 0.12)
    axb.invert_yaxis()
    tidy(axb, left_only=True)
    axb.spines['bottom'].set_visible(False)
    tag(axb, 'b', dx=-0.30)
    axb.set_title('a tight quota costs no subscriber', loc='left', pad=4)
    save(fig, 'fig2_separation')


# ---------------------------------------------------------------- figure 3
def fig3_evasion():
    e2 = load('e2_window.json')
    sw = e2['sweep']
    a = np.array([r['alpha'] for r in sw])
    rho = np.array([r['rho'] for r in sw])
    tpr = np.array([r['tpr'] for r in sw])
    dist = np.array([r['dist_flag_rate'] for r in sw])
    cons = np.array([r['cons_flag_rate'] for r in sw])
    win = e2['evasion_window']
    lo, hi = min(win), max(win)
    p90 = e2['client_rho_p90']
    x_dl = float(next(r['downlink_x'] for r in sw
                    if abs(r['alpha'] - 0.05) < 1e-9))
    x_lo = float(next(r['volume_up_x'] for r in sw
                      if abs(r['alpha'] - lo) < 1e-9))

    fig = plt.figure(figsize=(FULL, 2.5))
    gs = gridspec.GridSpec(1, 2, left=0.078, right=0.985, top=0.855, bottom=0.20,
                           wspace=0.30)

    axa = fig.add_subplot(gs[0, 0])
    axa.axvspan(lo, hi, color=WASH, zorder=0)
    axa.plot(a, dist, 's', ms=3.4, color=BLUE, zorder=3)
    axa.plot(a, tpr, 'o', ms=3.8, color=WARM, zorder=4)
    axa.plot(a, cons, '^', ms=3.4, color=GREY, zorder=3)
    axa.axhline(0.5, color=GREY, lw=0.6, ls=(0, (3, 2)), zorder=1)
    axa.text(0.88, 0.53, 'chance', fontsize=6.2, color=GREY, va='bottom', ha='right')
    axa.text(0.30, 1.015, 'distribution flows', fontsize=6.3, color=BLUE, va='bottom')
    axa.text(0.055, 0.30, "all of the\nnode's traffic", fontsize=6.3, color=WARM,
             va='center', ha='left')
    axa.text(0.615, 0.055, 'household flows', fontsize=6.3, color=GREY, va='bottom')
    axa.set_xlabel("distributed share $\\alpha$ of a node's own bytes")
    axa.set_ylabel("flag rate")
    axa.set_xlim(0, 1.04)
    axa.set_ylim(-0.03, 1.08)
    tidy(axa)

    axb = fig.add_subplot(gs[0, 1])
    axb.axvspan(lo, hi, color=WASH, zorder=0)
    m = (a >= lo) & (a <= hi)
    axb.plot(a[~m], rho[~m], 'o', ms=3.8, color=BLUE, zorder=3)
    axb.plot(a[m], rho[m], 'o', ms=3.8, color=WARM, zorder=3)
    axb.axhspan(0, p90, color='#F3E4D8', zorder=0)
    axb.axhline(p90, color=WARM, lw=0.7, ls=(0, (3, 2)), zorder=1)
    axb.text(0.60, p90 - 0.030, 'subscriber p90 = %.3f' % p90,
             fontsize=6.2, color=WARM, va='top', ha='left')
    axb.annotate('the meter still separates\nhere; the aggregate rule is empty',
                 xy=(0.16, 0.215), xytext=(0.44, 0.255), fontsize=6.3, color=WARM,
                 ha='left', va='bottom',
                 arrowprops=dict(arrowstyle='-|>', lw=0.7, color=WARM,
                                 shrinkA=2, shrinkB=3, mutation_scale=8))
    axb.set_xlabel("distributed share $\\alpha$ of a node's own bytes")
    axb.set_ylabel(r'metered $\rho$')
    axb.set_xlim(0, 1.04)
    axb.set_ylim(0, 1.05)
    tidy(axb)

    tag(axa, 'a', dx=-0.145)
    axa.set_title('dilution empties the aggregate rule', loc='left', pad=4)
    tag(axb, 'b', dx=-0.145)
    axb.set_title('the ratio holds until the bill is %d$\\times$' % round(x_dl),
                  loc='left', pad=4)
    fig.text(0.078, 0.030, 'shaded: the dilution range in which the aggregate flag rate is at or below '
             '60% while the metered ratio stays above the subscriber p90', fontsize=6.3, color=GREY)
    save(fig, 'fig3_evasion')


def fig4_robustness():
    e3 = load('e3_external.json')
    cic = e3['cic']
    tm = e3['time']
    at = e3['attack']

    fig = plt.figure(figsize=(FULL, 2.6))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1.25, 1.15, 1.0], left=0.07,
                           right=0.985, top=0.84, bottom=0.20, wspace=0.40)

    # (a) where the lobes sit, in an independently collected trace
    axa = fig.add_subplot(gs[0, 0])
    pk = sorted(cic['peaks'])
    e1 = load('e1_unsw.json')
    u_cli = e1['panel_role_stats']['client']['p90']
    u_srv = e1['panel_role_stats']['service']['median']
    for lo, hi in ((0.0, 0.35), (0.65, 1.0)):
        axa.axvspan(lo, hi, color=WASH, zorder=0)
    axa.axvline(cic['valley_rho'], color=WARM, lw=0.8, ls=(0, (3, 2)), zorder=2)
    axa.plot(pk, [1.0] * len(pk), 'o', ms=5.4, color=BLUE, mec='white', mew=0.6, zorder=4)
    axa.plot([u_cli, u_srv], [0.0, 0.0], 'o', ms=5.4, color=BLUE3, mec='white',
             mew=0.6, zorder=4)
    axa.set_yticks([0, 1])
    axa.set_yticklabels(['UNSW\nreference', 'CIC\npeaks'], fontsize=6.5)
    axa.set_ylim(-0.75, 1.65)
    axa.set_xlim(0, 1.0)
    axa.set_xlabel(r'$\rho$, endpoint aggregate')
    axa.text(0.5, 1.30, 'low %.3f vs %.3f' % (pk[0], u_cli), fontsize=6.2,
             color=INK, ha='center')
    axa.text(0.5, -0.45, 'high %.3f vs %.3f' % (pk[-2], u_srv), fontsize=6.2,
             color=INK, ha='center')
    axa.text(0.02, 1.57, 'valley %.3f, at %.0f%% of the shallow lobe'
             % (cic['valley_rho'], 100 * cic['valley_over_peak']),
             fontsize=6.1, color=WARM, va='top')
    axa.text(0.02, -0.68, 'CIC mass sits high: median %.3f (attack-dominated capture)'
             % cic['rho_median'], fontsize=6.1, color=GREY, va='bottom')
    tidy(axa, left_only=False)
    axa.spines['left'].set_visible(False)
    axa.tick_params(axis='y', length=0)
    tag(axa, 'a', dx=-0.20)
    axa.set_title('lobes survive, mass does not', loc='left', pad=4)

    # (b) temporal extrapolation
    axb = fig.add_subplot(gs[0, 1])
    hrs = tm['hours']
    h = np.array([r['hour'] for r in hrs])
    cap = np.array([r['capture'] for r in hrs])
    n = np.array([r['n_endpoints'] for r in hrs])
    idx = np.arange(1, len(hrs) + 1)
    axb.scatter(idx, cap, s=8 + 2.2 * n, color=BLUE, alpha=0.8, lw=0.4,
                edgecolor='white', zorder=3)
    axb.set_xlabel('hourly period (hours %d–%d and %d–%d)' % (h.min(), h[12], h[13], h.max()))
    axb.set_ylabel('capture of service endpoints')
    axb.set_ylim(0.75, 1.03)
    axb.set_xlim(0, len(hrs) + 1)
    axb.set_xticks([1, 6, 13, 18, 22])
    axb.text(0.6, 0.775, 'false alarm 0.0000 in all %d periods' % len(hrs),
             fontsize=6.2, color=WARM, va='bottom', ha='left')
    tidy(axb)
    tag(axb, 'b', dx=-0.155)
    axb.set_title('one threshold, set once', loc='left', pad=4)

    # (c) persistence separates distribution from bursts
    axc = fig.add_subplot(gs[0, 2])
    roles = [('client', at['by_role']['client']),
             ('other', at['by_role']['other']),
             ('service', at['by_role']['service'])]
    for name, d in roles:
        axc.scatter([d['longest_run_median']], [d['over_share_median']],
                    s=40 + 3.0 * d['n'], color=BLUE if name == 'service' else BLUE3,
                    alpha=0.85, lw=0.5, edgecolor='white', zorder=3)
        axc.annotate(name, (d['longest_run_median'], d['over_share_median']),
                     textcoords='offset points', xytext=(6, 5), fontsize=6.6, color=INK)
    axc.scatter([at['crossers']['attacker_over_share_median'] * 0], [0.473], marker='X',
                s=44, color=WARM, lw=0.5, edgecolor='white', zorder=4)
    axc.annotate('attackers: %d crossed,\nnone persisted' % round(
        at['crossers']['n'] * at['crossers']['attacker_share']),
        (0, 0.473), textcoords='offset points',
        xytext=(10, -16), fontsize=6.2, color=WARM)
    axc.set_xlabel('longest run above quota (windows)')
    axc.set_ylabel('share of windows above quota')
    axc.set_xlim(-6, 60)
    axc.set_ylim(-0.05, 1.0)
    tidy(axc)
    tag(axc, 'c', dx=-0.22)
    axc.set_title('distribution persists', loc='left', pad=4)
    save(fig, 'fig4_robustness')


# ---------------------------------------------------------------- figure 5
def fig5_peeringdb():
    e4 = load('e4_peeringdb.json')
    kinds = e4['kinds']
    labels = e4['ratio_labels']
    tab = np.array(e4['table'], dtype=float)
    tot = tab.sum(axis=1)
    share = tab / np.where(tot[:, None] == 0, 1, tot[:, None])
    expect = (tab.sum(axis=0)[None, :] * tot[:, None]) / tab.sum()
    resid = (tab - expect) / np.sqrt(np.maximum(expect, 1e-9))

    order = np.argsort(-tot)
    kinds = [kinds[i] for i in order]
    tab, share, resid, tot = tab[order], share[order], resid[order], tot[order]
    denom = np.abs(resid).max()

    fig = plt.figure(figsize=(FULL, 3.35))
    ax = fig.add_axes([0.175, 0.225, 0.60, 0.675])
    cmap = LinearSegmentedColormap.from_list('div', [BLUE, '#FFFFFF', WARM])
    for i in range(len(kinds)):
        for j in range(len(labels)):
            r = resid[i, j]
            col = cmap(0.5 + 0.5 * r / denom)
            ax.scatter([j], [i], s=8 + 140 * share[i, j], color=col,
                       alpha=0.92, lw=0.5, edgecolor='white', zorder=3)
            if share[i, j] >= 0.030:
                ax.text(j, i, '%.0f' % (100 * share[i, j]), ha='center', va='center',
                        fontsize=6.0, color='white' if abs(r) > 0.55 * denom else INK, zorder=4)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([l.replace(' ', '\n') for l in labels], fontsize=6.4)
    ax.set_yticks(range(len(kinds)))
    ax.set_yticklabels(['%s  (n=%s)' % (k, format(int(t), ',')) for k, t in zip(kinds, tot)],
                       fontsize=6.8)
    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.set_ylim(-0.6, len(kinds) - 0.4)
    ax.invert_yaxis()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.text(-0.5, -0.95, "share of each network type's declared ratio, per cent"
            "  $\\cdot$  colour = signed residual under independence  "
            "($V=%.3f$)" % e4['cramers_v'], fontsize=6.3, color=GREY, va='bottom')
    fig.text(0.175, 0.955, 'access networks declare inbound, content networks declare outbound',
             fontsize=7.4, color=INK, va='bottom', ha='left')

    axr = fig.add_axes([0.80, 0.225, 0.155, 0.675])
    gap = (share[:, :2].sum(axis=1) - share[:, 3:5].sum(axis=1)) * 100.0
    axr.barh(range(len(kinds)), gap,
             color=[WARM if v > 0 else BLUE for v in gap],
             height=0.55, alpha=0.85, lw=0)
    for i, v in enumerate(gap):
        axr.text(v + (2.0 if v > 0 else -2.0), i, '%.0f' % v, fontsize=5.8,
                 color=INK, va='center', ha='left' if v > 0 else 'right')
    axr.set_yticks(range(len(kinds)))
    axr.set_yticklabels([])
    axr.set_xlabel('inbound minus\noutbound (%)', fontsize=6.4)
    axr.axvline(0, color=INK, lw=0.6)
    axr.set_ylim(len(kinds) - 0.4, -0.6)
    axr.tick_params(length=0)
    for s in axr.spines.values():
        s.set_visible(False)
    axr.set_xlim(-45, 70)
    save(fig, 'fig5_peeringdb')


# ---------------------------------------------------------------- figure 6
def fig6_window():
    e8 = load('e8_window.json')
    rows = [r for r in e8['rows'] if r['window_s'] > 0]
    w = np.array([r['window_s'] for r in rows], dtype=float)
    tpr = np.array([r['tpr_cell'] for r in rows])
    tpr3 = np.array([r['tpr_sustained3'] for r in rows])
    fp = np.array([r['fp_cell'] for r in rows])
    c95 = np.array([r['client_p95'] for r in rows])
    s05 = np.array([r['service_p05'] for r in rows])
    cells = np.array([r['cells'] for r in rows])

    fig = plt.figure(figsize=(FULL, 2.45))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.15, 1.0], left=0.075, right=0.985,
                           top=0.85, bottom=0.195, wspace=0.28)

    axa = fig.add_subplot(gs[0, 0])
    axa.plot(w, tpr, 'o', ms=4.2, color=BLUE3, zorder=3)
    axa.plot(w, tpr3, 's', ms=4.0, color=BLUE, zorder=3)
    axa.axvline(300, color=WARM, lw=0.8, ls=(0, (3, 2)), zorder=2)
    axa.text(315, 0.797, 'chosen: 300 s', fontsize=6.4, color=WARM, va='bottom')
    axa.set_xscale('log')
    axa.set_xticks([60, 120, 300, 600, 900, 1800, 3600])
    axa.set_xticklabels(['1 min', '2', '5', '10', '15', '30', '60'])
    axa.set_xlabel('aggregation window')
    axa.set_ylabel('capture of service endpoints')
    axa.set_ylim(0.79, 1.02)
    tidy(axa)
    tag(axa, 'a', dx=-0.145)
    axa.set_title('three consecutive windows recover every distributor', loc='left', pad=4)

    axb = fig.add_subplot(gs[0, 1])
    axb.fill_between(w, c95, s05, color=WASH, zorder=0)
    axb.plot(w, c95, 'v', ms=4.0, color=BLUE3, zorder=3, label='subscriber p95')
    axb.plot(w, s05, '^', ms=4.0, color=BLUE, zorder=3, label='service p05')
    axb.axhline(0.5, color=WARM, lw=0.8, ls=(0, (3, 2)), zorder=2)
    axb.text(65, 0.515, 'quota', fontsize=6.3, color=WARM, va='bottom')
    axb.set_xscale('log')
    axb.set_xticks([60, 120, 300, 600, 900, 1800, 3600])
    axb.set_xticklabels(['1 min', '2', '5', '10', '15', '30', '60'])
    axb.set_xlabel('aggregation window')
    axb.set_ylabel(r'$\rho$ at the tails')
    axb.set_ylim(0, 0.60)
    axb.legend(loc='center left', bbox_to_anchor=(0.02, 0.62), frameon=False,
               handletextpad=0.4, borderpad=0.1, fontsize=6.3)
    tidy(axb)
    tag(axb, 'b', dx=-0.145)
    axb.set_title('longer windows widen the gap, but slow the reaction', loc='left', pad=4)
    fig.text(0.075, 0.035, 'cell-level false alarm is 0.0000 at every width above 1 min '
             '(0.0002 at 1 min); under the three-window rule it is 0.0000 everywhere',
             fontsize=6.2, color=GREY)
    save(fig, 'fig6_window')


# ---------------------------------------------------------------- figure 7
def fig7_regimes():
    e5 = load('e5_regime.json')
    nq = load('e5_noquota.json')
    base = e5['base']
    # panel (a) shows the tariff this paper defines for S2 -- every upstream
    # gigabyte billed, no allowance -- with the balanced ledger, because that is
    # the column of Table 2.  The ratio-quota cell lives in panel (b) and in
    # Table 4.
    s2w = nq['base']['none|eps=1.0']
    pr = e5['provider_rate']
    ev = e5['evasion']

    fig = plt.figure(figsize=(FULL, 2.7))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.25, 1.0], left=0.08, right=0.985,
                           top=0.85, bottom=0.20, wspace=0.28)

    axa = fig.add_subplot(gs[0, 0])
    trio = {'S1': base, 'S2': s2w, 'S3': base}
    vs = np.array([trio[k]['volume_served'][k] / 1e6 for k in ('S1', 'S2', 'S3')])
    hm = np.array([trio[k]['unpriced_harm'][k] / 1e3 for k in ('S1', 'S2', 'S3')])
    wf = np.array([trio[k]['welfare'][k] / 1e3 for k in ('S1', 'S2', 'S3')])
    shapes = {'S1': 'o', 'S2': 'D', 'S3': 's'}
    names = {'S1': 'enforcement', 'S2': 'spot pricing', 'S3': 'declared tiers'}
    offs = {'S1': (12, 6), 'S2': (-6, 26), 'S3': (10, 8)}
    has = {'S1': 'left', 'S2': 'right', 'S3': 'left'}
    for i, k in enumerate(('S1', 'S2', 'S3')):
        axa.scatter([vs[i]], [hm[i]], s=40 + 250 * (wf[i] / wf.max()),
                    marker=shapes[k],
                    color=WARM if k == 'S2' else (BLUE if k == 'S3' else BLUE3),
                    alpha=0.8, lw=0.7, edgecolor='white', zorder=3)
        axa.annotate(names[k] + '\n%.0f welfare' % wf[i],
                     (vs[i], hm[i]), textcoords='offset points',
                     xytext=offs[k], fontsize=6.5, color=INK, ha=has[k],
                     va='center')
    axa.set_xlabel('volume served (10$^6$ GB per month)')
    axa.set_ylabel('congestion left unpaid (10$^3$ CNY/mo)')
    axa.set_xlim(-0.05, 1.30)
    axa.set_ylim(-6.0, 27)
    axa.text(0.03, 0.95, 'marker area = welfare\nfigures in $10^3$ CNY/mo',
             transform=axa.transAxes, fontsize=6.3, color=GREY, va='top')
    tidy(axa)
    tag(axa, 'a', dx=-0.15)
    axa.set_title('equal welfare, opposite incidence', loc='left', pad=4)

    axb = fig.add_subplot(gs[0, 1])
    ec = np.array([r['evasion_cost'] for r in ev])
    s2 = np.array([r['operator_margin_S2'] for r in ev]) / 1e3
    s3 = np.array([r['operator_margin_S3'] for r in ev]) / 1e3
    axb.plot(ec, s2, 'o', ms=4.2, color=WARM, zorder=3, label='spot charge, ratio quota')
    axb.plot(ec, s3, 's', ms=4.0, color=BLUE, zorder=3, label='declared tiers')
    ps = base['p_spot']
    axb.axvspan(0, ps, color=WASH, zorder=0)
    axb.axvline(ps, color=WARM, lw=0.8, ls=(0, (3, 2)), zorder=2)
    axb.text(0.012, 80, 'disguise costs less\nthan the price charged:\nthe ratio-quota base collapses',
             fontsize=6.1, color=WARM, va='top')
    axb.text(0.012, 52, '$p_{spot}$ = %.2f' % ps, fontsize=6.1, color=WARM, va='top')
    axb.set_xlabel('cost of buying downlink to dilute the ratio (CNY/GB)')
    axb.set_ylabel('operator margin (10$^3$ CNY/mo)')
    axb.set_ylim(-6, 118)
    axb.legend(loc='center right', frameon=False, handletextpad=0.4, borderpad=0.1)
    tidy(axb)
    tag(axb, 'b', dx=-0.16)
    axb.set_title('one regime has a price base, the other a rule', loc='left', pad=4)
    save(fig, 'fig7_regimes')


# ---------------------------------------------------------------- figure 8
def fig8_meter():
    e7 = load('e7_meter.json')
    s = e7['summary']
    rows = [('exact counter', s['records_per_sec_exact'] / 1e6, 320,
             float(np.mean([r['exact_rel_err'] for r in e7['runs']]))),
            ('count-min sketch', s['records_per_sec_cms'] / 1e6, s['cms_memory_kib'],
             s['cms_rel_err_mean']),
            ('space-saving', s['records_per_sec_ss'] / 1e6, s['ss_memory_kib'],
             s['ss_rel_err_mean'])]

    fig = plt.figure(figsize=(HALF, 2.30))
    ax = fig.add_axes([0.245, 0.235, 0.725, 0.60])
    # what a ten-gigabit port demands, at the benchmark's own mean packet size
    port = 10e9 / 8.0 / s['mean_packet_bytes'] / 1e6
    offs = [(-9, 9, 'right'), (10, -13, 'left'), (9, -2, 'left')]
    for i, (name, mps, kib, err) in enumerate(rows):
        ax.scatter([kib], [mps], s=48 + 520 * err, color=BLUE if i == 0 else BLUE3,
                   alpha=0.90, lw=0.5, edgecolor='white', zorder=3)
        dx, dy, ha = offs[i]
        ax.annotate('%s\n%.1f%% error' % (name, 100 * err), (kib, mps),
                    textcoords='offset points', xytext=(dx, dy),
                    ha=ha, fontsize=6.2, color=INK)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('counter memory (KiB, log)')
    ax.set_ylabel('records per second (log)')
    ax.set_xlim(12, 900)
    ax.set_ylim(0.05, 20)
    ax.set_xticks([20, 50, 100, 300, 900])
    ax.set_xticklabels(['20', '50', '100', '300', '900'])
    ax.set_yticks([0.1, 1, 10])
    ax.set_yticklabels(['0.1', '1', '10'])
    ax.minorticks_off()
    ax.axhline(port, color=WARM, lw=0.7, ls=(0, (3, 2)), zorder=1)
    ax.text(13, port * 1.18, '10 Gbps port at the study mix',
            fontsize=6.1, color=WARM, va='bottom')
    tidy(ax)
    ax.set_title('16 B per subscriber, one core per port', loc='left', pad=4, fontsize=7.6)
    save(fig, 'fig8_meter')


# ---------------------------------------------------------------- figure A
def figA_sweeps():
    """Appendix small multiples: the full grids behind the figures in the body."""
    e2 = load('e2_window.json')
    e9 = load('e9_threshold.json')['scan']
    e5 = load('e5_regime.json')

    a = np.array([r['alpha'] for r in e2['sweep']])
    tpr = np.array([r['tpr'] for r in e2['sweep']]) * 100
    rho = np.array([r['rho'] for r in e2['sweep']])
    win = e2['evasion_window']
    lo, hi = min(win), max(win)

    taus = [r['tau'] for r in e9]
    fp = [r['false_alarm'] for r in e9]
    cap = [r['capture'] for r in e9]

    pr = e5['provider_rate']
    rate = [r['p_provider'] for r in pr]
    reg = [100 * r['registration_rate'] for r in pr]
    mar = [r['operator_margin_S3'] / 1e3 for r in pr]

    ev = e5['evasion']
    ecost = [r['evasion_cost'] for r in ev]
    m2 = [r['operator_margin_S2'] / 1e3 for r in ev]
    m3 = [r['operator_margin_S3'] / 1e3 for r in ev]
    switch = max(r['evasion_cost'] for r in ev if r['laundering_pays'])

    fig = plt.figure(figsize=(FULL, 1.58))
    gs = fig.add_gridspec(1, 4, wspace=0.66, left=0.050, right=0.992,
                          top=0.86, bottom=0.20)

    # (a) full mixing grid, flag rate
    ax = fig.add_subplot(gs[0, 0])
    ax.axvspan(lo, hi, color=WASH, lw=0, zorder=0)
    ax.scatter(a, tpr, s=9, color=BLUE, zorder=3)
    ax.axhline(50, color=WARM, lw=0.7, ls=(0, (3, 2)), zorder=1)
    ax.set_xlabel('mixing $\\alpha$', labelpad=1.5)
    ax.set_ylabel('flagged (\\%)')
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_ylim(-4, 108)
    tidy(ax)
    tag(ax, 'a', dx=-0.30)
    ax.set_title('classifier', loc='left', pad=4, fontsize=7.2)

    # (b) full mixing grid, ratio
    ax = fig.add_subplot(gs[0, 1])
    ax.axvspan(lo, hi, color=WASH, lw=0, zorder=0)
    ax.scatter(a, rho, s=9, color=BLUE, zorder=3)
    ax.axhline(e2['client_rho_p90'], color=WARM, lw=0.7, ls=(0, (3, 2)), zorder=1)
    ax.set_xlabel('mixing $\\alpha$', labelpad=1.5)
    ax.set_ylabel('$\\rho$')
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_ylim(0, 1.04)
    tidy(ax)
    tag(ax, 'b', dx=-0.26)
    ax.set_title('meter', loc='left', pad=4, fontsize=7.2)

    # (c) threshold scan, both rates on one scale
    ax = fig.add_subplot(gs[0, 2])
    ax.scatter(taus, [100 * v for v in cap], s=14, marker='s', color=BLUE, zorder=3)
    ax.scatter(taus, [100 * v for v in fp], s=14, facecolor='white',
               edgecolor=WARM, lw=0.8, zorder=3)
    ax.set_xlabel('threshold on $\\rho$', labelpad=1.5)
    ax.set_ylabel('rate (\\%)')
    ax.set_ylim(-4, 108)
    tidy(ax)
    tag(ax, 'c', dx=-0.30)
    ax.set_title('capture / alarm', loc='left', pad=4, fontsize=7.2)
    ax.annotate('capture', (taus[3], 92.3), textcoords='offset points',
                xytext=(6, 7), fontsize=6.0, color=INK)
    ax.annotate('false alarm', (taus[1], 2.6), textcoords='offset points',
                xytext=(12, 16), fontsize=6.0, color=WARM,
                arrowprops=dict(arrowstyle='-', lw=0.5, color=WARM,
                                shrinkA=0, shrinkB=2))

    # (d) declared share against the uplink rate
    ax = fig.add_subplot(gs[0, 3])
    ax.scatter(rate, reg, s=11, color=BLUE, zorder=3)
    ax.axvline(e5['params']['E_UPLINK'] + e5['params']['LAMBDA_CAP'],
               color=WARM, lw=0.7, ls=(0, (3, 2)), zorder=1)
    ax.set_xlabel('uplink rate (CNY/GB)', labelpad=1.5)
    ax.set_ylabel('declare (\\%)')
    ax.set_ylim(0, 60)
    tidy(ax)
    tag(ax, 'd', dx=-0.30)
    ax.set_title('who signs', loc='left', pad=4, fontsize=7.2)

    # (e) omitted: the margin-versus-disguise-cost sweep is Fig. 7(b).
    save(fig, 'figA_sweeps')


def fig10_closures():
    """Two closures of the quota: time (SIEVE) and granularity (TRIBUTARY)."""
    e10 = load('e10_temporal.json')
    e11 = load('e11_farm.json')
    fig = plt.figure(figsize=(FULL, 2.28))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1.06, 1.0, 1.0], left=0.088,
                           right=0.988, top=0.845, bottom=0.235, wspace=0.42)

    # (a) detection rate by schedule and rule
    axa = fig.add_subplot(gs[0, 0])
    names = ['steady', 'alternate', 'pulse', 'ramp']
    cols = ['rule3_rate', 'interval_ratio_rate', 'sieve_rate']
    for i, nm in enumerate(names):
        r = e10['schedules'][nm]
        for j, c in enumerate(cols):
            v = r[c]
            axa.scatter([j], [i], s=8 + 210 * v, color=BLUE if v >= 0.8 else
                        (BLUE3 if v > 0.05 else WASH), alpha=0.85, lw=0.6,
                        edgecolor='white', zorder=3)
            axa.text(j + 0.20, i, '%.2f' % v, ha='left', va='center',
                     fontsize=6.1, color=INK, zorder=4)
    axa.set_xticks([0, 1, 2])
    axa.set_xticklabels(['three\nwindows', 'interval\nratio', 'SIEVE\n+ floor'],
                        fontsize=6.2)
    axa.set_yticks(range(4))
    axa.set_yticklabels(names, fontsize=6.3)
    axa.set_xlim(-0.45, 2.85)
    axa.set_ylim(-0.55, 3.55)
    axa.invert_yaxis()
    tidy(axa, left_only=True)
    axa.spines['bottom'].set_visible(False)
    tag(axa, 'a', dx=-0.34)
    axa.set_title('the same bytes, four rhythms', loc='left', pad=4, fontsize=7.0)

    # (b) lines needed to hide a volume, two quotas
    axb = fig.add_subplot(gs[0, 1])
    law = e11['law']
    for tau, col, mk in ((0.50, BLUE, 'o'), (0.25, BLUE3, 's')):
        pts = [r for r in law if abs(r['tau'] - tau) < 1e-9]
        x = [r['volume_x_household'] for r in pts]
        y = [r['k_law'] for r in pts]
        axb.scatter(x, y, s=16, color=col, marker=mk, lw=0.6, edgecolor='white',
                    zorder=3, label=r'$\tau=%.2f$' % tau)
    axb.set_xscale('log')
    axb.set_yscale('log')
    axb.set_xlabel('volume to hide (households)', labelpad=1.5)
    axb.set_ylabel('households needed')
    axb.legend(frameon=False, fontsize=6.1, loc='upper left',
               handletextpad=0.25, borderpad=0.1)
    axb.annotate('12 lines', xy=(10, 12), xytext=(2.2, 26), fontsize=6.0,
                 color=INK,
                 arrowprops=dict(arrowstyle='-', lw=0.5, color=GREY))
    tidy(axb)
    tag(axb, 'b', dx=-0.26)
    axb.set_title('splitting is linear, not free', loc='left', pad=4, fontsize=7.0)

    # (c) recoverability of the split group from destination overlap
    axc = fig.add_subplot(gs[0, 2])
    scan = e11['confluence']['scan']
    xs = [r['threshold'] for r in scan]
    # recall and precision coincide over the working band, so the two series are
    # drawn at a small offset and with different sizes instead of on top of each
    # other.
    axc.scatter([x - 0.006 for x in xs], [r['recall'] for r in scan], s=26,
                color=BLUE, marker='o', lw=0.6, edgecolor='white', zorder=4,
                label='recall')
    axc.scatter([x + 0.006 for x in xs], [r['precision'] for r in scan], s=14,
                color=WARM, marker='s', lw=0.6, edgecolor='white', zorder=3,
                label='precision')
    for r in scan:
        if r['threshold'] == 0.10:
            axc.annotate('%d lines' % r['component'], xy=(r['threshold'] - 0.006,
                         r['recall']), xytext=(5, 3),
                         textcoords='offset points', ha='left', fontsize=5.8,
                         color=GREY)
        if r['threshold'] == 0.40:
            axc.annotate('seed only', xy=(r['threshold'] - 0.006, r['recall']),
                         xytext=(-4, 6), textcoords='offset points', ha='right',
                         fontsize=5.8, color=GREY)
    axc.set_xlabel('destination-overlap threshold', labelpad=1.5)
    axc.set_ylabel('rate')
    axc.set_ylim(-0.08, 1.16)
    axc.legend(frameon=False, fontsize=6.1, loc='center left',
               handletextpad=0.25, borderpad=0.1)
    tidy(axc)
    tag(axc, 'c', dx=-0.26)
    axc.set_title('visible only inside a band', loc='left', pad=4,
                  fontsize=7.0)
    save(fig, 'fig10_closures')


def fig11_audit():
    e14 = load('e14_policy.json')
    e15 = load('e15_sampling.json')
    fig = plt.figure(figsize=(FULL, 2.05))
    gs = fig.add_gridspec(1, 3, wspace=0.30, left=0.052, right=0.995,
                          top=0.80, bottom=0.20)

    # (a) welfare against the price of the externality
    axa = fig.add_subplot(gs[0, 0])
    hp = e14['harm']['harm_price']
    wf = e14['harm']['welfare']
    series = [('S0', '#9AA9B4', 'inaction'), ('S1', WARM, 'enforcement'),
              ('S2', BLUE, 'spot price'), ('S3', BLUE3, 'declared tiers')]
    for key, col, lab in series:
        axa.plot(hp, wf[key], linestyle='none', marker='o', ms=2.7,
                 mfc=col, mec=col, label=lab, zorder=3)
    # every label is placed where its own curve is the only mark in the window:
    # inaction under its descending arc, the other three left of the right edge.
    for lab, col, xy, ha, va in (
            ('inaction', '#6E7B86', (0.03, 330000), 'left', 'top'),
            ('enforcement', WARM, (0.03, 132000), 'left', 'bottom'),
            ('spot price', BLUE, (hp[-1], wf['S2'][-1]), 'right', 'bottom'),
            ('declared tiers', BLUE3, (hp[-1], wf['S3'][-1]), 'right', 'top')):
        dx = -3 if ha == 'right' else 4
        dy = 4 if va == 'bottom' else -4
        axa.annotate(lab, xy, xytext=(dx, dy), textcoords='offset points',
                     fontsize=6.0, color=col, ha=ha, va=va)
    axa.axvline(0.10, color=WARM, lw=0.7, ls=(0, (3, 1.6)), zorder=1)
    axa.text(0.115, 0.035, 'assumed price', fontsize=5.8, color=WARM,
             ha='left', va='bottom', transform=axa.get_xaxis_transform())
    axa.axhline(0.0, color=INK, lw=0.6, zorder=1)
    axa.set_xlim(0, 0.60)
    axa.set_ylim(-105000, 570000)
    axa.set_xlabel('price of the unpriced externality (CNY/GB)', fontsize=6.6)
    axa.set_ylabel('welfare', fontsize=6.6)
    axa.set_xticks([0, 0.2, 0.4])
    axa.set_yticks([-100000, 0, 200000, 400000])
    axa.set_yticklabels(['−100k', '0', '200k', '400k'], fontsize=6.2)
    axa.tick_params(labelsize=6.2)
    tidy(axa)
    tag(axa, 'a', dx=-0.20)
    axa.set_title('enforcement never crosses', loc='left', pad=4, fontsize=7.0)

    # (b) welfare against the quality of detection
    axb = fig.add_subplot(gs[0, 1])
    det = e14['detection']
    axb.plot(det['tpr'], det['welfare_S1'], linestyle='none', marker='o', ms=2.9,
             mfc=WARM, mec=WARM, zorder=3)
    axb.plot(det['tpr'], det['welfare_S3'], linestyle='none', marker='s', ms=2.7,
             mfc=BLUE, mec=BLUE, zorder=3)
    axb.annotate('enforcement', (0.06, 24000), fontsize=6.0, color=WARM,
                 ha='left', va='center')
    axb.annotate('declared tiers', (0.62, det['welfare_S3'][12]), xytext=(0, -3.2),
                 textcoords='offset points', fontsize=6.0, color=BLUE, ha='center',
                 va='top')
    axb.set_xlim(-0.02, 1.02)
    axb.set_xlabel('share of distributors a detector finds', fontsize=6.6)
    axb.set_ylabel('welfare', fontsize=6.6)
    axb.set_xticks([0, 0.5, 1.0])
    axb.set_yticks([0, 150000, 300000, 450000])
    axb.set_yticklabels(['0', '150k', '300k', '450k'], fontsize=6.2)
    axb.tick_params(labelsize=6.2)
    tidy(axb)
    tag(axb, 'b', dx=-0.22)
    axb.set_title('more detection, less welfare', loc='left', pad=4,
                  fontsize=7.0)

    # (c) what sampling costs the primitive
    axc = fig.add_subplot(gs[0, 2])
    rows = e15['rows']
    dil = [1.0 / r['rate'] for r in rows]
    axc.plot(dil, [r['coverage'] for r in rows], linestyle='none', marker='o',
             ms=2.9, mfc=BLUE4, mec=BLUE, mew=0.7, zorder=3, label='cells kept')
    axc.plot(dil, [r['tpr'] for r in rows], linestyle='none', marker='s', ms=2.7,
             mfc='white', mec=BLUE, mew=0.8, zorder=3, label='capture')
    axc.plot(dil, [r['fp'] for r in rows], linestyle='none', marker='^', ms=3.0,
             mfc=WARM, mec=WARM, zorder=3, label='false alarm')
    axc.axvline(20, color=WARM, lw=0.7, ls=(0, (3, 1.6)), zorder=1)
    axc.text(26, 0.42, '1 in 20', fontsize=5.9, color=WARM, ha='left')
    axc.legend(frameon=False, fontsize=6.0, loc='center left',
               bbox_to_anchor=(0.015, 0.52), handletextpad=0.3,
               borderpad=0.1, labelspacing=0.32)
    axc.set_xscale('log')
    axc.set_xlim(0.85, 2600)
    axc.set_ylim(-0.02, 1.06)
    axc.set_xlabel('flow sampling, one record kept in N', fontsize=6.6)
    axc.set_ylabel('fraction', fontsize=6.6)
    axc.set_xticks([1, 10, 100, 1000])
    axc.set_xticklabels(['1', '10', '100', '1000'], fontsize=6.2)
    axc.set_yticks([0, 0.5, 1.0])
    axc.tick_params(labelsize=6.2)
    tidy(axc)
    tag(axc, 'c', dx=-0.20)
    axc.set_title('sampling starves the thin cells', loc='left', pad=4,
                  fontsize=7.0)
    save(fig, 'fig11_audit')


if __name__ == '__main__':
    which = sys.argv[1:] or ['1', '2', '3', '4', '5', '6', '7', '8', '10', '11',
                             'A']
    fns = {'1': fig1_mechanism, '2': fig2_separation, '3': fig3_evasion,
           '4': fig4_robustness, '5': fig5_peeringdb, '6': fig6_window,
           '7': fig7_regimes, '8': fig8_meter, '10': fig10_closures,
           '11': fig11_audit, 'A': figA_sweeps}
    for k in which:
        print('figure', k)
        fns[k]()
