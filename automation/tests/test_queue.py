"""Tests for the apply queue (automation/scripts/queue.py). Offline: temp folders only."""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
# Loaded by path under another name: "import queue" may already mean the standard library's module in this process.
_spec = importlib.util.spec_from_file_location('apply_queue', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)
_spec = importlib.util.spec_from_file_location('import_backlog', SCRIPTS / 'import_backlog.py')
imp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(imp)

NOW = datetime(2026, 11, 13, 1, 0, tzinfo=timezone.utc)  # midday on 13 Nov 2026 in Melbourne
CONFIG = {'lanes': {'drafter': {'rank': 1}, 'technician': {'rank': 2}, 'engineer': {'rank': 3}},
          'limits': {'seek_submissions_per_day': 6, 'email_sends_per_day': 3, 'portal_submissions_per_day': 3,
                     'min_minutes_between_seek_submissions': 20}}
# The parts of automation/facts.json these tests rely on, as approved on 13 Nov 2026.
FACTS = {
    'identity': {'phone': '0478 764 077', 'location': 'Melton VIC 3337'},
    'education': [{'qualification': 'Advanced Diploma of Civil Construction Design'},
                  {'qualification': 'Bachelor of Science in Civil Engineering (BSCE)'}],
    'experience': [{'role': 'Console Operator (casual)'}, {'role': 'Project-in-Charge Engineer (Entry Level)'},
                   {'role': 'Field Engineer'}, {'role': 'Technical Support Representative – Microsoft Software'}],
    'answers': {
        'right_to_work': {'choose': 'The option that names a graduate temporary work visa (Subclass 485). If the list has no such '
                                    'option, choose the temporary visa option that has no restriction on hours or industry.'},
        'notice_period': '2 weeks',
        'expected_salary': {'rule': 'If the advert states pay, choose the band that contains the advertised figure (the lower end '
                                    'when it is a range). If the advert states no pay, choose $65,000 to $75,000.',
                            'single_figure_when_no_pay_stated': '70000'},
        'drivers_licence': 'Yes. If the form asks full or probationary, or manual or automatic: not confirmed, skip and report.',
        'own_car_or_regular_access': 'Yes',
        'white_card': 'Yes',
        'police_check': 'Yes, current National Police Certificate',
        'pre_employment_medical': 'Yes',
        'drug_and_alcohol_screening': 'Yes',
        'currently_studying': 'No',
        'qualification_questions': {'civil engineering': 'Yes: Bachelor of Science in Civil Engineering (2019)', 'engineering': 'Yes',
                                    'engineering drafting or design': 'Yes: Advanced Diploma of Civil Construction Design',
                                    'any other named qualification': "Only if it is in 'education' or 'eligibility'; otherwise No"},
        'years_of_experience': {
            'civil engineer, site engineer, project engineer, construction industry':
                "Choose the option that contains 11 months (usually 'Less than 1 year'): April 2019 to February 2020, Philippines.",
            'drafter, draftsperson, designer, CAD': 'Choose the lowest option (no paid role). Free text if offered: two years of study.',
            'laboratory, materials testing, technician, estimator, project coordinator, project management, any other role':
                'Choose the lowest option (no paid role).',
            'rule': 'Never choose an option higher than the facts support.'},
        'software': {'CAD': 'AutoCAD, Civil 3D and Revit only. Never tick 12d, MicroStation, OpenRoads, Tekla, SIDRA or anything else.',
                     'Microsoft Office': 'Yes. If individual products must be ticked: not confirmed, skip and report.'},
        'experience_yes_no': {'engineering drawing interpretation': 'Yes',
                              'site inspections, quality checks, progress reports, coordinating crews': 'Yes',
                              'preparing and submitting tenders': 'No',
                              'civil infrastructure projects': 'Not confirmed (see honest_limits): if mandatory, skip and report',
                              'anything else': "Yes only if a line in 'experience' or 'education' supports it; otherwise No"},
        'english_self_rating': 'Not on record: skip and report',
    },
}
# The saved adverts keep question text only, no option lists, so these lists are written the way the SEEK form usually
# shows them. The tests check how an answer is picked, not SEEK's exact wording.
RIGHT_TO_WORK = ["I'm an Australian citizen", "I'm a permanent resident and/or NZ citizen",
                 'I have a family/partner visa with no restrictions', 'I have a graduate temporary work visa',
                 'I have a holiday temporary work visa', 'I have a temporary visa with restrictions on industry (e.g. skilled work visa 482)',
                 'I have a temporary visa with no restrictions (e.g. doctoral student)',
                 'I have a temporary visa with restrictions on work hours (e.g. student visa, retirement visa)',
                 'I require sponsorship to work for a new employer (e.g. 482, 457)']
YEARS = ['No experience', 'Less than 1 year', '1 year', '2 years', '3 years', '4 years', '5 years', 'More than 5 years']
NOTICE = ["None, I'm ready to go now", 'Less than 2 weeks', '2 weeks', '1 month', '2 months', '3 months', 'More than 3 months']
YES_NO = ['Yes', 'No']
RTW = 'Which of the following statements best describes your right to work in Australia?'


def ans(question, options=None, facts=FACTS):
    return q.answer_question(question, options, facts)


def entry(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


def email_entry(n, **kw):
    e = entry(n, route='EMAIL', seek_id='', url=f'https://example{n}.com.au/careers',
              email={'to': f'jobs@example{n}.com.au', 'subject': 'Junior Civil Drafter', 'body': 'Hello.',
                     'evidence_url': f'https://example{n}.com.au/careers'})
    e.update(kw)
    return e


class StdlibNameTests(unittest.TestCase):
    def test_standard_queue_names_are_re_exported(self):
        for name in ('Queue', 'Empty', 'Full', 'LifoQueue', 'PriorityQueue', 'SimpleQueue'):
            self.assertTrue(hasattr(q, name), name)
        box = q.Queue()
        box.put(1)
        self.assertEqual(box.get_nowait(), 1)
        with self.assertRaises(q.Empty):
            box.get_nowait()

    def test_standard_library_still_works_with_scripts_folder_first_on_path(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import queue, concurrent.futures as cf\n'
                'assert queue.__file__.startswith(sys.argv[1]) and hasattr(queue, "answer_question")\n'
                'with cf.ThreadPoolExecutor(2) as ex: print(sum(ex.map(lambda x: x * 2, range(4))))')
        out = subprocess.run([sys.executable, '-c', code, str(SCRIPTS)], capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout.strip()), (0, '12'), out.stderr)


