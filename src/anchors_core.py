# -*- coding: utf-8 -*-
"""Find verifiable, peer-reviewed anchors for the core-network mapping.

3GPP and ETSI document servers reject automated access with 403, so no spec
text can be quoted or paraphrased here. What can be verified is the published
literature that describes the same functions, and the target journals are the
best place to look because those citations serve two purposes at once.
"""
import json, os, time
import urllib.request, urllib.parse, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'data', 'anchors_core.json')
CTX = ssl.create_default_context()

QUERIES = [
    '5G user plane function UPF traffic measurement usage reporting',
    'policy control charging 5G network slice quota',
    'network slice admission control quota subscription',
    'in-network traffic classification encrypted traffic operator',
    'mobile edge computing offloading incentive pricing operator',
    'application aware charging differentiated QoS 5G',
    'residential broadband uplink congestion ISP',
    'peer-assisted content delivery measurement ISP',
]

# lowercase fragments matched against the source display name
WANT = ['network science and engineering',
        'computer networks',
        'network and service management',
        'journal on selected areas in communications',
        'communications magazine',
        'transactions on mobile computing',
        'transactions on services computing',
        'transactions on communications']

SKIP = ['communications surveys', 'computer networks and communications']


def get(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'mailto:research@example.org'})
            return json.loads(urllib.request.urlopen(req, timeout=40, context=CTX).read())
        except Exception as e:
            if k == tries - 1:
                print('  FAIL', type(e).__name__, str(e)[:90])
                return None
            time.sleep(2 + 2 * k)


def inv(ab):
    if not ab:
        return ''
    if isinstance(ab, dict):
        pos = []
        for word, idxs in ab.items():
            for i in idxs:
                pos.append((i, word))
        pos.sort()
        return ' '.join(w for _, w in pos)
    return str(ab)[:1200]


def venue_ok(name):
    n = (name or '').lower()
    if 'abstract' in n or not n:
        return False
    if any(s in n for s in SKIP):
        return False
    return any(w in n for w in WANT)


def main():
    hits = {}
    for q in QUERIES:
        url = ('https://api.openalex.org/works?search=' + urllib.parse.quote(q)
               + '&filter=from_publication_date:2021-01-01&per-page=40'
               + '&select=id,doi,title,publication_year,primary_location,cited_by_count,abstract_inverted_index,type')
        d = get(url)
        if not d:
            continue
        n0 = len(hits)
        for w in d.get('results', []):
            src = ((w.get('primary_location') or {}).get('source') or {}).get('display_name') or ''
            if not venue_ok(src):
                continue
            doi = (w.get('doi') or '').replace('https://doi.org/', '')
            if not doi or doi in hits:
                continue
            hits[doi] = {'doi': doi, 'title': w.get('title'), 'year': w.get('publication_year'),
                         'venue': src, 'cites': w.get('cited_by_count'),
                         'query': q, 'abstract': inv(w.get('abstract_inverted_index'))[:1200]}
        print('  %-56s +%d -> %d' % (q[:56], len(hits) - n0, len(hits)))
        time.sleep(0.4)

    hits = dict(sorted(hits.items(), key=lambda kv: -(kv[1]['cites'] or 0)))
    print('\n%d target-venue anchors\n' % len(hits))
    for doi, h in list(hits.items())[:30]:
        print('%-33s %-4s c=%-4s %s' % (doi, h['year'], h['cites'], (h['title'] or '')[:90]))
        print('    %s' % h['venue'])
        if h['abstract']:
            print('    %s' % h['abstract'][:300].replace('\n', ' '))

    json.dump(hits, open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
