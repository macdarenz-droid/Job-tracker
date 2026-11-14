#!/usr/bin/env python3
"""The apply queue: one JSON file per job application, worked through by the submitters.

Open entries live in automation/queue/open/<id>.json; finished ones move to automation/queue/done/<YYYY-MM>/<id>.json.
One file per entry, so several runners pushing to the same branch rarely conflict.

Usage (global options --dir, --config, --facts, --prior and --now go before the command):
  queue.py add ENTRY.json [--by NAME]
  queue.py list [--route R] [--status S] [--all] [--started] [--json]
  queue.py show ID
  queue.py next --route R [--by NAME] [--run RUN_ID]          (EMAIL: --by, --run and that runner's own send lock)
  queue.py mark ID applied --by NAME --kind K --ref REF [--thread THREAD_ID] [--at ISO]
  queue.py mark ID skipped --by NAME --reason TEXT             (closed or changed advert, or not to be sent)
  queue.py mark ID failed --by NAME --note TEXT [--final]      (only when it is known that nothing was submitted)
  queue.py mark ID uncertain --by NAME --note TEXT             (unknown whether it went: UNCERTAIN until someone checks)
  queue.py mark ID linkout --by NAME [--note TEXT]             (SEEK's apply button leads to the employer's site)
  queue.py mark ID ask --by NAME --question TEXT
  queue.py mark ID open --by NAME [--note TEXT]                (an UNCERTAIN entry: --note "checked: not submitted ...")
  queue.py outcome ID --kind acknowledged|rejected|reply|interview|offer --at YYYY-MM-DD --by NAME [--note TEXT]
  queue.py lock take --by NAME --run RUN_ID [--minutes 30]
  queue.py lock release --by NAME --run RUN_ID
  queue.py lock show
  queue.py answer ID [--question TEXT [--option O]... [--set ANSWER --basis FACTS.KEY --by NAME]]
  queue.py letter ID --file LETTER.txt [--subject TEXT] [--body-file EMAIL.txt] [--to ADDRESS] [--evidence-url URL]
                     [--allow PHRASE]...
  queue.py expire [--today YYYY-MM-DD]
  queue.py render
  queue.py stats [--json]
  queue.py report [--days N] [--json]
  queue.py check

Exit codes: 0 done; 1 refused (reason on stderr); 3 the day's cap, the SEEK spacing or the quiet hours
(config.json -> limits -> quiet_hours, 21:00-07:00 Melbourne time when not set); 4 nothing to hand out.

next hands out nothing at all while queue.py check finds a problem (for example an entry that is both in open/ and,
finished, in done/), during the quiet hours, or once the day's cap is used. The cap and the 20-minute SEEK spacing
count every APPLIED receipt, every UNCERTAIN entry (at its uncertain mark) and every start not yet marked (at the
start), on the Melbourne date. On the EMAIL route next needs --by, --run and that runner's own unexpired send lock.
It never hands out an entry that is not OPEN, has a finished copy in done/, is past its closing date or stated
closing time, has an unanswered question, repeats an application (the rule below), has a twin at the same employer
that a runner has started and not marked, is a speculative enquiry once limits.max_speculative_per_week (3 when not
set) have been applied for, left uncertain or started in this ISO week (Melbourne time), still carries a letter
marked "rewrite before use", has letter or email text over the word limits or with a flagged phrase of
config -> tone, has no email text or no evidence_url (EMAIL route), or was started by a runner that recorded no
result. Advertised vacancies go before speculative enquiries, then lane, then the soonest stated closing date, then
the newest listing. With --by it records the start and prints on stderr, after the entry, the git commands that
commit and push that claim: run them before submitting, and finish every entry it hands out with a mark. It also
prints on stderr the resume file for resume_variant with its sha256, and the entry's verify_before_submit checks
under "BEFORE SUBMITTING, CHECK:".

Repeats. The same advert (id, seek_id or url) is always a duplicate. The same employer and the same role is blocked
for ever once an entry for it is APPLIED or UNCERTAIN, and for limits.repeat_block_days (90) from an entry of
prior_outreach.json; a prior_outreach.json entry that does not say which role blocks every role at that employer for
those days. Another role at an employer already applied to is allowed, and next adds a line to the entry's notes
naming the earlier application. Employers are compared as tracker.py compares them (Pty Ltd, Group, Australia and
bracketed trading names aside); roles in lower case without punctuation, bracketed notes and the words junior,
graduate, trainee, cadet, entry level and senior, so "Junior Civil Drafter" and "Civil Drafter" are the same role.

Statuses: OPEN (waiting, ready or held), ASK_OWNER (waiting on the owner), UNCERTAIN (unknown whether it went; kept
in open/, never handed out or expired, counted as an application until "mark ID applied" or "mark ID open --note
'checked: ...'" settles it), APPLIED, SKIPPED, EXPIRED, FAILED. stats: queue_open counts status OPEN only (ready or
held), not ASK_OWNER or UNCERTAIN. A start that next --by recorded is released only by the runner that made it
("mark ID open --by NAME"); another runner may only mark it applied (with the receipt) or uncertain. expire leaves
UNCERTAIN entries and unmarked starts where they are.

Receipts. mark applied --ref is a public record: plain words such as "SEEK confirmation screen shown", never an email
address, a web address or a number of 6 or more digits (application, candidate or reference numbers). With --kind
gmail_message_id the ref is the Gmail message id (16 hex characters) and --thread may give the thread id (16 hex).

Outcomes (outcome ID): acknowledged, rejected, reply, interview or offer, on an APPLIED or UNCERTAIN entry, with the
date. The note is at most 140 characters, in your own words: no names and no quotes (queue.py cannot detect them, so
leave them out yourself), and no email address, phone number, number of 6 or more digits or web address.

Send lock (automation/queue/SEND_LOCK.json: by, run, taken_at, expires_at). lock take refuses while another run holds
an unexpired lock and prints the git commands that publish it: push it before sending; a rejected push means someone
else holds it. lock release refuses another run's lock. RUN_ID is the id journal.py start printed (20261114T0202Z).

Entry fields for add (one JSON object):
  required  lane (drafter, technician or engineer); route (SEEK, EMAIL, EMPLOYER_PORTAL or EMPLOYER_FORM); company;
            role (title is taken as role); url (the advert or the employer's page)
  by route  SEEK: seek_id, the SEEK job number (taken from a seek.com.au/job/<n> url when missing).
            EMAIL: email {to, subject, body, evidence_url (the page where the employer publishes the address)}.
  optional  id (made from seek_id, or company, role and url); application_type (ADVERTISED_VACANCY, the default, or
            SPECULATIVE_ENQUIRY; a role that starts "Speculative enquiry" is SPECULATIVE_ENQUIRY); location; listed_at
            (YYYY-MM-DD); closes_at (YYYY-MM-DD, or YYYY-MM-DDThh:mm when the advert states a time) with closes_source
            (advert or listing_expiry; listing_expiry when closes_at is given without it); fit (0 to 100);
            resume_variant (the lane when not given); relocation_line; cover_letter_text; questions (["exact text"]
            or [{"question": ..., "options": [...]}], answered from facts.json); verify_before_submit (a list of short
            one-line checks the submitter makes first); status (OPEN by default; ASK_OWNER with ask_owner; APPLIED
            with receipt {at, by, kind, ref} for an application made elsewhere); ask_owner; notes; source_run;
            created_by (else --by); created_at; tone_allow (flagged phrases the letter or email may keep; set by
            letter --allow).

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
import shlex
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
STATUSES = ('OPEN', 'ASK_OWNER', 'UNCERTAIN', 'APPLIED', 'SKIPPED', 'EXPIRED', 'FAILED')
OPEN_STATUSES = ('OPEN', 'ASK_OWNER')        # waiting to be worked
IN_OPEN = OPEN_STATUSES + ('UNCERTAIN',)       # kept in open/ and still to be marked
SUBMITTED = ('APPLIED', 'UNCERTAIN')           # count as an application: caps, spacing, repeats, outcomes
APPLICATION_TYPES = ('ADVERTISED_VACANCY', 'SPECULATIVE_ENQUIRY')
CLOSES_SOURCES = ('advert', 'listing_expiry', 'none')
RECEIPT_KINDS = ('seek_receipt_email', 'seek_confirmation_screen', 'gmail_message_id', 'portal_confirmation')
OUTCOME_KINDS = ('acknowledged', 'rejected', 'reply', 'interview', 'offer')
CAP_KEY = {'SEEK': 'seek_submissions_per_day', 'EMAIL': 'email_sends_per_day',
           'EMPLOYER_PORTAL': 'portal_submissions_per_day', 'EMPLOYER_FORM': 'portal_submissions_per_day'}
REWRITE_MARK = 'rewrite before use'
REPEAT_BLOCK_DAYS = 90  # used when config.json -> limits -> repeat_block_days is not set
QUIET_HOURS = '21:00-07:00'  # Melbourne time; used when config.json -> limits -> quiet_hours is not set
MAX_SPECULATIVE_PER_WEEK = 3  # used when config.json -> limits -> max_speculative_per_week is not set
LOCK_FILE = 'SEND_LOCK.json'
LOCK_MINUTES = 30
NOTE_LIMIT = 140
RUN_ID = re.compile(r'\d{8}T\d{4}Z')  # as journal.py start writes it
RESUME_DIR = ROOT.parent / 'documents' / 'resume'
COMPANY_NOISE = re.compile(r'\([^)]*\)|\b(?:pty|ltd|limited|plc|inc|co|group|holdings|australia|aust|the|and)\b|&', re.I)
ROLE_NOISE = re.compile(r'\b(?:junior|graduate|trainee|cadet|entry level|senior)\b')
# A role text that names no role: a receipt, or a note of how the application went in (as tracker.py reads it).
NO_ROLE = re.compile(r'receipt|position name|unknown|not (stated|shown|given|named|recorded)|application (received|via)|^(e-?mail|portal|employer portal)\b', re.I)
PHONE = re.compile(r'(?<![\w/=.-])(?:\+?61[\s-]?\(?0?|\(?0)[2-478]\)?(?:[\s-]?\d){8}(?!\d)'   # mobile or landline with area code
                   r'|(?<![\w/=.-])1[38]00(?:[\s-]?\d){6}(?!\d)')                                # 1300 and 1800 numbers
EMAIL_ADDRESS = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
WEB_ADDRESS = re.compile(r'https?://|\bwww\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|gov|edu|io|au|nz|uk)\b', re.I)
LONG_NUMBER = re.compile(r'\d{6,}')
OTHER_PHONE = re.compile(r'\+\d[\d\s().-]{6,}\d')   # an international number
GMAIL_ID = re.compile(r'[0-9a-f]{16}')
FIELDS = ('id', 'lane', 'route', 'application_type', 'company', 'role', 'location', 'url', 'seek_id', 'listed_at', 'closes_at',
          'closes_source', 'fit', 'resume_variant', 'relocation_line', 'cover_letter_text', 'email', 'questions', 'status',
          'ask_owner', 'attempts', 'receipt', 'created_by', 'created_at', 'source_run', 'notes')


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


def role_key(role):
    """A role title for the "same role" test: lower case, without punctuation, bracketed notes and the words junior,
    graduate, trainee, cadet, entry level and senior. 'Junior Civil Drafter' and 'Civil Drafter' are one role."""
    words = ' '.join(re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\([^)]*\)', ' ', str(role or '').lower())).split())
    return ' '.join(ROLE_NOISE.sub(' ', words).split()) or words


def same_role(a, b):
    ka = role_key(a)
    return bool(ka) and ka == role_key(b)


def same_job(a, b):
    """The same employer and the same role."""
    return same_employer(a.get('company'), b.get('company')) and same_role(a.get('role'), b.get('role'))


def role_unknown(role):
    """True when an earlier application's role is not on record (a receipt, 'position name blank'), as in tracker.py."""
    bare = re.sub(r'\([^)]*\)', ' ', str(role or '')).strip()
    return not role_key(bare) or bool(NO_ROLE.search(bare))


