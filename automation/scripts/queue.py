#!/usr/bin/env python3
"""The apply queue: one JSON file per job application, worked through by the submitters.

Open entries live in automation/queue/open/<id>.json; finished ones move to automation/queue/done/<YYYY-MM>/<id>.json.
One file per entry, so several runners pushing to the same branch rarely conflict.

Usage (global options --dir, --config, --facts, --prior and --now go before the command):
  queue.py add ENTRY.json [--by NAME] [--repeat-ok REASON]
  queue.py list [--route R] [--status S] [--all] [--json]
  queue.py show ID
  queue.py next --route R [--by NAME]
  queue.py mark ID applied --by NAME --kind K --ref REF [--at ISO]
  queue.py mark ID skipped --by NAME --reason TEXT
  queue.py mark ID failed --by NAME --note TEXT [--final]      (only when it is known that nothing was submitted)
  queue.py mark ID uncertain --by NAME --note TEXT           (unknown whether it went: held until someone checks)
  queue.py mark ID ask --by NAME --question TEXT
  queue.py mark ID open --by NAME [--note TEXT]
  queue.py answer ID [--question TEXT [--option O]... [--set ANSWER --basis FACTS.KEY --by NAME]]
  queue.py letter ID --file LETTER.txt [--subject TEXT] [--body-file EMAIL.txt] [--to ADDRESS] [--evidence-url URL]
                     [--allow PHRASE]...
  queue.py expire [--today YYYY-MM-DD]
  queue.py render
  queue.py stats [--json]
  queue.py check

Exit codes: 0 done; 1 refused (reason on stderr); 3 the day's cap or the SEEK spacing is reached; 4 nothing to hand out.

next never hands out an entry that is not OPEN, is past its closing date or stated closing time, has an unanswered
question, repeats a company and role already APPLIED, goes to an employer applied to in the last
limits.repeat_block_days (in the queue or in prior_outreach.json), has a twin for the same employer that a runner has
started or left uncertain, still carries a letter marked "rewrite before use", has letter or email text over the word
limits or with a flagged phrase of config -> tone, has no email text or no evidence_url (EMAIL route), or was started
by a runner that recorded no result. With --by it records the start, so finish every entry it hands out with a mark.

Two optional fields beyond the standard ones: repeat_ok (why this entry may go although the employer or the same
company and role is already in the queue or applied to; set by add --repeat-ok) and tone_allow (flagged phrases the
letter or email may keep; set by letter --allow).

This file has the same name as the standard library's "queue" module and sits first on sys.path when a script in
this folder runs. It therefore re-exports the standard module's names (see just below); import it from other code as
"import queue as apply_queue" with this folder first on sys.path.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import sysconfig
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _stdlib_queue():
    """The real standard-library queue module, loaded by path because this file shadows its name."""
    mod = sys.modules.get('_stdlib_queue')
    if mod is None:
        spec = importlib.util.spec_from_file_location('_stdlib_queue', os.path.join(sysconfig.get_path('stdlib'), 'queue.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules['_stdlib_queue'] = mod
        spec.loader.exec_module(mod)
    return mod


try:
    for _name in _stdlib_queue().__all__:  # Queue, Empty, Full ... for standard-library code that does "import queue"
        globals()[_name] = getattr(_stdlib_queue(), _name)
except Exception:  # pragma: no cover - a Python whose library is not on disk as .py files
    sys.modules.pop('_stdlib_queue', None)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = ROOT / 'queue'
LANES = ('drafter', 'technician', 'engineer')
ROUTES = ('SEEK', 'EMAIL', 'EMPLOYER_PORTAL', 'EMPLOYER_FORM')
STATUSES = ('OPEN', 'ASK_OWNER', 'APPLIED', 'SKIPPED', 'EXPIRED', 'FAILED')
OPEN_STATUSES = ('OPEN', 'ASK_OWNER')
CLOSES_SOURCES = ('advert', 'listing_expiry', 'none')
RECEIPT_KINDS = ('seek_receipt_email', 'seek_confirmation_screen', 'gmail_message_id', 'portal_confirmation')
CAP_KEY = {'SEEK': 'seek_submissions_per_day', 'EMAIL': 'email_sends_per_day',
           'EMPLOYER_PORTAL': 'portal_submissions_per_day', 'EMPLOYER_FORM': 'portal_submissions_per_day'}
REWRITE_MARK = 'rewrite before use'
REPEAT_BLOCK_DAYS = 90  # used when config.json -> limits -> repeat_block_days is not set
COMPANY_NOISE = re.compile(r'\([^)]*\)|\b(?:pty|ltd|limited|plc|inc|co|group|holdings|australia|aust|the|and)\b|&', re.I)
PHONE = re.compile(r'(?<![\w/=.-])(?:\+?61[\s-]?\(?0?|\(?0)[2-478]\)?(?:[\s-]?\d){8}(?!\d)'   # mobile or landline with area code
                   r'|(?<![\w/=.-])1[38]00(?:[\s-]?\d){6}(?!\d)')                                # 1300 and 1800 numbers
FIELDS = ('id', 'lane', 'route', 'company', 'role', 'location', 'url', 'seek_id', 'listed_at', 'closes_at', 'closes_source',
          'fit', 'resume_variant', 'relocation_line', 'cover_letter_text', 'email', 'questions', 'status', 'ask_owner',
          'attempts', 'receipt', 'created_by', 'created_at', 'source_run', 'notes')


class Refused(Exception):
    code = 1


class CapReached(Refused):
    code = 3


class NothingToDo(Refused):
    code = 4


# ---------- small helpers ----------

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as err:  # a missing file, or one left broken by a merge conflict
        raise Refused(f'{path}: cannot be read as JSON ({err})')


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s or '').lower()).strip('-')


def _melbourne():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Australia/Melbourne')
    except Exception:  # pragma: no cover - no time zone data on this machine
        return timezone(timedelta(hours=10))


def parse_time(s):
    """ISO date or date-time to an aware datetime. A value with no offset is Melbourne time."""
    try:
        dt = datetime.fromisoformat(str(s).strip().replace('Z', '+00:00'))
    except ValueError:
        raise Refused(f'not a date or time: {s} (use 2026-11-13 or 2026-11-13T10:05:00+11:00)')
    return dt if dt.tzinfo else dt.replace(tzinfo=_melbourne())


def iso(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def melbourne_date(x):
    """YYYY-MM-DD in Melbourne for a datetime or an ISO string."""
    return (x if isinstance(x, datetime) else parse_time(x)).astimezone(_melbourne()).strftime('%Y-%m-%d')


def norm_url(u):
    u = str(u or '').strip().lower()
    m = re.search(r'seek\.com(?:\.au)?/job/(\d+)', u)
    if m:
        return 'seek:' + m.group(1)
    return re.sub(r'^https?://(www\.)?', '', re.sub(r'#.*$', '', u)).rstrip('/')


def company_key(name):
    """An employer name without its legal and filler words: 'Fyfe Pty Ltd' and 'Fyfe' are the same (as in tracker.py)."""
    return slug(COMPANY_NOISE.sub(' ', str(name or '')))


def same_employer(a, b):
    """True when two company names are one employer: the same key, one key is the other plus more words ('Fortec' and
    'Fortec Civil'), or one is the trading name the other gives in brackets ('AGT Operations Pty Ltd (Australian
    Ground Technologies)' and 'Australian Ground Technologies')."""
    ka, kb = company_key(a), company_key(b)
    in_brackets = lambda name: {company_key(x) for x in re.findall(r'\(([^)]*)\)', str(name or ''))} - {''}
    if not ka or not kb:
        return False
    return ka == kb or (min(len(ka), len(kb)) >= 6 and (ka.startswith(kb + '-') or kb.startswith(ka + '-'))) or ka in in_brackets(b) or kb in in_brackets(a)


