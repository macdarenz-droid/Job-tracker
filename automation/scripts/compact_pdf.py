#!/usr/bin/env python3
"""Compact PDFs for email attachments: base-14 Helvetica, nothing embedded, about 10 KB each.

The Gmail tool takes attachments as inline base64, so every byte costs tokens. The tracker keeps
the master résumé (Portfolio PDF) for portal submissions; emails carry these compact renderings of
the same facts.

Usage:
  compact_pdf.py letter DRAFT.json OUT.pdf
  compact_pdf.py resume OUT.pdf
"""
import argparse
import json
import sys
from datetime import datetime

import pymupdf

from common import FACTS, read_json

A4 = pymupdf.paper_rect('a4')
L, R, T, B = 56, 56, 52, 52
W = A4.width - L - R
INK = (0.1, 0.1, 0.1)
GREY = (0.35, 0.35, 0.35)


def clean(s):
    """Base-14 fonts lack some glyphs; keep the text plain."""
    return (s.replace(' – ', ' to ').replace('–', '-').replace('—', ', ').replace('’', "'").replace('‘', "'")
             .replace('“', '"').replace('”', '"').replace('…', '...').replace('·', '·'))


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

    def bullets(self, items, size=9.8, indent=12):
        for it in items:
            self.need(14)
            self.page.insert_text((L + 2, self.y + size), '•', fontsize=size, fontname='helv', color=INK)
            self.text(it, size=size, indent=indent, gap=2)

    def heading(self, s, size=11.2):
        self.y += 2
        self.text(s, size=size, font='hebo', gap=3)

    def save(self):
        self.doc.save(self.path, garbage=4, deflate=True)
        self.doc.close()


def header(sh, ident):
    sh.text(ident['name'], size=17, font='hebo', gap=1)
    sh.text(ident['title'], size=10, color=GREY, gap=2)
    sh.text(f"{ident['phone']}  ·  {ident['email']}  ·  {ident['portfolio_url'].replace('https://', '')}  ·  {ident['location']}", size=9.2, color=GREY, gap=4)
    sh.rule(10)


def letter_pdf(letter, out):
    ident = FACTS['identity']
    sh = Sheet(out)
    header(sh, ident)
    sh.text(letter.get('date') or datetime.now().strftime('%-d %B %Y'), gap=2)
    for k in ('recipient_name', 'recipient_role', 'company', 'company_line'):
        if letter.get(k):
            sh.text(letter[k], gap=1)
    sh.y += 8
    if letter.get('subject'):
        sh.text(letter['subject'], font='hebo', gap=8)
    sh.text(letter.get('greeting') or 'Hello,', gap=8)
    for p in letter.get('paragraphs') or []:
        sh.text(p, gap=8)
    sh.text(letter.get('closing') or 'Kind regards,', gap=16)
    sh.text(ident['name'], font='hebo', gap=1)
    sh.text(f"{ident['phone']}  ·  {ident['email']}", size=9.5, color=GREY)
    sh.save()
    return out


def resume_pdf(out):
    f = FACTS; ident = f['identity']; e = f['eligibility']; c = f['capabilities']
    sh = Sheet(out)
    header(sh, ident)
    sh.text(f"{e['work_rights']}  ·  {e['drivers_licence']}  ·  {e['white_card']}", size=9.4, color=GREY, gap=8)
    sh.heading('Professional profile')
    sh.text("Civil Engineering graduate (BSCE, Philippines) with an Australian Advanced Diploma of Civil Construction Design and practical site experience in the Philippines supporting construction delivery, site coordination and quality inspections. Experienced in reviewing structural and architectural drawings, supervising site activities, maintaining progress and material records, and coordinating with engineers, subcontractors, suppliers and clients. Academic design experience includes earthworks, road geometry, pavement design and stormwater drainage. Brings a practical approach to problem-solving, accurate documentation and a strong willingness to develop under experienced civil engineers.", gap=6)
    sh.heading('Key capabilities')
    sh.bullets([
        f"Civil design: {c['civil_design']}",
        f"Construction support: {c['construction_support']}",
        f"Project coordination: {c['project_coordination']}",
        f"Technical documentation: {c['technical_documentation']}",
        f"Stakeholder communication: {c['stakeholder_communication']}",
        f"Software: {', '.join(c['software'])}",
    ])
    sh.heading('Relevant experience')
    for x in f['experience'][:2]:
        sh.text(f"{x['role']}  ·  {x['employer']}  ·  {x['dates']}", font='hebo', size=10.2, gap=3)
        sh.bullets(x['points'])
        sh.y += 2
    sh.heading('Education')
    for x in f['education']:
        sh.text(f"{x['qualification']}  ·  {x['provider']}  ·  {x['dates']}", font='hebo', size=10.2, gap=3)
        sh.bullets(x['points'])
        sh.y += 2
    sh.heading('Standards and methods (Advanced Diploma coursework)')
    sh.text('Standards: ' + ', '.join(c['standards_coursework']) + '.  Methods: ' + ', '.join(c['methods_coursework']) + '.', gap=6)
    sh.heading('Additional professional experience')
    x = f['experience'][2]
    sh.text(f"{x['role']}  ·  {x['employer']}  ·  {x['dates']}", font='hebo', size=10.2, gap=3)
    sh.bullets(x['points'])
    sh.heading('Licences and work eligibility')
    sh.bullets([e['drivers_licence'], e['white_card'], e['wwcc'], e['work_rights']] + e['availability'][:2])
    sh.heading('Professional strengths')
    sh.text(' · '.join(f['strengths']), gap=6)
    sh.text('References: ' + f['references'].lower(), gap=4)
    sh.save()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    l = sub.add_parser('letter'); l.add_argument('draft_json'); l.add_argument('out_pdf')
    r = sub.add_parser('resume'); r.add_argument('out_pdf')
    a = ap.parse_args(argv)
    if a.cmd == 'letter':
        d = read_json(a.draft_json)
        print(letter_pdf(d.get('letter', d), a.out_pdf))
    else:
        print(resume_pdf(a.out_pdf))


if __name__ == '__main__':
    main()
