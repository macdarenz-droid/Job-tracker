#!/usr/bin/env python3
"""Offline diagnostic; never loads common, credentials, network clients or live state.

python automation/scripts/health.py [--tracker-snapshot local-export.json]
Output is JSON on stdout. A snapshot is optional and is never presumed current.
Reported statuses/counters are not verified outcomes. Evidence-backed counts mean
only that an explicit status, date and receipt/reference coexist in the supplied
snapshot; this tool cannot authenticate those references against remote services.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def date(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def iso(value):
    return value.isoformat().replace('+00:00', 'Z') if value else None


def identifier(value):
    """Do not echo arbitrary journal strings even if labelled an ID."""
    value = str(value)
    if re.fullmatch(r'\d{8}T\d{4,6}Z(?:-[a-z0-9_-]{1,32})?', value):
        return value
    return 'sha256:' + hashlib.sha256(value.encode()).hexdigest()[:16]


def parse_journal(path):
    rows, issues = [], []
    conflict = False
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return [], [{'code': 'JOURNAL_UNREADABLE'}]
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith(('<<<<<<<', '|||||||', '=======', '>>>>>>>')):
            issues.append({'code': 'CONFLICT_MARKER', 'line': number})
            if line.lstrip().startswith('>>>>>>>'):
                conflict = False
            else:
                conflict = True
            continue
        if conflict:
            issues.append({'code': 'CONFLICT_CONTENT_EXCLUDED', 'line': number})
            # Validate for diagnosis only. Never ingest either conflicted branch.
            if line.strip():
                try:
                    json.loads(line)
                except (ValueError, RecursionError):
                    issues.append({'code': 'MALFORMED_CONFLICT_CONTENT', 'line': number})
            continue
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, RecursionError):
            issues.append({'code': 'MALFORMED_JSON', 'line': number})
            continue
        if not isinstance(row, dict) or not isinstance(row.get('run_id'), str) or not row['run_id']:
            issues.append({'code': 'INVALID_EVENT', 'line': number})
            continue
        if not date(row.get('at')):
            issues.append({'code': 'INVALID_EVENT_DATE', 'line': number})
            continue
        rows.append(row)
    if conflict:
        issues.append({'code': 'UNCLOSED_CONFLICT'})
    return rows, issues


def blockers(row):
    # Match locally, emit only fixed codes. Historical writers stored some notes
    # in keys, so scan both keys and values without exposing either in the report.
    text = json.dumps(row).lower().replace('_', ' ').replace('-', ' ')
    found = []
    if re.search(r'\b413\b', text):
        found.append('HTTP_413')
    if 'tracker full' in text:
        found.append('TRACKER_FULL')
    if ('lease' in text and any(s in text for s in (
            'no lease', 'skipped no lease', 'inaccessible', 'not acquired', 'unavailable', 'lease not', 'lease access'))):
        found.append('SKIPPED_NO_LEASE')
    return found


def _norm(value):
    return re.sub(r'[^a-z0-9]', '', value.lower()) if isinstance(value, str) else ''


def _url_key(value):
    # Retain identity-bearing query parameters (for example ?vid=123 on council
    # portals). Dropping every query can merge distinct vacancies at one path.
    if not isinstance(value, str):
        return ''
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return ''
        query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
                 if not key.lower().startswith('utm_')
                 and key.lower() not in ('gclid', 'fbclid', 'msclkid', 'tracking')]
        suffix = '?' + urlencode(sorted(query)) if query else ''
        return parsed.hostname.lower() + parsed.path.rstrip('/').lower() + suffix
    except ValueError:
        return ''


def _overlay_targets(manual, automatic):
    """Use the strongest available identity; names never broaden an exact match."""
    origin = manual.get('origin_key')
    if isinstance(origin, str) and origin.strip():
        return {origin} if origin in automatic else set()
    url = _url_key(manual.get('job_url'))
    names = (_norm(manual.get('company')), _norm(manual.get('role')))
    exact, fallback = set(), set()
    for key, row in automatic.items():
        row_url = _url_key(row.get('job_url'))
        # SEEK IDs have a known global namespace. A generic employer job_id does
        # not, so it cannot identify a vacancy independently of its URL/origin.
        id_pairs = [(manual.get('seek_id'), row.get('seek_id'))]
        id_pairs = [(str(a), str(b)) for a, b in id_pairs
                    if isinstance(a, (str, int)) and not isinstance(a, bool) and str(a).strip()
                    and isinstance(b, (str, int)) and not isinstance(b, bool) and str(b).strip()]
        # A contradictory stable ID or URL prevents a company/role fallback.
        if any(a != b for a, b in id_pairs):
            continue
        if any(a == b for a, b in id_pairs):
            exact.add(key)
            continue
        if url and row_url:
            if url == row_url:
                exact.add(key)
            continue
        if all(names) and names == (_norm(row.get('company')), _norm(row.get('role'))):
            fallback.add(key)
    return exact if exact else fallback


def effective_rows(state):
    """Follow allRows active semantics, resolving overlays by stable identity first.

    Unlike UI first-wins handling, conflicting copies or multiple manual overlays
    are excluded and counted. No history is altered and empty names/invalid URLs
    never match. Malformed overlays with identifiable originals exclude those
    originals as ambiguous, rather than revive stale pending records. Unlike the
    UI name fallback, explicit origins and distinct vacancy URLs cannot cross-match.
    """
    unique, manual_keys, conflicts = {}, set(), set()
    sources, malformed_overlays, conflicting_variants = {}, [], []
    stats = Counter({k: 0 for k in ('input_records', 'records_without_ids_excluded',
        'malformed_manual_records_excluded', 'duplicate_copies_suppressed',
        'overlapping_collection_copies_suppressed', 'malformed_overlay_automatic_records_excluded',
        'automatic_records_replaced', 'overlay_conflict_groups',
        'overlay_conflicting_records_excluded', 'inactive_records_excluded')})
    for group in ('applications', 'leads', 'manual_entries'):
        for r in state.get(group, []):
            stats['input_records'] += 1
            manual = group == 'manual_entries'
            key = r.get('key') or (('manual:' + str(r['id'])) if manual and r.get('id') else r.get('id'))
            if not isinstance(key, (str, int)) or isinstance(key, bool) or not key:
                stats['records_without_ids_excluded'] += 1
                if manual:
                    malformed_overlays.append(r)
                continue
            key = str(key)
            if manual:
                fields = ('origin_key', 'company', 'role', 'job_url', 'status')
                malformed = any(r.get(f) is not None and not isinstance(r[f], str) for f in fields)
                has_job_identity = (isinstance(r.get('origin_key'), str) and bool(r['origin_key'].strip())) or bool(_url_key(r.get('job_url'))) or bool(_norm(r.get('company')) and _norm(r.get('role')))
                if malformed or not has_job_identity or not isinstance(r.get('status'), str) or not r['status'].strip():
                    stats['malformed_manual_records_excluded'] += 1
                    malformed_overlays.append(r)
                    continue
                manual_keys.add(key)
            if key in unique:
                if sources[key] == 'applications' and group == 'leads':
                    stats['overlapping_collection_copies_suppressed'] += 1
                    continue
                if unique[key] != r:
                    conflicts.add(key)
                    if manual or key in manual_keys:
                        conflicting_variants.extend((unique[key], r))
                else:
                    stats['duplicate_copies_suppressed'] += 1
            unique[key] = r
            sources[key] = group
    automatic = {k: r for k, r in unique.items() if k not in manual_keys and k not in conflicts}
    manual = {k: r for k, r in unique.items() if k in manual_keys and k not in conflicts}
    # Keep all ambiguous overlays out of current counts, including the automatic
    # row they conflict over. This is not a claim that either history is wrong.
    targets = {k: _overlay_targets(r, automatic) for k, r in manual.items()}
    overlay_conflicts = {key for bad in malformed_overlays + conflicting_variants
                         for key in _overlay_targets(bad, automatic)}
    stats['malformed_overlay_automatic_records_excluded'] = len(overlay_conflicts)
    manual_items = list(manual.items())
    for i, (key, row) in enumerate(manual_items):
        for other, other_row in manual_items[i + 1:]:
            shared = targets[key] & targets[other]
            same_origin = row.get('origin_key') and row.get('origin_key') == other_row.get('origin_key')
            # Matching names alone do not make two manual applications compete:
            # distinct vacancies can legitimately share an employer and role.
            if shared or same_origin:
                stats['overlay_conflict_groups'] += 1
                overlay_conflicts.update((key, other))
                overlay_conflicts.update(targets[key] | targets[other])
    replaced = {target for key, matches in targets.items() if key not in overlay_conflicts
                for target in matches if target not in overlay_conflicts}
    stats['automatic_records_replaced'] = len(replaced)
    stats['overlay_conflicting_records_excluded'] = len(overlay_conflicts)
    visibility = {}
    visibility_conflicts = set()
    for entry in state.get('record_visibility', []):
        key = entry.get('record_key')
        if not isinstance(key, str) or type(entry.get('deleted')) not in (bool, int) or entry['deleted'] not in (0, 1):
            continue
        if key in visibility and visibility[key] != bool(entry['deleted']):
            visibility_conflicts.add(key)
        visibility[key] = bool(entry['deleted'])
    active = []
    for key, row in unique.items():
        if key in conflicts or key in overlay_conflicts or key in replaced or key in visibility_conflicts:
            continue
        if visibility.get(key) or row.get('status') in ('EXPIRED', 'SKIPPED_EXPIRED', 'SKIPPED_CLOSED', 'VACANCY_REMOVED'):
            stats['inactive_records_excluded'] += 1
            continue
        active.append(row)
    stats.update({'conflicting_record_ids_excluded': len(conflicts), 'distinct_record_ids': len(unique),
                  'conflicting_visibility_ids_excluded': len(visibility_conflicts), 'effective_active_records': len(active)})
    return active, dict(stats)


def _receipt_evidence(row):
    """Actual tracker schema: replies[].type/received_at/gmail_message_id.

    APPLICATION_ACKNOWLEDGEMENT confirms receipt, not a human response. Do not
    inspect prose, attachments or thread IDs as proof of a response/interview.
    """
    replies = row.get('replies', [])
    if not isinstance(replies, list):
        return set()
    return {reply.get('type') for reply in replies if isinstance(reply, dict)
            and isinstance(reply.get('type'), str) and date(reply.get('received_at'))
            and isinstance(reply.get('gmail_message_id'), str) and reply['gmail_message_id'].strip()}


def snapshot_counts(path):
    if path is None:
        return {'code': 'NO_SNAPSHOT', 'verified_against_live_services': False}
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError()
        state = data.get('state', data)
        if not isinstance(state, dict) or not any(k in state for k in ('applications', 'leads', 'manual_entries')):
            raise ValueError()
        for key in ('applications', 'leads', 'manual_entries', 'record_visibility'):
            group = state.get(key, [])
            if not isinstance(group, list) or any(not isinstance(r, dict) for r in group):
                raise ValueError()
    except (OSError, UnicodeError, ValueError, RecursionError):
        return {'code': 'SNAPSHOT_UNREADABLE_OR_INVALID', 'verified_against_live_services': False}
    records, stats = effective_rows(state)
    reported = Counter({k: 0 for k in ('ready', 'prepared', 'applied', 'under_review', 'sent', 'response', 'interview', 'other')})
    backed = Counter({k: 0 for k in ('applied', 'sent', 'response', 'interview')})
    specs = {
        'applied': (('APPLIED', 'MANUAL_APPLIED', 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED'), ('applied_date', 'applied_at'), ('application_receipt_id', 'submission_id')),
        'sent': (('SENT', 'EOI_SENT'), ('sent_at',), ('gmail_message_id', 'message_id')),
        'response': (('REPLIED', 'RESPONSE', 'RESPONSE_RECEIVED'), ('reply_at', 'response_at'), ('reply_message_id', 'response_message_id')),
        'interview': (('INTERVIEW', 'INTERVIEW_SCHEDULED', 'INTERVIEWED'), ('interview_at', 'interview_date'), ('interview_message_id', 'interview_event_id')),
    }
    for r in records:
        status = str(r.get('status', '')).upper()
        bucket = 'ready' if status.startswith('READY_') else 'prepared' if status == 'PREPARED_NOT_SENT' else 'under_review' if status == 'APPLICATION_UNDER_REVIEW' else 'other'
        supported = set()
        for name, (statuses, dates, refs) in specs.items():
            if status in statuses:
                bucket = name
                if any(date(r.get(d)) for d in dates) and any(isinstance(r.get(f), str) and r[f].strip() for f in refs):
                    supported.add(name)
        receipts = _receipt_evidence(r)
        if bucket in ('applied', 'under_review') and 'APPLICATION_ACKNOWLEDGEMENT' in receipts:
            supported.add('applied')
        # No human response/interview inference from an acknowledgement or from
        # APPLICATION_UNDER_REVIEW alone. Historical generic reference fields
        # above remain supported but are not required for the actual reply schema.
        if bucket == 'response' and 'HUMAN_REPLY' in receipts:
            supported.add('response')
        if bucket == 'interview' and 'INTERVIEW_INVITATION' in receipts:
            supported.add('interview')
        backed.update(supported)
        reported[bucket] += 1
    return {'code': 'LOCAL_SNAPSHOT_ONLY', 'snapshot_at': iso(date(state.get('updated_at'))),
            'verified_against_live_services': False, 'scope': 'ACTIVE_EFFECTIVE_ROWS',
            'acknowledgement_evidence_scope': 'RECEIPT_ONLY_NOT_HUMAN_RESPONSE_OR_SCREENING_COMPLETION',
            'reported_current_status_counts': dict(reported),
            'evidence_backed_current_status_counts': dict(backed), **stats}


def build_report(journal, config, snapshot=None, now=None, stale_hours=10, recent_hours=168, limit=10):
    now = now or datetime.now(timezone.utc)
    rows, issues = parse_journal(journal)
    try:
        cfg = json.loads(Path(config).read_text(encoding='utf-8'))
        if not isinstance(cfg, dict):
            raise ValueError()
    except (OSError, UnicodeError, ValueError):
        cfg = {}
        issues.append({'code': 'CONFIG_UNREADABLE_OR_INVALID'})
    # Exact known automation identities only; never print arbitrary contact data.
    identity = {}
    for field in ('contributor_name', 'created_by'):
        value = cfg.get(field)
        identity[field] = value if value in ('Grok AI', 'Claude', 'Codex', 'grok-job-search', 'claude-job-search', 'codex-job-search') else 'UNRECOGNIZED_OR_UNSET'
    schedule = cfg.get('schedule', {})
    cadence = schedule.get('every_hours') if isinstance(schedule, dict) else None
    identity['configured_every_hours'] = cadence if type(cadence) in (int, float) and 0 < cadence < 10000 else None
    identity['code'] = 'INFORMATIONAL_NOT_ATTRIBUTION_OR_LIVE_SCHEDULE_VERIFICATION'
    runs = {}
    for row in rows:
        runs.setdefault(row['run_id'], []).append(row)
    summaries, end_dates = [], []
    for rid, events in runs.items():
        ends = [r for r in events if r.get('stage') == 'end']
        latest = max(ends or events, key=lambda r: date(r['at']))
        if ends:
            end_dates.append(date(latest['at']))
        summary = {'run_id': identifier(rid), 'at': iso(date(latest['at'])),
                   'code': 'RECORDED_END' if ends else 'NO_RECORDED_END',
                   'end_event_count': len(ends), 'reported_counts': {}}
        for k in ('new', 'prepared', 'ready', 'sent', 'held', 'duplicates'):
            value = latest.get(k)
            if type(value) is int and value >= 0:
                summary['reported_counts'][k] = value
        summary['blocker_codes'] = sorted({code for r in events for code in blockers(r)})
        summaries.append(summary)
    latest_end = max(end_dates, default=None)
    cutoff = now - timedelta(hours=recent_hours)
    recent = [r for r in rows if cutoff <= date(r['at']) <= now]
    recent_codes = {code: len({r['run_id'] for r in recent if code in blockers(r)})
                    for code in ('HTTP_413', 'TRACKER_FULL', 'SKIPPED_NO_LEASE')}
    return {'schema_version': 1, 'generated_at': iso(now), 'mode': 'OFFLINE_READ_ONLY',
            'config': identity, 'journal': {'valid_events': len(rows), 'distinct_runs': len(runs), 'issues': issues},
            'runner': {'code': 'NO_RECORDED_END' if latest_end is None else 'FUTURE_END_DATE' if latest_end > now else 'STALE_RECORDED_END' if (now - latest_end).total_seconds() > stale_hours * 3600 else 'RECENT_RECORDED_END',
                       'last_end_at': iso(latest_end), 'stale_after_hours': stale_hours},
            'recent_blockers': {'window_hours': recent_hours, 'distinct_run_counts': recent_codes},
            'latest_distinct_runs': sorted(summaries, key=lambda r: r['at'], reverse=True)[:limit],
            'tracker': snapshot_counts(snapshot)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, default=ROOT / 'journal.jsonl')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.json')
    parser.add_argument('--tracker-snapshot', type=Path)
    parser.add_argument('--now', help='ISO timestamp, for reproducible offline reports')
    parser.add_argument('--stale-hours', type=float, default=10)
    parser.add_argument('--recent-hours', type=float, default=168)
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args(argv)
    if not (0 < args.stale_hours < 1e7 and 0 < args.recent_hours < 1e7 and args.limit > 0):
        parser.error('thresholds and limit must be positive and finite')
    now = date(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error('--now must be an ISO timestamp')
    print(json.dumps(build_report(args.journal, args.config, args.tracker_snapshot, now,
                                  args.stale_hours, args.recent_hours, args.limit), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
