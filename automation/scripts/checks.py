#!/usr/bin/env python3
"""Checks before anything is sent or submitted: tone and length (config -> tone), truth against
facts.json, standing answers for form questions, and record completeness.

Usage:
  checks.py tone FILE [--kind email|letter|answer] [--visa-asked]   # banned phrases, dashes, volunteered limits, length
  checks.py facts FILE             # claims that do not trace to facts.json
  checks.py draft DRAFT.json       # every written part of one draft: email, cover letter, free-text form answers
  checks.py questions FILE.json    # form questions of a draft or candidate: standing answer in facts.json, or ask the owner
  checks.py record RECORD.json     # everything a tracker record needs
Exit code 1 when any issue is found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import CONFIG, FACTS, canonical_status, read_json

TONE = CONFIG['tone']
STATUSES = CONFIG['statuses']
ANSWERS = FACTS.get('answers', {})
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
# The approved short work-rights line says "no sponsorship needed"; that is not a sponsorship request.
APPROVED = re.compile(r'no sponsorship (is )?(needed|required)', re.I)
VISA_DATE = re.compile(r'\bdec(ember|\.)?\s+2027\b', re.I)
VISA_FLAG = re.compile(r'2027|expires', re.I)  # the flag patterns that are about the visa end date
SALARY_QUESTION = re.compile(r'salary|remuneration|\brate\b', re.I)
VISA_QUESTION = re.compile(r'visa|work(ing)? rights?|rights? to work|residency|permanent resident|citizen', re.I)
# The current Australian job is casual console-operator work at a service station (facts -> experience -> use).
CONSOLE = re.compile(r'console operator|service station|rockbank|rampage', re.I)
CIVIL_EXPERIENCE = re.compile(r'\b(civil|construction|site|engineering|drafting|design|technical|industry|relevant)\b[^.!?]{0,40}\bexperience\b'
                              r'|\bexperience\b[^.!?]{0,30}\b(civil|construction|site|engineering|drafting|design)\b', re.I)
ELSEWHERE = re.compile(r'philippines|justbuilt|grand travaux|2019|2020', re.I)
LINK = re.compile(r'https?://\S+|\S+@\S+\.\S+')


def words(text):
    """Word count. A link or an email address counts as one word."""
    return len(re.findall(r"[A-Za-z0-9'’]+", LINK.sub('link', text)))


def tone_issues(text, kind='email', visa_asked=False):
    """config -> tone on one piece of text. kind: 'email' (130 words), 'letter' (200), 'answer' (a free-text
    form answer, no word limit). visa_asked: the advert or the form question asks about visa or residency,
    so the end date may be given."""
    issues = []
    low = text.replace('’', "'").replace('‘', "'").lower()
    for phrase in TONE['banned_phrases']:
        if phrase in low:
            issues.append(f'banned phrase: "{phrase}"')
    for ch in TONE['banned_characters']:
        if ch in text:
            issues.append(f'banned character: {ch!r} (use a comma, full stop or "to")')
    for pattern in TONE['no_volunteered_limits']['flag_patterns']:
        if pattern.lower() in low and not (visa_asked and VISA_FLAG.search(pattern)):
            issues.append(f'volunteers a limit: "{pattern}" (say what he has done; never what he lacks)')
    if VISA_DATE.search(text) and not visa_asked:
        issues.append('gives the visa end date; only where the advert or form asks about visa or residency (advert_asks_about_visa)')
    if text.count('!') > TONE['max_exclamations']:
        issues.append('too many exclamation marks')
    limit = {'email': TONE['max_email_words'], 'letter': TONE['max_cover_letter_words']}.get(kind)
    n = words(text)
    if limit and n > limit:
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
    denial = re.compile(r"\b(haven't|have not|hasn't|has not|never|not yet)\s+(used|worked|touched|learned|learnt)\b|\bwould be new\b|\bnew to me\b", re.I)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for tool in KNOWN_TOOLS:
        pat = r'(?<![A-Za-z])' + re.escape(tool) + r'(?![A-Za-z])'
        if tool.lower() in software_ok or not re.search(pat, text):
            continue
        # Naming a tool to say Marc has not used it is not a false claim (tone_issues fails it as a volunteered limit).
        claims = [s for s in sentences if re.search(pat, s) and not denial.search(s)]
        if claims:
            issues.append(f'names software not in facts: {tool}')
    # A year is a claim about Marc only when it sits in a first-person sentence; employer history is fine.
    for sentence in sentences:
        if not re.search(r"\b(I|I'm|I've|I'd|my|me|mine)\b", sentence):
            continue
        for y in set(re.findall(r'\b(19\d\d|20\d\d)\b', sentence)):
            if y not in ALLOWED_YEARS:
                issues.append(f'year not in facts: {y}')
    for pat, why in FORBIDDEN_CLAIMS:
        if re.search(pat, APPROVED.sub('', text), re.I):
            issues.append(why)
    for amount in re.findall(r'(?:PHP|AUD|\$)\s?[\d,.]+\s*(?:million|m\b|k\b)?', text, re.I):
        a = amount.lower().replace(' ', '')
        if not any(k in a for k in ('php1million', 'php1.2million', 'aud22,000', 'aud27,000', '22,000', '27,000', '1million', '1.2million')):
            issues.append(f'amount not in facts: {amount}')
    if any(CONSOLE.search(s) and CIVIL_EXPERIENCE.search(s) and not ELSEWHERE.search(s) for s in sentences):
        issues.append('presents the casual console operator job as civil experience (facts: it is current Australian work, nothing more)')
    return issues


def draft_parts(draft):
    """(email body, letter paragraphs, [(question, answer)]) of a draft. Reads the run-folder draft
    (email_body, letter.paragraphs, screening_answers) and the queue-entry names (email.body,
    cover_letter_text + relocation_line, questions)."""
    email = draft.get('email') if isinstance(draft.get('email'), dict) else {}
    body = str(draft.get('email_body') or email.get('body') or '')
    paragraphs = [str(p) for p in (draft.get('letter') or {}).get('paragraphs') or []]
    if not paragraphs and draft.get('cover_letter_text'):
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', str(draft['cover_letter_text'])) if p.strip()]
        if draft.get('relocation_line') and str(draft['relocation_line']) not in paragraphs[-1]:
            paragraphs[-1] += ' ' + str(draft['relocation_line'])
    answers = [(str(a.get('question') or ''), a.get('answer')) for a in (draft.get('screening_answers') or draft.get('questions') or []) if isinstance(a, dict)]
    return body, paragraphs, answers


def draft_issues(draft):
    """Everything written in one draft against config -> tone and facts.json. The visa end date passes
    only when the draft carries advert_asks_about_visa true (or, in a form answer, the question asks)."""
    visa = draft.get('advert_asks_about_visa') is True
    body, paragraphs, answers = draft_parts(draft)
    issues = ['email ' + i for i in tone_issues(body, 'email', visa) + fact_issues(body)] if body else []
    if paragraphs:
        text = '\n'.join(paragraphs)
        issues += ['letter ' + i for i in tone_issues(text, 'letter', visa) + fact_issues(text)]
        if len(paragraphs) > 3:
            issues.append(f'letter has {len(paragraphs)} paragraphs (three short paragraphs: config -> tone -> letter_shape)')
    letter = draft.get('letter') or {}
    for name, line in (('email subject', draft.get('subject')), ('letter subject', letter.get('subject')), ('letter greeting', letter.get('greeting'))):
        issues += [f'{name} {i}' for i in tone_issues(str(line or ''), 'answer', visa)]
    for question, answer in answers:
        if not isinstance(answer, str) or not answer.strip():
            continue
        asked = visa or bool(VISA_QUESTION.search(question))
        truth = [i for i in fact_issues(answer) if not (i.startswith('amount not in facts') and SALARY_QUESTION.search(question))]  # a salary answer is a figure
        issues += [f'answer to "{question[:60]}" {i}' for i in tone_issues(answer, 'answer', asked) + truth]
        if re.search(r'\[[^\]]*\]', answer):
            issues.append(f'answer to "{question[:60]}" leaves a blank in square brackets for someone to fill in')
    return issues


# Form questions: which line of facts.json -> answers covers a question. First match wins. A None key means
# the detail is private or unknown and nobody but the owner answers it.
UNSETTLED = re.compile(r'not confirmed|not on record|skip and report', re.I)
OFFICE_PRODUCT = re.compile(r'\b(excel|word|powerpoint|outlook|ms project|microsoft project)\b')
LOOKUPS = ('qualification_questions', 'years_of_experience', 'software', 'experience_yes_no')
ANSWER_RULES = [
    (None, r'visa (grant )?number|passport|date of birth|\bdob\b|legal name|tax file|\btfn\b|bank|medical condition|injur|disabilit|gender|aboriginal|torres strait|rate your|referred by'),
    ('currently_studying', r'currently (studying|enrolled)'),
    (None, r'engineers australia|washington accord|recognised|accredited'),
    ('right_to_work', r'rights? to work|work(ing)? rights?|(eligib\w+|entitled|authori[sz]ed|allowed) to (live and )?work|visa|sponsorship|citizen|permanent resident'),
    ('notice_period', r'notice|availab\w+ to start|start date|when can you start'),
    ('expected_salary', r'salary|remuneration|hourly rate|rate expectation'),
    ('drivers_licence', r'driver|licen[cs]ed to drive|class c\b'),
    ('own_car_or_regular_access', r'access to a (car|vehicle)|own (a |reliable )?(car|vehicle|transport)'),
    ('white_card', r'white card|construction induction'),
    ('police_check', r'police|criminal history'),
    ('drug_and_alcohol_screening', r'drug'),
    ('pre_employment_medical', r'pre.?employment medical|medical (check|assessment|examination)'),
    ('willing_to_relocate', r'relocat'),
    ('willing_to_travel_or_fifo', r'fifo|dido|travel'),
    ('identity.location', r'\breside\b|current location|which suburb|where are you (currently )?(based|located)|living in australia'),
    ('identity.short_name', r'^preferred name'),
    ('english_self_rating', r'english'),
    ('referees', r'referee'),
    ('free_text_cover_letter', r'cover letter'),
    ('years_of_experience', r"how many years|years of|years'? experience"),
    ('software', r'software|autocad|civil 3d|revit|12d|microstation|microsoft|excel|bluebeam|\bcad\b'),
    ('qualification_questions', r'qualification|education|degree|diploma|certificate|licen[cs]e|ticket|induction|registration|registered|accreditation|member'),
    ('experience_yes_no', r'^(do|have|are|did) you\b.*\b(experience|worked|familiar)'),
]


def _entry(table, question):
    """The line of a lookup table whose key names something in the question, else its catch-all ('any other ...', 'anything else', 'other')."""
    rest = None
    for key, value in table.items():
        names = [n.strip().lower() for n in key.split(',')]
        if key in ('rule', '_about'):
            continue
        if any(n and n in question for n in names if not re.match(r'any other|anything else|other$', n)):
            return value
        if any(re.match(r'any other|anything else|other$', n) for n in names):
            rest = value
    return rest


def _unsettled(answer, question):
    """True when a standing answer leaves this question to the owner: it says 'not confirmed', 'not on record'
    or 'skip and report' outright, or in an 'If the form asks X: ...' sentence whose X is in the question."""
    if not isinstance(answer, str):
        return False  # a rule with choose / never_choose is an answer
    for sentence in re.split(r'(?<=\.)\s+', answer):
        if not UNSETTLED.search(sentence):
            continue
        cond = re.match(r'if (.+?):', sentence, re.I)
        if not cond or any(re.search(r'\b' + w, question) for w in re.findall(r'[a-z]{4,}', cond.group(1).lower()) if w not in ('form', 'asks', 'must', 'that', 'whether')):
            return True
    return False


def standing_answer(question):
    """(key, problem) for one form question. key is the line of facts.json -> answers that covers it (None when
    nothing does); problem is None when that line settles the answer, else why the owner must be asked. This
    only says whether a standing answer exists: the submitter still reads that line and the form's options."""
    q = ' '.join(str(question or '').lower().replace('’', "'").split())
    for key, pattern in ANSWER_RULES:
        if not re.search(pattern, q):
            continue
        if key is None:
            return None, 'a private or unknown detail: only the owner can answer it'
        answer = FACTS['identity'].get(key[9:]) if key.startswith('identity.') else ANSWERS.get(key)
        if key == 'software' and OFFICE_PRODUCT.search(q) and isinstance(answer, dict):
            answer, q = answer.get('Microsoft Office'), q + ' individual products'  # one Office product named
        elif key in LOOKUPS and isinstance(answer, dict):
            answer = _entry(answer, q)
        if answer is None:
            return key, f'facts.json -> answers has no "{key}"'
        if _unsettled(answer, q):
            return key, f'facts.json -> answers -> {key} is not confirmed for this question'
        return key, None
    return None, 'no standing answer in facts.json -> answers'


