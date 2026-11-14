#!/usr/bin/env python3
"""Checks before anything is sent or submitted: tone and length (config -> tone), truth against
facts.json, standing answers for form questions, and record completeness.

Usage:
  checks.py tone FILE [--kind email|letter|answer] [--visa-asked]   # banned phrases, dashes, volunteered limits, length
  checks.py facts FILE             # claims that do not trace to facts.json
  checks.py draft DRAFT.json       # every written part of one draft or queue entry: email, cover letter, form answers
  checks.py questions FILE.json    # form questions of a draft or candidate: standing answer in facts.json, or ask the owner
                                   # (the salary question needs the advert's pay: advert_pay, or a candidate's salary text)
  checks.py record RECORD.json     # everything a tracker record needs
Exit code 1 when any issue is found.

Letters and emails: letter_issues(text) and email_issues(subject, body) hold the one set of writing rules; queue.py
(next, letter) and letter_pdf.py call them too. A letter is an optional greeting line ('Hello,' or 'Hello <name>,'),
exactly three paragraphs, and an optional sign-off ('Marc Masarate', with a closing, phone, email or portfolio line);
the greeting and the sign-off are not paragraphs. A queue entry's relocation_line is checked where compose_letter
puts it, at the end of the last paragraph.

Form answers are read in every shape the drafts use: a list of {question, answer}, a list of {q, a},
or one {question: answer} object. A shape that cannot be read is an issue, never a silent pass.
A form question is answered only by answers.py, the one gate queue.py uses too (standing_answer, standing_line and
resolve are thin wrappers over it): a question no line of facts.json -> answers clearly covers goes to the owner.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import answers as gate
from common import CONFIG, FACTS, canonical_status, read_json

TONE = CONFIG['tone']
STATUSES = CONFIG['statuses']
READY_STATUSES = (STATUSES['ready_seek'], STATUSES['ready_portal'], STATUSES['ready_form'])
ANSWERS = FACTS.get('answers', {})
KNOWN_TOOLS = gate.KNOWN_TOOLS  # one list: software a text or a form may name that is not his
ALLOWED_YEARS = {'2014', '2015', '2016', '2017', '2018', '2019', '2020', '2022', '2024', '2026', '2027'}
FORBIDDEN_CLAIMS = [
    (r'\bpermanent resid', 'claims permanent residency'),
    (r'\bcitizen', 'claims citizenship'),
    (r'\bPR\b', 'claims PR'),
    (r'australian (work|site|construction|industry) experience', 'claims Australian work experience'),
    (r'\b(chartered|CPEng|RPEQ|NER\b|registered engineer|licensed engineer)', 'claims a professional registration'),
    (r'\b\d+\+?\s*years?\s+(of\s+)?(commercial|industry|professional|drafting|design|civil)\b', 'claims years of professional experience'),
    (r'\b(sponsor|sponsorship|migration|residency goal)', 'mentions sponsorship or migration'),
    (r'\bskills? assessment', 'mentions a skills assessment (facts.json -> never_mention)'),
    (r'\bvisa (application|applications|grant|plans?|pathway|nomination|lodg\w*)\b|\b(state|regional|employer) nomination\b'
     r'|\b(subclass\s*)?(189|190|191|482|491|494|186|187)\s*(visa|nomination|subclass|application)\b|\bsubclass\s*(189|190|191|482|491|494|186|187)\b'
     r'|\bnominat\w*\b[^.!?\n]{0,30}\bvisa\b|\b(apply|applying|applied) for (a |an |my |the )?(permanent |new |next )?visa\b', 'mentions visa plans (facts.json -> never_mention)'),
    (r'\bmaster(\'s)?\s+(degree|of)', 'claims a master degree'),
    (r'\bhonours\b', 'claims honours'),
    (r'\binternship\b', 'claims an internship'),
    (r'\bwork placement\b', 'claims a placement'),
    (r'\breferee', 'names or offers referees inline'),
]
# The approved short work-rights line says "no sponsorship needed"; that is not a sponsorship request.
APPROVED = re.compile(r'no sponsorship (is )?(needed|required)', re.I)
# Residency or migration talk in a letter, an email or its subject (facts.json -> never_mention; AGENTS.md rule 6), in
# whole words: 'PR' in capitals only (not 'PRE-START', 'Present' or 'prepared'), 'nomination' (not 'nominated').
RESIDENCY_TALK = re.compile(r'(?-i:\bPR\b)|\bresidency\b|\bresident status\b|\bpermanent visas?\b|\bsettle permanently\b'
                            r'|\blong[- ]?term visas?\b|\bsponsor me\b|\bsponsorship in the future\b|\bvisa pathways?\b|\bnominations?\b', re.I)
RESIDENCY_WHY = 'mentions residency or migration (facts.json -> never_mention): "{}"'


def residency_issues(text):
    """The residency or migration phrases (RESIDENCY_TALK) in a text, each once, as issues."""
    found = dict.fromkeys(m.group(0) for m in RESIDENCY_TALK.finditer(APPROVED.sub('', str(text or ''))))
    return [RESIDENCY_WHY.format(phrase) for phrase in found]
# The visa end date, however it is written: 'December 2027', 'Dec 2027', '12/2027', 'visa valid through 2027', 'until the end of 2027',
# or as time left: 'valid for another 13 months', 'has 13 months left', 'runs out late next year'.
COUNT = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|eighteen|twenty(-\w+)?)'
VISA_DATE = re.compile(r'\bdec(ember|\.)?\s+2027\b|\b12\s*/\s*(20)?27\b|\b(until|till|through|thru)\s+(the\s+)?(end\s+of\s+)?(\w+\s+)?2027\b'
                       r'|\b(visa|485|work(ing)? rights?|expir\w*)\b[^.!?\n]{0,40}\b2027\b|\b2027\b[^.!?\n]{0,20}\bexpir'
                       r'|\b' + COUNT + r'\s+(more\s+)?(months?|years?)\s+(left|remaining|to run|to go)\b'
                       r'|\bvalid for (about |around |roughly |another |a further |at least |over )*' + COUNT + r'\s+(more\s+)?(months?|years?)\b'
                       r'|\b(visa|485|work(ing)? rights?)\b[^.!?\n]{0,40}\b(runs? out|ends?|expires?|finish(es)?|lapses?|is valid (until|till|to|for)'
                       r'|valid (until|till|to|for)|left on it)\b', re.I)
VISA_FLAG = re.compile(r'2027|expires', re.I)  # the flag patterns that are about the visa end date
SALARY_QUESTION = re.compile(r'salary|remuneration|\brate\b', re.I)
VISA_QUESTION = re.compile(r'visa|work(ing)? rights?|rights? to work|residency|permanent resident|citizen', re.I)
# The current Australian job is casual console-operator work at a service station (facts -> experience -> use).
# A sentence about that job must not carry civil work, unless the civil part is plainly somewhere else (the
# Philippines, 2019, 2020), is the name of his qualification, or sits in a clause about study or job hunting.
CONSOLE = re.compile(r"console operator|service station|\bbp\b|\bsince\s+(may\s+)?2024\b|\bmy (current|present) (role|job|position|work|employer|employment)\b"
                     r"|\b(currently|presently) (work|working|employed)\b|\bmy australian (work|job|role)\b", re.I)
CIVIL_WORK = re.compile(r'\b(civil|construction|sites?|engineering|drafting|design\w*|inspect\w*|co-?ordinat\w*|infrastructure|earthworks|drainage)\b', re.I)
ELSEWHERE = re.compile(r'philippines|justbuilt|grand travaux|2019|2020', re.I)
QUALIFICATION_NAMES = re.compile(r'(advanced diploma of )?civil construction design|bachelor of science in civil engineering|civil engineering (degree|graduate)', re.I)
ASIDE = re.compile(r'\b(while|whilst|alongside|during|look\w* for|seek\w*|apply\w* for|want\w* to|hop\w* to|aim\w* to|return\w* to|mov\w* (back )?(in)?to)\b[^,;]*', re.I)
LINK = re.compile(r'https?://\S+|\S+@\S+\.\S+')


def words(text):
    """Word count. A link or an email address counts as one word."""
    return len(re.findall(r"[A-Za-z0-9'’]+", LINK.sub('link', text)))


def _tone(tone=None):
    """config -> tone, with the rules of another config (queue.py --config) added: the lists are joined, the numbers
    of the other config are used. Both are automation/config.json unless a caller says otherwise."""
    tone = tone or {}
    out = {**TONE, **{k: v for k, v in tone.items() if k not in ('banned_phrases', 'banned_characters', 'no_volunteered_limits')}}
    out['banned_phrases'] = list(dict.fromkeys(list(TONE['banned_phrases']) + list(tone.get('banned_phrases') or [])))
    out['banned_characters'] = list(dict.fromkeys(list(TONE['banned_characters']) + list(tone.get('banned_characters') or [])))
    flags = list(TONE['no_volunteered_limits']['flag_patterns']) + list((tone.get('no_volunteered_limits') or {}).get('flag_patterns') or [])
    out['no_volunteered_limits'] = {**TONE['no_volunteered_limits'], 'flag_patterns': list(dict.fromkeys(flags))}
    return out


def tone_issues(text, kind='email', visa_asked=False, tone=None, allow=()):
    """config -> tone on one piece of text. kind: 'email' (130 words), 'letter' (200), 'answer' (a free-text
    form answer, no word limit). visa_asked: the advert or the form question asks about visa or residency,
    so the end date may be given. tone: the tone block of another config (see _tone). allow: flagged phrases this
    text may keep (a queue entry's tone_allow)."""
    tone = _tone(tone)
    allowed = {' '.join(str(x).lower().split()) for x in allow or []}
    issues = []
    low = text.replace('’', "'").replace('‘', "'").lower()
    for phrase in tone['banned_phrases']:
        if phrase in low:
            issues.append(f'banned phrase: "{phrase}"')
    for ch in tone['banned_characters']:
        if ch in text:
            issues.append(f'banned character: {ch!r} (use a comma, full stop or "to")')
    for pattern in tone['no_volunteered_limits']['flag_patterns']:
        # Whole words only: 'have not' is not in 'I have noted' or 'I have nothing but', 'although i' is not in 'although it'.
        found = re.search(r'(?<![a-z])' + re.escape(pattern.lower()) + r'(?![a-z])', low)
        if found and pattern.lower() not in allowed and not (visa_asked and VISA_FLAG.search(pattern)):
            issues.append(f'volunteers a limit: "{pattern}" (say what he has done; never what he lacks)')
    if VISA_DATE.search(text) and not visa_asked:
        issues.append('gives the visa end date; only where the advert or form asks about visa or residency (advert_asks_about_visa)')
    if text.count('!') > tone['max_exclamations']:
        issues.append('too many exclamation marks')
    limit = {'email': tone['max_email_words'], 'letter': tone['max_cover_letter_words']}.get(kind)
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
    the blank lines are; cover_letter_text with no blank line is split on its line breaks. The greeting line and
    the sign-off of cover_letter_text are not paragraphs (letter_blocks)."""
    email = draft.get('email') if isinstance(draft.get('email'), dict) else {}
    body = str(draft.get('email_body') or email.get('body') or '')
    paragraphs = [b.strip() for p in (draft.get('letter') or {}).get('paragraphs') or [] for b in re.split(r'\n\s*\n', str(p)) if b.strip()]
    if not paragraphs and draft.get('cover_letter_text'):
        paragraphs = letter_blocks(compose_letter(draft['cover_letter_text'], draft.get('relocation_line')))[1]
    return body, paragraphs, [(item['question'], item['answer']) for item in answer_items(draft)[0]]


def letter_text(draft):
    """The whole letter of a draft as one text, for letter_issues: cover_letter_text with its relocation line, or the
    paragraphs of a run-folder letter (its greeting and closing are checked as lines of their own)."""
    paragraphs = [str(p) for p in (draft.get('letter') or {}).get('paragraphs') or [] if str(p).strip()]
    if paragraphs:
        return '\n\n'.join(paragraphs)
    return compose_letter(draft.get('cover_letter_text'), draft.get('relocation_line'))


# ------------------------------------------------------------------------------------------- the answer gate
# Form questions are answered by answers.py alone, the one gate queue.py uses too: it answers only what a line of
# facts.json -> answers clearly covers and sends everything else to the owner. The functions below keep their
# names for their callers (publish.py, the questions and record commands); each is a thin wrapper over gate.answer.

def _gate(question, options=None, pay=None):
    return gate.answer(question, options or [], FACTS, pay=pay)


def _key(basis):
    """The facts.json key a basis names: 'answers.years_of_experience.<row>' -> 'years_of_experience';
    'identity.location', 'eligibility.availability' and 'education' as they are; None for no basis."""
    basis = str(basis or '')
    return basis.split('.')[1] if basis.startswith('answers.') and basis.count('.') else basis or None


def rule_keys():
    """Every line of facts.json -> answers (and identity, eligibility, education) that the gate reads."""
    return set(gate.KEYS)


def _words(text):
    return re.findall(r'[a-z0-9]+', str(text).lower())


def resolve(question, pay=None):
    """{'key', 'entry', 'value', 'problem', 'basis', 'answer'} for one form question, from the gate (answers.py):
    key is the line of facts.json it reads (None when none), entry the row of a lookup table or the part of a rule
    ('free_text', 'choose'), value the gate's answer (or the facts line when it gives none), problem why the owner
    must be asked (None when the gate answers it). pay: the advert's own pay text ("not stated" when it gives none);
    without it the salary question is not answered."""
    r = _gate(question, pay=pay)
    key = _key(r['basis'])
    entry = r['basis'][len('answers.' + key) + 1:] or None if key and r['basis'].startswith('answers.') else None
    value = r['answer'] if r['status'] == 'answered' else (fact_at(r['basis']) if r['basis'] else None)
    return {'key': key, 'entry': entry, 'value': value, 'problem': None if r['status'] == 'answered' else (r['why'] or 'no standing answer in facts.json -> answers'),
            'basis': r['basis'], 'answer': r['answer']}


def standing_answer(question, pay=None):
    """(key, problem) for one form question: the line of facts.json the gate reads (None when none) and why the
    owner must be asked (None when the gate gives an answer). pay as in resolve."""
    found = resolve(question, pay)
    return found['key'], found['problem']


def line_text(value):
    """A standing answer as one line of text: a rule with choose / never_choose is written out part by part."""
    if isinstance(value, dict):
        return ' '.join(f"{k.replace('_', ' ').capitalize()}: {line_text(v).rstrip('.')}." for k, v in value.items() if not k.startswith('_'))
    if isinstance(value, list):
        return '; '.join(line_text(v) for v in value)
    return str(value)


def standing_line(question, pay=None):
    """(basis, answer, problem): where in facts.json the gate's answer comes from ('answers.notice_period',
    'answers.years_of_experience.<row>', 'identity.location'), the answer to give with no options on screen, and
    why the owner must be asked instead (None when the gate answers it; the answer is then '' only when unanswered).
    pay as in resolve."""
    found = resolve(question, pay)
    return found['basis'], (found['answer'] if not found['problem'] else ''), found['problem']


def advert_pay(data):
    """The advert's pay text a draft, record, queue entry or candidate carries: advert_pay, the record's advert.pay,
    or a candidate's SEEK salary text. None when none is recorded (a candidate whose SEEK salary is empty may still
    state pay in the advert's text, so that is not "not stated")."""
    advert = data.get('advert') if isinstance(data.get('advert'), dict) else {}
    for value in (data.get('advert_pay'), advert.get('pay'), data.get('salary')):
        if isinstance(value, str) and value.strip():
            return value
    return None