def job_key(e):
    """Company and role, loosely: 'Fyfe Pty Ltd' and 'Fyfe' are the same employer."""
    return company_key(e.get('company')) + '|' + slug(e.get('role'))


def closed(e, now):
    """True once the entry's closing date (the whole Melbourne day) or its stated closing time has passed."""
    c = str(e.get('closes_at') or '').strip()
    if not c:
        return False
    return parse_time(c) < now if len(c) > 10 else c < melbourne_date(now)


def closes_text(e):
    """The closing date, with the time when the advert states one, for people to read."""
    return e['closes_at'][:16].replace('T', ' ')


def make_id(e):
    """Stable id: seek-<seek_id>, or company and role plus a short hash of the url."""
    if e.get('seek_id'):
        return f"seek-{e['seek_id']}"
    h = hashlib.sha1(norm_url(e.get('url')).encode('utf-8')).hexdigest()[:8]
    return f"{slug(e.get('company'))[:30].strip('-')}-{slug(e.get('role'))[:40].strip('-')}-{h}"


def fact_at(facts, path):
    """The value at a dotted facts.json path such as 'answers.notice_period'; None when there is none."""
    node, rest = facts, str(path or '')
    while rest:
        if not isinstance(node, dict):
            return None
        key = next((k for k in sorted(node, key=len, reverse=True) if rest == k or rest.startswith(k + '.')), None)
        if key is None:
            return None
        node, rest = node[key], rest[len(key) + 1:]
    return node


# ---------- standing answers for form questions ----------

def _plain(value):
    """A fact usable as an answer; '' when the fact itself says it is not known."""
    v = str(value or '').strip()
    return '' if re.match(r'not (on record|confirmed)', v, re.I) else v


def _yes_no(value, opts):
    v = _plain(value)
    head = 'Yes' if re.match(r'yes\b', v, re.I) else 'No' if re.match(r'no\b', v, re.I) else ''
    if not head or not opts:
        return head
    hits = [o for o in opts if re.match(head + r'\b', o, re.I)]
    return hits[0] if len(hits) == 1 else ''


def _same(value, opts):
    v = _plain(value)
    if not v or not opts:
        return v
    hits = [o for o in opts if slug(o) == slug(v)]
    return hits[0] if len(hits) == 1 else ''


# Words that may stand before a role he has held without changing what is asked ("Assistant Civil Engineer").
ROLE_PREFIXES = ('civil', 'junior', 'graduate', 'assistant', 'construction', 'site', 'project')
# The few ways a listed "Do you have experience ...?" question leads into the activity it names.
LEAD_INS = ('working on ', 'carrying out ', 'in ', 'with ')


def _under_one_year(opts):
    return [o for o in opts if re.match(r'(less than|under|<)\s*(1|one)\s*year|0\s*(-|to)\s*1\s*years?$', o.strip(), re.I)]


def _right_to_work(m, opts, a, facts):
    rule, basis = (a.get('right_to_work') or {}).get('choose'), 'answers.right_to_work.choose'
    if not rule or not opts:
        return rule or '', basis
    allowed = [o for o in opts if not re.search(r'citizen|permanent resident|sponsor', o, re.I)]
    graduate = [o for o in allowed if re.search(r'graduate temporary|\b485\b', o, re.I)]
    free = [o for o in allowed if re.search(r'temporary visa', o, re.I)
            and re.search(r'no restrictions?|without restrictions?|unrestricted', o, re.I)]
    pick = graduate if graduate else free
    return (pick[0] if len(pick) == 1 else ''), basis


def _years(m, opts, a, facts):
    years = {k: v for k, v in (a.get('years_of_experience') or {}).items() if k != 'rule'}
    is_role = bool(m.re.groupindex.get('role'))
    x, hits, near = re.sub(r'^the ', '', ' '.join(m.group('x').lower().split())), {}, False
    for key, value in years.items():
        worked = '11 months' in value   # a role he has held: the answer claims months of work
        for part in (p.strip() for p in key.lower().split(',') if p.strip()):
            if not re.search(r'\b' + re.escape(part) + r'\b', x):
                continue
            near = True
            plain = x == part or (is_role and x.endswith(' ' + part) and all(w in ROLE_PREFIXES for w in x[:-len(part)].split()))
            if worked and not plain:
                # Months of work are claimed only for the named role itself, alone or after a plain prefix ("Civil
                # Site Engineer"). Any other word ("... in Australia", "Senior ...", "Rail ...") asks something else.
                return '', ''
            if plain or (is_role and not worked):   # a lowest-option answer cannot overstate: the role anywhere in a title
                hits[key] = value
    held = {w for job in facts.get('experience') or [] for w in re.findall(r'[a-z]{5,}', str(job.get('role') or '').lower())}
    if not near and is_role and not held & set(re.findall(r'[a-z]{5,}', x)):
        # "any other role" is a standing answer too, but not for a title that shares a word with a job he has held
        hits = {k: v for k, v in years.items() if 'any other role' in k.lower()}
    kinds = {'11 months' if '11 months' in v else 'lowest' if 'lowest option' in v else 'other' for v in hits.values()}
    if len(kinds) != 1:
        return '', ''
    key, value = next(iter(hits.items()))
    basis = 'answers.years_of_experience.' + key
    if not opts:
        return value, basis
    under, none = _under_one_year(opts), [o for o in opts if re.match(r'(no experience|none|no|0( years?)?)$', o.strip(), re.I)]
    pick = under if kinds == {'11 months'} else (none or under) if kinds == {'lowest'} else []
    return (pick[0] if len(pick) == 1 else ''), basis


def _salary(m, opts, a, facts):
    s = a.get('expected_salary') or {}
    if not s.get('rule'):
        return '', 'answers.expected_salary.rule'
    single = re.match(r'[\d,]+', str(s.get('single_figure_when_no_pay_stated') or ''))
    return s['rule'] + (f' Single figure when the advert states no pay: {single.group(0)}.' if single else ''), 'answers.expected_salary.rule'


def _licence(m, opts, a, facts):
    if re.search(r'full|probation|provisional|manual|automatic|learner|p[- ]?plate|open licen', ' '.join([m.string] + opts), re.I):
        return '', 'answers.drivers_licence'
    return _yes_no(a.get('drivers_licence'), opts), 'answers.drivers_licence'


