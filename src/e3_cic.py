# -*- coding: utf-8 -*-
"""E3: does the directional ratio carry over to an independent capture?

E1 established the separation on UNSW-NB15. A single dataset invites the
objection that the effect is an artefact of one testbed: one topology, one
traffic generator, one extraction tool. This experiment repeats the measurement
on CIC-IDS2017 flows, extracted by a different team with a different tool from a
different network five semesters later, and asks three things.

  * Does the endpoint-level rho distribution keep its two-lobed shape, and is
    the gap between the lobes still wide enough to place a threshold in?
  * Does the subscriber-side upper quantile land near the same place?
  * Does a weak role label that does not use bytes at all -- who owns the low
    port -- still sort the two lobes the same way?

The third question matters because it is the one a referee will ask: if rho
separates the lobes only because the lobes were defined by rho, the finding is
circular. Port ownership is fixed by the service a host offers, not by how much
it sends.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'e3_cic.json')

# Addresses that cannot be a subscriber endpoint: link-local, multicast,
# broadcast, and the unspecified address.
BAD_PREFIX = ('fe80:', 'ff0', 'ff1', 'ff2', '224.', '239.', '0.', '255.')
SERVICE_PORTS = {20, 21, 22, 23, 25, 53, 67, 68, 69, 80, 110, 123, 135, 137,
                 138, 139, 143, 161, 162, 179, 389, 443, 445, 465, 514, 587,
                 636, 993, 995, 1433, 1521, 2049, 3306, 3389, 5060, 5432,
                 5900, 6379, 8080, 8443, 9200, 27017}


def load():
    p = os.path.join(DATA, 'raw', 'ids_cic_binary_head.csv')
    df = pd.read_csv(p, usecols=['SRC_IP', 'DST_IP', 'SRC_PORT', 'DST_PORT',
                                 'TIME_FIRST', 'LABEL', 'BYTES', 'BYTES_REV'],
                     low_memory=False, on_bad_lines='skip')
    df = df.dropna(subset=['SRC_IP', 'DST_IP'])
    return df


def clean(df):
    m = ~df['SRC_IP'].astype(str).str.startswith(BAD_PREFIX)
    m &= ~df['DST_IP'].astype(str).str.startswith(BAD_PREFIX)
    m &= (df['BYTES'] + df['BYTES_REV']) > 0
    return df[m].copy()


def endpoint_rho(df, min_flows=5):
    """Accumulate each address's sent and received bytes.

    A flow record reports the initiator's bytes in BYTES and the responder's in
    BYTES_REV. So a host's sent total is what it originated plus what it
    answered, and its received total is the mirror.

    The role label uses only port ownership: an address that terminates at least
    half of its flows on a well-known port is acting as a service. Bytes never
    enter the label.
    """
    src, dst = df['SRC_IP'].values, df['DST_IP'].values
    b, br = df['BYTES'].values.astype('int64'), df['BYTES_REV'].values.astype('int64')
    dport = df['DST_PORT'].values
    is_svc_port = np.isin(dport, list(SERVICE_PORTS))

    sent = {}
    recv = {}
    nflow = {}
    n_svc = {}
    for ip, mb, mbr in ((src, b, br), (dst, br, b)):
        # np.add.at is slow here; use pandas grouping instead below
        pass

    ent = pd.DataFrame({
        'ip_s': src, 'ip_d': dst,
        'sent_s': b, 'recv_s': br,      # bytes the source sent / received
        'sent_d': br, 'recv_d': b,      # bytes the destination sent / received
        'svc': is_svc_port,
    })
    a = ent.groupby('ip_s').agg(sent=('sent_s', 'sum'), recv=('recv_s', 'sum'),
                                n=('sent_s', 'size'))
    bb = ent.groupby('ip_d').agg(sent=('sent_d', 'sum'), recv=('recv_d', 'sum'),
                                 n=('sent_d', 'size'))
    agg = a.add(bb, fill_value=0)
    agg = agg[agg['n'] >= min_flows]
    agg['rho'] = agg['sent'] / (agg['sent'] + agg['recv']).replace(0, np.nan)
    agg = agg.dropna(subset=['rho'])

    svc = ent[ent['svc']].groupby('ip_d').size()
    allasd = ent.groupby('ip_d').size()
    share = (svc.reindex(allasd.index).fillna(0) / allasd)
    agg['svc_share'] = share.reindex(agg.index).fillna(0)
    agg['role'] = np.where(agg['svc_share'] >= 0.5, 'service', 'client')
    return agg


def kde_modes(x, grid=512, bw=None):
    """Gaussian KDE on [0,1] by reflection; return grid, density, local maxima."""
    x = np.asarray(x, dtype=float)
    if bw is None:
        # Silverman, on the reflected sample
        s = x.std(ddof=1)
        n = len(x)
        bw = 0.9 * min(s, float(np.subtract(*np.percentile(x, [75, 25]))) / 1.349) * n ** (-1 / 5)
        bw = max(bw, 0.01)
    g = np.linspace(0, 1, grid)
    k = np.exp(-0.5 * ((g[:, None] - x[None, :]) / bw) ** 2)
    dens = k.sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))
    # local maxima
    peaks = [i for i in range(1, grid - 1)
             if dens[i] > dens[i - 1] and dens[i] >= dens[i + 1]]
    peaks = sorted(peaks, key=lambda i: -dens[i])[:4]
    return g, dens, sorted(peaks), bw


def main():
    print('== E3: the directional ratio on an independent capture ==')
    df = load()
    print('  raw flows: %d' % len(df))
    df = clean(df)
    print('  usable flows after address hygiene: %d' % len(df))
    print('  attack-labelled share: %.3f' % df['LABEL'].mean())

    results = {}
    for tag, sub in (('all', df), ('benign', df[~df['LABEL']])):
        agg = endpoint_rho(sub)
        rho = agg['rho'].values
        g, dens, peaks, bw = kde_modes(rho)
        peak_pos = [float(g[i]) for i in peaks]
        # gap: the lowest-density point between the two strongest peaks
        gap = None
        if len(peaks) >= 2:
            lo, hi = min(peaks[:2]), max(peaks[:2])
            j = lo + int(np.argmin(dens[lo:hi + 1]))
            gap = {'rho': float(g[j]), 'density': float(dens[j]),
                   'peaks': [float(g[lo]), float(g[hi])]}
        svc = agg.loc[agg['role'] == 'service', 'rho']
        cli = agg.loc[agg['role'] == 'client', 'rho']
        # probability a random service endpoint outranks a random client one
        if len(svc) and len(cli):
            cmp = (svc.values[:, None] > cli.values[None, :])
            auc = float(cmp.mean() + 0.5 * (svc.values[:, None] == cli.values[None, :]).mean())
        else:
            auc = float('nan')
        results[tag] = {
            'n_endpoints': int(len(agg)),
            'n_service': int(len(svc)), 'n_client': int(len(cli)),
            'rho_quantiles': {q: float(np.quantile(rho, q)) for q in
                              [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]},
            'service_median': float(svc.median()) if len(svc) else None,
            'client_median': float(cli.median()) if len(cli) else None,
            'client_p90': float(np.quantile(cli, 0.90)) if len(cli) else None,
            'auc_service_vs_client': auc,
            'kde_peaks': peak_pos,
            'kde_bandwidth': bw,
            'gap': gap,
            'kde_grid': [round(float(v), 4) for v in g[::8]],
            'kde_density': [round(float(v), 6) for v in dens[::8]],
        }
        print('\n  [%s]  endpoints=%d  service=%d  client=%d'
              % (tag, len(agg), len(svc), len(cli)))
        print('    rho  client median %.4f (p90 %.4f)   service median %.4f'
              % (results[tag]['client_median'] or float('nan'),
                 results[tag]['client_p90'] or float('nan'),
                 results[tag]['service_median'] or float('nan')))
        print('    P(service rho > client rho) = %.4f' % auc)
        print('    KDE modes at %s   bandwidth %.4f'
              % (['%.3f' % p for p in peak_pos], bw))
        if gap:
            print('    valley between lobes at rho=%.3f (density %.5f), lobes at %.3f / %.3f'
                  % (gap['rho'], gap['density'], gap['peaks'][0], gap['peaks'][1]))

    json.dump(results, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
