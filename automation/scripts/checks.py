#!/usr/bin/env python3
"""Checks before anything is sent or submitted: tone and length (config -> tone), truth against
facts.json, standing answers for form questions, and record completeness.

Usage:
  checks.py tone FILE [--kind email|letter|answer] [--visa-asked]   # banned phrases, dashes, volunteered limits, length
  checks.py facts FILE             # claims that do not trace to facts.json
  checks.py draft DRAFT.json       # every written part of one draft: email, cover letter, form answers
  checks.py questions FILE.json    # form questions of a draft or candidate: standing answer in facts.json, or ask the owner
  checks.py record RECORD.json     # everything a tracker record needs
Exit code 1 when any issue is found.

Form answers are read in every shape the drafts use: a list of {question, answer}, a list of {q, a},
or one {question: answer} object. A shape that cannot be read is an issue, never a silent pass.
A form question is answered only from facts.json -> answers. The gate (standing_answer) fails closed:
a question no rule covers, or whose line says 'not confirmed', 'not on record' or 'skip and report',
goes to the owner.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import CONFIG, FACTS, canonical_status, read_json

TONE = CONFIG['tone']
STATUSES = CONFIG['statuses']
READY_STATUSES = (STATUSES['ready_seek'], STATUSES['ready_portal'], STATUSES['ready_form'])
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
# The visa end date, however it is written: 'December 2027', 'Dec 2027', '12/2027', 'visa valid through 2027', 'until the end of 2027'.
VISA_DATE = re.compile(r'\bdec(ember|\.)?\s+2027\b|\b12\s*/\s*(20)?27\b|\b(until|till|through|thru)\s+(the\s+)?(end\s+of\s+)?(\w+\s+)?2027\b'
                       r'|\b(visa|485|work(ing)? rights?|expir\w*)\b[^.!?\n]{0,40}\b2027\b|\b2027\b[^.!?\n]{0,20}\bexpir', re.I)
VISA_FLAG = re.compile(r'2027|expires', re.I)  # the flag patterns that are about the visa end date
SALARY_QUESTION = re.compile(r'salary|remuneration|\brate\b', re.I)
VISA_QUESTION = re.compile(r'visa|work(ing)? rights?|rights? to work|residency|permanent resident|citizen', re.I)
# The current Australian job is casual console-operator work at a service station (facts -> experience -> use).
# A sentence about that job must not carry civil work, unless the civil part is plainly somewhere else (the
# Philippines, 2019, 2020), is the name of his qualification, or sits in a clause about study or job hunting.
CONSOLE = re.compile(r"console operator|service station|rockbank|rampage|\bbp\b|\bsince\s+(may\s+)?2024\b|\bmy (current|present) (role|job|position|work|employer|employment)\b"
                     r"|\b(currently|presently) (work|working|employed)\b|\bmy australian (work|job|role)\b", re.I)
CIVIL_WORK = re.compile(r'\b(civil|construction|sites?|engineering|drafting|design\w*|inspect\w*|co-?ordinat\w*|infrastructure|earthworks|drainage)\b', re.I)
ELSEWHERE = re.compile(r'philippines|justbuilt|grand travaux|2019|2020', re.I)
QUALIFICATION_NAMES = re.compile(r'(advanced diploma of )?civil construction design|bachelor of science in civil engineering|civil engineering (degree|graduate)', re.I)
ASIDE = re.compile(r'\b(while|whilst|alongside|during|look\w* for|seek\w*|apply\w* for|want\w* to|hop\w* to|aim\w* to|return\w* to|mov\w* (back )?(in)?to)\b[^,;]*', re.I)
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
        # Whole words only: 'have not' is not in 'I have noted' or 'I have nothing but', 'although i' is not in 'although it'.
        found = re.search(r'(?<![a-z])' + re.escape(pattern.lower()) + r'(?![a-z])', low)
        if found and not (visa_asked and VISA_FLAG.search(pattern)):
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


def console_job_as_civil(sentence):
    """True when a sentence about the current casual job (console operator at a service station) carries civil work."""
    if not CONSOLE.search(sentence) or ELSEWHERE.search(sentence):
        return False
    rest = ASIDE.sub(' ', QUALIFICATION_NAMES.sub(' ', sentence))
    return bool(CIVIL_WORK.search(rest))


def unknown_tools(text):
    """The tools named in a text that are not in facts.json -> capabilities -> software."""
    software_ok = [s.lower() for s in FACTS['capabilities']['software']]
    return [t for t in KNOWN_TOOLS if t.lower() not in software_ok and re.search(r'(?<![A-Za-z])' + re.escape(t) + r'(?![A-Za-z])', text)]


def fact_issues(text):
    issues = []
    denial = re.compile(r"\b(haven't|have not|hasn't|has not|never|not yet)\s+(used|worked|touched|learned|learnt)\b|\bwould be new\b|\bnew to me\b", re.I)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for tool in unknown_tools(text):
        pat = r'(?<![A-Za-z])' + re.escape(tool) + r'(?![A-Za-z])'
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
    if any(console_job_as_civil(s) for s in sentences):
        issues.append('presents the casual console operator job as civil experience (facts: it is current Australian work, nothing more)')
    return issues


# ------------------------------------------------------------------------------------------- form answers
def answer_items(data):
    """(items, problem). items: [{'question', 'answer', 'basis'}] for the form answers in a draft, a record or a
    queue entry (screening_answers, or questions). Reads the three shapes the drafts use: a list of
    {question, answer}, a list of {q, a}, and one {question: answer} object. On a record an open question
    carries its proposal as draft_answer; it is read as the answer. problem says why a shape cannot be read
    (items then holds what could be), so nothing is skipped in silence."""
    raw = data.get('screening_answers')
    if raw in (None, '', [], {}):
        raw = data.get('questions') or []
    if isinstance(raw, dict):
        return [{'question': ' '.join(str(q).split()), 'answer': a, 'basis': ''} for q, a in raw.items()], None
    if not isinstance(raw, list):
        return [], f'form answers cannot be read ({type(raw).__name__}): write a list of {{"question", "answer"}}'
    items, problem = [], None
    for entry in raw:
        if isinstance(entry, str) and entry.strip():  # a question with no answer yet
            items.append({'question': ' '.join(entry.split()), 'answer': None, 'basis': ''})
            continue
        question = (entry.get('question') or entry.get('q')) if isinstance(entry, dict) else None
        if not isinstance(question, str) or not question.strip():
            problem = f'a form answer cannot be read ({json.dumps(entry, ensure_ascii=False)[:80]}): write {{"question", "answer"}}'
            continue
        answer = next((entry[k] for k in ('answer', 'a', 'draft_answer') if k in entry), None)
        items.append({'question': ' '.join(question.split()), 'answer': answer, 'basis': str(entry.get('basis') or '')})
    return items, problem


def form_questions(data):
    """The form questions in a draft, record, queue entry or candidate file, as text: the advert's own list
    (screening_questions) and the questions that carry an answer."""
    listed = data.get('screening_questions') or (data.get('advert') or {}).get('screening_questions') or []
    listed = [(q.get('question') or q.get('text') or q.get('q')) if isinstance(q, dict) else q for q in (listed if isinstance(listed, list) else [listed])]
    asked = [item['question'] for item in answer_items(data)[0]]
    return [q for q in listed + asked if isinstance(q, str) and q.strip()]


def draft_parts(draft):
    """(email body, letter paragraphs, [(question, answer)]) of a draft. Reads the run-folder draft
    (email_body, letter.paragraphs, screening_answers) and the queue-entry names (email.body,
    cover_letter_text + relocation_line, questions). A paragraph is a block between blank lines, wherever
    the blank lines are; cover_letter_text with no blank line is split on its line breaks."""
    email = draft.get('email') if isinstance(draft.get('email'), dict) else {}
    body = str(draft.get('email_body') or email.get('body') or '')
    paragraphs = [b.strip() for p in (draft.get('letter') or {}).get('paragraphs') or [] for b in re.split(r'\n\s*\n', str(p)) if b.strip()]
    if not paragraphs and draft.get('cover_letter_text'):
        text = str(draft['cover_letter_text']).strip()
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n' if re.search(r'\n\s*\n', text) else r'\n', text) if p.strip()]
        if draft.get('relocation_line') and str(draft['relocation_line']) not in paragraphs[-1]:
            paragraphs[-1] += ' ' + str(draft['relocation_line'])
    return body, paragraphs, [(item['question'], item['answer']) for item in answer_items(draft)[0]]


# Form questions: which line of facts.json -> answers covers a question. Rules are read top to bottom and the
# first match decides, so a narrow rule stands above the broad rule it would otherwise fall into (future
# sponsorship above right to work, manual and interstate licences above driver's licence, experience in X
# above the topic X). A key that facts.json does not have yet (expected_hourly_rate, declarations_and_consents)
# means: ask the owner, and one line added to facts.json -> answers under that name settles it for good.
UNSETTLED = re.compile(r'not confirmed|not on record|skip and report|not answered here', re.I)
OFFICE_PRODUCT = re.compile(r'\b(excel|word|powerpoint|outlook|products)\b')
QUALIFICATION = r"\bqualifications?\b|\bdegree\b|\bdiploma\b|\bbachelor|\bcertificat|level of education|educational background|\byear 12\b"
SOFTWARE = (r'software|autocad|civil ?3d|revit|microsoft|ms office|\bcad\b|\bbim\b|(?<![a-z0-9])('
            + '|'.join(re.escape(t.lower()) for t in KNOWN_TOOLS) + r')(?![a-z0-9])')
LOOKUPS = ('qualification_questions', 'years_of_experience', 'software', 'experience_yes_no')
EXPERIENCE = '@experience'  # a yes/no question about experience: software when it names software, else experience_yes_no
ANSWER_RULES = [
    # Private or unknowable: nobody but the owner answers.
    (None, r'visa (grant )?number|passport|date of birth|\bdob\b|legal name|tax file|\btfn\b|\bbank\b|medical condition|injur|disabilit|gender|pronoun'
           r'|aboriginal|torres strait|\breferred|security clearance|linkedin|defence force|military|adjustments|how far|commute'),
    # A question where yes is the bad answer, or that asks about his past conduct: a standing 'Yes' must never land on it.
    (None, r"\bever\b|suspend|disqualified|cancel|revoked?\b|offen[cs]e|convict|demerit|infringement|penalt|dismiss|terminated|bankrupt|conflict of interest|any reason"
           r"|\bobject\b|\brefus|\bunable\b|\bprevent|\bfail|criminal (record|history\b(?! (check|screen)))|illicit|\b(use|take|taking|using) (of )?(any )?drugs|addict"),
    (None, r"(how many|number of) years\b.*\b(in australia|australian|locally?)\b"),  # his paid engineering work was in the Philippines
    (None, r"(how many|number of) years\b.*\b(current occupation|similar role|relevant experience|role you are applying|this (role|position))"),  # years in a role the question does not name
    ('years_of_experience', r"^(?!(do|have|are|did) you\b).*(how many years\b.*\bexperience|\byears of [\w ,/&'-]*experience|\byears'? experience|number of years)"),
    (EXPERIENCE, r'^(?!.*(' + QUALIFICATION + r'))(do|have|are|did) you\b.*\b(experienced?|worked|familiar|proficient)\b'),
    ('currently_studying', r'currently (studying|enrolled)'),
    ('english_self_rating', r'english'),
    ('engineers_australia_membership_or_recognition', r'engineers australia|washington accord|\b(recognised|accredited|assessed) by\b'),
    ('future_visa_sponsorship', r'sponsor\w*\b.*\b(future|later|at any time)\b|\b(future|will you|would you)\b.*\bsponsor'),
    ('right_to_work', r'rights? to work|work(ing)? rights?|(eligib\w+|entitled|authori[sz]ed|allowed|permitted) to (live and )?work|visa|sponsor|citizen|permanent resident'),
    ('notice_period', r'notice|availab\w+ to (start|commence)|start date|when can you (start|commence)'),
    ('expected_salary', r'salary|remuneration'),
    ('expected_hourly_rate', r'hourly rate|rate expectation|\b(current|daily|day|charge|pay) rate\b'),
    (('manual_licence', 'drivers_licence'), r'manual (vehicle|car|licen[cs]e|transmission|driver)|drive (a )?manual|manual or auto'),
    ('interstate_drivers_licence', r"\b(wa|nsw|qld|queensland|western australian?|new south wales|south australian?|tasmanian?|northern territory)\b[^?.]{0,25}\b(driver|licen[cs]e)"),
    ('qualification_questions', r'heavy (rigid|vehicle|combination)|truck|forklift|motorcycle|\b(hr|mr|hc|lr|mc)\b[ -]?(class )?licen[cs]e'),
    ('drivers_licence', r"driver|licen[cs]ed? to drive|\bclass c\b|car licen[cs]e|\b(provisional|probationary)\b|\bp[ -]?plate"),
    ('own_car_or_regular_access', r'access to a (car|vehicle)|own (a |reliable |your own )?(car|vehicle|transport)|reliable (access to )?transport'),
    ('white_card', r'white card|construction induction|general construction induction'),
    ('police_check', r'police (check|certificate|clearance)|national police|criminal history (check|screen)'),
    ('drug_and_alcohol_screening', r'drugs?\b.*\b(screen|test)|\b(screen|test)\w*\b.*\bdrug'),
    ('pre_employment_medical', r'pre.?employment medical|medical (check|assessment|examination)'),
    ('willing_to_relocate', r'relocat'),
    ('willing_to_travel_or_fifo', r'fifo|dido|\btravel|roster'),
    ('identity.location', r'\bresid(e|ing)\b|current location|^location\b|which suburb|where (are|do) you\b[^?]*\b(based|located|living|live)\b|do you (currently )?live\b|living in australia|are you located'),
    ('identity.short_name', r'^preferred name'),
    ('referees', r'referee'),
    ('free_text_cover_letter', r'cover letter'),
    ('declarations_and_consents', r"^i (acknowledge|consent|agree|declare|confirm|certify|understand)\b|privacy policy|true and correct|terms and conditions"),
    # Open-ended: free text, a self-rating or a choice nobody has made for him.
    (None, r"\b(please|can you|could you) (briefly )?(outline|describe|explain|share|name some|tell (us|me))\b|^(outline|describe|explain|share|tell (us|me))\b"
           r"|^what (previous |relevant |prior )?(experience|skills)\b|^why\b|\bwhat (interests|motivated|attracted|led)\b|how did you (hear|find)|\brate your\b|how would you rate"),
    ('qualification_questions', QUALIFICATION),
    ('software', SOFTWARE),
    ('qualification_questions', r"licen[cs]e|ticket|induction|registration|registered|accreditation|\bmember|working with children|\bwwcc?\b"),
]


def rule_keys():
    """Every line of facts.json -> answers (and identity) that a rule can lead to."""
    keys = set()
    for key, _ in ANSWER_RULES:
        keys.update(('software', 'experience_yes_no') if key == EXPERIENCE else key if isinstance(key, tuple) else [key] if key else [])
    return keys


def _words(text):
    return re.findall(r'[a-z0-9]+', str(text).lower())


def _stem(word):
    """'designer' and 'design', 'drafter' and 'drafting', 'estimator' and 'estimating' meet at one stem."""
    return re.sub(r'(sperson|person|ers|er|ors|or|ing|ion|s)$', '', word) if len(word) > 5 else word


def _phrase_span(name, question_words):
    """(start, end) of the last match of a table name in the question, or None: each word of the name, as a
    stem, begins the next word of the question."""
    stems = [_stem(w) for w in _words(name)]
    same = lambda word, stem: word.startswith(stem) if len(stem) > 3 else word == stem  # 'cad' is not the start of 'cadet'
    starts = [i for i in range(len(question_words) - len(stems) + 1) if stems and all(same(question_words[i + j], s) for j, s in enumerate(stems))]
    return (starts[-1], starts[-1] + len(stems)) if starts else None


CATCH_ALL = re.compile(r'any other|anything else|other$')
GENERIC = {'project', 'projects', 'work', 'works', 'role', 'roles', 'experience', 'any', 'other', 'and', 'or', 'of', 'in', 'the', 'a'}
# A named line says something exact ('Yes', 'eleven months as a civil engineer'). A question that narrows or raises
# it asks something else and gets the table's catch-all instead: '3+ years of site inspections', 'an Australian
# degree in civil engineering', 'Rail Project Engineer', 'Senior Site Engineer'.
MORE_ASKED = r"\d+\s*\+?\s*(years?|yrs?|months?)|\bat least\b|\bminimum\b|\bextensive\b|\baustralian?\b|\bhonours\b|\bmasters?\b|\bpost ?graduate\b|\b(4|four)[ -]year\b"
PLAIN_BEFORE_ROLE = {'civil', 'junior', 'graduate', 'assistant', 'construction', 'site', 'project'}  # 'Assistant Civil Engineer' is still a civil engineer
ROLE_STARTS_AFTER = {'a', 'an', 'the', 'as', 'in', 'of', 'with', 'for', 'have', 'years', 'experience'}


def _entry(key, table, q):
    """(name, value) of the line of a lookup table (facts.json -> answers -> key) that covers the question;
    the table's catch-all ('any other ...', 'anything else', 'other') when no line names it; (None, None)
    when the table has neither."""
    rows = {name: value for name, value in table.items() if name not in ('rule', '_about')}
    rest = next((name for name in rows if any(CATCH_ALL.match(n.strip().lower()) for n in name.split(','))), None)
    names = [(name, n.strip().lower()) for name in rows for n in name.split(',') if n.strip() and not CATCH_ALL.match(n.strip().lower())]
    found = None
    if key == 'software':  # tool names are matched as written: 'cad' is in 'autocad'
        office = next((name for name, n in names if 'office' in n), None)
        found = office if office and OFFICE_PRODUCT.search(q) else next((name for name, n in names if n in q), None)
    elif key == 'qualification_questions':
        # 'a qualification in X': X must BE a field facts.json names. 'engineering' is not 'mechanical engineering'.
        field = re.search(r"\b(?:qualifications?|degree|diploma|background|bachelor(?:'?s)?(?: degree)?) (?:in|of) ([^?.]+)", q)
        options = {' '.join(_words(o)) for o in re.split(r'\bor\b|/|,', field.group(1))} if field else set()
        found = next((name for name, n in names if {' '.join(_words(o)) for o in re.split(r'\bor\b', n)} & options), None)
    else:  # the name that ends last in the question is the head of the phrase: 'Civil Engineering Technician' is a technician
        qw, spans = _words(q), []
        for name, n in names:
            span = _phrase_span(n, qw)
            before = []
            for word in reversed(qw[:span[0]] if span else []):
                if word in ROLE_STARTS_AFTER:
                    break
                before.append(word)
            claims = 'lowest option' not in str(rows[name]).lower()  # a line that claims time worked: only for the plain role
            if span and not (key == 'years_of_experience' and claims and set(before) - PLAIN_BEFORE_ROLE):
                spans.append((span[1], len(n), name))
        found = max(spans)[2] if spans else None
    if found and key in ('qualification_questions', 'experience_yes_no') and re.search(MORE_ASKED, q):
        found = None
    name = found or rest
    return (name, rows[name]) if name else (None, None)


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


def _open_line(q):
    """(key, name, value) of a lookup line that is open whatever the form asks ('Not confirmed ...') and whose
    subject is in the question, in any order and any phrasing: 'civil infrastructure projects' covers
    'experience in civil infrastructure' and 'years of civil infrastructure construction experience'."""
    qw = _words(q)
    for key in LOOKUPS:
        table = ANSWERS.get(key)
        for name, value in (table.items() if isinstance(table, dict) else []):
            if name in ('rule', '_about') or not _unsettled(value, ''):
                continue
            for n in name.split(','):
                subject = [_stem(w) for w in _words(n) if w not in GENERIC]
                if subject and all(any(w.startswith(s) for w in qw) for s in subject):
                    return key, name, value
    return None


def _case(key, q):
    """The question plus the words an 'If the form asks X: ...' sentence uses for the case it is asking about."""
    if key == 'drivers_licence':
        q += ' full' * bool(re.search(r'\b(open|unrestricted)\b', q)) + ' probationary' * bool(re.search(r"provisional|\bp[ -]?plate|\bp[12]\b", q))
    if key == 'software' and OFFICE_PRODUCT.search(q):
        q += ' individual products'  # one Office product named
    return q


def resolve(question):
    """{'key', 'entry', 'value', 'problem'} for one form question: the line of facts.json -> answers that covers
    it (key None when nothing does, entry the row of a lookup table) and, in problem, why the owner must be
    asked (None when the line settles the answer)."""
    q = ' '.join(str(question or '').lower().replace('’', "'").split())
    out = {'key': None, 'entry': None, 'value': None, 'problem': 'no standing answer in facts.json -> answers'}
    if not q:
        return out
    if any(re.search(pattern, q) for key, pattern in ANSWER_RULES[:2]):
        return {**out, 'problem': 'a private, open-ended or unknown detail: only the owner can answer it'}
    open_line = _open_line(q)
    if open_line:
        key, name, value = open_line
        return {'key': key, 'entry': name, 'value': value, 'problem': f'facts.json -> answers -> {key} -> {name} is not confirmed'}
    for key, pattern in ANSWER_RULES[2:]:
        if not re.search(pattern, q):
            continue
        if key is None:
            return {**out, 'problem': 'a private, open-ended or unknown detail: only the owner can answer it'}
        if key == EXPERIENCE:
            key = 'software' if re.search(SOFTWARE, q) else 'experience_yes_no'
        if isinstance(key, tuple):
            key = next((k for k in key if k in ANSWERS), key[0])
        value = FACTS['identity'].get(key[9:]) if key.startswith('identity.') else ANSWERS.get(key)
        entry = None
        if key in LOOKUPS and isinstance(value, dict):
            entry, value = _entry(key, value, q)
        if value is None:
            return {'key': key, 'entry': entry, 'value': None, 'problem': f'facts.json -> answers has no "{key}"'}
        if _unsettled(value, _case(key, q)):
            return {'key': key, 'entry': entry, 'value': value, 'problem': f'facts.json -> answers -> {key} is not confirmed for this question'}
        return {'key': key, 'entry': entry, 'value': value, 'problem': None}
    return out


def standing_answer(question):
    """(key, problem) for one form question. key is the line of facts.json -> answers that covers it (None when
    nothing does); problem is None when that line settles the answer, else why the owner must be asked. This
    only says whether a standing answer exists: the submitter still reads that line and the form's options."""
    found = resolve(question)
    return found['key'], found['problem']