def unanswered_questions(questions, pay=None):
    """[{question, why}] for the form questions with no settled standing answer, in order, each once. pay as in
    resolve."""
    out, seen = [], set()
    for question in questions or []:
        text = ' '.join(str(question or '').split())
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        _, problem = standing_answer(text, pay)
        if problem:
            out.append({'question': text, 'why': problem})
    return out


# ------------------------------------------------------------------------------------------- letters and emails
# One set of rules for every letter and email, used by `checks.py draft`, by queue.py (next, letter) and by
# letter_pdf.py, so what the queue hands out is what these checks pass.
GREETING = re.compile(r"^(?:(?:hello|hi|dear)\b[^\n,.!?;:]{0,40},|(?:hello|hi))$", re.I)
CLOSING = re.compile(r'^(kind regards|regards|best regards|warm regards|many thanks|thank you|thanks|yours sincerely|sincerely|yours faithfully),?$', re.I)


def _sign_off_line(line):
    """True for a line of the sign-off block: a closing, his name, his phone, email or portfolio address."""
    ident = FACTS['identity']
    name = ident['name'].split()
    names = {' '.join(name).lower(), f'{name[0]} {name[-1]}'.lower(), str(ident.get('short_name') or name[0]).lower()}
    low = ' '.join(line.lower().split()).rstrip(',.')
    url = ident['portfolio_url'].lower()
    digits = re.sub(r'\D', '', low)
    return (bool(CLOSING.match(low)) or low in names or low in (url, url.replace('https://', ''), ident['email'].lower())
            or (bool(digits) and digits == re.sub(r'\D', '', ident['phone']) and not re.search(r'[a-z]', low)))


