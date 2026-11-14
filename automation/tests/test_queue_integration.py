"""Packages A (queue core) and B (answer gate, letters) together, 14 Nov 2026: next works every answer out again from
facts.json AND keeps the integrity check, the quiet hours, the caps, UNCERTAIN, the repeat rule, the speculative limit
and the send lock; answer never ends a start another runner made; letter_pdf.py refuses an id with two files.
Offline: temp folders only, the repository's own facts.json read as data."""
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
_spec = importlib.util.spec_from_file_location('apply_queue_integration', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)
sys.path.insert(0, str(SCRIPTS))
import letter_pdf  # noqa: E402

FACTS = json.loads((SCRIPTS.parent / 'facts.json').read_text(encoding='utf-8'))
NOW = datetime(2026, 11, 13, 1, 0, tzinfo=timezone.utc)   # midday on Friday 13 Nov 2026 in Melbourne
RUN = '20261113T0100Z'
CONFIG = {'lanes': {'drafter': {'rank': 1}, 'technician': {'rank': 2}, 'engineer': {'rank': 3}},
          'limits': {'seek_submissions_per_day': 6, 'email_sends_per_day': 3, 'portal_submissions_per_day': 3,
                     'min_minutes_between_seek_submissions': 20, 'repeat_block_days': 90, 'max_speculative_per_week': 1}}
POLICE = 'Do you have a current Police Check (National Police Certificate) for employment?'
NOTICE = 'How much notice are you required to give your current employer?'
TRAFFIC = 'Do you have Traffic Control experience?'
LETTER = ('Hello,\n\n'
          'I am applying for the Junior Civil Drafter role. Your advert asks for subdivision drawings in Civil 3D.\n\n'
          'In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks and '
          'stormwater drainage in AutoCAD and Civil 3D to Australian Standards.\n\n'
          'I live in Melton and can start two weeks after an offer. Full working rights in Australia (Subclass 485 visa), no '
          'sponsorship needed. Could we talk this week?\n\n'
          'Marc Masarate')


def entry(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


def email_entry(n, **kw):
    e = entry(n, route='EMAIL', seek_id='', url=f'https://example{n}.com.au/careers', id=f'email-{n}', cover_letter_text=LETTER,
              email={'to': f'jobs@example{n}.com.au', 'subject': 'Junior Civil Drafter', 'body': 'Hello.',
                     'evidence_url': f'https://example{n}.com.au/careers'})
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

    def add(self, e):
        return q.add(e, self.dir, FACTS, NOW)

    def stored(self, entry_id):
        return q.find(self.dir, entry_id)[1]

    def stale_answer(self, entry_id):
        """Store the answer the old rules gave to the police check for employment ('Yes'), as the live queue held it."""
        path, e = q.find(self.dir, entry_id)
        qn = next(x for x in e['questions'] if x['question'] == POLICE)
        qn.update(answer='Yes', basis='answers.police_check', status='answered')
        q.write_json(path, e)
        return path

    def files(self):
        return {str(p.relative_to(self.dir)): p.read_bytes() for p in sorted(self.dir.rglob('*.json'))}

    def cli(self, *args, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--prior', str(self.prior),
                           '--now', q.iso(now), *args])
        return code, out.getvalue(), err.getvalue()


class AnswerKeepsOtherRunnersStarts(Case):
    """B's `answer ID --question` ended any unmarked start; A lets only the runner that started an entry release it."""

    def test_an_unanswered_question_from_another_runner_stores_nothing_and_keeps_the_start(self):
        self.add(entry(1, questions=[NOTICE]))
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', '20261113T0100Z')[0], 0)
        before = self.files()
        for by in (('--by', 'Claude'), ()):
            code, out, err = self.cli('answer', 'seek-1', '--question', TRAFFIC, '--option', 'Yes', '--option', 'No', *by)
            self.assertEqual((code, out), (5, ''), by)
            self.assertIn('Do not submit; leave the form. Nothing is stored: seek-1 was started by Grok', err)
            self.assertEqual(self.files(), before, by)
        self.assertIn('started by Grok', self.cli('list', '--started')[1])
        # the runner that started it (any letter case) ends its own start: ASK_OWNER, no longer under way
        code, _, err = self.cli('answer', 'seek-1', '--question', TRAFFIC, '--option', 'Yes', '--option', 'No', '--by', 'grok')
        self.assertEqual(code, 5)   # M2: the right name without the session's run stores nothing either
        self.assertIn('in another run (session)', err)
        self.assertEqual(self.files(), before)
        code, _, err = self.cli('answer', 'seek-1', '--question', TRAFFIC, '--option', 'Yes', '--option', 'No', '--by', 'grok', '--run', RUN)
        self.assertEqual(code, 5)
        self.assertIn('seek-1 is now ASK_OWNER: do not submit; leave the form', err)
        e = self.stored('seek-1')
        self.assertEqual((e['status'], e['attempts'][-1]['result'], e['attempts'][-1]['by']), ('ASK_OWNER', 'asked_owner', 'grok'))
        self.assertEqual(self.cli('list', '--started')[1].strip(), 'no unmarked starts')

    def test_an_answered_question_on_another_runners_start_is_still_answered(self):
        self.add(entry(1, questions=[NOTICE]))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', '20261113T0100Z')
        code, out, _ = self.cli('answer', 'seek-1', '--question', NOTICE, '--option', '2 weeks', '--option', '1 month', '--by', 'Claude')
        self.assertEqual((code, out), (0, '2 weeks\n'))
        self.assertEqual(q.started(self.stored('seek-1'))['by'], 'Grok')