class AnswerQuestionTests(unittest.TestCase):
    def ok(self, result, answer, basis_end):
        self.assertEqual((result['status'], result['answer']), ('answered', answer))
        self.assertTrue(result['basis'].endswith(basis_end), result['basis'])
        self.assertIsNotNone(q.fact_at(FACTS, result['basis']))

    def no(self, result):
        self.assertEqual((result['status'], result['answer']), ('unanswered', ''))

    def test_right_to_work(self):
        self.ok(ans(RTW, RIGHT_TO_WORK), 'I have a graduate temporary work visa', 'right_to_work.choose')
        self.ok(ans(RTW), FACTS['answers']['right_to_work']['choose'], 'right_to_work.choose')
        without_485 = [o for o in RIGHT_TO_WORK if 'graduate' not in o]
        self.ok(ans(RTW, without_485), 'I have a temporary visa with no restrictions (e.g. doctoral student)', 'right_to_work.choose')
        self.ok(ans(RTW.replace('?', ''), RIGHT_TO_WORK), 'I have a graduate temporary work visa', 'right_to_work.choose')

    def test_right_to_work_never_citizen_resident_or_sponsorship(self):
        self.no(ans(RTW, ["I'm an Australian citizen", "I'm a permanent resident and/or NZ citizen",
                          'I require sponsorship to work for a new employer (e.g. 482, 457)']))
        self.no(ans(RTW, ['Graduate visa 485, sponsorship required later', "I'm an Australian citizen"]))
        self.no(ans(RTW, ['I have a family/partner visa with no restrictions', "I'm an Australian citizen"]))
        self.no(ans('Are you legally entitled to work in Australia?', YES_NO))
        self.no(ans('Will you require visa sponsorship in the future?', YES_NO))

    def test_years_as_an_engineer_is_under_one_year(self):
        for role in ('a civil engineer', 'a site engineer', 'a project engineer', 'a Civil Project Engineer', 'a Civil Site Engineer'):
            text = f"How many years' experience do you have as {role}?"
            self.ok(ans(text, YEARS), 'Less than 1 year', 'construction industry')
            self.assertIn('11 months', ans(text)['answer'])
        self.ok(ans("How many years' experience do you have in the construction industry?", YEARS), 'Less than 1 year', 'construction industry')
        self.ok(ans('How many years’ experience do you have as a civil engineer?', ['0-1 years', '1-2 years', '3+ years']), '0-1 years', 'industry')
        self.no(ans("How many years' experience do you have as a civil engineer?", ['1 year', '2 years', '3 or more years']))

    def test_years_as_a_drafter_or_other_role_is_the_lowest_option(self):
        for role in ('a draftsperson', 'a civil drafter', 'a civil designer', 'a CAD Draftsperson', 'a Revit Draftsperson'):
            self.ok(ans(f"How many years' experience do you have as {role}?", YEARS), 'No experience', 'designer, CAD')
        for role in ('an Estimator', 'a project coordinator', 'a Civil Engineering Technician', 'a Quality Assurance Trainee'):
            self.ok(ans(f"How many years' experience do you have as {role}?", YEARS), 'No experience', 'any other role')
        self.ok(ans("How many years' experience do you have as a civil drafter?", YEARS[1:]), 'Less than 1 year', 'designer, CAD')
        self.assertIn('lowest option', ans("How many years' experience do you have as a civil drafter?")['answer'])
        self.no(ans("How many years' experience do you have as a civil drafter?", ['1 year', '2 years']))

    def test_years_is_not_guessed(self):
        for text in ("How many years' experience do you have as an Engineer Graduate?",   # an engineer title outside the named ones
                     "How many years' experience do you have as a design engineer?",
                     "How many years' experience do you have as a Technical Support Officer?",  # a job he has held
                     "How many years' experience do you have as a Console Operator?",
                     "How many years' experience do you have in your current occupation?",
                     "How many years' experience do you have in a consulting role?",
                     "How many years' experience do you have with project planning and scheduling?",
                     "How many years' experience do you have as a Site Engineer / Estimator?",  # two standing answers disagree
                     'How many years of estimating experience do you have?',
                     'How many years of Road Construction experience do you have?'):
            self.no(ans(text, YEARS))
            self.no(ans(text))
        self.assertEqual(ans("How many years' experience do you have as a civil engineer?", YEARS, {'answers': {}})['status'], 'unanswered')

    def test_notice(self):
        text = 'How much notice are you required to give your current employer?'
        self.ok(ans(text, NOTICE), '2 weeks', 'notice_period')
        self.ok(ans(text), '2 weeks', 'notice_period')
        self.no(ans(text, ['None', '1 month', '2 months']))
        self.no(ans('What is the notice period for your current employment?', NOTICE))

    def test_salary_gives_the_rule(self):
        for text in ("What's your expected annual base salary?", 'What’s your expected Annual Base Salary? ', 'What is your expected annual base salary?'):
            r = ans(text, ['$60K', '$70K', '$80K'])
            self.assertEqual((r['status'], r['basis']), ('answered', 'answers.expected_salary.rule'))
            self.assertIn('$65,000 to $75,000', r['answer'])
            self.assertTrue(r['answer'].endswith('Single figure when the advert states no pay: 70000.'), r['answer'])
        self.no(ans("What's your expected hourly rate?"))
        self.no(ans('Please detail your minimum salary expectations (including super):'))

    def test_drivers_licence(self):
        text = "Do you have a current Australian driver's licence?"
        self.ok(ans(text, YES_NO), 'Yes', 'drivers_licence')
        self.ok(ans('Do you have a current Australian driver’s licence?'), 'Yes', 'drivers_licence')
        self.no(ans(text, ['Yes, full licence', 'Yes, probationary licence', 'No']))   # full or probationary is not confirmed
        self.no(ans(text, ['Yes - manual', 'Yes - automatic', 'No']))
        self.no(ans("Do you have a current Australian manual driver's licence?", YES_NO))
        self.no(ans('Do you hold a valid driver’s license?', YES_NO))

    def test_qualification(self):
        base = 'Have you completed a qualification in {}?'
        self.ok(ans(base.format('civil engineering'), YES_NO), 'Yes', 'qualification_questions.civil engineering')
        self.ok(ans(base.format('engineering')), 'Yes', 'qualification_questions.engineering')
        self.ok(ans(base.format('engineering drafting / engineering design'), YES_NO), 'Yes', 'engineering drafting or design')
        self.ok(ans(base.format('civil construction'), YES_NO), 'Yes', 'any other named qualification')
        for field in ('construction management', 'structural engineering', 'building design / building design drafting', 'project management'):
            self.ok(ans(base.format(field), YES_NO), 'No', 'any other named qualification')
        self.no(ans(base.format('civil engineering'), ['Completed', 'Currently studying', 'Not started']))
        self.no(ans(base.format('surveying'), YES_NO, {'answers': {'qualification_questions': {}}}))
        self.no(ans("What's your highest level of education?"))

    def test_experience_yes_no(self):
        self.ok(ans('Do you have Engineering Drawing Interpretation experience?', YES_NO), 'Yes', 'engineering drawing interpretation')
        self.ok(ans('Do you have experience preparing and submitting tenders?', YES_NO), 'No', 'preparing and submitting tenders')
        self.ok(ans('Do you have experience carrying out site inspections?'), 'Yes', 'coordinating crews')
        not_confirmed = ans('Do you have experience working on civil infrastructure projects?', YES_NO)
        self.no(not_confirmed)
        self.assertEqual(not_confirmed['basis'], 'answers.experience_yes_no.civil infrastructure projects')
        for text in ('Do you have experience using Microsoft Excel?', 'Do you have customer service experience?',
                     'Do you have mine site experience?', 'Do you have Traffic Control experience?',
                     'Do you have experience working on residential construction projects?'):
            self.no(ans(text, YES_NO))

    def test_which_of_the_following(self):
        cad = 'Which of the following CAD software do you have experience with?'
        self.ok(ans(cad, ['AutoCAD', 'Revit', 'MicroStation', '12D', 'AutoCAD Civil 3D', 'Tekla', 'None of these']),
                'AutoCAD; Revit; AutoCAD Civil 3D', 'software.CAD')
        self.ok(ans(cad), FACTS['answers']['software']['CAD'], 'software.CAD')
        self.no(ans(cad, ['12D', 'MicroStation', 'None of these']))
        office = ans('Which of the following Microsoft Office products are you experienced with?', ['Word', 'Excel', 'Outlook'])
        self.no(office)   # individual products are not confirmed
        self.assertEqual(office['basis'], 'answers.software.Microsoft Office')
        self.no(ans('Which of the following Microsoft Office products are you experienced with?'))
        self.no(ans('Which of the following types of infrastructure project do you have experience with?', ['Roads', 'Rail']))

    def test_plain_yes_no_questions(self):
        for text, answer, key in (
                ('Do you hold a Construction Induction Safety certificate (White Card)?', 'Yes', 'white_card'),
                ('Are you willing to undergo a pre-employment medical check?', 'Yes', 'pre_employment_medical'),
                ('Do you have a current Police Check (National Police Certificate) for employment?', 'Yes', 'police_check'),
                ('Do you own or have regular access to a car?', 'Yes', 'own_car_or_regular_access'),
                ('Are you willing to undergo pre-employment drug and alcohol screening?', 'Yes', 'drug_and_alcohol_screening'),
                ('Are you currently studying?', 'No', 'currently_studying')):
            self.ok(ans(text, YES_NO), answer, key)
            self.ok(ans(text), answer, key)
            self.no(ans(text, ['Maybe', 'Unsure']))
            self.no(ans(text, YES_NO, {'answers': {}}))
        self.no(ans('Do you hold a current White Card / General Construction Induction Training Card?', YES_NO))
        self.no(ans('Are you willing to complete a Police Check?', YES_NO))

    def test_english_rating_is_not_on_record(self):
        text = 'How would you rate your English language skills?'
        self.no(ans(text, ['Speaks proficiently in a professional setting', 'Writes proficiently in a professional setting', 'Limited proficiency']))
        self.no(ans(text))
        self.assertEqual(ans(text)['basis'], 'answers.english_self_rating')
        later = {'answers': {'english_self_rating': 'Fluent'}}   # once the owner gives an answer it is used
        self.assertEqual(ans(text, ['Basic', 'Fluent'], later)['answer'], 'Fluent')

    def test_unknown_questions_come_back_unanswered(self):
        for text in ('Tell us what motivated you to apply for this role?', 'Are you a current member of Engineers Australia?',
                     'Are you willing to relocate for this role?', 'Where are you located?', '', None):
            self.no(ans(text, YES_NO))

    def test_every_listed_question_against_the_real_facts_file(self):
        facts = q.read_json(SCRIPTS.parent / 'facts.json')
        listed = [RTW, "How many years' experience do you have as a civil drafter?", 'How much notice are you required to give your current employer?',
                  "What's your expected annual base salary?", "Do you have a current Australian driver's licence?",
                  'Have you completed a qualification in civil engineering?', 'Do you have Engineering Drawing Interpretation experience?',
                  'Which of the following CAD software do you have experience with?', "How many years' experience do you have in the construction industry?",
                  'Do you hold a Construction Induction Safety certificate (White Card)?', 'Are you willing to undergo a pre-employment medical check?',
                  'Do you have a current Police Check (National Police Certificate) for employment?', 'Do you own or have regular access to a car?',
                  'Are you willing to undergo pre-employment drug and alcohol screening?', 'How would you rate your English language skills?',
                  'Are you currently studying?']
        for text in listed:
            r = q.answer_question(text, None, facts)
            self.assertEqual(set(r), {'answer', 'basis', 'status'})
            self.assertEqual(r['status'] == 'answered', bool(r['answer']), text)
            self.assertIsNotNone(q.fact_at(facts, r['basis']), text)   # every listed question maps to a key that exists


class QueueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / 'queue'
        self.config = Path(self.tmp.name) / 'config.json'
        self.facts = Path(self.tmp.name) / 'facts.json'
        q.write_json(self.config, CONFIG)
        q.write_json(self.facts, FACTS)

    def add(self, e, **kw):
        return q.add(e, self.dir, FACTS, kw.pop('now', NOW), **kw)

    def next(self, route='SEEK', now=NOW, by=None):
        return q.next_entry(route, self.dir, CONFIG, now, by)

    def applied(self, entry_id, at, kind='seek_confirmation_screen'):
        return q.mark(self.dir, entry_id, 'applied', 'grok', NOW, kind, 'ref-1', at, facts=FACTS)

    def cli(self, *args, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--now', q.iso(now), *args])
        return code, out.getvalue(), err.getvalue()

    def file(self, name, data):
        path = Path(self.tmp.name) / name
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
        return str(path)


class AddTests(QueueCase):
    def test_add_fills_the_entry_and_writes_one_file(self):
        e = self.add(entry(101, questions=[RTW]))
        self.assertEqual(e['id'], 'seek-101')
        self.assertEqual(list(e), list(q.FIELDS))
        self.assertEqual((e['status'], e['resume_variant'], e['closes_source'], e['created_at']), ('OPEN', 'drafter', 'none', '2026-11-13T01:00:00Z'))
        self.assertEqual(e['questions'][0]['status'], 'answered')
        self.assertEqual([p.name for p in (self.dir / 'open').iterdir()], ['seek-101.json'])
        self.assertEqual(q.read_json(self.dir / 'open' / 'seek-101.json'), e)

    def test_id_without_a_seek_number_is_company_role_and_url_hash(self):
        e = self.add(email_entry(7, company='Breese Pitt Dixon', role='Speculative enquiry: civil designer'))
        self.assertRegex(e['id'], r'^breese-pitt-dixon-speculative-enquiry-civil-designer-[0-9a-f]{8}$')
        self.assertEqual(q.make_id(e), e['id'])

    def test_duplicates_are_refused_open_or_done(self):
        self.add(entry(101))
        for dup in (entry(101), entry(999, id='seek-101'), entry(101, id='other-id'),
                    entry(999, seek_id='999', url='https://au.seek.com/job/101?tracking=x')):
            with self.assertRaises(q.Refused) as r:
                self.add(dup)
            self.assertIn('duplicate of seek-101', str(r.exception))
        self.add(email_entry(1))
        with self.assertRaises(q.Refused):
            self.add(email_entry(1, company='Another name', url='https://www.example1.com.au/careers/'))
        self.applied('seek-101', '2026-11-13T00:30:00Z')
        with self.assertRaises(q.Refused) as r:
            self.add(entry(101))
        self.assertIn('APPLIED', str(r.exception))
        self.assertEqual(len(q.load(self.dir)), 2)

    def test_an_application_made_elsewhere_can_be_added_as_applied(self):
        receipt = {'at': '2026-10-06T03:00:00Z', 'by': 'owner', 'kind': 'seek_receipt_email', 'ref': 'SEEK receipt email of 6 Oct 2026'}
        self.add(entry(1, company='Fyfe Pty Ltd', role='Graduate Civil Engineer', status='APPLIED', receipt=receipt))
        self.assertTrue((self.dir / 'done' / '2026-10' / 'seek-1.json').exists())
        self.add(email_entry(2, company='Fyfe', role='Graduate Civil Engineer'))
        with self.assertRaises(q.NothingToDo) as r:
            self.next('EMAIL')
        self.assertIn('already applied for this company and role', str(r.exception))

    def test_a_broken_file_is_named_not_a_traceback(self):
        self.add(entry(1))
        (self.dir / 'open' / 'seek-1.json').write_text('<<<<<<< HEAD\n{"id": "seek-1"}\n', encoding='utf-8')
        code, out, err = self.cli('list')
        self.assertEqual(code, 1)
        self.assertIn('seek-1.json: cannot be read as JSON', err)

    def test_invalid_entries_are_refused(self):
        bad = [entry(1, lane='labourer'), entry(1, route='JORA'), entry(1, seek_id=''), entry(1, company=''), entry(1, url='seek'),
               entry(1, closes_at='16 Nov 2026', closes_source='advert'), entry(1, closes_at='2026-11-16'),
               entry(1, closes_source='advert'), entry(1, status='ASK_OWNER'), entry(1, status='HELD'), entry(1, fit=140),
               email_entry(1, email={'to': '', 'subject': 's', 'body': 'b', 'evidence_url': 'https://x.com.au'}),
               email_entry(1, email={'to': 'jobs@x.com.au', 'subject': 's', 'body': 'b', 'evidence_url': ''}),
               entry(1, status='APPLIED')]
        for e in bad:
            with self.assertRaises(q.Refused, msg=e):
                self.add(e)
        self.assertEqual(q.load(self.dir), [])

    def test_privacy_checks(self):
        own = self.add(email_entry(1, email={'to': 'jobs@example1.com.au', 'subject': 's', 'evidence_url': 'https://example1.com.au',
                                             'body': 'Kind regards,\nMarc\n0478 764 077\n+61 478 764 077'}))
        self.assertEqual(own['status'], 'OPEN')
        for text in ('Call Greg on 1300 176 077', 'Enquiries (02) 6622 1011', 'ring\n0412 345 678', 'Licence number: 012345678',
                     'Date of birth: 3 March 1996', 'DOB 03/03/1996'):
            with self.assertRaises(q.Refused, msg=text) as r:
                self.add(entry(2, notes=text))
            self.assertIn('privacy', str(r.exception))
        self.assertEqual(q.privacy_problems(entry(3, notes='SEEK 95347045, closes 2026-11-18, $80,000 to $85,000, AS 1289'), FACTS), [])


class NextTests(QueueCase):
    def test_order_is_lane_then_real_closing_date_then_newest_listing(self):
        self.add(entry(1, lane='engineer', closes_at='2026-11-14', closes_source='advert'))
        self.add(entry(2, lane='technician', closes_at='2026-11-15', closes_source='advert'))
        self.add(entry(3, lane='drafter', listed_at='2026-11-01'))
        self.add(entry(4, lane='drafter', listed_at='2026-11-12'))
        self.add(entry(5, lane='drafter', listed_at='2026-11-13', closes_at='2026-11-14', closes_source='listing_expiry'))
        self.add(entry(6, lane='drafter', listed_at='2026-10-20', closes_at='2026-11-30', closes_source='advert'))
        self.add(entry(7, lane='drafter', listed_at='2026-10-25', closes_at='2026-11-20', closes_source='advert'))
        order = []
        for _ in range(7):
            e = self.next()
            order.append(e['seek_id'])
            q.mark(self.dir, e['id'], 'skipped', 'test', NOW, note='ordering test')
        # drafter first: stated closing dates soonest (7, 6), then the rest newest first (a listing expiry is not a
        # real closing date); then technician; then engineer
        self.assertEqual(order, ['7', '6', '5', '4', '3', '2', '1'])

    def test_next_is_per_route_and_peeks_without_by(self):
        self.add(entry(1))
        self.add(email_entry(2))
        self.assertEqual(self.next('EMAIL')['route'], 'EMAIL')
        self.assertEqual(self.next('SEEK')['id'], 'seek-1')
        self.assertEqual(self.next('SEEK')['id'], 'seek-1')
        self.assertEqual(q.find(self.dir, 'seek-1')[1]['attempts'], [])
        with self.assertRaises(q.NothingToDo):
            self.next('EMPLOYER_PORTAL')

    def test_unanswered_question_is_never_handed_out(self):
        e = self.add(entry(1, questions=[RTW, 'How would you rate your English language skills?']))
        self.assertEqual(e['status'], 'ASK_OWNER')
        self.assertIn('English language skills', e['ask_owner'])
        with self.assertRaises(q.NothingToDo) as r:
            self.next()
        self.assertIn('seek-1: status ASK_OWNER; unanswered question', str(r.exception))
        # even when a file is edited by hand to say OPEN, the unanswered question still holds it back
        path, stored = q.find(self.dir, 'seek-1')
        stored['status'], stored['ask_owner'] = 'OPEN', ''
        q.write_json(path, stored)
        with self.assertRaises(q.NothingToDo):
            self.next()
        # a question marked optional does not hold it back
        stored['questions'][1]['mandatory'] = False
        q.write_json(path, stored)
        self.assertEqual(self.next()['id'], 'seek-1')

    def test_past_closing_date_is_never_handed_out(self):
        self.add(entry(1, closes_at='2026-11-12', closes_source='advert'))
        self.add(entry(2, closes_at='2026-11-12', closes_source='listing_expiry'))
        with self.assertRaises(q.NothingToDo):
            self.next()
        self.add(entry(3, closes_at='2026-11-13', closes_source='advert'))   # closes today: still good
        self.assertEqual(self.next()['id'], 'seek-3')

    def test_company_and_role_already_applied_is_never_handed_out(self):
        self.add(entry(1, company='Fyfe Pty Ltd', role='Graduate Civil Engineer'))
        self.add(entry(2, company='Fyfe', role='Graduate Civil Engineer', route='EMPLOYER_PORTAL', url='https://careers.example.com/fyfe/1', seek_id=''))
        self.applied('seek-1', '2026-11-12T00:00:00Z')
        with self.assertRaises(q.NothingToDo) as r:
            self.next('EMPLOYER_PORTAL')
        self.assertIn('already applied for this company and role', str(r.exception))

    def test_letter_marked_for_rewrite_and_missing_email_text_are_held_back(self):
        self.add(entry(1, notes='letter written under the old rules: rewrite before use\nfit 70% under the old rubric'))
        self.add(email_entry(2, email={'to': 'jobs@example2.com.au', 'subject': '', 'body': '', 'evidence_url': 'https://example2.com.au/careers'}))
        for route, why in (('SEEK', 'letter to rewrite'), ('EMAIL', 'email text missing')):
            with self.assertRaises(q.NothingToDo) as r:
                self.next(route)
            self.assertIn(why, str(r.exception))
        letter = self.file('letter.txt', 'A new short letter.\n')
        self.assertEqual(self.cli('letter', 'seek-1', '--file', letter)[0], 0)
        e = self.next()
        self.assertEqual((e['cover_letter_text'], e['notes']), ('A new short letter.', 'fit 70% under the old rubric'))
        body = self.file('email.txt', 'Hello,\nMarc\n0478 764 077\n')
        e2 = q.find(self.dir, 'seek-1')[1]['id']
        self.assertEqual(e2, 'seek-1')
        email_id = [e['id'] for _, e in q.load(self.dir) if e['route'] == 'EMAIL'][0]
        self.assertEqual(self.cli('letter', email_id, '--file', letter, '--subject', 'Junior Civil Drafter', '--body-file', body)[0], 0)
        self.assertEqual(self.next('EMAIL')['email']['body'], 'Hello,\nMarc\n0478 764 077')

    def test_by_records_the_start_and_a_started_entry_is_not_handed_out_twice(self):
        self.add(entry(1))
        self.add(entry(2, listed_at='2026-11-01'))
        first = self.next(by='grok')
        self.assertEqual((first['id'], first['attempts'][-1]['result'], first['attempts'][-1]['by']), ('seek-1', 'started', 'grok'))
        self.assertEqual(self.next(by='grok')['id'], 'seek-2')
        with self.assertRaises(q.NothingToDo) as r:
            self.next(by='grok')
        self.assertIn('started by grok, no result recorded', str(r.exception))
        q.mark(self.dir, 'seek-1', 'failed', 'grok', NOW, note='SEEK page timed out')
        self.assertEqual(self.next()['id'], 'seek-1')   # a recorded failure frees it for another try

    def test_cli_next_prints_the_entry_or_exits_4(self):
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, out), (4, ''))
        self.assertIn('nothing to hand out', err)
        self.add(entry(1))
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', 'grok')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['id'], 'seek-1')


