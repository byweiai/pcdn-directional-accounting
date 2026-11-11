# -*- coding: utf-8 -*-
"""Minimal, dependency-free pcap reader + per-IP send/receive accounting.

Why this exists
---------------
The claim to be tested is that *uplink/downlink asymmetry* is an observable,
encapsulation-invariant property of an endpoint, and therefore a better
out-of-bounds criterion than a content fingerprint. That claim only becomes
empirical if we can measure, on real traffic, how much each IP sends versus
receives. This module provides exactly that primitive and nothing else:
parse classic pcap (Ethernet / Linux-SLL / raw-IP), walk IPv4+IPv6, and
accumulate bytes per (address, direction).

Direction is assigned *locally*: for every IP we accumulate the bytes it
emitted (as a source) and the bytes it absorbed (as a destination). No
knowledge of which side of the link is 'the ISP' is required, which is what
makes the resulting ratio computable from any vantage point.

Run standalone for a quick look:  python pcap_stats.py <file.pcap> [min_pkts]
"""
import struct
import sys
import collections
import os

PCAP_MAGICS = {
    b'\xd4\xc3\xb2\xa1': ('<', 1_000_000),   # little endian, microseconds
    b'\xa1\xb2\xc3\xd4': ('>', 1_000_000),   # big endian, microseconds
    b'\x4d\x3c\xb2\xa1': ('<', 1_000_000_000),  # little endian, nanoseconds
    b'\xa1\xb2\x3c\x4d': ('>', 1_000_000_000),
}

LINKTYPE_ETHERNET = 1
LINKTYPE_RAW = 101
LINKTYPE_LINUX_SLL = 113
LINKTYPE_LINUX_SLL2 = 276
LINKTYPE_NULL = 0


def iter_packets(path, max_bytes=None):
    """Yield (ts, linktype, frame_bytes) for a classic pcap file."""
    with open(path, 'rb') as f:
        gh = f.read(24)
        if len(gh) < 24:
            return
        magic = gh[:4]
        if magic not in PCAP_MAGICS:
            raise ValueError('not a classic pcap: magic=%s' % magic.hex())
        endian, _ = PCAP_MAGICS[magic]
        # network field is the last 4 bytes of the global header
        linktype = struct.unpack(endian + 'I', gh[20:24])[0]
        read = 0
        while True:
            rh = f.read(16)
            if len(rh) < 16:
                return
            ts_sec, ts_frac, incl, orig = struct.unpack(endian + 'IIII', rh)
            if incl > 262144:      # corrupt / truncated tail
                return
            data = f.read(incl)
            if len(data) < incl:
                return
            read += incl
            if max_bytes and read > max_bytes:
                return
            yield ts_sec + ts_frac / 1e6, linktype, data


def _ip_from_frame(linktype, d):
    """Return (version, l3_offset) or (0, -1)."""
    off = None
    if linktype == LINKTYPE_ETHERNET:
        if len(d) < 14:
            return 0, -1
        et = struct.unpack('>H', d[12:14])[0]
        off = 14
        # VLAN / QinQ
        guard = 0
        while et in (0x8100, 0x88a8, 0x9100) and len(d) >= off + 4 and guard < 3:
            et = struct.unpack('>H', d[off + 2:off + 4])[0]
            off += 4
            guard += 1
        if et not in (0x0800, 0x86DD):
            return 0, -1
    elif linktype == LINKTYPE_RAW:
        off = 0
    elif linktype == LINKTYPE_LINUX_SLL:
        if len(d) < 16:
            return 0, -1
        off = 16
    elif linktype == LINKTYPE_LINUX_SLL2:
        if len(d) < 20:
            return 0, -1
        off = 20
    elif linktype == LINKTYPE_NULL:
        off = 4
    else:
        return 0, -1
    if len(d) <= off:
        return 0, -1
    v = d[off] >> 4
    if v == 4:
        return 4, off
    if v == 6:
        return 6, off
    return 0, -1


