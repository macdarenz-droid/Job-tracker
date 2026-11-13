#!/usr/bin/env python3
"""Turn a run's verified drafts into tracker records: render the cover letter, upload both PDFs,
build the record, run the checks, and add everything under the version guard.

Usage:
  publish.py build RUN_ID [--only ID ...]     # drafts + screen + contacts → runs/RUN_ID/records.json (no uploads)
  publish.py go RUN_ID [--only ID ...]        # build, render PDFs, upload to R2, add to the tracker

One application per advert, through the one channel the draft names in "route": EMAIL, SEEK,
EMPLOYER_PORTAL or EMPLOYER_FORM. Any other route text is refused. A draft with no route goes by email
when it carries a recipient_email, to SEEK when the advert is a SEEK job, and is refused otherwise; an
email application is never turned into a SEEK one. Status of a built record (names from config -> statuses):
  PREPARED_NOT_SENT    route EMAIL; refused unless the employer publishes the address (a direct contact or
                       an application inbox, from the contacts file)
  READY_SEEK, READY_EMPLOYER_PORTAL, READY_EMPLOYER_FORM    the advert takes applications there; no email is added
  ASK_OWNER            a form question has no standing answer in facts.json -> answers, or the screen left a
                       mandatory fact unresolved; the record carries the question(s) in ask_owner and the
                       status it takes once they are answered
Form answers on a record are the lines of facts.json -> answers, never the drafter's own wording: each is
{question, answer, basis}. A question with no standing answer is kept as {question, draft_answer} on an
ASK_OWNER record, so the owner sees what the drafter proposed.
Records made before 13 Nov 2026 say READY_JEREMIE_*; common.canonical_status reads them as READY_*.
An advert with an unmet mandatory requirement gets no record (config -> fit -> decisions: REJECT; there
is no HELD state for new adverts, so the old `held` command is gone). Drafts that fail a check are
written to runs/RUN_ID/rejected.json and not added.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import ROOT, REPO, CONFIG, FACTS, now_iso, read_json, write_json, slug, eprint
import tracker
import checks
import render_pdf

STATUSES = CONFIG['statuses']
LIMITS = CONFIG['limits']
READY = {'SEEK': STATUSES['ready_seek'], 'EMPLOYER_PORTAL': STATUSES['ready_portal'], 'EMPLOYER_FORM': STATUSES['ready_form']}


def eligibility_issues(cand, screen, draft=None):
    """Fail closed before rendering or uploading. Human review still reads the full advert."""
    issues = []
    speculative = (draft or {}).get('application_type') == 'SPECULATIVE_ENQUIRY'
    if speculative and (screen.get('company_work_verified') is not True or (draft or {}).get('vacancy_status') != 'NO_ADVERTISED_VACANCY_VERIFIED'):
        issues.append('speculative enquiry needs verified company work and an explicit no-advertised-vacancy label')
    if not speculative and (screen.get('open') is not True or cand.get('is_expired') is True):
        issues.append('current open advert not verified')
    if screen.get('mandatory_unmet') != []:
        issues.append('a mandatory requirement is unmet or was not checked')
    percent = screen.get('percent')
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not CONFIG['fit']['threshold_percent'] <= percent <= 100:
        issues.append('fit is below the threshold or invalid')
    expiry = None if speculative else cand.get('expires_at') or screen.get('expires_at')
    if expiry:
        try:
            when = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
            if when.tzinfo is None or when <= datetime.now(timezone.utc):
                issues.append('advert expiry is past or has no timezone')
        except (ValueError, TypeError):
            issues.append('advert expiry cannot be verified')
    return issues


def speculative_this_week(run_id):
    """Speculative enquiries built in the seven days up to this run, counted from the other run folders' records.json."""
    try:
        day = datetime.strptime(str(run_id)[:8], '%Y%m%d')
    except ValueError:
        return 0
    count = 0
    for path in (ROOT / 'runs').glob('*/records.json'):
        name = path.parent.name
        try:
            other = datetime.strptime(name[:8], '%Y%m%d')
        except ValueError:
            continue
        if name == run_id or not day - timedelta(days=6) <= other <= day:
            continue
        try:
            count += sum(1 for r in read_json(path) if isinstance(r, dict) and r.get('application_type') == 'SPECULATIVE_ENQUIRY')
        except Exception:
            pass
    return count


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


def on_seek(cand, draft):
    """True when the advert is a SEEK job: a SEEK id on a SEEK candidate, or a SEEK job URL."""
    url = draft.get('job_url') or cand.get('url') or cand.get('job_url') or ''
    return bool(cand.get('seek_id')) and (cand.get('source') or 'seek') == 'seek' or tracker.url_key(url).startswith('seek:')


