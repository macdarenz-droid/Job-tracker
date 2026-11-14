"""The re-check of 14 Nov 2026 (literal run L-B1 to L-B3, L-M1, L-M3, L-m2, L-m8; safety S-B1 to S-B3, S-M1, S-m1; privacy
R1, R2, R4 to R6). Each test failed on commit c671456 and passes after the fix. Offline: temp folders only; the
repository's own facts.json and test files are read as data."""
import contextlib
import copy
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
TESTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('apply_queue_recheck', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)
sys.path.insert(0, str(SCRIPTS))
import answers  # noqa: E402
import checks  # noqa: E402
import letter_pdf  # noqa: E402
import pymupdf  # noqa: E402

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
STANDARDS = 'Have you worked in a role which requires a sound understanding of Australian design standards?'
LETTER = ('Hello,\n\n'
          'I am applying for the Junior Civil Drafter role. Your advert asks for subdivision drawings in Civil 3D.\n\n'
          'In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks '
          'and stormwater drainage in AutoCAD and Civil 3D to Australian Standards.\n\n'
          'Full working rights in Australia (Subclass 485 visa), no sponsorship needed. Could we talk this week?\n\n'
          'Marc Masarate')
RELOCATE = 'I will relocate to Port Adelaide for this role and can start two weeks after an offer.'


def gate(question, options=None, facts=FACTS, pay=None):
    return answers.answer(question, options or [], facts, pay=pay, today=TODAY)


def opts(options):
    return [x for o in options for x in ('--option', o)]


def entry(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


def flat(text):
    return ' '.join(str(text).split())


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

    def add(self, e, now=NOW, facts=FACTS):
        return q.add(e, self.dir, facts, now, config=CONFIG, prior=[])

    def stored(self, entry_id):
        return q.find(self.dir, entry_id)[1]

    def files(self):
        return {str(p.relative_to(self.dir)): p.read_bytes() for p in sorted(self.dir.rglob('*.json'))}

    def file(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return str(path)

    def cli(self, *args, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--prior', str(self.prior),
                           '--now', q.iso(now), *args])
        return code, out.getvalue(), err.getvalue()

    def claim(self, n=1, by='Grok', run=RUN, now=NOW):
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', by, '--run', run, now=now)
        self.assertEqual(code, 0, err)
        return json.loads(out), err


# ------------------------------------------------------------------ L-B1: a new session never types an earlier run id

class ANewSessionNeverTypesAnEarlierRunId(Case):
    def test_mark_refusals_say_mark_it_uncertain_or_applied_and_never_type_the_run_id(self):
        self.add(entry(1))
        self.claim()
        later = NOW + timedelta(minutes=6)
        before = self.files()
        code, _, err = self.cli('mark', 'seek-1', 'failed', '--by', 'Grok', '--note', 'session crashed', '--run', OTHER_RUN, now=later)
        self.assertEqual(code, 1)
        self.assertIn('seek-1 was started by Grok in another run (session) at 2026-11-13T01:00:00Z and not marked: a new session cannot '
                      "know whether it went. Mark it uncertain, or applied with the receipt. Never type an earlier session's run id.", err)
        for gone in ('give --run', 'session that ran next', RUN, '--run RUN_ID'):
            self.assertNotIn(gone, err)
        code, _, err = self.cli('mark', 'seek-1', 'skipped', '--by', 'Claude', '--reason', 'advert closed', '--run', OTHER_RUN, now=later)
        self.assertEqual(code, 1)
        self.assertIn('seek-1 was started by Grok at 2026-11-13T01:00:00Z and not marked: another runner cannot know whether it went. '
                      "Mark it uncertain, or applied with the receipt. Never type another runner's name or run id.", err)
        self.assertEqual(self.files(), before)

    def test_the_answer_refusal_does_not_name_the_earlier_run_either(self):
        self.add(entry(1))
        self.claim()
        before = self.files()
        code, out, err = self.cli('answer', 'seek-1', '--question', 'Do you have Traffic Control experience?', *opts(YN),
                                  '--by', 'Grok', '--run', OTHER_RUN, now=NOW + timedelta(minutes=6))
        self.assertEqual((code, out), (1, ''))   # round 2 F8: refused outright, answered or not
        self.assertIn('Do not fill or submit its form (answer refused; nothing changed).', err)
        self.assertIn("Never type an earlier session's run id.", err)
        for gone in ('--run RUN_ID', 'mark seek-1 ask', RUN):
            self.assertNotIn(gone, err)
        self.assertEqual(self.files(), before)


# ------------------------------------------------------------------ L-B2: an owner question is never handed out as OPEN

class AnOwnerQuestionIsNeverOpen(Case):
    ASK = 'The advert asks for demonstrated drafting experience: apply anyway?'

    def test_add_sets_ask_owner_when_the_draft_has_no_status(self):
        e = self.add(entry(1, ask_owner=self.ASK))
        self.assertEqual((e['status'], e['ask_owner']), ('ASK_OWNER', self.ASK))
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(code, 4)
        self.assertIn('status ASK_OWNER', err)
        with self.assertRaises(q.Refused) as r:   # an explicit OPEN with an owner question is refused
            self.add(entry(2, status='OPEN', ask_owner=self.ASK))
        self.assertIn('ask_owner: an OPEN entry carries an owner question: set status ASK_OWNER, or clear ask_owner', str(r.exception))
        code, out, _ = self.cli('mark', 'seek-1', 'open', '--by', 'Claude', '--note', 'owner: apply anyway, 14 Nov 2026')
        self.assertEqual((code, out.strip()), (0, 'seek-1: OPEN'))
        self.assertEqual(self.stored('seek-1')['ask_owner'], '')

    def test_check_and_next_refuse_an_open_entry_with_an_owner_question(self):
        q.save(self.dir, q.fill(entry(3, status='OPEN', ask_owner=self.ASK)))   # a hand edit or a merge
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('seek-3: ask_owner: an OPEN entry carries an owner question: set status ASK_OWNER, or clear ask_owner', out)
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)[0], 1)


