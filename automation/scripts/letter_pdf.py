#!/usr/bin/env python3
"""The cover letter PDF for one queue entry: one A4 page with the same header as the resume of the entry's
resume_variant, then the entry's own cover_letter_text.

Usage:
  letter_pdf.py ENTRY_ID OUT.pdf [--dir QUEUE_DIR] [--date "14 November 2026"]

It reads automation/queue/open/<id>.json (or done/<YYYY-MM>/<id>.json). The header is resume.py's: his name, the
headline of the lane (facts.json -> identity -> titles), the contact line and the short work-rights line. Under it
come the date, the employer, and the letter as checks.compose_letter gives it (cover_letter_text, with the entry's
relocation_line at the end of the last paragraph when the text does not already carry it): the greeting line, the
three paragraphs and the sign-off ('Kind regards,' and his name are added when the text has none). Drawn in the
standard PDF fonts, nothing embedded, a few KB.

It refuses (exit 1, nothing written) a letter that checks.letter_issues does not pass, or one that does not fit on
one page. On success it prints the file, its size in bytes and its sha256. An email application attaches this file
and documents/resume/Marc_Masarate_Resume_<Variant>.pdf for the entry's resume_variant.
"""
import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import pymupdf

import answers
import checks
import resume
from common import FACTS, ROOT, read_json

QUEUE_DIR = ROOT / 'queue'
A4, LEFT, TOP, BOTTOM, WIDTH, LEADING = resume.A4, resume.LEFT, resume.TOP, resume.BOTTOM, resume.WIDTH, resume.LEADING
PARAGRAPH_GAP = 9   # points between the blocks of the letter


def find_entry(entry_id, qdir=QUEUE_DIR):
    """The queue entry with this id, open or done. Refused when the id has more than one file (a stale open/ copy of a
    finished entry, as queue.py check reports it), so a letter is never built from the wrong copy."""
    qdir = Path(qdir)
    paths = [p for p in [qdir / 'open' / f'{entry_id}.json'] + sorted((qdir / 'done').glob(f'*/{entry_id}.json')) if p.exists()]
    if len(paths) > 1:
        raise ValueError(f"{len(paths)} files ({', '.join(str(p) for p in paths)}): run queue.py check and remove the stale copy first")
    if paths:
        return read_json(paths[0])
    raise ValueError(f'no queue entry with id {entry_id} in {qdir}')


def plain(text):
    """Text the standard fonts can print: straight quotes, no ellipsis character."""
    return (str(text).replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('…', '...'))


def melbourne_today():
    now = datetime.now(answers.melbourne())   # the tz database, or the AEST/AEDT rule where this machine has none
    return f'{now.day} {now:%B %Y}'


def letter_lines(entry, facts=FACTS, date=None):
    """[(kind, text, space above)] of the letter: resume.py's header for the lane, then the date, the employer and the
    letter. Raises ValueError when the letter fails checks.letter_issues."""
    lane = entry.get('resume_variant') or entry.get('lane')
    if lane not in resume.LANES:
        raise ValueError(f'resume_variant: one of {", ".join(resume.LANES)} (the header is that resume\'s)')
    text = checks.compose_letter(entry.get('cover_letter_text'), entry.get('relocation_line'))
    problems = checks.letter_issues(text, allow=entry.get('tone_allow') or [])
    if problems:
        raise ValueError('letter refused: ' + '; '.join(problems))
    greeting, paragraphs, sign_off = checks.letter_blocks(text)
    head = resume.Lines(facts)
    resume.header(head, lane)
    lines = [(kind, plain(line), 0) for kind, line, _ in head]
    lines.append(('rule', '', 4))
    lines += [('p', plain(date or melbourne_today()), 10), ('p', plain(' '.join(str(entry.get('company') or '').split())), 2)]
    if greeting:
        lines.append(('p', plain(greeting), 14))
    lines += [('p', plain(' '.join(p.split())), PARAGRAPH_GAP if n or greeting else 14) for n, p in enumerate(paragraphs)]
    name = facts['identity']['name'].split()
    if not any(checks.CLOSING.match(line.lower()) for line in sign_off):
        sign_off = ['Kind regards,'] + sign_off
    names = {' '.join(name).lower(), f'{name[0]} {name[-1]}'.lower()}
    if not any(' '.join(line.lower().split()) in names for line in sign_off):
        sign_off.append(f'{name[0]} {name[-1]}')
    lines += [('p', plain(line), PARAGRAPH_GAP if n == 0 else 0) for n, line in enumerate(sign_off)]
    return lines


def draw(lines, facts=FACTS):
    """The PDF as bytes. Raises ValueError when the lines do not fit on one page."""
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    y = TOP
    for kind, text, space in lines:
        if kind == 'rule':
            y += space
            page.draw_line((LEFT, y), (LEFT + WIDTH, y), color=resume.GREY, width=0.6)
            y += space
            continue
        font, size, colour, gap, indent = resume.STYLE[kind]
        _, rows, _ = resume.shape(kind, text)
        y += gap + space
        for row in rows:
            page.insert_text((LEFT + indent, y + size), row, fontname=font, fontsize=size, color=colour)
            y += size * LEADING
        if y > A4.height - BOTTOM:
            doc.close()
            raise ValueError('the letter does not fit on one page: shorten it')
    page.clean_contents()
    ident = facts['identity']
    for needle, uri in ((ident['portfolio_url'], ident['portfolio_url']), (ident['email'], 'mailto:' + ident['email'])):
        for rect in page.search_for(needle):
            page.insert_link({'kind': pymupdf.LINK_URI, 'from': rect, 'uri': uri})
    doc.set_metadata({'title': ident['name'] + ' cover letter', 'author': ident['name']})
    data = doc.tobytes(garbage=4, deflate=True, no_new_id=True)
    doc.close()
    return data


def build(entry, out, facts=FACTS, date=None):
    """Write the letter PDF of one entry. Returns (path, size in bytes, sha256). Nothing is written on a refusal."""
    data = draw(letter_lines(entry, facts, date), facts)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out, len(data), hashlib.sha256(data).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('id', help='the queue entry')
    ap.add_argument('out', help='where to write the PDF')
    ap.add_argument('--dir', default=str(QUEUE_DIR), help='queue folder (default automation/queue)')
    ap.add_argument('--date', help='the date printed on the letter (default: today in Melbourne)')
    a = ap.parse_args(argv)
    try:
        path, size, digest = build(find_entry(a.id, a.dir), a.out, date=a.date)
    except ValueError as err:
        print(f'{a.id}: {err}', file=sys.stderr)
        return 1
    print(f'{path}  {size} bytes  sha256 {digest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
