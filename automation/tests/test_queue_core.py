"""Tests for the queue core (automation/scripts/queue.py and journal.py) added on 14 Nov 2026: integrity before
hand-out, caps and quiet hours, UNCERTAIN, link-outs, repeats, speculative enquiries, claims, outcomes, receipt refs,
the send lock, add's fields, verify_before_submit, the resume line, report and stats. Offline: temp folders only."""
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
# Loaded by path under its own name: "import queue" may already mean the standard library's module in this process.
_spec = importlib.util.spec_from_file_location('apply_queue_core', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)
sys.path.insert(0, str(SCRIPTS))
import journal  # noqa: E402

NOW = datetime(2026, 11, 13, 1, 0, tzinfo=timezone.utc)  # midday on Friday 13 Nov 2026 in Melbourne (ISO week 46)
RUN = '20261113T0100Z'
CONFIG = {'lanes': {'drafter': {'rank': 1}, 'technician': {'rank': 2}, 'engineer': {'rank': 3}},
          'limits': {'seek_submissions_per_day': 6, 'email_sends_per_day': 3, 'portal_submissions_per_day': 3,
                     'min_minutes_between_seek_submissions': 20, 'repeat_block_days': 90}}
FACTS = {'identity': {'name': 'Marc Darenz Masarate', 'phone': '0478 764 077', 'location': 'Melton VIC 3337'}, 'answers': {}}


def at(text):
    """A Melbourne local time such as '2026-11-13T09:00'."""
    return q.parse_time(text)