def advert_keys(e):
    """What makes two entries the same advert: the id, the url and the SEEK job number."""
    return {'id:' + e['id'], norm_url(e.get('url'))} | ({'seek:' + e['seek_id']} if e.get('seek_id') else set())


def is_speculative(e):
    return e.get('application_type') == 'SPECULATIVE_ENQUIRY'


def same_name(a, b):
    return ' '.join(str(a or '').split()).lower() == ' '.join(str(b or '').split()).lower()


def _rel(path):
    """A path as typed from the current folder."""
    try:
        return os.path.relpath(path)
    except ValueError:  # pragma: no cover - another drive on Windows
        return str(path)


def git_command(paths, message):
    """The git commands that commit and push these queue files, to be run from the current folder."""
    files = ' '.join(shlex.quote(_rel(p)) for p in paths)
    return f'git add -A -- {files} && git commit -m {shlex.quote(message)} && git pull --rebase && git push'


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
    if not e.get('application_type'):   # entries written before the field existed: read from the id or the role
        spec = str(e.get('role') or '').strip().lower().startswith('speculative enquiry') or 'speculative-enquiry' in str(e['id'])
        e['application_type'] = 'SPECULATIVE_ENQUIRY' if spec else 'ADVERTISED_VACANCY'
    if e['status'] == 'ASK_OWNER' and e['attempts'] and (e['attempts'][-1] or {}).get('result') == 'uncertain':
        e['status'], e['ask_owner'] = 'UNCERTAIN', ''   # marked uncertain before UNCERTAIN was a status of its own
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
    need(e.get('status') != 'UNCERTAIN' or any(a.get('result') == 'uncertain' for a in e.get('attempts') or []),
         'status: UNCERTAIN needs its uncertain attempt (set by mark ID uncertain)')
    kind = e.get('application_type') or 'ADVERTISED_VACANCY'
    need(kind in APPLICATION_TYPES, f'application_type: one of {", ".join(APPLICATION_TYPES)}')
    need(kind == 'SPECULATIVE_ENQUIRY' or not str(e.get('role') or '').strip().lower().startswith('speculative enquiry'),
         'application_type: the role says "Speculative enquiry", so it is SPECULATIVE_ENQUIRY')
    checks = e.get('verify_before_submit')
    need(checks is None or (isinstance(checks, list) and all(isinstance(c, str) and c.strip() and '\n' not in c and len(c) <= 200 for c in checks)),
         'verify_before_submit: a list of short one-line checks (at most 200 characters each)')
    for o in e.get('outcomes') or []:
        ok = isinstance(o, dict) and o.get('kind') in OUTCOME_KINDS and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(o.get('at') or '')) and o.get('by')
        need(ok, f'outcomes: each needs kind (one of {", ".join(OUTCOME_KINDS)}), at (YYYY-MM-DD) and by')
        why = note_problems(str(o.get('note') or '')) if isinstance(o, dict) else []
        need(not why, 'outcomes: a note ' + '; '.join(why))
    return p + privacy_problems(e, facts)


