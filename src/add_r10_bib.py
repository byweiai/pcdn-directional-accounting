"""Append the R10 references to references.bib, IEEE style, once.

The metadata comes from data/refs_r10.json, which was built from Crossref
/works/{doi} lookups; this script only formats, it does not invent fields.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'refs_r10.json')
BIB = os.path.join(ROOT, 'paper', 'references.bib')

JOURNAL = {
    'xie2008p4p': ('proc', 'Proc. ACM SIGCOMM', ''),
    'poese2012itracker': ('article', 'ACM SIGCOMM Comput. Commun. Rev.', ''),
    'seedorf2009alto': ('proc', 'Proc. IEEE Int. Conf. Peer-to-Peer Comput. (P2P)', ''),
    'little2000settlement': ('article', 'J. Regulatory Econ.', ''),
    'teixeira2004hotpotato': ('article', 'ACM SIGMETRICS Perform. Eval. Rev.', ''),
    'wang2021paidpeering': ('article', 'IEEE/ACM Trans. Netw.', ''),
    'genakos2011waterbed': ('article', 'J. Eur. Econ. Assoc.', ''),
    'kramer2012flatrate': ('article', 'Telecommun. Policy', ''),
    'zhao2024p95': ('article', 'IEEE/ACM Trans. Netw.', ''),
    'deneckere1996damaged': ('article', 'J. Econ. Manage. Strategy', ''),
    'mi2019residentevil': ('proc', 'Proc. IEEE Symp. Security Privacy (S&P)', ''),
    'yang2022residential': ('proc', 'Proc. ACM SIGSAC Conf. Comput. Commun. Secur. (CCS)', ''),
}


def fmt_name(a):
    g = (a.get('given') or '').strip()
    f = (a.get('family') or '').strip()
    if not g:
        return f
    initials = ' '.join(p[0] + '.' for p in g.replace('-', ' ').split() if p)
    return '%s %s' % (initials, f)


def entry(r):
    kind, venue, _ = JOURNAL[r['key']]
    authors = ' and '.join(fmt_name(a) for a in r['authors'])
    lines = ['@%s{%s,' % ('inproceedings' if kind == 'proc' else 'article', r['key']),
             '  author    = {%s},' % authors,
             '  title     = {{%s}},' % r['title']]
    key = 'booktitle' if kind == 'proc' else 'journal'
    lines.append('  %-9s = {%s},' % (key, venue))
    if r.get('volume'):
        lines.append('  volume    = {%s},' % r['volume'])
    if r.get('issue'):
        lines.append('  number    = {%s},' % r['issue'])
    if r.get('pages'):
        lines.append('  pages     = {%s},' % r['pages'].replace('--', '-'))
    lines.append('  year      = {%s},' % r['year'])
    lines.append('  doi       = {%s},' % r['doi'])
    lines.append('}')
    return '\n'.join(lines)


def main():
    refs = json.load(open(SRC, encoding='utf-8'))['refs']
    text = open(BIB, encoding='utf-8').read()
    added, skipped = [], []
    blocks = []
    for r in refs:
        if '@%s{' % r['key'] in text or '{%s,' % r['key'] in text:
            skipped.append(r['key'])
            continue
        blocks.append(entry(r))
        added.append(r['key'])
    if blocks:
        with open(BIB, 'a', encoding='utf-8') as fh:
            for b in blocks:
                fh.write('\n' + b + '\n')
    print('added %d: %s' % (len(added), ', '.join(added)))
    print('skipped %d: %s' % (len(skipped), ', '.join(skipped)))
    n = sum(1 for line in open(BIB, encoding='utf-8') if line.startswith('@'))
    print('total entries now', n)


if __name__ == '__main__':
    main()
