#!/usr/bin/env python3
"""One-off: move the finds made while the tracker was full (17 Oct to 13 Nov 2026) into the apply queue.

Reads automation/queue/import_source_backlog.json (a copy of the backlog built on 13 Nov 2026 from automation/runs and
the journal) and the draft, record and saved-advert files under automation/runs, applies the rules of 13 Nov 2026
(automation/config.json -> lanes) and writes one queue entry for each find it keeps. Every find it drops is listed
with its reason in automation/queue/import_report.json.

Usage: import_backlog.py [--source BACKLOG.json] [--today 2026-11-13] [--at ISO] [--dry-run]
  --source copies that file to automation/queue/import_source_backlog.json first, so the import can be repeated
  from the repo alone. The queue folder must hold no entries yet.

The lane comes from the job title where the title settles it. Where the advert had to be read (the discipline, the
years asked for, a fact about Marc that is missing) the decision and its reason are written in DECISIONS below.
"""
import argparse
import glob
import importlib.util
import json
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# The apply queue next to this file, loaded by path: plain "import queue" can mean the standard library's module.
_spec = importlib.util.spec_from_file_location('apply_queue', Path(__file__).resolve().with_name('queue.py'))
apply_queue = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply_queue)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'queue' / 'import_source_backlog.json'
REPORT = ROOT / 'queue' / 'import_report.json'
OLD_RULES = 'letter written under the old rules: rewrite before use'
RELOCATE = 'I will relocate to {} for this role and can start two weeks after an offer.'

# Excluded families (config -> lanes -> excluded), matched on the job title.
EXCLUDED = (
    ('graduate programs', r'\bgraduate\b.*\bprogram\b|\bprogram\b.*\bgraduate\b'),
    ('student, intern, vacation or undergraduate roles', r'\b(student|intern|internship|vacation|undergraduate)\b'),
    ('estimator', r'\bestimat(or|ing)\b'),
    ('project coordinator', r'\bproject co-?ordinator\b'),
    ('document control', r'\bdocument control'),
    ('contract administrator', r'\bcontracts? administrator\b'),
    ('site or project administration', r'\badministrat(or|ion)\b'),
    ('traffic controller', r'\btraffic controller\b'),
    ('survey assistant or chainperson', r'\bsurvey assistant\b|\bchain(person|man)\b'),
    ('labourer', r'\blabourer\b'),
)