def _qualification(m, opts, a, facts):
    known, x, other = a.get('qualification_questions') or {}, ' '.join(m.group('x').lower().split()), 'any other named qualification'
    parts = [p.strip() for p in x.split('/') if p.strip()]
    key = x if x in known and x != other else None   # a field facts.json answers by name
    if parts and all(p in ('engineering drafting', 'engineering design') for p in parts):
        key = 'engineering drafting or design'
    if key:
        return _yes_no(known.get(key), opts), 'answers.qualification_questions.' + key
    if other not in known:
        return '', ''
    held = [str(e.get('qualification') or '').lower() for e in facts.get('education') or []]
    words = lambda text: set(re.findall(r'[a-z]{4,}', text))
    if len(x.split()) > 1 and any(re.search(r'\b' + re.escape(x) + r'\b', h) for h in held):
        answer = 'Yes'   # the field is named, whole, in the title of a qualification he holds
    elif words(x) and not words(x) & words(' '.join(held)):
        answer = 'No'    # nothing he holds shares a word with it
    else:
        answer = ''      # a field that shares a word with his own ("science", "construction management"): not guessed
    return _yes_no(answer, opts), 'answers.qualification_questions.' + other


def _experience(m, opts, a, facts):
    # The question must name exactly one of the activities in facts.json, alone: "3+ years of ...", "... on civil
    # infrastructure projects" or "... in Procore" ask something else.
    x = ' '.join(m.group('x').lower().split())
    asked = {x.rstrip('s')} | {x[len(lead):].rstrip('s') for lead in LEAD_INS if x.startswith(lead)}
    for key, value in (a.get('experience_yes_no') or {}).items():
        if key != 'anything else' and asked & {p.strip().lower().rstrip('s') for p in key.split(',') if p.strip()}:
            return _yes_no(value, opts), 'answers.experience_yes_no.' + key
    return '', ''  # "anything else" needs a reading of his history: not decided here


def _which(m, opts, a, facts):
    x, software = ' '.join(m.group('x').lower().split()), a.get('software') or {}
    key = {'cad software': 'CAD', 'microsoft office products': 'Microsoft Office'}.get(x)
    value = str(software.get(key) or '') if key else ''
    if ' only' not in value:  # no approved list to tick from (Microsoft Office products are not confirmed)
        return '', ('answers.software.' + key) if key else ''
    if not opts:
        return value, 'answers.software.' + key
    names = {n.strip().lower() for n in re.split(r',|\band\b', value.split(' only')[0]) if n.strip()}
    def named(o):
        o = re.sub(r'^autodesk\s+', '', o.strip().lower())
        return o in names or (o.startswith('autocad ') and o[8:] in names)
    return '; '.join(o for o in opts if named(o)), 'answers.software.' + key


def _fact(key, how):
    return lambda m, opts, a, facts: (how(a.get(key), opts), 'answers.' + key)


# Only the common SEEK questions. Anything else comes back unanswered, never guessed.
PATTERNS = [(re.compile(p + r'\??'), h) for p, h in (
    (r'which of the following statements best describes your right to work in australia', _right_to_work),
    (r"how many years'? experience do you have as an? (?P<role>(?P<x>.+?))", _years),
    (r"how many years'? experience do you have (?:in|with) (?P<x>.+?)", _years),
    (r'how much notice are you required to give your current employer', _fact('notice_period', _same)),
    (r"what(?:'s| is) your expected annual base salary", _salary),
    (r"do you have a current australian driver'?s licen[cs]e", _licence),
    (r'have you completed a qualification in (?P<x>.+?)', _qualification),
    (r'do you have experience (?P<x>.+?)', _experience),
    (r'do you have (?P<x>.+?) experience', _experience),
    (r'which of the following (?P<x>.+?) (?:do you have experience with|are you experienced with)', _which),
    (r'do you hold a construction induction safety certificate \(white card\)', _fact('white_card', _yes_no)),
    (r'are you willing to undergo a pre-employment medical check', _fact('pre_employment_medical', _yes_no)),
    (r'do you have a current police check \(national police certificate\) for employment', _fact('police_check', _yes_no)),
    (r'do you own or have regular access to a car', _fact('own_car_or_regular_access', _yes_no)),
    (r'are you willing to undergo pre-employment drug and alcohol screening', _fact('drug_and_alcohol_screening', _yes_no)),
    (r'how would you rate your english language skills', _fact('english_self_rating', _same)),
    (r'are you currently studying', _fact('currently_studying', _yes_no)),
)]


def _question(text):
    return ' '.join(str(text or '').replace('’', "'").lower().split())


def answer_question(question_text, options, facts):
    """The standing answer to one form question, taken only from facts['answers'].

    Returns {'answer', 'basis', 'status'}: status is 'answered' or 'unanswered', basis is the facts.json key used.
    With the form's options the answer is one of them, word for word (several joined by '; ' for a tick list); with no
    options it is the approved answer or rule for the submitter to apply on screen. The salary question always gets
    the rule, because the band depends on the pay the advert states. Pure: no files, no clock.
    """
    a = (facts or {}).get('answers') or {}
    q = _question(question_text)
    opts = [str(o).strip() for o in (options or []) if str(o).strip()]
    for pattern, handler in PATTERNS:
        m = pattern.fullmatch(q)
        if m:
            answer, basis = handler(m, opts, a, facts or {})
            return {'answer': answer or '', 'basis': basis, 'status': 'answered' if answer else 'unanswered'}
    return {'answer': '', 'basis': '', 'status': 'unanswered'}


def standing(question_text):
    """True for one of the listed questions: PATTERNS and facts.json decide its answer, never a runner."""
    q = _question(question_text)
    return any(pattern.fullmatch(q) for pattern, _ in PATTERNS)


NEVER_CHOOSE = re.compile(r'citizen|permanent resident|(?<!\bno )sponsor', re.I)
WORK_RIGHTS = re.compile(r'citizen|resident|residency|visa|sponsor|rights? to work|work(?:ing)? rights|(?:entitled|eligible|allowed) to work', re.I)


def set_problem(question, answer, basis, facts):
    """Why a runner may not give this answer on this basis ('' when it may). The answer must be the fact itself."""
    value = fact_at(facts, basis)
    values = value if isinstance(value, list) else [value]
    if not basis or value in (None, [], '') or any(isinstance(v, (dict, list)) or v is None for v in values):
        return 'the basis must name one value in facts.json (for example identity.location), not a missing key or a whole block'
    if standing(question):
        return 'this is one of the listed questions: its standing answer in facts.json -> answers governs and cannot be set by hand'
    if NEVER_CHOOSE.search(answer):
        return 'facts.json -> answers.right_to_work.never_choose: never citizen, permanent resident or sponsorship'
    if WORK_RIGHTS.search(question) and not re.match(r'answers\.right_to_work\.|eligibility\.work_rights', basis):
        return 'a work-rights question needs a basis under answers.right_to_work or eligibility.work_rights'
    want = slug(answer)
    for v in (_plain(v) for v in values):   # '' when the fact itself says not confirmed or not on record
        head = _yes_no(v, [])
        if want and v and (want == slug(v) or want == slug(head) or (basis.startswith('identity.') and f'-{want}-' in f'-{slug(v)}-')):
            return ''
    return ('the answer is not the value at that key: it must be the same text, a plain Yes or No that the value starts '
            'with, or part of an identity value such as the suburb')