def letter_blocks(text):
    """(greeting, paragraphs, sign_off) of a letter. A first line 'Hello,' or 'Hello <name>,' is the greeting and the
    closing, name, phone and link lines at the end are the sign-off: neither counts as a paragraph. The paragraphs
    are the blocks between blank lines, or the lines of a body that has no blank line."""
    lines = [line.rstrip() for line in str(text or '').strip().splitlines()]
    greeting = lines.pop(0).strip() if lines and GREETING.match(lines[0].strip()) else ''
    sign_off = []
    while lines and (not lines[-1].strip() or _sign_off_line(lines[-1])):
        line = lines.pop().strip()
        if line:
            sign_off.insert(0, line)
    body = '\n'.join(lines).strip()
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n' if re.search(r'\n\s*\n', body) else r'\n', body) if p.strip()]
    return greeting, paragraphs, sign_off


def compose_letter(cover_letter_text, relocation_line=''):
    """The letter as it is sent: cover_letter_text, with relocation_line at the end of the last paragraph (before
    the sign-off) when the text does not already carry it."""
    text, line = str(cover_letter_text or '').strip(), ' '.join(str(relocation_line or '').split())
    if not line or not text or ' '.join(text.split()).find(line.rstrip('.')) >= 0:
        return text
    greeting, paragraphs, sign_off = letter_blocks(text)
    if not paragraphs:
        return text
    paragraphs[-1] = paragraphs[-1].rstrip() + ' ' + line
    return '\n\n'.join(([greeting] if greeting else []) + paragraphs + (['\n'.join(sign_off)] if sign_off else []))


