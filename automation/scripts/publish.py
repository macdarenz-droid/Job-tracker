#!/usr/bin/env python3
"""Turn a run's verified drafts into tracker records: render the cover letter, upload both PDFs,
build the Claude record, run the pre-send checks, and add everything under the version guard.

Usage:
  publish.py build RUN_ID [--only ID ...]     # drafts + screen + contacts → runs/RUN_ID/records.json (no uploads)
  publish.py go RUN_ID [--only ID ...]        # build, render PDFs, upload to R2, add to the tracker
  publish.py held RUN_ID                      # add HELD_ records for screened adverts with a mandatory problem

A draft is published as PREPARED_NOT_SENT when its contact is a published direct address or an
inbox that accepts applications; otherwise as READY_JEREMIE_SEEK / READY_JEREMIE_EMPLOYER_PORTAL
with the screening answers and checklist. Records that fail checks.py are written to
runs/RUN_ID/rejected.json and not added.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import ROOT, REPO, CONFIG, FACTS, now_iso, read_json, write_json, slug, eprint
import tracker
import checks
import render_pdf

STATUSES = CONFIG['statuses']


def load_run(run_id):
    run = ROOT / 'runs' / run_id
    cands = {}
    cfile = run / 'candidates.json'
    if cfile.exists():
        for c in read_json(cfile).get('candidates', []):
            cands[str(c.get('seek_id'))] = c
    for extra in (run / 'extra').glob('*.json'):
        if extra.name.startswith('_'):
            continue
        try:
            c = read_json(extra)
            cands[str(c.get('id') or extra.stem)] = c
        except Exception:
            pass
    screens = {p.stem: read_json(p) for p in (run / 'screen').glob('*.json')}
    contacts = {p.stem: read_json(p) for p in (run / 'contacts').glob('*.json')}
    drafts = {p.stem: read_json(p) for p in (run / 'drafts').glob('*.json')}
    return run, cands, screens, contacts, drafts


def route_status(draft, contact):
    conf = (contact or {}).get('contact_confidence') or 'none'
    route = (draft.get('route') or '').upper()
    email = draft.get('recipient_email') or (contact or {}).get('recipient_email') or ''
    if email and conf in ('published_direct', 'published_inbox'):
        if route in ('SEEK', 'EMPLOYER_PORTAL', 'EMPLOYER_FORM'):
            # Double touch: the portal pack is the primary record; the email waits until Applied.
            return {'SEEK': STATUSES['ready_seek'], 'EMPLOYER_PORTAL': STATUSES['ready_portal'], 'EMPLOYER_FORM': STATUSES['ready_form']}[route], route, 'double_touch'
        return STATUSES['prepared'], 'EMAIL', 'email'
    if route == 'EMPLOYER_FORM':
        return STATUSES['ready_form'], route, 'portal'
    if route == 'EMPLOYER_PORTAL':
        return STATUSES['ready_portal'], route, 'portal'
    return STATUSES['ready_seek'], 'SEEK', 'portal'


COMMON_CALL_QUESTIONS = [
    "What are your work rights? → Subclass 485 visa, full working rights until December 2027.",
    "Tell me about your site experience. → About a year in the Philippines, 2019 to 2020: project-in-charge on a community hall renovation (10 to 15 workers a day, drawing reviews, inspections, quality checks), then field engineer on subdivision finishing works (site reports, material records, procurement, coordinating with engineers and suppliers).",
    "What did you study in Australia? → Advanced Diploma of Civil Construction Design, Albright Institute, February 2024 to February 2026: road geometry, earthworks, pavement and stormwater drainage, drawings in AutoCAD and Civil 3D to Australian Standards, Before You Dig Australia enquiries.",
    "Which software do you use? → AutoCAD 2D and 3D, Civil 3D, Revit (coursework), Microsoft Office, Google Workspace. Say plainly that drafting experience is from study, not a paid job.",
    "Do you have a licence, White Card, transport? → Yes to all three; also a Working with Children Check.",
    "When could you start, and what salary? → Answer honestly; nothing was promised in the application.",
]


def how_found(cand, screen, contact, route, mode):
    src = (cand.get('source') or 'seek')
    listed = (cand.get('listed_at') or '')[:10]
    expires = (cand.get('expires_at') or screen.get('expires_at') or '')[:10]
    parts = [f"Found on {'SEEK' if src == 'seek' else src} (listed {listed or 'date not shown'}{', closes ' + expires if expires else ''})."]
    conf = (contact or {}).get('contact_confidence') or 'none'
    if conf == 'published_direct':
        parts.append(f"Contact: {contact.get('recipient_name')} ({contact.get('recipient_role')}), whose work email the employer publishes at {contact.get('contact_evidence_url')}.")
    elif conf == 'published_inbox':
        parts.append(f"Contact: the application inbox {contact.get('recipient_email')} published by the employer ({contact.get('contact_evidence_url')}); no personal address was used.")
    else:
        parts.append("No published email for a hiring person; the application goes through the employer's portal or SEEK.")
    if (contact or {}).get('named_people'):
        parts.append('Named people seen on employer pages: ' + '; '.join(f"{p.get('name')} ({p.get('role')})" for p in contact['named_people'][:3]) + '.')
    parts.append({'email': 'Sent by email from macdarenz@gmail.com once Marc\'s Gmail is connected; recorded as SENT with the Gmail id.',
                  'double_touch': 'Marc or Jeremie submits through the portal or SEEK first; the short email to the contact goes only after Applied is pressed.',
                  'portal': 'Marc or Jeremie submits through the portal or SEEK using the pack on this record.'}[mode])
    return ' '.join(parts)


def call_prep(draft, screen):
    q = [f"How did you find us? → Your advert for the {draft.get('role') or screen.get('title')} role" + (" on SEEK." if (screen.get('source') or 'seek') == 'seek' else " on your website.")]
    for gap in (screen.get('gaps') or [])[:3]:
        q.append(f"They may ask about: {gap} → answer honestly from the facts; nothing beyond them was claimed.")
    return q + COMMON_CALL_QUESTIONS


def how_found_block(cand, screen, contact, draft, route, mode):
    return 'HOW CLAUDE FOUND THIS\n' + how_found(cand, screen, contact, route, mode) + '\n\nIF THEY CALL, LIKELY QUESTIONS\n' + '\n'.join('• ' + x for x in call_prep(draft, screen))


def build_record(run_id, cand, screen, contact, draft, attachments=None):
    status, route, mode = route_status(draft, contact)
    method = {'EMAIL': 'Email', 'SEEK': 'SEEK', 'EMPLOYER_PORTAL': 'Company website', 'EMPLOYER_FORM': 'Company website'}[route]
    email = draft.get('recipient_email') or (contact or {}).get('recipient_email') or ''
    fields = {
        'company': draft.get('company') or cand.get('company'),
        'role': draft.get('role') or cand.get('title'),
        'location': draft.get('location') or cand.get('location') or '',
        'job_url': draft.get('job_url') or cand.get('url') or cand.get('job_url') or '',
        'company_url': (contact or {}).get('company_url') or '',
        'status': status,
        'application_type': draft.get('application_type') or 'ADVERTISED_VACANCY',
        'application_route': route,
        'application_method': method,
        'recipient_name': draft.get('recipient_name') or (contact or {}).get('recipient_name') or '',
        'recipient_role': draft.get('recipient_role') or (contact or {}).get('recipient_role') or '',
        'recipient_email': email,
        'contact_email': email,
        'contact_evidence_url': draft.get('contact_evidence_url') or (contact or {}).get('contact_evidence_url') or '',
        'contact_verified_at': now_iso() if email else '',
        'contact_confidence': (contact or {}).get('contact_confidence') or 'none',
        'subject': draft.get('subject') or '',
        'email_body': draft.get('email_body') or '',
        'fit': screen.get('rationale') or '',
        'gaps': screen.get('gaps') or [],
        'match_score': {'percent': screen.get('percent'), 'method': CONFIG['fit']['method'], 'rationale': screen.get('rationale') or '', 'caution': screen.get('caution') or ''},
        'advert': {'source': cand.get('source') or 'seek', 'listed_at': cand.get('listed_at') or screen.get('listed_at') or '', 'expires_at': cand.get('expires_at') or screen.get('expires_at') or '',
                   'verified_at': cand.get('checked_at') or now_iso(), 'apply_instructions': screen.get('apply_instructions') or '', 'screening_questions': cand.get('screening_questions') or screen.get('screening_questions') or []},
        'screening_answers': draft.get('screening_answers') or [],
        'checklist': draft.get('checklist') or [],
        'notes': '\n'.join(x for x in [draft.get('notes'), (contact or {}).get('notes'), 'Double touch: email the contact only after this record is marked Applied.' if mode == 'double_touch' else '', how_found_block(cand, screen, contact, draft, route, mode)] if x),
        'how_found': how_found(cand, screen, contact, route, mode),
        'call_prep': call_prep(draft, screen),
        'checked_at': now_iso(),
        'seek_id': cand.get('seek_id') if cand.get('source', 'seek') == 'seek' else None,
        'attachments': attachments or [],
    }
    return tracker.new_record(fields, run_id=run_id)


def held_record(run_id, cand, screen):
    reason = (screen.get('mandatory_unmet') or ['advert closed'])[0]
    tag = re.sub(r'[^A-Z0-9]+', '_', reason.upper())[:40].strip('_') or 'CHECK'
    return tracker.new_record({
        'company': screen.get('company') or cand.get('company'), 'role': screen.get('title') or cand.get('title'),
        'location': screen.get('location') or cand.get('location') or '', 'job_url': screen.get('url') or cand.get('url') or '',
        'status': f"{STATUSES['held_prefix']}{tag}", 'application_type': 'ADVERTISED_VACANCY', 'application_route': screen.get('route') or 'SEEK',
        'fit': screen.get('rationale') or '', 'gaps': (screen.get('mandatory_unmet') or []) + (screen.get('gaps') or []),
        'match_score': {'percent': screen.get('percent'), 'method': CONFIG['fit']['method'], 'rationale': screen.get('rationale') or '', 'caution': screen.get('caution') or ''},
        'notes': 'Held by Claude: ' + '; '.join(screen.get('mandatory_unmet') or ['advert not open']),
        'checked_at': now_iso(), 'seek_id': cand.get('seek_id') if cand.get('source', 'seek') == 'seek' else None,
    }, run_id=run_id)


def pdf_names(rec):
    co = re.sub(r'[^A-Za-z0-9]+', '_', rec['company']).strip('_')[:40]
    role = re.sub(r'[^A-Za-z0-9]+', '_', rec['role']).strip('_')[:40]
    return f'Marc_Masarate_{co}_{role}_Cover_Letter.pdf', f'Marc_Masarate_{co}_Resume.pdf'


def publish(run_id, only=None, go=False):
    run, cands, screens, contacts, drafts = load_run(run_id)
    records, rejected = [], []
    for sid, draft in sorted(drafts.items()):
        if only and sid not in only:
            continue
        cand, screen, contact = cands.get(sid, {}), screens.get(sid, {}), contacts.get(sid, {})
        if not screen:
            rejected.append({'seek_id': sid, 'why': 'no screen file'}); continue
        letter = draft.get('letter') or {}
        rec = build_record(run_id, cand, screen, contact, draft)
        cover_name, resume_name = pdf_names(rec)
        cover_pdf = run / cover_name
        if go:
            render_pdf.render_letter({**letter, 'date': None}, cover_pdf)
            up_cover = tracker.upload_document(cover_pdf, 'cover', cover_name)
            up_resume = tracker.upload_document(render_pdf.resume_pdf(), 'resume', resume_name)
            rec['attachments'] = [{**up_resume, 'kind': 'resume'}, {**up_cover, 'kind': 'cover'}]
        else:
            rec['attachments'] = [{'kind': 'resume', 'filename': resume_name, 'stored_in': 'cloudflare_r2', 'sha256': 'pending'}, {'kind': 'cover', 'filename': cover_name, 'stored_in': 'cloudflare_r2', 'sha256': 'pending'}]
        issues = checks.record_issues(rec)
        letter_text = '\n'.join(letter.get('paragraphs') or [])
        issues += ['letter ' + i for i in checks.tone_issues(letter_text, 'letter') + checks.fact_issues(letter_text)]
        if issues:
            rejected.append({'seek_id': sid, 'status': rec['status'], 'issues': issues}); continue
        records.append(rec)
    write_json(run / 'records.json', records)
    write_json(run / 'rejected.json', rejected)
    result = {'built': [(r['id'], r['company'], r['role'], r['status']) for r in records], 'rejected': rejected}
    if go and records:
        result['tracker'] = tracker.add_records(records)
    return result


def publish_held(run_id):
    run, cands, screens, contacts, drafts = load_run(run_id)
    recs = []
    for sid, screen in sorted(screens.items()):
        if sid in drafts or screen.get('percent', 0) < CONFIG['fit']['threshold_percent']:
            continue
        if screen.get('open') and not screen.get('mandatory_unmet'):
            continue
        recs.append(held_record(run_id, cands.get(sid, {}), screen))
    write_json(run / 'held.json', recs)
    return tracker.add_records(recs) if recs else {'unchanged': True, 'held': 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('build', 'go'):
        s = sub.add_parser(name); s.add_argument('run_id'); s.add_argument('--only', nargs='*')
    h = sub.add_parser('held'); h.add_argument('run_id')
    a = ap.parse_args(argv)
    if a.cmd in ('build', 'go'):
        print(json.dumps(publish(a.run_id, set(a.only or []) or None, go=(a.cmd == 'go')), indent=1, ensure_ascii=False))
    else:
        print(json.dumps(publish_held(a.run_id), indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
