#!/usr/bin/env python3
"""SEEK discovery: the public search API plus the GraphQL job-details query.

Usage:
  seek.py sweep [--daterange N] [--max-details N] --out FILE   # all keyword sets, prefilter, details
  seek.py search "keywords" [--daterange N]                     # one query, listing rows
  seek.py details JOB_ID                                        # one job's full details
  seek.py digest RUN_DIR [--max N]                              # compact screen_input.json for the screening agent
  seek.py lane "TITLE" [--text-file ADVERT.txt]                 # drafter, technician, engineer or none (config -> lanes)

sweep and digest write each candidate's lane (lane_for) so the screening agent starts from it; the duties still decide.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse

from common import CONFIG, http, strip_html, now_iso, write_json, eprint

SEEK = CONFIG['seek']
PRE = CONFIG['prefilter']
LIMITS = CONFIG['limits']

DETAILS_QUERY = (
    'query jobDetails($jobId: ID!, $locale: Locale!, $zone: Zone!, $languageCode: LanguageCodeIso!) {'
    ' jobDetails(id: $jobId) { job { id title abstract isExpired isLinkOut content(platform: WEB)'
    ' shareLink(platform: WEB, zone: $zone, locale: $locale) advertiser { id name } location { label }'
    ' listedAt { dateTimeUtc } expiresAt { dateTimeUtc } workTypes { label(locale: $locale) }'
    ' salary { label } classifications { label(languageCode: $languageCode) }'
    ' products { bullets questionnaire { questions } } } } }'
)


def search(keywords, daterange=None, page=1, page_size=None):
    params = {
        'siteKey': 'AU-Main', 'where': SEEK['where'], 'keywords': keywords,
        'sortmode': 'ListedDate', 'page': page, 'pageSize': page_size or SEEK['page_size'],
    }
    if daterange:
        params['daterange'] = daterange
    status, body = http(f"{SEEK['search_url']}?{urllib.parse.urlencode(params)}")
    if status != 200 or not isinstance(body, dict) or 'data' not in body:
        raise RuntimeError(f'SEEK search failed ({status}) for {keywords!r}: {str(body)[:200]}')
    return body


def normalise_listing(j):
    locs = j.get('locations') or []
    advertiser = j.get('advertiser') or {}
    return {
        'source': 'seek',
        'seek_id': str(j.get('id')),
        'title': j.get('title') or '',
        'company': j.get('companyName') or advertiser.get('description') or '',
        'location': locs[0].get('label') if locs else (j.get('location') or ''),
        'listed_at': j.get('listingDate'),
        'teaser': j.get('teaser') or '',
        'bullets': j.get('bulletPoints') or [],
        'classifications': [
            f"{c.get('subclassification', {}).get('description', '')} ({c.get('classification', {}).get('description', '')})"
            for c in j.get('classifications') or []
        ],
        'work_type': j.get('workType'),
        'url': f"https://www.seek.com.au/job/{j.get('id')}",
    }


def plain(text):
    """Lower case, accents dropped, punctuation turned into single spaces, one space at each end: ' lab field technician '."""
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    return ' ' + ' '.join(re.sub(r'[^a-z0-9+&]+', ' ', text).split()) + ' '


def term_in(term, plain_text):
    """True when a config word is in plain() text. Words match anywhere ('draughts' finds 'draughtsman',
    'cad' finds 'autocad'). A space written at either end of the config word asks for a word boundary there:
    ' lab ' finds 'Lab Technician' and 'Soils Lab/Field' but not 'Laboratory' or 'Collaboration'; 'lead ' finds
    'Team Lead' but not 'Leading Hand'."""
    t = str(term).lower()
    core = plain(t).strip()
    return bool(core) and (' ' if t[:1] == ' ' else '') + core + (' ' if t[-1:] == ' ' else '') in plain_text


def title_exclusion(title):
    """The first config -> prefilter -> title_exclude_any word found in the title, or None."""
    text = plain(title)
    return next((bad.strip() for bad in PRE['title_exclude_any'] if term_in(bad, text)), None)


def prefilter(listing):
    """Cheap title and classification screen. Returns (ok, reason)."""
    title = listing.get('title', '')
    bad = title_exclusion(title)
    if bad:
        return False, f'title excludes: {bad}'
    if not any(term_in(good, plain(title)) for good in PRE['title_include_any']):
        return False, 'title has no junior/civil signal'
    classes = ' | '.join(listing.get('classifications') or [])
    if classes and not any(allow.lower() in classes.lower() for allow in PRE['classification_allow']):
        return False, f'classification not allowed: {classes}'
    return True, 'ok'


# Plain keyword rules behind lane_for. config -> lanes says what each lane is, what it is not, and the order.
CIVIL = r'\b(civil|roads?|highways?|drainage|stormwater|subdivisions?|land development|earthworks|infrastructure|pavements?|sewer|structural)\b'
TESTING = r'\b(materials?|soils?|geotech\w*|asphalt|aggregates?|cmt|nata|compaction|quarry)\b'
ENTRY = r'\b(graduates?|junior|cadet|trainee|entry level|assistant)\b'
# In advert text only the plainer words count: 'infrastructure', 'structural' and 'materials' turn up in every trade.
CIVIL_TEXT = r'\b(civil|drainage|stormwater|subdivisions?|earthworks|pavements?)\b'
TESTING_TEXT = r'\b(materials test\w*|construction materials?|soils?|geotech\w*|asphalt|aggregates?|cmt|nata|compaction)\b'
WELCOME = (r'\b(graduates? (are )?(welcome|encouraged|considered)|recent graduates?|entry level|no experience|training provided|0 (to )?[12] years?|'
           r'suit(s|ed)?( to)? (a |an )?(recent )?(graduate|junior)|(graduate|junior) (level|role|position|opportunity))\b')
YEARS = r'(\d+)\+?(?: (?:to )?\d+\+?)? years?(?: of)?(?: \w+){0,3} experience|(?:minimum|at least)(?: of)? (\d+)\+? years?'
LANE_TITLE = {
    'drafter': r'\b(draft\w*|draught\w*|cad|autocad|civil 3d|design technician|designers?|modeller)\b',
    'technician': r'\b(technicians?|geotechnicians?|technical officer|testers?|testing|laboratory|lab|engineering assistant)\b',
    'engineer': r'\bengineers?\b',
}
LANE_NOT = {  # config -> lanes -> <lane> -> not, as title words (the prefilter words already cover the rest)
    'drafter': r'\b(steel|detail\w*|truss\w*|joinery|kitchen|cabinet\w*|architect\w*|archicad|mechanical|electrical|interior|building|residential|sheet ?metal|metalwork|fabrication|manufactur\w*|solidworks|inventor|tekla|substations?|piping|hydraulic|fire|scaffold\w*)\b',
    'technician': r'\b(medical|pathology|food|chemi\w*|environmental|water|science|school|geolog\w*|exploration|mine|mining|non destructive|ndt|pest|fire|service|maintenance|installation|handling|plant|automotive|cad)\b',
    'engineer': r'\b(programs?|programmes?|it|ict|data|cloud|devops|mine|mining|subsea|offshore)\b',
}
ALSO_EXCLUDED = r'\b(admin\w*|co ?ordinators?|labourers?|traffic controllers?|chainm[ae]n|leaders?|scholarships?|work experience)\b'  # lanes -> excluded and seniority words the prefilter list lacks
PLAIN_WORDS = (r'draft\w*|draught\w*|cad|autocad|design\w*|technicians?|technical|officers?|laborator\w+|lab|testers?|testing|field|engineer\w*|assistants?|'
               r'junior|trainees?|cadets?|graduates?|entry|level|full|part|time|casual|permanent|fixed|term|contract|positions?|roles?|multiple|x\d*|\d+|and|or|a|the|of|in|for|qld|nsw|vic|wa|sa|nt|tas|act|fifo|dido')
LANE_SIGNAL = {'drafter': CIVIL, 'technician': TESTING + r'|\b(civil|roads?|highways?|pavements?|earthworks)\b', 'engineer': CIVIL + r'|\b(site|project|field|construction)\b'}
LANE_TEXT = {'drafter': CIVIL_TEXT, 'technician': TESTING_TEXT, 'engineer': CIVIL_TEXT + r'|\b(roads?|sewer|construction)\b'}
LANE_PLAIN = {'drafter': r'\b(draft\w*|draught\w*|cad|autocad)\b', 'technician': r'\b(laboratory|lab|testers?|testing|engineering|technical officer)\b', 'engineer': ENTRY}


def lane_for(title, text=''):
    """The role lane a title belongs to: 'drafter', 'technician', 'engineer' or None (config -> lanes).

    A first sort by plain words, for ranking and for the screening agent, who still reads the duties.
    1. None when the title has a word the prefilter or the lanes exclude (senior, estimator, project
       coordinator, steel detailer, pathology, graduate program, administration ...).
    2. A title that says what the work is gets its lane from the title: 'Civil Drafter', 'Soil
       Technician', 'Concrete Tester', 'Graduate Site Engineer'.
    3. A general title needs the advert text to show it: civil work for a drafter or engineer, testing
       words for a technician. With no text to read it keeps its lane only when the title is nothing
       but the job word, a level and a state ('Junior Draftsperson', 'Laboratory Technician', 'Graduate
       Engineer - Full Time'); one that names anything else ('Junior Manufacturing Engineer') gets None.
    4. A Site, Project or Civil Engineer title without graduate, junior, cadet, trainee or assistant
       counts only when the text welcomes them and does not ask for two or more years' experience.
    """
    t, body = plain(title), plain(text)
    known = bool(body.strip())
    if title_exclusion(title) or re.search(ALSO_EXCLUDED, t):
        return None
    nothing_else = not re.sub(r'\b(' + PLAIN_WORDS + r')\b|[&+]', ' ', t).strip()
    lanes = sorted((k for k, v in CONFIG['lanes'].items() if isinstance(v, dict) and 'rank' in v), key=lambda k: CONFIG['lanes'][k]['rank'])
    for lane in lanes:
        if lane not in LANE_TITLE or not re.search(LANE_TITLE[lane], t) or re.search(LANE_NOT[lane], t):
            continue
        concrete = lane == 'technician' and re.search(r'\bconcrete\b', t) and re.search(r'\b(test\w*|laboratory|lab)\b', t)
        if lane == 'engineer' and not re.search(ENTRY, t):  # rule 4
            if re.search(LANE_SIGNAL[lane], t) and re.search(WELCOME, body) and not any(int(a or b) >= 2 for a, b in re.findall(YEARS, body)):
                return lane
        elif re.search(LANE_SIGNAL[lane], t) or concrete:  # rule 2
            return lane
        elif known:  # rule 3, text given; an engineering technician or technical officer may show civil work instead of testing
            officer = lane == 'technician' and re.search(r'\b(engineering|technical officer)\b', t)
            if re.search(LANE_TEXT['engineer' if officer else lane], body):
                return lane
        elif not known and nothing_else and re.search(LANE_PLAIN[lane], t):  # rule 3, title only
            return lane
    return None


def relevance(listing):
    """Rank prefiltered listings so the detail fetches go to the likeliest civil junior roles."""
    text = ' '.join([listing.get('title', ''), listing.get('teaser', ''), ' '.join(listing.get('bullets') or [])]).lower()
    title = listing.get('title', '').lower()
    classes = ' '.join(listing.get('classifications') or []).lower()
    score = 0
    for w, pts in PRE['rank_title'].items():
        if w in title:
            score += pts
    for w, pts in PRE['rank_text'].items():
        if w in text:
            score += pts
    for w, pts in PRE['rank_classification'].items():
        if w in classes:
            score += pts
    for w in PRE['rank_penalty_words']:
        if w in text:
            score -= 4
    return score


def details(job_id):
    payload = {
        'operationName': 'jobDetails',
        'variables': {'jobId': str(job_id), 'locale': 'en-AU', 'zone': 'anz-1', 'languageCode': 'en'},
        'query': DETAILS_QUERY,
    }
    status, body = http(SEEK['graphql_url'], data=payload, headers={'Content-Type': 'application/json'})
    job = (((body or {}).get('data') or {}).get('jobDetails') or {}).get('job') if isinstance(body, dict) else None
    if status != 200 or not job:
        raise RuntimeError(f'SEEK details failed ({status}) for {job_id}: {str(body)[:300]}')
    products = job.get('products') or {}
    questionnaire = products.get('questionnaire') or {}
    return {
        'source': 'seek',
        'seek_id': str(job['id']),
        'title': job.get('title') or '',
        'abstract': job.get('abstract') or '',
        'company': (job.get('advertiser') or {}).get('name') or '',
        'advertiser_id': (job.get('advertiser') or {}).get('id'),
        'location': (job.get('location') or {}).get('label') or '',
        'listed_at': (job.get('listedAt') or {}).get('dateTimeUtc'),
        'expires_at': (job.get('expiresAt') or {}).get('dateTimeUtc'),
        'is_expired': bool(job.get('isExpired')),
        'is_link_out': bool(job.get('isLinkOut')),
        'work_type': (job.get('workTypes') or {}).get('label'),
        'salary': (job.get('salary') or {}).get('label'),
        'classifications': [c.get('label') for c in job.get('classifications') or []],
        'bullets': products.get('bullets') or [],
        'screening_questions': questionnaire.get('questions') or [],
        'content_text': strip_html(job.get('content') or ''),
        'url': f"https://www.seek.com.au/job/{job['id']}",
        'share_link': job.get('shareLink'),
        'checked_at': now_iso(),
    }


def sweep(daterange, max_details, out, keyword_sets=None, sleep=0.4):
    keyword_sets = keyword_sets or SEEK['keyword_sets']
    seen, listings, log = {}, [], []
    for kw in keyword_sets:
        for page in range(1, SEEK['max_pages_per_keyword'] + 1):
            try:
                body = search(kw, daterange=daterange, page=page)
            except Exception as e:  # keep sweeping other keyword sets
                log.append({'keywords': kw, 'page': page, 'error': str(e)[:200]})
                break
            rows = body.get('data') or []
            log.append({'keywords': kw, 'page': page, 'rows': len(rows), 'total': body.get('totalCount')})
            for j in rows:
                item = normalise_listing(j)
                if item['seek_id'] in seen:
                    seen[item['seek_id']]['matched_keywords'].append(kw)
                    continue
                item['matched_keywords'] = [kw]
                seen[item['seek_id']] = item
                listings.append(item)
            if len(rows) < SEEK['page_size']:
                break
            time.sleep(sleep)
    passed, rejected = [], []
    for item in listings:
        ok, reason = prefilter(item)
        item['prefilter'] = reason
        (passed if ok else rejected).append(item)
    for item in passed:
        item['relevance'] = relevance(item)
    passed.sort(key=lambda r: (r['relevance'], r.get('listed_at') or ''), reverse=True)
    candidates = []
    for item in passed[:max_details]:
        try:
            d = details(item['seek_id'])
            d['matched_keywords'] = item['matched_keywords']
            d['teaser'] = item['teaser']
            d['relevance'] = item['relevance']
            d['lane'] = lane_for(d['title'], d.get('content_text'))
            candidates.append(d)
        except Exception as e:
            item['details_error'] = str(e)[:200]
            candidates.append({**item, 'details_error': str(e)[:200]})
        time.sleep(sleep)
    result = {
        'run_at': now_iso(), 'daterange_days': daterange, 'keyword_sets': keyword_sets,
        'listings_seen': len(listings), 'prefilter_passed': len(passed), 'details_fetched': len(candidates),
        'not_detailed': [{'seek_id': r['seek_id'], 'title': r['title'], 'company': r['company'], 'relevance': r['relevance']} for r in passed[max_details:]],
        'search_log': log,
        'candidates': candidates,
        'rejected_titles': [{'seek_id': r['seek_id'], 'title': r['title'], 'company': r['company'], 'why': r['prefilter']} for r in rejected],
    }
    if out:
        write_json(out, result)
    return result


KEY_LINES = re.compile(r'(experience|years|citizen|resident|visa|licen|degree|diploma|qualif|autocad|civil 3d|revit|apply|email|close|graduate|junior|cadet|trainee|must|essential|require)', re.I)


def digest(run_dir, max_items):
    """Compact view of the new candidates for a single screening agent."""
    from pathlib import Path
    from common import read_json
    run = Path(run_dir)
    data = read_json(run / 'candidates.json')
    items = [c for c in data['candidates'] if not (c.get('duplicate') or {}).get('blocked')]
    for extra in sorted(run.glob('extra/*.json')):
        if extra.name.startswith('_'):
            continue
        c = read_json(extra)
        if not (c.get('duplicate') or {}).get('blocked'):
            items.append({**c, 'seek_id': c.get('id') or extra.stem})
    # Skip adverts already screened in an earlier run (their screen files hold the score and reasons).
    seen = {}
    for prior in sorted(run.parent.glob('*/screen/*.json')):
        if prior.parent.parent == run:
            continue
        try:
            sc = read_json(prior)
            seen[str(sc.get('id') or prior.stem)] = {'run': prior.parent.parent.name, 'percent': sc.get('percent'), 'mandatory_unmet': sc.get('mandatory_unmet')}
        except Exception:
            pass
    skipped_seen = [{'id': c.get('seek_id'), 'company': c.get('company'), 'title': c.get('title'), **seen[str(c.get('seek_id'))]} for c in items if str(c.get('seek_id')) in seen]
    items = [c for c in items if str(c.get('seek_id')) not in seen]
    items.sort(key=lambda c: (c.get('relevance', 0), c.get('listed_at') or ''), reverse=True)
    out = []
    for c in items[:max_items]:
        text = c.get('content_text') or ''
        key = [l.strip() for l in text.splitlines() if KEY_LINES.search(l)][:14]
        out.append({
            'id': c.get('seek_id'), 'source': c.get('source', 'seek'), 'title': c.get('title'), 'lane': lane_for(c.get('title'), text), 'company': c.get('company'),
            'location': c.get('location'), 'url': c.get('url'), 'work_type': c.get('work_type'), 'salary': c.get('salary'),
            'listed_at': c.get('listed_at'), 'expires_at': c.get('expires_at'), 'is_expired': c.get('is_expired', False),
            'is_link_out': c.get('is_link_out', False), 'screening_questions': c.get('screening_questions') or [],
            'summary': (c.get('abstract') or c.get('teaser') or '')[:300], 'opening': text[:900], 'key_lines': key,
        })
    write_json(run / 'screen_input.json', {'count': len(out), 'skipped': max(0, len(items) - max_items), 'screened_in_earlier_runs': skipped_seen, 'candidates': out})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('sweep'); s.add_argument('--daterange', type=int, default=SEEK['daterange_days']); s.add_argument('--max-details', type=int, default=LIMITS['max_candidate_details_per_run']); s.add_argument('--out', required=True); s.add_argument('--keywords', nargs='*')
    q = sub.add_parser('search'); q.add_argument('keywords'); q.add_argument('--daterange', type=int, default=SEEK['daterange_days']); q.add_argument('--page', type=int, default=1)
    d = sub.add_parser('details'); d.add_argument('job_id')
    g = sub.add_parser('digest'); g.add_argument('run_dir'); g.add_argument('--max', type=int, default=LIMITS['screen_max_per_run'])
    ln = sub.add_parser('lane'); ln.add_argument('title'); ln.add_argument('--text-file')
    a = ap.parse_args(argv)
    if a.cmd == 'sweep':
        r = sweep(a.daterange, a.max_details, a.out, keyword_sets=a.keywords or None)
        eprint(f"seen {r['listings_seen']} · prefilter passed {r['prefilter_passed']} · details {r['details_fetched']} → {a.out}")
    elif a.cmd == 'search':
        body = search(a.keywords, daterange=a.daterange, page=a.page)
        for j in body.get('data') or []:
            i = normalise_listing(j)
            print(f"{i['seek_id']} | {i['title']} | {i['company']} | {i['location']} | {i['listed_at']} | {prefilter(i)[1]}")
        eprint('total', body.get('totalCount'))
    elif a.cmd == 'details':
        print(json.dumps(details(a.job_id), indent=1, ensure_ascii=False))
    elif a.cmd == 'lane':
        text = ''
        if a.text_file:
            with open(a.text_file, encoding='utf-8') as f:
                text = f.read()
        print(lane_for(a.title, text) or 'none')
    elif a.cmd == 'digest':
        out = digest(a.run_dir, a.max)
        eprint(f'{len(out)} candidates → {a.run_dir}/screen_input.json')


if __name__ == '__main__':
    main()