def note_problems(text, limit=NOTE_LIMIT):
    """Why a short note may not go into a public queue file ('' parts when it may): too long, or contact details."""
    p = [f'is {len(text)} characters (at most {limit})'] if len(text) > limit else []
    for what, pattern in (('an email address', EMAIL_ADDRESS), ('a phone number', PHONE), ('a phone number', OTHER_PHONE),
                          ('a number of 6 or more digits', LONG_NUMBER), ('a web address', WEB_ADDRESS)):
        if pattern.search(text) and f'holds {what}' not in p:
            p.append(f'holds {what}')
    return p


def ref_problems(kind, ref, thread=''):
    """Why this receipt reference may not be recorded in the public queue (empty when it may)."""
    ref, thread = str(ref or '').strip(), str(thread or '').strip()
    if kind == 'gmail_message_id':
        p = [] if GMAIL_ID.fullmatch(ref) else [f'--ref {ref!r}: with --kind gmail_message_id the ref is the Gmail message id, 16 hex characters (for example 1a1570496429d890)']
        return p + ([] if not thread or GMAIL_ID.fullmatch(thread) else [f'--thread {thread!r}: the Gmail thread id, 16 hex characters'])
    if thread:
        return ['--thread goes only with --kind gmail_message_id']
    held = [what for what, pattern in (('an email address', EMAIL_ADDRESS), ('a web address', WEB_ADDRESS), ('a number of 6 or more digits', LONG_NUMBER))
            if pattern.search(ref)]
    return [f'--ref holds {" and ".join(held)}: the queue is public, so write plain words such as "SEEK confirmation screen shown", '
            'never the confirmation text or an application, candidate or reference number'] if held else []


# ---------- storage ----------

def load(qdir=QUEUE_DIR):
    """Every entry as (path, entry): open ones first, then done."""
    qdir = Path(qdir)
    paths = sorted((qdir / 'open').glob('*.json')) + sorted((qdir / 'done').glob('*/*.json'))
    return [(p, fill(read_json(p))) for p in paths]


def find(qdir, entry_id, open_only=False, statuses=None):
    """The one file of an entry. open_only: it must be OPEN or ASK_OWNER; statuses: it must have one of these."""
    hits = [(path, e) for path, e in load(qdir) if e['id'] == entry_id]
    if not hits:
        raise Refused(f'no queue entry with id {entry_id}')
    if len(hits) > 1:
        raise Refused(f"{entry_id} has {len(hits)} files ({', '.join(_rel(p) for p, _ in hits)}): run queue.py check and "
                      'remove the stale copy first')
    path, e = hits[0]
    allowed = statuses or (OPEN_STATUSES if open_only else None)
    if allowed and e['status'] not in allowed:
        raise Refused(f"{entry_id} is already {e['status']}")
    return path, e


def save(qdir, e, old_path=None, finished_at=None):
    """Write an entry where its status says it belongs; remove the old file when it moved."""
    qdir = Path(qdir)
    if e['status'] in IN_OPEN:
        path = qdir / 'open' / f"{e['id']}.json"
    else:
        path = qdir / 'done' / melbourne_date(finished_at or datetime.now(timezone.utc))[:7] / f"{e['id']}.json"
    write_json(path, fill(e))
    if old_path and Path(old_path) != path and Path(old_path).exists():
        Path(old_path).unlink()
    return path


def add(entry, qdir=QUEUE_DIR, facts=None, now=None, by=None, config=None, prior=None):
    """Validate and store a new entry.

    title is taken as role when role is missing, seek_id is read from a seek.com.au/job/<n> url when it is missing, and
    closes_source is listing_expiry when closes_at is given without it. Refuses a duplicate id, SEEK job or url, whether
    open or done. An entry to be worked (OPEN or ASK_OWNER) is also refused when the same employer and role is already
    waiting in the queue, or would repeat an application (repeat_check: the queue's APPLIED and UNCERTAIN entries, and
    prior, the entries of prior_outreach.json).
    """
    now = now or datetime.now(timezone.utc)
    e = dict(entry)
    title = e.pop('title', None)
    if not str(e.get('role') or '').strip() and str(title or '').strip():
        e['role'] = title
    seek = re.search(r'seek\.com(?:\.au)?/job/(\d+)', str(e.get('url') or ''), re.I)
    if not str(e.get('seek_id') or '').strip() and seek:
        e['seek_id'] = seek.group(1)
    if e.get('closes_at') and not e.get('closes_source'):
        e['closes_source'] = 'listing_expiry'
    e['created_at'] = e.get('created_at') or iso(now)
    e['created_by'] = e.get('created_by') or by or ''
    e = fill(e)
    if facts is not None:
        apply_answers(e, facts)
    problems = validate(e, facts) + (ref_problems(e['receipt'].get('kind'), e['receipt'].get('ref'), e['receipt'].get('thread')) if e['receipt'] else [])
    if problems:
        raise Refused('not added: ' + '; '.join(problems))
    if e['route'] == 'EMAIL' and e['status'] in OPEN_STATUSES and not e['email']['evidence_url']:
        raise Refused('not added: email.evidence_url: the page where the employer publishes the address')
    others = [other for _, other in load(qdir)]
    for other in others:
        same = advert_keys(e) & advert_keys(other)
        if same:
            raise Refused(f"not added: duplicate of {other['id']} ({other['status']}): same {', '.join(sorted(same))}")
    if e['status'] in OPEN_STATUSES:
        twin = next((o for o in others if o['status'] in OPEN_STATUSES and same_job(o, e)), None)
        why = (f"same company and role as {twin['id']} ({twin['status']}, {twin['route']})" if twin
               else repeat_check(e, applications(others, prior), melbourne_date(now), repeat_days(config))[0])
        if why:
            raise Refused(f'not added: {why}')
    save(qdir, e, finished_at=parse_time(e['receipt']['at']) if e['receipt'].get('at') else now)
    return e


