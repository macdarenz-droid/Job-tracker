#!/usr/bin/env python3
"""Live tracker client: Cloudflare D1 state through the Worker API.

Reads the shared state, builds the duplicate index, and writes Claude's records as
manual entries under the version guard (a stale write gets 409 and is retried from a
fresh read). Never touches applications, leads or record_visibility.

Usage:
  tracker.py state                       # print version and counts
  tracker.py index                       # print the duplicate index summary
  tracker.py check CANDIDATES.json       # annotate candidates with duplicate verdicts
  tracker.py add RECORDS.json            # append new Claude records (list of records)
  tracker.py update RECORD_ID PATCH.json # merge fields into one Claude record
  tracker.py upload FILE KIND            # upload a PDF/DOCX/PNG/JPG to R2 (kind: resume|cover|confirmation)
  tracker.py list [--mine]               # list manual entries (or only Claude's)
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

from common import CONFIG, http, norm, now_iso, read_json, write_json, eprint

API = CONFIG['tracker_api'].rstrip('/')
OUTREACH_STATUSES = re.compile(r'^(SENT|EOI_SENT|SENDING|SEND_UNCERTAIN|DELIVERY_FAILED|MANUAL_APPLIED\w*|APPLICATION_UNDER_REVIEW|INTERVIEW|OFFER|PREPARED_NOT_SENT|READY_\w+)$')
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


def record_date(r):
    for k in ('sent_at', 'applied_date', 'updated_at', 'checked_at', 'created_at'):
        v = r.get(k)
        if v:
            return str(v)[:10]
    return ''


def dedupe_index(state):
    """Everything a new record must not collide with."""
    idx = {'keys': set(), 'seek_ids': set(), 'url_keys': set(), 'company_role': set(), 'company': {}}
    rows = list(state.get('applications', [])) + list(state.get('leads', [])) + list(state.get('manual_entries', []))
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
        idx['company_role'].add(company_key(r.get('company')) + '|' + norm(r.get('role')))
        c = company_key(r.get('company'))
        if c:
            idx['company'].setdefault(c, []).append({'status': r.get('status', ''), 'date': record_date(r), 'role': r.get('role', ''), 'key': r.get('key') or r.get('id')})
    return idx


def check_duplicate(candidate, idx, repeat_block_days=None):
    """Returns (blocked, reason, notes). blocked=True means do not create a record."""
    days = repeat_block_days or CONFIG['limits']['repeat_block_days']
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
    sid = str(candidate.get('seek_id') or '') or (url_key(candidate.get('url') or candidate.get('job_url'))[5:] if url_key(candidate.get('url') or candidate.get('job_url')).startswith('seek:') else '')
    if sid and sid in idx['seek_ids']:
        return True, 'same SEEK job already in the tracker', []
    uk = url_key(candidate.get('url') or candidate.get('job_url'))
    if uk and not uk.startswith('seek:') and uk in idx['url_keys']:
        return True, 'same job URL already in the tracker', []
    cr = company_key(candidate.get('company')) + '|' + norm(candidate.get('title') or candidate.get('role'))
    if cr in idx['company_role']:
        return True, 'same company and role already in the tracker', []
    notes = []
    c = company_key(candidate.get('company'))
    priors = [p for key, rows in idx['company'].items() if same_company(key, c) for p in rows] if c else []
    for prior in priors:
        st = prior['status'] or ''
        if st in ('SENDING', 'SEND_UNCERTAIN'):
            return True, f"unresolved outreach to the same employer ({prior['role']} · {st})", []
        recent = prior['date'] >= cutoff if prior['date'] else False
        if OUTREACH_STATUSES.match(st) and recent:
            return True, f"recent outreach to the same employer ({prior['role']} · {st} · {prior['date']})", []
        if st == 'REJECTED' and recent:
            return True, f"recent rejection from the same employer ({prior['role']} · {prior['date']})", []
        notes.append(f"employer seen before: {prior['role']} · {st} · {prior['date']}")
    return False, 'new', notes


def new_record(fields, run_id=None):
    """Build a Claude manual entry. Caller supplies company, role, location, job_url, status and the rest."""
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
            blocked, why, _ = check_duplicate({'company': r['company'], 'title': r['role'], 'url': r.get('job_url'), 'seek_id': r.get('seek_id')}, idx)
            if blocked:
                skipped.append((r['id'], why))
                continue
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
                    raise RuntimeError('refusing to edit a record Claude did not create')
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
            print(f"{'DUP ' if blocked else 'new '} | {cnd.get('seek_id') or cnd.get('url')} | {cnd.get('company')} | {cnd.get('title') or cnd.get('role')} | {why}")
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
            print(f"{r['id']} | {r.get('contributor_name')} | {r.get('status')} | {r.get('company')} | {r.get('role')} | {r.get('job_url')} | {record_date(r)}")


if __name__ == '__main__':
    main()