def line_text(value):
    """A standing answer as one line of text: a rule with choose / never_choose is written out part by part."""
    if isinstance(value, dict):
        return ' '.join(f"{k.replace('_', ' ').capitalize()}: {line_text(v).rstrip('.')}." for k, v in value.items() if not k.startswith('_'))
    if isinstance(value, list):
        return '; '.join(line_text(v) for v in value)
    return str(value)


def standing_line(question):
    """(basis, text, problem): where in facts.json the standing answer is ('answers.notice_period',
    'answers.years_of_experience.<row>', 'identity.location'), that line as text, and why the owner must be
    asked instead (None when the line settles it; text is then what the submitter follows)."""
    found = resolve(question)
    if not found['key']:
        return '', '', found['problem']
    basis = found['key'] if found['key'].startswith('identity.') else 'answers.' + found['key'] + ('.' + found['entry'] if found['entry'] else '')
    return basis, '' if found['value'] is None else line_text(found['value']), found['problem']


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


# A written answer against the standing one.
PLACEHOLDER = re.compile(r'\b(marc|owner|he) (to|must|should|needs to) (confirm|answer|decide|choose|check|provide|complete|fill|advise)\b|\bto be (confirmed|advised|decided)\b|\btb[ca]\b', re.I)
BARE_YES = re.compile(r"^\W*(yes|yep|yeah|correct|true)\b", re.I)
AFFIRMS = re.compile(r"^\W*(yes|yep|yeah|correct|true|i do|i am|i have|i hold)\b", re.I)
DENIES = re.compile(r"^\W*(no|nope|none|not|never|false|i do not|i don't|i am not|i'm not|i have not|i haven't|i have no)\b", re.I)
RESIDENCY = ('claims permanent residency', 'claims citizenship', 'claims PR')
SAYS_YES_TO = RESIDENCY + ('claims a professional registration', 'claims a master degree', 'claims honours')
NUMBER_WORDS = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'six': '6', 'eight': '8'}
YEARS_GIVEN = re.compile(r"(?P<lead>(?:less than|under|below|up to|fewer than|<|\b0\s*(?:-|to))\s*)?(?P<n>\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b"
                         r"|\b(?P<word>one|two|three|four|five|six|seven|eight|nine|ten|several|many)\s+(?:\w+\s+)?years?\b", re.I)
