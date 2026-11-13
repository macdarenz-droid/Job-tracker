import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))

import common  # noqa: E402
import seek  # noqa: E402
import tracker  # noqa: E402
import checks  # noqa: E402
import render_pdf  # noqa: E402
import email_html  # noqa: E402
import compact_pdf  # noqa: E402
import browse  # noqa: E402


class PrefilterTests(unittest.TestCase):
    def listing(self, title, classes=('Civil/Structural Engineering (Engineering)',)):
        return {'title': title, 'classifications': list(classes)}

    def test_junior_civil_titles_pass(self):
        for t in ['Graduate Civil Engineer', 'Junior Civil Drafter', 'Trainee Structural Drafter', 'Cadet Civil Engineer',
                  'Site Engineer', 'Civil Designer', 'Civil 3D Drafter', 'Engineering Officer',
                  'Construction Materials Testing Technician - Entry-Level', 'Trainee Soil Technicians', 'Geotechnical Laboratory Technician',
                  'Concrete Tester - Fifo', 'Engineering Technical Officer', 'Civil Engineering Assistant']:
            self.assertTrue(seek.prefilter(self.listing(t))[0], t)

    def test_senior_and_other_disciplines_fail(self):
        for t in ['Senior Civil Engineer', 'Civil Project Manager', 'Structures Foreman', 'Lead Drafter', 'Electrical Engineer',
                  'Trainee Surveyor', 'Building Surveyor', 'Principal Engineer', 'Experienced Estimator', 'Quantity Surveyor',
                  'Structural Engineer', 'Geotechnical Engineer', 'Supervisor / Estimator']:
            self.assertFalse(seek.prefilter(self.listing(t))[0], t)

    def test_roles_the_owner_excluded_on_13_nov_fail(self):
        for t in ['Junior Estimator', 'Project Coordinator', 'Undergraduate Engineer', 'Document Controller', 'Site Administrator',
                  'Traffic Controller', 'Survey Assistant', 'Steel Detailer', '2027 Engineering Graduate Program', 'Vacation Student - Civil',
                  'Medical Laboratory Technician', 'Dental Laboratory Technician-Chatswood', 'Asphalt Labourer']:
            self.assertFalse(seek.prefilter(self.listing(t))[0], t)

    def test_classification_filter(self):
        self.assertFalse(seek.prefilter(self.listing('Junior Engineer', ('Nursing (Healthcare & Medical)',)))[0])
        self.assertTrue(seek.prefilter(self.listing('Junior Engineer', ('Government - Local (Government & Defence)',)))[0])
        self.assertTrue(seek.prefilter(self.listing('Junior Engineer', ()))[0])

    def test_normalise_listing(self):
        j = {'id': 123, 'title': 'Junior Civil Engineer', 'advertiser': {'description': 'Acme Civil'}, 'locations': [{'label': 'Melton, Melbourne VIC'}],
             'listingDate': '2026-09-28T00:00:00Z', 'teaser': 't', 'bulletPoints': ['a'], 'classifications': [{'classification': {'description': 'Engineering'}, 'subclassification': {'description': 'Civil/Structural Engineering'}}]}
        n = seek.normalise_listing(j)
        self.assertEqual(n['seek_id'], '123')
        self.assertEqual(n['company'], 'Acme Civil')
        self.assertEqual(n['location'], 'Melton, Melbourne VIC')
        self.assertEqual(n['url'], 'https://www.seek.com.au/job/123')
        self.assertEqual(n['classifications'], ['Civil/Structural Engineering (Engineering)'])

    def test_strip_html(self):
        self.assertEqual(common.strip_html('<p>Hi <b>there</b></p><ul><li>one</li><li>two &amp; three</li></ul>'), 'Hi there\n- one\n- two & three')