# Decisions that needed the advert (or the old screening notes) to be read. Key: SEEK job number, or advert url.
DECISIONS = {
    # lane settled by the duties, not the title
    '95347045': {'lane': 'technician', 'why': 'Quality assurance trainee: site inspections, ITPs, test records and help with material testing; experience not essential'},
    '95487722': {'lane': 'drafter', 'why': 'Land-development consultancy asking for Civil Engineers and Civil Designers; the duties are civil design and drafting'},
    '95372255': {'lane': 'engineer', 'why': 'Junior Project Manager at a civil contractor, aimed at a recent civil engineering graduate (old screening notes; advert text not saved)'},
    'https://careers.pageuppeople.com/817/cw/en/job/496994/civil-works-project-officer':
        {'lane': 'technician', 'why': 'Council project officer scoping and inspecting road and footpath reinstatement works; no minimum years (old screening notes)',
         'note': 'The position description with the selection criteria was not read (the site blocked the download): read it before applying.'},
    '95514711': {'lane': 'engineer', 'why': "Site Engineer expression of interest; the advert says you don't need to know everything from day one (old screening notes; advert text not saved)"},
    '95798711': {'lane': 'engineer', 'why': 'Civil Engineer at a consultancy; the advert asks for 1+ years'},
    '95835638': {'lane': 'engineer', 'why': 'Civil Site Engineer; the advert asks for 1 to 5 years'},
    '95871692': {'lane': 'engineer', 'why': 'Site Engineer; the advert says graduate to intermediate level (old screening notes; advert text not saved)',
                 'note': 'SEEK questions were not saved (old notes: work rights, salary, years as site engineer, notice).'},
    '95866809': {'lane': 'engineer', 'why': 'Council Development Engineer; the advert asks for a civil engineering background as a recent graduate (old letter; advert text not saved)'},
    '95865921': {'lane': 'engineer', 'why': 'Council Civil Services Engineer; the advert says it only wants applications from current graduates',
                 'note': 'Check what "current graduates" means in the position description before applying.'},
    'https://www.quantumcivil.com.au/careers': {'lane': 'engineer', 'why': 'Speculative enquiry for a graduate or junior civil site role, through the careers form'},
    # read and left in the lane the title gives; something to know before applying. Where the old record was held
    # until the owner answered (needs_owner_answer_first in the backlog), the question goes to him: 'ask'.
    '95446060': {'note': 'The advert asks for a recently completed Bachelor of Engineering.',
                 'ask': "Cooke & Dowsett's advert asks for a recently completed Bachelor of Engineering; yours is from 2019: apply anyway?"},
    '95352132': {'note': 'The email address is known from a journal note only (advert not saved): find the page where the employer '
                         'publishes it and record it with queue.py letter --evidence-url before this can be sent.'},
    '95736615': {'note': 'The requirements list says Australian citizenship or permanent residency; the last line of the advert says people who hold full Australian working rights will be considered.',
                 'ask': "Fyfe's requirements list says Australian citizenship or permanent residency, but the advert's last line says "
                        'people who hold full Australian working rights will be considered: apply?'},
    '95655998': {'note': 'Three-year traineeship that requires completing a Diploma of Civil Construction Design at TAFE Ultimo.'},
    '95842971': {'note': "The advert lists a current Queensland driver's licence.",
                 'ask': "Civilivic's advert lists a current Queensland driver's licence; yours is Victorian: apply anyway?"},
    '95773573': {'note': "The advert asks for a civil engineering degree or an equivalent recognised in Australia."},
    'https://au.indeed.com/job/graduate-project-engineer-438ca52bc822d185': {'note': 'Seen on job boards only; an earlier copy had expired. Confirm the advert is live first.'},
    'https://www.simplyhired.com.au/job/6Pbf9pqbHHreuUa9VUxiOFJMue5kUqLT_iod1MlWa9uv9RQgvHXCVw': {'note': "Seen on job-board mirrors only, not on the employer's own board. Find the live advert first."},
    # not in a lane
    '95398302': {'reject': ('no_lane', 'Electrical substation drafting, not civil drafting or design')},
    '95815474': {'reject': ('no_lane', 'Cadastral survey drafting, not civil drafting or design')},
    '95409467': {'reject': ('no_lane', 'Bare Site Engineer title; the advert asks, ideally, for at least two years')},
    '95573011': {'reject': ('no_lane', 'Bare Project Engineer title; the advert neither welcomes graduates nor asks for one year or less')},
    '95577489': {'reject': ('no_lane', 'Bare Roads Engineer title; the advert asks for experience delivering road works and does not welcome graduates')},
    '95755286': {'reject': ('no_lane', 'Bare Site Engineer title; advert text not saved and nothing on record says it welcomes graduates')},
    '95841578': {'reject': ('no_lane', 'Bare Civil Site Engineer title; the advert wants someone who works on their own and does not welcome graduates')},
    'https://jobs.mammoet.com/careers-home/jobs/9300': {'reject': ('no_lane', 'Heavy-lift and transport graduate program, not a civil, site or project engineer role')},
    # a stated requirement he does not meet
    '95606153': {'reject': ('mandatory_unmet', 'The advert states at least 2 to 3 years as a civil engineering assistant')},
    '95870684': {'reject': ('mandatory_unmet', 'The advert states a minimum of 3 years (old screening notes; advert text not saved)')},
    # one fact is missing: ask the owner once
    'https://au.prosple.com/graduate-employers/hobsons-bay-city-council/jobs-internships/graduate-drainage-and-development-engineer':
        {'ask': 'Hobsons Bay City Council asks for eligibility for Engineers Australia membership: are you eligible? (closes 16 Nov)'},
    'https://www.careersatcouncil.com.au/job/graduate-traffic-design-engineer-20261016/':
        {'ask': 'Griffith City Council asks for an engineering degree acceptable to Engineers Australia: is yours?'},
    '95823436': {'ask': "Cairns Regional Council's Cadet Designer job runs for up to six years and includes studying an Associate Degree in "
                        'Engineering (Civil): would you enrol and apply?'},
}