# ------------------------------------------------------------------ L-B3: answer --from-file, no shell quoting

class AnswerFromFile(Case):
    def test_without_an_entry_it_prints_what_the_typed_options_print(self):
        typed = self.cli('answer', '--question', SALARY, *opts(BANDS), '--advert-pay', '$120,000 per year')
        path = self.file('salary.json', {'question': SALARY, 'options': BANDS, 'advert_pay': '$120,000 per year'})
        got = self.cli('answer', '--from-file', path)
        self.assertEqual(got, typed)
        self.assertEqual((got[0], got[1]), (0, '$90k+\n'))
        path = self.file('licence.json', {'question': "Do you have a current Australian driver's licence?"})
        self.assertEqual(self.cli('answer', '--from-file', path)[:2], (0, 'Yes\n'))

    def test_on_an_entry_it_stores_what_the_typed_options_store(self):
        self.add(entry(1))
        self.add(entry(2))
        typed = self.cli('answer', 'seek-1', '--question', SALARY, *opts(SAL), '--advert-pay', '$80,000 to $115,000 plus super')
        path = self.file('salary.json', {'question': SALARY, 'options': SAL, 'advert_pay': '$80,000 to $115,000 plus super'})
        got = self.cli('answer', 'seek-2', '--from-file', path)
        self.assertEqual(got, typed)
        self.assertEqual(got[1], '$80k\n')
        one, two = self.stored('seek-1'), self.stored('seek-2')
        self.assertEqual((two['advert_pay'], two['questions']), (one['advert_pay'], one['questions']))
        self.assertEqual(two['advert_pay'], '$80,000 to $115,000 plus super')
        # only the pay: the same as answer ID --advert-pay
        self.add(entry(3, questions=[{'question': SALARY, 'options': SAL}], advert_pay='not stated'))
        path = self.file('pay.json', {'advert_pay': '$100,000 per year'})
        code, out, _ = self.cli('answer', 'seek-3', '--from-file', path)
        self.assertEqual((code, json.loads(out)['questions'][0]['answer']), (0, '$100k'))
        self.assertEqual(self.stored('seek-3')['advert_pay'], '$100,000 per year')

    def test_mixed_with_typed_text_is_a_usage_error_and_a_bad_file_is_refused(self):
        self.add(entry(1))
        path = self.file('q.json', {'question': SALARY, 'options': SAL})
        before = self.files()
        for extra in (['--question', SALARY], ['--option', '$70k'], ['--advert-pay', 'not stated']):
            code, out, err = self.cli('answer', 'seek-1', '--from-file', path, *extra)
            self.assertEqual((code, out), (2, ''), extra)
            self.assertIn('--from-file', err)
        for bad in (['a list'], {'question': SALARY, 'option': ['$70k']}, {'question': SALARY, 'options': '$70k'},
                    {'question': 7}, {'question': SALARY, 'advert_pay': 120000}, {'options': SAL}):
            code, out, err = self.cli('answer', 'seek-1', '--from-file', self.file('bad.json', bad))
            self.assertEqual((code, out), (1, ''), bad)
            self.assertIn('--from-file', err)
        code, _, err = self.cli('answer', 'seek-1', '--from-file', str(self.root / 'missing.json'))
        self.assertEqual(code, 1)
        self.assertEqual(self.files(), before)