class CapTests(QueueCase):
    def fill(self, count, route='SEEK', start=100, at='2026-11-12T22:00:00Z', kind='seek_confirmation_screen'):
        for n in range(start, start + count):
            e = self.add(entry(n) if route == 'SEEK' else email_entry(n, route=route))
            self.applied(e['id'], at, kind)

    def test_seek_daily_cap(self):
        self.fill(5)
        self.add(entry(1))
        self.assertEqual(self.next()['id'], 'seek-1')
        self.fill(1, start=200)
        with self.assertRaises(q.CapReached) as r:
            self.next()
        self.assertIn('6 of 6 submitted on 2026-11-13', str(r.exception))
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, out), (3, ''))
        self.assertIn("the day's cap is reached", err)
        self.assertEqual(self.next(now=NOW + timedelta(days=1))['id'], 'seek-1')   # a new Melbourne day

    def test_cap_counts_the_melbourne_date_of_the_receipt(self):
        self.fill(6, at='2026-11-12T12:30:00Z')   # 11.30pm on 12 Nov in Melbourne: yesterday
        self.add(entry(1))
        self.assertEqual(self.next()['id'], 'seek-1')
        self.fill(6, start=200, at='2026-11-12T13:30:00Z')   # 12.30am on 13 Nov in Melbourne: today
        with self.assertRaises(q.CapReached):
            self.next()

    def test_seek_spacing(self):
        self.add(entry(1))
        self.fill(1, at='2026-11-13T00:48:00Z')   # 12 minutes before NOW
        with self.assertRaises(q.CapReached) as r:
            self.next()
        self.assertIn('12 minutes ago; wait 9 more', str(r.exception))
        self.assertEqual(self.cli('next', '--route', 'SEEK')[0], 3)
        self.assertEqual(self.next(now=NOW + timedelta(minutes=8))['id'], 'seek-1')

    def test_email_cap_and_no_spacing_rule_for_email(self):
        self.add(email_entry(1))
        self.fill(2, route='EMAIL', at='2026-11-13T00:59:00Z', kind='gmail_message_id')
        self.assertEqual(self.next('EMAIL')['route'], 'EMAIL')
        self.fill(1, route='EMAIL', start=300, at='2026-11-13T00:59:30Z', kind='gmail_message_id')
        with self.assertRaises(q.CapReached):
            self.next('EMAIL')
        self.add(entry(2))
        self.assertEqual(self.next('SEEK')['id'], 'seek-2')   # other routes are not affected

    def test_portal_and_form_share_one_cap(self):
        self.fill(2, route='EMPLOYER_PORTAL', kind='portal_confirmation')
        self.fill(1, route='EMPLOYER_FORM', start=300, kind='portal_confirmation')
        self.add(email_entry(1, route='EMPLOYER_PORTAL'))
        for route in ('EMPLOYER_PORTAL', 'EMPLOYER_FORM'):
            with self.assertRaises(q.CapReached):
                self.next(route)

    def test_a_missing_limit_is_refused_not_ignored(self):
        self.add(entry(1))
        with self.assertRaises(q.Refused) as r:
            q.next_entry('SEEK', self.dir, {'limits': {}}, NOW)
        self.assertIn('seek_submissions_per_day is not set', str(r.exception))


