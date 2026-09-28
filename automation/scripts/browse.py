#!/usr/bin/env python3
"""Render a JavaScript page with headless Chromium and print its text and links.

Council and corporate careers portals (SmartRecruiters, SuccessFactors, PageUp, Workday, applynow,
pulse) are often empty shells without JavaScript, so curl and WebFetch see nothing. This runs the
pre-installed Chromium, waits for the page's scripts, and prints the rendered text plus the links.

Setup once per session (RUNBOOK §1): Chromium trusts the session proxy only after the proxy CA is
in the browser NSS store; `browse.py trust` does that (needs certutil from libnss3-tools).

Usage:
  browse.py trust                       # import the proxy CA into ~/.pki/nssdb (idempotent)
  browse.py text URL [--wait 20]        # rendered text (scripts and styles stripped)
  browse.py links URL [--match job]     # absolute links, optionally filtered by substring
  browse.py html URL                    # raw rendered DOM
"""
import argparse
import html as htmllib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urljoin

CHROME = os.environ.get('CHROME_BIN') or '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
NSSDB = os.path.expanduser('~/.pki/nssdb')
BUNDLE = '/root/.ccr/ca-bundle.crt'


def trust():
    """Import every Anthropic proxy CA from the session bundle into the browser NSS store."""
    if not shutil.which('certutil'):
        subprocess.run(['apt-get', 'install', '-y', '-q', 'libnss3-tools'], capture_output=True)
    if not shutil.which('certutil'):
        print('certutil missing: apt-get update && apt-get install -y libnss3-tools', file=sys.stderr)
        return 1
    os.makedirs(NSSDB, exist_ok=True)
    if not os.path.exists(os.path.join(NSSDB, 'cert9.db')):
        subprocess.run(['certutil', '-d', f'sql:{NSSDB}', '-N', '--empty-password'], check=True)
    have = subprocess.run(['certutil', '-d', f'sql:{NSSDB}', '-L'], capture_output=True, text=True).stdout
    pem = open(BUNDLE).read()
    added = 0
    for i, cert in enumerate(re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', pem, re.S)):
        subj = subprocess.run(['openssl', 'x509', '-noout', '-subject'], input=cert, capture_output=True, text=True).stdout
        if 'Anthropic' not in subj and 'CCR' not in subj:
            continue
        nick = f'ccr-proxy-{i}'
        if nick in have:
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.crt', delete=False) as f:
            f.write(cert)
        r = subprocess.run(['certutil', '-d', f'sql:{NSSDB}', '-A', '-t', 'C,,', '-n', nick, '-i', f.name], capture_output=True, text=True)
        os.unlink(f.name)
        added += r.returncode == 0
    print(f'proxy CAs added: {added}')
    return 0


def render(url, wait=20):
    """Rendered DOM after the page's scripts have had `wait` seconds of virtual time."""
    cmd = [CHROME, '--headless=new', '--no-sandbox', '--disable-gpu', '--dump-dom', f'--virtual-time-budget={int(wait) * 1000}',
           '--window-size=1280,3000', '--hide-scrollbars', url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=wait + 60)
    dom = r.stdout
    if 'ERR_CERT_AUTHORITY_INVALID' in dom:
        raise SystemExit('Chromium does not trust the proxy CA yet: run `browse.py trust` first')
    return dom


def text_of(dom):
    t = re.sub(r'<(script|style|noscript|svg)\b.*?</\1>', ' ', dom, flags=re.S | re.I)
    t = re.sub(r'<br\s*/?>|</(p|div|li|tr|h[1-6]|section|article)>', '\n', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = htmllib.unescape(t)
    t = re.sub(r'[ \t\r\f\v]+', ' ', t)
    return re.sub(r'\n\s*\n+', '\n', t).strip()


def links_of(dom, base, match=None):
    out = []
    for href, label in re.findall(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', dom, flags=re.S | re.I):
        absolute = urljoin(base, htmllib.unescape(href))
        label = re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', ' ', label))).strip()
        if match and match.lower() not in (absolute + ' ' + label).lower():
            continue
        if absolute not in [o[0] for o in out]:
            out.append((absolute, label))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('trust')
    for name in ('text', 'links', 'html'):
        p = sub.add_parser(name); p.add_argument('url'); p.add_argument('--wait', type=int, default=20)
        if name == 'links':
            p.add_argument('--match')
    a = ap.parse_args(argv)
    if a.cmd == 'trust':
        return trust()
    dom = render(a.url, a.wait)
    if a.cmd == 'html':
        print(dom)
    elif a.cmd == 'text':
        print(text_of(dom))
    else:
        for href, label in links_of(dom, a.url, a.match):
            print(f'{href}\t{label}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