STATE = {
    'applications': [{'key': 'wml.com.au|junior-structural-drafter', 'company': 'WML Consulting Engineers', 'role': 'Junior Structural Drafter', 'status': 'SENT', 'sent_at': '2026-09-12T08:01:18Z', 'job_url': 'https://www.wml.com.au/careers'}],
    'leads': [{'key': 'kantershow|seek:94482077', 'company': 'Kantershow Civil', 'role': 'Junior Graduate Civil Engineer', 'status': 'READY_JEREMIE_SEEK', 'job_url': 'https://www.seek.com.au/job/94482077', 'checked_at': '2026-09-12T14:31:00+10:00'},
              {'key': 'old-co|seek:1', 'company': 'Old Co', 'role': 'Cadet', 'status': 'SENT', 'sent_at': '2025-01-01T00:00:00Z', 'job_url': 'https://www.seek.com.au/job/1'}],
    'manual_entries': [{'id': 'm1', 'key': 'manual:m1', 'company': 'Doval Constructions', 'role': 'Graduate Engineer', 'status': 'MANUAL_APPLIED', 'applied_date': '2026-09-26', 'job_url': 'https://au.seek.com/job/94539368', 'origin_key': 'doval-constructions|seek:94539368', 'contributor_name': 'Grok AI', 'attachments': []},
                       {'id': 'm2', 'key': 'manual:m2', 'company': 'Fortec Australia Pty Ltd', 'role': 'Junior Civil Engineer', 'status': 'REJECTED', 'applied_date': '2026-08-18', 'job_url': '', 'contributor_name': 'Grok AI', 'attachments': []}],
    'record_visibility': [],
}


TODAY = datetime(2026, 9, 28, tzinfo=timezone.utc)  # the day these cases were written for


class DedupeTests(unittest.TestCase):
    def setUp(self):
        self._po = mock.patch.object(tracker, 'prior_outreach', return_value=[])  # keep the live receipt file out of these cases
        self._po.start()
        self.idx = tracker.dedupe_index(json.loads(json.dumps(STATE)))

    def tearDown(self):
        self._po.stop()

    def test_seek_id_from_any_url_form(self):
        self.assertIn('94539368', self.idx['seek_ids'])
        self.assertIn('94482077', self.idx['seek_ids'])
        blocked, why, _ = tracker.check_duplicate({'seek_id': '94539368', 'company': 'Doval', 'title': 'Other'}, self.idx)
        self.assertTrue(blocked); self.assertIn('SEEK', why)
        blocked, _, _ = tracker.check_duplicate({'url': 'https://au.seek.com/job/94482077?tracking=x', 'company': 'X', 'title': 'Y'}, self.idx)
        self.assertTrue(blocked)

    def test_company_role_and_url(self):
        blocked, why, _ = tracker.check_duplicate({'company': 'WML Consulting Engineers', 'title': 'Junior Structural Drafter', 'url': 'https://x.com/a'}, self.idx, today=TODAY)
        self.assertTrue(blocked); self.assertIn('already applied for this role', why)
        blocked, why, _ = tracker.check_duplicate({'company': 'WML Consulting', 'title': 'Civil Drafter', 'url': 'https://www.wml.com.au/careers/'}, self.idx, today=TODAY)
        self.assertTrue(blocked); self.assertIn('URL', why)

    def test_same_role_blocks_and_another_role_gets_a_note(self):
        # Doval: applied 26 Sep for Graduate Engineer. The same role is blocked; a different role is allowed with a note.
        blocked, why, _ = tracker.check_duplicate({'company': 'Doval Constructions', 'title': 'Graduate Engineer', 'url': 'https://www.seek.com.au/job/999'}, self.idx, today=TODAY)
        self.assertTrue(blocked); self.assertIn('MANUAL_APPLIED', why); self.assertIn('2026-09-26', why)
        blocked, why, notes = tracker.check_duplicate({'company': 'Doval Constructions', 'title': 'Site Engineer', 'url': 'https://www.seek.com.au/job/999'}, self.idx, today=TODAY)
        self.assertFalse(blocked); self.assertTrue(any('Graduate Engineer' in n and 'different role' in n for n in notes))
        # Fortec: rejected for Junior Civil Engineer in August. Same employer name without 'Pty Ltd'.
        blocked, why, _ = tracker.check_duplicate({'company': 'Fortec Australia', 'title': 'Junior Civil Engineer', 'url': 'https://www.seek.com.au/job/998'}, self.idx, today=TODAY)
        self.assertTrue(blocked); self.assertIn('REJECTED', why)
        blocked, why, notes = tracker.check_duplicate({'company': 'Fortec Australia', 'title': 'Civil Drafter', 'url': 'https://www.seek.com.au/job/998'}, self.idx, today=TODAY)
        self.assertFalse(blocked); self.assertTrue(notes)
        blocked, why, notes = tracker.check_duplicate({'company': 'Old Co', 'title': 'Cadet', 'url': 'https://www.seek.com.au/job/997'}, self.idx, today=TODAY)
        self.assertFalse(blocked); self.assertTrue(any('outside the repeat block' in n for n in notes))
        blocked, why, notes = tracker.check_duplicate({'company': 'Brand New Pty Ltd', 'title': 'Graduate Civil Engineer', 'url': 'https://www.seek.com.au/job/996'}, self.idx, today=TODAY)
        self.assertFalse(blocked); self.assertEqual(notes, [])

    def test_new_record_shape(self):
        r = tracker.new_record({'company': 'Acme', 'role': 'Junior Civil Engineer', 'status': 'LEAD', 'job_url': 'https://www.seek.com.au/job/5'}, run_id='r1')
        self.assertEqual(r['contributor_name'], common.CONFIG['contributor_name'])  # whoever config says runs the loop
        self.assertEqual(r['created_by'], common.CONFIG['created_by'])
        self.assertEqual(r['key'], 'manual:' + r['id'])
        self.assertEqual(r['duplicate_key'], 'acme|seek:5')
        self.assertEqual(r['version'], 1)
        with self.assertRaises(ValueError):
            tracker.new_record({'company': 'Acme', 'role': 'X', 'status': 'LEAD', 'attachments': [{'data_base64': 'x'}]})


