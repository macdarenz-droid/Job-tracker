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
  queue.py answer --question TEXT [--option O]... [--advert-pay TEXT]   (no entry yet: the standing answer, or UNANSWERED)
  queue.py answer ID --question TEXT [--option O]... [--advert-pay TEXT] [--by NAME]   (a question on the form of an entry)
  queue.py answer ID                                         (every stored answer again, from facts.json as it is now)
  queue.py letter ID --file LETTER.txt [--subject TEXT] [--body-file EMAIL.txt] [--to ADDRESS] [--evidence-url URL]
                     [--allow PHRASE]...
  queue.py expire [--today YYYY-MM-DD]
  queue.py render
  queue.py stats [--json]
  queue.py check

Exit codes: 0 done; 1 refused (reason on stderr); 3 the day's cap or the SEEK spacing is reached; 4 nothing to hand out;
5 a form question has no standing answer in facts.json (do not submit; leave the form).

Answers come only from facts.json, through answers.py (the one gate checks.py uses too). answer prints the answer to
give, word for word one of the options given, on stdout; a question it cannot answer prints UNANSWERED: <why> on
stderr and exits 5, and on an entry it also stores the question, sets ASK_OWNER and ends an unmarked start. next
works out every answer again from facts.json before handing an entry out, and prints each question on stderr as
'Q: <question> | give: <answer>'. With no options an answer is the text to type or a short description of the
choice: for every multiple-choice question run answer with the options on screen.

next never hands out an entry that is not OPEN, is past its closing date or stated closing time, has an unanswered
question, repeats a company and role already APPLIED, goes to an employer applied to in the last
limits.repeat_block_days (in the queue or in prior_outreach.json), has a twin for the same employer that a runner has
started or left uncertain, still carries a letter marked "rewrite before use", has a letter or email that fails
checks.py's letter_issues or email_issues (the same rules as `checks.py draft`; an EMAIL entry needs its letter), has no
email text or no evidence_url (EMAIL route), or was started by a runner that recorded no result. With --by it records
the start, so finish every entry it hands out with a mark.

Three optional fields beyond the standard ones: repeat_ok (why this entry may go although the employer or the same
company and role is already in the queue or applied to; set by add --repeat-ok), tone_allow (flagged phrases the
letter or email may keep; set by letter --allow) and advert_pay (the advert's own pay text, which decides the salary
answer; set by add from the entry file, or by answer --advert-pay).

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


class Unanswered(Refused):
    """A form question has no standing answer in facts.json: do not submit."""
    code = 5


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

def _sibling(name):
    """A module from this folder (answers.py, checks.py), imported once by name. The folder goes at the end of
    sys.path, never the front: this file must not shadow the standard library's queue module for other code."""
    folder = str(Path(__file__).resolve().parent)
    if folder not in sys.path:
        sys.path.append(folder)
    return importlib.import_module(name)


def answer_question(question_text, options, facts, pay=None):
    """The standing answer to one form question, from the one answer gate (answers.py): {'answer', 'basis', 'status'}.

    status is 'answered' only when a line of facts.json clearly covers the question; with the form's options the
    answer is one of them, word for word (several joined by '; ' for a tick list), and with no options it is the text
    to give. pay is the advert's own pay text (the salary question). Nothing else is guessed.
    """
    r = _sibling('answers').answer(question_text, options, facts, pay=pay)
    return {'answer': r['answer'], 'basis': r['basis'], 'status': r['status']}


def set_problem(question, answer, basis, facts):
    """Why an answer set by hand does not stand: every answer now comes from facts.json through answers.py (the
    owner's answers go into facts.json, and `queue.py answer ID` recomputes). Kept so that validate and check name an
    old hand-set answer ('by') that is still in a file; the next recompute replaces it."""
    return 'answers are set only from facts.json by answers.py (queue.py answer ID recomputes them); a hand-set answer does not stand'


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


