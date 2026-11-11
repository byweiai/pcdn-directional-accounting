# -*- coding: utf-8 -*-
"""E7: does the meter fit in a softwarized core?

The mechanism needs one thing from the network: for each subscriber, the bytes
it sent and the bytes it received, aggregated over a window. That is two
counters and an address. This experiment measures the cost of keeping them and
the error of keeping them in bounded memory, so the deployment section can state
a number instead of an assurance.

Three implementations are compared on the same synthetic workload:

  exact   dict keyed by address, two integer accumulators
  cms     count-min sketch, width x depth counters, conservative update
  ss      space-saving, k counters, replaces the minimum on a miss

The workload is Zipf over subscriber addresses, alpha given, because subscriber
traffic is heavy tailed: most bytes come from few endpoints, which is exactly
the case E1 measured.
"""
import json, os, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'data', 'e7_meter.json')

N_SUBS = 20000
N_RECORDS = 2_000_000
SEEDS = (11, 12, 13)
ZIPF_ALPHA = 1.10
PACKET_BYTES = np.array([64, 128, 256, 512, 1024, 1500], dtype=np.int64)
PACKET_P = np.array([0.28, 0.16, 0.13, 0.14, 0.17, 0.12])


class ExactMeter:
    def __init__(self):
        self.up = {}
        self.dn = {}

    def add(self, addr, nbytes, uplink):
        d = self.up if uplink else self.dn
        d[addr] = d.get(addr, 0) + nbytes


class CountMin:
    def __init__(self, width=4096, depth=4):
        self.w = width
        self.d = depth
        self.t = [[0] * width for _ in range(depth)]
        self.mask = width - 1

    def add(self, addr, nbytes):
        h = hash(addr)
        est = min(self.t[i][(h >> (i * 13)) & self.mask] for i in range(self.d))
        for i in range(self.d):
            j = (h >> (i * 13)) & self.mask
            if self.t[i][j] <= est:
                self.t[i][j] += nbytes

    def get(self, addr):
        h = hash(addr)
        return min(self.t[i][(h >> (i * 13)) & self.mask] for i in range(self.d))


class SpaceSaving:
    def __init__(self, k=4096):
        self.k = k
        self.d = {}
        self.err = {}

    def add(self, addr, nbytes):
        d = self.d
        if addr in d:
            d[addr] += nbytes
            return
        if len(d) < self.k:
            d[addr] = nbytes
            self.err[addr] = 0
            return
        victim = min(d, key=d.get)
        base = d.pop(victim)
        e = self.err.pop(victim)
        d[addr] = base + nbytes
        self.err[addr] = base + e

    def get(self, addr):
        return self.d.get(addr, 0)


def workload(seed):
    rng = np.random.default_rng(seed)
    p = 1.0 / np.arange(1, N_SUBS + 1) ** ZIPF_ALPHA
    p /= p.sum()
    addr = rng.choice(N_SUBS, size=N_RECORDS, p=p)
    size = rng.choice(PACKET_BYTES, size=N_RECORDS, p=PACKET_P)
    up = rng.random(N_RECORDS) < 0.5
    return addr, size, up


def time_exact(addr, size, up):
    m = ExactMeter()
    t0 = time.perf_counter()
    for i in range(len(addr)):
        m.add(int(addr[i]), int(size[i]), bool(up[i]))
    dt = time.perf_counter() - t0
    return dt, m


def time_cms(addr, size):
    m = CountMin(width=4096, depth=4)
    t0 = time.perf_counter()
    for i in range(len(addr)):
        m.add(int(addr[i]), int(size[i]))
    dt = time.perf_counter() - t0
    return dt, m


def time_ss(addr, size):
    m = SpaceSaving(k=4096)
    t0 = time.perf_counter()
    for i in range(len(addr)):
        m.add(int(addr[i]), int(size[i]))
    dt = time.perf_counter() - t0
    return dt, m