MONEY = re.compile(r'(\$)?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k\b)?', re.I)


def says(text):
    """'yes', 'no' or '' for how a written answer begins."""
    return 'no' if DENIES.match(text) else 'yes' if AFFIRMS.match(text) else ''


def salary_band():
    """(low, high) of the standing salary band in facts.json -> answers -> expected_salary, or None."""
    rule = ANSWERS.get('expected_salary')
    band = re.search(r'\$([\d,]+) to \$([\d,]+)', line_text(rule or ''))
    return tuple(int(x.replace(',', '')) for x in band.groups()) if band else None


def amounts(text):
    """[(amount, as written)] for the money figures in a text: '$95k', '$70,000', '70000', '$60-65k'. A bare small number is not money."""
    out = []
    for dollar, digits, k in MONEY.findall(re.sub(r'(\d+)\s*(-|to)\s*(\d+)\s*k\b', r'\1k \2 \3k', str(text or ''), flags=re.I)):
        amount = float(digits.replace(',', '')) * (1000 if k else 1)
        if dollar or k or ',' in digits or amount >= 20000:
            out.append((amount, f"{'$' if dollar else ''}{digits}{'k' if k else ''}"))
    return out


def answer_issues(question, answer, advert_pay=''):
    """A written form answer against facts.json: a placeholder is not an answer, a yes must not claim what the
    question names and the facts do not have, a yes or no must not contradict the standing line, years and a
    salary figure must be the ones the standing line gives. advert_pay: the advert's own pay text; a figure
    in it may be given."""
    issues = []
    text = str(answer or '').strip()
    found = resolve(question)
    line = '' if found['value'] is None else line_text(found['value'])
    if re.search(r'\[[^\]]*\]', text):
        issues.append('leaves a blank in square brackets for someone to fill in')
    elif PLACEHOLDER.search(text):
        issues.append('is a placeholder, not an answer: the question goes to the owner (ASK_OWNER)')
    said = says(text)
    if BARE_YES.match(text):  # a bare yes takes on whatever the question names
        asked = str(question or '')
        names_his_tool = any(re.search(r'(?<![a-z0-9])' + re.escape(s.lower().split()[0]), asked.lower()) for s in FACTS['capabilities']['software'])
        for tool in ([] if names_his_tool or unknown_tools(text) else unknown_tools(asked)):
            issues.append(f'says yes to software not in facts: {tool}')
        offers_visa = re.search(r'visa|rights? to work|work(ing)? rights?|entitled|eligib', asked, re.I)  # 'citizen, resident or valid visa': yes is true
        for pat, why in FORBIDDEN_CLAIMS:
            if why in SAYS_YES_TO and re.search(pat, asked, re.I) and not (offers_visa and why in RESIDENCY):
                issues.append(f'says yes to a question that {why}')
    plain = isinstance(found['value'], str) and re.match(r'\W*(yes|no)\b(?! only)', found['value'], re.I)
    if plain and not found['problem'] and said and plain.group(1).lower() != said:
        issues.append(f"says {said} where facts.json -> answers -> {found['key']} says: {line[:80]}")
    short = isinstance(found['value'], str) and not plain and not found['problem'] and len(found['value'].split()) <= 3
    digits = lambda t: ' '.join(NUMBER_WORDS.get(w, w) for w in _words(t))
    if short and found['key'] in ANSWERS and digits(found['value']) not in digits(text):  # '2 weeks' is the answer; 'None, ready now' is not
        issues.append(f"does not give the standing answer in facts.json -> answers -> {found['key']}: {line}")
    if found['key'] == 'years_of_experience' and ' '.join(text.lower().split()) not in ' '.join(line.lower().split()):
        for m in YEARS_GIVEN.finditer(text):
            if m.group('word') or (float(m.group('n')) >= 1 and not m.group('lead')):
                issues.append(f'gives "{m.group(0).strip()}" where facts.json -> answers -> years_of_experience says: {line[:90]}')
                break
    band = salary_band()
    if found['key'] == 'expected_salary' and band:
        advertised = {amount for amount, _ in amounts(advert_pay)}
        for amount, shown in amounts(text):
            if amount < 1000:
                issues.append(f'gives an hourly or daily figure ({shown}); facts.json -> answers has no hourly rate')
            elif not band[0] <= amount <= band[1] and amount not in advertised:
                issues.append(f"salary figure {shown} is outside the standing band ${band[0]:,} to ${band[1]:,} (facts.json -> answers -> expected_salary) and is not the advert's own figure (advert_pay)")
    return issues