def entry(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


# An email application attaches its cover letter, and next holds an EMAIL entry without one (checks.py's letter rules).
LETTER = ('Hello,\n\n'
          'I am applying for the Junior Civil Drafter role. Your advert asks for subdivision drawings in Civil 3D.\n\n'
          'In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks and '
          'stormwater drainage in AutoCAD and Civil 3D to Australian Standards.\n\n'
          'I live in Melton and can start two weeks after an offer. Full working rights in Australia (Subclass 485 visa), no '
          'sponsorship needed. Could we talk this week?\n\n'
          'Marc Masarate')


def email_entry(n, **kw):
    e = entry(n, route='EMAIL', seek_id='', url=f'https://example{n}.com.au/careers', id=f'email-{n}', cover_letter_text=LETTER,
              email={'to': f'jobs@example{n}.com.au', 'subject': 'Junior Civil Drafter', 'body': 'Hello.',
                     'evidence_url': f'https://example{n}.com.au/careers'})
    e.update(kw)
    return e


def form_entry(n, **kw):
    e = entry(n, route='EMPLOYER_FORM', seek_id='', url=f'https://careers.example{n}.com.au/apply', id=f'form-{n}')
    e.update(kw)
    return e


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dir = self.root / 'queue'
        self.config, self.facts, self.prior = self.root / 'config.json', self.root / 'facts.json', self.root / 'prior_outreach.json'
        q.write_json(self.config, CONFIG)
        q.write_json(self.facts, FACTS)
        q.write_json(self.prior, {'entries': []})

    def add(self, e, **kw):
        return q.add(e, self.dir, FACTS, kw.pop('now', NOW), **kw)

    def put(self, e):
        """Write an entry file without the checks of add, as a second runner's push or a hand edit would."""
        return q.save(self.dir, q.fill(e))

    def next(self, route='SEEK', now=NOW, by=None, prior=None, config=CONFIG):
        return q.next_entry(route, self.dir, config, now, by, prior)

    def mark(self, entry_id, action, by='grok', now=NOW, **kw):
        return q.mark(self.dir, entry_id, action, by, now, facts=FACTS, **kw)

    def applied(self, entry_id, when, kind='seek_confirmation_screen', ref='SEEK confirmation screen shown'):
        return self.mark(entry_id, 'applied', kind=kind, ref=ref, at=when)

    def cli(self, *args, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--prior', str(self.prior),
                           '--now', q.iso(now), *args])
        return code, out.getvalue(), err.getvalue()

    def file(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return str(path)


class IntegrityTests(Case):   # F1
    def test_a_stale_open_copy_of_a_finished_entry_stops_next_and_is_never_handed_out(self):
        self.add(entry(1))
        self.add(entry(2, listed_at='2026-11-01'))
        stale = (self.dir / 'open' / 'seek-1.json').read_text(encoding='utf-8')
        self.applied('seek-1', '2026-11-13T00:30:00Z')
        (self.dir / 'open' / 'seek-1.json').write_text(stale, encoding='utf-8')   # a commit that kept the old file
        later = NOW + timedelta(minutes=30)
        code, out, err = self.cli('next', '--route', 'SEEK', now=later)
        self.assertEqual((code, out), (1, ''))
        self.assertIn('nothing is handed out while queue.py check finds problems', err)
        self.assertIn('seek-1: a finished copy is in done/2026-11/ and this copy in open/ is stale', err)
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('remove it with git rm', out)
        self.assertEqual(out.count('seek-1:'), 1)   # one problem for the pair, not one for each key
        code, _, err = self.cli('mark', 'seek-1', 'applied', '--by', 'grok', '--kind', 'seek_confirmation_screen', '--ref', 'shown')
        self.assertEqual(code, 1)
        self.assertIn('seek-1 has 2 files', err)
        ctx = q.hold_context([e for _, e in q.load(self.dir)], CONFIG, later)
        self.assertIn('a finished copy of this entry is in done/: run queue.py check', q.blockers(q.fill(json.loads(stale)), ctx))
        (self.dir / 'open' / 'seek-1.json').unlink()
        self.assertEqual(self.cli('check')[0], 0)
        self.assertEqual(self.next(now=later)['id'], 'seek-2')

    def test_next_hands_out_nothing_on_any_route_while_check_finds_a_problem(self):
        self.add(entry(1))
        bad = self.put(entry(2, lane='labourer'))
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('seek-2: lane: one of', err)
        bad.unlink()
        self.put(form_entry(3, company='Acme 1 Pty Ltd', role='Civil Drafter'))   # the same job as seek-1, pushed by another runner
        for route in ('SEEK', 'EMPLOYER_PORTAL'):
            code, _, err = self.cli('next', '--route', route)
            self.assertEqual(code, 1, route)
            self.assertIn('same company and role as form-3, both waiting: mark one of them skipped', err)


class CapTests(Case):   # S6, F15
    def test_uncertain_entries_and_unmarked_starts_count_toward_the_days_cap(self):
        for n in (1, 2, 3, 4):
            self.add(form_entry(n))
        self.applied('form-1', '2026-11-12T22:00:00Z', kind='portal_confirmation', ref='portal confirmation page shown')
        self.assertEqual(self.next('EMPLOYER_FORM', by='grok')['id'], 'form-2')
        self.mark('form-2', 'uncertain', note='page froze after Submit')
        self.assertEqual(self.next('EMPLOYER_FORM', by='grok')['id'], 'form-3')   # not marked yet
        with self.assertRaises(q.CapReached) as r:
            self.next('EMPLOYER_FORM')
        self.assertIn('3 of 3 submitted on 2026-11-13', str(r.exception))
        self.assertEqual(self.cli('next', '--route', 'EMPLOYER_PORTAL')[0], 3)   # portal and form share the cap
        self.mark('form-3', 'failed', note='the form would not load, nothing was submitted')
        self.assertEqual(self.next('EMPLOYER_FORM')['id'], 'form-3')   # known not to have gone: no longer counted
        self.next('EMPLOYER_FORM', by='grok')
        with self.assertRaises(q.CapReached):
            self.next('EMPLOYER_FORM')
        self.assertEqual(self.next('EMPLOYER_FORM', now=NOW + timedelta(days=1))['id'], 'form-4')   # yesterday's do not count

    def test_the_seek_spacing_counts_an_uncertain_mark_and_an_unmarked_start(self):
        for n in (1, 2, 3):
            self.add(entry(n))
        self.assertEqual(self.next(by='grok', now=at('2026-11-13T09:00'))['id'], 'seek-1')
        self.mark('seek-1', 'uncertain', now=at('2026-11-13T09:10'), note='page froze after Submit')
        with self.assertRaises(q.CapReached) as r:
            self.next(now=at('2026-11-13T09:11'))
        self.assertIn('the last submission or start was 1 minutes ago; wait 20 more', str(r.exception))
        self.assertEqual(self.next(by='grok', now=at('2026-11-13T09:31'))['id'], 'seek-2')
        with self.assertRaises(q.CapReached):   # its start counts until it is marked
            self.next(now=at('2026-11-13T09:32'))
        self.assertEqual(self.next(now=at('2026-11-13T09:52'))['id'], 'seek-3')

    def test_quiet_hours(self):
        self.add(entry(1))
        for text in ('2026-11-13T21:00', '2026-11-13T23:30', '2026-11-14T06:59'):
            with self.assertRaises(q.CapReached) as r:
                self.next(now=at(text))
            self.assertIn('no submissions between 21:00 and 07:00 Melbourne time', str(r.exception))
        for text in ('2026-11-13T20:59', '2026-11-14T07:00'):
            self.assertEqual(self.next(now=at(text))['id'], 'seek-1')
        code, out, err = self.cli('next', '--route', 'SEEK', now=at('2026-11-13T23:30'))
        self.assertEqual((code, out), (3, ''))
        self.assertIn('quiet_hours', err)
        later = {**CONFIG, 'limits': {**CONFIG['limits'], 'quiet_hours': '22:00-06:00'}}
        self.assertEqual(self.next(now=at('2026-11-13T21:30'), config=later)['id'], 'seek-1')
        with self.assertRaises(q.CapReached) as r:
            self.next(now=at('2026-11-14T05:59'), config=later)
        self.assertIn('between 22:00 and 06:00', str(r.exception))
        for bad in ('evenings', '21:00', '25:00-07:00', '07:00-07:00'):
            with self.assertRaises(q.Refused) as r:
                self.next(config={**CONFIG, 'limits': {**CONFIG['limits'], 'quiet_hours': bad}})
            self.assertNotIsInstance(r.exception, q.CapReached, bad)
            self.assertIn('quiet_hours', str(r.exception))


class UncertainTests(Case):   # S4
    def test_an_uncertain_entry_stays_until_applied_or_checked_open(self):
        self.add(entry(1, closes_at='2026-11-18', closes_source='listing_expiry'))
        self.next(by='grok')
        code, out, _ = self.cli('mark', 'seek-1', 'uncertain', '--by', 'grok', '--note', 'page froze after Submit')
        self.assertEqual((code, out.strip()), (0, 'seek-1: UNCERTAIN'))
        self.assertEqual(q.expire(self.dir, now=NOW + timedelta(days=10)), [])   # never "closed, never submitted"
        e = q.find(self.dir, 'seek-1')[1]
        self.assertEqual((e['status'], e['ask_owner'], (self.dir / 'open' / 'seek-1.json').exists()), ('UNCERTAIN', '', True))
        for action, kw in (('skipped', {'note': 'advert closed'}), ('failed', {'note': 'x'}), ('ask', {'note': 'Did it go?'}),
                           ('uncertain', {'note': 'again'}), ('linkout', {})):
            with self.assertRaises(q.Refused) as r:
                self.mark('seek-1', action, **kw)
            self.assertIn('seek-1 is UNCERTAIN', str(r.exception))
        with self.assertRaises(q.Refused):
            self.mark('seek-1', 'open', note='not in the list')
        s = q.stats(self.dir, NOW)
        self.assertEqual((s['uncertain'], s['queue_open']['total'], s['ask_owner_open']), (1, 0, 0))
        q.render(self.dir, CONFIG, NOW)
        text = (self.dir / 'APPLY_QUEUE.md').read_text(encoding='utf-8')
        self.assertIn('## Unknown whether it went (1)', text)
        self.assertIn('check the applied jobs list on SEEK before any retry', text)
        self.assertEqual(self.mark('seek-1', 'open', note='checked: not in the applied jobs list on SEEK')['status'], 'OPEN')
        self.assertEqual([e['id'] for e in q.expire(self.dir, now=NOW + timedelta(days=10))], ['seek-1'])

    def test_an_entry_marked_uncertain_before_the_status_existed_reads_as_uncertain(self):
        old = {k: v for k, v in q.fill(entry(1)).items() if k != 'application_type'}
        old.update(status='ASK_OWNER', ask_owner='Unknown whether the application to Acme 1 went (timed out). Check the applied jobs list on SEEK before any retry: did it go?',
                   attempts=[{'at': '2026-11-12T22:00:00Z', 'by': 'grok', 'result': 'started', 'note': ''},
                             {'at': '2026-11-12T22:05:00Z', 'by': 'grok', 'result': 'uncertain', 'note': 'timed out'}])
        path = self.dir / 'open' / 'seek-1.json'
        q.write_json(path, old)
        before = path.read_text(encoding='utf-8')
        self.assertEqual(q.find(self.dir, 'seek-1')[1]['status'], 'UNCERTAIN')
        self.assertEqual(self.cli('check')[0], 0)
        self.assertEqual(q.expire(self.dir, now=NOW), [])
        self.assertEqual(path.read_text(encoding='utf-8'), before)   # read, not rewritten

    def test_uncertain_needs_its_mark_and_lives_in_open(self):
        self.assertIn('status: UNCERTAIN needs its uncertain attempt (set by mark ID uncertain)', q.validate(q.fill(entry(1, status='UNCERTAIN'))))
        self.add(entry(1))
        e = self.mark('seek-1', 'uncertain', note='timed out')
        q.write_json(self.dir / 'done' / '2026-11' / 'seek-1.json', e)
        (self.dir / 'open' / 'seek-1.json').unlink()
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('status UNCERTAIN does not belong in 2026-11/', out)


class LinkoutTests(Case):   # F3, F4, S17
    def test_linkout_moves_a_seek_entry_to_the_portal_route_and_releases_the_start(self):
        self.add(entry(1))
        self.add(entry(2, listed_at='2026-11-01'))
        self.next(by='grok')
        code, out, _ = self.cli('mark', 'seek-1', 'linkout', '--by', 'grok')
        self.assertEqual((code, out.strip()), (0, 'seek-1: OPEN'))
        e = q.find(self.dir, 'seek-1')[1]
        self.assertEqual((e['route'], e['status'], e['seek_id'], e['attempts'][-1]['result']), ('EMPLOYER_PORTAL', 'OPEN', '1', 'linkout'))
        self.assertIn("employer's site", e['attempts'][-1]['note'])
        soon = NOW + timedelta(minutes=1)
        self.assertEqual(self.next(now=soon)['id'], 'seek-2')   # no longer on SEEK, and its start no longer holds the spacing
        self.assertEqual(self.next('EMPLOYER_PORTAL', now=soon)['id'], 'seek-1')
        code, _, err = self.cli('mark', 'seek-1', 'linkout', '--by', 'grok')
        self.assertEqual(code, 1)
        self.assertIn('seek-1 is on EMPLOYER_PORTAL', err)
        self.next(by='grok', now=soon)
        code, _, err = self.cli('mark', 'seek-2', 'linkout', '--by', 'claude')
        self.assertEqual(code, 1)
        self.assertIn('was started by grok', err)
        self.assertEqual(self.cli('mark', 'seek-2', 'skipped', '--by', 'grok', '--reason', 'advert closed')[0], 0)   # closed: unchanged


class RepeatTests(Case):   # F13, S18, D56
    def test_the_same_role_in_other_words(self):
        for a, b in (('Junior Civil Drafter', 'Civil Drafter'), ('Entry-Level Civil Drafter', 'civil drafter'), ('Senior Civil Drafter', 'CIVIL DRAFTER.'),
                     ('Graduate / Trainee Civil Engineer', 'Civil Engineer'), ('Civil Engineer (Wollongong)', 'Civil Engineer'), ('Cadet Designer', 'Designer')):
            self.assertTrue(q.same_role(a, b) and q.same_role(b, a), (a, b))
        for a, b in (('Civil Drafter', 'Civil Designer'), ('Site Engineer', 'Civil Site Engineer'), ('Civil Engineer - Wodonga', 'Civil Engineer'), ('', '')):
            self.assertFalse(q.same_role(a, b) or q.same_role(b, a), (a, b))
        for unknown in ('employer portal application receipt (position name blank in the email)', 'email application to admin@example.com.au', '', '(none)'):
            self.assertTrue(q.role_unknown(unknown), unknown)
        self.assertFalse(q.role_unknown('Engineering Technician (employer portal application received)'))

    def test_the_same_role_is_blocked_for_ever_after_an_application(self):
        self.add(entry(1, role='Junior Civil Drafter'))
        self.applied('seek-1', '2026-11-12T22:00:00Z')
        for n, role in ((2, 'Civil Drafter'), (3, 'Civil Drafter (Wollongong)'), (4, 'Senior Civil Drafter')):
            with self.assertRaises(q.Refused) as r:
                self.add(entry(n, company='Acme 1 Pty Ltd', role=role))
            self.assertIn('already applied for this company and role (seek-1)', str(r.exception))
        self.put(entry(5, company='Acme 1', role='Civil Drafter', repeat_ok='second vacancy'))   # arrived by a merge; repeat_ok means nothing
        for days in (1, 400):
            with self.assertRaises(q.NothingToDo) as r:
                self.next(now=NOW + timedelta(days=days))
            self.assertIn('seek-5: already applied for this company and role (seek-1)', str(r.exception))

    def test_another_role_goes_and_next_names_the_earlier_application_once(self):
        self.add(entry(1, role='Junior Civil Drafter'))
        self.applied('seek-1', '2026-11-12T22:00:00Z')
        self.assertEqual(self.add(entry(2, company='Acme 1 Pty Ltd', role='Laboratory Technician'))['status'], 'OPEN')
        line = 'Earlier application at this employer, for another role or outside the repeat block: seek-1 (Junior Civil Drafter, APPLIED 2026-11-13).'
        self.assertIn(line, self.next(by='grok')['notes'])
        self.assertIn(line, q.find(self.dir, 'seek-2')[1]['notes'])   # saved with the start
        self.mark('seek-2', 'open')
        self.assertEqual(self.next(by='grok', now=NOW + timedelta(minutes=30))['notes'].count(line), 1)

    def test_a_prior_application_with_no_role_blocks_every_role_there_for_90_days(self):
        prior = [{'date': '2026-10-20', 'company': 'Gamuda', 'role': 'employer portal application receipt (position name blank in the email)'},
                 {'date': '', 'company': 'Undated Civil', 'role': 'Civil Engineer'}]
        with self.assertRaises(q.Refused) as r:
            self.add(entry(1, company='Gamuda Australia Pty Ltd', role='Civil Designer'), prior=prior)
        self.assertIn('applied to this employer on 2026-10-20 (prior_outreach.json) and the record does not say for which role', str(r.exception))
        with self.assertRaises(q.Refused) as r:   # no date: blocked as if recent
            self.add(entry(2, company='Undated Civil', role='Graduate Civil Engineer'), prior=prior)
        self.assertIn('applied for this company and role on an unknown date', str(r.exception))
        self.assertEqual(self.add(entry(3, company='Undated Civil', role='Civil Designer'), prior=prior)['status'], 'OPEN')
        self.put(entry(4, company='Gamuda', role='Civil Designer', listed_at='2026-11-12'))
        self.assertEqual(self.next(prior=prior)['id'], 'seek-3')
        self.assertEqual(self.next(now=NOW + timedelta(days=90), prior=prior)['id'], 'seek-4')   # 20 Oct plus 90 days has passed

    def test_repeat_ok_is_gone(self):
        self.assertNotIn('repeat-ok', q.__doc__)
        self.assertNotIn('repeat_ok', q.__doc__)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            q.main(['add', '--help'])
        self.assertNotIn('repeat', out.getvalue())


class SpeculativeTests(Case):   # F18
    def test_application_type_is_read_from_old_entries_without_rewriting_them(self):
        files = {}
        for e in (form_entry(1, role='Speculative enquiry: junior civil designer'),
                  form_entry(2, id='tgvk-speculative-enquiry-junior-civil-designe-36e928c0', role='Junior civil designer'),
                  form_entry(3)):
            old = {k: v for k, v in q.fill(e).items() if k != 'application_type'}
            files[e['id']] = self.dir / 'open' / f"{e['id']}.json"
            q.write_json(files[e['id']], old)
        before = {k: p.read_text(encoding='utf-8') for k, p in files.items()}
        self.assertEqual({e['id']: e['application_type'] for _, e in q.load(self.dir)},
                         {'form-1': 'SPECULATIVE_ENQUIRY', 'tgvk-speculative-enquiry-junior-civil-designe-36e928c0': 'SPECULATIVE_ENQUIRY',
                          'form-3': 'ADVERTISED_VACANCY'})
        self.next('EMPLOYER_FORM')
        self.assertEqual({k: p.read_text(encoding='utf-8') for k, p in files.items()}, before)

    def test_add_checks_application_type(self):
        for e in (form_entry(1, application_type='EOI'), form_entry(2, role='Speculative enquiry: civil designer', application_type='ADVERTISED_VACANCY')):
            with self.assertRaises(q.Refused) as r:
                self.add(e)
            self.assertIn('application_type', str(r.exception))
        self.assertEqual(self.add(form_entry(3, application_type='SPECULATIVE_ENQUIRY', role='Civil designer (speculative)'))['application_type'], 'SPECULATIVE_ENQUIRY')
        self.assertEqual(self.add(form_entry(4))['application_type'], 'ADVERTISED_VACANCY')

    def test_advertised_vacancies_go_before_speculative_enquiries(self):
        self.add(form_entry(1, lane='drafter', role='Speculative enquiry: civil drafter'))
        self.add(form_entry(2, lane='engineer', role='Graduate Civil Engineer'))
        self.assertEqual(self.next('EMPLOYER_FORM')['id'], 'form-2')

    def test_speculative_enquiries_stop_at_the_weekly_limit(self):
        for n in (1, 2, 3, 4):
            self.add(form_entry(n, role=f'Speculative enquiry: civil drafter {n}'))
        self.assertEqual(self.next('EMPLOYER_FORM', now=at('2026-11-10T12:00'), by='grok')['id'], 'form-1')
        self.applied('form-1', '2026-11-10T12:05', kind='portal_confirmation', ref='form confirmation page shown')
        self.assertEqual(self.next('EMPLOYER_FORM', now=at('2026-11-11T12:00'), by='grok')['id'], 'form-2')
        self.mark('form-2', 'uncertain', now=at('2026-11-11T12:05'), note='no confirmation page')
        self.assertEqual(self.next('EMPLOYER_FORM', now=at('2026-11-12T12:00'), by='grok')['id'], 'form-3')   # started, not marked
        with self.assertRaises(q.NothingToDo) as r:
            self.next('EMPLOYER_FORM')
        self.assertIn("form-4: this week's speculative enquiries are used up (3 of 3 applied for, uncertain or started in 2026-W46", str(r.exception))
        self.add(form_entry(5, role='Civil Drafter'))
        self.assertEqual(self.next('EMPLOYER_FORM')['id'], 'form-5')   # advertised vacancies still go
        self.mark('form-5', 'skipped', note='test')
        more = {**CONFIG, 'limits': {**CONFIG['limits'], 'max_speculative_per_week': 4}}
        self.assertEqual(self.next('EMPLOYER_FORM', config=more)['id'], 'form-4')
        with self.assertRaises(q.NothingToDo):
            self.next('EMPLOYER_FORM', config={**CONFIG, 'limits': {**CONFIG['limits'], 'max_speculative_per_week': 2}})
        self.assertEqual(self.next('EMPLOYER_FORM', now=at('2026-11-16T12:00'))['id'], 'form-4')   # Monday: a new ISO week


class ClaimTests(Case):   # S5, F2, F22
    def test_next_by_prints_the_git_commands_for_the_claim_after_the_entry(self):
        self.add(entry(1))
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok')
        self.assertEqual((code, json.loads(out)['id']), (0, 'seek-1'))
        git = [line.strip() for line in err.splitlines() if 'git ' in line and '&&' in line]
        self.assertEqual(git, [f"git add -A -- {q._rel(self.dir)} && git commit -m 'queue: seek-1 started by Grok' && git pull --rebase && git push"])
        self.assertIn('do not submit', err)
        self.add(entry(2))
        code, out, err = self.cli('next', '--route', 'SEEK', now=NOW + timedelta(minutes=21))   # a peek claims nothing
        self.assertEqual((code, json.loads(out)['id']), (0, 'seek-2'))
        self.assertNotIn('git ', err)

    def test_list_started_and_only_the_runner_that_started_an_entry_releases_it(self):
        self.add(entry(1))
        self.next(by='Grok')
        code, out, _ = self.cli('list', '--started')
        self.assertEqual((code, out.split()), (0, ['seek-1', 'started', 'by', 'Grok', 'at', '2026-11-13T01:00:00Z', '(SEEK)']))
        self.assertEqual(json.loads(self.cli('list', '--started', '--json')[1]), [{'id': 'seek-1', 'by': 'Grok', 'at': '2026-11-13T01:00:00Z', 'route': 'SEEK'}])
        for action, args in (('open', []), ('failed', ['--note', 'x']), ('skipped', ['--reason', 'x']), ('linkout', []), ('ask', ['--question', 'Did it go?'])):
            code, _, err = self.cli('mark', 'seek-1', action, '--by', 'Claude', *args)
            self.assertEqual(code, 1, action)
            self.assertIn('was started by Grok', err)
        self.assertEqual(self.cli('mark', 'seek-1', 'open', '--by', 'grok')[0], 0)   # the name is compared without case
        self.assertEqual(self.cli('list', '--started')[1].strip(), 'no unmarked starts')
        soon = NOW + timedelta(minutes=1)
        self.assertEqual(self.next(now=soon, by='Grok')['id'], 'seek-1')   # released: neither held nor spaced
        self.assertEqual(self.cli('mark', 'seek-1', 'uncertain', '--by', 'Claude', '--note', 'Grok went quiet after Submit', now=soon)[0], 0)

    def test_expire_leaves_an_unmarked_start(self):
        self.add(entry(1, closes_at='2026-11-13', closes_source='advert'))
        self.next(by='grok')
        self.assertEqual(q.expire(self.dir, now=NOW + timedelta(days=1)), [])
        self.mark('seek-1', 'failed', note='the form would not load, nothing was submitted')
        self.assertEqual([e['id'] for e in q.expire(self.dir, now=NOW + timedelta(days=1))], ['seek-1'])


class OutcomeTests(Case):   # F16, P2
    def test_outcomes_are_recorded_in_place_on_applied_and_uncertain_entries(self):
        self.add(entry(1))
        self.applied('seek-1', '2026-11-03T00:00:00Z')
        path = self.dir / 'done' / '2026-11' / 'seek-1.json'
        code, out, _ = self.cli('outcome', 'seek-1', '--kind', 'rejected', '--at', '2026-11-12', '--by', 'Claude', '--note', 'rejection email, no reason given')
        self.assertEqual((code, out.strip()), (0, 'seek-1: rejected on 2026-11-12 recorded'))
        e = q.read_json(path)
        self.assertEqual(e['outcomes'], [{'kind': 'rejected', 'at': '2026-11-12', 'by': 'Claude', 'note': 'rejection email, no reason given'}])
        self.assertEqual((e['status'], e['receipt']['ref'], len(q.load(self.dir))), ('APPLIED', 'SEEK confirmation screen shown', 1))
        self.assertIn('was already recorded', self.cli('outcome', 'seek-1', '--kind', 'rejected', '--at', '2026-11-12', '--by', 'Claude')[1])
        self.assertEqual(self.cli('outcome', 'seek-1', '--kind', 'acknowledged', '--at', '2026-11-04', '--by', 'Claude')[0], 0)
        self.assertEqual([o['kind'] for o in q.read_json(path)['outcomes']], ['rejected', 'acknowledged'])
        self.assertEqual(self.cli('check')[0], 0)
        self.add(entry(2))
        code, _, err = self.cli('outcome', 'seek-2', '--kind', 'reply', '--at', '2026-11-12', '--by', 'Claude')
        self.assertEqual(code, 1)
        self.assertIn('only on APPLIED or UNCERTAIN entries', err)
        self.mark('seek-2', 'uncertain', note='timed out')
        code, out, _ = self.cli('outcome', 'seek-2', '--kind', 'interview', '--at', '2026-11-13', '--by', 'Claude')
        self.assertEqual(code, 0)
        self.assertIn('still UNCERTAIN', out)

    def test_outcome_notes_and_dates(self):
        self.add(entry(1))
        self.applied('seek-1', '2026-11-03T00:00:00Z')
        path = self.dir / 'done' / '2026-11' / 'seek-1.json'
        before = path.read_text(encoding='utf-8')
        for note in ('x' * 141, 'Sarah replied from sarah.lee@example-firm.com.au', 'asked him to call 0412 345 678',
                     'reference 4471923', 'see https://example.com/a', 'see example-firm.com.au', 'call +44 20 7946 0958'):
            code, out, err = self.cli('outcome', 'seek-1', '--kind', 'reply', '--at', '2026-11-12', '--by', 'Claude', '--note', note)
            self.assertEqual((code, out), (1, ''), note)
            self.assertIn('No names and no quotes', err)
        for day in ('14/11/2026', '2026-02-30', '2026-11-14', 'today'):   # 14 Nov is tomorrow in Melbourne
            self.assertEqual(self.cli('outcome', 'seek-1', '--kind', 'reply', '--at', day, '--by', 'Claude')[0], 1, day)
        self.assertEqual(path.read_text(encoding='utf-8'), before)
        self.assertEqual(self.cli('outcome', 'seek-1', '--kind', 'reply', '--at', '2026-11-12', '--by', 'Claude', '--note', 'x' * 140)[0], 0)
        e = q.read_json(path)   # a note edited in by hand is caught by check
        e['outcomes'][0]['note'] = 'from sarah@example.com'
        q.write_json(path, e)
        self.assertIn('outcomes: a note holds an email address', self.cli('check')[1])


class ReceiptTests(Case):   # P1, S12
    def test_a_receipt_ref_is_plain_words(self):
        self.add(entry(1))
        path = self.dir / 'open' / 'seek-1.json'
        before = path.read_text(encoding='utf-8')
        for ref in ('Application submitted. Your application reference is APP-4471923.', 'Confirmation sent to macdarenz@gmail.com',
                    'https://www.seek.com.au/applied/95487722', 'seen at seek.com.au/applied'):
            code, out, err = self.cli('mark', 'seek-1', 'applied', '--by', 'grok', '--kind', 'seek_confirmation_screen', '--ref', ref)
            self.assertEqual((code, out), (1, ''), ref)
            self.assertIn('plain words such as "SEEK confirmation screen shown"', err)
        self.assertEqual(path.read_text(encoding='utf-8'), before)
        self.assertEqual(self.cli('mark', 'seek-1', 'applied', '--by', 'grok', '--kind', 'seek_confirmation_screen', '--ref', 'SEEK confirmation screen shown')[0], 0)
        receipt = {'at': '2026-10-06T03:00:00Z', 'by': 'owner', 'kind': 'portal_confirmation', 'ref': 'Candidate ID 991234 confirmed'}
        with self.assertRaises(q.Refused):   # a record added by hand is held to the same rule
            self.add(entry(2, status='APPLIED', receipt=receipt))

    def test_gmail_receipts_take_the_message_id_and_the_thread(self):
        self.add(email_entry(1))
        base = ('mark', 'email-1', 'applied', '--by', 'Claude', '--kind', 'gmail_message_id')
        for extra in (('--ref', '18f3a'), ('--ref', 'message 1a1570496429d890'), ('--ref', '1a1570496429d890', '--thread', 'abc')):
            self.assertEqual(self.cli(*base, *extra)[0], 1, extra)
        self.assertEqual(self.cli('mark', 'email-1', 'applied', '--by', 'Claude', '--kind', 'portal_confirmation', '--ref', 'page shown', '--thread', '1a1570496429d890')[0], 1)
        self.assertEqual(self.cli(*base, '--ref', '1A1570496429D890', '--thread', '1a1570496429d891')[0], 0)
        receipt = q.read_json(self.dir / 'done' / '2026-11' / 'email-1.json')['receipt']
        self.assertEqual((receipt['ref'], receipt['thread']), ('1a1570496429d890', '1a1570496429d891'))


class LockTests(Case):   # S11
    def test_take_show_and_release(self):
        code, out, _ = self.cli('lock', 'take', '--by', 'Claude', '--run', RUN)
        self.assertEqual(code, 0)
        self.assertEqual(q.read_json(self.dir / 'SEND_LOCK.json'),
                         {'by': 'Claude', 'run': RUN, 'taken_at': '2026-11-13T01:00:00Z', 'expires_at': '2026-11-13T01:30:00Z'})
        self.assertIn(f"git add -A -- {q._rel(self.dir / 'SEND_LOCK.json')} && git commit -m 'send lock: taken by Claude, run {RUN}' "
                      '&& git pull --rebase && git push', out)
        self.assertIn('someone else holds the lock: do not send', out)
        five = NOW + timedelta(minutes=5)
        for by, run in (('Claude', '20261113T0105Z'), ('Codex', '20261113T0105Z')):
            code, _, err = self.cli('lock', 'take', '--by', by, '--run', run, now=five)
            self.assertEqual(code, 1)
            self.assertIn(f'the send lock is held by Claude (run {RUN}) until 2026-11-13T01:30:00Z', err)
        self.assertEqual(self.cli('lock', 'take', '--by', 'claude', '--run', RUN, '--minutes', '45', now=five)[0], 0)   # renewed
        self.assertEqual(q.read_json(self.dir / 'SEND_LOCK.json')['expires_at'], '2026-11-13T01:50:00Z')
        self.assertIn('44 minutes left', self.cli('lock', 'show', now=five + timedelta(seconds=30))[1])
        self.assertEqual(self.cli('lock', 'release', '--by', 'Claude', '--run', '20261113T0105Z')[0], 1)
        self.assertTrue((self.dir / 'SEND_LOCK.json').exists())
        code, out, _ = self.cli('lock', 'release', '--by', 'Claude', '--run', RUN)
        self.assertEqual(code, 0)
        self.assertIn("git commit -m 'send lock: released by", out)
        self.assertFalse((self.dir / 'SEND_LOCK.json').exists())
        self.assertEqual(self.cli('lock', 'release', '--by', 'Claude', '--run', RUN)[1].strip(), 'no send lock to release')
        self.assertEqual(self.cli('lock', 'show')[1].strip(), 'no send lock')
        self.cli('lock', 'take', '--by', 'Claude', '--run', RUN)
        code, out, _ = self.cli('lock', 'take', '--by', 'Codex', '--run', '20261113T0131Z', now=NOW + timedelta(minutes=31))
        self.assertEqual(code, 0)
        self.assertIn(f'replaced the expired send lock of Claude (run {RUN}', out)
        for bad in (('--run', 'stage=end'), ('--run', 'r'), ('--run', '2026-11-13'), ('--run', RUN, '--minutes', '0'), ('--run', RUN, '--minutes', '500'), ()):
            self.assertEqual(self.cli('lock', 'take', '--by', 'Codex', *bad)[0], 1, bad)

    def test_next_on_email_needs_the_runners_own_unexpired_lock(self):
        self.add(email_entry(1))
        for args, why in ((('--by', 'Claude'), '--run'), ((), '--run'), (('--by', 'Claude', '--run', RUN), 'there is no send lock')):
            code, out, err = self.cli('next', '--route', 'EMAIL', *args)
            self.assertEqual((code, out), (1, ''), args)
            self.assertIn(why, err)
        self.cli('lock', 'take', '--by', 'Codex', '--run', '20261113T0055Z')
        code, _, err = self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN)
        self.assertEqual(code, 1)
        self.assertIn('the send lock is held by Codex', err)
        self.cli('lock', 'release', '--by', 'Codex', '--run', '20261113T0055Z')
        self.cli('lock', 'take', '--by', 'Claude', '--run', RUN)
        late = NOW + timedelta(minutes=31)
        code, _, err = self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN, now=late)
        self.assertEqual(code, 1)
        self.assertIn('your send lock expired at 2026-11-13T01:30:00Z', err)
        self.cli('lock', 'take', '--by', 'Claude', '--run', RUN, now=late)
        code, out, _ = self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN, now=late)
        self.assertEqual((code, json.loads(out)['id']), (0, 'email-1'))
        self.add(entry(2))
        self.assertEqual(self.cli('next', '--route', 'SEEK')[0], 0)   # the other routes need no lock


