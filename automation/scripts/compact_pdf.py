#!/usr/bin/env python3
"""Retired 14 Nov 2026: compact PDFs for email attachments.

Its resume was a different, unchecked resume (one fixed profile for every lane, with a claim about site supervision
that facts.json does not hold), and its letter command read a 'paragraphs' field that queue entries do not have, so it
printed a letter with no body. Both commands now stop with a message:

  compact_pdf.py resume ...   attach documents/resume/Marc_Masarate_Resume_<Variant>.pdf (built by resume.py)
  compact_pdf.py letter ...   build the letter with letter_pdf.py ENTRY_ID OUT.pdf

The page helpers below (Sheet, clean, headline, header) stay for any later one-page document.
"""
import argparse
import re
import sys

import pymupdf

from common import FACTS

A4 = pymupdf.paper_rect('a4')
L, R, T, B = 56, 56, 52, 52
W = A4.width - L - R
INK = (0.1, 0.1, 0.1)
GREY = (0.35, 0.35, 0.35)


_MONTH = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
_DATE = rf'(?:{_MONTH}\s+)?(?:19|20)\d\d'
DATE_RANGE = re.compile(rf'\b({_DATE})\s*[–—]\s*({_DATE}|present|now|current)\b', re.I)


def clean(s):
    """Base-14 fonts lack some glyphs; keep the text plain. An en dash becomes ' to ' only between two dates
    ('Feb 2024 – Feb 2026', '2014–2019', 'May 2024 – present'); anywhere else, such as inside a job title,
    it becomes a hyphen."""
    s = DATE_RANGE.sub(r'\1 to \2', s)
    return (s.replace('–', '-').replace(' — ', ', ').replace('—', ', ').replace('’', "'").replace('‘', "'")
             .replace('“', '"').replace('”', '"').replace('…', '...').replace('·', '·'))


def headline(lane=None):
    """The headline under the name for a role lane (facts.json -> identity -> titles), else the general title."""
    ident = FACTS['identity']
    return (ident.get('titles') or {}).get(lane) or ident['title']


class Sheet:
    def __init__(self, path):
        self.doc = pymupdf.open()
        self.path = path
        self.page = None
        self.y = T
        self.new_page()

    def new_page(self):
        self.page = self.doc.new_page(width=A4.width, height=A4.height)
        self.y = T

    def need(self, h):
        if self.y + h > A4.height - B:
            self.new_page()

    def text(self, s, size=10.2, font='helv', color=INK, gap=6, indent=0, width=None, line=1.3):
        """Wrapped paragraph. Returns height used."""
        width = width or W - indent
        s = clean(str(s))
        est = self._measure(s, size, font, width, line)
        self.need(est)
        rect = pymupdf.Rect(L + indent, self.y, L + indent + width, self.y + est + 2)
        rc = self.page.insert_textbox(rect, s, fontsize=size, fontname=font, color=color, lineheight=line)
        if rc < 0:  # did not fit (should not happen after measure); push to a new page
            self.new_page()
            rect = pymupdf.Rect(L + indent, self.y, L + indent + width, A4.height - B)
            self.page.insert_textbox(rect, s, fontsize=size, fontname=font, color=color, lineheight=line)
        self.y += est + gap
        return est

    def _measure(self, s, size, font, width, line):
        scratch = pymupdf.open(); p = scratch.new_page(width=A4.width, height=5000)
        rect = pymupdf.Rect(0, 0, width, 5000)
        rc = p.insert_textbox(rect, s, fontsize=size, fontname=font, lineheight=line)
        used = 5000 - rc
        scratch.close()
        return used + 1

    def rule(self, gap=8):
        self.need(gap)
        self.page.draw_line((L, self.y), (L + W, self.y), color=INK, width=0.8)
        self.y += gap

    def height(self, s, size=10.2, font='helv', indent=0, gap=0):
        """Height a text() call with these settings will use, gap included."""
        return self._measure(clean(str(s)), size, font, W - indent, 1.3) + gap

    def bullets(self, items, size=9.8, indent=12):
        for it in items:
            self.need(self.height(it, size, indent=indent))  # the dot and its text move to the next page together
            self.page.insert_text((L + 2, self.y + size), '•', fontsize=size, fontname='helv', color=INK)
            self.text(it, size=size, indent=indent, gap=2)

    def heading(self, s, size=11.2, room=0):
        """Section heading. room is the height of the first item under it: a heading is never left alone at
        the bottom of a page, it moves to the next page with that item."""
        self.need(2 + self.height(s, size, 'hebo', gap=3) + room)
        self.y += 2
        self.text(s, size=size, font='hebo', gap=3)

    def entry(self, line, points, heading=None):
        """A bold line (role, employer, dates) and its bullets. The line, its first bullet and the heading
        above it (when given) stay on one page."""
        room = self.height(line, 10.2, 'hebo', gap=3) + (self.height(points[0], 9.8, indent=12, gap=2) if points else 0)
        if heading:
            self.heading(heading, room=room)
        else:
            self.need(room)
        self.text(line, font='hebo', size=10.2, gap=3)
        self.bullets(points)
        self.y += 2

    def link(self, needle, uri):
        """Make every occurrence of `needle` on every page a clickable link to `uri`."""
        for page in self.doc:
            for rect in page.search_for(needle):
                page.insert_link({'kind': pymupdf.LINK_URI, 'from': rect, 'uri': uri})

    def save(self):
        ident = FACTS['identity']
        url = ident['portfolio_url']
        self.link(url, url)
        self.link(url.replace('https://', ''), url)
        self.link(ident['email'], 'mailto:' + ident['email'])
        self.doc.save(self.path, garbage=4, deflate=True)
        self.doc.close()


def header(sh, ident, lane=None):
    sh.text(ident['name'], size=17, font='hebo', gap=1)
    sh.text(headline(lane), size=10, color=GREY, gap=2)
    sh.text(f"{ident['phone']}  ·  {ident['email']}  ·  {ident['portfolio_url'].replace('https://', '')}  ·  {ident['location']}", size=9.2, color=GREY, gap=4)
    sh.rule(10)


RETIRED = {
    'resume': "compact_pdf.py resume is retired: attach documents/resume/Marc_Masarate_Resume_<Variant>.pdf for the entry's "
              'resume_variant (Drafter, Technician or Engineer; built by resume.py build).',
    'letter': 'compact_pdf.py letter is retired: build the cover letter with python3 letter_pdf.py ENTRY_ID OUT.pdf '
              "(the entry's cover_letter_text under the same header as its resume).",
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=sorted(RETIRED))
    ap.add_argument('rest', nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    sys.exit(RETIRED[a.cmd])


if __name__ == '__main__':
    main()