class NextNamesWhatItsRecomputeRewrote(Case):
    """B's recompute saves entry files; next now says which, and how to commit them when no claim follows."""

    def test_peek_claim_and_nothing_to_hand_out(self):
        self.add(entry(1, questions=[POLICE]))
        self.stale_answer('seek-1')
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, json.loads(out)['id']), (0, 'seek-1'))
        self.assertIn('ANSWERS RECOMPUTED from facts.json, files rewritten (1): seek-1\nCommit and push them (run from this folder):\n'
                      "  git add -A -- ", err)
        self.assertIn("git commit -m 'queue: answers recomputed from facts.json' && git pull --rebase --autostash && git push", err)
        self.assertEqual(self.stored('seek-1')['questions'][0]['answer'], 'No. Willing to obtain a new check.')
        code, out, err = self.cli('next', '--route', 'SEEK')   # nothing changed since: nothing to report
        self.assertNotIn('ANSWERS RECOMPUTED', err)
        self.stale_answer('seek-1')
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', '20261113T0100Z')
        self.assertEqual(code, 0)
        self.assertIn("ANSWERS RECOMPUTED from facts.json, files rewritten (1): seek-1\n(the claim's git commands below commit them with it)", err)
        self.assertIn("queue: seek-1 started by Grok", err)
        # an entry the new facts hold back: exit 4, and the rewritten file is named with its git commands
        self.add(entry(2, questions=[NOTICE]))
        changed = copy.deepcopy(FACTS)
        changed['answers']['notice_period'] = 'Not on record: skip and report.'
        q.write_json(self.facts, changed)
        code, out, err = self.cli('next', '--route', 'SEEK', now=NOW + timedelta(minutes=30))
        self.assertEqual((code, out), (4, ''))
        self.assertIn('ANSWERS RECOMPUTED from facts.json, files rewritten (1): seek-2\nCommit and push them', err)
        self.assertEqual(self.stored('seek-2')['status'], 'ASK_OWNER')


class NextGatesComeBeforeTheRecompute(Case):
    def test_quiet_hours_and_a_check_problem_stop_next_before_any_file_is_rewritten(self):
        self.add(entry(1, questions=[POLICE]))
        self.stale_answer('seek-1')
        before = self.files()
        night = datetime(2026, 11, 13, 11, 30, tzinfo=timezone.utc)   # 22:30 in Melbourne
        code, out, err = self.cli('next', '--route', 'SEEK', now=night)
        self.assertEqual((code, out), (3, ''))
        self.assertIn('quiet_hours', err)
        bad = q.save(self.dir, q.fill(entry(2, lane='labourer')))
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('seek-2: lane: one of', err)
        bad.unlink()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.cli('next', '--route', 'SEEK')[0], 0)
        self.assertNotEqual(self.files(), before)   # now the stale answer is replaced

    def test_a_hand_set_answer_stops_every_route_until_answer_ID_recomputes(self):
        self.add(entry(1, questions=[NOTICE]))
        path, e = q.find(self.dir, 'seek-1')
        e['questions'][0].update(answer='1 month', basis='answers.notice_period', by='Claude')
        q.write_json(path, e)
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('seek-1: questions: the answer Claude set does not stand', out)
        for route in ('SEEK', 'EMPLOYER_PORTAL'):
            self.assertEqual(self.cli('next', '--route', route)[0], 1, route)
        self.assertEqual(self.cli('answer', 'seek-1')[0], 0)
        self.assertEqual(self.stored('seek-1')['questions'][0]['answer'], '2 weeks')
        self.assertEqual(self.cli('check')[0], 0)
        self.assertEqual(json.loads(self.cli('next', '--route', 'SEEK')[1])['id'], 'seek-1')


