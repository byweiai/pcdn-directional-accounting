"""Build references.bib from Crossref records pinned by DOI.

Every entry names its venue explicitly, because Crossref container titles are
sometimes truncated and sometimes carry HTML entities.  Target-journal entries
(TSNE / Computer Networks, 2024-2026) are pulled from the local OpenAlex dumps
so authors, volume and pages match the indexed record exactly; older or
elsewhere-published entries go straight to Crossref by DOI.

Usage:  py -3.13 src\\make_bib.py
"""
import html
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'paper')
UA = 'pcdn-metric-paper/1.0 (mailto:lvyue@yn.chinamobile.com)'

TSNE = 'IEEE Trans. Netw. Sci. Eng.'
CN = 'Comput. Netw.'

# (key, doi, venue, source)  source: tnse | comnet | crossref
ENTRIES = [
    # --- target journal: IEEE TNSE ---------------------------------------
    ('liu2026pcdn', '10.1109/tnse.2026.3682795', TSNE, 'tnse'),
    ('ecoshield2026', '10.1109/tnse.2026.3664638', TSNE, 'tnse'),
    ('gflow2024', '10.1109/tnse.2024.3481413', TSNE, 'tnse'),
    ('gtcc2024', '10.1109/tnse.2024.3443099', TSNE, 'tnse'),
    ('proxadyn2025', '10.1109/tnse.2025.3547424', TSNE, 'tnse'),
    ('eigenobfu2024', '10.1109/tnse.2024.3501396', TSNE, 'tnse'),
    ('dynnet2026', '10.1109/tnse.2026.3673521', TSNE, 'tnse'),
    # --- target journal: Computer Networks --------------------------------
    ('fu2026pcdn', '10.1016/j.comnet.2026.112838', CN, 'comnet'),
    ('encryptovision2025', '10.1016/j.comnet.2025.111499', CN, 'comnet'),
    ('adept2026', '10.1016/j.comnet.2026.112352', CN, 'comnet'),
    ('degnn2024', '10.1016/j.comnet.2024.110372', CN, 'comnet'),
    ('eapt2024', '10.1016/j.comnet.2024.110973', CN, 'comnet'),
    ('graphmux2026', '10.1016/j.comnet.2026.112370', CN, 'comnet'),
    ('halo2026', '10.1016/j.comnet.2026.112656', CN, 'comnet'),
    ('encsurvey2026', '10.1016/j.comnet.2026.112524', CN, 'comnet'),
    ('corepow2024', '10.1016/j.comnet.2024.110312', CN, 'comnet'),
    ('bico2011', '10.1016/j.comnet.2011.02.009', CN, 'crossref'),
    ('sdnreroute2017', '10.1016/j.comnet.2016.12.010', CN, 'crossref'),
    ('sdcdn2022', '10.1016/j.comnet.2021.108686', CN, 'crossref'),
    # --- adjacent journals ------------------------------------------------
    ('cose2024', '10.1016/j.cose.2024.104283', 'Comput. Secur.', 'crossref'),
    ('tdsc2026', '10.1109/tdsc.2025.3615592', 'IEEE Trans. Dependable Secure Comput.', 'crossref'),
    ('sla5g2021', '10.1109/tnsm.2021.3102890', 'IEEE Trans. Netw. Service Manag.', 'crossref'),
    ('mon5g2022', '10.1109/tnsm.2022.3150586', 'IEEE Trans. Netw. Service Manag.', 'crossref'),
    ('seta2021', '10.1109/tnsm.2021.3085097', 'IEEE Trans. Netw. Service Manag.', 'crossref'),
    ('ccfeedback2025', '10.1109/tnsm.2025.3648180', 'IEEE Trans. Netw. Service Manag.', 'crossref'),
    ('ispcdn2015', '10.1109/tnsm.2015.2404792', 'IEEE Trans. Netw. Service Manag.', 'crossref'),
    ('edgeprice2023', '10.1109/tmc.2023.3334914', 'IEEE Trans. Mobile Comput.', 'crossref'),
    ('telpol2023', '10.1016/j.telpol.2023.102621', 'Telecommun. Policy', 'crossref'),
    ('jinfopol2022', '10.5325/jinfopoli.12.2022.0006', 'J. Inf. Policy', 'crossref'),
    ('csur2013', '10.1145/2480741.2480742', 'ACM Comput. Surv.', 'crossref'),
    ('isr2012', '10.1287/isre.1120.0420', 'Inf. Syst. Res.', 'crossref'),
    ('dpi2012', '10.24908/ss.v9i4.4340', 'Surveillance Soc.', 'crossref'),
    ('ieice2011', '10.1587/transinf.e94.d.2460',
     'IEICE Trans. Inf. Syst.', 'crossref'),
    ('netnomics2017', '10.1007/s11066-017-9114-x',
     'NETNOMICS: Econ. Res. Electron. Netw.', 'crossref'),
    ('nrl2025', '10.1002/nav.22241', 'Naval Res. Logist.', 'crossref'),
    # --- conference papers (booktitle, not journal) -----------------------
    ('aann2026', '10.1109/aann71145.2026.11709229',
     'Proc. IEEE Int. Conf. Artif. Neural Netw. (AANN)', 'inproc'),
    ('unsw2015', '10.1109/milcis.2015.7348942',
     'Proc. Mil. Commun. Inf. Syst. Conf. (MilCIS)', 'inproc'),
    ('cic2018', '10.5220/0006639801080116',
     'Proc. 4th Int. Conf. Inf. Syst. Secur. Privacy (ICISSP)', 'inproc'),
]


