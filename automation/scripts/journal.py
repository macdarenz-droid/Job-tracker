#!/usr/bin/env python3
"""Append-only run journal (automation/journal.jsonl) and per-run folders (automation/runs/<run_id>/).

Usage:
  journal.py start                 # prints a new run id and creates its folder
  journal.py note RUN_ID KEY=VALUE ...   # append one JSON line
  journal.py last [N]              # show the last N lines
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, now_iso

JOURNAL = ROOT / 'journal.jsonl'
RUNS = ROOT / 'runs'


def start():
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%MZ')
    (RUNS / run_id).mkdir(parents=True, exist_ok=True)
    note(run_id, stage='start')
    return run_id


def note(run_id, **fields):
    line = {'run_id': run_id, 'at': now_iso(), **fields}
    with JOURNAL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')
    return line


def last(n=10):
    if not JOURNAL.exists():
        return []
    lines = JOURNAL.read_text(encoding='utf-8').strip().splitlines()
    return [json.loads(l) for l in lines[-n:]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('start')
    n = sub.add_parser('note'); n.add_argument('run_id'); n.add_argument('fields', nargs='*')
    l = sub.add_parser('last'); l.add_argument('n', nargs='?', type=int, default=10)
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
        print(json.dumps(note(a.run_id, **fields)))
    else:
        for line in last(a.n):
            print(json.dumps(line, ensure_ascii=False))


if __name__ == '__main__':
    main()
