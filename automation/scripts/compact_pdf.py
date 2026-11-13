#!/usr/bin/env python3
"""Compact PDFs for email attachments: base-14 Helvetica, nothing embedded, about 10 KB each.

The Gmail tool takes attachments as inline base64, so every byte costs tokens. The tracker keeps
the master résumé (Portfolio PDF) for portal submissions; emails carry these compact renderings of
the same facts.

Usage:
  compact_pdf.py letter DRAFT.json OUT.pdf [--lane drafter|technician|engineer]
  compact_pdf.py resume OUT.pdf [--lane drafter|technician|engineer]

The lane picks the headline under the name (facts.json -> identity -> titles); a draft's own "lane"
field is used when --lane is not given.
"""
import argparse
import json
import re
import sys
from datetime import datetime

import pymupdf

from common import FACTS, read_json

A4 = pymupdf.paper_rect('a4')
L, R, T, B = 56, 56, 52, 52
W = A4.width - L - R
INK = (0.1, 0.1, 0.1)
GREY = (0.35, 0.35, 0.35)


_MONTH = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
_DATE = rf'(?:{_MONTH}\s+)?(?:19|20)\d\d'
DATE_RANGE = re.compile(rf'\b({_DATE})\s*[–—]\s*({_DATE}|present|now|current)\b', re.I)
STREET = re.compile(r'\b\d+[a-z]?(?:\s*[-/]\s*\d+)?\s+(?:[A-Za-z\']+\s+){1,3}(?:street|st|road|rd|avenue|ave|drive|dr|highway|hwy|parade|pde|court|ct|place|pl|lane|ln|'
                    r'boulevard|blvd|crescent|cres|way|terrace|tce|close|circuit|cct|esplanade|quay)\b|\b(?:po|gpo) box\s+\d+|\blocked bag\s+\d+', re.I)


def clean(s):
    """Base-14 fonts lack some glyphs; keep the text plain. An en dash becomes ' to ' only between two dates
    ('Feb 2024 – Feb 2026', '2014–2019', 'May 2024 – present'); anywhere else, such as inside a job title,
    it becomes a hyphen."""
    s = DATE_RANGE.sub(r'\1 to \2', s)
    return (s.replace('–', '-').replace(' — ', ', ').replace('—', ', ').replace('’', "'").replace('‘', "'")
             .replace('“', '"').replace('”', '"').replace('…', '...').replace('·', '·'))


def is_street_address(line):
    """'Level 20, 2 Market Street, Sydney NSW' and 'PO Box 12, Melton' are; 'Gunnedah NSW' and a sentence about the company are not."""
    line = str(line or '').strip()
    return bool(line) and len(line) <= 90 and bool(STREET.search(line))


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


def letter_pdf(letter, out, lane=None):
    ident = FACTS['identity']
    sh = Sheet(out)
    header(sh, ident, lane or letter.get('lane'))
    sh.text(letter.get('date') or datetime.now().strftime('%-d %B %Y'), gap=2)
    for k in ('recipient_name', 'recipient_role', 'company'):
        if letter.get(k):
            sh.text(letter[k], gap=1)
    if is_street_address(letter.get('company_line')):  # a line about the company is not part of an address
        sh.text(letter['company_line'], gap=1)
    sh.y += 8
    if letter.get('subject'):
        sh.text(letter['subject'], font='hebo', gap=8)
    sh.text(letter.get('greeting') or 'Hello,', gap=8)
    for p in letter.get('paragraphs') or []:
        sh.text(p, gap=8)
    closing = letter.get('closing') or 'Kind regards,'
    sh.need(sh.height(closing, gap=16) + sh.height(ident['name'], font='hebo', gap=1) + sh.height(ident['phone'], 9.5))  # sign-off stays in one piece
    sh.text(closing, gap=16)
    sh.text(ident['name'], font='hebo', gap=1)
    sh.text(f"{ident['phone']}  ·  {ident['email']}", size=9.5, color=GREY)
    sh.save()
    return out


