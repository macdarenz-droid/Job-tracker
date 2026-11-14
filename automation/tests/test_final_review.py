"""The last review of the merged queue, 14 Nov 2026 (safety B1-B3, M1-M6, m1, m2; privacy R1-R8). Each test failed on
commit 0fc8911 and passes after the fix. Offline: temp folders and temp git repositories only; the repository's own
facts.json and .gitattributes are read as data."""
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
_spec = importlib.util.spec_from_file_location('apply_queue_final_review', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)
sys.path.insert(0, str(SCRIPTS))
import answers  # noqa: E402
import checks  # noqa: E402
import journal  # noqa: E402
import letter_pdf  # noqa: E402

FACTS = json.loads((SCRIPTS.parent / 'facts.json').read_text(encoding='utf-8'))
NOW = datetime(2026, 11, 13, 1, 0, tzinfo=timezone.utc)   # midday on Friday 13 Nov 2026 in Melbourne
RUN, OTHER_RUN = '20261113T0100Z', '20261113T010600Z'
TODAY = date(2026, 11, 14)
CONFIG = {'lanes': {'drafter': {'rank': 1}, 'technician': {'rank': 2}, 'engineer': {'rank': 3}},
          'limits': {'seek_submissions_per_day': 6, 'email_sends_per_day': 3, 'portal_submissions_per_day': 3,
                     'min_minutes_between_seek_submissions': 20, 'repeat_block_days': 90, 'max_speculative_per_week': 3}}
SALARY = "What's your expected annual base salary?"
SAL = ['$40k', '$50k', '$60k', '$70k', '$80k', '$90k', '$100k']
BANDS = ['$40k - $50k', '$50k - $60k', '$60k - $70k', '$70k - $80k', '$80k - $90k', '$90k+']
YN = ['Yes', 'No']
LETTER = ('Hello,\n\n'
          'I am applying for the Junior Civil Drafter role. Your advert asks for subdivision drawings in Civil 3D.\n\n'
          '{middle}\n\n'
          'I live in Melton and can start two weeks after an offer. Full working rights in Australia (Subclass 485 visa), no '
          'sponsorship needed. Could we talk this week?\n\n'
          'Marc Masarate')
GOOD_MIDDLE = ('In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks '
               'and stormwater drainage in AutoCAD and Civil 3D to Australian Standards.')


def gate(question, options=None, pay=None, today=TODAY):
    return answers.answer(question, options or [], FACTS, pay=pay, today=today)


