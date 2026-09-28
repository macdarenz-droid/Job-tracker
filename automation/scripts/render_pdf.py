#!/usr/bin/env python3
"""Render a cover letter PDF from JSON with headless Chromium, and locate the master résumé PDF.

Usage:
  render_pdf.py letter LETTER.json OUT.pdf
  render_pdf.py resume            # prints the path of the master résumé PDF after checking it

LETTER.json fields: date (optional), recipient_name, recipient_role, company, company_line (optional),
subject, greeting, paragraphs (list of strings), closing (optional).
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from common import ROOT, REPO, FACTS, read_json, eprint, today_melbourne

CHROME_CANDIDATES = [
    os.environ.get('CHROME_BIN', ''),
    '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    shutil.which('chromium') or '', shutil.which('chromium-browser') or '', shutil.which('google-chrome') or '',
]


def chrome_path():
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    for p in Path('/opt/pw-browsers').glob('chromium-*/chrome-linux/chrome'):
        return str(p)
    raise RuntimeError('no Chromium found; set CHROME_BIN')


def esc(s):
    return html.escape(str(s or ''), quote=False)


def letter_html(letter):
    # RUNBOOK passes a complete draft JSON; the renderer also accepts a bare letter.
    letter = letter.get('letter', letter)
    if not letter.get('paragraphs'):
        raise ValueError('cover letter has no paragraphs')
    ident = FACTS['identity']
    t = (ROOT / 'templates' / 'cover-letter.html').read_text(encoding='utf-8')
    recipient = []
    if letter.get('recipient_name'):
        recipient.append(esc(letter['recipient_name']))
    if letter.get('recipient_role'):
        recipient.append(esc(letter['recipient_role']))
    if letter.get('company'):
        recipient.append(esc(letter['company']))
    if letter.get('company_line'):
        recipient.append(esc(letter['company_line']))
    recipient_block = ''.join(f'<p>{line}</p>' for line in recipient)
    paragraphs = ''.join(f'<p>{esc(p)}</p>' for p in letter.get('paragraphs') or [])
    date = letter.get('date') or datetime.fromisoformat(today_melbourne()).strftime('%-d %B %Y')
    fill = {
        'name': esc(ident['name']), 'title': esc(ident['title']), 'phone': esc(ident['phone']), 'email': esc(ident['email']),
        'portfolio_url': esc(ident['portfolio_url']), 'portfolio_display': esc(ident['portfolio_url'].replace('https://', '')),
        'location': esc(ident['location']), 'date': esc(date), 'recipient_block': recipient_block,
        'subject': esc(letter.get('subject') or ''), 'greeting': esc(letter.get('greeting') or 'Hello,'),
        'paragraphs': paragraphs, 'closing': esc(letter.get('closing') or 'Kind regards,'),
    }
    for k, v in fill.items():
        t = t.replace('{{' + k + '}}', v)
    return t


def render_letter(letter, out_pdf):
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'letter.html'
        src.write_text(letter_html(letter), encoding='utf-8')
        cmd = [chrome_path(), '--headless=new', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
               f'--print-to-pdf={out_pdf}', f'--user-data-dir={tmp}/profile', str(src)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not out_pdf.exists() or out_pdf.read_bytes()[:4] != b'%PDF':
            raise RuntimeError(f'PDF not produced: {r.stderr[-400:]}')
    return out_pdf


def resume_pdf():
    p = (REPO / FACTS['identity']['resume_pdf_repo_path']).resolve()
    if not p.exists():
        raise RuntimeError(f'master résumé PDF missing at {p}; clone macdarenz-droid/Portfolio next to Job-tracker')
    if p.read_bytes()[:4] != b'%PDF':
        raise RuntimeError('master résumé is not a PDF')
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    l = sub.add_parser('letter'); l.add_argument('letter_json'); l.add_argument('out_pdf')
    sub.add_parser('resume')
    a = ap.parse_args(argv)
    if a.cmd == 'letter':
        out = render_letter(read_json(a.letter_json), a.out_pdf)
        print(out)
    else:
        print(resume_pdf())


if __name__ == '__main__':
    main()