class GuardedWriteTests(unittest.TestCase):
    def test_add_retries_on_409_and_skips_duplicates(self):
        store = {'version': 4, 'state': json.loads(json.dumps(STATE))}
        calls = {'put': 0}

        def fake_request(path, method='GET', data=None, headers=None, raw=False):
            if path == '/api/state' and method == 'GET':
                return 200, {'version': store['version'], 'state': json.loads(json.dumps(store['state']))}
            if path == '/api/state' and method == 'PUT':
                calls['put'] += 1
                if calls['put'] == 1:  # someone else saved in between
                    store['version'] += 1
                    return 409, {'error': 'newer'}
                if data['expected_version'] != store['version']:
                    return 409, {'error': 'newer'}
                store['state'] = data['state']; store['version'] += 1
                return 200, {'version': store['version'], 'updated_at': 'now'}
            raise AssertionError(path)
        with mock.patch.object(tracker, 'request', fake_request), mock.patch.object(tracker.time, 'sleep'):
            new = tracker.new_record({'company': 'Brand New', 'role': 'Graduate Civil Engineer', 'status': 'LEAD', 'job_url': 'https://www.seek.com.au/job/77'})
            dup = tracker.new_record({'company': 'Doval Constructions', 'role': 'Graduate Engineer', 'status': 'LEAD', 'job_url': 'https://www.seek.com.au/job/94539368'})
            out = tracker.add_records([new, dup])
        self.assertEqual(calls['put'], 2)
        self.assertEqual(out['result']['added'], [new['id']])
        self.assertEqual(len(out['result']['skipped']), 1)
        self.assertEqual(len(store['state']['manual_entries']), 3)
        self.assertEqual(store['state']['applications'], STATE['applications'])

    def test_update_only_claude_records(self):
        state = json.loads(json.dumps(STATE))
        mine = tracker.new_record({'company': 'Acme', 'role': 'X', 'status': 'PREPARED_NOT_SENT', 'attachments': [{'id': 'a', 'kind': 'resume', 'stored_in': 'cloudflare_r2', 'sha256': '1'}]})
        state['manual_entries'].append(mine)
        store = {'version': 1, 'state': state}

        def fake_request(path, method='GET', data=None, headers=None, raw=False):
            if method == 'GET':
                return 200, {'version': store['version'], 'state': json.loads(json.dumps(store['state']))}
            store['state'] = data['state']; store['version'] += 1
            return 200, {'version': store['version'], 'updated_at': 'now'}
        with mock.patch.object(tracker, 'request', fake_request):
            tracker.update_record(mine['id'], {'status': 'SENT', 'sent_at': 'x', 'attachments': [{'id': 'b', 'kind': 'cover', 'stored_in': 'cloudflare_r2', 'sha256': '2'}]}, expect_status='PREPARED_NOT_SENT')
            rec = [r for r in store['state']['manual_entries'] if r['id'] == mine['id']][0]
            self.assertEqual(rec['status'], 'SENT'); self.assertEqual(rec['version'], 2)
            self.assertEqual([d['id'] for d in rec['attachments']], ['a', 'b'])
            with self.assertRaises(RuntimeError):
                tracker.update_record('m1', {'status': 'SENT'})
            with self.assertRaises(RuntimeError):
                tracker.update_record(mine['id'], {'status': 'SENT'}, expect_status='PREPARED_NOT_SENT')


