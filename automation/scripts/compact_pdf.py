#!/usr/bin/env python3
"""Retired 14 Nov 2026: compact PDFs for email attachments.

Its resume was a different, unchecked resume (one fixed profile for every lane, with a claim about site supervision
that facts.json does not hold), and its letter command read a 'paragraphs' field that queue entries do not have, so it
printed a letter with no body. Both commands now stop with a message:

  compact_pdf.py resume ...   attach documents/resume/Marc_Masarate_Resume_<Variant>.pdf (built by resume.py)
  compact_pdf.py letter ...   build the letter with letter_pdf.py ENTRY_ID OUT.pdf
"""
import argparse
import sys

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
