"""The one answer gate (automation/scripts/answers.py) and what queue.py and checks.py do with it. Offline."""
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import checks  # noqa: E402
import common  # noqa: E402

try:
    import answers  # noqa: E402
except ImportError:   # the gate did not exist before 14 Nov 2026: every gate test then fails, as it should
    answers = None
_spec = importlib.util.spec_from_file_location('apply_queue_for_answers', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)

FACTS = json.loads((SCRIPTS.parent / 'facts.json').read_text(encoding='utf-8'))
TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 13, 1, 0, tzinfo=timezone.utc)
RTW = 'Which of the following statements best describes your right to work in Australia?'
RIGHT_TO_WORK = ["I'm an Australian citizen", "I'm a permanent resident and/or NZ citizen",
                 'I have a family/partner visa with no restrictions', 'I have a graduate temporary work visa',
                 'I have a holiday temporary work visa', 'I have a temporary visa with restrictions on industry (e.g. skilled work visa 482)',
                 'I have a temporary visa with no restrictions (e.g. doctoral student)',
                 'I have a temporary visa with restrictions on work hours (e.g. student visa, retirement visa)',
                 'I require sponsorship to work for a new employer (e.g. 482, 457)']
YEARS = ['No experience', 'Less than 1 year', '1 year', '2 years', '3 years', '4 years', '5 years', 'More than 5 years']
NOTICE = ["None, I'm ready to go now", 'Less than 2 weeks', '2 weeks', '1 month', '2 months', '3 months', 'More than 3 months']
YES_NO = ['Yes', 'No']
POLICE = 'Do you have a current Police Check (National Police Certificate) for employment?'
GOOD_LETTER = ('Hello,\n\n'
               'I am applying for the Junior Civil Drafter role advertised on SEEK. Your advert asks for subdivision drawings in Civil 3D.\n\n'
               'In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks and '
               'stormwater drainage in AutoCAD and Civil 3D to Australian Standards.\n\n'
               'I live in Melton and can start two weeks after an offer. Full working rights in Australia (Subclass 485 visa), no '
               'sponsorship needed. Could we talk this week?\n\n'
               'Marc Masarate')


def gate(question, options=None, facts=FACTS, **kw):
    if answers is None:
        raise AssertionError('automation/scripts/answers.py (the one answer gate) is missing')
    return answers.answer(question, options or [], facts, today=kw.pop('today', TODAY), **kw)