def fact_at(basis):
    """The value at a dotted facts.json path such as 'answers.notice_period' or 'answers.software.CAD'; None when there is none."""
    value, parts = FACTS, str(basis or '').split('.')
    while parts:
        if not isinstance(value, dict):
            return None
        take = next((n for n in range(len(parts), 0, -1) if '.'.join(parts[:n]) in value), 0)  # a row name may hold a full stop
        if not take:
            return None
        value, parts = value['.'.join(parts[:take])], parts[take:]
    return value


def draft_issues(draft):
    """Everything written in one draft against config -> tone and facts.json. The visa end date passes
    only when the draft carries advert_asks_about_visa true (or, in a form answer, the question asks)."""
    visa = draft.get('advert_asks_about_visa') is True
    body, paragraphs, _ = draft_parts(draft)
    issues = ['email ' + i for i in tone_issues(body, 'email', visa) + fact_issues(body)] if body else []
    if paragraphs:
        text = '\n'.join(paragraphs)
        issues += ['letter ' + i for i in tone_issues(text, 'letter', visa) + fact_issues(text)]
        if len(paragraphs) > 3:
            issues.append(f'letter has {len(paragraphs)} paragraphs (three short paragraphs: config -> tone -> letter_shape)')
    letter = draft.get('letter') or {}
    email = draft.get('email') if isinstance(draft.get('email'), dict) else {}
    for name, line in (('email subject', draft.get('subject') or email.get('subject')), ('letter subject', letter.get('subject')), ('letter greeting', letter.get('greeting')),
                       ('letter closing', letter.get('closing'))):
        issues += [f'{name} {i}' for i in tone_issues(str(line or ''), 'answer', visa)]
    answers, unreadable = answer_items(draft)
    if unreadable:
        issues.append(unreadable)
    for item in answers:
        question, answer = item['question'], item['answer']
        if not isinstance(answer, str) or not answer.strip():
            if answer not in (None, ''):
                issues.append(f'answer to "{question[:60]}" is not text ({type(answer).__name__})')
            continue
        if item['basis']:  # an answer taken from facts.json: it must be that line, and a yes or no must agree with it
            value = fact_at(item['basis'])
            plain = isinstance(value, str) and re.match(r'\W*(yes|no)\b', value, re.I)
            if value is None:
                issues.append(f'answer to "{question[:60]}" names a basis that is not in facts.json: {item["basis"]}')
            elif plain and says(answer) and says(answer) != plain.group(1).lower():
                issues.append(f'answer to "{question[:60]}" contradicts facts.json -> {item["basis"]}')
            continue
        asked = visa or bool(VISA_QUESTION.search(question))
        truth = [i for i in fact_issues(answer) if not (i.startswith('amount not in facts') and SALARY_QUESTION.search(question))]  # a salary answer is a figure
        found = tone_issues(answer, 'answer', asked) + truth + answer_issues(question, answer, draft.get('advert_pay'))
        issues += [f'answer to "{question[:60]}" {i}' for i in found]
    return issues


