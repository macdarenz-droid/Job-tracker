#!/usr/bin/env python3
"""Append-only run journal (automation/journal.jsonl) and per-run folders (automation/runs/<run_id>/).

Usage:
  journal.py start                       # prints a new run id and creates its folder
  journal.py note RUN_ID KEY=VALUE ...   # append one JSON line
  journal.py last [N]                    # show the last N lines
  journal.py weekly [--json]             # totals per ISO week (Melbourne time) from the end rows

A row with stage=end is the tick's result and takes only these fields:
  queue_open            entries waiting in the apply queue when the tick ended
  applied               applications submitted WITH A RECEIPT since the last end row
  emails_sent, seek_submitted, portal_submitted    the same count, by route
  expired_unsubmitted   queue entries whose advert closed before anyone submitted
  replies, interviews   employer replies and interview requests read since the last end row
  new_adverts_screened, queued, rejected, ask_owner    what screening did with new adverts
  nothing_new           true when no new advert was found (a valid result)
  note                  free text (optional)
Every count is a whole number, or null when this runner could not check it (no Gmail: replies=null).
Any other field name is refused. Rows written before 13 Nov 2026 used new, prepared, ready, held
and sent; they are still read (weekly counts sent as emails_sent and applied) but cannot be written.
The stage is stored in lower case without spaces around it, so stage=END is an end row and is checked.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import CONFIG, ROOT, now_iso

JOURNAL = ROOT / 'journal.jsonl'
RUNS = ROOT / 'runs'
COUNTS = ('queue_open', 'applied', 'emails_sent', 'seek_submitted', 'portal_submitted', 'expired_unsubmitted',
          'replies', 'interviews', 'new_adverts_screened', 'queued', 'rejected', 'ask_owner')
END_FIELDS = COUNTS + ('nothing_new', 'note')
LEGACY_END_FIELDS = ('new', 'prepared', 'ready', 'held', 'sent')  # read only


def start():
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%MZ')
    (RUNS / run_id).mkdir(parents=True, exist_ok=True)
    note(run_id, stage='start')
    return run_id


def check_end_fields(fields):
    """Raise ValueError unless these are exactly the defined end-row fields with usable values."""
    allowed = ', '.join(END_FIELDS)
    unknown = sorted(k for k in fields if k not in END_FIELDS)
    if unknown:
        old = [k for k in unknown if k in LEGACY_END_FIELDS]
        hint = f" ({', '.join(old)}: old names, read from old rows only)" if old else ''
        raise ValueError(f"end row refused, unknown field(s): {', '.join(unknown)}{hint}. Allowed: {allowed}. Put anything else in note.")
    missing = [k for k in COUNTS + ('nothing_new',) if k not in fields]
    if missing:
        raise ValueError(f"end row refused, missing field(s): {', '.join(missing)}. Give every count (null when this runner could not check it). Allowed: {allowed}")
    for k in COUNTS:
        v = fields[k]
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            raise ValueError(f'end row refused: {k} must be a whole number or null, got {v!r}')
    if not isinstance(fields['nothing_new'], bool):
        raise ValueError(f"end row refused: nothing_new must be true or false, got {fields['nothing_new']!r}")


def note(run_id, **fields):
    if isinstance(fields.get('stage'), str):
        fields['stage'] = fields['stage'].strip().lower()  # 'END' or ' end' is an end row too, checked like one
    if fields.get('stage') == 'end':
        check_end_fields({k: v for k, v in fields.items() if k != 'stage'})
    line = {'run_id': run_id, 'at': now_iso(), **fields}
    with JOURNAL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')
    return line


def rows():
    """Every readable journal row. Lines that are not JSON objects (old merge-conflict markers) are skipped."""
    out = []
    if JOURNAL.exists():
        for line in JOURNAL.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def last(n=10):
    return rows()[-n:]


def iso_week(at):
    """'2026-W46' for a journal timestamp, in the owner's time zone."""
    when = datetime.fromisoformat(str(at).replace('Z', '+00:00'))
    try:
        from zoneinfo import ZoneInfo
        when = when.astimezone(ZoneInfo(CONFIG['schedule']['timezone']))
    except Exception:  # pragma: no cover - no tz database on this machine
        pass
    year, week, _ = when.isocalendar()
    return f'{year}-W{week:02d}'


def weekly(journal_rows=None):
    """Totals per ISO week from the end rows, oldest week first. queue_open is the week's last reading, not a sum."""
    weeks = {}
    for row in (rows() if journal_rows is None else journal_rows):
        if row.get('stage') != 'end' or not row.get('at'):
            continue
        w = weeks.setdefault(iso_week(row['at']), {'week': iso_week(row['at']), 'ticks': 0, **{k: 0 for k in COUNTS}, 'nothing_new': 0})
        w['ticks'] += 1
        if 'applied' not in row and isinstance(row.get('sent'), int) and not isinstance(row.get('sent'), bool):
            row = {**row, 'emails_sent': row['sent'], 'applied': row['sent']}  # old row: the only receipt it recorded was a sent email
        for k in COUNTS:
            v = row.get(k)
            if isinstance(v, int) and not isinstance(v, bool):
                w[k] = v if k == 'queue_open' else w[k] + v
        w['nothing_new'] += row.get('nothing_new') is True
    return [weeks[k] for k in sorted(weeks)]


def weekly_line(w):
    return (f"{w['week']}  ticks {w['ticks']}  applied {w['applied']} (seek {w['seek_submitted']}, email {w['emails_sent']}, portal {w['portal_submitted']})"
            f"  replies {w['replies']}  interviews {w['interviews']}  screened {w['new_adverts_screened']}  queued {w['queued']}"
            f"  rejected {w['rejected']}  ask_owner {w['ask_owner']}  expired_unsubmitted {w['expired_unsubmitted']}"
            f"  queue_open {w['queue_open']}  nothing_new {w['nothing_new']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('start')
    n = sub.add_parser('note'); n.add_argument('run_id'); n.add_argument('fields', nargs='*')
    l = sub.add_parser('last'); l.add_argument('n', nargs='?', type=int, default=10)
    w = sub.add_parser('weekly'); w.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'start':
        print(start())
    elif a.cmd == 'note':
        fields = {}
        for kv in a.fields:
            k, _, v = kv.partition('=')
            try:
                fields[k] = json.loads(v)
            except Exception:
                fields[k] = v
        try:
            print(json.dumps(note(a.run_id, **fields), ensure_ascii=False))
        except ValueError as e:
            sys.exit(str(e))
    elif a.cmd == 'weekly':
        for week in weekly():
            print(json.dumps(week) if a.json else weekly_line(week))
    else:
        for line in last(a.n):
            print(json.dumps(line, ensure_ascii=False))


if __name__ == '__main__':
    main()