class CheckTests(unittest.TestCase):
    def test_tone(self):
        bad = 'Dear Hiring Manager, I am writing to express my interest — please find attached my tailored résumé! Wow!'
        issues = checks.tone_issues(bad)
        self.assertTrue(any('dear hiring manager' in i for i in issues))
        self.assertTrue(any('banned character' in i for i in issues))
        self.assertTrue(any('exclamation' in i for i in issues))
        good = "Hi Sam,\n\nI saw your ad for a junior civil drafter and wanted to get in touch directly.\n\nI finished an Advanced Diploma of Civil Construction Design in February 2026 and drafted road, earthworks, pavement and drainage work in Civil 3D and AutoCAD during the course. Before that I worked on site in the Philippines as a field engineer.\n\nI've attached my resume and cover letter.\n\nThanks,\nMarc"
        self.assertEqual(checks.tone_issues(good), [])
        self.assertTrue(any('portfolio link' in i for i in checks.tone_issues(good + '\nmacdarenz-droid.github.io/Portfolio')))
        self.assertEqual(checks.tone_issues(good + '\nhttps://macdarenz-droid.github.io/Portfolio'), [])

    def test_facts(self):
        self.assertEqual(checks.fact_issues('I used AutoCAD and Civil 3D in my Advanced Diploma, finished February 2026, and worked on a PHP 1.2 million subdivision job.'), [])
        self.assertEqual(checks.fact_issues('Acme has built trusses in Somerton since 2005. I finished my diploma in 2026.'), [])
        self.assertTrue(checks.fact_issues('I graduated in 2005.'))
        issues = checks.fact_issues('I have 3 years of commercial drafting experience with 12d and SIDRA, I am a permanent resident, and graduated in 2021 with honours.')
        for needle in ['12d', 'SIDRA', 'permanent residency', '2021', 'honours', 'years of professional experience']:
            self.assertTrue(any(needle in i for i in issues), needle)

    def test_record(self):
        rec = tracker.new_record({'company': 'Acme', 'role': 'Junior Civil Drafter', 'status': 'PREPARED_NOT_SENT', 'job_url': 'https://www.seek.com.au/job/5',
                                  'subject': 'Junior Civil Drafter, Marc Masarate', 'email_body': 'Hi Sam,\n\nShort note.\n\nThanks,\nMarc', 'recipient_email': 'sam@acme.com.au',
                                  'recipient_name': 'Sam Lee', 'recipient_role': 'Engineering Manager', 'contact_evidence_url': 'https://acme.com.au/team', 'fit': 'x', 'gaps': ['y'],
                                  'match_score': {'percent': 70}, 'contact_confidence': 'published_direct', 'attachments': [{'kind': 'resume', 'stored_in': 'cloudflare_r2', 'sha256': 'a' * 64, 'id': 'resume-id', 'path': '/api/documents/resume-id', 'filename': 'r.pdf'}, {'kind': 'cover', 'stored_in': 'cloudflare_r2', 'sha256': 'b' * 64, 'id': 'cover-id', 'path': '/api/documents/cover-id', 'filename': 'c.pdf'}]})
        self.assertEqual(checks.record_issues(rec), [])
        rec['recipient_email'] = 'sam@gmail.com'; rec['attachments'] = rec['attachments'][:1]
        issues = checks.record_issues(rec)
        self.assertTrue(any('personal mailbox' in i for i in issues)); self.assertTrue(any('cover letter' in i for i in issues))
        rec['recipient_email'] = 'careers@acme.com.au'; rec['recipient_name'] = ''; rec['contact_confidence'] = 'published_inbox'; rec['attachments'] += [{'kind': 'cover', 'stored_in': 'cloudflare_r2', 'sha256': 'b' * 64, 'id': 'cover-id', 'path': '/api/documents/cover-id', 'filename': 'c.pdf'}]
        self.assertEqual(checks.record_issues(rec), [])
        rec['contact_confidence'] = 'none'
        self.assertTrue(any('neither' in i for i in checks.record_issues(rec)))