class MarkTests(QueueCase):
    def test_applied_moves_the_entry_to_done_with_its_receipt(self):
        self.add(entry(1, status='ASK_OWNER', ask_owner='Would you move to Perth?'))
        code, out, err = self.cli('mark', 'seek-1', 'applied', '--by', 'grok', '--kind', 'seek_receipt_email', '--ref', 'gmail:18f3a', '--at', '2026-10-31T22:15:00Z')
        self.assertEqual((code, out.strip()), (0, 'seek-1: APPLIED'))
        self.assertFalse((self.dir / 'open' / 'seek-1.json').exists())
        e = q.read_json(self.dir / 'done' / '2026-11' / 'seek-1.json')   # 1 Nov in Melbourne
        self.assertEqual(e['receipt'], {'at': '2026-10-31T22:15:00Z', 'by': 'grok', 'kind': 'seek_receipt_email', 'ref': 'gmail:18f3a'})
        self.assertEqual((e['status'], e['ask_owner'], e['attempts'][-1]['result']), ('APPLIED', '', 'applied'))
        self.assertEqual(self.cli('mark', 'seek-1', 'skipped', '--by', 'grok', '--reason', 'x')[0], 1)   # finished entries stay finished

    def test_applied_needs_kind_and_ref(self):
        self.add(entry(1))
        for kw in ({'kind': None, 'ref': 'r'}, {'kind': 'seek_receipt_email', 'ref': ''}, {'kind': 'text_message', 'ref': 'r'}):
            with self.assertRaises(q.Refused):
                q.mark(self.dir, 'seek-1', 'applied', 'grok', NOW, **kw)
        self.assertEqual(q.find(self.dir, 'seek-1')[1]['status'], 'OPEN')
        with self.assertRaises(q.Refused):
            q.mark(self.dir, 'seek-404', 'applied', 'grok', NOW, 'seek_receipt_email', 'r')

    def test_skipped_needs_a_reason_and_moves_to_done(self):
        self.add(entry(1))
        self.assertEqual(self.cli('mark', 'seek-1', 'skipped', '--by', 'grok')[0], 1)
        self.assertEqual(self.cli('mark', 'seek-1', 'skipped', '--by', 'grok', '--reason', 'advert removed')[0], 0)
        e = q.read_json(self.dir / 'done' / '2026-11' / 'seek-1.json')
        self.assertEqual((e['status'], e['attempts'][-1]['note']), ('SKIPPED', 'advert removed'))

    def test_failed_stays_open_and_the_third_failure_asks_the_owner(self):
        self.add(entry(1))
        for n in (1, 2):
            self.assertEqual(self.cli('mark', 'seek-1', 'failed', '--by', 'grok', '--note', f'timeout {n}')[0], 0)
            self.assertEqual(q.find(self.dir, 'seek-1')[1]['status'], 'OPEN')
        self.assertEqual(self.next()['id'], 'seek-1')
        code, out, _ = self.cli('mark', 'seek-1', 'failed', '--by', 'grok', '--note', 'form would not load')
        e = q.find(self.dir, 'seek-1')[1]
        self.assertEqual((e['status'], e['ask_owner']), ('ASK_OWNER', 'Three failed attempts (last: form would not load). Try again or drop it?'))
        self.assertTrue((self.dir / 'open' / 'seek-1.json').exists())
        self.assertIn('Three failed attempts', out)
        with self.assertRaises(q.NothingToDo):
            self.next()
        # the owner says try again: the count starts over
        self.assertEqual(self.cli('mark', 'seek-1', 'open', '--by', 'claude', '--note', 'owner: try again')[0], 0)
        self.cli('mark', 'seek-1', 'failed', '--by', 'grok', '--note', 'timeout again')
        self.assertEqual(q.find(self.dir, 'seek-1')[1]['status'], 'OPEN')

    def test_failed_final_closes_the_entry(self):
        self.add(entry(1))
        self.assertEqual(self.cli('mark', 'seek-1', 'failed', '--by', 'grok', '--note', 'employer form is broken', '--final')[0], 0)
        self.assertEqual(q.read_json(self.dir / 'done' / '2026-11' / 'seek-1.json')['status'], 'FAILED')

    def test_ask_and_open(self):
        self.add(entry(1, questions=['How would you rate your English language skills?']))
        self.add(entry(2))
        self.assertEqual(self.cli('mark', 'seek-2', 'ask', '--by', 'grok', '--question', 'The form asks for a start date: which date?')[0], 0)
        e = q.find(self.dir, 'seek-2')[1]
        self.assertEqual((e['status'], e['ask_owner'], e['attempts'][-1]['result']), ('ASK_OWNER', 'The form asks for a start date: which date?', 'asked_owner'))
        self.assertEqual(self.cli('mark', 'seek-2', 'open', '--by', 'claude')[0], 0)
        self.assertEqual(self.next()['id'], 'seek-2')
        code, _, err = self.cli('mark', 'seek-1', 'open', '--by', 'claude')   # cannot be opened past an unanswered question
        self.assertEqual(code, 1)
        self.assertIn('still has an unanswered question', err)


class ExpireTests(QueueCase):
    def test_expire_moves_past_entries_to_done_and_reports_them(self):
        self.add(entry(1, closes_at='2026-11-12', closes_source='advert'))
        self.add(entry(2, closes_at='2026-11-13', closes_source='advert'))
        self.add(entry(3, closes_at='2026-11-10', closes_source='listing_expiry', status='ASK_OWNER', ask_owner='Would you move to Cairns?'))
        self.add(entry(4))
        code, out, _ = self.cli('expire')
        self.assertEqual(code, 0)
        self.assertIn('expired seek-1: Acme 1, Junior Civil Drafter (closed 2026-11-12)', out)
        self.assertIn('2 expired', out)
        self.assertEqual(sorted(p.name for p in (self.dir / 'open').iterdir()), ['seek-2.json', 'seek-4.json'])
        gone = q.read_json(self.dir / 'done' / '2026-11' / 'seek-3.json')
        self.assertEqual((gone['status'], gone['ask_owner'], gone['attempts'][-1]['result']), ('EXPIRED', '', 'expired'))
        self.assertEqual(self.cli('expire')[1].strip(), '0 expired')

    def test_expire_today_option(self):
        self.add(entry(2, closes_at='2026-11-13', closes_source='advert'))
        self.assertIn('1 expired', self.cli('expire', '--today', '2026-11-14')[1])
        self.assertEqual(q.stats(self.dir, NOW)['expired_unsubmitted_total'], 1)