STATUS_ROUTE = {'READY_SEEK': 'SEEK', 'READY_JEREMIE_SEEK': 'SEEK', 'READY_EMPLOYER_PORTAL': 'EMPLOYER_PORTAL',
                'READY_JEREMIE_EMPLOYER_PORTAL': 'EMPLOYER_PORTAL', 'READY_EMPLOYER_FORM': 'EMPLOYER_FORM',
                'READY_JEREMIE_EMPLOYER_FORM': 'EMPLOYER_FORM',
                # job boards that need an account to apply are worked like a portal
                'READY_JEREMIE_INDEED': 'EMPLOYER_PORTAL', 'READY_JEREMIE_JOBSNEXT': 'EMPLOYER_PORTAL', 'READY_JEREMIE_JORA': 'EMPLOYER_PORTAL'}

# Within daily travel of Melton VIC: Greater Melbourne, Geelong and Ballarat. Suburbs are listed only where the
# backlog's location text does not say Melbourne.
NEAR_MELTON = ('melbourne', 'melton', 'geelong', 'ballarat', 'southbank', 'williamstown', 'officer vic')
CITIES = ('Sydney', 'Brisbane', 'Perth', 'Adelaide', 'Canberra', 'Hobart', 'Darwin')
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december')
CLOSES = re.compile(r'(?i)\bclos(?:e|es|ing)\b[^\n]{0,60}?\b(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})[^\n]{0,25}')
CLOCK = re.compile(r'(?i)\b(\d{1,2})(?:[.:](\d{2}))?\s*([ap])\.?m\b')


def old_status(row):
    """The find's old status under its current name (READY_JEREMIE_SEEK is now READY_SEEK)."""
    return str(row.get('status') or '').replace('JEREMIE_', '')


def repo_path(p):
    """A path recorded on another checkout, as a path in this one."""
    return ROOT / str(p).split('/automation/', 1)[1] if '/automation/' in str(p) else Path(p)


def saved_adverts():
    """SEEK job number -> the advert as saved by a sweep (the latest copy that has its text)."""
    found = {}
    for f in sorted(glob.glob(str(ROOT / 'runs' / '*' / 'candidates*.json'))):
        try:
            data = apply_queue.read_json(f)
        except apply_queue.Refused:  # a sweep file that is not valid JSON
            continue
        for c in (data.get('candidates') if isinstance(data, dict) else data) or []:
            if isinstance(c, dict) and c.get('seek_id') and (c.get('content_text') or str(c['seek_id']) not in found):
                found[str(c['seek_id'])] = c
    return found


def excluded_family(role):
    return next((name for name, pattern in EXCLUDED if re.search(pattern, role, re.I)), None)


def lane_from_title(role):
    """The lane when the title settles it; None when the advert has to be read (a bare engineer title, anything else)."""
    t = role.lower()
    if re.search(r'draft|designer\b|\bcad\b|civil 3d', t):
        return 'drafter'
    if re.search(r'technician|materials testing|laborator|engineering assistant', t):
        return 'technician'
    if re.search(r'\b(graduate|junior|cadet|trainee)\b', t) and re.search(r'\bengineer\b', t):
        return 'engineer'
    return None