class NextRecomputesAndKeepsEveryRule(Case):
    def test_seek_recompute_with_caps_spacing_uncertain_and_repeats(self):
        self.add(entry(1, company='Acme Civil Pty Ltd', role='Civil Drafter', questions=[POLICE], listed_at='2026-11-12'))
        self.add(entry(2, company='Beta', listed_at='2026-11-11'))
        self.stale_answer('seek-1')
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', '20261113T0100Z')
        self.assertEqual((code, json.loads(out)['id'], json.loads(out)['questions'][0]['answer']), (0, 'seek-1', 'No. Willing to obtain a new check.'))
        self.assertIn(f'Q: {POLICE} | give: No. Willing to obtain a new check.', err)
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', '20261113T0100Z', now=NOW + timedelta(minutes=5))[0], 3)   # the start counts
        self.assertEqual(self.cli('mark', 'seek-1', 'uncertain', '--by', 'Grok', '--note', 'the page froze after submit')[0], 0)
        self.assertEqual(self.cli('next', '--route', 'SEEK', now=NOW + timedelta(minutes=10))[0], 3)   # the uncertain mark counts
        # a repost of the same job at the same employer is held while the first is UNCERTAIN; the answers still follow facts
        q.save(self.dir, q.fill(entry(3, company='Acme Civil', role='Junior Civil Drafter', questions=[POLICE])))
        self.stale_answer('seek-3')
        later = NOW + timedelta(minutes=30)
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', '20261113T0100Z', now=later)
        self.assertEqual((code, json.loads(out)['id']), (0, 'seek-2'))
        e3 = self.stored('seek-3')
        self.assertEqual(e3['questions'][0]['answer'], 'No. Willing to obtain a new check.')
        self.assertIn('seek-1 for this company and role is UNCERTAIN', '; '.join(q.blockers(e3, q.hold_context([x for _, x in q.load(self.dir)], CONFIG, later))))
        # a cap of 2 is used up by one UNCERTAIN entry and one unmarked start
        tight = copy.deepcopy(CONFIG)
        tight['limits']['seek_submissions_per_day'] = 2
        q.write_json(self.config, tight)
        code, _, err = self.cli('next', '--route', 'SEEK', now=later + timedelta(minutes=30))
        self.assertEqual(code, 3)
        self.assertIn("the day's cap is reached (2 of 2", err)

    def test_email_recompute_with_the_lock_and_the_speculative_limit(self):
        spec = dict(role='Speculative enquiry: Junior Civil Drafter', questions=[POLICE])
        self.add(email_entry(1, **spec))
        self.add(email_entry(2, **spec))
        self.add(email_entry(3, questions=[POLICE], listed_at='2026-11-01'))
        for n in (1, 3):
            self.stale_answer(f'email-{n}')
        self.assertIn('there is no send lock', self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN)[2])
        self.assertEqual(self.cli('lock', 'take', '--by', 'Claude', '--run', RUN)[0], 0)
        code, out, err = self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN)
        e = json.loads(out)
        self.assertEqual((code, e['id'], e['application_type']), (0, 'email-3', 'ADVERTISED_VACANCY'))   # advertised first
        self.assertEqual(e['questions'][0]['answer'], 'No. Willing to obtain a new check.')
        self.assertIn('ANSWERS RECOMPUTED from facts.json, files rewritten (2): email-1, email-3', err)
        self.assertEqual(self.cli('mark', 'email-3', 'applied', '--by', 'Claude', '--kind', 'gmail_message_id', '--ref', '1a1570496429d890')[0], 0)
        code, out, _ = self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN, now=NOW + timedelta(minutes=5))
        self.assertEqual((code, json.loads(out)['id']), (0, 'email-1'))
        self.assertEqual(self.stored('email-1')['questions'][0]['answer'], 'No. Willing to obtain a new check.')
        self.assertEqual(self.cli('mark', 'email-1', 'applied', '--by', 'Claude', '--kind', 'gmail_message_id', '--ref', '1a1570496429d891')[0], 0)
        code, out, err = self.cli('next', '--route', 'EMAIL', '--by', 'Claude', '--run', RUN, now=NOW + timedelta(minutes=10))
        self.assertEqual((code, out), (4, ''))
        self.assertIn("email-2: this week's speculative enquiries are used up (1 of 1", err)
        code, _, err = self.cli('next', '--route', 'EMAIL', '--by', 'Codex', '--run', '20261113T0105Z', now=NOW + timedelta(minutes=10))
        self.assertEqual(code, 1)
        self.assertIn('the send lock is held by Claude', err)


class LetterPdfAndTheStaleCopy(Case):
    def test_letter_pdf_refuses_an_id_with_an_open_and_a_done_file(self):
        e = q.fill(email_entry(1))
        q.write_json(self.dir / 'open' / 'email-1.json', e)
        self.assertEqual(letter_pdf.find_entry('email-1', self.dir)['id'], 'email-1')
        q.write_json(self.dir / 'done' / '2026-11' / 'email-1.json', dict(e, status='APPLIED'))
        with self.assertRaises(ValueError) as r:
            letter_pdf.find_entry('email-1', self.dir)
        self.assertIn('2 files', str(r.exception))
        self.assertIn('remove the stale copy first', str(r.exception))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(letter_pdf.main(['email-1', str(self.root / 'out.pdf'), '--dir', str(self.dir)]), 1)
        self.assertFalse((self.root / 'out.pdf').exists())


if __name__ == '__main__':
    unittest.main()