def record_issues(rec, require_uploaded=True):
    issues = []
    for k in ('company', 'role', 'status', 'job_url', 'fit', 'gaps', 'match_score'):
        if not rec.get(k):
            issues.append(f'missing {k}')
    status = canonical_status(rec.get('status'))
    ask = rec.get('ask_owner')
    ask = {'questions': [{'question': ask}]} if isinstance(ask, str) and ask.strip() else ask if isinstance(ask, dict) else {}  # a queue entry asks in one line of text
    target = canonical_status(ask.get('then')) if status == STATUSES['ask_owner'] else status  # what it is, or becomes once the owner answers
    email = str(rec.get('recipient_email') or '')
    route = str(rec.get('application_route') or '').upper()
    ready = target in READY_STATUSES
    # The channel is the record's route, not its status: an email application stays one while it is SENDING or SENT.
    by_email = route == 'EMAIL' if route else target == STATUSES['prepared'] or (not ready and bool(email))
    if ready and (by_email or email or rec.get('email_body')):
        issues.append('one application per advert through one channel: a SEEK, portal or form record carries no email to send (double touch retired 13 Nov 2026)')
    elif by_email:
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
    if status == STATUSES['ask_owner'] and not ask.get('questions'):
        issues.append('ASK_OWNER record needs the question for the owner (ask_owner.questions)')
    if status != STATUSES['ask_owner'] and ask.get('questions'):
        issues.append(f'{status} record still has an open question for the owner')
    if ready:  # what a submitter will type into a form: only the lines of facts.json, checked again here
        for item in answer_items(rec)[0]:
            basis, text, problem = standing_line(item['question'])
            if item['basis'] and (problem or (item['basis'], item['answer']) != (basis, text)):
                issues.append(f'form answer is not the standing answer in facts.json -> answers: "{item["question"][:60]}"')
            elif not item['basis'] and status != STATUSES['ask_owner']:
                issues.append(f'{status} record carries a form answer that is not from facts.json -> answers: "{item["question"][:60]}"')
        if status != STATUSES['ask_owner']:
            issues += [f'{status} record has a form question with no standing answer (it must be ASK_OWNER): "{u["question"][:60]}"' for u in unanswered_questions(form_questions(rec))]
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
        data = read_json(a.file)
        unreadable = answer_items(data)[1]
        issues = ([unreadable] if unreadable else []) + [f"ask the owner: {u['question']} ({u['why']})" for u in unanswered_questions(form_questions(data))]
    else:
        issues = record_issues(read_json(a.file))
    for i in issues:
        print('- ' + i)
    print('OK' if not issues else f'{len(issues)} issue(s)')
    sys.exit(1 if issues else 0)


if __name__ == '__main__':
    main()