def working_chrome(limit=20):
    """(path, None) for a Chromium that prints a page to PDF on this machine, else (None, why not).

    Looks at the Playwright headless shell and /opt/pw-browsers/chromium, then whatever render_pdf finds.
    Each is tried on a one-line page first: in some sandboxes the full browser starts but never prints,
    and the render test would then sit for two minutes and fail for a reason that has nothing to do with
    the letter."""
    found = [str(p) for p in sorted(Path('/opt/pw-browsers').glob('chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'))]
    found.append('/opt/pw-browsers/chromium')
    try:
        found.append(render_pdf.chrome_path())
    except RuntimeError:
        pass
    found = [p for i, p in enumerate(found) if Path(p).exists() and p not in found[:i]]
    if not found:
        return None, 'no Chromium on this machine'
    for chrome in found:
        with tempfile.TemporaryDirectory() as d:
            page, pdf = Path(d) / 'probe.html', Path(d) / 'probe.pdf'
            page.write_text('<p>probe</p>', encoding='utf-8')
            try:
                subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', f'--print-to-pdf={pdf}', f'--user-data-dir={d}/profile', str(page)],
                               capture_output=True, timeout=limit)
            except (subprocess.TimeoutExpired, OSError):
                continue
            if pdf.exists() and pdf.read_bytes()[:4] == b'%PDF':
                return chrome, None
    return None, f'Chromium is installed but did not print a page within {limit} s here: ' + ', '.join(found)


class RenderTests(unittest.TestCase):
    def test_letter_html_escapes_and_fills(self):
        h = render_pdf.letter_html({'recipient_name': 'Sam <Lee>', 'company': 'Acme', 'subject': 'Junior drafter', 'paragraphs': ['One & two', 'Three']})
        self.assertIn('Sam &lt;Lee&gt;', h); self.assertIn('<p>One &amp; two</p>', h); self.assertIn('Marc Darenz Masarate', h); self.assertNotIn('{{', h)

    def test_pdf_render(self):
        chrome, why = working_chrome()
        if not chrome:
            self.skipTest(why)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(render_pdf, 'chrome_path', return_value=chrome):
            out = Path(d) / 'letter-test.pdf'
            render_pdf.render_letter({'recipient_name': 'Sam Lee', 'company': 'Acme', 'subject': 'Junior drafter', 'paragraphs': ['One.', 'Two.']}, out)
            self.assertEqual(out.read_bytes()[:4], b'%PDF')

    def test_resume_pdf_present(self):
        try:
            p = render_pdf.resume_pdf()
        except RuntimeError as e:
            self.skipTest(str(e))
        self.assertTrue(p.exists())