class AddFieldTests(Case):   # F7
    def test_title_seek_id_and_closes_source_are_filled_in(self):
        draft = {'lane': 'drafter', 'route': 'SEEK', 'company': 'Acme Civil', 'title': 'Junior Civil Drafter',
                 'url': 'https://www.seek.com.au/job/95900099?type=standard', 'closes_at': '2026-12-13'}
        code, out, _ = self.cli('add', self.file('draft.json', draft), '--by', 'Claude')
        self.assertEqual((code, out.strip()), (0, 'added seek-95900099 (OPEN, SEEK, drafter)'))
        e = q.find(self.dir, 'seek-95900099')[1]
        self.assertEqual((e['role'], e['seek_id'], e['closes_source'], e['created_by'], 'title' in e),
                         ('Junior Civil Drafter', '95900099', 'listing_expiry', 'Claude', False))
        kept = self.add(dict(draft, url='https://www.seek.com.au/job/95900100', closes_source='advert', role='Civil Designer', title='ignored'))
        self.assertEqual((kept['closes_source'], kept['role'], 'title' in kept), ('advert', 'Civil Designer', False))

    def test_help_lists_the_fields_add_requires_and_accepts(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            q.main(['add', '--help'])
        for text in (q._parser().format_help(), out.getvalue()):
            for word in ('Entry fields for add', 'required  lane', 'route (SEEK, EMAIL, EMPLOYER_PORTAL or EMPLOYER_FORM)', 'company',
                         'role (title is taken as role)', 'url', 'seek_id', 'email {to, subject, body, evidence_url', 'application_type',
                         'closes_source', 'listing_expiry when closes_at is given without it', 'verify_before_submit', 'questions',
                         'resume_variant', 'receipt {at, by, kind, ref}'):
                self.assertIn(word, text)


class VerifyBeforeSubmitTests(Case):   # F9
    def test_checks_are_validated_and_printed_by_next(self):
        for bad in ('Open the careers page', ['line one\nline two'], ['x' * 201], [''], [3]):
            with self.assertRaises(q.Refused, msg=bad) as r:
                self.add(entry(1, verify_before_submit=bad))
            self.assertIn('verify_before_submit', str(r.exception))
        checks = ['Open https://www.tgvk.com.au/careers/ live: it must still invite a CV to the address in email.to, else mark skipped',
                  'Read the Key Selection Criteria in the Position Description first']
        self.add(entry(1, verify_before_submit=checks))
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, json.loads(out)['verify_before_submit']), (0, checks))
        self.assertIn('BEFORE SUBMITTING, CHECK:\n  - ' + checks[0] + '\n  - ' + checks[1] + '\n', err)
        self.put(entry(2, verify_before_submit='Open the careers page'))
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('seek-2: verify_before_submit', out)