def unanswered(e):
    return [q for q in e.get('questions') or [] if q.get('status') != 'answered' and q.get('mandatory', True)]


def question_ask(e):
    """The one-line owner question for an entry's unanswered form questions ('' when there are none)."""
    qs = [q['question'] + (f" (options: {' / '.join(q['options'])})" if q.get('options') else '') for q in unanswered(e)]
    if not qs:
        return ''
    head = 'No standing answer for this form question: ' if len(qs) == 1 else f'No standing answer for {len(qs)} form questions: '
    return head + ' | '.join(' '.join(q.split()) for q in qs)


def owner_line(e):
    """Everything the owner is asked about an entry, on one line: its ask_owner, then any form question still open."""
    ask, questions = ' '.join(str(e.get('ask_owner') or '').split()), question_ask(e)
    return ask if not questions or questions in ask else (ask + ' Also: ' + questions if ask else questions)


def apply_answers(e, facts, before=None):
    """Recompute every question from facts and move the entry between OPEN and ASK_OWNER to match.

    An answer a named runner set with a facts key (it has 'by') is kept while it still stands: the question is not one
    of the listed ones and the answer is still the value at its basis. An ASK_OWNER put there for another reason stays.
    before is the entry's question line as it was before the caller changed its questions.
    """
    before = question_ask(e) if before is None else before
    for q in e['questions']:
        if not q.get('by') or set_problem(q.get('question'), str(q.get('answer') or ''), str(q.get('basis') or ''), facts):
            q.pop('by', None)
            q.update(answer_question(q.get('question'), q.get('options'), facts))
    after = question_ask(e)
    ours = e['status'] == 'ASK_OWNER' and bool(before) and e['ask_owner'] == before
    if after and (e['status'] == 'OPEN' or ours):
        e['status'], e['ask_owner'] = 'ASK_OWNER', after
    elif not after and ours:
        e['status'], e['ask_owner'] = 'OPEN', ''
    return e


# ---------- entries ----------

def fill(entry):
    """A copy of the entry with every field present, in the standard order."""
    e = json.loads(json.dumps(entry))
    e['seek_id'] = str(e.get('seek_id') or '').strip()
    defaults = {'location': '', 'listed_at': '', 'closes_at': '', 'closes_source': 'none', 'fit': None,
                'resume_variant': e.get('lane'), 'relocation_line': '', 'cover_letter_text': '', 'questions': [],
                'status': 'OPEN', 'ask_owner': '', 'attempts': [], 'receipt': {}, 'created_by': '', 'created_at': '',
                'source_run': '', 'notes': ''}
    for k, v in defaults.items():
        if e.get(k) is None and k != 'fit':
            e[k] = v
    e.setdefault('fit', None)
    e['email'] = {k: str((e.get('email') or {}).get(k) or '') for k in ('to', 'subject', 'body', 'evidence_url')}
    questions = [{'question': q} if isinstance(q, str) else q for q in e['questions']]
    e['questions'] = [{'question': ' '.join(str(q.get('question') or '').split()), 'options': list(q.get('options') or []),
                       'answer': q.get('answer') or '', 'basis': q.get('basis') or '', 'status': q.get('status') or 'unanswered',
                       **{k: q[k] for k in ('by', 'mandatory') if k in q}} for q in questions]
    if not e.get('id'):
        e['id'] = make_id(e)
    return {**{k: e.get(k) for k in FIELDS}, **{k: v for k, v in sorted(e.items()) if k not in FIELDS}}


def privacy_problems(e, facts=None):
    """Things a public queue file must not hold: another phone number, a licence number, a date of birth.

    Pattern checks, not proof. The phone check needs facts (to know his own number) and is skipped without them.
    """
    def strings(x):
        if isinstance(x, dict):
            x = list(x.values())
        return [x] if isinstance(x, str) else [s for v in x for s in strings(v)] if isinstance(x, list) else []
    text = '\n'.join(strings(e))
    own = re.sub(r'\D', '', str(((facts or {}).get('identity') or {}).get('phone') or ''))
    problems = []
    for p in [] if facts is None else dict.fromkeys(PHONE.findall(text)):
        digits = re.sub(r'^61', '0', re.sub(r'\D', '', p))
        if digits != own:
            problems.append(f'privacy: phone number {p.strip()} (only the one in facts.json identity may appear)')
    if re.search(r'licen[cs]e\s*(?:no\.?|number|#)\s*:?\s*[A-Z0-9]{5,}', text, re.I):
        problems.append('privacy: a licence number')
    if re.search(r'\b(?:date of birth|d\.?o\.?b\.?|born)\b\W{0,5}(?:on\s+)?\d', text, re.I):
        problems.append('privacy: a date of birth')
    return problems


def validate(e, facts=None):
    """List of problems with an entry (empty when it is sound)."""
    p = []

    def need(ok, msg):
        if not ok:
            p.append(msg)

    def is_date(v):
        try:
            parse_time(v)
        except Refused:
            return False
        return bool(re.match(r'\d{4}-\d{2}-\d{2}', str(v)))
    need(re.fullmatch(r'[a-z0-9][a-z0-9-]{2,90}', str(e.get('id') or '')), 'id: lower-case letters, digits and hyphens only')
    need(e.get('lane') in LANES, f'lane: one of {", ".join(LANES)}')
    need(e.get('route') in ROUTES, f'route: one of {", ".join(ROUTES)}')
    need(e.get('resume_variant') in LANES, f'resume_variant: one of {", ".join(LANES)}')
    for k in ('company', 'role'):
        need(str(e.get(k) or '').strip(), f'{k}: missing')
    need(re.match(r'https?://', str(e.get('url') or '')), 'url: missing or not a web address')
    need(re.fullmatch(r'\d*', str(e.get('seek_id') or '')), 'seek_id: digits only')
    need(e.get('route') != 'SEEK' or e.get('seek_id'), 'seek_id: the SEEK route needs the SEEK job number')
    for k in ('listed_at', 'closes_at'):
        need(not e.get(k) or is_date(e[k]), f'{k}: YYYY-MM-DD' + (', or YYYY-MM-DDThh:mm when the advert states a closing time' if k == 'closes_at' else ''))
    need(e.get('closes_source') in CLOSES_SOURCES, f'closes_source: one of {", ".join(CLOSES_SOURCES)}')
    need(bool(e.get('closes_at')) == (e.get('closes_source') in ('advert', 'listing_expiry')),
         'closes_at and closes_source disagree (a date needs advert or listing_expiry; no date needs none)')
    need(e.get('fit') is None or (isinstance(e['fit'], (int, float)) and 0 <= e['fit'] <= 100), 'fit: a percentage or null')
    need(e.get('status') in STATUSES, f'status: one of {", ".join(STATUSES)}')
    ask = str(e.get('ask_owner') or '')
    need(e.get('status') != 'ASK_OWNER' or ask.strip(), 'ask_owner: ASK_OWNER needs its one-line question')
    need('\n' not in ask, 'ask_owner: one line only')
    email = e.get('email') or {}
    if e.get('route') == 'EMAIL':
        need(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email.get('to') or ''), 'email.to: the EMAIL route needs the address')
        # an entry with no evidence_url may be stored, but next holds it back until the address has a source
        need(not email.get('evidence_url') or re.match(r'https?://', email['evidence_url']), 'email.evidence_url: the page where the employer publishes the address')
    for q in e.get('questions') or []:
        need(q.get('question'), 'questions: a question has no text')
        need(q.get('status') in ('answered', 'unanswered'), 'questions: status is answered or unanswered')
        need(q.get('status') != 'answered' or q.get('answer'), f"questions: answered but empty: {q.get('question')}")
        why = set_problem(q.get('question'), str(q.get('answer') or ''), str(q.get('basis') or ''), facts) if q.get('by') and facts is not None else ''
        need(not why, f"questions: the answer {q.get('by')} set does not stand ({why}): {q.get('question')}")
    for a in e.get('attempts') or []:
        need(a.get('at') and a.get('by') and a.get('result'), 'attempts: each needs at, by and result')
    if e.get('status') == 'APPLIED':
        r = e.get('receipt') or {}
        need(r.get('at') and r.get('by') and r.get('ref'), 'receipt: APPLIED needs at, by and ref')
        need(r.get('kind') in RECEIPT_KINDS, f'receipt.kind: one of {", ".join(RECEIPT_KINDS)}')
    return p + privacy_problems(e, facts)