def main():
    print('== E7: cost and error of the per-subscriber meter ==')
    print('  %d records, %d subscribers, Zipf alpha %.2f' % (N_RECORDS, N_SUBS, ZIPF_ALPHA))

    rows = []
    for seed in SEEDS:
        addr, size, up = workload(seed)
        truth = np.bincount(addr, weights=size, minlength=N_SUBS)

        dt, m = time_exact(addr, size, up)
        tot = dict(m.up)
        for k, v in m.dn.items():
            tot[k] = tot.get(k, 0) + v
        exact_err = 0.0
        mem_exact = len(m.up) + len(m.dn)

        dt_cms, cms = time_cms(addr, size)
        top = np.argsort(truth)[-100:]
        cms_err = np.mean([abs(cms.get(int(i)) - truth[i]) / max(1, truth[i]) for i in top])

        dt_ss, ss = time_ss(addr, size)
        ss_err = np.mean([abs(ss.get(int(i)) - truth[i]) / max(1, truth[i]) for i in top])

        rows.append({'seed': seed,
                     'exact_mps': N_RECORDS / dt / 1e6,
                     'cms_mps': N_RECORDS / dt_cms / 1e6,
                     'ss_mps': N_RECORDS / dt_ss / 1e6,
                     'exact_counters': mem_exact,
                     'exact_rel_err': exact_err,
                     'cms_bits': 4096 * 4 * 32,
                     'cms_rel_err_top100': float(cms_err),
                     'ss_bits': 4096 * 48,
                     'ss_rel_err_top100': float(ss_err)})
        print('  seed %d | exact %6.2f Mrec/s | cms %6.3f | ss %6.3f | '
              'cms err %5.2f%% | ss err %5.2f%%'
              % (seed, rows[-1]['exact_mps'], rows[-1]['cms_mps'], rows[-1]['ss_mps'],
                 100 * cms_err, 100 * ss_err))

    m_ = lambda k: float(np.mean([r[k] for r in rows]))
    s_ = lambda k: float(np.std([r[k] for r in rows]))
    summary = {'records_per_sec_exact': m_('exact_mps') * 1e6,
               'records_per_sec_exact_sd': s_('exact_mps') * 1e6,
               'records_per_sec_cms': m_('cms_mps') * 1e6,
               'records_per_sec_ss': m_('ss_mps') * 1e6,
               'cms_rel_err_mean': m_('cms_rel_err_top100'),
               'ss_rel_err_mean': m_('ss_rel_err_top100'),
               'cms_memory_kib': 4096 * 4 * 4 / 1024,
               'ss_memory_kib': 4096 * 6 / 1024,
               'exact_counters_max': max(r['exact_counters'] for r in rows),
               'active_share': float(len(np.unique(workload(SEEDS[0])[0])) / N_SUBS)}

    # what load does that throughput correspond to?
    mean_pkt = float((PACKET_BYTES * PACKET_P).sum())
    summary['mean_packet_bytes'] = mean_pkt
    summary['gbps_at_mean_packet'] = summary['records_per_sec_exact'] * 8 * mean_pkt / 1e9
    print('\n  the benchmark draws packets with the study packet-size mix,')
    print('  so its own mean is %.1f B, not the 1 kB round number:' % mean_pkt)
    print('    one exact-meter core sustains %5.1f Gbps at %.1f B'
          % (summary['gbps_at_mean_packet'], mean_pkt))
    for gbps in (1, 10, 40, 100):
        pps = gbps * 1e9 / 8 / mean_pkt
        print('    %3d Gbps -> %6.2f Mpps at %.1f B' % (gbps, pps / 1e6, mean_pkt))

    print('\n  bounded memory: cms %.0f KiB (4 x 4096 x 32 bit), ss %.0f KiB (4096 x 48 bit)'
          % (summary['cms_memory_kib'], summary['ss_memory_kib']))
    exact_kib = N_SUBS * (8 + 8) / 1024.0
    print('  exact meter: one address and one counter per subscriber, %d B each, '
          'so %.0f KiB for the whole base of %d' % (16, exact_kib, N_SUBS))
    print('  relative error on the top 100 subscribers: cms %.2f%%, space-saving %.2f%%'
          % (100 * summary['cms_rel_err_mean'], 100 * summary['ss_rel_err_mean']))
    print('  NOTE space-saving is reported for memory and error only: its Python')
    print('       reference scans k counters on a miss, so its throughput here')
    print('       measures dict.min(), not the algorithm. A heap implementation')
    print('       is the fair comparison and is not built here.')

    json.dump({'params': {'N_SUBS': N_SUBS, 'N_RECORDS': N_RECORDS, 'SEEDS': list(SEEDS),
                          'ZIPF_ALPHA': ZIPF_ALPHA, 'PACKET_BYTES': PACKET_BYTES.tolist(),
                          'PACKET_P': PACKET_P.tolist()},
               'runs': rows, 'summary': summary},
              open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