class ResumeTests(Case):   # F20, S20
    def test_next_names_the_resume_file_and_its_sha256(self):
        self.add(entry(1, lane='technician'))
        path = SCRIPTS.parents[1] / 'documents' / 'resume' / 'Marc_Masarate_Resume_Technician.pdf'
        self.assertTrue(path.exists(), path)
        code, _, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual(code, 0)
        self.assertIn(f'RESUME: documents/resume/Marc_Masarate_Resume_Technician.pdf sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}', err)
        with mock.patch.object(q, 'RESUME_DIR', self.root / 'nothing'):
            self.assertIn('Marc_Masarate_Resume_Technician.pdf is missing: do not submit', q.handout_notes(q.find(self.dir, 'seek-1')[1], self.dir)[0])


class ReportTests(Case):   # F24
    def test_report_by_lane_state_route_with_outcomes_and_uncertain(self):
        self.add(entry(1, lane='drafter', location='Melton VIC'))
        self.add(entry(2, lane='technician', location='Townsville, Northern QLD'))
        self.add(email_entry(3, lane='engineer', location='Perth WA'))
        self.add(form_entry(4, route='EMPLOYER_PORTAL', location='Fully remote'))
        self.add(entry(5))
        self.applied('seek-1', '2026-11-12T01:00:00Z')
        self.applied('seek-2', '2026-11-10T01:00:00Z')
        self.applied('email-3', '2026-11-13T00:30:00Z', kind='gmail_message_id', ref='1a1570496429d890')
        self.applied('form-4', '2026-11-01T01:00:00Z', kind='portal_confirmation', ref='portal confirmation page shown')
        self.mark('seek-5', 'uncertain', note='timed out')
        q.record_outcome(self.dir, 'seek-2', 'rejected', '2026-11-12', 'Claude', now=NOW)
        q.record_outcome(self.dir, 'form-4', 'acknowledged', '2026-11-02', 'Claude', now=NOW)
        r = q.report(self.dir, NOW, 7)
        self.assertEqual(r, {'from': '2026-11-07', 'to': '2026-11-13', 'days': 7, 'applied': 3,
                             'by_lane': {'drafter': 1, 'technician': 1, 'engineer': 1},
                             'by_state': {'VIC': 1, 'NSW': 0, 'QLD': 1, 'WA': 1, 'SA': 0, 'TAS': 0, 'ACT': 0, 'NT': 0, 'other': 0},
                             'by_route': {'SEEK': 2, 'EMAIL': 1, 'EMPLOYER_PORTAL': 0, 'EMPLOYER_FORM': 0},
                             'outcomes': {'acknowledged': 0, 'rejected': 1, 'reply': 0, 'interview': 0, 'offer': 0}, 'uncertain_now': 1})
        wide = q.report(self.dir, NOW, 14)
        self.assertEqual((wide['applied'], wide['by_state']['other'], wide['outcomes']['acknowledged']), (4, 1, 1))
        code, out, _ = self.cli('report', '--days', '7')
        self.assertEqual(code, 0)
        for line in ('applications with a receipt, 2026-11-07 to 2026-11-13 (7 days, Melbourne dates): 3',
                     'by lane: drafter 1, technician 1, engineer 1', 'by state: VIC 1, NSW 0, QLD 1, WA 1, SA 0, TAS 0, ACT 0, NT 0, other 0',
                     'by route: SEEK 2, EMAIL 1, EMPLOYER_PORTAL 0, EMPLOYER_FORM 0',
                     'outcomes dated in those days: acknowledged 0, rejected 1, reply 0, interview 0, offer 0', 'uncertain now (unknown whether they went): 1'):
            self.assertIn(line, out.splitlines())
        self.assertEqual(json.loads(self.cli('report', '--json')[1])['applied'], 3)
        self.assertEqual(self.cli('report', '--days', '0')[0], 1)

    def test_state_of(self):
        for location, state in (('Port Adelaide, Adelaide SA', 'SA'), ('Wagga Wagga / Forbes, NSW', 'NSW'), ('Hobart, Tasmania', 'TAS'),
                                ('Darwin NT', 'NT'), ('Canberra ACT', 'ACT'), ('Henderson WA (Perth)', 'WA'), ('Fully remote', 'other'),
                                ('', 'other'), ('Washington', 'other'), ('Victoria Park, Perth WA', 'WA'), ('Bendigo, Victoria', 'VIC')):
            self.assertEqual(q.state_of(location), state, location)