def route_for(row, advert):
    route = STATUS_ROUTE.get(row['status'])
    if not route:  # PREPARED_NOT_SENT and HELD_*: the backlog's own route column
        r = str(row.get('route') or '')
        route = r if r in ('EMAIL', 'EMPLOYER_FORM') else 'SEEK' if r.upper().startswith('SEEK') and 'link' not in r.lower() else 'EMPLOYER_PORTAL'
    if route == 'SEEK' and ((advert or {}).get('is_link_out') or not row.get('seek_id')):
        route = 'EMPLOYER_PORTAL'  # a SEEK advert whose Apply button goes to the employer's site
    return route


def closing(row, advert):
    """(closes_at, closes_source): a date the advert states, an end date the advertiser set, or SEEK's 30-day expiry.

    A closing time the advert states ("9am, Wednesday 25 November 2026") is kept as YYYY-MM-DDThh:mm. The queue reads it
    as Melbourne time, which is never later than the same clock time anywhere else in Australia.
    """
    stated = CLOSES.search((advert or {}).get('content_text') or '')
    if stated:
        day = date(int(stated.group(3)), MONTHS.index(stated.group(2).lower()) + 1, int(stated.group(1))).isoformat()
        clock = CLOCK.search(stated.group(0))
        if clock and 1 <= int(clock.group(1)) <= 12 and int(clock.group(2) or 0) < 60:
            day += f"T{int(clock.group(1)) % 12 + (12 if clock.group(3).lower() == 'p' else 0):02d}:{int(clock.group(2) or 0):02d}"
        return day, 'advert'
    closes = row.get('effective_close_date') or ''
    if not closes:
        return '', 'none'
    if not row.get('seek_id'):
        return closes, 'advert'
    listed = row.get('listed_date')
    days = (date.fromisoformat(closes) - date.fromisoformat(listed)).days if listed else 30
    return closes, 'listing_expiry' if days >= 29 else 'advert'


def relocation_line(location):
    """'' within daily travel of Melton; otherwise the owner's sentence with the city or region."""
    if any(place in location.lower() for place in NEAR_MELTON):
        return ''
    plain = re.sub(r'\([^)]*\)', '', location)
    city = next((c for c in CITIES if c in plain), None)
    place = city or re.sub(r'\s+(VIC|NSW|QLD|WA|SA|TAS|NT|ACT)$', '', plain.split(',')[0].strip()).replace(' / ', ' or ')
    return RELOCATE.format(place.strip())


def drafts(row):
    """(cover letter text, email subject, email body, evidence url) from the find's draft files, '' where there is none."""
    files = [repo_path(f) for f in row.get('draft_files') or []]
    files = [f for f in files if f.exists()]
    main = next((apply_queue.read_json(f) for f in files if f.suffix == '.json' and not f.name.endswith('_L.json')), {})
    text = lambda end: next((f.read_text(encoding='utf-8').strip() for f in files if f.name.endswith(end)), '')
    letter = text('_letter.txt') or '\n\n'.join(((main.get('letter') or {}).get('paragraphs')) or [])
    body = text('_email.txt') or str(main.get('email_body') or '').strip()
    return letter, str(main.get('subject') or ''), body, str(main.get('contact_evidence_url') or '')


def record_questions(row):
    """Screening question texts kept on the old record, for adverts no sweep saved."""
    path = repo_path(row.get('source_file') or '')
    if not path.is_file():
        return []
    data = apply_queue.read_json(path)
    for r in data if isinstance(data, list) else []:
        if isinstance(r, dict) and r.get('id') == row.get('record_id'):
            return [x for x in (r.get('advert') or {}).get('screening_questions') or [] if isinstance(x, str)]
    return []