# ---------- storage ----------

def load(qdir=QUEUE_DIR):
    """Every entry as (path, entry): open ones first, then done."""
    qdir = Path(qdir)
    paths = sorted((qdir / 'open').glob('*.json')) + sorted((qdir / 'done').glob('*/*.json'))
    return [(p, fill(read_json(p))) for p in paths]


def find(qdir, entry_id, open_only=False):
    for path, e in load(qdir):
        if e['id'] == entry_id:
            if open_only and e['status'] not in OPEN_STATUSES:
                raise Refused(f"{entry_id} is already {e['status']}")
            return path, e
    raise Refused(f'no queue entry with id {entry_id}')


def save(qdir, e, old_path=None, finished_at=None):
    """Write an entry where its status says it belongs; remove the old file when it moved."""
    qdir = Path(qdir)
    if e['status'] in OPEN_STATUSES:
        path = qdir / 'open' / f"{e['id']}.json"
    else:
        path = qdir / 'done' / melbourne_date(finished_at or datetime.now(timezone.utc))[:7] / f"{e['id']}.json"
    write_json(path, fill(e))
    if old_path and Path(old_path) != path and Path(old_path).exists():
        Path(old_path).unlink()
    return path


def add(entry, qdir=QUEUE_DIR, facts=None, now=None, by=None, config=None, prior=None):
    """Validate and store a new entry.

    Refuses a duplicate id, SEEK job or url, whether open or done. An entry to be worked (OPEN or ASK_OWNER) is also
    refused when the same company and role is already open or applied for, or the employer was applied to within
    limits.repeat_block_days, in the queue or in prior (the entries of prior_outreach.json), unless the entry carries
    repeat_ok with the reason.
    """
    now = now or datetime.now(timezone.utc)
    e = dict(entry)
    e['created_at'] = e.get('created_at') or iso(now)
    e['created_by'] = e.get('created_by') or by or ''
    e = fill(e)
    if facts is not None:
        apply_answers(e, facts)
    problems = validate(e, facts)
    if problems:
        raise Refused('not added: ' + '; '.join(problems))
    if e['route'] == 'EMAIL' and e['status'] in OPEN_STATUSES and not e['email']['evidence_url']:
        raise Refused('not added: email.evidence_url: the page where the employer publishes the address')
    keys = lambda x: {'id:' + x['id'], norm_url(x.get('url'))} | ({'seek:' + x['seek_id']} if x.get('seek_id') else set())
    others = [other for _, other in load(qdir)]
    for other in others:
        same = keys(e) & keys(other)
        if same:
            raise Refused(f"not added: duplicate of {other['id']} ({other['status']}): same {', '.join(sorted(same))}")
    if e['status'] in OPEN_STATUSES and not e.get('repeat_ok'):
        twin = next((o for o in others if o['status'] in OPEN_STATUSES and job_key(o) == job_key(e)), None)
        why = (f"same company and role as {twin['id']} ({twin['status']}, {twin['route']})" if twin
               else repeat_reason(e, applications(others, prior), melbourne_date(now), repeat_days(config)))
        if why:
            raise Refused(f'not added: {why}. If this really is another job, add it with --repeat-ok REASON')
    save(qdir, e, finished_at=parse_time(e['receipt']['at']) if e['receipt'].get('at') else now)
    return e


# ---------- handing out and recording ----------

def lane_rank(e, config):
    lane = ((config or {}).get('lanes') or {}).get(e['lane']) or {}
    return lane.get('rank') or LANES.index(e['lane']) + 1


def sort_key(e, config):
    """Lane rank, then a real (advert-stated) closing date soonest, then listed date newest."""
    c = e['closes_at']
    try:   # a bare date means the end of that day
        real_close = iso(parse_time(c if len(c) > 10 else c + 'T23:59:59')) if c and e['closes_source'] == 'advert' else '9999-12-31'
    except Refused:
        real_close = c
    listed = int(e['listed_at'][:10].replace('-', '')) if e['listed_at'] else 0
    return (lane_rank(e, config), real_close, -listed, e['id'])


def repeat_days(config):
    return ((config or {}).get('limits') or {}).get('repeat_block_days') or REPEAT_BLOCK_DAYS


def applications(entries, prior=None):
    """Every application on record as (company, job key, Melbourne date, where it is recorded): the queue's APPLIED
    entries, and prior, the entries of prior_outreach.json (applications made outside the queue)."""
    rows = [(e['company'], job_key(e), melbourne_date(e['receipt']['at']) if e['receipt'].get('at') else '', e['id'])
            for e in entries if e['status'] == 'APPLIED']
    return rows + [(str(p.get('company') or ''), '', str(p.get('date') or '')[:10], 'prior_outreach.json') for p in prior or []]


def repeat_reason(e, applied, today, days):
    """Why applying for this entry would repeat an application ('' when it would not, or the entry carries repeat_ok)."""
    if e.get('repeat_ok'):
        return ''
    cutoff = (datetime.fromisoformat(today) - timedelta(days=days)).strftime('%Y-%m-%d')
    same_job = [where for _, key, _, where in applied if key == job_key(e) and where != e['id']]
    if same_job:
        return f'already applied for this company and role ({same_job[0]})'
    for other, _, when, where in applied:
        if where != e['id'] and same_employer(other, e['company']) and (not when or when >= cutoff):
            return f"applied to this employer on {when or 'an unknown date'} ({where}): no repeat within {days} days"
    return ''