# ---------- handing out and recording ----------

def lane_rank(e, config):
    lane = ((config or {}).get('lanes') or {}).get(e['lane']) or {}
    return lane.get('rank') or LANES.index(e['lane']) + 1


def sort_key(e, config):
    """Advertised vacancies before speculative enquiries, then lane rank, then a real (advert-stated) closing date
    soonest, then listed date newest."""
    c = e['closes_at']
    try:   # a bare date means the end of that day
        real_close = iso(parse_time(c if len(c) > 10 else c + 'T23:59:59')) if c and e['closes_source'] == 'advert' else '9999-12-31'
    except Refused:
        real_close = c
    listed = int(e['listed_at'][:10].replace('-', '')) if e['listed_at'] else 0
    return (is_speculative(e), lane_rank(e, config), real_close, -listed, e['id'])


def repeat_days(config):
    return ((config or {}).get('limits') or {}).get('repeat_block_days') or REPEAT_BLOCK_DAYS


def max_speculative(config):
    value = ((config or {}).get('limits') or {}).get('max_speculative_per_week')
    return value if isinstance(value, int) and not isinstance(value, bool) else MAX_SPECULATIVE_PER_WEEK


def started(e):
    """The start next --by recorded on a waiting entry that no mark has followed ({} when there is none)."""
    last = e['attempts'][-1] if e['attempts'] else {}
    return last if e['status'] in OPEN_STATUSES and last.get('result') == 'started' else {}


def submission_time(e):
    """When an entry counts as submitted, for the caps and the spacing: the receipt of an APPLIED entry, the uncertain
    mark of an UNCERTAIN one, the start of a waiting one that was started and not marked. None for anything else."""
    if e['status'] == 'APPLIED':
        at = e['receipt'].get('at')
    elif e['status'] == 'UNCERTAIN':
        at = next((a.get('at') for a in reversed(e['attempts']) if a.get('result') == 'uncertain'), None)
    else:
        at = started(e).get('at')
    try:
        return parse_time(at) if at else None
    except Refused:
        return None


def applications(entries, prior=None):
    """Every application on record, as dicts {company, role, date, where, status}: the queue's APPLIED and UNCERTAIN
    entries (dated by the receipt or the uncertain mark, Melbourne date), and prior, the entries of prior_outreach.json
    (applications made outside the queue: status 'prior')."""
    rows = []
    for e in entries:
        if e['status'] in SUBMITTED:
            t = submission_time(e)
            rows.append({'company': e['company'], 'role': e['role'], 'date': melbourne_date(t) if t else '', 'where': e['id'], 'status': e['status']})
    for p in prior or []:
        rows.append({'company': str(p.get('company') or ''), 'role': str(p.get('role') or ''), 'date': str(p.get('date') or '').strip()[:10],
                     'where': 'prior_outreach.json', 'status': 'prior'})
    return rows


def repeat_check(e, applied, today, days):
    """(why applying for this entry would repeat an application, a line naming the earlier applications at the same
    employer that do not block it); each '' when there is none.

    The same employer and role is blocked for ever by an APPLIED or UNCERTAIN entry of the queue, and for days by an
    entry of prior_outreach.json; a prior_outreach.json entry with no role on record blocks every role at the employer
    for those days. Another role at the same employer is allowed and named in the line.
    """
    cutoff = (datetime.fromisoformat(today) - timedelta(days=days)).strftime('%Y-%m-%d')
    earlier = []
    for a in applied:
        if a['where'] == e['id'] or not same_employer(a['company'], e['company']):
            continue
        role, when = ' '.join(a['role'].split()) or 'role not recorded', a['date'] or 'an unknown date'
        if a['status'] == 'APPLIED' and same_role(a['role'], e['role']):
            return f"already applied for this company and role ({a['where']})", ''
        if a['status'] == 'UNCERTAIN' and same_role(a['role'], e['role']):
            return (f"{a['where']} for this company and role is UNCERTAIN (marked {when}): settle it first with mark "
                    f"{a['where']} applied, or mark {a['where']} open --note \"checked: ...\""), ''
        if a['status'] == 'prior':
            inside = not re.fullmatch(r'\d{4}-\d{2}-\d{2}', a['date']) or a['date'] >= cutoff   # no date, or none readable, blocks
            if inside and role_unknown(a['role']):
                return (f"applied to this employer on {when} ({a['where']}) and the record does not say for which role: "
                        f'no application to this employer within {days} days'), ''
            if inside and same_role(a['role'], e['role']):
                return f"applied for this company and role on {when} ({a['where']}): no repeat within {days} days", ''
            earlier.append(f"{a['where']} ({role}, {when})")
        else:
            earlier.append(f"{a['where']} ({role}, {a['status']} {when})")
    return '', ('Earlier application at this employer, for another role or outside the repeat block: ' + '; '.join(earlier) + '.') if earlier else ''


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


def iso_week(dt):
    year, week, _ = dt.astimezone(_melbourne()).isocalendar()
    return f'{year}-W{week:02d}'


def hold_context(entries, config, now, prior=None):
    """What blockers needs besides the entry: the time, the rules, the applications on record, the entries under way,
    the ids that have a finished copy and this ISO week's speculative enquiries."""
    busy = [(e['company'], e['id'], f"started by {started(e).get('by')}") for e in entries if started(e)]
    week = iso_week(now)
    speculative = 0
    for e in entries:
        t = submission_time(e)
        speculative += bool(is_speculative(e) and t and iso_week(t) == week)
    return {'now': now, 'config': config, 'days': repeat_days(config), 'applied': applications(entries, prior), 'busy': busy,
            'finished': {e['id'] for e in entries if e['status'] not in IN_OPEN}, 'week': week,
            'speculative_this_week': speculative, 'max_speculative': max_speculative(config)}


def blockers(e, ctx):
    """Why next will not hand this entry out (empty when it is ready). ctx comes from hold_context."""
    b = []
    if e['status'] != 'OPEN':
        b.append('status ' + e['status'])
    if e['status'] in IN_OPEN and e['id'] in ctx['finished']:
        b.append('a finished copy of this entry is in done/: run queue.py check')
    try:
        if closed(e, ctx['now']):
            b.append('closing date has passed')
    except Refused:
        b.append('closes_at is not a date')
    if unanswered(e):
        b.append('unanswered question')
    repeat = repeat_check(e, ctx['applied'], melbourne_date(ctx['now']), ctx['days'])[0]
    if repeat:
        b.append(repeat)
    if is_speculative(e) and ctx['speculative_this_week'] >= ctx['max_speculative']:
        b.append(f"this week's speculative enquiries are used up ({ctx['speculative_this_week']} of {ctx['max_speculative']} "
                 f"applied for, uncertain or started in {ctx['week']}, Melbourne time)")
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
    """Raise CapReached when the day's cap for this route, or the SEEK spacing, is already used up.

    Both count every APPLIED receipt, every UNCERTAIN entry (at its uncertain mark) and every start not yet marked.
    """
    limits = (config or {}).get('limits') or {}
    cap = limits.get(CAP_KEY[route])
    if not isinstance(cap, int):
        raise Refused(f'config.json -> limits -> {CAP_KEY[route]} is not set')
    group = [r for r in ROUTES if CAP_KEY[r] == CAP_KEY[route]]
    times = [t for t in (submission_time(e) for _, e in entries if e['route'] in group) if t]
    today = melbourne_date(now)
    done = sum(1 for t in times if melbourne_date(t) == today)
    if done >= cap:
        raise CapReached(f"{route}: the day's cap is reached ({done} of {cap} submitted on {today}, Melbourne date; uncertain "
                         'entries and starts not yet marked count). Stop until tomorrow.')
    gap = limits.get('min_minutes_between_seek_submissions') or 0
    if route == 'SEEK' and times and gap:
        minutes = (now - max(times)).total_seconds() / 60
        if minutes < gap:
            raise CapReached(f'SEEK: the last submission or start was {int(minutes)} minutes ago; wait {int(gap - minutes) + 1} more '
                             f'(at least {gap} minutes apart).')


