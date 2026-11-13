#!/usr/bin/env python3
"""Live tracker client: Cloudflare D1 state through the Worker API.

Reads the shared state, builds the duplicate index, and writes this runner's records as
manual entries under the version guard (a stale write gets 409 and is retried from a
fresh read). Never touches applications, leads or record_visibility.

Usage:
  tracker.py state                       # print version and counts
  tracker.py index                       # print the duplicate index summary
  tracker.py check CANDIDATES.json       # annotate candidates with duplicate verdicts
  tracker.py add RECORDS.json            # append new records (list of records)
  tracker.py update RECORD_ID PATCH.json # merge fields into one of this runner's records
  tracker.py upload FILE KIND            # upload a PDF/DOCX/PNG/JPG to R2 (kind: resume|cover|confirmation)
  tracker.py list [--mine]               # list manual entries (or only this runner's)

Duplicate rule (13 Nov 2026):
  1. The same SEEK id or the same URL is always a duplicate.
  2. The same employer AND the same role title is blocked for limits.repeat_block_days after a
     REAL submission or outcome (SUBMITTED below, and automation/prior_outreach.json), counted
     from the day it was sent or applied. An unresolved send (SENDING, SEND_UNCERTAIN) blocks
     that role until it is reconciled, whatever its date.
  3. A different role at an employer he applied to is allowed, with a note naming the earlier
     application. A speculative enquiry is not: it is blocked while any application to that
     employer is inside the window.
  4. A lead nobody submitted (LEAD, PREPARED_NOT_SENT, READY_*, HELD_*, ASK_OWNER, EXPIRED)
     blocks only its own advert (rule 1).
  Where the record does not say, the rule blocks: an application whose role is not on record
  ('employer portal application receipt', 'email to ...') counts as the same role, and a date
  that cannot be read counts as inside the window. A record's seek_id field counts as its SEEK
  id even when its job_url is the employer's own page (a SEEK link-out).
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import CONFIG, canonical_status, http, norm, now_iso, read_json, write_json, eprint

API = CONFIG['tracker_api'].rstrip('/')
# A real submission or its outcome. The loop's own unsubmitted leads are deliberately not here.
SUBMITTED = re.compile(r'^(SENT|EOI_SENT|SENDING|SEND_UNCERTAIN|DELIVERY_FAILED|MANUAL_APPLIED\w*|APPLICATION_UNDER_REVIEW|INTERVIEW|OFFER|REJECTED)$')
UNRESOLVED = ('SENDING', 'SEND_UNCERTAIN')
SEEK_ID = re.compile(r'seek\.com(?:\.au)?/job/(\d+)', re.I)
_code_cache = None


def access_code():
    global _code_cache
    if _code_cache:
        return _code_cache
    code = os.environ.get(CONFIG['code_env'], '').strip()
    if not code:
        p = Path(CONFIG['code_file'])
        if p.exists():
            code = p.read_text().strip()
    if not re.fullmatch(r'\d{6}', code or ''):
        raise SystemExit(f"Tracker code missing: set {CONFIG['code_env']} or write {CONFIG['code_file']}")
    _code_cache = code
    return code


def request(path, method='GET', data=None, headers=None, raw=False):
    return http(API + path, data=data, method=method, raw=raw,
                headers={'X-Tracker-Code': access_code(), **(headers or {})})


def get_state():
    status, body = request('/api/state')
    if status != 200 or 'state' not in body:
        raise RuntimeError(f'tracker read failed ({status}): {str(body)[:200]}')
    return body['version'], body['state']


def put_state(version, state):
    return request('/api/state', method='PUT', data={'expected_version': version, 'state': state},
                   headers={'Content-Type': 'application/json'})


def url_key(u):
    m = SEEK_ID.search(str(u or ''))
    if m:
        return 'seek:' + m.group(1)
    try:
        from urllib.parse import urlparse
        p = urlparse(str(u))
        if not p.hostname:
            return ''
        return p.hostname.lower().removeprefix('www.') + p.path.rstrip('/').lower()
    except Exception:
        return ''


COMPANY_NOISE = re.compile(r'\b(pty|ltd|limited|plc|inc|co|group|holdings|australia|aust|the|and|&)\b|\(.*?\)', re.I)


def company_key(name):
    """Normalise an employer name so 'Fortec Australia Pty Ltd' and 'Fortec Australia' collide."""
    return norm(COMPANY_NOISE.sub(' ', str(name or '')))


def same_company(a, b):
    a, b = company_key(a), company_key(b)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a)))


def role_words(title):
    """Words of a role title for comparison: bracketed notes dropped, plurals folded."""
    words = re.findall(r'[a-z0-9]+', re.sub(r'\(.*?\)', ' ', str(title or '').lower()))
    return [w[:-1] if len(w) > 3 and w.endswith('s') else w for w in words]


def same_role(a, b):
    """The same title, or one title is the other with something added at the end ('Graduate Civil Engineer - Wodonga')."""
    a, b = role_words(a), role_words(b)
    short, long = sorted((a, b), key=len)
    return bool(short) and (a == b or (len(short) >= 2 and long[:len(short)] == short))


# A role text that names no role: a receipt, or a note of how the application went in.
NO_ROLE = re.compile(r'receipt|position name|unknown|not (stated|shown|given|named|recorded)|application (received|via)|^(e-?mail|portal|employer portal)\b', re.I)


def role_unknown(title):
    """True when an earlier application's role is not on record, so nobody can say a new advert is a different role."""
    bare = re.sub(r'\(.*?\)', ' ', str(title or '')).strip()
    return not role_words(bare) or bool(NO_ROLE.search(bare))