class StatsTests(Case):   # F25
    def test_stats_names_waiting_ask_owner_and_uncertain(self):
        self.add(entry(1))
        self.add(entry(2, status='ASK_OWNER', ask_owner='Would you move to Cairns?'))
        self.add(entry(3))
        self.mark('seek-3', 'uncertain', note='timed out')
        lines = self.cli('stats')[1].splitlines()
        for line in ('waiting (OPEN, ready or held), queue_open: SEEK 1, EMAIL 0, EMPLOYER_PORTAL 0, EMPLOYER_FORM 0, total 1', 'ask_owner: 1', 'uncertain: 1'):
            self.assertIn(line, lines)
        self.assertIn('stats: queue_open counts status OPEN only (ready or held), not ASK_OWNER or UNCERTAIN', ' '.join(q.__doc__.split()))


class JournalRunIdTests(unittest.TestCase):   # F12
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, path in (('JOURNAL', Path(tmp.name) / 'journal.jsonl'), ('RUNS', Path(tmp.name) / 'runs')):
            patch = mock.patch.object(journal, name, path)
            patch.start()
            self.addCleanup(patch.stop)

    def test_note_refuses_a_run_id_that_start_did_not_make(self):
        for bad in ('stage=end', 'r', '20261114T0202', '$RUN', ''):
            with self.assertRaises(SystemExit) as stop:
                journal.main(['note', bad, 'stage=end', 'queue_open=1'])
            self.assertIn('is not a run id', str(stop.exception.code), bad)
        with self.assertRaises(SystemExit) as stop:
            journal.main(['note', 'stage=end', 'queue_open=1'])
        self.assertIn('the run id is missing', str(stop.exception.code))
        self.assertEqual(journal.rows(), [])
        with contextlib.redirect_stdout(io.StringIO()):
            journal.main(['note', '20261114T0202Z', 'stage=discover'])
            run_id = journal.start()
        self.assertTrue(journal.RUN_ID.fullmatch(run_id), run_id)
        self.assertEqual([r['run_id'] for r in journal.rows()], ['20261114T0202Z', run_id])


if __name__ == '__main__':
    unittest.main()