def check_quiet_hours(config, now):
    """Raise CapReached during config.json -> limits -> quiet_hours ('HH:MM-HH:MM', Melbourne time; 21:00-07:00 when
    the key is not set)."""
    text = ((config or {}).get('limits') or {}).get('quiet_hours') or QUIET_HOURS
    m = re.fullmatch(r'\s*([01]?\d|2[0-3]):([0-5]\d)\s*-\s*([01]?\d|2[0-3]):([0-5]\d)\s*', str(text))
    if not m or m.group(1, 2) == m.group(3, 4):
        raise Refused(f'config.json -> limits -> quiet_hours: {text!r} is not HH:MM-HH:MM, Melbourne time (for example 21:00-07:00)')
    start, end = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
    local = now.astimezone(_melbourne())
    t = local.hour * 60 + local.minute
    if (start <= t < end) if start < end else (t >= start or t < end):
        until = f'{int(m[3]):02d}:{m[4]}'
        raise CapReached(f'no submissions between {int(m[1]):02d}:{m[2]} and {until} Melbourne time (config.json -> limits -> '
                         f'quiet_hours); it is {local:%H:%M} there now. Stop until {until}.')


# ---------- the send lock (EMAIL) ----------

def check_run_id(run):
    if not RUN_ID.fullmatch(str(run or '')):
        raise Refused(f'--run {run!r} is not a run id: give the id journal.py start printed, for example 20261114T0202Z')


def read_lock(qdir):
    """The send lock in qdir/SEND_LOCK.json, or None when there is none."""
    path = Path(qdir) / LOCK_FILE
    if not path.exists():
        return None
    lock = read_json(path)
    if not isinstance(lock, dict) or not all(lock.get(k) for k in ('by', 'run', 'taken_at', 'expires_at')):
        raise Refused(f'{path}: not a send lock {{by, run, taken_at, expires_at}}: remove it with git rm, commit and push')
    parse_time(lock['expires_at'])
    return lock


def lock_mine(lock, by, run):
    return bool(lock) and same_name(lock['by'], by) and lock['run'] == run


def take_lock(qdir, by, run, now=None, minutes=LOCK_MINUTES):
    """Take (or renew) the send lock for this runner and run. Returns (lock, note). Refused while another run holds
    an unexpired lock."""
    now = now or datetime.now(timezone.utc)
    if not str(by or '').strip():
        raise Refused('lock take needs --by NAME')
    check_run_id(run)
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 120:
        raise Refused('--minutes: a whole number from 1 to 120')
    lock, note = read_lock(qdir), ''
    if lock and not lock_mine(lock, by, run):
        if parse_time(lock['expires_at']) > now:
            raise Refused(f"the send lock is held by {lock['by']} (run {lock['run']}) until {lock['expires_at']}: do not send. "
                          'Try again after it expires or is released.')
        note = f"replaced the expired send lock of {lock['by']} (run {lock['run']}, expired {lock['expires_at']})"
    lock = {'by': ' '.join(by.split()), 'run': run, 'taken_at': iso(now), 'expires_at': iso(now + timedelta(minutes=minutes))}
    write_json(Path(qdir) / LOCK_FILE, lock)
    return lock, note


def release_lock(qdir, by, run):
    """Remove this runner's send lock. Returns the lock removed, or None when there was none."""
    if not str(by or '').strip():
        raise Refused('lock release needs --by NAME')
    check_run_id(run)
    lock = read_lock(qdir)
    if lock is None:
        return None
    if not lock_mine(lock, by, run):
        raise Refused(f"the send lock belongs to {lock['by']} (run {lock['run']}), not to {by} (run {run}): not released")
    (Path(qdir) / LOCK_FILE).unlink()
    return lock


def check_lock(qdir, by, run, now):
    """Refused unless this runner (by and run) holds the unexpired send lock: the EMAIL route needs it."""
    take = 'queue.py lock take --by NAME --run RUN_ID, commit and push it, then next --route EMAIL --by NAME --run RUN_ID'
    if not by or not run:
        raise Refused(f'EMAIL: next needs --by and --run, and that runner\'s own send lock: {take}')
    lock = read_lock(qdir)
    if lock is None:
        raise Refused(f'EMAIL: there is no send lock: {take}')
    if not lock_mine(lock, by, run):
        raise Refused(f"EMAIL: the send lock is held by {lock['by']} (run {lock['run']}), not by {by} (run {run}): do not send")
    if parse_time(lock['expires_at']) <= now:
        raise Refused(f"EMAIL: your send lock expired at {lock['expires_at']}: take it again and push it before sending")


def check_problems(entries, facts=None):
    """Every problem queue.py check reports, as (id, message) pairs. next hands nothing out while there is one."""
    out, seen, copies, waiting = [], {}, {}, []
    for path, e in entries:
        copies.setdefault(e['id'], []).append(path)
    for path, e in entries:
        problems = validate(e, facts)
        in_open = path.parent.name == 'open'
        if (e['status'] in IN_OPEN) != in_open:
            problems.append(f"status {e['status']} does not belong in {path.parent.name}/")
        if path.stem != e['id']:
            problems.append('file name is not the id')
        finished = [p for p in copies[e['id']] if p.parent.name != 'open']
        if in_open and finished:
            problems.append(f'a finished copy is in done/{finished[0].parent.name}/ and this copy in open/ is stale (the move to '
                            f'done/ was not committed whole): remove it with git rm {_rel(path)}, then commit and push')
        for key in sorted(advert_keys(e)):
            first, other = seen.setdefault(key, (path, e))
            open_and_done = other['id'] == e['id'] and (first.parent.name == 'open') != in_open   # named just above
            if first != path and not open_and_done:
                problems.append(f'duplicate of {first.name} ({key})')
        if e['status'] in OPEN_STATUSES:
            twin = next((o for o in waiting if same_job(o, e)), None)
            if twin:
                problems.append(f"same company and role as {twin['id']}, both waiting: mark one of them skipped")
            waiting.append(e)
        out += [(e['id'], msg) for msg in problems]
    return out