def _visa(visa_asked, allow):
    """The end date may be given when the advert asks, or when the entry allows a flagged visa-date phrase."""
    return bool(visa_asked) or any(VISA_FLAG.search(str(p)) for p in allow or [])


def letter_issues(text, visa_asked=False, tone=None, allow=()):
    """Everything wrong with one letter (cover_letter_text with its relocation line): config -> tone (word limit,
    banned phrases and characters, en and em dashes, volunteered limits, the visa end date however written), the
    facts, and its shape: exactly three paragraphs between an optional greeting line and the sign-off."""
    text = str(text or '')
    if not text.strip():
        return ['letter text missing']
    visa = _visa(visa_asked, allow)
    issues = ['letter ' + i for i in tone_issues(text, 'letter', visa, tone, allow) + fact_issues(text) + residency_issues(text)]
    _, paragraphs, _ = letter_blocks(text)
    if len(paragraphs) != 3:
        issues.append(f'letter has {len(paragraphs)} paragraphs (exactly three between the greeting line and the sign-off: config -> tone -> letter_shape)')
    return issues


def email_issues(subject, body, visa_asked=False, tone=None, allow=()):
    """Everything wrong with one email: the body against config -> tone and the facts, and the subject line."""
    visa = _visa(visa_asked, allow)
    body, subject = str(body or ''), str(subject or '')
    issues = ['email ' + i for i in tone_issues(body, 'email', visa, tone, allow) + fact_issues(body) + residency_issues(body)] if body.strip() else []
    return issues + ['email subject ' + i for i in tone_issues(subject, 'answer', visa, tone, allow) + residency_issues(subject)]


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


