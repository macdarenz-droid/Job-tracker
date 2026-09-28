"""Shared helpers for Claude's job-search loop. Standard library only."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
FACTS = json.loads((ROOT / 'facts.json').read_text(encoding='utf-8'))
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/128.0 Safari/537.36')


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def today_melbourne():
    """Date in Australia/Melbourne as YYYY-MM-DD (matches the tracker's Applied date)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('Australia/Melbourne')).strftime('%Y-%m-%d')
    except Exception:  # pragma: no cover
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def http(url, data=None, headers=None, method=None, timeout=40, raw=False):
    """HTTP request. Returns (status, body) where body is parsed JSON unless raw."""
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={'User-Agent': UA, 'Accept': 'application/json, text/html;q=0.9,*/*;q=0.8',
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        content = e.read()
        status = e.code
    if raw:
        return status, content
    try:
        return status, json.loads(content.decode('utf-8'))
    except Exception:
        return status, {'_raw': content.decode('utf-8', 'replace')[:2000]}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s or '').lower())


def slug(s):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', str(s or '').lower())).strip('-')


def strip_html(s):
    s = re.sub(r'(?i)<br\s*/?>', '\n', str(s or ''))
    s = re.sub(r'(?i)</(p|li|div|h\d|tr)>', '\n', s)
    s = re.sub(r'(?i)<li[^>]*>', '- ', s)
    s = re.sub(r'<[^>]+>', '', s)
    import html as _html
    s = _html.unescape(s)
    s = re.sub(r'[ \t\r\f\v]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


def eprint(*a):
    print(*a, file=sys.stderr)