def resume_file(e):
    return RESUME_DIR / f"Marc_Masarate_Resume_{str(e.get('resume_variant') or '').capitalize()}.pdf"


def handout_notes(e, qdir, by=None):
    """What next prints on stderr after the entry: the resume file with its sha256, the checks to make before
    submitting, and with --by the git commands that commit and push the claim."""
    path = resume_file(e)
    shown = path.relative_to(ROOT.parent) if path.is_relative_to(ROOT.parent) else path
    lines = [f'RESUME: {shown} sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}' if path.exists()
             else f'RESUME: {shown} is missing: do not submit until it is built']
    if e.get('verify_before_submit'):
        lines += ['BEFORE SUBMITTING, CHECK:'] + [f'  - {c}' for c in e['verify_before_submit']]
    if by:
        lines += ['Commit and push this claim before you submit anything (run from this folder):',
                  '  ' + git_command([qdir], f"queue: {e['id']} started by {' '.join(by.split())}"),
                  'If a step fails (the push is rejected, or the pull stops on a conflict), another runner changed the queue '
                  'at the same time: do not submit; stop and report it.']
    return lines


def next_entry(route, qdir=QUEUE_DIR, config=None, now=None, by=None, prior=None, facts=None, run=None):
    """The single next entry to submit on this route. Raises Refused, CapReached or NothingToDo.

    prior is the list of applications made outside the queue (the entries of prior_outreach.json). Nothing is handed
    out while check_problems finds a problem, in the quiet hours, or (EMAIL) without this runner's send lock.
    """
    if route not in ROUTES:
        raise Refused(f'route: one of {", ".join(ROUTES)}')
    now = now or datetime.now(timezone.utc)
    entries = load(qdir)
    problems = check_problems(entries, facts)
    if problems:
        raise Refused(f'{route}: nothing is handed out while queue.py check finds problems ({len(problems)}). Run '
                      'python3 queue.py check, fix what it names, commit and push, then run next again:'
                      + ''.join(f'\n  {i}: {msg}' for i, msg in problems))
    check_quiet_hours(config, now)
    check_caps(route, entries, config, now)
    if route == 'EMAIL':
        check_lock(qdir, by, run, now)
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
    earlier = repeat_check(e, ctx['applied'], melbourne_date(now), ctx['days'])[1]
    if earlier and earlier not in e['notes']:
        e['notes'] = (e['notes'] + '\n' + earlier).strip()
    if by:
        e['attempts'].append({'at': iso(now), 'by': by, 'result': 'started', 'note': ''})
        save(qdir, e, path)
    return e


def uncertain_where(e):
    return {'SEEK': 'the applied jobs list on SEEK', 'EMAIL': 'Gmail Sent'}.get(e['route'], "the employer's confirmation email")


def mark(qdir, entry_id, action, by, now=None, kind=None, ref=None, at=None, note='', final=False, facts=None, thread=None):
    """Record what happened to an entry: applied, skipped, failed (known not to have gone), uncertain (unknown
    whether it went), linkout (SEEK's apply button leads to the employer's site: re-routed to EMPLOYER_PORTAL),
    ask (owner question) or open (back to OPEN; releases a start; settles an UNCERTAIN entry with "checked: ...")."""
    now = now or datetime.now(timezone.utc)
    path, e = find(qdir, entry_id, statuses=IN_OPEN)
    if not by:
        raise Refused('--by NAME is needed')
    already = validate(e, facts)   # a fault the file already had must not stop a real result from being recorded
    when = iso(parse_time(at)) if at else iso(now)
    note = ' '.join(str(note or '').split())
    start = started(e)
    if start and not same_name(start.get('by'), by) and action not in ('applied', 'uncertain'):
        raise Refused(f"{entry_id} was started by {start.get('by')} at {start.get('at')} and not marked: only {start.get('by')} "
                      'knows whether it went, so only that runner marks it open, failed, skipped, linkout or ask. Anyone else may '
                      'mark it applied (with the receipt) or uncertain.')
    if e['status'] == 'UNCERTAIN' and action not in ('applied', 'open'):
        raise Refused(f'{entry_id} is UNCERTAIN: check {uncertain_where(e)} first. If it went: mark {entry_id} applied --kind ... '
                      f'--ref ...; if it certainly did not: mark {entry_id} open --note "checked: not submitted (where you looked)"')
    if action == 'applied':
        if kind not in RECEIPT_KINDS or not ref:
            raise Refused(f'applied needs --ref and --kind (one of {", ".join(RECEIPT_KINDS)})')
        ref = ' '.join(str(ref).split()).lower() if kind == 'gmail_message_id' else ' '.join(str(ref).split())
        thread = str(thread or '').strip().lower() if kind == 'gmail_message_id' else str(thread or '').strip()
        problems = ref_problems(kind, ref, thread)
        if problems:
            raise Refused('not saved: ' + '; '.join(problems))
        e['status'], e['ask_owner'] = 'APPLIED', ''
        e['receipt'] = {'at': when, 'by': by, 'kind': kind, 'ref': ref, **({'thread': thread} if thread else {})}
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
        e['status'], e['ask_owner'] = 'UNCERTAIN', ''
    elif action == 'linkout':
        if e['route'] != 'SEEK':
            raise Refused(f"linkout is for a SEEK entry whose apply button leads to the employer's site; {entry_id} is on {e['route']}")
        e['route'] = 'EMPLOYER_PORTAL'
        note = note or "SEEK's apply button leads to the employer's site: re-routed to EMPLOYER_PORTAL"
    elif action == 'ask':
        if not note:
            raise Refused('ask needs --question')
        e['status'], e['ask_owner'] = 'ASK_OWNER', note
    elif action == 'open':
        if e['status'] == 'UNCERTAIN' and not re.match(r'checked:\s*\S', note, re.I):
            raise Refused(f'{entry_id} is UNCERTAIN: open it only after checking {uncertain_where(e)}, with --note "checked: not '
                          'submitted (where you looked)"; if it went, mark it applied with the receipt instead')
        if unanswered(e) and e['status'] != 'UNCERTAIN':
            raise Refused(f'{entry_id} still has an unanswered question: ' + question_ask(e))
        e['status'], e['ask_owner'] = ('ASK_OWNER', question_ask(e)) if unanswered(e) else ('OPEN', '')
    else:
        raise Refused(f'unknown action {action}')
    result = {'ask': 'asked_owner', 'open': 'reopened'}.get(action, action)
    e['attempts'].append({'at': when, 'by': by, 'result': result, 'note': note})
    problems = [x for x in validate(e, facts) if x not in already]
    if problems:
        raise Refused('not saved: ' + '; '.join(problems))
    save(qdir, e, path, finished_at=parse_time(when))
    return e


NOTE_RULE = (f'Write at most {NOTE_LIMIT} characters in your own words, for example "rejection email, no reason given". No names '
             'and no quotes (queue.py cannot detect a name or quoted text, so leave them out yourself), and no email address, '
             'phone number, number of 6 or more digits or web address: the queue is public.')