def run_questions():
    """Every distinct form question text in automation/runs/*/candidates*.json."""
    seen = set()
    for path in (SCRIPTS.parent / 'runs').glob('*/candidates*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            continue
        for cand in (data.get('candidates') if isinstance(data, dict) else None) or []:
            seen.update(' '.join(x.split()) for x in cand.get('screening_questions') or [] if isinstance(x, str) and x.strip())
    return sorted(seen)


class GateCase(unittest.TestCase):
    def ok(self, result, answer, basis=None):
        self.assertEqual((result['status'], result['answer']), ('answered', answer), result)
        if basis:
            self.assertEqual(result['basis'], basis)
        self.assertEqual(result['why'], '')

    def no(self, result):
        self.assertEqual((result['status'], result['answer']), ('unanswered', ''), result)
        self.assertTrue(result['why'], result)


class WorkRightsAndSponsorship(GateCase):
    def test_the_graduate_visa_option_or_the_unrestricted_temporary_one_never_citizen_or_sponsorship(self):
        self.ok(gate(RTW, RIGHT_TO_WORK), 'I have a graduate temporary work visa', 'answers.right_to_work.choose')
        self.ok(gate(RTW, [o for o in RIGHT_TO_WORK if 'graduate' not in o]), 'I have a temporary visa with no restrictions (e.g. doctoral student)')
        self.ok(gate(RTW, ['Australian citizen', 'Subclass 485 Temporary Graduate visa', 'Other']), 'Subclass 485 Temporary Graduate visa')
        for options in ([RIGHT_TO_WORK[0], RIGHT_TO_WORK[1], RIGHT_TO_WORK[-1]], ['Graduate visa 485, sponsorship required later', "I'm an Australian citizen"],
                        ['I have a family/partner visa with no restrictions', "I'm an Australian citizen"], YES_NO):
            self.no(gate(RTW, options))
        self.ok(gate(RTW), FACTS['answers']['right_to_work']['free_text'], 'answers.right_to_work.free_text')
        self.ok(gate('Are you legally entitled to work in Australia?'), FACTS['answers']['right_to_work']['free_text'])
        self.no(gate('Are you legally entitled to work in Australia?', YES_NO))   # facts.json gives no plain yes for it

    def test_sponsorship_now_is_no_and_in_the_future_goes_to_the_owner(self):
        self.ok(gate('Do you require sponsorship to work in Australia now?', YES_NO), 'No', 'answers.future_visa_sponsorship')
        self.ok(gate('Do you require sponsorship to work in Australia?'), 'No')
        for text in ('Will you require visa sponsorship in the future?', 'Do you now or will you in the future require sponsorship?'):
            self.no(gate(text, YES_NO))
            self.no(gate(text))


class NoticeStartAndSalary(GateCase):
    def test_notice_is_two_weeks_or_the_option_meaning_two_weeks(self):
        text = 'How much notice are you required to give your current employer?'
        self.ok(gate(text, NOTICE), '2 weeks', 'answers.notice_period')
        self.ok(gate(text, ['Immediately', 'Two weeks', 'One month']), 'Two weeks')
        self.ok(gate(text), '2 weeks')
        self.no(gate(text, ['None', 'Less than 2 weeks', '1 month']))   # never the nearest option

    def test_start_date_is_free_text_two_weeks_after_an_offer(self):
        for text in ('What is your estimated start date?', 'Availability to start', 'When can you commence in a full time capacity?'):
            self.ok(gate(text), 'Two weeks after an offer', 'eligibility.availability')
        self.no(gate('Are you available to start work on 27 January 2027?'))

    def test_salary_with_options_is_the_option_holding_the_band_or_the_advertised_figure(self):  # S13
        text = "What's your expected annual base salary?"
        self.ok(gate(text, ['$50k', '$60k', '$70k', '$80k', '$90k']), '$70k', 'answers.expected_salary.rule')
        self.ok(gate(text, ['$40k - $60k', '$60k - $80k', '$80k - $100k']), '$60k - $80k')
        self.no(gate(text, ['$60k-$70k', '$70k-$80k']))           # $70,000 is in both: not decided
        self.no(gate(text, ['$80k', '$90k', '$100k']))             # no option holds the band: the owner's
        self.no(gate(text, ['$60k + super', '$70k + super', '$80k + super']))   # a package, not the base salary on record
        self.ok(gate(text, ['$60k-$75k', '$75k-$90k', '$90k-$105k'], pay='$80,000 to $95,000 plus super'), '$75k-$90k')
        self.no(gate(text, ['$60k', '$70k'], pay='$80,000 to $95,000 plus super'))
        self.no(gate(text, ['$60k', '$70k'], pay='$35 to $40 per hour'))
        for result in (gate(text, ['$50k', '$60k', '$70k']), gate(text, ['$40k - $60k', '$60k - $80k'])):
            self.assertNotIn('If the advert states pay', result['answer'])   # never the rule paragraph where options are shown

    def test_salary_free_text_follows_the_rule_and_the_other_pay_questions_go_to_the_owner(self):
        self.ok(gate("What's your expected annual base salary?"), '65000 to 75000')
        self.ok(gate('Salary Expectations (in AUD)'), '65000 to 75000')
        self.ok(gate("What's your expected annual base salary?", pay='$80,000 to $95,000 plus super'), '80000')
        for text in ("What's your expected hourly rate?", 'Please provide your salary or hourly rate expectations:',
                     'Please detail your minimum salary expectations (including super):',
                     'The Salary for this position is $60-65k plus superannuation. Please confirm this salary is inline with your expectations'):
            self.no(gate(text))


class LicenceCarAndChecks(GateCase):
    def test_drivers_licence(self):
        text = "Do you have a current Australian driver's licence?"
        self.ok(gate(text, YES_NO), 'Yes', 'answers.drivers_licence')
        self.ok(gate(text), 'Yes')
        self.ok(gate("Do you hold a full driver's licence?", YES_NO), 'Yes')
        self.ok(gate(text, ['Yes, full licence', 'Yes, probationary licence', 'No']), 'Yes, full licence')
        self.ok(gate(text, ['Yes - manual', 'Yes - automatic', 'No']), 'Yes - automatic')
        self.ok(gate('Are you licenced to drive a manual vehicle?', YES_NO), 'No', 'answers.manual_licence')
        self.ok(gate("Is your driver's licence manual or automatic?"), 'Automatic')
        for other in ('Do you have a valid WA drivers licence?', "Do you hold a current Queensland driver's licence?", "Do you have a heavy vehicle driver's licence?"):
            self.no(gate(other, YES_NO))

    def test_car_white_card_medical_and_drug_tests_studying_relocation_travel(self):
        for text, answer in (('Do you own or have regular access to a car?', 'Yes'),
                             ('Do you hold a Construction Induction Safety certificate (White Card)?', 'Yes'),
                             ('Do you hold a current White Card / General Construction Induction Training Card?', 'Yes'),
                             ('Are you willing to undergo a pre-employment medical check?', 'Yes'),
                             ('Are you willing to undergo pre-employment drug and alcohol screening?', 'Yes'),
                             ('Are you willing to undergo pre-employment medical incl. drug and alcohol screening?', 'Yes'),
                             ('Are you currently studying?', 'No'),
                             ('Are you willing to relocate for this role?', 'Yes'),
                             ('Are you available to work FIFO / DIDO contracts?', 'Yes')):
            self.ok(gate(text, YES_NO), answer)
            self.no(gate(text, ['Maybe', 'Unsure']))
        self.ok(gate('Are you willing to relocate for this role?'), 'Yes, anywhere in Australia', 'answers.willing_to_relocate')
        for text in ('Do you have experience in a FIFO/DIDO role?', 'How far are you willing to travel for work?', 'Would you relocate to New Zealand?',
                     'Do you have a current Category 3 Rail Medical Clearance?', 'Is there any reason you could not pass a pre-employment medical?'):
            self.no(gate(text, YES_NO))

    def test_a_police_check_for_employment_or_a_recent_one_is_no(self):  # S1, P8
        self.ok(gate(POLICE, YES_NO), 'No', 'answers.police_check')
        self.ok(gate(POLICE), 'No. Willing to obtain a new check.')
        self.ok(gate('Do you hold a police check issued within the last 6 months?', YES_NO), 'No')
        self.ok(gate('Do you have a current police check?', YES_NO), 'Yes')
        self.ok(gate('Do you have a current police check?'), 'Yes (AFP National Police Check certificate, March 2026)')
        self.ok(gate('Are you willing to complete a Police Check?', YES_NO), 'Yes')
        self.ok(gate('Are you willing to undertake Criminal History Screening?', YES_NO), 'Yes')
        self.no(gate('Are you able to obtain a National Police Check and other related security clearances required for this role?', YES_NO))
        self.no(gate('Do you have a criminal record?', YES_NO))

    def test_from_the_month_facts_json_names_a_current_check_is_no(self):
        self.ok(gate('Do you have a current police check?', YES_NO, today=date(2027, 2, 28)), 'Yes')
        self.ok(gate('Do you have a current police check?', YES_NO, today=date(2027, 3, 1)), 'No')
        self.ok(gate('Do you have a current police check?', today=date(2027, 3, 1)), 'No, willing to obtain one')

    def test_a_police_line_that_says_nothing_about_employment_leaves_that_question_open(self):
        older = copy.deepcopy(FACTS)
        older['answers']['police_check'] = 'Yes, current National Police Certificate'
        self.no(gate(POLICE, YES_NO, older))
        self.no(gate('Are you willing to complete a Police Check?', YES_NO, older))
        self.ok(gate('Do you have a current police check?', YES_NO, older), 'Yes')


class QualificationsYearsSoftware(GateCase):
    def test_qualification_questions(self):
        base = 'Have you completed a qualification in {}?'
        self.ok(gate(base.format('civil engineering'), YES_NO), 'Yes', 'answers.qualification_questions.civil engineering')
        self.ok(gate(base.format('civil engineering')), 'Yes: Bachelor of Science in Civil Engineering (2019)')
        self.ok(gate(base.format('engineering drafting / engineering design'), YES_NO), 'Yes')
        self.ok(gate(base.format('carpentry'), YES_NO), 'No', 'answers.qualification_questions.any other named qualification')
        for field in ('construction management', 'structural engineering', 'science', 'civil engineering in Australia'):
            self.no(gate(base.format(field), YES_NO))
        self.ok(gate("Do you hold a Bachelor's degree in civil engineering or an equivalent qualification?", YES_NO), 'Yes')
        self.no(gate('Have you completed a Bachelor of Engineering that is accredited by Engineers Australia?', YES_NO))
        self.ok(gate('What qualifications do you currently hold?'),
                'Advanced Diploma of Civil Construction Design, 2026; Bachelor of Science in Civil Engineering (BSCE), 2019', 'education')
        self.no(gate('What qualifications do you currently hold?', ['Diploma', 'Bachelor degree']))

    def test_years_engineering_titles_eleven_months_other_roles_lowest(self):
        worked = 'answers.years_of_experience.civil engineer, site engineer, project engineer, construction industry'
        for role in ('a civil engineer', 'a Civil Site Engineer', 'an Engineer Graduate', 'a Construction Engineer', 'an Assistant Civil Engineer'):
            text = f"How many years' experience do you have as {role}?"
            self.ok(gate(text, YEARS), 'Less than 1 year', worked)
            self.ok(gate(text), 'Less than 1 year (11 months, April 2019 to February 2020)')
        self.ok(gate("How many years' experience do you have in the construction industry?", ['0-1 years', '1-2 years', '3+ years']), '0-1 years')
        for role in ('a Rail Project Engineer', 'a Structural Site Engineer', 'a Senior Site Engineer', 'a Site Engineer / Estimator', 'a design engineer'):
            self.no(gate(f"How many years' experience do you have as {role}?", YEARS))   # the facts never cover these engineering titles
        self.ok(gate("How many years' experience do you have as a civil drafter?", YEARS), 'No experience', 'answers.years_of_experience.drafter, draftsperson, designer, CAD')
        self.ok(gate("How many years' experience do you have as a civil drafter?", YEARS[1:]), 'Less than 1 year')
        self.ok(gate("How many years' experience do you have as an Estimator?", YEARS), 'No experience')
        self.ok(gate("How many years' experience do you have as a Quality Assurance Trainee?", YEARS), 'No experience')
        self.no(gate("How many years' experience do you have as a civil drafter?", ['None', 'Some', 'Lots']))   # options that cannot be read
        self.no(gate("How many years' experience do you have as a civil drafter?", ['1 year', '2 years']))   # the lowest still claims a year
        self.no(gate("How many years' experience do you have as a civil engineer?", ['1 year', '2 years', '3 or more years']))
        for text in ('How many years of estimating experience do you have?', "How many years' experience do you have in your current occupation?",
                     'How many years of experience do you have in civil construction?', "How many years' experience do you have as a Console Operator?",
                     "How many years' experience do you have as an Engineering Team Leader?"):
            self.no(gate(text, YEARS))

    def test_software(self):
        cad = 'Which of the following CAD software do you have experience with?'
        self.ok(gate(cad, ['AutoCAD', 'Revit', 'MicroStation', '12D', 'AutoCAD Civil 3D', 'Tekla', 'None of these']), 'AutoCAD; Revit; AutoCAD Civil 3D', 'answers.software.CAD')
        self.ok(gate(cad), 'AutoCAD, Civil 3D, Revit')
        self.no(gate(cad, ['12D', 'MicroStation', 'None of these']))
        self.no(gate('Which of the following Microsoft Office products are you experienced with?', ['Word', 'Excel']))
        self.no(gate('Which of the following data visualisation tools are you experienced with?'))
        self.ok(gate('Do you have experience using AutoCAD Civil 3D?', YES_NO), 'Yes')
        self.ok(gate('Do you have experience using AutoCAD 2D/3D?', YES_NO), 'Yes')
        self.ok(gate('Do you have any experience using Revit or AutoCAD?', YES_NO), 'Yes')
        self.ok(gate('Do you have experience using Bluebeam?', YES_NO), 'No')
        self.no(gate('Do you have any experience using Revit, AutoCAD, 12D?', YES_NO))   # his tools and another together
        self.no(gate('Do you have experience using Microsoft Excel?', YES_NO))

    def test_experience_lines_as_facts_say_otherwise_unanswered(self):
        self.ok(gate('Do you have Engineering Drawing Interpretation experience?', YES_NO), 'Yes', 'answers.experience_yes_no.engineering drawing interpretation')
        self.ok(gate('Do you have experience preparing and submitting tenders?', YES_NO), 'No')
        for text in ('Do you have experience working on civil infrastructure projects?', 'Do you have mine site experience?', 'Do you have customer service experience?'):
            self.no(gate(text, YES_NO))


class DeclarationsAndTheRest(GateCase):
    def test_declarations(self):
        for text in ('I acknowledge that all information I provided in this application is true and correct to the best of my knowledge and that any '
                     'incorrect or misleading information may lead to disqualification, or if appointed, to termination of Employment?',
                     'Do you agree with the privacy policy?', 'Do you consent to us conducting reference checks?',
                     'Certain roles require a criminal history check to be performed as part of the recruitment process for shortlisted candidates. '
                     'Please acknowledge that you are aware of this and are willing to participate if needed.'):
            self.ok(gate(text, ['Yes', 'No']), 'Yes', 'answers.declarations_and_consents')
            self.ok(gate(text), 'Yes')
        self.ok(gate('Do you agree with the privacy policy?', ['I agree', 'I do not agree']), 'I agree')
        for text in ('When the time comes, do you consent to a mandatory pre-employment police check and medical check?',
                     'I consent to my details being shared with third parties for marketing.', 'I declare that I have no criminal convictions.'):
            self.no(gate(text, YES_NO))

    def test_referees_location_english_engineers_australia(self):
        self.ok(gate('Please provide two referees'), 'Available on request', 'answers.referees')
        self.no(gate('Please provide two referees', ['Yes', 'No']))
        self.no(gate('If you have been referred by a past/current TTW Employee, please specify their full name.'))
        self.ok(gate('Where are you located?'), 'Melton VIC 3337', 'identity.location')
        self.ok(gate('What is your current location?'), 'Melton VIC 3337')
        self.no(gate('Where are you located?', ['Melbourne', 'Sydney']))
        self.no(gate('How would you rate your English language skills?', ['Fluent', 'Basic']))
        later = copy.deepcopy(FACTS)
        later['answers']['english_self_rating'] = 'Fluent'   # one line in facts.json settles it, with no code change
        self.ok(gate('How would you rate your English language skills?', ['Basic', 'Fluent'], later), 'Fluent')
        self.no(gate('Are you a current member of Engineers Australia?', YES_NO))
        self.no(gate('Are you registered as a Registered Professional Engineer of Queensland (RPEQ)?', YES_NO))

    def test_two_questions_at_once_private_details_and_unknown_questions_go_to_the_owner(self):
        for text in ("Do you hold a current Australian driver's licence and have reliable transport?",
                     'Where are you currently based, are you available to work a 9 days on, 5 days off roster in Moranbah, and what is your earliest available start date?',
                     'Have you completed (or are you completing) Year 12 in 2026? or enrolled in TAFE ?',
                     'What is your gender? Male Female', 'Do you have a current Working With Children (WWC) Check?', 'Preferred Name',
                     'What motivated you to apply for this position?', 'Anything else you\'d like to add to support your application? (e.g. notice period, relevant experience, etc.)',
                     '', None):
            self.no(gate(text))

    def test_an_answer_with_options_is_always_one_of_them_word_for_word(self):
        option_sets = [YES_NO, YEARS, NOTICE, RIGHT_TO_WORK, ['$50k', '$60k', '$70k', '$80k'], ['I agree', 'I do not agree'],
                       ['AutoCAD', 'Revit', '12D', 'Tekla'], ['Yes - manual', 'Yes - automatic', 'No']]
        for question in run_questions()[:250] + [RTW, POLICE]:
            for options in option_sets:
                r = gate(question, options)
                if r['status'] == 'answered':
                    self.assertTrue(all(part in options for part in r['answer'].split('; ')), (question, options, r))


class OneGate(unittest.TestCase):
    """S16 and F16: queue.py and checks.py gave different answers to 377 of the 661 run-folder questions."""

    def test_checks_and_queue_give_the_gates_answer_for_every_real_question(self):
        questions = run_questions()
        if not questions:
            self.skipTest('run folders are not in this checkout')
        differ = []
        for question in questions:
            mine = q.answer_question(question, [], common.FACTS)
            basis, line, problem = checks.standing_line(question)
            if (mine['status'] == 'answered') != (problem is None) or (problem is None and (mine['basis'], mine['answer']) != (basis, line)):
                differ.append(question)
        self.assertEqual(differ, [])

    def test_standing_answer_and_unanswered_questions_read_the_gate(self):
        self.assertEqual(checks.standing_answer('How much notice are you required to give your current employer?'), ('notice_period', None))
        key, problem = checks.standing_answer('How would you rate your English language skills?')
        self.assertEqual(key, 'english_self_rating')
        self.assertTrue(problem)
        self.assertEqual([u['question'] for u in checks.unanswered_questions([POLICE, 'How would you rate your English language skills?'])],
                         ['How would you rate your English language skills?'])
        self.assertEqual(checks.standing_line(POLICE), ('answers.police_check', 'No. Willing to obtain a new check.', None))

    def test_a_truthful_no_to_the_police_check_for_employment_passes_the_draft_check(self):  # S1: checks.py used to flag it
        self.assertEqual(checks.answer_issues(POLICE, 'No'), [])
        self.assertTrue(any('says yes where' in i for i in checks.answer_issues(POLICE, 'Yes')))


# ---------------------------------------------------------------------------------------------- the queue command
CONFIG = json.loads((SCRIPTS.parent / 'config.json').read_text(encoding='utf-8'))


def entry(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melton VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


class QueueAnswerCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.dir, self.config, self.facts, self.prior = root / 'queue', root / 'config.json', root / 'facts.json', root / 'prior.json'
        q.write_json(self.config, CONFIG)
        q.write_json(self.facts, FACTS)
        q.write_json(self.prior, {'entries': []})

    def cli(self, *args, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--prior', str(self.prior),
                               '--now', q.iso(now), *args])
            except SystemExit as stop:   # argparse refuses an option that does not exist
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def add(self, e):
        return q.add(e, self.dir, FACTS, NOW)

    def stored(self, entry_id='seek-1'):
        return q.find(self.dir, entry_id)[1]

    def test_set_and_basis_are_gone(self):  # S7: any yes-valued key let a runner put Yes on any question
        self.add(entry(1, questions=[RTW]))
        code, out, err = self.cli('answer', 'seek-1', '--question', 'Are you registered as a Registered Professional Engineer of Queensland (RPEQ)?',
                                  '--option', 'Yes', '--option', 'No', '--set', 'Yes', '--basis', 'answers.white_card', '--by', 'Claude')
        self.assertEqual(code, 2)
        self.assertIn('unrecognized arguments: --set', err)
        self.assertEqual([x['question'] for x in self.stored()['questions']], [RTW])

    def test_with_no_entry_it_prints_the_gates_answer_or_unanswered_and_exit_5(self):  # F9
        code, out, err = self.cli('answer', '--question', RTW, *[x for o in RIGHT_TO_WORK for x in ('--option', o)])
        self.assertEqual((code, out), (0, 'I have a graduate temporary work visa\n'))
        code, out, err = self.cli('answer', '--question', 'Do you have Traffic Control experience?', '--option', 'Yes', '--option', 'No')
        self.assertEqual((code, out), (5, ''))
        self.assertTrue(err.startswith('UNANSWERED: '), err)
        code, out, _ = self.cli('answer', '--question', "What's your expected annual base salary?", '--option', '$70k', '--option', '$90k',
                                '--advert-pay', '$90,000 to $100,000')
        self.assertEqual((code, out), (0, '$90k\n'))
        self.assertFalse((self.dir / 'open').exists())   # nothing is stored at screening

    def test_on_an_entry_an_answered_question_prints_the_option_to_choose(self):  # F23
        self.add(entry(1, questions=[RTW]))
        code, out, _ = self.cli('answer', 'seek-1', '--question', RTW, *[x for o in RIGHT_TO_WORK for x in ('--option', o)])
        self.assertEqual((code, out), (0, 'I have a graduate temporary work visa\n'))
        self.assertEqual(self.stored()['questions'][0]['options'], RIGHT_TO_WORK)
        self.assertEqual(self.stored()['status'], 'OPEN')

    def test_an_unanswered_question_on_an_entry_asks_the_owner_releases_the_start_and_exits_5(self):  # F10, F22
        self.add(entry(1, questions=[RTW]))
        self.assertEqual(q.next_entry('SEEK', self.dir, CONFIG, NOW, 'Grok', [], FACTS)['id'], 'seek-1')
        code, out, err = self.cli('answer', 'seek-1', '--question', 'Do you have Traffic Control experience?', '--option', 'Yes', '--option', 'No', '--by', 'Grok')
        self.assertEqual((code, out), (5, ''))
        self.assertIn('do not submit; leave the form', err)
        e = self.stored()
        self.assertEqual(e['status'], 'ASK_OWNER')
        self.assertIn('Do you have Traffic Control experience? (options: Yes / No)', e['ask_owner'])
        self.assertEqual((e['attempts'][-2]['result'], e['attempts'][-1]['result'], e['attempts'][-1]['by']), ('started', 'asked_owner', 'Grok'))
        self.assertNotIn('no result recorded', ' '.join(q.blockers(e, q.hold_context([e], CONFIG, NOW))))
        # the owner answers in facts.json; `answer ID` recomputes and the entry is OPEN again
        later = copy.deepcopy(FACTS)
        later['answers']['experience_yes_no']['traffic control'] = 'No'
        q.write_json(self.facts, later)
        code, out, _ = self.cli('answer', 'seek-1')
        self.assertEqual((code, json.loads(out)['status']), (0, 'OPEN'))
        self.assertEqual(self.stored()['questions'][1]['answer'], 'No')

    def test_mark_ask_about_a_form_question_keeps_it_reopenable(self):  # F10
        self.add(entry(1, questions=['Do you have Traffic Control experience?']))
        self.assertEqual(self.stored()['status'], 'ASK_OWNER')
        self.assertEqual(self.cli('mark', 'seek-1', 'ask', '--by', 'Grok', '--question', 'SEEK asks: Do you have Traffic Control experience? (Yes / No)')[0], 0)
        later = copy.deepcopy(FACTS)
        later['answers']['experience_yes_no']['traffic control'] = 'No'
        q.write_json(self.facts, later)
        code, out, _ = self.cli('answer', 'seek-1')
        self.assertEqual((code, json.loads(out)['status']), (0, 'OPEN'))
        # an ask about something else stays with the owner
        self.add(entry(2, questions=[RTW]))
        self.assertEqual(self.cli('mark', 'seek-2', 'ask', '--by', 'Grok', '--question', 'The advert wants citizens: apply anyway?')[0], 0)
        self.assertEqual(json.loads(self.cli('answer', 'seek-2')[1])['status'], 'ASK_OWNER')

    def test_recompute_with_a_question_still_open_exits_5(self):
        self.add(entry(1, questions=['How would you rate your English language skills?']))
        code, out, err = self.cli('answer', 'seek-1')
        self.assertEqual((code, json.loads(out)['status']), (5, 'ASK_OWNER'))
        self.assertIn('UNANSWERED', err)

    def test_next_works_the_answers_out_again_from_the_facts_of_now(self):  # S8
        self.add(entry(1, questions=['How much notice are you required to give your current employer?', 'Do you hold a Construction Induction Safety certificate (White Card)?']))
        changed = copy.deepcopy(FACTS)
        changed['answers']['notice_period'] = 'Not on record: skip and report.'
        q.write_json(self.facts, changed)
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual(code, 4)
        self.assertIn('unanswered question', err)
        self.assertEqual(self.stored()['status'], 'ASK_OWNER')
        q.write_json(self.facts, FACTS)   # back: the entry is handed out again
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual((code, json.loads(out)['id']), (0, 'seek-1'))

    def test_next_replaces_an_answer_stored_under_older_rules(self):  # S1 in the live queue: 'Yes' stored for the employment check
        self.add(entry(1, questions=[POLICE]))
        path, e = q.find(self.dir, 'seek-1')
        e['questions'][0].update(answer='Yes', basis='answers.police_check', status='answered')
        q.write_json(path, e)
        code, out, err = self.cli('next', '--route', 'SEEK')
        self.assertEqual(json.loads(out)['questions'][0]['answer'], 'No. Willing to obtain a new check.')
        self.assertIn(f'Q: {POLICE} | give: No. Willing to obtain a new check.', err)

    def test_next_prints_what_to_give_for_each_question(self):  # F23
        self.add(entry(1, questions=[RTW, 'How much notice are you required to give your current employer?']))
        code, out, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok')
        self.assertEqual(code, 0)
        self.assertEqual(err.splitlines(), [f"Q: {RTW} | give: {FACTS['answers']['right_to_work']['free_text']}",
                                            'Q: How much notice are you required to give your current employer? | give: 2 weeks'])


# ---------------------------------------------------------------------------------------------- one set of letter rules
class LetterAndEmailRules(unittest.TestCase):
    """F6 and S15: a greeting and a sign-off counted as paragraphs; next ignored banned phrases, dashes and visa dates."""

    def test_the_greeting_and_the_sign_off_are_not_paragraphs(self):
        self.assertEqual(checks.letter_issues(GOOD_LETTER), [])
        self.assertEqual(checks.letter_blocks(GOOD_LETTER)[0], 'Hello,')
        self.assertEqual(checks.letter_blocks(GOOD_LETTER)[2], ['Marc Masarate'])
        body = GOOD_LETTER.split('\n\n')[1:4]
        for text in ('Hello Aaron,\n' + '\n\n'.join(body) + '\nMarc Masarate',
                     '\n\n'.join(body) + '\n\nKind regards,\nMarc Darenz Masarate\n0478 764 077\nhttps://macdarenz-droid.github.io/Portfolio',
                     '\n'.join(body)):
            self.assertEqual(checks.letter_issues(text), [], text)
        self.assertTrue(any('has 2 paragraphs' in i for i in checks.letter_issues('Hello,\n\n' + '\n\n'.join(body[:2]) + '\n\nMarc Masarate')))
        self.assertTrue(any('has 4 paragraphs' in i for i in checks.letter_issues(GOOD_LETTER.replace('Could we', 'Thanks.\n\nCould we'))))
        self.assertEqual(checks.draft_issues({'cover_letter_text': GOOD_LETTER}), [])   # checks.py draft on a queue entry

    def test_queue_and_checks_apply_the_same_rules(self):
        cases = [GOOD_LETTER.replace('I am applying for', 'Please accept my application for'),
                 GOOD_LETTER.replace('to Australian Standards', 'to Australian Standards – quickly'),
                 GOOD_LETTER.replace('no sponsorship needed', 'no sponsorship needed until Dec 2027'),
                 GOOD_LETTER.replace('no sponsorship needed', 'no sponsorship needed, visa to 12/2027'),
                 GOOD_LETTER.replace('no sponsorship needed', 'no sponsorship needed until December 2027')]
        for text in cases:
            e = q.fill(entry(1, cover_letter_text=text))
            self.assertTrue(q.tone_problems(e, CONFIG), text)
            self.assertEqual(q.tone_problems(e, CONFIG), checks.letter_issues(text), text)
        self.assertEqual(q.tone_problems(q.fill(entry(1, cover_letter_text=GOOD_LETTER)), CONFIG), [])

    def test_an_email_entry_needs_its_letter_and_a_clean_subject(self):
        e = q.fill(entry(1, route='EMAIL', seek_id='', email={'to': 'jobs@acme.example', 'subject': 'Junior Drafter – application', 'body': 'Hello,\n\nShort note.\n\nMarc',
                                                                 'evidence_url': 'https://acme.example/careers'}))
        problems = q.tone_problems(e, CONFIG)
        self.assertIn('letter text missing (an email application attaches the cover letter)', problems)
        self.assertTrue(any(p.startswith('email subject banned character') for p in problems))
        self.assertEqual(checks.email_issues('Junior Drafter application, Marc Masarate', 'Hello,\n\nShort note.\n\nMarc'), [])

    def test_the_relocation_line_goes_into_the_last_paragraph_once(self):
        line = 'I will relocate to Geelong for this role and can start two weeks after an offer.'
        text = checks.compose_letter(GOOD_LETTER, line)
        greeting, paragraphs, sign_off = checks.letter_blocks(text)
        self.assertTrue(paragraphs[2].endswith(line))
        self.assertEqual((greeting, sign_off, len(paragraphs)), ('Hello,', ['Marc Masarate'], 3))
        self.assertEqual(checks.compose_letter(text, line), text)   # already there: not added twice


if __name__ == '__main__':
    unittest.main()