YEARS_QUESTION = re.compile(r"how many years|years'? (of )?experience|number of years", re.I)


def answer_issues(question, answer, advert_pay=''):
    """A written form answer against facts.json: a placeholder is not an answer, a yes must not claim what the
    question names and the facts do not have, a yes or no must not contradict the gate's answer, years and a
    salary figure must be the ones facts.json gives. advert_pay: the advert's own pay text; a figure in it may be
    given."""
    issues = []
    text = str(answer or '').strip()
    found = resolve(question, advert_pay or None)
    line = found['answer'] if not found['problem'] else ''
    key = found['key']
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
    plain = re.match(r'\W*(yes|no)\b(?! only)', line, re.I)
    if plain and said and plain.group(1).lower() != said:
        issues.append(f"says {said} where facts.json -> answers -> {key} says: {line[:80]}")
    short = line and not plain and key in ANSWERS and key != 'expected_salary' and len(line.split()) <= 3
    digits = lambda t: ' '.join(NUMBER_WORDS.get(w, w) for w in _words(t))
    if short and digits(line) not in digits(text):  # '2 weeks' is the answer; 'None, ready now' is not
        issues.append(f"does not give the standing answer in facts.json -> answers -> {key}: {line}")
    if (key == 'years_of_experience' or YEARS_QUESTION.search(str(question or ''))) and ' '.join(text.lower().split()) not in ' '.join(line.lower().split()):
        for m in YEARS_GIVEN.finditer(text):
            if m.group('word') or (float(m.group('n')) >= 1 and not m.group('lead')):
                issues.append(f'gives "{m.group(0).strip()}" where facts.json -> answers -> years_of_experience says: {line[:90] or "nothing for this question (it goes to the owner)"}')
                break
    band = salary_band()
    if key == 'expected_salary' and band:
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
    """Everything written in one draft against config -> tone and facts.json, with the rules of letter_issues and
    email_issues. The visa end date passes only when the draft carries advert_asks_about_visa true (or, in a form
    answer, the question asks); a queue entry's tone_allow lists the flagged phrases it may keep."""
    visa = draft.get('advert_asks_about_visa') is True
    allow = draft.get('tone_allow') or []
    email = draft.get('email') if isinstance(draft.get('email'), dict) else {}
    body = str(draft.get('email_body') or email.get('body') or '')
    issues = email_issues(draft.get('subject') or email.get('subject'), body, visa, allow=allow)
    letter = letter_text(draft)
    if letter.strip():
        issues += letter_issues(letter, visa, allow=allow)
    run_letter = draft.get('letter') or {}
    for name, line in (('letter subject', run_letter.get('subject')), ('letter greeting', run_letter.get('greeting')), ('letter closing', run_letter.get('closing'))):
        issues += [f'{name} {i}' for i in tone_issues(str(line or ''), 'answer', visa, allow=allow)]
    answers, unreadable = answer_items(draft)
    if unreadable:
        issues.append(unreadable)
    options = {' '.join(str(q.get('question') or '').split()): q.get('options') or [] for q in draft.get('questions') or [] if isinstance(q, dict)}
    for item in answers:
        question, answer = item['question'], item['answer']
        if not isinstance(answer, str) or not answer.strip():
            if answer not in (None, ''):
                issues.append(f'answer to "{question[:60]}" is not text ({type(answer).__name__})')
            continue
        if item['basis']:  # an answer taken from facts.json: it must be the gate's answer for this question and its options
            gated = _gate(question, options.get(question), advert_pay(draft))
            if fact_at(item['basis']) is None:
                issues.append(f'answer to "{question[:60]}" names a basis that is not in facts.json: {item["basis"]}')
            elif gated['status'] != 'answered':
                issues.append(f'answer to "{question[:60]}" has no standing answer in facts.json ({gated["why"]})')
            elif answer != gated['answer']:
                issues.append(f'answer to "{question[:60]}" contradicts facts.json -> {gated["basis"]}: the answer is "{gated["answer"][:80]}"')
            continue
        asked = visa or bool(VISA_QUESTION.search(question))
        truth = [i for i in fact_issues(answer) if not (i.startswith('amount not in facts') and SALARY_QUESTION.search(question))]  # a salary answer is a figure
        found = tone_issues(answer, 'answer', asked, allow=allow) + truth + answer_issues(question, answer, advert_pay(draft))
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
            basis, text, problem = standing_line(item['question'], advert_pay(rec))
            if item['basis'] and (problem or (item['basis'], item['answer']) != (basis, text)):
                issues.append(f'form answer is not the standing answer in facts.json -> answers: "{item["question"][:60]}"')
            elif not item['basis'] and status != STATUSES['ask_owner']:
                issues.append(f'{status} record carries a form answer that is not from facts.json -> answers: "{item["question"][:60]}"')
        if status != STATUSES['ask_owner']:
            issues += [f'{status} record has a form question with no standing answer (it must be ASK_OWNER): "{u["question"][:60]}"' for u in unanswered_questions(form_questions(rec), advert_pay(rec))]
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
    return issues + draft_issues({'email_body': rec.get('email_body'), 'subject': rec.get('subject'), 'screening_answers': rec.get('screening_answers'),
                                  'advert_asks_about_visa': visa, 'advert_pay': advert_pay(rec)})


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
        issues = ([unreadable] if unreadable else []) + [f"ask the owner: {u['question']} ({u['why']})" for u in unanswered_questions(form_questions(data), advert_pay(data))]
    else:
        issues = record_issues(read_json(a.file))
    for i in issues:
        print('- ' + i)
    print('OK' if not issues else f'{len(issues)} issue(s)')
    sys.exit(1 if issues else 0)


if __name__ == '__main__':
    main()