QUESTION_LINE = 'No standing answer for '   # how question_ask starts: an ask_owner the form questions put there


def apply_answers(e, facts, before=None):
    """Recompute every question from facts (answers.py) and move the entry between OPEN and ASK_OWNER to match.

    Every stored answer is worked out again, so a change to facts.json reaches every entry; an old answer set by hand
    ('by') is dropped. The entry goes to ASK_OWNER while a mandatory question is unanswered, and back to OPEN once the
    owner question is only about form questions and all of them are answered. An ASK_OWNER put there for another
    reason stays. before is the entry's question line as it was before the caller changed its questions.
    """
    before = question_ask(e) if before is None else before
    for q in e['questions']:
        q.pop('by', None)
        q.update(answer_question(q.get('question'), q.get('options'), facts, e.get('advert_pay') or None))
    after = question_ask(e)
    ours = e['status'] == 'ASK_OWNER' and (bool(before) and e['ask_owner'] == before or str(e['ask_owner']).startswith(QUESTION_LINE))
    if after and (e['status'] == 'OPEN' or ours):
        e['status'], e['ask_owner'] = 'ASK_OWNER', after
    elif not after and ours:
        e['status'], e['ask_owner'] = 'OPEN', ''
    return e


def refresh(qdir, path, e, facts):
    """Recompute an entry's answers from the facts.json of now and save the file when anything changed."""
    was = json.dumps([e['status'], e['ask_owner'], e['questions']], sort_keys=True)
    apply_answers(e, facts)
    if json.dumps([e['status'], e['ask_owner'], e['questions']], sort_keys=True) != was:
        save(qdir, e, path)
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
    """Where the letter (with its relocation line) or, on the EMAIL route, the email breaks the writing rules. These
    are checks.py's own rules (letter_issues, email_issues), so next and `checks.py draft` agree: the word limits,
    config -> tone banned phrases and characters (en and em dashes too), the volunteered-limit patterns not listed
    under tone_allow, the visa end date however written, claims facts.json does not hold, and the letter's three
    paragraphs between the greeting line and the sign-off. An email application also needs its letter."""
    checks = _sibling('checks')
    tone, allow = (config or {}).get('tone'), e.get('tone_allow') or []
    letter = checks.compose_letter(e['cover_letter_text'], e['relocation_line'])
    problems = checks.letter_issues(letter, tone=tone, allow=allow) if letter.strip() else []
    if e['route'] == 'EMAIL':
        if not letter.strip():
            problems.append('letter text missing (an email application attaches the cover letter)')
        problems += checks.email_issues(e['email']['subject'], e['email']['body'], tone=tone, allow=allow)
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