class AnswerCommandTests(QueueCase):
    def test_recompute_after_the_owner_answers_reopens_the_entry(self):
        self.add(entry(1, questions=[RTW, 'How would you rate your English language skills?']))
        facts = json.loads(json.dumps(FACTS))
        facts['answers']['english_self_rating'] = 'Fluent'
        q.write_json(self.facts, facts)
        code, out, _ = self.cli('answer', 'seek-1')
        shown = json.loads(out)
        self.assertEqual((code, shown['status'], shown['ask_owner']), (0, 'OPEN', ''))
        self.assertEqual(shown['questions'][1], {'question': 'How would you rate your English language skills?', 'options': [],
                                                 'answer': 'Fluent', 'basis': 'answers.english_self_rating', 'status': 'answered'})
        self.assertEqual(self.next()['id'], 'seek-1')

    def test_a_question_seen_on_the_form_is_added_with_its_options(self):
        self.add(entry(1, questions=[RTW]))
        code, out, _ = self.cli('answer', 'seek-1', '--question', RTW, *[x for o in RIGHT_TO_WORK for x in ('--option', o)])
        self.assertEqual(json.loads(out)['questions'][0]['answer'], 'I have a graduate temporary work visa')
        code, out, _ = self.cli('answer', 'seek-1', '--question', 'Do you have Traffic Control experience?', '--option', 'Yes', '--option', 'No')
        shown = json.loads(out)
        self.assertEqual(shown['status'], 'ASK_OWNER')
        self.assertEqual(shown['ask_owner'], 'No standing answer for this form question: Do you have Traffic Control experience? (options: Yes / No)')
        self.assertEqual(len(shown['questions']), 2)
        with self.assertRaises(q.NothingToDo):
            self.next()

    def test_a_runner_may_set_an_answer_only_with_a_facts_key(self):
        self.add(entry(1, questions=['Where are you located?']))
        ask = ('answer', 'seek-1', '--question', 'Where are you located?', '--set', 'Melton VIC 3337')
        self.assertEqual(self.cli(*ask)[0], 1)
        self.assertEqual(self.cli(*ask, '--by', 'grok', '--basis', 'identity.suburb')[0], 1)   # no such key
        code, out, _ = self.cli(*ask, '--by', 'grok', '--basis', 'identity.location')
        shown = json.loads(out)
        self.assertEqual((code, shown['status']), (0, 'OPEN'))
        self.assertEqual(shown['questions'][0]['by'], 'grok')
        self.assertEqual(json.loads(self.cli('answer', 'seek-1')[1])['questions'][0]['answer'], 'Melton VIC 3337')   # kept on recompute
        code, _, err = self.cli('answer', 'seek-1', '--question', 'Are you currently studying?', '--option', 'Yes', '--option', 'No',
                                '--set', 'Not at the moment', '--by', 'grok', '--basis', 'answers.currently_studying')
        self.assertEqual(code, 1)
        self.assertIn('must be one of the options', err)

    def test_finished_entries_are_not_changed(self):
        self.add(entry(1, questions=[RTW]))
        self.applied('seek-1', '2026-11-12T00:00:00Z')
        letter = self.file('letter.txt', 'New letter.')
        for args in (('answer', 'seek-1'), ('letter', 'seek-1', '--file', letter)):
            code, _, err = self.cli(*args)
            self.assertEqual(code, 1)
            self.assertIn('seek-1 is already APPLIED', err)
        self.add(entry(2))
        self.assertEqual(self.cli('answer', 'seek-2', '--option', 'Yes')[0], 1)   # options belong to a question

    def test_an_owner_question_put_there_for_another_reason_stays(self):
        self.add(entry(1, status='ASK_OWNER', ask_owner='Would you enrol in an Associate Degree for this cadetship?', questions=[RTW]))
        self.assertEqual(json.loads(self.cli('answer', 'seek-1')[1])['status'], 'ASK_OWNER')
        self.assertEqual(q.find(self.dir, 'seek-1')[1]['ask_owner'], 'Would you enrol in an Associate Degree for this cadetship?')


class ReportTests(QueueCase):
    def build(self):
        self.add(entry(1, company='Mendi | Constructions', lane='technician', location='Townsville, Northern QLD', closes_at='2026-11-18', closes_source='listing_expiry'))
        self.add(entry(2, closes_at='2026-11-25', closes_source='advert'))
        self.add(entry(3, lane='engineer', questions=['How would you rate your English language skills?']))
        self.add(email_entry(4, company='Core Environmental Projects'))
        self.add(email_entry(5, route='EMPLOYER_PORTAL', status='ASK_OWNER', ask_owner='Are you eligible for Engineers Australia membership?'))
        self.add(entry(6))
        self.add(entry(7))
        self.add(entry(8, closes_at='2026-11-01', closes_source='advert'))
        self.applied('seek-6', '2026-11-12T23:00:00Z')
        self.applied('seek-7', '2026-11-01T00:00:00Z')
        q.expire(self.dir, now=NOW)

    def test_render(self):
        self.build()
        code, out, _ = self.cli('render')
        self.assertEqual((code, out.strip()), (0, str(self.dir / 'APPLY_QUEUE.md')))
        text = (self.dir / 'APPLY_QUEUE.md').read_text(encoding='utf-8')
        heads = [line for line in text.splitlines() if line.startswith('## ')]
        self.assertEqual(heads, ['## SEEK (2 open)', '## EMAIL (1 open)', '## EMPLOYER_PORTAL (0 open)', '## EMPLOYER_FORM (0 open)', '## Waiting on the owner (2)'])
        self.assertIn('| # | Lane | Company | Role | Location | Closes | Link | Note |', text)
        self.assertIn('| 1 | drafter | Acme 2 | Junior Civil Drafter | Melton VIC | 2026-11-25 (advert) | [seek-2](https://www.seek.com.au/job/2) |  |', text)
        self.assertIn('| 2 | technician | Mendi / Constructions | Junior Civil Drafter | Townsville, Northern QLD | 2026-11-18 (listing expiry) | [seek-1](https://www.seek.com.au/job/1) |  |', text)
        self.assertIn('| 1 | drafter | Core Environmental Projects | Junior Civil Drafter | Melton VIC | not stated |', text)
        self.assertIn('Nothing open.', text)
        self.assertIn('- **Acme 5, Junior Civil Drafter** (EMPLOYER_PORTAL, drafter, closes not stated, `acme-5-junior-civil-drafter-', text)
        self.assertIn('`): Are you eligible for Engineers Australia membership?', text)
        self.assertIn('No standing answer for this form question: How would you rate your English language skills?', text)
        self.assertNotIn('Acme 6', text)   # applied
        self.assertNotIn('Acme 8', text)   # expired
        self.assertEqual(text, (self.cli('render'), (self.dir / 'APPLY_QUEUE.md').read_text(encoding='utf-8'))[1])   # same input, same file

    def test_render_notes_what_holds_an_open_entry_back(self):
        self.add(entry(1, notes='letter written under the old rules: rewrite before use'))
        q.render(self.dir, CONFIG, NOW)
        self.assertIn('| letter to rewrite |', (self.dir / 'APPLY_QUEUE.md').read_text(encoding='utf-8'))

    def test_stats(self):
        self.build()
        code, out, _ = self.cli('stats', '--json')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {
            'queue_open': {'SEEK': 2, 'EMAIL': 1, 'EMPLOYER_PORTAL': 0, 'EMPLOYER_FORM': 0, 'total': 3},
            'applied_last_7_days': 1, 'applied_total': 2, 'expired_unsubmitted_total': 1, 'ask_owner_open': 2,
            'open_with_letter_to_rewrite': 0})
        self.assertIn('queue_open: SEEK 2, EMAIL 1, EMPLOYER_PORTAL 0, EMPLOYER_FORM 0, total 3', self.cli('stats')[1])

    def test_list(self):
        self.build()
        code, out, _ = self.cli('list')
        rows = out.strip().splitlines()
        self.assertEqual(len(rows), 5)   # open and waiting on the owner; not the finished ones
        self.assertTrue(rows[0].startswith('seek-2'), rows[0])
        self.assertEqual([e['id'] for e in json.loads(self.cli('list', '--route', 'SEEK', '--status', 'OPEN', '--json')[1])], ['seek-2', 'seek-1'])
        self.assertEqual(len(json.loads(self.cli('list', '--status', 'APPLIED', '--json')[1])), 2)
        self.assertEqual(len(json.loads(self.cli('list', '--all', '--json')[1])), 8)
        self.assertEqual(json.loads(self.cli('show', 'seek-2')[1])['company'], 'Acme 2')

    def test_check(self):
        self.build()
        code, out, _ = self.cli('check')
        self.assertEqual((code, out.strip()), (0, '8 entries, 0 problems'))
        path, e = q.find(self.dir, 'seek-2')
        e['status'], e['lane'] = 'SKIPPED', 'labourer'
        q.write_json(path, e)
        q.write_json(self.dir / 'open' / 'copy.json', q.find(self.dir, 'seek-1')[1])
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        for msg in ('seek-2: lane: one of', 'seek-2: status SKIPPED does not belong in open/', 'seek-1: file name is not the id', 'seek-1: duplicate of copy.json (id:seek-1)'):
            self.assertIn(msg, out)