def get(url):
    for k in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:  # noqa: BLE001
            if k == 4:
                print('  FAILED', url, e)
                return None
            time.sleep(1.5 + 1.5 * k)
    return None


def from_openalex(dump, doi):
    path = os.path.join(DATA, dump + '_oa.json')
    for w in json.load(io.open(path, encoding='utf-8')):
        if (w.get('doi') or '').lower() == doi.lower():
            return w
    return None


def esc(s):
    s = html.unescape(s or '')
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('\n', ' ').replace('  ', ' ').strip()
    s = s.replace('&', r'\&').replace('%', r'\%').replace('_', r'\_')
    return s


def pages(a, b):
    if not a:
        return None
    a, b = str(a), str(b)
    return a if (not b or a == b) else '%s--%s' % (a, b)


def write_entry(key, authors, title, venue, year, volume, number, page, doi, kind):
    tag = 'inproceedings' if kind == 'inproc' else 'article'
    field = 'booktitle' if kind == 'inproc' else 'journal'
    L = ['@%s{%s,' % (tag, key),
         '  author    = {%s},' % ' and '.join(authors),
         '  title     = {{%s}},' % esc(title),
         '  %-9s = {%s},' % (field, esc(venue))]
    if volume:
        L.append('  volume    = {%s},' % volume)
    if number:
        L.append('  number    = {%s},' % number)
    if page:
        L.append('  pages     = {%s},' % page)
    L.append('  year      = {%s},' % year)
    if doi:
        L.append('  doi       = {%s},' % doi)
    L.append('}')
    return '\n'.join(L)


def main():
    os.makedirs(OUT, exist_ok=True)
    blocks, log, missing = [], [], []

    for key, doi, venue, src in ENTRIES:
        # Crossref is authoritative for names; the local dump fills gaps only.
        m = get('https://api.crossref.org/works/' + urllib.parse.quote(doi))
        au, title, yr, vol, num, pg, how = [], None, None, None, None, None, 'crossref'
        if m:
            m = m['message']
            for a in m.get('author', []):
                g, f = a.get('given', ''), a.get('family', '')
                au.append(('%s %s' % (g, f)).strip() or a.get('name', ''))
            title = (m.get('title') or [''])[0]
            yr = (m.get('issued', {}).get('date-parts') or [[None]])[0][0]
            vol, num, pg = m.get('volume'), m.get('issue'), m.get('page')

        if src in ('tnse', 'comnet'):
            w = from_openalex(src, doi)
            if w:
                if not title:
                    title, how = w['title'], 'openalex'
                yr = yr or w['year']
                vol = vol or w.get('volume')
                num = num or w.get('issue')
                pg = pg or pages(w.get('first_page'), w.get('last_page'))
                if not au:
                    au, how = w['authors'], 'openalex'
        if not (au and title and yr):
            missing.append((key, doi, 'no usable record'))
            continue
        blocks.append(write_entry(key, au, title, venue, yr, vol, num, pg, doi,
                                  'inproc' if src == 'inproc' else 'article'))
        log.append((key, yr, venue, how, title))

    blocks.append('\n'.join([
        '@misc{peeringdb2026,',
        '  title        = {{PeeringDB}},' ,
        '  author       = {{PeeringDB}},',
        '  howpublished = {\\url{https://www.peeringdb.com}},',
        '  year         = {2026},',
        '  note         = {Network, facility and interconnection registry; accessed 6 Nov. 2026}',
        '}']))
    log.append(('peeringdb2026', 2026, 'online registry', 'manual', 'PeeringDB'))

    path = os.path.join(OUT, 'references.bib')
    io.open(path, 'w', encoding='utf-8').write('\n\n'.join(blocks) + '\n')
    print('wrote %s (%d entries)' % (path, len(blocks)))
    for k, y, v, how, t in log:
        print('  %-20s %-5s %-42s %-8s %s' % (k, y, str(v)[:42], how, str(t)[:60]))
    if missing:
        print('\nMISSING:')
        for k, d, why in missing:
            print('  ', k, d, why)
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