# ------------------------------------------------------------------ L-M1: the owner's answers are read from facts.json

def with_owner_answers(rows):
    facts = copy.deepcopy(FACTS)
    facts['answers']['owner_answers'] = rows
    return facts


ROW = {'question': STANDARDS, 'options': ['Yes', 'No'], 'answer': 'Yes', 'date': '2026-11-14'}


class OwnerAnswers(Case):
    def test_the_gate_gives_the_owners_answer_before_any_other_rule(self):
        facts = with_owner_answers([ROW, {'question': 'Have you ever been dismissed from a job?', 'answer': 'No', 'date': '2026-11-14'},
                                    {'question': 'Why do you want this role?', 'answer': 'Civil drafting is the work my diploma trained me for.',
                                     'date': '2026-11-14', 'entry': 'seek-1'}])   # round 2 F5: a question about one job needs its entry
        self.assertEqual(gate(STANDARDS, YN)['status'], 'unanswered')   # without the row
        for question in (STANDARDS, '  have you worked in a role which requires a sound understanding of australian design standards',
                         STANDARDS.replace('Australian', '“Australian”')):
            r = gate(question, YN, facts)
            self.assertEqual((r['status'], r['answer'], r['basis']), ('answered', 'Yes', 'answers.owner_answers'), question)
        self.assertEqual(gate(STANDARDS, ['YES', 'NO'], facts)['answer'], 'YES')   # word for word one of the options on screen
        self.assertEqual(gate(STANDARDS, [], facts)['answer'], 'Yes')   # free text
        for options in (['Yes, more than 2 years', 'No'], ['Agree', 'Disagree']):   # the stored answer is not on screen
            self.assertEqual(gate(STANDARDS, options, facts)['status'], 'unanswered', options)
        self.assertEqual(gate('Have you ever been dismissed from a job?', YN, facts)['answer'], 'No')   # before the traps
        self.assertEqual(answers.answer('Why do you want this role?', [], facts, entry='seek-1')['answer'],
                         'Civil drafting is the work my diploma trained me for.')
        self.assertEqual(gate('Why do you want this role?', [], facts)['status'], 'unanswered')   # not at screening, not elsewhere
        self.assertEqual(gate(STANDARDS + ' Please explain.', YN, facts)['status'], 'unanswered')   # another question

    def test_answer_id_reopens_an_entry_once_the_owner_has_answered(self):
        self.add(entry(1, questions=[{'question': STANDARDS, 'options': YN}]))
        self.assertEqual(self.stored('seek-1')['status'], 'ASK_OWNER')
        q.write_json(self.facts, with_owner_answers([ROW]))
        code, out, err = self.cli('answer', 'seek-1')
        self.assertEqual(code, 0, err)
        e = self.stored('seek-1')
        self.assertEqual((e['status'], e['ask_owner']), ('OPEN', ''))
        self.assertEqual((e['questions'][0]['answer'], e['questions'][0]['basis']), ('Yes', 'answers.owner_answers'))
        self.assertEqual(self.cli('next', '--route', 'SEEK')[0], 0)

    def test_a_malformed_or_private_owner_answer_stops_check_next_and_answer(self):
        self.add(entry(1))
        for rows, needle in (({'question': STANDARDS}, 'owner_answers: a list'),
                             ([{'question': STANDARDS, 'answer': 'Yes'}], 'date'),
                             ([{**ROW, 'date': '14 Nov 2026'}], 'date'),
                             ([{**ROW, 'date': '2026-02-30'}], 'date'),
                             ([{**ROW, 'answer': ''}], 'answer'),
                             ([{**ROW, 'answer': 'Maybe'}], 'is not one of its options'),
                             ([{**ROW, 'note': 'x'}], 'note'),
                             ([ROW, {**ROW, 'answer': 'No'}], 'twice'),
                             ([{**ROW, 'question': STANDARDS + ' Email jane.doe@example.com'}], 'an email address'),
                             ([{'question': 'Referee?', 'answer': 'Sarah Lee, 0412 345 678', 'date': '2026-11-14'}], 'a phone number'),
                             ([{'question': 'Notes?', 'answer': 'He said "yes"', 'date': '2026-11-14'}], 'quoted text')):
            q.write_json(self.facts, with_owner_answers(rows))
            code, out, _ = self.cli('check')
            self.assertEqual(code, 1, rows)
            self.assertIn('facts.json: answers -> owner_answers', out)
            self.assertIn(needle, out, rows)
            self.assertEqual(self.cli('next', '--route', 'SEEK')[0], 1, rows)
            code, _, err = self.cli('answer', 'seek-1', '--question', STANDARDS, *opts(YN))
            self.assertEqual(code, 1, rows)
            self.assertIn('owner_answers', err)
        q.write_json(self.facts, with_owner_answers([ROW]))
        self.assertEqual(self.cli('check')[0], 0)
        self.assertIn('owner_answers', answers.KEYS)


