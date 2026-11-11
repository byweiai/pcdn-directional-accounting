"""Final gate for the submission package.

Everything here is measured, never asserted: page count, abstract length, budget
for the highlights, reference counts by venue, figure count, and whether the
manuscript still carries author identity.
"""
import os
import html as html_mod
import re
import sys

import pymupdf

import package_truth as truth

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(os.path.dirname(HERE), 'paper')
PDF = os.path.join(PAPER, 'main.pdf')
BIB = os.path.join(PAPER, 'references.bib')
HTML = os.path.join(PAPER, 'submission', 'submit_sheet.html')
HL = os.path.join(PAPER, 'submission', 'highlights.txt')

fails = []


def check(ok, msg):
    print(('  ok   ' if ok else '  FAIL ') + msg)
    if not ok:
        fails.append(msg)


def main():
    doc = pymupdf.open(PDF)
    print('manuscript')
    check(doc.page_count <= 18, 'pages %d (journal limit 18)' % doc.page_count)
    check(doc.page_count >= 16, 'pages %d (a full paper, not a note)' % doc.page_count)

    raw = re.sub(r'-\n', '', doc[0].get_text())
    flat = re.sub(r'\s+', ' ', raw)
    a = flat.find('Abstract')
    b = flat.find('Index Terms')
    abstract = flat[a + 9:b].strip()
    n = len(abstract.split())
    check(75 <= n <= 200,
          'abstract %d words (journal band 75-200)' % n)
    if not 185 <= n <= 196:
        print('  note   abstract %d words, outside the target band 185-196' % n)

    terms = flat[b:flat.find('I. INTRODUCTION')]
    k = terms.count(',') + 1
    check(2 <= k <= 5, 'index terms %d (journal limit 5)' % k)

    body = ''.join(doc[i].get_text() for i in range(doc.page_count))
    names = re.findall(r'\\newcommand\{\\([A-Za-z]+)\}',
                       open(os.path.join(PAPER, 'numbers.tex'),
                            encoding='utf-8').read())
    leaked = [nm for nm in names if nm in body]
    check(not leaked, 'no macro of numbers.tex prints as text (%d defined)%s'
          % (len(names), '' if not leaked else ' ' + str(leaked[:3])))
    low = body.lower()
    for probe in truth.IDENTITY:
        check(probe not in low, 'manuscript text free of %r' % probe)

    figs = {int(m) for m in re.findall(r'Fig\. (\d+)\.', body)}
    check(figs == set(range(1, 6)),
          'body carries figures %s, expected 1-5' % sorted(figs))

    print('references')
    bib = open(BIB, encoding='utf-8').read()
    ents = re.findall(r'@\w+\{([^,]+),', bib)
    jour = re.findall(r'journal\s*=\s*\{([^}]*)\}', bib)
    tnse = sum(1 for j in jour if 'netw. sci. eng' in j.lower())
    comnet = sum(1 for j in jour if 'comput. netw' in j.lower())
    check(len(ents) == 36, 'entries %d (the frozen 36)' % len(ents))
    check(tnse >= 5, 'IEEE TNSE entries %d' % tnse)
    check(comnet >= 5, 'Computer Networks entries %d' % comnet)
    check(not re.search(r'arxiv|preprint', bib, re.I), 'no preprint in the bibliography')
    # The count the sheet prints has to be the count the PDF prints, not the
    # count of entries in the source file.
    alltext = ''.join(doc[i].get_text() for i in range(doc.page_count))
    cut = alltext.rfind('REFERENCES')
    listed = [int(x) for x in re.findall(r'\[(\d{1,2})\]', alltext[cut:])]
    check(listed == list(range(1, len(ents) + 1)),
          'reference list prints 1-%d once each, in order (%d found)'
          % (len(ents), len(listed)))

    print('submission package')
    raw = [ln.rstrip('\n') for ln in open(HL, encoding='utf-8') if ln.strip()]
    check(not any(h.lstrip().startswith('#') for h in raw),
          'the uploaded highlights file carries no comment line')
    hl = raw
    check(len(hl) == 4, 'highlights %d (limit 5, target 4)' % len(hl))
    # The file is pasted into the portal, so any decoration in it counts against
    # the limit the portal enforces; nothing is stripped before measuring.
    check(all('[' not in h and ']' not in h for h in hl),
          'highlights carry no bracketed decoration')
    longest = max(len(h) for h in hl)
    check(longest <= 85, 'longest highlight %d chars (limit 85)' % longest)
    check(longest <= 80, 'longest highlight %d chars (target 80, margin of 5)' % longest)
    print('  note   highlight lengths %s' % [len(h) for h in hl])
    letter = os.path.join(PAPER, 'submission', 'cover_letter.pdf')
    ltex = os.path.join(PAPER, 'submission', 'cover_letter.tex')
    check(os.path.exists(letter), 'cover letter PDF present')
    if os.path.exists(letter):
        ldoc = pymupdf.open(letter)
        check(ldoc.page_count == 1, 'cover letter is %d page(s)' % ldoc.page_count)
        check(os.path.getmtime(letter) >= os.path.getmtime(ltex),
              'cover letter PDF is newer than its source')
        lt = re.sub(r'\s+', ' ', ''.join(ldoc[i].get_text()
                                          for i in range(ldoc.page_count)))
        for stale in ('1,251,831', '0.9985', 'survives every',
                      'on behalf of the authors', 'proved and then measured',
                      'single parameter once two loopholes', '7,403',
                      'All four corpora', 'beats any window rule'):
            check(stale not in lt, 'cover letter free of stale wording: %r' % stale)
        check('0.9999' in lt, 'cover letter states the cross-validated AUC')
        check('219' in lt, 'cover letter states the number of address pairs')
        import hashlib
        import json
        rec = os.path.join(PAPER, 'submission', 'letter_build.json')
        check(os.path.exists(rec), 'cover letter carries a build record')
        if os.path.exists(rec):
            heard = json.load(open(rec, encoding='utf-8'))
            sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
            check(sha(letter) == heard['pdf_sha256'],
                  'cover letter PDF is the one that was built')
            check(sha(ltex) == heard['tex_sha256'],
                  'cover letter source unchanged since that build')
        check('three input sources' in lt,
              'cover letter counts the public input sources as three')
        # The PDF is only authoritative if it was rebuilt from the source that
        # carries these sentences.
        src = re.sub(r'\s+', ' ',
                     open(os.path.join(PAPER, 'submission', 'cover_letter.tex'),
                          encoding='utf-8').read())

        def _dehyph(s):
            """Drop hyphens and any space a line break leaves after them.

            A hyphenated compound that falls at a line end reaches the text layer
            as 'three- window', so a literal substring probe fails on a correct
            PDF. Removing the hyphen and that space on both sides compares what
            the two documents say, not where they broke the line.
            """
            return re.sub(r'\s+', ' ', re.sub(r'-\s*', '', s))

        for probe in ('three input sources', 'three-window run rule',
                      'held out by group', 'Yue Lv'):
            check(_dehyph(probe) in _dehyph(src) and _dehyph(probe) in _dehyph(lt),
                  'cover letter PDF matches its source on %r' % probe)

    print('supplementary material')
    supp = os.path.join(PAPER, 'supplementary.pdf')
    check(os.path.exists(supp), 'supplementary PDF present')
    if os.path.exists(supp):
        sdoc = pymupdf.open(supp)
        check(sdoc.page_count == 6,
              'supplementary pages %d (the listed six)' % sdoc.page_count)
        stext = re.sub(r'\s+', ' ', ''.join(sdoc[i].get_text()
                                            for i in range(sdoc.page_count)))
        slow = stext.lower()
        for probe in truth.IDENTITY:
            check(probe not in slow, 'supplementary text free of %r' % probe)
        sleaked = [nm for nm in names if nm in stext]
        check(not sleaked, 'no macro name prints in the supplement%s'
              % ('' if not sleaked else ' ' + str(sleaked[:3])))
        for lab in ('S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7'):
            check(('Fig. %s' % lab) in stext, 'supplementary carries Fig. %s' % lab)
        check('TABLE S1' in stext,
              'supplementary carries Table S1')
        smeta = ' '.join(str(v) for v in sdoc.metadata.values())
        check('Lv' not in smeta and 'Yunnan' not in smeta,
              'supplementary PDF metadata anonymous')

    print('metadata')
    meta = ' '.join(str(v) for v in doc.metadata.values())
    for probe in ('Lv', 'Yunnan', 'Kunming', 'Rui', '0009-0006'):
        check(probe not in meta, 'manuscript metadata free of %r' % probe)

    check(os.path.exists(HTML), 'quick-fill page present')
    sheet = re.sub(r'<!--.*?-->', '', open(HTML, encoding='utf-8').read(),
                   flags=re.S)
    check(not re.search(r'__[A-Z]+__', sheet), 'no unfilled placeholder in the sheet')
    check('href="https://ieee.atyponrex.com/journal/tnse-cs"' in sheet,
          'submission portal href is the TNSE ReX form')
    stats = re.search(r'(\d+) pages, (\d+) figures, (\d+) references', sheet)
    check(stats is not None, 'page/figure/reference counts stated in the sheet')
    if stats:
        check(int(stats.group(1)) == doc.page_count,
              'sheet pages %s == pdf %d' % (stats.group(1), doc.page_count))
        check(int(stats.group(3)) == len(ents),
              'sheet references %s == bib %d' % (stats.group(3), len(ents)))
        check(int(stats.group(2)) == len(figs),
              'sheet figures %s == pdf %d' % (stats.group(2), len(figs)))
    mapped = [(int(a), b) for a, b in
              re.findall(r'Figure (\d+) <code>([^<]+)</code>', sheet)]
    check(mapped == truth.FIG_FILES,
          'sheet maps every figure number to its file, in order')
    for _, fname in truth.FIG_FILES:
        check(os.path.exists(os.path.join(os.path.dirname(PAPER), 'fig',
                                          fname)),
              'figure file %s exists' % fname)
    flat_sheet = re.sub(r'\s+', ' ', sheet)
    check('no author names, affiliations or funding' in flat_sheet,
          'sheet describes the anonymised body correctly')
    # The abstract and the index terms are copied out of the PDF, so the sheet
    # is only consistent if it carries the same words.
    LIG = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi',
       '\ufb04': 'ffl', '\ufb05': 'st', '\ufb06': 'st'}
    def _norm(s):
        s = html_mod.unescape(s)
        for k, v in LIG.items():
            s = s.replace(k, v)
        return ' '.join(s.split())
    check(_norm(abstract).replace('-', '') in _norm(sheet).replace('-', ''),
          'sheet abstract matches the PDF abstract (%d words, whole text)' % n)
    check('supplementary.pdf' in sheet, 'sheet lists the supplementary file')
    check('Table S1' in sheet, 'sheet states that Table S1 is in the supplement')
    for fig in ('fig1_mechanism.pdf', 'fig3_evasion.pdf', 'fig2_separation.pdf',
                'fig10_closures.pdf', 'fig7_regimes.pdf'):
        check(fig in sheet, 'sheet maps a figure name: %s' % fig)
    hlen = re.search(r'(\d+) items, up to (\d+) characters each', sheet)
    check(hlen is not None, 'sheet states the highlight character budget')
    if hlen:
        check(int(hlen.group(1)) == len(hl),
              'sheet item count %s == file %d' % (hlen.group(1), len(hl)))
        check(int(hlen.group(2)) == longest,
              'sheet highlight budget %s == file %d' % (hlen.group(2), longest))
    # The pasted text is the list on the page, not the file on disk.
    items = re.findall(r'<li><span>(.*?)</span><code>(\d+)</code></li>', sheet)
    check(len(items) == len(hl), 'sheet lists %d highlights' % len(items))
    check([html_mod.unescape(t) for t, _ in items] == hl,
          'sheet highlight text equals the file, in order')
    check([int(n) for _, n in items] == [len(h) for h in hl],
          'sheet highlight counts equal the pasted text')

    # Author block: one row, the four identity fields, nothing else.
    rows = re.findall(r'<tr>(.*?)</tr>', sheet, re.S)
    cells = [[html_mod.unescape(c) for c in re.findall(r'<td>(.*?)</td>', r, re.S)]
             for r in rows]
    cells = [c for c in cells if c]
    check(len(cells) == 1, 'author table has %d data row(s)' % len(cells))
    if len(cells) == 1:
        want = ['Yue Lv',
                'China Mobile Communications Group Yunnan Co., Ltd., '
                'Kunming 650000, China',
                'lvyue@yn.chinamobile.com', '0009-0006-7743-1644',
                'Corresponding and sole']
        check(cells[0] == want, 'author row equals the declared single author')

    # Fields the author copies: each is compared with the source of truth.
    ids = re.findall(r'<textarea[^>]*id="(f\d+)"', sheet)
    check(len(ids) == len(set(ids)),
          'copy-field ids are unique (%d fields)' % len(ids))
    boxes = dict(re.findall(r'<textarea id="f(\d+)"[^>]*>(.*?)</textarea>',
                            sheet, re.S))
    check(len(boxes) == 5, 'sheet carries %d copy fields' % len(boxes))
    if len(boxes) == 5:
        _b1 = _norm(html_mod.unescape(boxes['1'])).replace('-', '')
        check(_b1 == _norm(abstract).replace('-', ''),
              'copy field 1 is the PDF abstract')
        t2 = re.sub(r'^Index\s+Terms\s*[\u2014\-:.]*\s*', '', terms.strip())
        t2 = t2.strip().rstrip('.')
        b2 = _norm(html_mod.unescape(boxes['2'])).rstrip('.')
        check(b2 == _norm(t2), 'copy field 2 is the PDF index terms')
        check(_norm(html_mod.unescape(boxes['3'])) == _norm(truth.DECLARATIONS),
              'copy field 3 equals the declared declarations')
        check(_norm(html_mod.unescape(boxes['4']))
              == _norm(truth.DATA_AVAILABILITY),
              'copy field 4 equals the declared data availability')

    print()
    if fails:
        print('%d check(s) failed' % len(fails))
        sys.exit(1)
    print('all checks passed')


if __name__ == '__main__':
    main()