def entry(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


def email_entry(n, **kw):
    e = entry(n, route='EMAIL', seek_id='', url=f'https://example{n}.com.au/careers', id=f'email-{n}',
              cover_letter_text=LETTER.format(middle=GOOD_MIDDLE),
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

    def add(self, e, now=NOW):
        return q.add(e, self.dir, FACTS, now, config=CONFIG, prior=[])

    def stored(self, entry_id):
        return q.find(self.dir, entry_id)[1]

    def files(self):
        return {str(p.relative_to(self.dir)): p.read_bytes() for p in sorted(self.dir.rglob('*.json'))}

    def cli(self, *args, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--prior', str(self.prior),
                           '--now', q.iso(now), *args])
        return code, out.getvalue(), err.getvalue()


# ------------------------------------------------------------------ B1, R8: the salary answer needs the advert's pay

class SalaryNeedsTheAdvertsPay(Case):
    def test_no_pay_on_record_is_not_the_same_as_no_pay_stated(self):  # B1
        r = gate(SALARY, SAL)
        self.assertEqual(r['status'], 'unanswered')
        self.assertEqual(r['why'], answers.PAY_UNKNOWN)
        self.assertEqual(gate(SALARY, SAL, pay='')['status'], 'unanswered')
        self.assertEqual(gate(SALARY, SAL, pay='not stated')['answer'], '$70k')
        self.assertEqual(gate(SALARY, SAL, pay='None')['answer'], '$70k')
        self.assertEqual(gate(SALARY, SAL, pay='$80,000 – $100,000 per year')['answer'], '$80k')
        self.assertEqual(gate(SALARY, pay='not stated')['answer'], '65000 to 75000')

    def test_a_position_or_reference_number_is_not_pay(self):  # R8
        for pay, band, free in (('Position number 51234. $82,000 – $100,000 per year', '$80k - $90k', '82000'),
                                ('Ref 54321 - $85k + super', '$80k - $90k', '85000'),
                                ('Vacancy 52345: Band 5, $80,057 per year', '$80k - $90k', '80057'),
                                ('Job no. 61234, salary 85000', '$80k - $90k', '85000')):
            self.assertEqual(gate(SALARY, BANDS, pay=pay)['answer'], band, pay)
            self.assertEqual(gate(SALARY, pay=pay)['answer'], free, pay)
        self.assertEqual(answers.money('Position number 51234'), [])
        self.assertEqual(answers.money('80000 - 95000'), [80000, 95000])

    def test_answer_on_an_entry_without_advert_pay_stays_with_the_owner(self):  # B1, the reviewer's seek-95773573 case
        self.put_asking_entry()
        code, out, err = self.cli('answer', 'seek-1', '--question', SALARY, *sum((['--option', o] for o in SAL), []))
        self.assertEqual((code, out), (5, ''))
        self.assertIn("advert's pay is not recorded", err)
        self.assertEqual(self.stored('seek-1')['status'], 'ASK_OWNER')
        code, out, _ = self.cli('answer', 'seek-1', '--advert-pay', '$80,000 – $100,000 per year')
        self.assertEqual((code, json.loads(out)['status']), (0, 'OPEN'))
        e = self.stored('seek-1')
        self.assertEqual((e['advert_pay'], e['questions'][0]['answer']), ('$80,000 – $100,000 per year', '$80k'))

    def put_asking_entry(self):
        e = q.fill(entry(1, questions=[{'question': SALARY, 'options': SAL}], status='ASK_OWNER',
                         ask_owner='No standing answer for this form question: ' + SALARY))
        q.save(self.dir, e)

    def test_add_takes_a_candidates_salary_and_refuses_a_salary_question_without_pay(self):  # B1
        with self.assertRaises(q.Refused) as r:
            self.add(entry(1, questions=[{'question': SALARY, 'options': SAL}]))
        self.assertIn('has no advert_pay', str(r.exception))
        with self.assertRaises(q.Refused):
            self.add(entry(1, questions=[{'question': SALARY, 'options': SAL}], salary=None))   # SEEK showed none: read the advert
        e = self.add(entry(1, questions=[{'question': SALARY, 'options': SAL}], salary='$80,000 – $100,000 per year'))
        self.assertEqual((e['advert_pay'], e['questions'][0]['answer'], e['status']), ('$80,000 – $100,000 per year', '$80k', 'OPEN'))
        self.assertNotIn('salary', e)
        e = self.add(entry(2, questions=[{'question': SALARY, 'options': SAL}], advert_pay='not stated'))
        self.assertEqual(e['questions'][0]['answer'], '$70k')

    def test_recompute_takes_the_band_away_from_an_entry_with_no_pay(self):  # B1: next's recompute
        e = q.fill(entry(1, questions=[{'question': SALARY, 'options': SAL, 'answer': '$70k', 'basis': 'answers.expected_salary.rule',
                                        'status': 'answered'}]))
        q.save(self.dir, e)
        q.apply_answers(e, FACTS)
        self.assertEqual((e['status'], e['questions'][0]['status']), ('ASK_OWNER', 'unanswered'))


# ------------------------------------------------------------------ B2, B3, M1: the gate on joined, past and dated questions

class GateRefusesJoinedAndPastQuestions(unittest.TestCase):
    def test_a_subject_joined_to_another_requirement_is_not_answered(self):  # B2
        for text in ('Do you hold a current White Card and a current First Aid certificate?',
                     'Do you hold a White Card and a Working at Heights ticket?',
                     'Do you hold a Construction Induction (White Card) and Confined Spaces ticket?',
                     'Do you hold a White Card / First Aid?',
                     'Do you hold a White Card & First Aid certificate?',
                     'Are you willing to relocate at your own expense?',
                     'Are you willing to relocate to Perth at your own cost, without relocation assistance?',
                     'Do you have your own car with comprehensive insurance?',
                     'Are you willing to work FIFO on a 28/7 roster including night shifts?',
                     'Are you willing to relocate and work night shift?',
                     'Are you available to travel overseas for this role?',
                     'Are you willing to work FIFO night shifts?',
                     'Do you require employer sponsorship to work in Australia long term?',
                     'Will you require sponsorship after your current visa expires?'):
            self.assertEqual(gate(text, YN)['status'], 'unanswered', text)

    def test_the_single_subject_questions_are_still_answered(self):  # no regression on the real wordings
        for text, want in (('Do you hold a current White Card?', 'Yes'),
                           ('Do you hold a Construction Induction Safety certificate (White Card)?', 'Yes'),
                           ('Do you hold a current White Card / General Construction Induction Training Card?', 'Yes'),
                           ('Are you available to work FIFO / DIDO contracts?', 'Yes'),
                           ('As part of our recruitment process, you may be required to attend a pre employment medical, drug & alcohol '
                            'testing, and/or complete a medical check-list. Are you willing to do so?', 'Yes'),
                           ('Are you willing to undergo a pre-employment medical and drug and alcohol test?', 'Yes'),
                           ('Are you willing and able to travel to project sites as required?', 'Yes'),
                           ('Are you willing to relocate for this role?', 'Yes'),
                           ('Do you own or have regular access to a car?', 'Yes'),
                           ('Do you require sponsorship to work in Australia?', 'No')):
            self.assertEqual(gate(text, YN)['answer'], want, text)

    def test_something_already_done_is_not_answered_from_a_willing_line(self):  # B3
        for text in ('Have you completed a Coal Board Medical?', 'Have you completed a pre-employment medical in the last 12 months?',
                     'Have you completed a drug and alcohol test?', 'Have you relocated for work before?',
                     'Have you completed a police check?'):
            self.assertEqual(gate(text, YN)['status'], 'unanswered', text)
        for text in ('Have you obtained a police check in the last 6 months?',
                     'Have you obtained a Police Check (National Police Certificate) for employment?',
                     'Have you completed a National Police Check for employment purposes?',
                     'Have you undertaken a National Police Check within the last 3 months?'):
            self.assertEqual(gate(text, YN)['answer'], 'No', text)
        self.assertEqual(gate('Are you willing to obtain a National Police Check?', YN)['answer'], 'Yes')

    def test_a_police_check_window_is_judged_by_the_month_of_issue(self):  # M1
        for text in ('Do you have a recent National Police Check (within the past 12 months)?',
                     'Do you have a police check that is less than 12 months old?',
                     'Do you have a police check dated within the last year?',
                     'Do you hold a National Police Check issued in 2026?',
                     'Have you had a police check in the past 2 years?'):
            self.assertEqual(gate(text, YN)['answer'], 'Yes', text)
        for text in ('Do you have a recent National Police Check (within the past 12 months)?',
                     'Do you have a police check that is less than 12 months old?',
                     'Do you have a police check dated within the last year?'):
            self.assertEqual(gate(text, YN, today=date(2027, 4, 1))['answer'], 'No', text)
        self.assertEqual(gate('Do you hold a police check issued within the last 6 months?', YN)['answer'], 'No')
        self.assertEqual(gate('Do you hold a police check issued within the last 6 months?')['answer'], 'No. Willing to obtain a new check.')
        self.assertEqual(gate('Do you have a police check issued in the last 8 months?', YN)['status'], 'unanswered')   # March is on the edge
        self.assertEqual(gate('Do you have a recent police check?', YN)['status'], 'unanswered')   # no window to read
        self.assertEqual(gate('Do you have a current Police Check (National Police Certificate) for employment?', YN)['answer'], 'No')


# ------------------------------------------------------------------ R7: visa limits in letters

class LettersKeepVisaPlansOut(unittest.TestCase):
    def test_visa_time_left_skills_assessment_and_visa_plans_are_issues(self):  # R7
        for sentence, needle in (('My 485 visa is valid for about another 13 months.', 'visa end date'),
                                 ('My visa has 13 months left.', 'visa end date'),
                                 ('My visa runs out late next year.', 'visa end date'),
                                 ('My Engineers Australia skills assessment is under way.', 'skills assessment'),
                                 ('My visa application is lodged.', 'visa plans'),
                                 ('I plan to apply for a 190 nomination.', 'visa plans')):
            issues = checks.letter_issues(LETTER.format(middle=sentence))
            self.assertTrue(any(needle in i for i in issues), (sentence, issues))
        self.assertEqual(checks.letter_issues(LETTER.format(middle=GOOD_MIDDLE)), [])
        self.assertEqual(checks.letter_issues(LETTER.format(middle='I designed a 190 m culvert in Civil 3D.')), [])


# ------------------------------------------------------------------ M2: a start belongs to one session

class StartsBelongToOneSession(Case):
    def test_next_by_needs_the_run_and_stores_it(self):
        self.add(entry(1))
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok')
        self.assertEqual(code, 1)
        self.assertIn('next --by needs --run', err)
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)[0], 0)
        self.assertEqual(self.stored('seek-1')['attempts'][-1]['run'], RUN)

    def test_another_session_of_the_same_runner_cannot_release_the_start(self):  # the reviewer's q2 sequence
        self.add(entry(1))
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)[0], 0)
        later = NOW + timedelta(minutes=6)
        before = self.files()
        for action, args in (('failed', ['--note', 'page did not load']), ('open', []), ('skipped', ['--reason', 'closed']),
                             ('linkout', []), ('ask', ['--question', 'Did it go?'])):
            code, _, err = self.cli('mark', 'seek-1', action, '--by', 'grok', '--run', OTHER_RUN, *args, now=later)
            self.assertEqual(code, 1, action)
            self.assertIn('another run (session)', err)
            self.assertIn('uncertain', err)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', OTHER_RUN, now=NOW + timedelta(minutes=7))[0], 3)
        code, out, _ = self.cli('mark', 'seek-1', 'uncertain', '--by', 'Grok', '--run', OTHER_RUN, '--note', 'session 1 lost', now=later)
        self.assertEqual((code, out.strip()), (0, 'seek-1: UNCERTAIN'))

    def test_the_session_that_started_it_releases_it(self):
        self.add(entry(1))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(self.cli('mark', 'seek-1', 'failed', '--by', 'grok', '--run', RUN, '--note', 'page did not load')[0], 0)

    def test_journal_start_gives_every_session_its_own_run_id(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(journal, 'RUNS', Path(d) / 'runs'), \
                mock.patch.object(journal, 'JOURNAL', Path(d) / 'journal.jsonl'):
            at = datetime(2026, 11, 14, 2, 2, 30, tzinfo=timezone.utc)
            run = journal.start(at)
            self.assertEqual(run, '20261114T020230Z')
            self.assertTrue(q.RUN_ID.fullmatch(run) and journal.RUN_ID.fullmatch(run))
            with self.assertRaises(FileExistsError):
                journal.start(at)   # a second session in the same second gets no id that is in use
            self.assertTrue(q.RUN_ID.fullmatch('20261114T0202Z'))   # ids made before the seconds were added still work


# ------------------------------------------------------------------ M3: the claim's git chain works with a dirty journal

class ClaimChainPushesWithTheJournalDirty(unittest.TestCase):
    def test_git_command_autostashes(self):
        self.assertIn('git pull --rebase --autostash && git push', q.git_command([Path('queue')], 'x'))

    @unittest.skipUnless(shutil.which('git'), 'git is not installed')
    def test_the_printed_claim_commands_push_while_journal_jsonl_has_a_new_line(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            env = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@example.invalid', 'GIT_COMMITTER_NAME': 't',
                   'GIT_COMMITTER_EMAIL': 't@example.invalid', 'GIT_CONFIG_GLOBAL': str(d / 'gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1'}
            (d / 'gitconfig').write_text('', encoding='utf-8')
            git = lambda cwd, *args: subprocess.run(['git', *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout
            git(d, 'init', '-q', '--bare', 'origin.git')
            git(d, 'clone', '-q', 'origin.git', 'a')
            a = d / 'a'
            shutil.copy(SCRIPTS.parents[1] / '.gitattributes', a / '.gitattributes')   # the repository's own merge rules
            (a / 'automation').mkdir()
            (a / 'automation' / 'journal.jsonl').write_text('{"run_id": "x"}\n', encoding='utf-8')
            qdir = a / 'automation' / 'queue'
            q.add(entry(1), qdir, FACTS, NOW, config=CONFIG, prior=[])
            git(a, 'add', '-A'); git(a, 'commit', '-qm', 'init'); git(a, 'push', '-q', 'origin', 'HEAD')
            git(d, 'clone', '-q', 'origin.git', 'b')   # another runner appends to the journal and pushes first
            with (d / 'b' / 'automation' / 'journal.jsonl').open('a', encoding='utf-8') as f:
                f.write('{"run_id": "b"}\n')
            git(d / 'b', 'commit', '-qam', 'b journal'); git(d / 'b', 'push', '-q')
            with (a / 'automation' / 'journal.jsonl').open('a', encoding='utf-8') as f:   # journal.py start in this clone
                f.write('{"run_id": "a"}\n')
            e = q.next_entry('SEEK', qdir, CONFIG, NOW, 'Grok', [], FACTS, run=RUN)
            here = os.getcwd()
            os.chdir(a / 'automation')
            try:
                lines = q.handout_notes(e, qdir, 'Grok')
            finally:
                os.chdir(here)
            chain = next(line.strip() for line in lines if line.strip().startswith('git add'))
            done = subprocess.run(chain, shell=True, cwd=a / 'automation', env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(git(d / 'origin.git', 'log', '--format=%s', '-1').strip(), 'queue: seek-1 started by Grok')   # pushed
            self.assertEqual(git(a, 'status', '--porcelain').split(), ['M', 'automation/journal.jsonl'])   # the journal line is kept
            self.assertEqual((a / 'automation' / 'journal.jsonl').read_text(encoding='utf-8').splitlines(),
                             ['{"run_id": "x"}', '{"run_id": "b"}', '{"run_id": "a"}'])


# ------------------------------------------------------------------ M4: a council under both its names

class CouncilNames(Case):
    def test_both_names_of_a_council_are_one_employer(self):
        for a, b in (('Yarra City Council', 'City of Yarra'), ('City of Moreton Bay', 'Moreton Bay City Council'),
                     ('City of Moreton Bay', 'Moreton Bay Regional Council'), ('Hobsons Bay City Council', 'City of Hobsons Bay'),
                     ('Cardinia Shire Council', 'Shire of Cardinia'), ('Wyndham City', 'Wyndham City Council')):
            self.assertTrue(q.same_employer(a, b), (a, b))
        for a, b in (('Yarra City Council', 'Yarra Ranges Council'), ('City of Melbourne', 'Melbourne Water'),
                     ('Melton City Council', 'Melton Concrete')):
            self.assertFalse(q.same_employer(a, b), (a, b))

    def test_a_repost_under_the_other_name_is_a_repeat(self):
        self.add(entry(1, route='EMPLOYER_PORTAL', seek_id='', url='https://yarracity.vic.gov.au/careers/1', id='yarra-1',
                       company='Yarra City Council', role='Civil Works Project Officer', lane='technician'))
        q.mark(self.dir, 'yarra-1', 'applied', 'Grok', NOW, 'portal_confirmation', 'PageUp confirmation screen shown', facts=FACTS)
        with self.assertRaises(q.Refused) as r:
            self.add(entry(99990001, company='City of Yarra', role='Civil Works Project Officer', lane='technician'))
        self.assertIn('already applied for this company and role (yarra-1)', str(r.exception))


# ------------------------------------------------------------------ M5: a receipt found after FAILED, SKIPPED or EXPIRED

class LateReceipts(Case):
    def test_a_receipt_after_failed_final_makes_it_applied_and_blocks_the_repost(self):
        self.add(entry(1, company='Newton Denny Chapelle', role='Civil Engineer / Design Engineer'))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(self.cli('mark', 'seek-1', 'failed', '--by', 'Grok', '--run', RUN, '--final', '--note', 'Submit gave an error page')[0], 0)
        self.assertEqual(self.stored('seek-1')['status'], 'FAILED')
        nextday = NOW + timedelta(days=1)
        code, out, _ = self.cli('mark', 'seek-1', 'applied', '--by', 'Claude', '--kind', 'seek_receipt_email', '--ref', 'SEEK receipt email',
                                '--at', q.iso(NOW + timedelta(minutes=3)), now=nextday)
        self.assertEqual((code, out.strip()), (0, 'seek-1: APPLIED'))
        e = self.stored('seek-1')
        self.assertEqual((e['receipt']['at'], e['attempts'][-1]['note']), ('2026-11-13T01:03:00Z', 'receipt found after FAILED.'))
        self.assertTrue((self.dir / 'done' / '2026-11' / 'seek-1.json').exists())
        self.assertEqual(self.cli('outcome', 'seek-1', '--kind', 'acknowledged', '--at', '2026-11-14', '--by', 'Claude', now=nextday)[0], 0)
        with self.assertRaises(q.Refused) as r:
            self.add(entry(99990002, company='Newton Denny Chapelle', role='Civil Engineer / Design Engineer'), now=nextday)
        self.assertIn('already applied', str(r.exception))

    def test_a_receipt_after_expired_makes_it_applied(self):
        self.add(entry(1, closes_at='2026-11-12'))
        self.assertEqual([x['id'] for x in q.expire(self.dir, now=NOW)], ['seek-1'])
        code, out, _ = self.cli('mark', 'seek-1', 'applied', '--by', 'Claude', '--kind', 'seek_receipt_email', '--ref', 'SEEK receipt email')
        self.assertEqual((code, out.strip()), (0, 'seek-1: APPLIED'))

    def test_an_outcome_on_a_failed_entry_says_to_record_the_receipt(self):
        self.add(entry(1))
        q.mark(self.dir, 'seek-1', 'failed', 'Grok', NOW, note='nothing went', final=True, facts=FACTS)
        code, _, err = self.cli('outcome', 'seek-1', '--kind', 'rejected', '--at', '2026-11-13', '--by', 'Claude')
        self.assertEqual(code, 1)
        self.assertIn('mark seek-1 applied with the receipt first', err)
        self.assertEqual(self.cli('mark', 'seek-1', 'skipped', '--by', 'Claude', '--reason', 'x')[0], 1)   # only applied reaches done/


# ------------------------------------------------------------------ M6: notes and checks are printed at hand-out

class HandoutPrintsNotesAndChecks(Case):
    def test_attempt_notes_and_notes_lines_are_printed(self):
        e = q.fill(email_entry(1, notes='Owner binned this enquiry on 20 Sep 2026: ask before sending.',
                               attempts=[{'at': '2026-11-12T00:00:00Z', 'by': 'Claude', 'result': 'reopened',
                                          'note': 'Before sending: re-open the careers page; if it is gone, skip.'}]))
        lines = q.handout_notes(e, self.dir)
        self.assertIn('NOTES (read before submitting; a condition here is a check too):', lines)
        self.assertTrue(any('Owner binned this enquiry' in line for line in lines))
        self.assertTrue(any('Before sending: re-open the careers page' in line for line in lines))

    def test_verify_adds_a_check_that_next_prints(self):
        self.add(entry(1))
        code, out, _ = self.cli('verify', 'seek-1', '--add', 'Read the Position Description at https://example.com.au/pd and answer its criteria',
                                '--by', 'Claude')
        self.assertEqual(code, 0, out)
        self.assertIn('git pull --rebase --autostash', out)
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(code, 0)
        self.assertIn('BEFORE SUBMITTING, CHECK:\n  - Read the Position Description at https://example.com.au/pd', err)
        before = self.files()
        code, _, err = self.cli('verify', 'seek-1', '--add', 'Ask jane.doe@gmail.com first', '--by', 'Claude')
        self.assertEqual(code, 1)
        self.assertIn('the queue is public', err)
        self.assertEqual(self.files(), before)


# ------------------------------------------------------------------ m1: Melbourne time without the tz database

class MelbourneWithoutTzData(Case):
    def test_the_rule_gives_aedt_in_summer_and_aest_in_winter(self):
        with mock.patch('zoneinfo.ZoneInfo', side_effect=Exception('no time zone data')):
            zone = q._melbourne()
            self.assertIs(zone, answers.MELBOURNE_RULE)
            self.assertIs(answers.melbourne(), answers.MELBOURNE_RULE)
            self.assertEqual(datetime(2026, 11, 16, 10, 30, tzinfo=timezone.utc).astimezone(zone).utcoffset(), timedelta(hours=11))
            self.assertEqual(datetime(2026, 7, 16, 10, 30, tzinfo=timezone.utc).astimezone(zone).utcoffset(), timedelta(hours=10))
            # the changes: 2 am AEST on the first Sunday of October (4 Oct 2026), 3 am AEDT on the first Sunday of April (5 Apr 2026)
            self.assertEqual(datetime(2026, 10, 3, 15, 59, tzinfo=timezone.utc).astimezone(zone).hour, 1)
            self.assertEqual(datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc).astimezone(zone).hour, 3)
            self.assertEqual(datetime(2026, 4, 4, 15, 59, tzinfo=timezone.utc).astimezone(zone).hour, 2)
            self.assertEqual(datetime(2026, 4, 4, 16, 0, tzinfo=timezone.utc).astimezone(zone).hour, 2)
            self.assertEqual(q.parse_time('2026-11-16T21:30').utcoffset(), timedelta(hours=11))
            self.assertTrue(letter_pdf.melbourne_today())

    def test_the_quiet_hours_hold_in_summer_without_tz_data(self):
        self.add(entry(1))
        with mock.patch('zoneinfo.ZoneInfo', side_effect=Exception('no time zone data')):
            code, _, err = self.cli('next', '--route', 'SEEK', now=datetime(2026, 11, 16, 10, 30, tzinfo=timezone.utc))   # 21:30 AEDT
        self.assertEqual(code, 3)
        self.assertIn('it is 21:30 there now', err)


# ------------------------------------------------------------------ m2, R6: times that cannot be right

class TimesMustBeReal(Case):
    def test_mark_refuses_a_future_or_impossible_at(self):
        self.add(entry(1))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        before = self.files()
        for at in ('2026-12-14T10:05', '2026-11-12T10:00'):
            code, _, err = self.cli('mark', 'seek-1', 'applied', '--by', 'Grok', '--run', RUN, '--kind', 'seek_confirmation_screen',
                                    '--ref', 'SEEK confirmation screen shown', '--at', at, now=NOW + timedelta(minutes=5))
            self.assertEqual(code, 1, at)
            self.assertRegex(err, 'later than now|earlier than the first hand-out')
        self.assertEqual(self.files(), before)
        self.assertEqual(self.cli('mark', 'seek-1', 'applied', '--by', 'Grok', '--kind', 'seek_confirmation_screen',
                                  '--ref', 'SEEK confirmation screen shown', '--at', q.iso(NOW + timedelta(minutes=4)),
                                  now=NOW + timedelta(minutes=5))[0], 0)

    def test_check_and_next_refuse_a_future_or_unreadable_receipt_time(self):
        self.add(entry(1))
        self.add(entry(2))
        q.mark(self.dir, 'seek-1', 'applied', 'Grok', NOW, 'seek_confirmation_screen', 'SEEK confirmation screen shown', facts=FACTS)
        path = next((self.dir / 'done').glob('*/seek-1.json'))
        for bad in ('2026-12-14T10:05:00Z', '14/11/2026 10:05'):
            e = q.read_json(path)
            e['receipt']['at'] = bad
            q.write_json(path, e)
            code, out, _ = self.cli('check')
            self.assertEqual(code, 1, bad)
            self.assertRegex(out, 'later than now|is not a time')
            self.assertEqual(self.cli('next', '--route', 'SEEK')[0], 1, bad)


# ------------------------------------------------------------------ R1, R2: what a runner types is public

class TypedTextStaysOutOfThePublicQueue(Case):
    def test_mark_notes_with_contact_details_or_reference_numbers_are_refused(self):
        self.add(entry(1))
        self.add(email_entry(2))
        before = self.files()
        for action, flag, text in (('failed', '--note', 'Portal error at https://careers.example.com/apply?candidateId=4471923&token=abc'),
                                   ('failed', '--note', 'recruiter jane.doe@gmail.com said to wait'),
                                   ('uncertain', '--note', 'SEEK showed: Application submitted, reference 99123456'),
                                   ('uncertain', '--note', 'application ref APP-4471-923 shown'),
                                   ('skipped', '--reason', 'Login shows candidate number 1234567 already exists'),
                                   ('ask', '--question', 'Sarah Lee (sarah.lee@centralvic.com.au) replied: interview Tue. Reply?')):
            code, _, err = self.cli('mark', 'seek-1', action, '--by', 'Grok', flag, text)
            self.assertEqual(code, 1, text)
            self.assertIn('the queue is public', err)
        for args in (('--question', 'Please confirm your email address macdarenz.private@outlook.com'),
                     ('--question', 'Confirm your details', '--option', 'https://tracking.example.com/r?uid=55443322')):
            code, _, err = self.cli('answer', 'seek-1', *args)
            self.assertEqual(code, 1, args)
            self.assertIn('the queue is public', err)
        self.assertEqual(self.files(), before)
        # the entry's own address and his own details may be named
        self.assertEqual(self.cli('mark', 'email-2', 'uncertain', '--by', 'Claude', '--note', 'Gmail shows a draft to jobs@example2.com.au')[0], 0)
        self.assertEqual(self.cli('mark', 'email-2', 'open', '--by', 'Claude', '--note', 'checked: Gmail Sent to:jobs@example2.com.au, nothing')[0], 0)
        q.save(self.dir, q.fill(entry(3)))
        self.assertEqual(self.cli('mark', 'seek-3', 'linkout', '--by', 'Grok', '--note', 'the apply button opens https://careers.example3.com.au/jobs/1')[0], 0)

    def test_receipt_refs_with_a_reference_number_in_any_form_are_refused(self):
        for ref in ('Application reference 44719', 'Your reference number is APP-4471-923', 'Candidate no. 12 345 678',
                    'Ref: JR-2026-11-1234', 'Thank you Marc, your application JR-2026-11-1234 (candidate C-4471-923) was received'):
            self.assertTrue(q.ref_problems('portal_confirmation', ref), ref)
        for ref in ('SEEK receipt email of 6 Oct 2026', 'portal confirmation page shown', 'gmail:18f3a', 'SEEK confirmation screen shown',
                    'SEEK receipt email 14 Nov 2026 10:05'):
            self.assertEqual(q.ref_problems('seek_receipt_email', ref), [], ref)


# ------------------------------------------------------------------ R3, R4, R5: owner questions and outcomes stick

class OwnerQuestionsAndOutcomesStick(Case):
    def test_an_entry_with_an_outcome_is_never_reopened(self):  # R3
        self.add(entry(1))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(self.cli('mark', 'seek-1', 'uncertain', '--by', 'Grok', '--note', 'browser closed after the submit click')[0], 0)
        self.assertEqual(self.cli('outcome', 'seek-1', '--kind', 'rejected', '--at', '2026-11-13', '--by', 'Claude')[0], 0)
        code, _, err = self.cli('mark', 'seek-1', 'open', '--by', 'Grok', '--note', 'checked: not in the SEEK applied jobs list')
        self.assertEqual(code, 1)
        self.assertIn('the employer outcome rejected on 2026-11-13 is recorded, so it went', err)
        e = self.stored('seek-1')
        e['status'] = 'OPEN'   # a hand edit or a merge
        q.write_json(self.dir / 'open' / 'seek-1.json', e)
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('outcomes: only an APPLIED or UNCERTAIN entry has employer outcomes', out)
        self.assertEqual(self.cli('next', '--route', 'SEEK', now=NOW + timedelta(days=1))[0], 1)

    def test_an_ask_that_says_more_than_the_form_question_stays_with_the_owner(self):  # R4
        question = 'Do you have Traffic Control experience?'
        self.add(entry(1, questions=[question]))
        self.assertEqual(self.stored('seek-1')['status'], 'ASK_OWNER')   # no standing answer yet
        ask = (question + ' Also: the advert now requires a degree accredited by Engineers Australia; is yours? Do not submit '
               'until you say.')
        self.assertEqual(self.cli('mark', 'seek-1', 'ask', '--by', 'Claude', '--question', ask)[0], 0)
        later = copy.deepcopy(FACTS)
        later['answers']['experience_yes_no']['traffic control'] = 'No'   # the owner answers the form question only
        q.write_json(self.facts, later)
        self.assertEqual(self.cli('answer', 'seek-1')[0], 0)
        self.assertEqual(self.stored('seek-1')['questions'][0]['answer'], 'No')
        e = self.stored('seek-1')
        self.assertEqual(e['status'], 'ASK_OWNER')
        self.assertIn('accredited by Engineers Australia', e['ask_owner'])

    def test_an_owner_question_is_reopened_only_with_his_answer(self):  # R5
        self.add(entry(1))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        why = 'The advert needs a current NSW driver licence and his is Victorian: apply anyway?'
        self.assertEqual(self.cli('mark', 'seek-1', 'ask', '--by', 'Grok', '--run', RUN, '--question', why)[0], 0)
        for by in ('Grok', 'Codex'):
            code, _, err = self.cli('mark', 'seek-1', 'open', '--by', by, '--run', RUN, now=NOW + timedelta(minutes=6))
            self.assertEqual(code, 1, by)
            self.assertIn('waits on the owner', err)
        code, _, _ = self.cli('mark', 'seek-1', 'open', '--by', 'Grok', '--note', 'owner: apply anyway, 14 Nov', now=NOW + timedelta(minutes=6))
        self.assertEqual(code, 0)
        e = self.stored('seek-1')
        self.assertEqual((e['status'], e['attempts'][-1]['note']), ('OPEN', f'owner: apply anyway, 14 Nov (question was: {why})'))


if __name__ == '__main__':
    unittest.main()