def unanswered_questions(questions):
    """[{question, why}] for the form questions with no settled standing answer, in order, each once."""
    out, seen = [], set()
    for question in questions or []:
        text = ' '.join(str(question or '').split())
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        _, problem = standing_answer(text)
        if problem:
            out.append({'question': text, 'why': problem})
    return out


def record_issues(rec, require_uploaded=True):
    issues = []
    for k in ('company', 'role', 'status', 'job_url', 'fit', 'gaps', 'match_score'):
        if not rec.get(k):
            issues.append(f'missing {k}')
    status = canonical_status(rec.get('status'))
    ask = rec.get('ask_owner') or {}
    channel = canonical_status(ask.get('then')) if status == STATUSES['ask_owner'] else status  # what it is, or becomes once the owner answers
    email = str(rec.get('recipient_email') or '')
    if channel == STATUSES['prepared']:  # an email application
        for k in ('subject', 'email_body', 'recipient_email', 'recipient_role', 'contact_evidence_url'):
            if not rec.get(k):
                issues.append(f'missing {k}')
        if rec.get('contact_confidence') == 'published_direct' and not rec.get('recipient_name'):
            issues.append('missing recipient_name for a direct contact')
        if rec.get('contact_confidence') not in ('published_direct', 'published_inbox'):
            issues.append('recipient is neither a published direct contact nor a published application inbox')
    elif rec.get('email_body'):
        issues.append('one application per advert through one channel: a SEEK, portal or form record carries no email to send (double touch retired 13 Nov 2026)')
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]{2,}', email, re.I):
        issues.append('recipient_email is not a valid address')
    if re.search(r'@(gmail|hotmail|outlook|yahoo|icloud|live)\.', email, re.I):
        issues.append('recipient_email is a personal mailbox')
    if status == STATUSES['ask_owner'] and not ask.get('questions'):
        issues.append('ASK_OWNER record needs the question for the owner (ask_owner.questions)')
    if status != STATUSES['ask_owner'] and ask.get('questions'):
        issues.append(f'{status} record still has an open question for the owner')
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
        issues.append(f"contributor_name is not {CONFIG['contributor_name']}")
    if rec.get('application_type') == 'SPECULATIVE_ENQUIRY' and 'speculative' not in str(rec.get('email_body', '')).lower() and 'no advertised' not in str(rec.get('notes', '')).lower():
        issues.append('speculative enquiry must say so')
    visa = rec.get('advert_asks_about_visa') is True
    return issues + draft_issues({'email_body': rec.get('email_body'), 'subject': rec.get('subject'), 'screening_answers': rec.get('screening_answers'), 'advert_asks_about_visa': visa})


