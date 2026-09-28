#!/usr/bin/env python3
"""SEEK discovery: the public search API plus the GraphQL job-details query.

Usage:
  seek.py sweep [--daterange N] [--max-details N] --out FILE   # all keyword sets, prefilter, details
  seek.py search "keywords" [--daterange N]                     # one query, listing rows
  seek.py details JOB_ID                                        # one job's full details
"""
import argparse
import json
import re
import sys
import time
import urllib.parse

from common import CONFIG, http, strip_html, now_iso, write_json, eprint

SEEK = CONFIG['seek']
PRE = CONFIG['prefilter']

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


def prefilter(listing):
    """Cheap title and classification screen. Returns (ok, reason)."""
    title = f" {listing.get('title', '').lower()} "
    for bad in PRE['title_exclude_any']:
        if bad.lower() in title:
            return False, f'title excludes: {bad.strip()}'
    if not any(good.lower() in title for good in PRE['title_include_any']):
        return False, 'title has no junior/civil signal'
    classes = ' | '.join(listing.get('classifications') or [])
    if classes and not any(allow.lower() in classes.lower() for allow in PRE['classification_allow']):
        return False, f'classification not allowed: {classes}'
    return True, 'ok'


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
            'id': c.get('seek_id'), 'source': c.get('source', 'seek'), 'title': c.get('title'), 'company': c.get('company'),
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
    s = sub.add_parser('sweep'); s.add_argument('--daterange', type=int, default=SEEK['daterange_days']); s.add_argument('--max-details', type=int, default=PRE['max_details_per_run']); s.add_argument('--out', required=True); s.add_argument('--keywords', nargs='*')
    q = sub.add_parser('search'); q.add_argument('keywords'); q.add_argument('--daterange', type=int, default=SEEK['daterange_days']); q.add_argument('--page', type=int, default=1)
    d = sub.add_parser('details'); d.add_argument('job_id')
    g = sub.add_parser('digest'); g.add_argument('run_dir'); g.add_argument('--max', type=int, default=CONFIG['limits']['screen_max_per_run'])
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
    elif a.cmd == 'digest':
        out = digest(a.run_dir, a.max)
        eprint(f'{len(out)} candidates → {a.run_dir}/screen_input.json')


if __name__ == '__main__':
    main()