class RankTests(unittest.TestCase):
    def test_civil_junior_outranks_noise(self):
        civil = {'title': 'Junior Civil Drafter', 'teaser': 'AutoCAD and Civil 3D for subdivision work', 'bullets': [], 'classifications': ['Engineering Drafting (Engineering)']}
        noise = {'title': 'Trainee Belt Splicers', 'teaser': 'mining equipment', 'bullets': [], 'classifications': ['Other (Trades & Services)']}
        homes = {'title': 'Draftsperson', 'teaser': 'custom homes', 'bullets': [], 'classifications': ['Architectural Drafting (Design & Architecture)']}
        self.assertGreater(seek.relevance(civil), seek.relevance(homes))
        self.assertGreater(seek.relevance(homes), seek.relevance(noise))
        self.assertFalse(seek.prefilter({'title': '1st Year Junior Plumbing Apprentice', 'classifications': []})[0])
        self.assertFalse(seek.prefilter({'title': 'RF Engineer - Wireless', 'classifications': []})[0])


class PublishTests(unittest.TestCase):
    def test_route_status_and_record(self):
        import publish
        statuses = common.CONFIG['statuses']
        draft = {'company': 'Acme Civil', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC', 'job_url': 'https://www.seek.com.au/job/5', 'route': 'SEEK',
                 'recipient_name': 'Sam Lee', 'recipient_role': 'Drafting Manager', 'recipient_email': 'sam.lee@acme.com.au', 'contact_evidence_url': 'https://acme.com.au/team',
                 'subject': 'Junior Civil Drafter, Marc Masarate', 'email_body': 'Hi Sam,\n\nShort note.\n\nThanks,\nMarc', 'letter': {'paragraphs': ['One.', 'Two.']},
                 'screening_answers': [{'question': 'How much notice are you required to give your current employer?', 'answer': '2 weeks'}], 'checklist': ['open']}
        screen = {'percent': 72, 'rationale': 'r', 'caution': 'c', 'gaps': ['g'], 'apply_instructions': 'Apply on SEEK', 'listed_at': '2026-09-27',
                  'screening_questions': ['How much notice are you required to give your current employer?']}
        contact = {'contact_confidence': 'published_direct', 'company_url': 'https://acme.com.au'}
        cand = {'seek_id': '5', 'source': 'seek', 'company': 'Acme Civil', 'title': 'Junior Civil Drafter', 'url': 'https://www.seek.com.au/job/5'}
        # The advert takes applications on SEEK: one application there, and the published email is not used as a second touch.
        rec = publish.build_record('r1', cand, screen, contact, draft)
        self.assertEqual(rec['status'], statuses['ready_seek']); self.assertEqual(rec['status'], 'READY_SEEK'); self.assertEqual(rec['application_method'], 'SEEK')
        self.assertNotIn('Double touch', rec['notes']); self.assertNotIn('Jeremie', rec['notes'])
        for k in ('recipient_email', 'contact_email', 'email_body', 'subject'):
            self.assertNotIn(k, rec)
        draft['route'] = 'EMAIL'
        rec = publish.build_record('r1', cand, screen, contact, draft)
        self.assertEqual(rec['status'], statuses['prepared']); self.assertEqual(rec['application_method'], 'Email'); self.assertEqual(rec['match_score']['percent'], 72)
        self.assertEqual(rec['recipient_email'], 'sam.lee@acme.com.au'); self.assertEqual(rec['email_body'], draft['email_body'])
        self.assertEqual(rec['contributor_name'], common.CONFIG['contributor_name']); self.assertEqual(rec['seek_id'], '5')
        rec = publish.build_record('r1', cand, screen, {'contact_confidence': 'none'}, {**draft, 'recipient_email': ''})
        self.assertEqual(rec['status'], statuses['ready_seek'])
        for route, key in (('EMPLOYER_PORTAL', 'ready_portal'), ('EMPLOYER_FORM', 'ready_form')):
            rec = publish.build_record('r1', cand, screen, contact, {**draft, 'route': route})
            self.assertEqual(rec['status'], statuses[key]); self.assertEqual(rec['application_method'], 'Company website')

    def test_naming_an_unused_tool_as_a_limit_is_not_a_claim(self):
        self.assertEqual(checks.fact_issues("I use Excel but haven't used Bluebeam or E1."), [])
        self.assertIn('names software not in facts: Bluebeam', checks.fact_issues('I am proficient in Bluebeam.'))