def job_line(x):
    return f"{x['role']}  ·  {x['employer']}  ·  {x['dates']}"


def resume_pdf(out, lane='drafter'):
    f = FACTS; ident = f['identity']; e = f['eligibility']; c = f['capabilities']
    current = [x for x in f['experience'] if 'present' in x['dates'].lower()]  # the Australian job he holds now
    past = [x for x in f['experience'] if x not in current]
    capabilities = [
        f"Civil design: {c['civil_design']}",
        f"Construction support: {c['construction_support']}",
        f"Project coordination: {c['project_coordination']}",
        f"Technical documentation: {c['technical_documentation']}",
        f"Stakeholder communication: {c['stakeholder_communication']}",
        f"Software: {', '.join(c['software'])}",
    ]
    profile = "Civil Engineering graduate (BSCE, Philippines) with an Australian Advanced Diploma of Civil Construction Design and practical site experience in the Philippines supporting construction delivery, site coordination and quality inspections. Experienced in reviewing structural and architectural drawings, supervising site activities, maintaining progress and material records, and coordinating with engineers, subcontractors, suppliers and clients. Academic design experience includes earthworks, road geometry, pavement design and stormwater drainage. Brings a practical approach to problem-solving, accurate documentation and a strong willingness to develop under experienced civil engineers."
    standards = 'Standards: ' + ', '.join(c['standards_coursework']) + '.  Methods: ' + ', '.join(c['methods_coursework']) + '.'
    licences = [e['drivers_licence'], e['white_card'], e['wwcc'], e['work_rights']] + e['availability'][:2]
    sh = Sheet(out)
    header(sh, ident, lane)
    sh.text(f"{e.get('work_rights_short') or e['work_rights']}  ·  {e['drivers_licence']}  ·  {e['white_card']}", size=9.4, color=GREY, gap=8)
    sh.heading('Professional profile', room=sh.height(profile, gap=6))
    sh.text(profile, gap=6)
    sh.heading('Key capabilities', room=sh.height(capabilities[0], 9.8, indent=12, gap=2))
    sh.bullets(capabilities)
    for i, x in enumerate(current):  # listed first, under its own heading: it is not civil experience
        sh.entry(job_line(x), x['points'], heading='Current work in Australia' if i == 0 else None)
    for i, x in enumerate(past[:2]):
        sh.entry(job_line(x), x['points'], heading='Relevant experience' if i == 0 else None)
    for i, x in enumerate(f['education']):
        sh.entry(f"{x['qualification']}  ·  {x['provider']}  ·  {x['dates']}", x['points'], heading='Education' if i == 0 else None)
    sh.heading('Standards and methods (Advanced Diploma coursework)', room=sh.height(standards, gap=6))
    sh.text(standards, gap=6)
    for i, x in enumerate(past[2:]):
        sh.entry(job_line(x), x['points'], heading='Additional professional experience' if i == 0 else None)
    sh.heading('Licences and work eligibility', room=sh.height(licences[0], 9.8, indent=12, gap=2))
    sh.bullets(licences)
    strengths = ' · '.join(f['strengths'])
    sh.heading('Professional strengths', room=sh.height(strengths, gap=6))
    sh.text(strengths, gap=6)
    sh.text('References: ' + f['references'].lower(), gap=4)
    sh.save()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    lanes = [k for k in FACTS['identity'].get('titles') or {} if not k.startswith('_')]
    l = sub.add_parser('letter'); l.add_argument('draft_json'); l.add_argument('out_pdf'); l.add_argument('--lane', choices=lanes)
    r = sub.add_parser('resume'); r.add_argument('out_pdf'); r.add_argument('--lane', choices=lanes, default='drafter')
    a = ap.parse_args(argv)
    if a.cmd == 'letter':
        d = read_json(a.draft_json)
        print(letter_pdf(d.get('letter', d), a.out_pdf, lane=a.lane or d.get('lane')))
    else:
        print(resume_pdf(a.out_pdf, lane=a.lane))


if __name__ == '__main__':
    main()