def parse_addr(ver, d, off):
    """Return (src_bytes_addr, dst_bytes_addr, total_len, proto, payload_len)."""
    if ver == 4:
        if len(d) < off + 20:
            return None
        ihl = (d[off] & 0x0F) * 4
        total = struct.unpack('>H', d[off + 2:off + 4])[0]
        proto = d[off + 9]
        frag = struct.unpack('>H', d[off + 6:off + 8])[0]
        src = d[off + 12:off + 16]
        dst = d[off + 16:off + 20]
        # count only the first fragment of a datagram to avoid double counting
        more_frag = (frag & 0x2000) != 0
        frag_off = frag & 0x1FFF
        if frag_off != 0:
            return ('v4skip', src, dst, 0, proto, 0)
        return ('v4', src, dst, total, proto, max(0, total - ihl))
    else:
        if len(d) < off + 40:
            return None
        plen = struct.unpack('>H', d[off + 4:off + 6])[0]
        nxt = d[off + 6]
        src = d[off + 8:off + 24]
        dst = d[off + 24:off + 40]
        return ('v6', src, dst, 40 + plen, nxt, plen)


def per_ip_accounting(path, max_bytes=None):
    """Accumulate sent/recv bytes and packets per IP address.

    Returns dict with:
      sent[addr]  bytes emitted by this address as source
      recv[addr]  bytes absorbed by this address as destination
      pkts_sent / pkts_recv
      total_pkts / total_bytes / skipped
      tcp_dst_port_counter   (top destination ports, TCP)
      distinct_peers[addr]   -> set size approximated by counter
    """
    sent = collections.Counter()
    recv = collections.Counter()
    psent = collections.Counter()
    precv = collections.Counter()
    dport = collections.Counter()
    peers_out = collections.defaultdict(set)
    peers_in = collections.defaultdict(set)
    total_pkts = 0
    total_bytes = 0
    skipped = 0

    for ts, lt, d in iter_packets(path, max_bytes):
        total_pkts += 1
        ver, off = _ip_from_frame(lt, d)
        if ver == 0:
            skipped += 1
            continue
        p = parse_addr(ver, d, off)
        if p is None:
            skipped += 1
            continue
        kind, src, dst, tot, proto, pay = p
        if kind == 'v4skip':
            continue
        if tot <= 0 or tot > 65535:
            skipped += 1
            continue
        total_bytes += tot
        sent[src] += tot
        recv[dst] += tot
        psent[src] += 1
        precv[dst] += 1
        # cap peer sets so memory stays bounded on big captures
        if len(peers_out[src]) < 512:
            peers_out[src].add(dst)
        if len(peers_in[dst]) < 512:
            peers_in[dst].add(src)
        if proto == 6 and len(d) >= off + (20 if ver == 4 else 40) + 4:
            base = off + ((d[off] & 0x0F) * 4 if ver == 4 else 40)
            dp = struct.unpack('>H', d[base + 2:base + 4])[0]
            dport[dp] += 1

    return {
        'sent': sent, 'recv': recv, 'psent': psent, 'precv': precv,
        'dport': dport, 'peers_out': peers_out, 'peers_in': peers_in,
        'total_pkts': total_pkts, 'total_bytes': total_bytes, 'skipped': skipped,
    }


def addr_str(b):
    if len(b) == 4:
        return '%d.%d.%d.%d' % tuple(b)
    # ipv6: compress zero runs minimally for readability
    parts = ['%02x%02x' % (b[i], b[i + 1]) for i in range(0, 16, 2)]
    return ':'.join(parts)


if __name__ == '__main__':
    path = sys.argv[1]
    minp = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    acc = per_ip_accounting(path)
    print('packets=%d bytes=%d skipped=%d' % (acc['total_pkts'], acc['total_bytes'], acc['skipped']))
    ips = set(acc['sent']) | set(acc['recv'])
    print('distinct IPs:', len(ips))
    rows = []
    for ip in ips:
        s = acc['sent'].get(ip, 0)
        r = acc['recv'].get(ip, 0)
        n = acc['psent'].get(ip, 0) + acc['precv'].get(ip, 0)
        if n < minp or (s + r) == 0:
            continue
        rows.append((s / (s + r), s, r, n, ip))
    rows.sort(reverse=True)
    print('\nmost send-dominated (asym = sent/(sent+recv)):')
    for a, s, r, n, ip in rows[:15]:
        print('  asym=%.3f sent=%.1fMB recv=%.1fMB pkts=%-7d %s' % (a, s / 1e6, r / 1e6, n, addr_str(ip)))
    print('\nleast (most receive-dominated):')
    for a, s, r, n, ip in rows[-10:]:
        print('  asym=%.3f sent=%.1fMB recv=%.1fMB pkts=%-7d %s' % (a, s / 1e6, r / 1e6, n, addr_str(ip)))