# ------------------------------------------------------------------ L-M3: no advert pay is the runner's to settle, not the owner's

class SalaryWithoutAdvertPay(Case):
    MESSAGE = ("UNANSWERED: the advert's pay is not recorded: run the same answer again with the advert's own pay text (or not stated) "
               'as "advert_pay" in the --from-file JSON, written with <<\'EOF\' (quoted, so the shell keeps every $)')   # round 2 F3

    def test_it_exits_5_keeps_the_start_and_stores_nothing(self):
        self.add(entry(1))
        self.claim()
        before = self.files()
        code, out, err = self.cli('answer', 'seek-1', '--question', SALARY, *opts(SAL), '--by', 'Grok', '--run', RUN)
        self.assertEqual((code, out, err.strip()), (5, '', self.MESSAGE))
        self.assertEqual(self.files(), before)
        e = self.stored('seek-1')
        self.assertEqual((e['status'], e['attempts'][-1]['result']), ('OPEN', 'started'))
        code, out, _ = self.cli('answer', 'seek-1', '--question', SALARY, *opts(SAL), '--advert-pay', 'not stated', '--by', 'Grok', '--run', RUN)
        self.assertEqual((code, out), (0, '$70k\n'))
        e = self.stored('seek-1')
        self.assertEqual((e['status'], e['attempts'][-1]['result'], e['advert_pay']), ('OPEN', 'started', 'not stated'))

    def test_the_same_message_without_an_entry(self):
        code, out, err = self.cli('answer', '--question', SALARY, *opts(SAL))
        self.assertEqual((code, out, err.strip()), (5, '', self.MESSAGE))


# ------------------------------------------------------------------ S-B1: a compound option is never ticked

class CompoundOptionsAreNotChosen(unittest.TestCase):
    def test_an_option_that_says_more_than_yes_or_no_is_not_chosen(self):
        for question, options in (
                ('Do you require sponsorship to work in Australia?', ['No, I am an Australian citizen', 'Yes']),
                ('Do you have experience using AutoCAD?', ['Yes - 5+ years', 'No']),
                ('Are you willing to relocate for this role?', ['Yes, at my own expense', 'No']),
                ('Do you agree with the privacy policy?', ['Yes, and I agree to receive marketing emails', 'No']),
                ('Have you completed a qualification in engineering?', ['Yes - a Bachelor of Engineering accredited by Engineers Australia', 'No']),
                ('Do you have a current Police Check?', ['Yes - issued within the last 3 months', 'No']),
                ("Do you have a current Australian driver's licence?", ['Yes - full licence with own car and trailer licence', 'No']),
                ("Do you have a current Australian driver's licence?", ['Yes, and I hold a forklift licence', 'No']),
                ('Do you hold a current White Card?', ['Yes, and I hold a forklift licence', 'No']),
                ('Are you currently studying?', ['No - but willing to study part time', 'Yes']),
                ('Are you willing to undergo a pre-employment medical?', ['Yes, at my own cost', 'No']),
                ('Do you own or have regular access to a car?', ['Yes, a company car', 'No']),
                ('I declare that the information I have provided is true and correct.', ['I agree and consent to a credit check', 'I do not agree'])):
            r = gate(question, options)
            self.assertEqual((r['status'], r['answer']), ('unanswered', ''), (question, options, r))

    def test_a_plain_yes_or_no_with_punctuation_is_still_chosen(self):
        for question, options, answer in (
                ('Do you have experience using AutoCAD?', ['Yes.', 'No.'], 'Yes.'),
                ('Are you willing to relocate for this role?', ['YES', 'NO'], 'YES'),
                ('Do you require sponsorship to work in Australia?', ['Yes', 'No!'], 'No!'),
                ('Do you hold a current White Card?', ['Yes', 'No'], 'Yes'),
                ('Do you agree with the privacy policy?', ['I agree', 'I do not agree'], 'I agree'),
                ("Do you have a current Australian driver's licence?", ['Full licence', 'Provisional licence', 'No licence'], 'Full licence'),
                ("Do you have a current Australian driver's licence?", ['Yes', 'No'], 'Yes')):
            r = gate(question, options)
            self.assertEqual((r['status'], r['answer']), ('answered', answer), (question, options, r))