def tone_problems(e, config):
    """Where the letter, or the email body on the EMAIL route, breaks config -> tone: over the word limit, or a phrase
    from no_volunteered_limits.flag_patterns that the entry does not list under tone_allow."""
    tone = (config or {}).get('tone') or {}
    allowed = [str(x).lower() for x in e.get('tone_allow') or []]
    flags = [f.lower() for f in (tone.get('no_volunteered_limits') or {}).get('flag_patterns') or [] if f.lower() not in allowed]
    texts = [('letter', e['cover_letter_text'], tone.get('max_cover_letter_words'))]
    if e['route'] == 'EMAIL':
        texts.append(('email', e['email']['body'], tone.get('max_email_words')))
    problems = []
    for name, text, limit in texts:
        count = len(re.findall(r"[A-Za-z0-9'’]+", text))   # counted as checks.py counts
        if limit and count > limit:
            problems.append(f'{name} is {count} words (limit {limit})')
        said = [f for f in flags if f in text.lower()]
        if said:
            problems.append(f'{name} says "{said[0]}"')
    return problems


def hold_context(entries, config, now, prior=None):
    """What blockers needs besides the entry: the time, the rules, the applications on record, the entries under way."""
    busy = []
    for e in entries:
        last = e['attempts'][-1] if e['attempts'] else {}
        if e['status'] in OPEN_STATUSES and last.get('result') in ('started', 'uncertain'):
            busy.append((e['company'], e['id'], f"started by {last.get('by')}" if last['result'] == 'started' else 'unresolved'))
    return {'now': now, 'config': config, 'days': repeat_days(config), 'applied': applications(entries, prior), 'busy': busy}


def blockers(e, ctx):
    """Why next will not hand this entry out (empty when it is ready). ctx comes from hold_context."""
    b = []
    if e['status'] != 'OPEN':
        b.append('status ' + e['status'])
    try:
        if closed(e, ctx['now']):
            b.append('closing date has passed')
    except Refused:
        b.append('closes_at is not a date')
    if unanswered(e):
        b.append('unanswered question')
    repeat = repeat_reason(e, ctx['applied'], melbourne_date(ctx['now']), ctx['days'])
    if repeat:
        b.append(repeat)
    b += [f'{other} for the same employer is {state}: settle it first' for company, other, state in ctx['busy']
          if other != e['id'] and same_employer(company, e['company'])]
    if REWRITE_MARK in e['notes']:
        b.append('letter to rewrite')
    else:
        b += tone_problems(e, ctx['config'])
    if e['route'] == 'EMAIL':
        if not (e['email']['to'] and e['email']['subject'] and e['email']['body']):
            b.append('email text missing')
        if not e['email']['evidence_url']:
            b.append('email address has no evidence_url')
    if e['attempts'] and e['attempts'][-1].get('result') == 'started':
        b.append(f"started by {e['attempts'][-1].get('by')}, no result recorded")
    return b


def check_caps(route, entries, config, now):
    """Raise CapReached when the day's cap for this route, or the SEEK spacing, is already used up."""
    limits = (config or {}).get('limits') or {}
    cap = limits.get(CAP_KEY[route])
    if not isinstance(cap, int):
        raise Refused(f'config.json -> limits -> {CAP_KEY[route]} is not set')
    group = [r for r in ROUTES if CAP_KEY[r] == CAP_KEY[route]]
    times = [parse_time(e['receipt']['at']) for _, e in entries
             if e['status'] == 'APPLIED' and e['route'] in group and e['receipt'].get('at')]
    today = melbourne_date(now)
    done = sum(1 for t in times if melbourne_date(t) == today)
    if done >= cap:
        raise CapReached(f"{route}: the day's cap is reached ({done} of {cap} submitted on {today}, Melbourne date). Stop until tomorrow.")
    gap = limits.get('min_minutes_between_seek_submissions') or 0
    if route == 'SEEK' and times and gap:
        minutes = (now - max(times)).total_seconds() / 60
        if minutes < gap:
            raise CapReached(f'SEEK: the last submission was {int(minutes)} minutes ago; wait {int(gap - minutes) + 1} more '
                             f'(at least {gap} minutes apart).')


def next_entry(route, qdir=QUEUE_DIR, config=None, now=None, by=None, prior=None):
    """The single next entry to submit on this route. Raises CapReached or NothingToDo.

    prior is the list of applications made outside the queue (the entries of prior_outreach.json).
    """
    if route not in ROUTES:
        raise Refused(f'route: one of {", ".join(ROUTES)}')
    now = now or datetime.now(timezone.utc)
    entries = load(qdir)
    check_caps(route, entries, config, now)
    ctx, ready, held = hold_context([e for _, e in entries], config, now, prior), [], {}
    for path, e in entries:
        if e['route'] != route or e['status'] not in OPEN_STATUSES:
            continue
        why = blockers(e, ctx)
        if why:
            held[e['id']] = why
        else:
            ready.append((sort_key(e, config), path, e))
    if not ready:
        raise NothingToDo(f'{route}: nothing to hand out.' + ''.join(f"\n  {i}: {'; '.join(w)}" for i, w in sorted(held.items())))
    _, path, e = min(ready, key=lambda r: r[0])
    if by:
        e['attempts'].append({'at': iso(now), 'by': by, 'result': 'started', 'note': ''})
        save(qdir, e, path)
    return e


def mark(qdir, entry_id, action, by, now=None, kind=None, ref=None, at=None, note='', final=False, facts=None):
    """Record what happened to an entry: applied, skipped, failed (known not to have gone), uncertain (unknown
    whether it went), ask (owner question) or open (back to OPEN)."""
    now = now or datetime.now(timezone.utc)
    path, e = find(qdir, entry_id, open_only=True)
    if not by:
        raise Refused('--by NAME is needed')
    already = validate(e, facts)   # a fault the file already had must not stop a real result from being recorded
    when = iso(parse_time(at)) if at else iso(now)
    note = ' '.join(str(note or '').split())
    if action == 'applied':
        if kind not in RECEIPT_KINDS or not ref:
            raise Refused(f'applied needs --ref and --kind (one of {", ".join(RECEIPT_KINDS)})')
        e['status'], e['ask_owner'] = 'APPLIED', ''
        e['receipt'] = {'at': when, 'by': by, 'kind': kind, 'ref': str(ref)}
    elif action == 'skipped':
        if not note:
            raise Refused('skipped needs --reason')
        e['status'], e['ask_owner'] = 'SKIPPED', ''
    elif action == 'failed':
        if not note:
            raise Refused('failed needs --note')
        failures = 1
        for a in reversed(e['attempts']):
            if a.get('result') == 'reopened':
                break
            failures += a.get('result') == 'failed'
        if final:
            e['status'], e['ask_owner'] = 'FAILED', ''
        elif failures >= 3:
            e['status'], e['ask_owner'] = 'ASK_OWNER', f'Three failed attempts (last: {note}). Try again or drop it?'
    elif action == 'uncertain':
        if not note:
            raise Refused('uncertain needs --note')
        where = {'SEEK': 'the applied jobs list on SEEK', 'EMAIL': 'Gmail Sent'}.get(e['route'], "the employer's confirmation email")
        e['status'] = 'ASK_OWNER'
        e['ask_owner'] = f"Unknown whether the application to {' '.join(e['company'].split())} went ({note}). Check {where} before any retry: did it go?"
    elif action == 'ask':
        if not note:
            raise Refused('ask needs --question')
        e['status'], e['ask_owner'] = 'ASK_OWNER', note
    elif action == 'open':
        if unanswered(e):
            raise Refused(f'{entry_id} still has an unanswered question: ' + question_ask(e))
        e['status'], e['ask_owner'] = 'OPEN', ''
    else:
        raise Refused(f'unknown action {action}')
    result = {'ask': 'asked_owner', 'open': 'reopened'}.get(action, action)
    e['attempts'].append({'at': when, 'by': by, 'result': result, 'note': note})
    problems = [x for x in validate(e, facts) if x not in already]
    if problems:
        raise Refused('not saved: ' + '; '.join(problems))
    save(qdir, e, path, finished_at=parse_time(when))
    return e


