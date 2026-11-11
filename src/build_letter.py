"""Build the cover letter and record what it was built from.

The gate cannot tell a rebuilt letter from a stale one by timestamps alone, so
the build writes the hash of the source and of the PDF it produced. Editing the
source without rebuilding leaves the record behind the file, and the gate fails.
"""
import hashlib
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.join(os.path.dirname(HERE), 'paper', 'submission')
TEX = os.path.join(SUB, 'cover_letter.tex')
PDF = os.path.join(SUB, 'cover_letter.pdf')
REC = os.path.join(SUB, 'letter_build.json')


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    subprocess.run(['latexmk', '-xelatex', '-interaction=nonstopmode',
                    'cover_letter.tex'], cwd=SUB, check=True)
    record = {'tex_sha256': sha(TEX), 'pdf_sha256': sha(PDF),
              'pages': None}
    import pymupdf
    record['pages'] = pymupdf.open(PDF).page_count
    with open(REC, 'w', encoding='utf-8') as fh:
        json.dump(record, fh, indent=2)
    print('letter built: %d page(s), source %s'
          % (record['pages'], record['tex_sha256'][:12]))


if __name__ == '__main__':
    main()