def form_questions(data):
    """The form questions in a draft, queue entry or candidate file, as text."""
    listed = data.get('screening_questions') or (data.get('advert') or {}).get('screening_questions') or []
    asked = [a.get('question') for a in (data.get('screening_answers') or data.get('questions') or []) if isinstance(a, dict)]
    return [q for q in list(listed) + asked if isinstance(q, str) and q.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('tone'); t.add_argument('file'); t.add_argument('--kind', default='email', choices=['email', 'letter', 'answer']); t.add_argument('--visa-asked', action='store_true')
    f = sub.add_parser('facts'); f.add_argument('file')
    d = sub.add_parser('draft'); d.add_argument('file')
    q = sub.add_parser('questions'); q.add_argument('file')
    r = sub.add_parser('record'); r.add_argument('file')
    a = ap.parse_args(argv)
    if a.cmd == 'tone':
        issues = tone_issues(Path(a.file).read_text(encoding='utf-8'), a.kind, a.visa_asked)
    elif a.cmd == 'facts':
        issues = fact_issues(Path(a.file).read_text(encoding='utf-8'))
    elif a.cmd == 'draft':
        issues = draft_issues(read_json(a.file))
    elif a.cmd == 'questions':
        issues = [f"ask the owner: {u['question']} ({u['why']})" for u in unanswered_questions(form_questions(read_json(a.file)))]
    else:
        issues = record_issues(read_json(a.file))
    for i in issues:
        print('- ' + i)
    print('OK' if not issues else f'{len(issues)} issue(s)')
    sys.exit(1 if issues else 0)


if __name__ == '__main__':
    main()