def build_entry(row, advert, decision, lane, today, at):
    route = route_for(row, advert)
    letter, subject, body, evidence = drafts(row)
    closes_at, closes_source = closing(row, advert)
    notes = [OLD_RULES, f"Imported from the backlog of {today} (old status {old_status(row)}). Fit {row.get('fit_percent')}% is from the old rubric."]
    if decision.get('why'):
        notes.append(f"Lane {lane}: {decision['why']}.")
    if decision.get('note'):
        notes.append(decision['note'])
    if not letter:
        notes.append('No letter text was in the repo for this find: write one.')
    questions = ((advert or {}).get('screening_questions') or record_questions(row)) if route == 'SEEK' else []
    if route == 'SEEK' and not questions and 'SEEK questions were not saved' not in ' '.join(notes):
        notes.append('No SEEK questions were saved for this advert: answer any on screen with queue.py answer.')
    email = {}
    if route == 'EMAIL':
        # evidence_url only where a draft recorded the page that publishes the address; without it next holds the entry
        email = {'to': row.get('apply_email') or '', 'subject': subject, 'body': body, 'evidence_url': evidence}
    return {
        'lane': lane, 'route': route, 'company': row['company'], 'role': row['role'], 'location': row.get('location') or '',
        'url': row['url'], 'seek_id': str(row.get('seek_id') or ''), 'listed_at': row.get('listed_date') or '',
        'closes_at': closes_at, 'closes_source': closes_source, 'fit': row.get('fit_percent'), 'resume_variant': lane,
        'relocation_line': relocation_line(row.get('location') or ''), 'cover_letter_text': letter, 'email': email,
        'questions': questions, 'status': 'ASK_OWNER' if decision.get('ask') else 'OPEN', 'ask_owner': decision.get('ask') or '',
        'created_by': 'import_backlog.py', 'created_at': at, 'source_run': row.get('run_id') or '', 'notes': '\n'.join(notes),
    }


def decide(row, advert, today):
    """(lane, decision, reject) for one backlog row; reject is (reason, detail) or None."""
    decision = DECISIONS.get(str(row.get('seek_id') or '')) or DECISIONS.get(row.get('url') or '') or {}
    for rejection in row.get('recorded_rejection_same_employer') or []:  # Australian Ground Technologies, 17 Oct 2026
        return None, decision, ('employer_rejected_him', f"{rejection.get('company')} rejected his application on {rejection.get('date')}")
    closes = closing(row, advert)[0][:10]
    if closes and closes < today:
        return None, decision, ('closed', f'closed {closes}')
    if not re.match(r'https?://', row.get('url') or ''):
        return None, decision, ('no_advert_in_repo', 'named only in a journal note: no advert url, text or draft in the repo')
    family = excluded_family(row['role'])
    if family:
        return None, decision, ('excluded_family', family)
    if decision.get('reject'):
        return None, decision, decision['reject']
    lane = decision.get('lane') or lane_from_title(row['role'])
    if not lane:
        return None, decision, ('no_lane', 'the title is in no lane and no reading of the advert is recorded')
    return lane, decision, None