def expire(qdir=QUEUE_DIR, today=None, now=None):
    """Move every open entry whose closing date or stated closing time has passed to done as EXPIRED. Returns them.

    today, a date or a date-time, judges the queue as at an earlier moment than now; a bare date is the start of that
    day in Melbourne, so entries that close that day stay. A value that is not a date, or is later than now, is refused.
    """
    now = now or datetime.now(timezone.utc)
    at = parse_time(today) if today else now
    if at > now:
        raise Refused(f"--today {today} is later than now ({now.astimezone(_melbourne()).strftime('%Y-%m-%d %H:%M')} in Melbourne): "
                      'nothing can have closed yet')
    gone = []
    for path, e in load(qdir):
        if e['status'] in OPEN_STATUSES and closed(e, at):
            e['attempts'].append({'at': iso(now), 'by': 'queue.py expire', 'result': 'expired',
                                  'note': f"closed {closes_text(e)} ({e['closes_source']}), never submitted"})
            e['status'], e['ask_owner'] = 'EXPIRED', ''
            save(qdir, e, path, finished_at=at)
            gone.append(e)
    return gone


def set_question(e, facts, question, options=None, answer=None, basis=None, by=None):
    """Add a form question (or update it with the options seen on screen), then recompute the entry's answers.

    A runner's own answer is taken only when set_problem finds nothing wrong: it must be the value at the basis key.
    """
    before = question_ask(e)
    q = next((q for q in e['questions'] if slug(q['question']) == slug(question)), None)
    if q is None:
        q = {'question': ' '.join(str(question).split()), 'options': [], 'answer': '', 'basis': '', 'status': 'unanswered'}
        e['questions'].append(q)
    if options:
        q['options'] = [str(o).strip() for o in options]
        q.pop('by', None)  # an earlier hand-set answer may not be one of the options: answer again
    if answer is not None:
        if not by:
            raise Refused('--set needs --by NAME and --basis naming a value in facts.json (for example identity.location)')
        why = set_problem(q['question'], str(answer), str(basis or ''), facts)
        if why:
            raise Refused('not set: ' + why)
        if q['options'] and not all(part in q['options'] for part in answer.split('; ')):
            raise Refused('the answer must be one of the options, word for word: ' + ' / '.join(q['options']))
        q.update({'answer': answer, 'basis': basis, 'status': 'answered', 'by': by})
    apply_answers(e, facts, before)
    return q


# ---------- reports ----------

def stats(qdir=QUEUE_DIR, now=None):
    now = now or datetime.now(timezone.utc)
    entries = [e for _, e in load(qdir)]
    week = {melbourne_date(now - timedelta(days=d)) for d in range(7)}
    is_open = [e for e in entries if e['status'] == 'OPEN']
    applied = [e for e in entries if e['status'] == 'APPLIED']
    return {
        'queue_open': {**{r: sum(1 for e in is_open if e['route'] == r) for r in ROUTES}, 'total': len(is_open)},
        'applied_last_7_days': sum(1 for e in applied if e['receipt'].get('at') and melbourne_date(e['receipt']['at']) in week),
        'applied_total': len(applied),
        'expired_unsubmitted_total': sum(1 for e in entries if e['status'] == 'EXPIRED'),
        'ask_owner_open': sum(1 for e in entries if e['status'] == 'ASK_OWNER'),
        'open_with_letter_to_rewrite': sum(1 for e in is_open if REWRITE_MARK in e['notes']),
    }


def _cell(s):
    return ' '.join(str(s or '').replace('|', '/').split())


def render(qdir=QUEUE_DIR, config=None, now=None, prior=None):
    """Write APPLY_QUEUE.md: open entries by route in hand-out order, then the questions waiting on the owner."""
    entries = [e for _, e in load(qdir)]
    ctx = hold_context(entries, config, now or datetime.now(timezone.utc), prior)
    lines = ['# Apply queue', '', 'Written by `automation/scripts/queue.py render` from the files in `open/`. Do not edit by hand.', '']
    for route in ROUTES:
        rows = sorted((e for e in entries if e['status'] == 'OPEN' and e['route'] == route), key=lambda e: sort_key(e, config))
        lines += [f'## {route} ({len(rows)} open)', '']
        if not rows:
            lines += ['Nothing open.', '']
            continue
        lines += ['| # | Lane | Company | Role | Location | Closes | Link | Note |', '|---|---|---|---|---|---|---|---|']
        for n, e in enumerate(rows, 1):
            closes = f"{closes_text(e)} ({'advert' if e['closes_source'] == 'advert' else 'listing expiry'})" if e['closes_at'] else 'not stated'
            note = '; '.join(blockers(e, ctx))
            lines.append(f"| {n} | {e['lane']} | {_cell(e['company'])} | {_cell(e['role'])} | {_cell(e['location'])} | {closes} | "
                         f"[{e['id']}]({e['url']}) | {_cell(note)} |")
        lines.append('')
    asks = sorted((e for e in entries if e['status'] == 'ASK_OWNER'), key=lambda e: sort_key(e, config))
    lines += [f'## Waiting on the owner ({len(asks)})', '']
    lines += [f"- **{_cell(e['company'])}, {_cell(e['role'])}** ({e['route']}, {e['lane']}, "
              f"closes {closes_text(e) or 'not stated'}, `{e['id']}`): {owner_line(e)}" for e in asks] or ['Nothing.']
    path = Path(qdir) / 'APPLY_QUEUE.md'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


# ---------- command line ----------

