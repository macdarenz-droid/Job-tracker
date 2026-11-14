#!/usr/bin/env python3
"""HTML version of a plain email body for the Gmail tool.

The Gmail connector rewrites every URL it finds, in the plain text and in every href, into a
google.com/url?q=... redirect that shows the reader a "Redirect Notice" page. It leaves the visible
text of an HTML anchor alone. So each email is sent with `body` (plain) and `htmlBody` built here:
the same words, HTML-escaped, line breaks kept, and every URL turned into an anchor whose visible
text is the clean address. The reader sees https://macdarenz-droid.github.io/Portfolio and the
click still reaches it (via the redirect page the connector adds).

Usage:
  email_html.py DRAFT.json        prints the HTML for draft['email_body'] (or a queue entry's email.body)
  email_html.py - < body.txt      prints the HTML for stdin
"""
import html
import json
import re
import sys

URL = re.compile(r'https?://[^\s<>"\')\]]+')
TRAIL = '.,;:!?'


def html_body(text):
    out = []
    pos = 0
    for m in URL.finditer(text):
        url = m.group(0)
        end = m.end()
        while url and url[-1] in TRAIL:  # a full stop after the link is prose, not the link
            url = url[:-1]; end -= 1
        out.append(html.escape(text[pos:m.start()]))
        out.append(f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>')
        pos = end
    out.append(html.escape(text[pos:]))
    body = ''.join(out).replace('\r\n', '\n').replace('\n', '<br>\n')
    return f'<div dir="auto">{body}</div>'


def email_text(draft):
    """The plain email body in a JSON file: email_body (a run-folder draft), email.body (an apply-queue entry) or a bare string."""
    if not isinstance(draft, dict):
        return draft
    email = draft.get('email') if isinstance(draft.get('email'), dict) else {}
    return draft.get('email_body') or email.get('body') or ''


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == '-':
        text = sys.stdin.read()
    else:
        with open(argv[0], encoding='utf-8') as f:
            text = email_text(json.load(f))
    print(html_body(text))


if __name__ == '__main__':
    main()
