"""One gate for the whole build.

Runs the two passes, then every check that has to hold before the manuscript is
called done: no error, no overfull box, no undefined reference, every bib entry
cited exactly as often as the text cites it, and the submission package with the
counts the target journal enforces.

    py -3.13 src/check_all.py

Exit code 0 means all of it passed. Nothing is edited here.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAPER = os.path.join(ROOT, 'paper')
TEX = r'D:\texlive\2026\bin\windows\pdflatex.exe'

fails = []
rows = []


def ok(name, detail=''):
    rows.append(('ok  ', name, detail))


def bad(name, detail=''):
    rows.append(('FAIL', name, detail))
    fails.append(name)


def run_latex(tag):
    env = dict(os.environ)
    env['PATH'] = os.path.dirname(TEX) + os.pathsep + env.get('PATH', '')
    log = os.path.join(PAPER, 'gate_%s.txt' % tag)
    with open(log, 'w', encoding='utf-8', errors='replace') as fh:
        subprocess.run([TEX, '-interaction=nonstopmode', 'main.tex'],
                       cwd=PAPER, stdout=fh, stderr=subprocess.STDOUT)
    with open(log, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def main():
    # pass 1 writes aux and bbl inputs, pass 2 settles references
    subprocess.run([os.path.join(os.path.dirname(TEX), 'bibtex.exe'), 'main'],
                   cwd=PAPER, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    run_latex('a')
    log = run_latex('b')

    errs = [ln for ln in log.splitlines() if ln.startswith('!')]
    ok('no latex error', '%d' % len(errs)) if not errs else bad(
        'no latex error', errs[0][:110])

    over = re.findall(r'Overfull \\[hv]box \(([\d.]+)pt', log)
    ok('no overfull box', 'none') if not over else bad(
        'no overfull box', '%d boxes, largest %spt' % (len(over), max(over, key=float)))

    undef = re.findall(r'(Reference|Citation) .* undefined', log)
    ok('no undefined reference', 'none') if not undef else bad(
        'no undefined reference', '%d' % len(undef))

    m = re.search(r'Output written on main\.pdf \((\d+) pages, (\d+) bytes\)', log)
    if m:
        ok('pdf built', '%s pages, %s bytes' % (m.group(1), m.group(2)))
    else:
        bad('pdf built', 'no output line in the log')

    # every entry cited, every citation defined
    with open(os.path.join(PAPER, 'references.bib'), encoding='utf-8') as fh:
        bib = fh.read()
    ents = re.findall(r'@\w+\{([^,]+),', bib)
    with open(os.path.join(PAPER, 'main.aux'), encoding='utf-8', errors='replace') as fh:
        aux = fh.read()
    cited = re.findall(r'\\citation\{([^}]*)\}', aux)
    keys = set()
    for group in cited:
        keys.update(k.strip() for k in group.split(','))
    uncited = [e for e in ents if e not in keys]
    missing = [k for k in keys if k not in ents and k != '*']
    if not uncited and not missing:
        ok('bibliography closed', '%d entries, all cited' % len(ents))
    else:
        bad('bibliography closed',
            'uncited %s / missing %s' % (uncited[:4], missing[:4]))

    # the package gate does its own counting
    pkg = subprocess.run([sys.executable, os.path.join(HERE, 'verify_package.py')],
                         cwd=ROOT, capture_output=True, text=True)
    tail = [ln.strip() for ln in pkg.stdout.splitlines() if ln.strip()]
    passed = (pkg.returncode == 0 and tail
              and tail[-1] == 'all checks passed')
    ok('submission package', 'all checks passed') if passed else bad(
        'submission package', '; '.join(t for t in tail if t.startswith('FAIL'))[:110])

    width = max(len(r[1]) for r in rows)
    for state, name, detail in rows:
        print('%s  %-*s  %s' % (state, width, name, detail))
    print()
    print('GATE %s' % ('PASS' if not fails else 'FAIL (%d)' % len(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