class EmailHtmlTests(unittest.TestCase):
    def test_urls_become_anchors_with_clean_visible_text(self):
        body = "Hi <Sam> & co,\nMy drawings are at https://macdarenz-droid.github.io/Portfolio. Thanks\nhttps://macdarenz-droid.github.io/Portfolio"
        out = email_html.html_body(body)
        self.assertEqual(out.count('<a href="https://macdarenz-droid.github.io/Portfolio">https://macdarenz-droid.github.io/Portfolio</a>'), 2)
        self.assertIn('Hi &lt;Sam&gt; &amp; co,<br>', out)
        self.assertIn('</a>. Thanks<br>', out)  # the full stop stays prose
        self.assertNotIn('Portfolio.<', out)

    def test_compact_pdfs_carry_clickable_portfolio_link(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = compact_pdf.resume_pdf(os.path.join(d, 'r.pdf'))
            doc = compact_pdf.pymupdf.open(out)
            uris = [l['uri'] for p in doc for l in p.get_links() if l.get('kind') == compact_pdf.pymupdf.LINK_URI]
            self.assertIn('https://macdarenz-droid.github.io/Portfolio', uris)
            out = compact_pdf.letter_pdf({'paragraphs': ['See https://macdarenz-droid.github.io/Portfolio for drawings.']}, os.path.join(d, 'l.pdf'))
            doc = compact_pdf.pymupdf.open(out)
            uris = [l['uri'] for p in doc for l in p.get_links() if l.get('kind') == compact_pdf.pymupdf.LINK_URI]
            self.assertGreaterEqual(uris.count('https://macdarenz-droid.github.io/Portfolio'), 2)


class PriorOutreachTests(unittest.TestCase):
    def test_seek_receipt_blocks_the_same_role_within_the_window(self):
        entries = [{'date': '2026-09-01', 'company': 'Offaly Civil Engineering Pty Ltd', 'role': 'Graduate Civil Engineer', 'gmail_message_id': 'x'},
                   {'date': '2025-01-01', 'company': 'Old Co', 'role': 'Cadet', 'gmail_message_id': 'y'}]
        with mock.patch.object(tracker, 'prior_outreach', return_value=entries):
            idx = tracker.dedupe_index({'applications': [], 'leads': [], 'manual_entries': []})
        blocked, why, _ = tracker.check_duplicate({'seek_id': '1', 'company': 'Offaly Civil Engineering', 'title': 'Graduate Civil Engineer'}, idx, today=TODAY)
        self.assertTrue(blocked); self.assertIn('MANUAL_APPLIED', why); self.assertIn('2026-09-01', why)
        blocked, why, notes = tracker.check_duplicate({'seek_id': '3', 'company': 'Offaly Civil Engineering', 'title': 'Site Engineer'}, idx, today=TODAY)
        self.assertFalse(blocked); self.assertTrue(any('Graduate Civil Engineer' in n and '2026-09-01' in n for n in notes))
        blocked, why, notes = tracker.check_duplicate({'seek_id': '2', 'company': 'Old Co Pty Ltd', 'title': 'Cadet'}, idx, today=TODAY)
        self.assertFalse(blocked); self.assertTrue(notes)


class BrowseTests(unittest.TestCase):
    def test_text_and_links_from_rendered_dom(self):
        dom = '<html><head><style>x{}</style><script>var a=1;</script></head><body><h1>Jobs</h1><ul><li><a href="/jobs/12-graduate-civil-engineer">Graduate Civil Engineer</a></li><li><a href="https://x.test/about">About &amp; us</a></li></ul></body></html>'
        text = browse.text_of(dom)
        self.assertIn('Jobs', text); self.assertIn('Graduate Civil Engineer', text); self.assertNotIn('var a', text)
        links = browse.links_of(dom, 'https://x.test/careers/', 'job')
        self.assertEqual(links, [('https://x.test/jobs/12-graduate-civil-engineer', 'Graduate Civil Engineer')])


if __name__ == '__main__':
    unittest.main()