def record_outcome(qdir, entry_id, kind, at, by, note='', now=None, facts=None):
    """Add {kind, at, by, note} to the outcomes of an APPLIED or UNCERTAIN entry, open or done, in place.

    Returns (entry, False) without writing when the same kind on the same date is already recorded.
    """
    now = now or datetime.now(timezone.utc)
    path, e = find(qdir, entry_id)
    if e['status'] not in SUBMITTED:
        raise Refused(f"{entry_id} is {e['status']}: outcomes are recorded only on APPLIED or UNCERTAIN entries")
    if kind not in OUTCOME_KINDS:
        raise Refused(f'--kind: one of {", ".join(OUTCOME_KINDS)}')
    if not str(by or '').strip():
        raise Refused('--by NAME is needed')
    day = str(at or '').strip()
    try:
        ok = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)) and bool(datetime.strptime(day, '%Y-%m-%d'))
    except ValueError:
        ok = False
    if not ok:
        raise Refused(f'--at {at!r}: the date of the outcome, YYYY-MM-DD')
    if day > melbourne_date(now):
        raise Refused(f'--at {day} is later than today ({melbourne_date(now)} in Melbourne)')
    note = ' '.join(str(note or '').split())
    why = note_problems(note)
    if why:
        raise Refused('not saved: the note ' + '; '.join(why) + '. ' + NOTE_RULE)
    outcomes = [o for o in e.get('outcomes') or [] if isinstance(o, dict)]
    if any(o.get('kind') == kind and o.get('at') == day for o in outcomes):
        return e, False
    already = validate(e, facts)
    e['outcomes'] = outcomes + [{'kind': kind, 'at': day, 'by': ' '.join(by.split()), 'note': note}]
    problems = [x for x in validate(e, facts) if x not in already]
    if problems:
        raise Refused('not saved: ' + '; '.join(problems))
    write_json(path, fill(e))   # in place: an outcome does not move the entry
    return e, True


