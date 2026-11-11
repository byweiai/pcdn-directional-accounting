"""Build the quick-fill page for the submission system.

The abstract and the index terms are read out of the compiled PDF rather than
typed again, so the sheet cannot drift from the manuscript. Hyphenation
introduced by the typesetter is undone before the text is embedded.
"""
import html
import os
import re

import pymupdf

import package_truth as truth

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(os.path.dirname(HERE), 'paper')   # ...\tnse\paper
PDF = os.path.join(PAPER, 'main.pdf')
OUT = os.path.join(PAPER, 'submission', 'submit_sheet.html')

TITLE = ('Upload May Not Exceed Download: Directional Accounting for '
         'Peer-Assisted Delivery in Operator Networks')

AUTHORS = [
    ('Yue Lv', 'China Mobile Communications Group '
               'Yunnan Co., Ltd., Kunming 650000, China',
     'lvyue@yn.chinamobile.com', '0009-0006-7743-1644', 'Corresponding and sole'),
]


def clean(s):
    """Join only the hyphens the typesetter inserted at a line break."""
    s = re.sub(r'-\n', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def main():
    doc = pymupdf.open(PDF)
    first = doc[0].get_text()
    flat = clean(first)

    a = flat.find('Abstract')
    b = flat.find('Index Terms')
    abstract = clean(flat[a + len('Abstract'):b]).lstrip('\u2014').strip()
    for _k, _v in {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi',
                   '\ufb04': 'ffl', '\ufb05': 'st', '\ufb06': 'st'}.items():
        abstract = abstract.replace(_k, _v)
    _src = open(os.path.join(PAPER, 'main.tex'), encoding='utf-8').read()
    _ab = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', _src, re.S)
    for _w in sorted(set(re.findall(r'[A-Za-z]+(?:-[A-Za-z]+)+', _ab.group(1))),
                     key=len, reverse=True):
        abstract = abstract.replace(_w.replace('-', ''), _w)
    k = flat.find('Index Terms')
    terms = clean(flat[k + len('Index Terms'):flat.find('I. INTRODUCTION')])
    terms = terms.lstrip('—').strip()
    for _k, _v in {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi',
                   '\ufb04': 'ffl', '\ufb05': 'st', '\ufb06': 'st'}.items():
        terms = terms.replace(_k, _v)

    # Counted off the compiled artefact every time, so the sheet cannot claim a
    # page or reference count the PDF does not have.
    pages = doc.page_count
    body = ''.join(doc[i].get_text() for i in range(pages))
    nfig = len({m for m in re.findall(r'Fig\. (\d+)\.', body)})
    with open(os.path.join(PAPER, 'references.bib'), encoding='utf-8') as fh:
        nref = len(re.findall(r'(?m)^@', fh.read()))

    with open(os.path.join(PAPER, 'submission', 'highlights.txt'),
              encoding='utf-8') as fh:
        hl = [ln.rstrip('\n') for ln in fh if ln.strip()]
    # The file is uploaded as it stands, so a comment line would travel to
    # the editor; the notes live beside it in highlights_notes.md instead.
    assert not any(h.lstrip().startswith('#') for h in hl), hl
    for h in hl:
        assert '[' not in h and len(h) <= 85, (len(h), h)

    rows = []
    for name, aff, mail, orcid, role in AUTHORS:
        rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (name, aff, mail or 'enter in portal',
                       orcid or 'enter in portal', role or 'Co-author'))

    fields = [
        ('Title', TITLE),
        ('Abstract (%d words)' % len(abstract.split()), abstract),
        ('Index terms', terms),
        ('Declarations', truth.DECLARATIONS),
        ('Data availability', truth.DATA_AVAILABILITY),
    ]

    blocks = []
    for label, value in fields:
        esc = html.escape(value)
        blocks.append(
            '<section><div class="hd"><h2>%s</h2>'
            '<button data-copy="#f%d">copy</button></div>'
            '<textarea id="f%d" rows="%d">%s</textarea></section>'
            % (label, len(blocks), len(blocks), max(2, min(14, 1 + len(value) // 95)),
               esc))

    hl_items = ''.join('<li><span>%s</span><code>%d</code></li>'
                       % (html.escape(h), len(h)) for h in hl)

    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Submission quick-fill — TNSE</title>
<style>
:root{--ink:#1d2b33;--mid:#5a6b74;--line:#d7dee2;--wash:#f4f7f8;--accent:#2f6f8f}
*{box-sizing:border-box}
body{margin:0;padding:28px 34px 60px;background:#fff;color:var(--ink);
 font:14px/1.55 -apple-system,"Segoe UI","Helvetica Neue",Arial,sans-serif}
h1{font-size:19px;margin:0 0 4px;letter-spacing:.01em}
.sub{color:var(--mid);font-size:12.5px;margin-bottom:22px}
.banner{background:var(--wash);border:1px solid var(--line);border-left:3px solid var(--accent);
 padding:12px 14px;margin-bottom:24px;font-size:13px}
.banner b{display:block;margin-bottom:3px}
section{margin-bottom:20px;border-bottom:1px solid var(--line);padding-bottom:16px}
.hd{display:flex;align-items:baseline;gap:12px;margin-bottom:7px}
h2{font-size:12.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--mid);
 margin:0;font-weight:600}
button{font:inherit;font-size:11.5px;padding:3px 10px;border:1px solid var(--line);
 background:#fff;color:var(--accent);border-radius:3px;cursor:pointer}
button:hover{background:var(--wash)}
button.done{color:#1f7a4d;border-color:#bfe0cf;background:#f2faf5}
textarea{width:100%;border:1px solid var(--line);border-radius:3px;padding:10px 12px;
 font:13px/1.5 ui-monospace,"SF Mono",Consolas,monospace;color:var(--ink);
 background:#fcfdfd;resize:vertical}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--mid);font-weight:600}
ul.hl{list-style:none;margin:0;padding:0}
ul.hl li{display:flex;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px dotted var(--line)}
ul.hl li:last-child{border-bottom:0}
ul.hl code{color:var(--mid);font-size:12px;min-width:26px;text-align:right}
.note{color:var(--mid);font-size:12.5px;margin-top:8px}
.files{font-size:13px}
.files li{margin:3px 0}
</style></head><body>

<h1>Submission quick-fill — IEEE Transactions on Network Science and Engineering</h1>
<div class="sub">Upload May Not Exceed Download &middot; Yue Lv &middot;
__STATS__</div>

<div class="banner"><b>Submission portal</b>
<a href="https://ieee.atyponrex.com/journal/tnse-cs" target="_blank"
rel="noopener">https://ieee.atyponrex.com/journal/tnse-cs</a> &mdash; the
submission site linked from the
<a href="https://www.comsoc.org/publications/journals/ieee-tnse/policies-guidelines"
target="_blank" rel="noopener">TNSE policies and guidelines</a> page (both
checked 2026-11-10); that page is also where the 18-page, 75&ndash;200-word and
five-keyword limits this sheet is built to are stated. The URL the portal shows
after login is authoritative. Paste each block below into the matching form
field.</div>

<section><div class="hd"><h2>Authors and affiliations</h2></div>
<table><thead><tr><th>Name</th><th>Affiliation</th><th>Email</th><th>ORCID</th><th>Role</th></tr></thead>
<tbody>__AUTHORS__</tbody></table></section>

__BLOCKS__

<section><div class="hd"><h2>Highlights (4 items, each &le; 85 characters)</h2></div>
<ul class="hl">__HL__</ul></section>

<section><div class="hd"><h2>Upload order</h2></div>
<ol class="files">
<li><code>main.pdf</code> — manuscript, anonymous, __PAGES__ pages</li>
<li><code>cover_letter.pdf</code> — one page, signed by the corresponding author</li>
<li><code>highlights.txt</code> — __NHL__ items, __HLLEN__ characters each</li>
<li><code>supplementary.pdf</code> — six pages: Figures S1–S7, Table S1 and the
proofs, outside the manuscript page limit</li>
<li><code>figures</code> — the __NFIG__ figures are embedded in <code>main.pdf</code>
and are listed here only in case the portal separates them:
__FIGLIST__</li>
</ol>
<div class="note">The manuscript carries no author names, affiliations or
funding; all cross-references resolve and all __NREF__ references are cited.</div>
</section>

<script>
document.querySelectorAll('button[data-copy]').forEach(function(b){
  b.addEventListener('click',function(){
    var el=document.querySelector(b.dataset.copy);
    navigator.clipboard.writeText(el.value).then(function(){
      var t=b.textContent; b.textContent='copied'; b.classList.add('done');
      setTimeout(function(){b.textContent=t;b.classList.remove('done');},1200);
    });
  });
});
</script>
</body></html>
"""
    figlist = ', '.join('Figure %d <code>%s</code>' % (n, f)
                        for n, f in truth.FIG_FILES)
    page = (page.replace('__AUTHORS__', ''.join(rows))
                .replace('__BLOCKS__', '\n'.join(blocks))
                .replace('__HL__', hl_items)
                .replace('__STATS__', '%d pages, %d figures, %d references'
                         % (pages, nfig, nref))
                .replace('__PAGES__', str(pages))
                .replace('__NFIG__', str(nfig))
                .replace('__FIGLIST__', figlist)
                .replace('__NREF__', str(nref))
                .replace('__NHL__', str(len(hl)))
                .replace('__HLLEN__',
                         ('up to %d' % max(len(h) for h in hl)) if hl else '0'))

    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(page)
    print('wrote', OUT)
    print('abstract words', len(abstract.split()))
    print('terms:', terms)


if __name__ == '__main__':
    main()