def route_status(draft, contact=None, cand=None):
    """(status, route): the one channel this application goes through, taken from the draft's route.
    Raises ValueError, which rejects the draft, when the route is not one of the four names, when a draft
    with no route is neither an email application nor a SEEK advert, or when route SEEK has no SEEK job
    behind it. An email application stays one: with no published address it fails the record check
    ('recipient is neither a published direct contact nor a published application inbox'); it is never
    sent to the SEEK queue instead."""
    cand = cand or {}
    route = str(draft.get('route') or '').strip().upper()
    if not route:
        route = 'EMAIL' if draft.get('recipient_email') else 'SEEK' if on_seek(cand, draft) else ''
        if not route:
            raise ValueError('draft names no route (EMAIL, SEEK, EMPLOYER_PORTAL or EMPLOYER_FORM) and the advert is not a SEEK job')
    if route == 'EMAIL':
        return STATUSES['prepared'], 'EMAIL'
    if route not in READY:
        raise ValueError(f"draft route {draft.get('route')!r} is not one of EMAIL, SEEK, EMPLOYER_PORTAL, EMPLOYER_FORM")
    if route == 'SEEK' and not on_seek(cand, draft):
        raise ValueError('route SEEK needs a SEEK job: the advert has no SEEK id and no SEEK job URL')
    return READY[route], route


def form_answers(cand, screen, draft, route):
    """(answers, asks) for a SEEK, portal or form application. answers go on the record: for each form
    question the line of facts.json -> answers as {question, answer, basis}, never what the draft wrote for
    it; a question with no standing answer as {question, draft_answer} (the drafter's proposal, left out
    when it is only a placeholder). asks: [{question, why}] for the owner. Raises ValueError when the
    draft's answers are in a shape that cannot be read. An email application has no form."""
    if route == 'EMAIL':
        return [], []
    given, unreadable = checks.answer_items(draft)
    if unreadable:
        raise ValueError(unreadable)
    proposed = {item['question'].lower(): item['answer'] for item in given}
    questions = list(dict.fromkeys(checks.form_questions({'screening_questions': cand.get('screening_questions') or screen.get('screening_questions'),
                                                          'screening_answers': draft.get('screening_answers') or draft.get('questions')})))
    asks = checks.unanswered_questions(questions)
    is_open = {a['question'].lower() for a in asks}
    answers, seen = [], set()
    for question in questions:
        text = ' '.join(question.split())
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        if text.lower() not in is_open:
            basis, line, _ = checks.standing_line(text)
            answers.append({'question': text, 'answer': line, 'basis': basis})
            continue
        proposal = proposed.get(text.lower())
        real = isinstance(proposal, str) and proposal.strip() and not checks.PLACEHOLDER.search(proposal) and not re.search(r'\[[^\]]*\]', proposal)
        answers.append({'question': text, 'draft_answer': proposal.strip()} if real else {'question': text})
    return answers, asks


def owner_questions(screen, form_asks):
    """What only the owner can settle before this is submitted: mandatory facts the screen left unresolved,
    then the form questions with no standing answer in facts.json -> answers."""
    return [{'question': str(x), 'why': 'the advert makes this mandatory and facts.json does not settle it'} for x in screen.get('mandatory_unresolved') or []] + form_asks


COMMON_CALL_QUESTIONS = [
    f"What are your work rights? → {FACTS['eligibility']['work_rights']}.",
    "Tell me about your site experience. → About a year in the Philippines, 2019 to 2020: project-in-charge on a community hall renovation (10 to 15 workers a day, drawing reviews, inspections, quality checks), then field engineer on subdivision finishing works (site reports, material records, procurement, coordinating with engineers and suppliers).",
    "What did you study in Australia? → Advanced Diploma of Civil Construction Design, Albright Institute, February 2024 to February 2026: road geometry, earthworks, pavement and stormwater drainage, drawings in AutoCAD and Civil 3D to Australian Standards, Before You Dig Australia enquiries.",
    "Which software do you use? → AutoCAD 2D and 3D, Civil 3D, Revit (coursework), Microsoft Office, Google Workspace. Say plainly that drafting experience is from study, not a paid job.",
    "Do you have a licence, White Card, transport? → Yes to all three; also a Working with Children Check.",
    "When could you start, and what salary? → Two weeks after an offer, as the application says. Salary: the advertised figure, or your standing band when none is stated.",
]