class HelperTests(unittest.TestCase):
    def test_times(self):
        self.assertEqual(q.melbourne_date('2026-11-12T13:30:00Z'), '2026-11-13')
        self.assertEqual(q.melbourne_date('2026-11-12T12:30:00Z'), '2026-11-12')
        self.assertEqual(q.iso(q.parse_time('2026-11-13T10:05')), '2026-11-12T23:05:00Z')   # no offset means Melbourne time
        self.assertEqual(q.iso(q.parse_time('2026-11-13T10:05:00+10:00')), '2026-11-13T00:05:00Z')
        with self.assertRaises(q.Refused):
            q.parse_time('13 Nov 2026')

    def test_urls_and_job_keys(self):
        self.assertEqual(q.norm_url('https://au.seek.com/job/95347045?tracking=SHR'), 'seek:95347045')
        self.assertEqual(q.norm_url('https://www.seek.com.au/job/95347045'), 'seek:95347045')
        self.assertEqual(q.norm_url('HTTPS://www.BPD.com.au/careers/#team'), 'bpd.com.au/careers')
        self.assertEqual(q.job_key({'company': 'Fyfe Pty Ltd', 'role': 'Graduate Civil Engineer'}), q.job_key({'company': 'Fyfe', 'role': 'graduate civil engineer'}))
        self.assertNotEqual(q.job_key({'company': 'BMD', 'role': 'Site Engineer'}), q.job_key({'company': 'BMD', 'role': 'Civil Site Engineer'}))

    def test_fact_at(self):
        self.assertEqual(q.fact_at(FACTS, 'answers.notice_period'), '2 weeks')
        self.assertEqual(q.fact_at(FACTS, 'answers.software.Microsoft Office')[:3], 'Yes')
        self.assertIn('11 months', q.fact_at(FACTS, 'answers.years_of_experience.civil engineer, site engineer, project engineer, construction industry'))
        for missing in ('answers.shoe_size', 'answers.notice_period.more', '', 'nothing'):
            self.assertIsNone(q.fact_at(FACTS, missing) if missing else None)


def row(**kw):
    r = {'company': 'Acme Civil', 'role': 'Junior Civil Drafter', 'location': 'Perth WA', 'url': 'https://www.seek.com.au/job/900', 'seek_id': 900,
         'status': 'READY_JEREMIE_SEEK', 'route': 'SEEK', 'fit_percent': 70, 'listed_date': '2026-11-01', 'effective_close_date': '2026-12-01',
         'apply_email': '', 'run_id': '20261101T0000Z', 'draft_files': [], 'source_file': '', 'recorded_rejection_same_employer': []}
    r.update(kw)
    return r


