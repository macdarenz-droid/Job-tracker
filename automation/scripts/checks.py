#!/usr/bin/env python3
"""Pre-send checks: human tone, truth against facts.json, and record completeness.

Usage:
  checks.py tone FILE            # banned phrases, dashes, length
  checks.py facts FILE           # claims that do not trace to facts.json
  checks.py record RECORD.json   # everything a send needs
Exit code 1 when any issue is found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import CONFIG, FACTS, read_json

TONE = CONFIG['tone']
KNOWN_TOOLS = ['SIDRA', 'OpenRoads', '12d', 'MicroStation', 'HEC-RAS', 'DRAINS', 'TUFLOW', 'Navisworks', 'Bluebeam',
               'Primavera', 'P6', 'MS Project', 'Trimble', 'Leica', 'ArcGIS', 'QGIS', 'InfraWorks', 'Python', 'Procore',
               'Aconex', 'SketchUp', 'Tekla', 'SpaceGass', 'Space Gass', 'ETABS', 'SAP2000', 'RAPT', 'Inventor', 'SolidWorks',
               'MATLAB', 'Power BI', 'Excel modelling', 'Excel modeling', 'GIS', 'BIM 360', 'Civil3D', 'Dynamo', 'Grasshopper']
ALLOWED_YEARS = {'2014', '2015', '2016', '2017', '2018', '2019', '2020', '2022', '2024', '2026', '2027'}
FORBIDDEN_CLAIMS = [
    (r'\bpermanent resid', 'claims permanent residency'),
    (r'\bcitizen', 'claims citizenship'),
    (r'\bPR\b', 'claims PR'),
    (r'australian (work|site|construction|industry) experience', 'claims Australian work experience'),
    (r'\b(chartered|CPEng|RPEQ|NER\b|registered engineer|licensed engineer)', 'claims a professional registration'),
    (r'\b\d+\+?\s*years?\s+(of\s+)?(commercial|industry|professional|drafting|design|civil)\b', 'claims years of professional experience'),
    (r'\b(sponsor|sponsorship|migration|residency goal)', 'mentions sponsorship or migration'),
    (r'\bmaster(\'s)?\s+(degree|of)', 'claims a master degree'),
    (r'\bhonours\b', 'claims honours'),
    (r'\binternship\b', 'claims an internship'),
    (r'\bwork placement\b', 'claims a placement'),
    (r'\breferee', 'names or offers referees inline'),
]


def words(text):
    return len(re.findall(r"[A-Za-z0-9'’]+", text))


def tone_issues(text, kind='email'):
    issues = []
    low = text.lower()
    for phrase in TONE['banned_phrases']:
        if phrase in low:
            issues.append(f'banned phrase: "{phrase}"')
    for ch in TONE['banned_characters']:
        if ch in text:
            issues.append(f'banned character: {ch!r} (use a comma, full stop or "to")')
    if text.count('!') > TONE['max_exclamations']:
        issues.append('too many exclamation marks')
    limit = TONE['max_email_words'] if kind == 'email' else TONE['max_cover_letter_words']
    n = words(text)
    if n > limit:
        issues.append(f'too long: {n} words (limit {limit})')
    if re.search(r'\b(AI|ChatGPT|Claude|language model)\b', text):
        issues.append('mentions AI')
    if kind == 'email' and re.search(r'(?<!https://)macdarenz-droid\.github\.io/Portfolio', text):
        issues.append('portfolio link must be written in full as https://macdarenz-droid.github.io/Portfolio')
    if len(re.findall(r'\bI\b', text)) > 14 and kind == 'email':
        issues.append('starts too many sentences with I')
    return issues


def fact_issues(text):
    issues = []
    software_ok = [s.lower() for s in FACTS['capabilities']['software']]
    for tool in KNOWN_TOOLS:
        if re.search(r'(?<![A-Za-z])' + re.escape(tool) + r'(?![A-Za-z])', text) and tool.lower() not in software_ok:
            issues.append(f'names software not in facts: {tool}')
    # A year is a claim about Marc only when it sits in a first-person sentence; employer history is fine.
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if not re.search(r"\b(I|I'm|I've|I'd|my|me|mine)\b", sentence):
            continue
        for y in set(re.findall(r'\b(19\d\d|20\d\d)\b', sentence)):
            if y not in ALLOWED_YEARS:
                issues.append(f'year not in facts: {y}')
    for pat, why in FORBIDDEN_CLAIMS:
        if re.search(pat, text, re.I):
            issues.append(why)
    for amount in re.findall(r'(?:PHP|AUD|\$)\s?[\d,.]+\s*(?:million|m\b|k\b)?', text, re.I):
        a = amount.lower().replace(' ', '')
        if not any(k in a for k in ('php1million', 'php1.2million', 'aud22,000', 'aud27,000', '22,000', '27,000', '1million', '1.2million')):
            issues.append(f'amount not in facts: {amount}')
    return issues


def record_issues(rec, require_uploaded=True):
    issues = []
    for k in ('company', 'role', 'status', 'job_url', 'fit', 'gaps', 'match_score'):
        if not rec.get(k):
            issues.append(f'missing {k}')
    email = str(rec.get('recipient_email') or '')
    emailing = rec.get('status') == CONFIG['statuses']['prepared'] or bool(email)
    if emailing:  # an email will go to this address, now or after the portal application
        for k in ('subject', 'email_body', 'recipient_email', 'recipient_role', 'contact_evidence_url'):
            if not rec.get(k):
                issues.append(f'missing {k}')
        if rec.get('contact_confidence') == 'published_direct' and not rec.get('recipient_name'):
            issues.append('missing recipient_name for a direct contact')
        if rec.get('contact_confidence') not in ('published_direct', 'published_inbox'):
            issues.append('recipient is neither a published direct contact nor a published application inbox')
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]{2,}', email, re.I):
        issues.append('recipient_email is not a valid address')
    if re.search(r'@(gmail|hotmail|outlook|yahoo|icloud|live)\.', email, re.I):
        issues.append('recipient_email is a personal mailbox')
    kinds = {d.get('kind') for d in rec.get('attachments') or []}
    if 'resume' not in kinds:
        issues.append('no résumé attached')
    if 'cover' not in kinds:
        issues.append('no cover letter attached')
    for d in rec.get('attachments') or []:
        if require_uploaded and (d.get('stored_in') != 'cloudflare_r2' or not re.fullmatch(r'[0-9a-f]{64}', str(d.get('sha256') or ''), re.I) or not d.get('id') or not str(d.get('path') or '').startswith('/api/documents/')):
            issues.append(f"attachment not in R2 with a hash: {d.get('filename')}")
    if require_uploaded and rec.get('preparation_only'):
        issues.append('dry-build record is not publishable or sendable')
    if rec.get('contributor_name') != CONFIG['contributor_name']:
        issues.append('contributor_name is not Claude')
    if rec.get('application_type') == 'SPECULATIVE_ENQUIRY' and 'speculative' not in str(rec.get('email_body', '')).lower() and 'no advertised' not in str(rec.get('notes', '')).lower():
        issues.append('speculative enquiry must say so')
    body = str(rec.get('email_body') or '')
    issues += ['email ' + i for i in tone_issues(body, 'email')]
    issues += ['email ' + i for i in fact_issues(body)]
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('tone'); t.add_argument('file'); t.add_argument('--kind', default='email', choices=['email', 'letter'])
    f = sub.add_parser('facts'); f.add_argument('file')
    r = sub.add_parser('record'); r.add_argument('file')
    a = ap.parse_args(argv)
    if a.cmd == 'tone':
        issues = tone_issues(Path(a.file).read_text(encoding='utf-8'), a.kind)
    elif a.cmd == 'facts':
        issues = fact_issues(Path(a.file).read_text(encoding='utf-8'))
    else:
        issues = record_issues(read_json(a.file))
    for i in issues:
        print('- ' + i)
    print('OK' if not issues else f'{len(issues)} issue(s)')
    sys.exit(1 if issues else 0)


if __name__ == '__main__':
    main()