def how_found(cand, screen, contact, route):
    src = (cand.get('source') or 'seek')
    listed = (cand.get('listed_at') or '')[:10]
    expires = (cand.get('expires_at') or screen.get('expires_at') or '')[:10]
    parts = [f"Found on {'SEEK' if src == 'seek' else src} (listed {listed or 'date not shown'}{', closes ' + expires if expires else ''})."]
    contact = contact or {}
    conf = contact.get('contact_confidence') or 'none'
    if route != 'EMAIL':
        parts.append({'SEEK': 'Applications go through SEEK', 'EMPLOYER_PORTAL': "Applications go through the employer's portal",
                      'EMPLOYER_FORM': "Applications go through the employer's web form"}[route] + ': submitted from the apply queue (automation/APPLY.md), one application, no separate email.')
        return ' '.join(parts)
    if conf == 'published_direct':
        parts.append(f"Contact: {contact.get('recipient_name')} ({contact.get('recipient_role')}), whose work email the employer publishes at {contact.get('contact_evidence_url')}.")
    elif conf == 'published_inbox':
        parts.append(f"Contact: the application inbox {contact.get('recipient_email')} published by the employer ({contact.get('contact_evidence_url')}); no personal address was used.")
    else:
        return ' '.join(parts + ['Contact: no address the employer publishes is on file, so this email application cannot be sent.'])
    if contact.get('named_people'):
        parts.append('Named people seen on employer pages: ' + '; '.join(f"{p.get('name')} ({p.get('role')})" for p in contact['named_people'][:3]) + '.')
    parts.append(f"Sent by email from {FACTS['identity']['email']} by the runner that has Gmail; recorded as SENT with the Gmail id.")
    return ' '.join(parts)


def call_prep(draft, screen):
    q = [f"How did you find us? → Your advert for the {draft.get('role') or screen.get('title')} role" + (" on SEEK." if (screen.get('source') or 'seek') == 'seek' else " on your website.")]
    for gap in (screen.get('gaps') or [])[:3]:
        q.append(f"They may ask about: {gap} → answer honestly from the facts; nothing beyond them was claimed.")
    return q + COMMON_CALL_QUESTIONS


def how_found_block(cand, screen, contact, draft, route):
    """Written once, inside notes (the tracker page shows notes). It used to be stored again as how_found and call_prep fields."""
    return f"HOW {CONFIG['contributor_name'].upper()} FOUND THIS\n" + how_found(cand, screen, contact, route) + '\n\nIF THEY CALL, LIKELY QUESTIONS\n' + '\n'.join('• ' + x for x in call_prep(draft, screen))


def build_record(run_id, cand, screen, contact, draft, attachments=None):
    status, route = route_status(draft, contact, cand)
    answers, form_asks = form_answers(cand, screen, draft, route)
    asks = owner_questions(screen, form_asks)
    method = {'EMAIL': 'Email', 'SEEK': 'SEEK', 'EMPLOYER_PORTAL': 'Company website', 'EMPLOYER_FORM': 'Company website'}[route]
    fields = {
        'company': draft.get('company') or cand.get('company'),
        'role': draft.get('role') or cand.get('title'),
        'location': draft.get('location') or cand.get('location') or '',
        'job_url': draft.get('job_url') or cand.get('url') or cand.get('job_url') or '',
        'company_url': (contact or {}).get('company_url') or '',
        'status': STATUSES['ask_owner'] if asks else status,
        'ask_owner': {'questions': asks, 'then': status} if asks else None,
        'application_type': draft.get('application_type') or 'ADVERTISED_VACANCY',
        'vacancy_status': draft.get('vacancy_status') or ('OPEN_ADVERT_VERIFIED' if screen.get('open') is True else 'VACANCY_UNVERIFIED'),
        'application_route': route,
        'application_method': method,
        'advert_asks_about_visa': True if draft.get('advert_asks_about_visa') is True else None,
        'fit': screen.get('rationale') or '',
        'gaps': screen.get('gaps') or [],
        'match_score': {'percent': screen.get('percent'), 'method': CONFIG['fit']['method'], 'caution': screen.get('caution') or ''},  # the reasons are in fit, once
        'advert': {'source': cand.get('source') or 'seek', 'listed_at': cand.get('listed_at') or screen.get('listed_at') or '', 'expires_at': cand.get('expires_at') or screen.get('expires_at') or '',
                   'verified_at': cand.get('checked_at') or now_iso(), 'apply_instructions': screen.get('apply_instructions') or '', 'screening_questions': cand.get('screening_questions') or screen.get('screening_questions') or []},
        'screening_answers': answers,
        'checklist': draft.get('checklist') or [],
        'notes': '\n'.join(x for x in [draft.get('notes'), (contact or {}).get('notes')] + [f"ASK OWNER: {a['question']} ({a['why']})" for a in asks] + [how_found_block(cand, screen, contact, draft, route)] if x),
        'checked_at': now_iso(),
        'seek_id': cand.get('seek_id') if cand.get('source', 'seek') == 'seek' else None,
        'attachments': attachments or [],
    }
    if route == 'EMAIL':  # the email and its recipient exist only on an email application
        email = draft.get('recipient_email') or (contact or {}).get('recipient_email') or ''
        researched = (contact or {}).get('recipient_email') or email
        published = str(email).strip().lower() == str(researched).strip().lower()  # the draft's address must be the one the contact research found
        fields.update({
            'recipient_name': draft.get('recipient_name') or (contact or {}).get('recipient_name') or '',
            'recipient_role': draft.get('recipient_role') or (contact or {}).get('recipient_role') or '',
            'recipient_email': email,
            'contact_email': email,
            'contact_evidence_url': draft.get('contact_evidence_url') or (contact or {}).get('contact_evidence_url') or '',
            'contact_verified_at': now_iso(),
            'contact_confidence': (contact or {}).get('contact_confidence') if published and (contact or {}).get('contact_confidence') else 'none',
            'subject': draft.get('subject') or '',
            'email_body': draft.get('email_body') or '',
        })
    return tracker.new_record(fields, run_id=run_id)