class ImportBacklogTests(unittest.TestCase):
    def test_excluded_families_by_title(self):
        for title, family in (('Assistant Estimator', 'estimator'), ('Graduate Estimator', 'estimator'), ('Project Coordinator, Civil Construction', 'project coordinator'),
                              ('Document Controller', 'document control'), ('BMD Graduate Program 2027 (Foundations)', 'graduate programs'),
                              ('Graduate Engineer (2027 Graduate Program)', 'graduate programs'), ('Graduate Civil Engineer Program (Expression of Interest)', 'graduate programs'),
                              ('Graduate/Undergraduate – Project Management', 'student, intern, vacation or undergraduate roles'),
                              ('Site Administrator', 'site or project administration'), ('Contracts Administrator', 'contract administrator'),
                              ('Traffic Controller', 'traffic controller'), ('Survey Assistant', 'survey assistant or chainperson'), ('Civil Labourer', 'labourer')):
            self.assertEqual(imp.excluded_family(title), family, title)
        for title in ('Graduate Civil Engineer', 'Junior Project Engineer - Traffic', 'Civil Engineering Technician', 'Trainee Civil Drafter', 'Cadet Designer'):
            self.assertIsNone(imp.excluded_family(title), title)

    def test_lane_from_title(self):
        for title, lane in (('Junior Civil Draftsperson', 'drafter'), ('Civil Design Drafter, Formwork', 'drafter'), ('Cadet Designer', 'drafter'),
                            ('Speculative enquiry: graduate civil engineer or civil designer', 'drafter'),
                            ('Construction Materials Testing Technician, Entry-Level', 'technician'), ('Civil Engineering Technician', 'technician'),
                            ('Graduate Design Engineer (Hydraulic/Civil)', 'engineer'), ('Civil Engineer / Graduate', 'engineer'),
                            ('Site Engineer (Site or Graduate Engineer)', 'engineer'), ('Junior Project Engineer - Traffic', 'engineer'),
                            # the advert has to be read for these: no lane from the title alone
                            ('Site Engineer', None), ('Project Engineer, Civil', None), ('Roads Engineer', None), ('Civil Engineer', None),
                            ('Junior Project Manager', None), ('Civil Works Project Officer', None), ('Quality Assurance Trainee, Civil Construction', None)):
            self.assertEqual(imp.lane_from_title(title), lane, title)

    def test_old_statuses_map_to_routes(self):
        self.assertEqual(imp.route_for(row(), None), 'SEEK')
        self.assertEqual(imp.route_for(row(status='READY_SEEK'), {'is_link_out': False}), 'SEEK')
        self.assertEqual(imp.route_for(row(), {'is_link_out': True}), 'EMPLOYER_PORTAL')   # SEEK advert that links out
        self.assertEqual(imp.route_for(row(status='READY_JEREMIE_EMPLOYER_PORTAL', route='SEEK link-out to the council careers portal'), None), 'EMPLOYER_PORTAL')
        self.assertEqual(imp.route_for(row(status='READY_JEREMIE_JOBSNEXT', route='EMPLOYER_PORTAL', seek_id=None), None), 'EMPLOYER_PORTAL')
        self.assertEqual(imp.route_for(row(status='PREPARED_NOT_SENT', route='EMAIL'), None), 'EMAIL')
        self.assertEqual(imp.route_for(row(status='PREPARED_NOT_SENT', route='EMPLOYER_FORM', seek_id=None), None), 'EMPLOYER_FORM')
        self.assertEqual(imp.route_for(row(status='HELD_MANDATORY_UNRESOLVED', route='SEEK'), None), 'SEEK')
        self.assertEqual(imp.route_for(row(status='HELD_MANDATORY_UNRESOLVED', route='EMPLOYER_PORTAL', seek_id=None), None), 'EMPLOYER_PORTAL')

    def test_closing_date_and_its_source(self):
        self.assertEqual(imp.closing(row(), None), ('2026-12-01', 'listing_expiry'))   # 30 days after listing on SEEK
        self.assertEqual(imp.closing(row(effective_close_date='2026-11-22'), None), ('2026-11-22', 'advert'))   # the advertiser set an earlier end
        self.assertEqual(imp.closing(row(seek_id=None, effective_close_date='2026-11-16'), None), ('2026-11-16', 'advert'))
        self.assertEqual(imp.closing(row(effective_close_date=None), None), ('', 'none'))
        for text, day in (('Applications close at 9.00am on Monday, 16 November 2026.', '2026-11-16'), ('Closing Date: 9am, Wednesday 25 November 2026.', '2026-11-25'),
                          ('Applications close Friday, 27th November 2026.', '2026-11-27'), ('Application Close Date: Wednesday, 25 November 2026 at 11.30pm AEST', '2026-11-25')):
            self.assertEqual(imp.closing(row(), {'content_text': 'About the role\n' + text}), (day, 'advert'), text)
        self.assertEqual(imp.closing(row(), {'content_text': 'We may close the advert early. Founded in March 2019.'}), ('2026-12-01', 'listing_expiry'))

    def test_relocation_line_only_outside_daily_travel_of_melton(self):
        for near in ('Werribee, Melbourne VIC', 'Norlane, Geelong VIC', 'Ballarat VIC', 'Melton VIC', 'Southbank VIC', 'Officer VIC', 'VIC 3094 (Montmorency, north east Melbourne) VIC'):
            self.assertEqual(imp.relocation_line(near), '', near)
        for far, place in (('Townsville, Northern QLD', 'Townsville'), ('Plumpton, Sydney NSW', 'Sydney'), ('Perth WA', 'Perth'), ('Port Adelaide, Adelaide SA', 'Adelaide'),
                           ('Henderson WA (Perth)', 'Henderson'), ('Toowoomba, Toowoomba & Darling Downs QLD', 'Toowoomba'), ('Griffith NSW', 'Griffith'),
                           ('Wagga Wagga / Forbes, NSW', 'Wagga Wagga or Forbes'), ('Lismore or Casuarina, Northern Rivers NSW', 'Lismore or Casuarina'),
                           ('Gympie QLD (Gympie and Sunshine Coast region)', 'Gympie'), ('Trafalgar, West Gippsland VIC', 'Trafalgar')):
            self.assertEqual(imp.relocation_line(far), f'I will relocate to {place} for this role and can start two weeks after an offer.', far)

    def test_decide(self):
        today = '2026-11-13'
        reason = lambda r, advert=None: (imp.decide(r, advert, today)[2] or (None,))[0]
        self.assertEqual(imp.decide(row(), None, today)[::2], ('drafter', None))
        self.assertEqual(reason(row(recorded_rejection_same_employer=[{'company': 'Australian Ground Technologies', 'date': '2026-10-17'}])), 'employer_rejected_him')
        self.assertEqual(reason(row(effective_close_date='2026-11-12')), 'closed')
        self.assertIsNone(reason(row(effective_close_date='2026-11-13')))   # closes today: kept
        self.assertEqual(reason(row(), {'content_text': 'Applications close: Wednesday 11th November 2026 at 11:30pm.'}), 'closed')
        self.assertEqual(reason(row(url='')), 'no_advert_in_repo')
        self.assertEqual(reason(row(role='Graduate Estimator')), 'excluded_family')
        self.assertEqual(reason(row(role='Site Engineer')), 'no_lane')
        self.assertEqual(reason(row(seek_id=95606153, role='Civil Engineering Assistant')), 'mandatory_unmet')   # read and recorded in DECISIONS
        self.assertEqual(imp.decide(row(seek_id=95347045, role='Quality Assurance Trainee, Civil Construction'), None, today)[0], 'technician')

    def test_build_entry(self):
        r = row(seek_id=901, url='https://www.seek.com.au/job/901')
        e = q.fill(imp.build_entry(r, {'screening_questions': [RTW], 'is_link_out': False}, {'why': 'read the advert', 'ask': ''}, 'drafter', '2026-11-13', '2026-11-13T00:40:00Z'))
        self.assertEqual((e['id'], e['route'], e['lane'], e['resume_variant'], e['status'], e['fit']), ('seek-901', 'SEEK', 'drafter', 'drafter', 'OPEN', 70))
        self.assertEqual(e['relocation_line'], 'I will relocate to Perth for this role and can start two weeks after an offer.')
        self.assertEqual(e['notes'].splitlines()[0], 'letter written under the old rules: rewrite before use')
        self.assertIn('(old status READY_SEEK)', e['notes'])   # the legacy READY_JEREMIE_SEEK under its current name
        self.assertIn('No letter text was in the repo', e['notes'])
        self.assertEqual([x['question'] for x in e['questions']], [RTW])
        self.assertEqual(q.validate(e, FACTS), [])
        asked = imp.build_entry(r, None, {'ask': 'Would you enrol?'}, 'drafter', '2026-11-13', '2026-11-13T00:40:00Z')
        self.assertEqual((asked['status'], asked['ask_owner']), ('ASK_OWNER', 'Would you enrol?'))

    @unittest.skipUnless(imp.SOURCE.exists() and imp.REPORT.exists() and (SCRIPTS.parent / 'runs').is_dir(),
                         'the import source, its report or automation/runs is no longer in the repo')
    def test_the_import_of_13_nov_2026_can_be_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = imp.run('2026-11-13', '2026-11-13T00:40:00Z', qdir=tmp)
            entries = [e for _, e in q.load(tmp)]
        self.assertEqual((report['source_rows'], report['imported'] + report['rejected_total']), (63, 63))
        self.assertEqual(len(entries), report['imported'])
        facts = q.read_json(SCRIPTS.parent / 'facts.json')
        for e in entries:
            self.assertEqual(q.validate(e, facts), [], e['id'])
            self.assertIn(imp.OLD_RULES, e['notes'], e['id'])
            self.assertIn(e['status'], ('OPEN', 'ASK_OWNER'))
            self.assertIsNone(imp.excluded_family(e['role']), e['id'])
            self.assertFalse(e['closes_at'] and e['closes_at'] < '2026-11-13', e['id'])
            self.assertEqual(e['status'] == 'ASK_OWNER', bool(e['ask_owner']), e['id'])
            self.assertTrue(e['status'] == 'ASK_OWNER' or not q.unanswered(e), e['id'])
        self.assertEqual(len({q.job_key(e) for e in entries}), len(entries))   # no duplicates
        self.assertFalse([e for e in entries if 'ground technologies' in e['company'].lower()])
        saved = q.read_json(imp.REPORT)   # the report committed with the import: same finds kept, same finds dropped
        self.assertEqual([(e['id'], e['lane'], e['route'], e['closes_at']) for e in saved['entries']],
                         [(e['id'], e['lane'], e['route'], e['closes_at']) for e in report['entries']])
        self.assertEqual(saved['rejected'], report['rejected'])
        with tempfile.TemporaryDirectory() as tmp:   # refuses to run into a queue that already has entries
            q.add(entry(1), tmp, FACTS, NOW)
            with self.assertRaises(SystemExit):
                imp.run('2026-11-13', '2026-11-13T00:40:00Z', qdir=tmp)


if __name__ == '__main__':
    unittest.main()