# ------------------------------------------------------------------ S-B2: a re-post with a place or a qualifier is the same role

class SameRoleBySubset(Case):
    def test_one_title_inside_the_other_is_the_same_role(self):
        for a, b in (('Civil Engineer', 'Civil Engineer - Wollongong'), ('Civil Engineer', 'Civil Engineer | Wollongong NSW'),
                     ('Site Engineer - Urban Development - EOI 2027', 'Site Engineer - Urban Development'),
                     ('Civil Engineer / Design Engineer', 'Civil Engineer'), ('Civil Engineer | Roads', 'Civil Engineer'),
                     ('Site Engineer', 'Civil Site Engineer'), ('Junior Civil Drafter', 'Civil Drafter - Melbourne')):
            self.assertTrue(q.same_role(a, b) and q.same_role(b, a), (a, b))
        for a, b in (('Civil Drafter', 'Civil Designer'), ('Civil Engineer', 'Laboratory Technician'), ('', ''), ('Civil Engineer', '')):
            self.assertFalse(q.same_role(a, b) or q.same_role(b, a), (a, b))

    def test_a_repost_with_a_place_after_an_application_is_refused(self):
        self.add(entry(1, company='Allen Price Pty Ltd', role='Civil Engineer'))
        q.mark(self.dir, 'seek-1', 'applied', 'Claude', NOW, kind='seek_confirmation_screen', ref='SEEK confirmation screen shown', facts=FACTS)
        with self.assertRaises(q.Refused) as r:
            self.add(entry(2, company='Allen Price', role='Civil Engineer - Wollongong'))
        self.assertIn('already applied for this company and role (seek-1)', str(r.exception))


# ------------------------------------------------------------------ S-B3: "already applied, found" blocks a repeat and is not a submission

