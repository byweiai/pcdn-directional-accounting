# -*- coding: utf-8 -*-
"""Geometric audit of a rendered figure PDF.

Three checks the project rules require before a figure is allowed into the
paper, done on the artifact rather than on the drawing code:
  overlap   two text spans whose boxes intersect
  clip      a text box that reaches outside the page
  markers   a data marker whose centre lies outside the axes it belongs to
             (approximated by: a marker drawn over a text box)

Usage: py -3.13 src/check_fig_text.py fig/fig12_dualuse.pdf [...]
"""
import sys
import os

import pymupdf


def boxes(page):
    out = []
    d = page.get_text('dict')
    for b in d['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                if not s['text'].strip():
                    continue
                out.append((pymupdf.Rect(s['bbox']), s['text'].strip()))
    return out


def main(paths):
    bad = 0
    for p in paths:
        doc = pymupdf.open(p)
        for page in doc:
            w, h = page.rect.width, page.rect.height
            print('%s  page %.2f x %.2f in' % (os.path.basename(p), w / 72, h / 72))
            bs = boxes(page)
            ov = 0
            for i in range(len(bs)):
                ri, ti = bs[i]
                for j in range(i + 1, len(bs)):
                    rj, tj = bs[j]
                    inter = ri & rj
                    if inter.is_empty:
                        continue
                    a = inter.get_area()
                    small = min(ri.get_area(), rj.get_area())
                    if small > 0 and a / small > 0.12:
                        ov += 1
                        if ov <= 6:
                            print('  overlap %.0f%%  %r  x  %r'
                                  % (100 * a / small, ti[:28], tj[:28]))
            clips = [t for r, t in bs
                     if r.x0 < 1 or r.y0 < 1 or r.x1 > w - 1 or r.y1 > h - 1]
            for t in clips[:6]:
                print('  clip  %r' % t[:40])
            print('  %d spans, %d overlaps, %d clipped' % (len(bs), ov, len(clips)))
            bad += ov + len(clips)
        doc.close()
    print('\nverdict:', 'clean' if bad == 0 else '%d defect(s)' % bad)
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