def _parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', default=str(QUEUE_DIR), help='queue folder (default automation/queue)')
    ap.add_argument('--config', default=str(ROOT / 'config.json'))
    ap.add_argument('--facts', default=str(ROOT / 'facts.json'))
    ap.add_argument('--prior', default=str(ROOT / 'prior_outreach.json'), help='applications made outside the queue (default automation/prior_outreach.json)')
    ap.add_argument('--now', help='ISO time to use as the current time (tests, back-dating)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('add'); c.add_argument('entry'); c.add_argument('--by')
    c.add_argument('--repeat-ok', metavar='REASON', help='this is another job at an employer already in the queue or applied to: say why')
    c = sub.add_parser('list'); c.add_argument('--route', choices=ROUTES); c.add_argument('--status', choices=STATUSES)
    c.add_argument('--all', action='store_true', help='include finished entries'); c.add_argument('--json', action='store_true')
    c = sub.add_parser('show'); c.add_argument('id')
    c = sub.add_parser('next'); c.add_argument('--route', required=True, choices=ROUTES); c.add_argument('--by')
    c = sub.add_parser('mark'); c.add_argument('id'); c.add_argument('action', choices=('applied', 'skipped', 'failed', 'uncertain', 'ask', 'open'))
    c.add_argument('--by', required=True); c.add_argument('--kind', choices=RECEIPT_KINDS); c.add_argument('--ref'); c.add_argument('--at')
    c.add_argument('--reason'); c.add_argument('--note'); c.add_argument('--question'); c.add_argument('--final', action='store_true')
    c = sub.add_parser('answer'); c.add_argument('id'); c.add_argument('--question'); c.add_argument('--option', action='append')
    c.add_argument('--set', dest='answer'); c.add_argument('--basis'); c.add_argument('--by')
    c = sub.add_parser('letter'); c.add_argument('id'); c.add_argument('--file', required=True); c.add_argument('--subject'); c.add_argument('--body-file')
    c.add_argument('--to', help='the address the email goes to'); c.add_argument('--evidence-url', help='the page where the employer publishes that address')
    c.add_argument('--allow', action='append', metavar='PHRASE', help='a flagged phrase this text may keep, for example the visa end date when the advert asks for it')
    c = sub.add_parser('expire'); c.add_argument('--today')
    sub.add_parser('render')
    c = sub.add_parser('stats'); c.add_argument('--json', action='store_true')
    sub.add_parser('check')
    return ap


def _show(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def run(a):
    qdir, now = Path(a.dir), parse_time(a.now) if a.now else datetime.now(timezone.utc)
    config, facts = read_json(a.config), read_json(a.facts)

    def prior():   # read by the commands that need it; a missing or broken file is refused, not ignored
        data = read_json(a.prior)
        return (data.get('entries') if isinstance(data, dict) else data) or []
    if a.cmd == 'add':
        entry = read_json(a.entry)
        if a.repeat_ok:
            entry['repeat_ok'] = ' '.join(a.repeat_ok.split())
        e = add(entry, qdir, facts, now, a.by, config, prior())
        print(f"added {e['id']} ({e['status']}, {e['route']}, {e['lane']})")
    elif a.cmd == 'list':
        rows = [e for _, e in load(qdir) if (a.all or a.status or e['status'] in OPEN_STATUSES)
                and (not a.route or e['route'] == a.route) and (not a.status or e['status'] == a.status)]
        rows.sort(key=lambda e: (e['status'] not in OPEN_STATUSES, ROUTES.index(e['route']), sort_key(e, config)))
        if a.json:
            return _show(rows)
        for e in rows:
            print(f"{e['id']:<34} {e['status']:<9} {e['route']:<15} {e['lane']:<10} {e['closes_at'][:10] or '-':<10} {e['company']}: {e['role']}")
    elif a.cmd == 'show':
        _show(find(qdir, a.id)[1])
    elif a.cmd == 'next':
        _show(next_entry(a.route, qdir, config, now, a.by, prior()))
    elif a.cmd == 'mark':
        e = mark(qdir, a.id, a.action, a.by, now, a.kind, a.ref, a.at, a.reason or a.note or a.question, a.final, facts)
        print(f"{e['id']}: {e['status']}" + (f" ({e['ask_owner']})" if e['ask_owner'] else ''))
    elif a.cmd == 'answer':
        path, e = find(qdir, a.id, open_only=True)
        if (a.option or a.answer is not None) and not a.question:
            raise Refused('--option and --set need --question')
        if a.question:
            set_question(e, facts, a.question, a.option, a.answer, a.basis, a.by)
        else:
            apply_answers(e, facts)
        problems = validate(e, facts)   # a question or an answer typed from a form can carry private details
        if problems:
            raise Refused('not saved: ' + '; '.join(problems))
        save(qdir, e, path)
        _show({'id': e['id'], 'status': e['status'], 'ask_owner': e['ask_owner'], 'questions': e['questions']})
    elif a.cmd == 'letter':
        path, e = find(qdir, a.id, open_only=True)
        if e['route'] == 'EMAIL' and REWRITE_MARK in e['notes'] and not (a.body_file and a.subject):
            raise Refused(f'{e["id"]} goes by email and is still marked "{REWRITE_MARK}": the email body is what is sent, '
                          'so give --body-file and --subject together with the new letter')
        e['cover_letter_text'] = Path(a.file).read_text(encoding='utf-8').strip()
        if a.body_file:
            e['email']['body'] = Path(a.body_file).read_text(encoding='utf-8').strip()
        for key, value in (('subject', a.subject), ('to', a.to), ('evidence_url', a.evidence_url)):
            if value:
                e['email'][key] = ' '.join(value.split())
        if a.allow:
            e['tone_allow'] = sorted({str(x).lower() for x in e.get('tone_allow') or []} | {' '.join(x.lower().split()) for x in a.allow})
        e['notes'] = '\n'.join(line for line in e['notes'].splitlines() if REWRITE_MARK not in line)
        problems = validate(e, facts) + tone_problems(e, config)
        if problems:
            raise Refused('not saved: ' + '; '.join(problems))
        save(qdir, e, path)
        print(f"{e['id']}: letter saved ({len(e['cover_letter_text'].split())} words)")
    elif a.cmd == 'expire':
        gone = expire(qdir, a.today, now)
        for e in gone:
            print(f"expired {e['id']}: {e['company']}, {e['role']} (closed {closes_text(e)})")
        print(f'{len(gone)} expired')
    elif a.cmd == 'render':
        print(render(qdir, config, now, prior()))
    elif a.cmd == 'stats':
        s = stats(qdir, now)
        if a.json:
            return _show(s)
        for k, v in s.items():
            print(f'{k}: ' + (', '.join(f'{r} {n}' for r, n in v.items()) if isinstance(v, dict) else str(v)))
    elif a.cmd == 'check':
        entries, bad, seen, jobs = load(qdir), 0, {}, {}
        for path, e in entries:
            problems = validate(e, facts)
            if (e['status'] in OPEN_STATUSES) != (path.parent.name == 'open'):
                problems.append(f"status {e['status']} does not belong in {path.parent.name}/")
            if path.stem != e['id']:
                problems.append('file name is not the id')
            for key in sorted({'id:' + e['id'], norm_url(e['url'])} | ({'seek:' + e['seek_id']} if e['seek_id'] else set())):
                if seen.setdefault(key, path) != path:
                    problems.append(f'duplicate of {seen[key].name} ({key})')
            if e['status'] in OPEN_STATUSES + ('APPLIED',) and not e.get('repeat_ok') and jobs.setdefault(job_key(e), path) != path:
                problems.append(f'same company and role as {jobs[job_key(e)].stem} (close one, or give this one repeat_ok with the reason)')
            for msg in problems:
                bad += 1
                print(f"{e['id']}: {msg}")
        print(f'{len(entries)} entries, {bad} problems')
        if bad:
            raise Refused('check failed')


def main(argv=None):
    a = _parser().parse_args(argv)
    try:
        run(a)
    except Refused as err:
        print(str(err), file=sys.stderr)
        return err.code
    return 0


if __name__ == '__main__':
    sys.exit(main())