def run(today, at, dry_run=False, source=SOURCE, qdir=None):
    qdir = Path(qdir or SOURCE.parent)
    if apply_queue.load(qdir):
        raise SystemExit('the queue already holds entries: this import is for an empty queue')
    backlog = apply_queue.read_json(source)
    facts = apply_queue.read_json(ROOT / 'facts.json')
    adverts, kept, rejected, seen = saved_adverts(), [], [], {}
    for row in backlog['backlog']:
        advert = adverts.get(str(row.get('seek_id') or ''))
        lane, decision, reject = decide(row, advert, today)
        entry = None
        if not reject:
            entry = apply_queue.fill(build_entry(row, advert, decision, lane, today, at))
            keys = [apply_queue.job_key(entry), apply_queue.norm_url(entry['url'])]
            first = next((seen[k] for k in keys if k in seen), None)
            if first:
                reject = ('duplicate', f"same job as {first['id']}")
                if not first['cover_letter_text'] and entry['cover_letter_text']:  # keep the letter the other copy had
                    first['cover_letter_text'] = entry['cover_letter_text']
                    first['notes'] = first['notes'].replace('No letter text was in the repo for this find: write one.',
                                                            f"Letter text carried over from the duplicate find at {entry['url']}.")
            else:
                if row.get('needs_owner_answer_first') and not decision.get('ask'):
                    raise SystemExit(f"{row['company']}: the old record was held for the owner's answer; DECISIONS needs its 'ask' line")
                seen.update({k: entry for k in keys})
                kept.append(entry)
        if reject:
            rejected.append({'company': row['company'], 'role': row['role'], 'location': row.get('location') or '', 'url': row.get('url') or '',
                             'seek_id': str(row.get('seek_id') or ''), 'old_status': old_status(row), 'reason': reject[0], 'detail': reject[1]})
    for entry in kept:
        apply_queue.apply_answers(entry, facts)
        problems = apply_queue.validate(entry, facts)
        if problems:
            raise SystemExit(f"{entry['id']}: " + '; '.join(problems))
        if not dry_run:
            apply_queue.save(qdir, entry)
    count = lambda rows, key: {k: sum(1 for r in rows if key(r) == k) for k in sorted({key(r) for r in rows})}
    is_open = [e for e in kept if e['status'] == 'OPEN']
    report = {
        '_about': 'Written by automation/scripts/import_backlog.py from import_source_backlog.json. One-off record of the import of 13 Nov 2026.',
        'today': today, 'created_at': at, 'source_rows': len(backlog['backlog']), 'imported': len(kept), 'rejected_total': len(rejected),
        'open_by_route': count(is_open, lambda e: e['route']), 'open_by_lane': count(is_open, lambda e: e['lane']),
        'ask_owner': [{'id': e['id'], 'company': e['company'], 'role': e['role'], 'route': e['route'], 'lane': e['lane'],
                       'closes_at': e['closes_at'], 'question': apply_queue.owner_line(e)} for e in kept if e['status'] == 'ASK_OWNER'],
        'rejected_by_reason': count(rejected, lambda r: r['reason']),
        'soonest_real_closing_dates': [{'closes_at': e['closes_at'], 'id': e['id'], 'company': e['company'], 'role': e['role'], 'route': e['route'],
                                        'status': e['status']} for e in sorted((e for e in kept if e['closes_source'] == 'advert'),
                                                                               key=lambda e: (e['closes_at'], e['id']))[:10]],
        'entries': [{'id': e['id'], 'company': e['company'], 'role': e['role'], 'lane': e['lane'], 'route': e['route'], 'status': e['status'],
                     'closes_at': e['closes_at'], 'closes_source': e['closes_source'], 'has_letter': bool(e['cover_letter_text']),
                     'relocation': bool(e['relocation_line'])} for e in kept],
        'rejected': rejected,
        'decisions_from_reading_the_advert': {k: {x: (list(v) if isinstance(v, tuple) else v) for x, v in d.items()} for k, d in DECISIONS.items()},
    }
    if not dry_run:
        apply_queue.write_json(qdir / REPORT.name, report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', help='backlog.json to copy into automation/queue/import_source_backlog.json first')
    ap.add_argument('--today', default='2026-11-13', help='the date the import is judged on (closing dates before it are dropped)')
    ap.add_argument('--at', help='created_at for the entries (default: now)')
    ap.add_argument('--dry-run', action='store_true', help='print the counts, write nothing')
    a = ap.parse_args(argv)
    if a.source and Path(a.source).resolve() != SOURCE.resolve():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.source, SOURCE)
    at = apply_queue.iso(apply_queue.parse_time(a.at)) if a.at else apply_queue.iso(datetime.now(timezone.utc))
    report = run(a.today, at, a.dry_run)
    print(json.dumps({k: v for k, v in report.items() if k not in ('entries', 'rejected', 'decisions_from_reading_the_advert', '_about')},
                     indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