class AlreadyApplied(Case):
    def mark_found(self, entry_id='seek-1', by='Claude', at='2026-10-02', now=NOW + timedelta(minutes=1), ref='SEEK shows applied on 2 Oct 2026'):
        return self.cli('mark', entry_id, 'applied', '--by', by, '--kind', 'already_applied', '--ref', ref, *(['--at', at] if at else []), now=now)

    def test_it_is_applied_blocks_the_role_and_is_allowed_from_any_runner_on_a_started_entry(self):
        self.add(entry(1))
        self.claim()
        code, out, err = self.mark_found()
        self.assertEqual((code, out.strip()), (0, 'seek-1: APPLIED'), err)
        e = self.stored('seek-1')
        self.assertEqual((e['receipt']['kind'], e['receipt']['ref'], e['receipt']['by']), ('already_applied', 'SEEK shows applied on 2 Oct 2026', 'Claude'))
        self.assertEqual(q.melbourne_date(e['receipt']['at']), '2026-10-02')
        with self.assertRaises(q.Refused) as r:   # the same employer and role is blocked for ever, as after any application
            self.add(entry(3, company='Acme 1 Pty Ltd', role='Civil Drafter'))
        self.assertIn('already applied for this company and role (seek-1)', str(r.exception))
        self.assertEqual(self.cli('check')[0], 0)

    def test_it_is_not_counted_toward_the_caps_the_spacing_or_report(self):
        self.add(entry(1))
        self.add(entry(2, listed_at='2026-11-09'))
        self.claim()
        code, _, err = self.mark_found(at=None)   # round 2 F4: on an entry next handed out, the date the site gives is needed
        self.assertEqual(code, 1)
        self.assertIn('give --at with the date the site shows he applied', err)
        self.assertEqual(self.mark_found(at='2026-10-02')[0], 0)   # before the hand-out: an application made earlier
        got, _ = self.claim(now=NOW + timedelta(minutes=2))   # no 20-minute wait: nothing was submitted
        self.assertEqual(got['id'], 'seek-2')
        r = q.report(self.dir, NOW + timedelta(minutes=3), 7)
        self.assertEqual((r['applied'], r['already_applied_found']), (0, 1))
        code, out, _ = self.cli('report', now=NOW + timedelta(minutes=3))
        self.assertIn('applications with a receipt, 2026-11-07 to 2026-11-13 (7 days, Melbourne dates): 0', out.splitlines())
        self.assertIn('already applied, found (not counted above): 1', out.splitlines())
        s = q.stats(self.dir, NOW + timedelta(minutes=3))
        self.assertEqual((s['applied_total'], s['applied_last_7_days'], s['already_applied_total']), (0, 0, 1))
        one = copy.deepcopy(CONFIG)
        one['limits']['seek_submissions_per_day'] = 1
        q.write_json(self.config, one)
        self.add(entry(4))
        self.assertEqual(self.mark_found('seek-4', now=NOW + timedelta(minutes=4))[0], 0)
        self.assertEqual(self.cli('mark', 'seek-2', 'open', '--by', 'Grok', '--run', RUN, now=NOW + timedelta(minutes=5))[0], 0)
        self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN, now=NOW + timedelta(minutes=30))[0], 0)

    def test_on_ask_owner_and_uncertain_but_not_on_finished_entries(self):
        self.add(entry(1, questions=['Do you have Traffic Control experience?']))
        self.assertEqual(self.stored('seek-1')['status'], 'ASK_OWNER')
        self.assertEqual(self.mark_found()[0], 0)
        self.add(entry(2))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(self.cli('mark', 'seek-2', 'uncertain', '--by', 'Grok', '--note', 'browser closed')[0], 0)
        self.assertEqual(self.mark_found('seek-2')[0], 0)
        self.add(entry(5))
        self.assertEqual(self.cli('mark', 'seek-5', 'skipped', '--by', 'Grok', '--reason', 'advert closed')[0], 0)
        code, _, err = self.mark_found('seek-5')
        self.assertEqual(code, 1)
        self.assertIn('already SKIPPED', err)
        self.add(entry(6))
        for ref, at in (('Your reference: KX92QZ', None), ('SEEK shows applied', '2026-11-20')):
            self.assertEqual(self.mark_found('seek-6', ref=ref, at=at)[0], 1, ref)


# ------------------------------------------------------------------ S-M1, S-m1: one letter text everywhere

class OneLetterTextEverywhere(Case):
    def pasted(self, err):
        lines = err.splitlines()
        start = lines.index('COVER LETTER TO PASTE (exactly, between the lines):')
        self.assertTrue(re.fullmatch(r'-{20,}', lines[start + 1]), lines[start + 1])
        end = lines.index(lines[start + 1], start + 2)
        return start, '\n'.join(lines[start + 2:end])

    def test_next_prints_the_composed_letter_after_the_questions(self):
        self.add(entry(1, cover_letter_text=LETTER, relocation_line=RELOCATE, questions=["Do you have a current Australian driver's licence?"]))
        _, err = self.claim()
        start, text = self.pasted(err)
        self.assertEqual(text, checks.compose_letter(LETTER, RELOCATE))
        self.assertIn(RELOCATE, text)
        lines = err.splitlines()
        self.assertLess(max(i for i, line in enumerate(lines) if line.startswith('Q: ')), start)
        self.assertLess(start, next(i for i, line in enumerate(lines) if line.startswith('RESUME: ')))

    def test_the_pdf_body_is_the_pasted_text_with_no_added_line(self):
        self.add(entry(1, cover_letter_text=LETTER, relocation_line=RELOCATE))
        _, err = self.claim()
        _, text = self.pasted(err)
        out = self.root / 'letter.pdf'
        letter_pdf.build(letter_pdf.find_entry('seek-1', self.dir), out, FACTS, '14 November 2026')
        with pymupdf.open(out) as doc:
            pdf = '\n'.join(page.get_text() for page in doc)
        body = pdf[pdf.index('14 November 2026\nAcme 1\n') + len('14 November 2026\nAcme 1\n'):]
        self.assertEqual(flat(body), flat(text))
        self.assertNotIn('Kind regards', pdf)

    def test_a_letter_without_his_name_gets_only_the_name_line(self):
        unsigned = LETTER.rsplit('\n\n', 1)[0]
        lines = letter_pdf.letter_lines({'resume_variant': 'drafter', 'company': 'Acme', 'cover_letter_text': unsigned}, FACTS, '14 November 2026')
        texts = [text for _, text, _ in lines]
        self.assertEqual(texts[-1], 'Marc Masarate')
        self.assertNotIn('Kind regards,', texts)