def next_entry(route, qdir=QUEUE_DIR, config=None, now=None, by=None, prior=None, facts=None):
    """The single next entry to submit on this route. Raises CapReached or NothingToDo.

    prior is the list of applications made outside the queue (the entries of prior_outreach.json). With facts, every
    entry on the route has its answers worked out again from them first, so a changed facts.json holds back an entry
    whose answer no longer stands (and releases one whose questions are now all answered).
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
        if facts is not None:
            refresh(qdir, path, e, facts)   # answers follow the facts.json of now, not of the day the entry was added
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
        open_questions = [q['question'] for q in unanswered(e)]
        if any(slug(q) in slug(note) for q in open_questions):
            # The ask is about the entry's own unanswered form questions: keep their line, so that `queue.py answer ID`
            # reopens the entry once facts.json answers them. The runner's words stay in the attempt note.
            e['status'], e['ask_owner'] = 'ASK_OWNER', question_ask(e)
        else:
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


def set_question(e, facts, question, options=None, pay=None):
    """Add a form question seen on screen (or give a stored one the options on screen), then recompute every answer
    of the entry from facts. pay, when given, is the advert's pay text and is kept on the entry (advert_pay). Returns
    the question as stored."""
    before = question_ask(e)
    q = next((q for q in e['questions'] if slug(q['question']) == slug(question)), None)
    if q is None:
        q = {'question': ' '.join(str(question).split()), 'options': [], 'answer': '', 'basis': '', 'status': 'unanswered'}
        e['questions'].append(q)
    if options:
        q['options'] = [' '.join(str(o).split()) for o in options if str(o).strip()]
    if pay:
        e['advert_pay'] = ' '.join(str(pay).split())
    apply_answers(e, facts, before)
    return q


def release_start(e, by, now, note):
    """End an unmarked start on the entry (its last attempt is 'started'), so that it is not held as under way."""
    last = e['attempts'][-1] if e['attempts'] else {}
    if last.get('result') == 'started':
        e['attempts'].append({'at': iso(now), 'by': by or last.get('by') or 'queue.py answer', 'result': 'asked_owner', 'note': ' '.join(note.split())})


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
    c = sub.add_parser('answer'); c.add_argument('id', nargs='?', help='the queue entry (leave out at screening, before the entry exists)')
    c.add_argument('--question'); c.add_argument('--option', action='append', help='each option on screen, word for word')
    c.add_argument('--advert-pay', help="the advert's own pay text, for the salary question")
    c.add_argument('--by', help='who is answering (recorded when an unmarked start is ended)')
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
        e = next_entry(a.route, qdir, config, now, a.by, prior(), facts)
        _show(e)
        for q in e['questions']:   # what to give for each question; run answer with the options for a multiple-choice one
            give = q['answer'] if q['status'] == 'answered' else '(no standing answer; optional: leave it blank)'
            print(f"Q: {q['question']} | give: {give}", file=sys.stderr)
    elif a.cmd == 'mark':
        e = mark(qdir, a.id, a.action, a.by, now, a.kind, a.ref, a.at, a.reason or a.note or a.question, a.final, facts)
        print(f"{e['id']}: {e['status']}" + (f" ({e['ask_owner']})" if e['ask_owner'] else ''))
    elif a.cmd == 'answer':
        if a.option and not a.question:
            raise Refused('--option needs --question')
        if not a.id:   # at screening, before the entry exists: the gate's answer only, nothing is stored
            if not a.question:
                raise Refused('give an entry id, or --question with the options on screen')
            r = _sibling('answers').answer(a.question, a.option, facts, pay=a.advert_pay)
            if r['status'] != 'answered':
                raise Unanswered(f"UNANSWERED: {r['why']}")
            print(r['answer'])
            print(f"(facts.json -> {r['basis']})", file=sys.stderr)
            return
        path, e = find(qdir, a.id, open_only=True)
        q = set_question(e, facts, a.question, a.option, a.advert_pay) if a.question else None
        if q is not None and q['status'] != 'answered' and q.get('mandatory', True):
            release_start(e, a.by, now, f"form question with no standing answer: {q['question']}")
        else:
            apply_answers(e, facts)
        problems = validate(e, facts)   # a question or an option typed from a form can carry private details
        if problems:
            raise Refused('not saved: ' + '; '.join(problems))
        save(qdir, e, path)
        if q is None:
            _show({'id': e['id'], 'status': e['status'], 'ask_owner': e['ask_owner'], 'questions': e['questions']})
            if unanswered(e):
                raise Unanswered(f"UNANSWERED: {e['id']} still has a form question with no standing answer ({e['status']}): " + question_ask(e))
        elif q['status'] == 'answered':
            print(q['answer'])
            print(f"(facts.json -> {q['basis']})", file=sys.stderr)
        else:
            why = _sibling('answers').answer(q['question'], q['options'], facts, pay=e.get('advert_pay') or None)['why']
            if not q.get('mandatory', True):
                print(f'UNANSWERED: {why}. The entry marks this question optional: leave it blank.', file=sys.stderr)
                return
            raise Unanswered(f"UNANSWERED: {why}. {e['id']} is now {e['status']}: do not submit; leave the form.")
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