def expire(qdir=QUEUE_DIR, today=None, now=None):
    """Move every waiting entry whose closing date or stated closing time has passed to done as EXPIRED. Returns them.

    UNCERTAIN entries and entries started and not yet marked stay: they may have been submitted.
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
        if e['status'] in OPEN_STATUSES and not started(e) and closed(e, at):
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

STAT_LABELS = {'queue_open': 'waiting (OPEN, ready or held), queue_open', 'ask_owner_open': 'ask_owner', 'uncertain': 'uncertain'}


def stats(qdir=QUEUE_DIR, now=None):
    """Counts for the journal and the daily report. queue_open is status OPEN only (ready or held), by route."""
    now = now or datetime.now(timezone.utc)
    entries = [e for _, e in load(qdir)]
    week = {melbourne_date(now - timedelta(days=d)) for d in range(7)}
    is_open = [e for e in entries if e['status'] == 'OPEN']
    applied = [e for e in entries if e['status'] == 'APPLIED']
    return {
        'queue_open': {**{r: sum(1 for e in is_open if e['route'] == r) for r in ROUTES}, 'total': len(is_open)},
        'ask_owner_open': sum(1 for e in entries if e['status'] == 'ASK_OWNER'),
        'uncertain': sum(1 for e in entries if e['status'] == 'UNCERTAIN'),
        'applied_last_7_days': sum(1 for e in applied if e['receipt'].get('at') and melbourne_date(e['receipt']['at']) in week),
        'applied_total': len(applied),
        'expired_unsubmitted_total': sum(1 for e in entries if e['status'] == 'EXPIRED'),
        'open_with_letter_to_rewrite': sum(1 for e in is_open if REWRITE_MARK in e['notes']),
    }


STATES = {'VIC': 'Victoria', 'NSW': 'New South Wales', 'QLD': 'Queensland', 'WA': 'Western Australia', 'SA': 'South Australia',
          'TAS': 'Tasmania', 'ACT': 'Australian Capital Territory', 'NT': 'Northern Territory'}
STATE_CODES = re.compile(r'\b(' + '|'.join(STATES) + r')\b')
STATE_NAMES = re.compile(r'\b(' + '|'.join(STATES.values()) + r')\b')


def state_of(location):
    """The state a location names ('Townsville, Northern QLD' is QLD), or 'other'. A code goes before a full name, so
    'Victoria Park, Perth WA' is WA."""
    text = str(location or '')
    code, name = STATE_CODES.search(text), STATE_NAMES.search(text)
    return code.group(1) if code else next(c for c, n in STATES.items() if n == name.group(1)) if name else 'other'


def report(qdir=QUEUE_DIR, now=None, days=7):
    """Applications with a receipt in the last days Melbourne dates (today included), by lane, state and route; the
    outcomes dated in those days, by kind; and how many entries are UNCERTAIN now."""
    if not isinstance(days, int) or isinstance(days, bool) or days < 1:
        raise Refused('--days: a whole number, 1 or more')
    now = now or datetime.now(timezone.utc)
    entries = [e for _, e in load(qdir)]
    window = {melbourne_date(now - timedelta(days=d)) for d in range(days)}
    got = [e for e in entries if e['status'] == 'APPLIED' and e['receipt'].get('at') and melbourne_date(e['receipt']['at']) in window]
    outcomes = [o.get('kind') for e in entries for o in e.get('outcomes') or [] if isinstance(o, dict) and str(o.get('at') or '')[:10] in window]
    count = lambda names, values: {n: sum(1 for v in values if v == n) for n in names}
    return {'from': min(window), 'to': max(window), 'days': days, 'applied': len(got),
            'by_lane': count(LANES, [e['lane'] for e in got]),
            'by_state': count(tuple(STATES) + ('other',), [state_of(e['location']) for e in got]),
            'by_route': count(ROUTES, [e['route'] for e in got]),
            'outcomes': count(OUTCOME_KINDS, outcomes),
            'uncertain_now': sum(1 for e in entries if e['status'] == 'UNCERTAIN')}


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
    unsure = [e for e in entries if e['status'] == 'UNCERTAIN']
    if unsure:
        lines += ['', f'## Unknown whether it went ({len(unsure)})', '']
        lines += [f"- **{_cell(e['company'])}, {_cell(e['role'])}** ({e['route']}, `{e['id']}`, marked uncertain "
                  f"{iso(submission_time(e)) if submission_time(e) else ''}): check {uncertain_where(e)} before any retry, then "
                  f"`mark {e['id']} applied` with the receipt, or `mark {e['id']} open --note \"checked: ...\"`" for e in unsure]
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
    c = sub.add_parser('add', description=ADD_HELP, formatter_class=argparse.RawDescriptionHelpFormatter); c.add_argument('entry'); c.add_argument('--by')
    c = sub.add_parser('list'); c.add_argument('--route', choices=ROUTES); c.add_argument('--status', choices=STATUSES)
    c.add_argument('--all', action='store_true', help='include finished entries'); c.add_argument('--json', action='store_true')
    c.add_argument('--started', action='store_true', help='only entries with a start that no mark has followed: id, by, time')
    c = sub.add_parser('show'); c.add_argument('id')
    c = sub.add_parser('next'); c.add_argument('--route', required=True, choices=ROUTES); c.add_argument('--by')
    c.add_argument('--run', help='the run id of this tick (journal.py start); EMAIL needs it, with the send lock of --by and --run')
    c = sub.add_parser('mark'); c.add_argument('id'); c.add_argument('action', choices=('applied', 'skipped', 'failed', 'uncertain', 'linkout', 'ask', 'open'))
    c.add_argument('--by', required=True); c.add_argument('--kind', choices=RECEIPT_KINDS); c.add_argument('--ref'); c.add_argument('--at'); c.add_argument('--thread')
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
    c = sub.add_parser('outcome', description='Record an employer outcome on an APPLIED or UNCERTAIN entry. ' + NOTE_RULE)
    c.add_argument('id'); c.add_argument('--kind', required=True, choices=OUTCOME_KINDS)
    c.add_argument('--at', required=True, help='the date of the outcome, YYYY-MM-DD'); c.add_argument('--by', required=True)
    c.add_argument('--note', default='', help=f'at most {NOTE_LIMIT} characters, no names, no quotes, no contact details')
    c = sub.add_parser('lock', description='The send lock for the EMAIL route (automation/queue/SEND_LOCK.json).')
    c.add_argument('action', choices=('take', 'release', 'show')); c.add_argument('--by'); c.add_argument('--run')
    c.add_argument('--minutes', type=int, default=LOCK_MINUTES, help=f'how long the lock lasts (default {LOCK_MINUTES})')
    c = sub.add_parser('report'); c.add_argument('--days', type=int, default=7); c.add_argument('--json', action='store_true')
    return ap


ADD_HELP = 'Add one entry from a JSON file.\n\n' + __doc__[__doc__.index('Entry fields for add'):__doc__.index('\n\n', __doc__.index('Entry fields for add'))]


def _show(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def run(a):
    qdir, now = Path(a.dir), parse_time(a.now) if a.now else datetime.now(timezone.utc)
    config, facts = read_json(a.config), read_json(a.facts)

    def prior():   # read by the commands that need it; a missing or broken file is refused, not ignored
        data = read_json(a.prior)
        return (data.get('entries') if isinstance(data, dict) else data) or []
    if a.cmd == 'add':
        e = add(read_json(a.entry), qdir, facts, now, a.by, config, prior())
        print(f"added {e['id']} ({e['status']}, {e['route']}, {e['lane']})")
    elif a.cmd == 'list' and a.started:
        rows = [(e, started(e)) for _, e in load(qdir) if started(e) and (not a.route or e['route'] == a.route)]
        if a.json:
            return _show([{'id': e['id'], 'by': s.get('by'), 'at': s.get('at'), 'route': e['route']} for e, s in rows])
        for e, s in rows:
            print(f"{e['id']:<34} started by {s.get('by')} at {s.get('at')} ({e['route']})")
        if not rows:
            print('no unmarked starts')
    elif a.cmd == 'list':
        rows = [e for _, e in load(qdir) if (a.all or a.status or e['status'] in IN_OPEN)
                and (not a.route or e['route'] == a.route) and (not a.status or e['status'] == a.status)]
        rows.sort(key=lambda e: (e['status'] not in IN_OPEN, ROUTES.index(e['route']), sort_key(e, config)))
        if a.json:
            return _show(rows)
        for e in rows:
            print(f"{e['id']:<34} {e['status']:<9} {e['route']:<15} {e['lane']:<10} {e['closes_at'][:10] or '-':<10} {e['company']}: {e['role']}")
    elif a.cmd == 'show':
        _show(find(qdir, a.id)[1])
    elif a.cmd == 'next':
        e = next_entry(a.route, qdir, config, now, a.by, prior(), facts, a.run)
        _show(e)
        sys.stdout.flush()
        for line in handout_notes(e, qdir, a.by):
            print(line, file=sys.stderr)
    elif a.cmd == 'mark':
        e = mark(qdir, a.id, a.action, a.by, now, a.kind, a.ref, a.at, a.reason or a.note or a.question, a.final, facts, a.thread)
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
            print(f'{STAT_LABELS.get(k, k)}: ' + (', '.join(f'{r} {n}' for r, n in v.items()) if isinstance(v, dict) else str(v)))
    elif a.cmd == 'report':
        r = report(qdir, now, a.days)
        if a.json:
            return _show(r)
        line = lambda counts: ', '.join(f'{k} {n}' for k, n in counts.items())
        print(f"applications with a receipt, {r['from']} to {r['to']} ({r['days']} days, Melbourne dates): {r['applied']}")
        print('by lane: ' + line(r['by_lane']))
        print('by state: ' + line(r['by_state']))
        print('by route: ' + line(r['by_route']))
        print('outcomes dated in those days: ' + line(r['outcomes']))
        print(f"uncertain now (unknown whether they went): {r['uncertain_now']}")
    elif a.cmd == 'outcome':
        e, added = record_outcome(qdir, a.id, a.kind, a.at, a.by, a.note, now, facts)
        print(f"{e['id']}: {a.kind} on {a.at} " + ('recorded' if added else 'was already recorded'))
        if e['status'] == 'UNCERTAIN':
            print(f"{e['id']} is still UNCERTAIN: an employer reply shows it went, so mark it applied with the receipt")
    elif a.cmd == 'lock':
        if a.action == 'show':
            lock = read_lock(qdir)
            if not lock:
                return print('no send lock')
            _show(lock)
            left = (parse_time(lock['expires_at']) - now).total_seconds() / 60
            print(f"held by {lock['by']} (run {lock['run']}), {int(left)} minutes left" if left > 0
                  else f"expired at {lock['expires_at']}: anyone may take it")
            return
        path = qdir / LOCK_FILE
        if a.action == 'take':
            lock, note = take_lock(qdir, a.by, a.run, now, a.minutes)
            if note:
                print(note)
            print(f"send lock taken by {lock['by']} (run {lock['run']}) until {lock['expires_at']}. Commit and push it before "
                  'sending anything (run from this folder):')
            print('  ' + git_command([path], f"send lock: taken by {lock['by']}, run {lock['run']}"))
            print('If a step fails (the push is rejected, or the pull stops on a conflict), someone else holds the lock: do not send.')
        else:
            lock = release_lock(qdir, a.by, a.run)
            if not lock:
                return print('no send lock to release')
            print(f"send lock of {lock['by']} (run {lock['run']}) released. Commit and push (run from this folder):")
            print('  ' + git_command([path], f"send lock: released by {lock['by']}, run {lock['run']}"))
    elif a.cmd == 'check':
        entries = load(qdir)
        problems = check_problems(entries, facts)
        for entry_id, msg in problems:
            print(f'{entry_id}: {msg}')
        print(f'{len(entries)} entries, {len(problems)} problems')
        if problems:
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