def pdf_names(rec):
    co = re.sub(r'[^A-Za-z0-9]+', '_', rec['company']).strip('_')[:40]
    role = re.sub(r'[^A-Za-z0-9]+', '_', rec['role']).strip('_')[:40]
    return f'Marc_Masarate_{co}_{role}_Cover_Letter.pdf', f'Marc_Masarate_{co}_Resume.pdf'


def publish(run_id, only=None, go=False):
    run, cands, screens, contacts, drafts = load_run(run_id)
    records, rejected = [], []
    speculative = speculative_this_week(run_id)
    for sid, draft in sorted(drafts.items()):
        if only and sid not in only:
            continue
        cand, screen, contact = cands.get(sid, {}), screens.get(sid, {}), contacts.get(sid, {})
        if not screen:
            rejected.append({'seek_id': sid, 'why': 'no screen file'}); continue
        eligibility = eligibility_issues(cand, screen, draft)
        if draft.get('application_type') == 'SPECULATIVE_ENQUIRY' and speculative >= LIMITS['max_speculative_per_week']:
            eligibility.append(f"speculative approaches are capped at {LIMITS['max_speculative_per_week']} a week (config -> limits -> max_speculative_per_week)")
        if eligibility:
            rejected.append({'seek_id': sid, 'issues': eligibility}); continue
        letter = draft.get('letter') or {}
        try:
            rec = build_record(run_id, cand, screen, contact, draft)
        except ValueError as e:  # no usable route, unreadable form answers, or a record with no company or role
            rejected.append({'seek_id': sid, 'issues': [str(e)]}); continue
        cover_name, resume_name = pdf_names(rec)
        cover_pdf = run / cover_name
        if go:
            render_pdf.render_letter({**letter, 'date': None}, cover_pdf)
            up_cover = tracker.upload_document(cover_pdf, 'cover', cover_name)
            up_resume = tracker.upload_document(render_pdf.resume_pdf(), 'resume', resume_name)
            rec['attachments'] = [{**up_resume, 'kind': 'resume'}, {**up_cover, 'kind': 'cover'}]
        else:
            rec['preparation_only'] = True
            rec['attachments'] = [{'kind': 'resume', 'filename': resume_name, 'stored_in': 'not_uploaded'}, {'kind': 'cover', 'filename': cover_name, 'stored_in': 'not_uploaded'}]
        issues = checks.record_issues(rec, require_uploaded=go)  # the record, its email and its form answers
        issues += checks.draft_issues({'letter': letter, 'advert_asks_about_visa': draft.get('advert_asks_about_visa')})  # the cover letter
        if issues:
            rejected.append({'seek_id': sid, 'status': rec['status'], 'issues': issues}); continue
        speculative += rec.get('application_type') == 'SPECULATIVE_ENQUIRY'
        records.append(rec)
    write_json(run / 'records.json', records)
    write_json(run / 'rejected.json', rejected)
    result = {'built': [(r['id'], r['company'], r['role'], r['status']) for r in records], 'rejected': rejected,
              'ask_owner': [{'company': r['company'], 'role': r['role'], 'questions': [a['question'] for a in r['ask_owner']['questions']]} for r in records if r.get('ask_owner')]}
    if go and records:
        result['tracker'] = tracker.add_records(records)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('build', 'go'):
        s = sub.add_parser(name); s.add_argument('run_id'); s.add_argument('--only', nargs='*')
    a = ap.parse_args(argv)
    print(json.dumps(publish(a.run_id, set(a.only or []) or None, go=(a.cmd == 'go')), indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
