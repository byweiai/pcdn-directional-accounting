import io
import json
import sys
import os
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_bib import get  # noqa: E402

QS = {
    'isr2012': 'Network neutrality and congestion sensitive content providers implications for investment and welfare',
    'csur2013': 'Game theory meets network security and privacy',
    'dpi2012': 'Policing the Network Using DPI for Copyright Enforcement',
    'netnomics2017': 'Internet service provision and content services paid peering and competition between ISPs',
    'nrl2025': 'Inspection Game With Imperfect Detection Technology',
    'unsw2015': 'UNSW-NB15 a comprehensive data set for network intrusion detection systems',
    'cic2018': 'Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization',
    'ieice2011': 'Understanding of network operator-friendly P2P traffic control techniques',
}

out = []
for k, q in QS.items():
    d = get('https://api.crossref.org/works?rows=3&query.bibliographic=' +
            urllib.parse.quote(q))
    out.append('== ' + k)
    if not d:
        out.append('   FAILED')
        continue
    for it in d['message']['items']:
        out.append('   %s | %s | %s | %s | %s' % (
            it.get('DOI'),
            ((it.get('issued', {}).get('date-parts') or [[None]])[0][0]),
            ((it.get('container-title') or [''])[0])[:55],
            it.get('type'),
            ((it.get('title') or [''])[0])[:64]))
io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'data', 'bib_probe.txt'), 'w', encoding='utf-8').write(
    '\n'.join(out) + '\n')
print('\n'.join(out))