def day(value):
    """'YYYY-MM-DD' for an ISO date or timestamp, or for a day-first date as Australians write it
    (12/11/2026); '' for no date; None for a date that cannot be read."""
    text = str(value or '').strip()
    if not text:
        return ''
    try:
        if re.match(r'\d{4}-\d{2}-\d{2}', text):
            return datetime.strptime(text[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
        m = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', text)
        if m:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime('%Y-%m-%d')
    except ValueError:
        pass
    return None


def record_date(r):
    for k in ('sent_at', 'applied_date', 'updated_at', 'checked_at', 'created_at'):
        v = r.get(k)
        if v:
            return str(v)[:10]
    return ''


def submitted_date(r):
    """The day an application went in, as written on the row: sent_at or the applied date. Never the day
    the lead was made; a submitted row with neither falls back to when it was last updated or checked."""
    for k in ('sent_at', 'applied_date', 'applied_at', 'updated_at', 'checked_at'):
        v = r.get(k)
        if v:
            return str(v)
    return ''


def prior_outreach():
    """Marc's own applications recorded from SEEK receipts (automation/prior_outreach.json)."""
    path = Path(__file__).resolve().parent.parent / 'prior_outreach.json'
    if not path.exists():
        return []
    return read_json(str(path)).get('entries', [])


def dedupe_index(state):
    """Everything a new record must not collide with."""
    idx = {'keys': set(), 'seek_ids': set(), 'url_keys': set(), 'company': {}}
    rows = list(state.get('applications', [])) + list(state.get('leads', [])) + list(state.get('manual_entries', []))
    for e in prior_outreach():
        c = company_key(e.get('company'))
        if c:
            idx['company'].setdefault(c, []).append({'status': 'MANUAL_APPLIED', 'submitted': True, 'date': str(e.get('date') or ''), 'role': e.get('role', ''), 'key': 'seek-receipt:' + str(e.get('gmail_message_id', ''))})
    for r in rows:
        for k in ('key', 'duplicate_key', 'origin_key'):
            if r.get(k):
                idx['keys'].add(str(r[k]))
                m = re.search(r'seek:(\d+)', str(r[k]))
                if m:
                    idx['seek_ids'].add(m.group(1))
        uk = url_key(r.get('job_url'))
        if uk.startswith('seek:'):
            idx['seek_ids'].add(uk[5:])
        elif uk:
            idx['url_keys'].add(uk)
        if str(r.get('seek_id') or '').strip():  # a SEEK link-out: the record's URL is the employer's page, the advert is still this SEEK job
            idx['seek_ids'].add(str(r['seek_id']).strip())
        c = company_key(r.get('company'))
        if c:
            status = str(r.get('status') or '').strip().upper()  # 'Sent' typed by hand is SENT
            submitted = bool(SUBMITTED.match(status))
            idx['company'].setdefault(c, []).append({'status': status, 'submitted': submitted, 'date': submitted_date(r) if submitted else record_date(r),
                                                     'role': r.get('role', ''), 'key': r.get('key') or r.get('id')})
    return idx


def check_duplicate(candidate, idx, repeat_block_days=None, today=None):
    """Returns (blocked, reason, notes). blocked=True means do not create a record. The rule is in the module docstring."""
    days = repeat_block_days or CONFIG['limits']['repeat_block_days']
    cutoff = ((today or datetime.now(timezone.utc)) - timedelta(days=days)).strftime('%Y-%m-%d')
    uk = url_key(candidate.get('url') or candidate.get('job_url'))
    sid = str(candidate.get('seek_id') or '') or (uk[5:] if uk.startswith('seek:') else '')
    if sid and sid in idx['seek_ids']:
        return True, 'same SEEK job already in the tracker', []
    if uk and not uk.startswith('seek:') and uk in idx['url_keys']:
        return True, 'same job URL already in the tracker', []
    c = company_key(candidate.get('company'))
    role = candidate.get('title') or candidate.get('role')
    speculative = candidate.get('application_type') == 'SPECULATIVE_ENQUIRY'
    notes = []
    for prior in [p for key, rows in idx['company'].items() if c and same_company(key, c) for p in rows]:
        st = canonical_status(prior['status'])
        if not prior.get('submitted'):
            notes.append(f"unsubmitted lead on file (does not block): {prior['role']} · {st}")
            continue
        when = day(prior['date'])
        inside = not when or when >= cutoff  # no date, or one that cannot be read, blocks
        what = f"{prior['role'] or 'role not recorded'} · {st} · {when or (str(prior['date'])[:20] + ' (date not readable)' if prior['date'] else 'no date')}"
        unknown = role_unknown(prior['role'])
        same = unknown or same_role(prior['role'], role)
        if same:
            if st in UNRESOLVED:
                return True, f'an earlier send for this role at this employer is unresolved ({what}); reconcile it first', []
            if inside and unknown:
                return True, f'already applied to this employer and the record does not say for which role ({what}); repeat block is {days} days', []
            if inside:
                return True, f'already applied for this role at this employer ({what}); repeat block is {days} days', []
        elif speculative and inside:
            return True, f'no speculative enquiry to an employer he applied to within {days} days ({what})', []
        notes.append(f'applied before, {"role not recorded" if unknown else "same role" if same else "different role, allowed"}{", outside the repeat block" if same else ""}: {what}')
    return False, 'new', list(dict.fromkeys(notes))


def new_record(fields, run_id=None):
    """Build this runner's manual entry. Caller supplies company, role, location, job_url, status and the rest."""
    rid = str(uuid.uuid4())
    ts = now_iso()
    rec = {
        'id': rid, 'key': 'manual:' + rid,
        'contributor_name': CONFIG['contributor_name'], 'created_by': CONFIG['created_by'],
        'record_kind': 'AUTOMATED_LEAD', 'run_id': run_id,
        'created_at': ts, 'updated_at': ts, 'version': 1, 'attachments': [],
    }
    rec.update({k: v for k, v in fields.items() if v is not None})
    for required in ('company', 'role', 'status'):
        if not rec.get(required):
            raise ValueError(f'record needs {required}')
    if not rec.get('duplicate_key'):
        uk = url_key(rec.get('job_url'))
        rec['duplicate_key'] = f"{norm(rec['company'])}|{uk if uk else norm(rec['role'])}"
    rec['attachments'] = list(rec.get('attachments') or [])
    if any(d.get('data_base64') for d in rec['attachments']):
        raise ValueError('upload attachments to R2 first')
    return rec


def _guarded(mutate, attempts=4):
    """Read → mutate(state) → PUT under the version guard; retry from a fresh read on 409."""
    last = None
    for i in range(attempts):
        version, state = get_state()
        outcome = mutate(state)
        if outcome is None:
            return {'version': version, 'unchanged': True}
        status, body = put_state(version, state)
        if status == 200:
            return {'version': body.get('version'), 'updated_at': body.get('updated_at'), 'result': outcome}
        last = (status, body)
        if status != 409:
            raise RuntimeError(f'tracker write rejected ({status}): {body}')
        time.sleep(1 + i)
    raise RuntimeError(f'tracker write kept conflicting: {last}')


def add_records(records):
    if any(r.get('preparation_only') for r in records):
        raise ValueError('dry-build records are not publishable; finish PDF verification and uploads first')

    def mutate(state):
        existing = {r['id'] for r in state['manual_entries']}
        fresh = [r for r in records if r['id'] not in existing]
        idx = dedupe_index(state)
        added, skipped = [], []
        for r in fresh:
            blocked, why, notes = check_duplicate({'company': r['company'], 'title': r['role'], 'url': r.get('job_url'), 'seek_id': r.get('seek_id'),
                                                   'application_type': r.get('application_type')}, idx)
            if blocked:
                skipped.append((r['id'], why))
                continue
            earlier = [n for n in notes if n.startswith('applied before') and n not in str(r.get('notes') or '')]
            if earlier:  # a different role at an employer he applied to: say so on the record
                r = {**r, 'notes': '\n'.join([str(r.get('notes') or '')] + earlier).strip()}
            state['manual_entries'].append(r)
            added.append(r['id'])
            # A later candidate in this same batch must see this accepted record.
            idx = dedupe_index(state)
        return {'added': added, 'skipped': skipped} if fresh else None
    return _guarded(mutate)


def update_record(record_id, patch, expect_status=None):
    def mutate(state):
        for r in state['manual_entries']:
            if r['id'] == record_id:
                if r.get('created_by') != CONFIG['created_by']:
                    raise RuntimeError(f"refusing to edit a record {CONFIG['created_by']} did not create")
                if expect_status and r.get('status') != expect_status:
                    raise RuntimeError(f"status is {r.get('status')}, expected {expect_status}")
                kept = list(r.get('attachments') or [])
                r.update({k: v for k, v in patch.items() if k not in ('id', 'key', 'created_at', 'created_by')})
                if 'attachments' in patch:
                    have = {d.get('id') or d.get('path') or d.get('sha256') for d in patch['attachments']}
                    r['attachments'] = kept + [d for d in patch['attachments'] if (d.get('id') or d.get('path') or d.get('sha256')) not in {k.get('id') or k.get('path') or k.get('sha256') for k in kept}]
                r['updated_at'] = now_iso()
                r['version'] = int(r.get('version') or 0) + 1
                return {'updated': record_id}
        raise RuntimeError(f'record {record_id} not found')
    return _guarded(mutate)


def upload_document(path, kind, filename=None):
    path = Path(path)
    if kind not in ('resume', 'cover', 'confirmation'):
        raise ValueError('kind must be resume, cover or confirmation')
    data = path.read_bytes()
    from urllib.parse import quote
    status, body = request('/api/documents', method='POST', data=data, headers={
        'Content-Type': 'application/octet-stream', 'X-Filename': quote(filename or path.name), 'X-Doc-Kind': kind})
    if status != 201:
        raise RuntimeError(f'upload failed ({status}): {body}')
    if body.get('sha256') != hashlib.sha256(data).hexdigest():
        raise RuntimeError('uploaded document hash does not match the exact local bytes; do not publish or send')
    return body


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('state'); sub.add_parser('index')
    c = sub.add_parser('check'); c.add_argument('candidates'); c.add_argument('--out')
    a = sub.add_parser('add'); a.add_argument('records')
    u = sub.add_parser('update'); u.add_argument('record_id'); u.add_argument('patch'); u.add_argument('--expect-status')
    up = sub.add_parser('upload'); up.add_argument('file'); up.add_argument('kind'); up.add_argument('--filename')
    ls = sub.add_parser('list'); ls.add_argument('--mine', action='store_true')
    args = ap.parse_args(argv)
    if args.cmd == 'state':
        v, s = get_state()
        print(json.dumps({'version': v, 'updated_at': s.get('updated_at'), **{k: len(s.get(k, [])) for k in ('applications', 'leads', 'manual_entries', 'record_visibility')}}))
    elif args.cmd == 'index':
        _, s = get_state(); idx = dedupe_index(s)
        print(json.dumps({'keys': len(idx['keys']), 'seek_ids': sorted(idx['seek_ids']), 'url_keys': sorted(idx['url_keys']), 'companies': len(idx['company'])}, indent=1))
    elif args.cmd == 'check':
        _, s = get_state(); idx = dedupe_index(s)
        data = read_json(args.candidates)
        cands = data['candidates'] if isinstance(data, dict) else data
        for cnd in cands:
            blocked, why, notes = check_duplicate(cnd, idx)
            cnd['duplicate'] = {'blocked': blocked, 'reason': why, 'notes': notes}
            print(f"{'DUP ' if blocked else 'new '} | {cnd.get('seek_id') or cnd.get('url')} | {cnd.get('company')} | {cnd.get('title') or cnd.get('role')} | {why}" + (' | ' + '; '.join(notes) if notes else ''))
        if args.out:
            write_json(args.out, data)
    elif args.cmd == 'add':
        recs = read_json(args.records)
        print(json.dumps(add_records(recs if isinstance(recs, list) else [recs]), indent=1))
    elif args.cmd == 'update':
        print(json.dumps(update_record(args.record_id, read_json(args.patch), args.expect_status), indent=1))
    elif args.cmd == 'upload':
        print(json.dumps(upload_document(args.file, args.kind, args.filename), indent=1))
    elif args.cmd == 'list':
        _, s = get_state()
        for r in s['manual_entries']:
            if args.mine and r.get('created_by') != CONFIG['created_by']:
                continue
            print(f"{r['id']} | {r.get('contributor_name')} | {canonical_status(r.get('status'))} | {r.get('company')} | {r.get('role')} | {r.get('job_url')} | {record_date(r)}")


if __name__ == '__main__':
    main()