# ------------------------------------------------------------------ L-m8: the plain work-rights yes/no questions

class WorkRightsYesNo(unittest.TestCase):
    def test_right_to_work_and_full_working_rights_are_yes(self):
        for question in ('Do you have the right to work in Australia?', 'Do you have the legal right to work in Australia?',
                         'Do you currently have the right to work in Australia?', 'Do you have full working rights in Australia?',
                         'Do you have working rights in Australia?', 'Do you hold the right to work in Australia?'):
            r = gate(question, YN)
            self.assertEqual((r['status'], r['answer']), ('answered', 'Yes'), question)

    def test_citizen_or_permanent_resident_is_no(self):
        for question in ('Are you an Australian citizen or permanent resident?', 'Are you an Australian Citizen or PR?',
                         'Are you an Australian permanent resident or citizen?', 'Are you a permanent resident or citizen of Australia?',
                         'Are you an Australian citizen or a permanent resident of Australia?'):
            r = gate(question, YN)
            self.assertEqual((r['status'], r['answer']), ('answered', 'No'), question)

    def test_the_rest_stays_with_the_owner(self):
        for question in ('Do you have unrestricted working rights in Australia?', 'Are you a citizen or permanent resident?',
                         'Do you have the right to work in Australia without restriction?', 'Are you an Australian citizen?',
                         'Do you have full working rights in Australia for the next 5 years?',
                         'Are you legally entitled to work in Australia?'):   # left with the owner by the earlier review
            self.assertEqual(gate(question, YN)['status'], 'unanswered', question)
        r = gate('Do you have the right to work in Australia?')   # no options: the free text, as before
        self.assertEqual(r['answer'], FACTS['answers']['right_to_work']['free_text'])


# ------------------------------------------------------------------ R1, R2: no workplace and no police-check dates in public code

class NoPrivateDetailsInCodeOrTests(unittest.TestCase):
    def test_his_workplace_and_police_check_dates_are_not_in_scripts_or_tests(self):
        words = ('rock' + 'bank', 'ram' + 'page', '19 ' + 'march', '23 ' + 'march', 'for his ' + 'visa')
        for path in [SCRIPTS / 'checks.py'] + sorted(TESTS.glob('*.py')):
            text = path.read_text(encoding='utf-8').lower()
            for word in words:
                self.assertNotIn(word, text, path.name)

    def test_the_console_job_check_still_works_without_them(self):
        self.assertTrue(checks.console_job_as_civil('My current role as a console operator at bp in Melbourne has given me construction experience.'))
        self.assertFalse(checks.console_job_as_civil('I work casually at a service station in Melbourne while looking for my first civil drafting role.'))


# ------------------------------------------------------------------ R4: a code mixing letters and digits is not a public ref

class RefCodes(unittest.TestCase):
    def test_mixed_letter_and_digit_codes_are_refused(self):
        for ref in ('Your reference: KX92QZ', 'confirmation code 7Q4T-AB', 'AB12C3 shown', 'portal said JR2026x'):
            self.assertTrue(q.ref_problems('portal_confirmation', ref), ref)
            self.assertTrue(q.ref_problems('already_applied', ref), ref)
        self.assertIn('a code mixing letters and digits', q.ref_problems('seek_confirmation_screen', 'KX92QZ')[0])

    def test_dates_and_plain_words_pass(self):
        for ref in ('SEEK confirmation screen shown', 'employer confirmation page shown', 'SEEK receipt email 14 Nov 2026 10:05',
                    'SEEK receipt email of 2026-11-14', 'SEEK shows applied on 2 Oct 2026', 'portal confirmation 1st Nov 2026, 9am'):
            self.assertEqual(q.ref_problems('seek_receipt_email', ref), [], ref)


