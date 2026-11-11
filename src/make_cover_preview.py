"""Render the cover-letter preview from the final PDF, not from an older build."""
import os

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.join(os.path.dirname(HERE), 'paper', 'submission')
src = os.path.join(SUB, 'cover_letter.pdf')
dst = os.path.join(SUB, 'cover_preview.png')
d = pymupdf.open(src)
d[0].get_pixmap(dpi=140).save(dst)
print('wrote', dst, d.page_count, 'page(s)', os.path.getsize(dst), 'bytes')