# ------------------------------------------------------------------ R5: quotation marks are refused in public notes

class QuotesInNotes(Case):
    def test_outcome_and_mark_notes_with_quotation_marks_are_refused(self):
        self.add(entry(1))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        self.assertEqual(self.cli('mark', 'seek-1', 'uncertain', '--by', 'Grok', '--note', 'browser closed')[0], 0)
        before = self.files()
        for note in ('HR wrote "we were impressed"', 'HR wrote “we were impressed”'):
            code, _, err = self.cli('outcome', 'seek-1', '--kind', 'interview', '--at', '2026-11-13', '--by', 'Claude', '--note', note)
            self.assertEqual(code, 1, note)
            self.assertIn('quoted text', err)
        self.add(entry(2))
        for flag, action in (('--reason', 'skipped'), ('--note', 'failed'), ('--question', 'ask')):
            code, _, err = self.cli('mark', 'seek-2', action, '--by', 'Grok', flag, 'the form said “position filled”')
            self.assertEqual(code, 1, action)
            self.assertIn('quoted text', err)
        self.assertEqual({k: v for k, v in self.files().items() if 'seek-1' in k}, before)
        self.assertEqual(self.cli('outcome', 'seek-1', '--kind', 'rejected', '--at', '2026-11-13', '--by', 'Claude', '--note',
                                  'rejection email, no reason given')[0], 0)
        self.assertEqual(q.note_problems("the employer's own words were kind"), [])

    def test_the_help_no_longer_says_quotes_cannot_be_detected(self):
        self.assertNotIn('cannot detect a name or quoted text', q.NOTE_RULE)
        self.assertNotIn('no quotes (queue.py cannot detect them', q.__doc__)


# ------------------------------------------------------------------ R6: residency and migration talk in letters and emails

class ResidencyTalk(unittest.TestCase):
    BASE = LETTER.replace('Could we talk this week?', '{} Could we talk this week?')

    def test_each_phrase_is_flagged_in_a_letter_and_an_email(self):
        for sentence in ('I hope to become a PR soon.', 'This role supports my residency.', 'My resident status is temporary.',
                         'I am working toward a permanent visa.', 'I want to settle permanently in Victoria.',
                         'I am looking for a long-term visa.', 'Could you sponsor me later?', 'I may need sponsorship in the future.',
                         'This is part of my visa pathway.', 'A nomination would help me.'):
            letter = checks.letter_issues(self.BASE.format(sentence))
            self.assertTrue(any('residency or migration' in i for i in letter), (sentence, letter))
            email = checks.email_issues('Junior Civil Drafter', 'Hello,\n\n' + sentence + '\n\nMarc Masarate')
            self.assertTrue(any('residency or migration' in i for i in email), (sentence, email))
        self.assertTrue(any('residency or migration' in i for i in checks.email_issues('PR holder, Junior Civil Drafter', 'Hello.')))

    def test_no_false_hits(self):
        for sentence in ('I present PRE-START checks each morning.', 'I prepared progress reports.', 'The present role suits me.',
                         'I was nominated for a student award.', 'I live in Melton and can start two weeks after an offer.'):
            issues = checks.letter_issues(self.BASE.format(sentence))
            self.assertFalse(any('residency or migration' in i for i in issues), (sentence, issues))
        self.assertEqual(checks.letter_issues(LETTER), [])


# ------------------------------------------------------------------ L-m2: exit 3 on SEEK names the routes still open

class OtherRoutesOnExit3(Case):
    def test_the_spacing_and_the_cap_say_the_other_routes_may_still_be_tried(self):
        self.add(entry(1))
        self.add(entry(2))
        self.claim()
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN, now=NOW + timedelta(minutes=1))
        self.assertEqual(code, 3)
        self.assertIn('the other routes (EMAIL, EMPLOYER_PORTAL, EMPLOYER_FORM) may still be tried', err)
        one = copy.deepcopy(CONFIG)
        one['limits']['seek_submissions_per_day'] = 1
        q.write_json(self.config, one)
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN, now=NOW + timedelta(minutes=40))
        self.assertEqual(code, 3)
        self.assertIn("the day's cap is reached", err)
        self.assertIn('the other routes (EMAIL, EMPLOYER_PORTAL, EMPLOYER_FORM) may still be tried', err)


if __name__ == '__main__':
    unittest.main()
