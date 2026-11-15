"""15 Nov 2026: the owner's sponsorship decisions (docs/COACHING-DECISIONS.md D68, APPLY.md section 8). Offline.

1. Applications never mention sponsorship unless the employer asks: checks.py flags it in letters and emails ("no
   sponsorship needed" included); a form answer may name it only when its question asks about sponsorship or visas.
2. Asked: needs it now, No; now or in the future, Yes; free text, his own words (facts.json -> answers ->
   future_visa_sponsorship and sponsorship_free_text). Someone else's sponsorship or another country's: unanswered.
3. Ranking: within a lane, adverts that offer or consider sponsorship (one group), then jobs in regional areas (the
   Home Affairs designated regional areas for skilled visas: config.json -> regional_areas).

Each rule is tested with the cases it must still refuse.
"""
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import answers  # noqa: E402
import checks  # noqa: E402

_spec = importlib.util.spec_from_file_location('apply_queue_for_sponsorship', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)

ROOT = SCRIPTS.parent
FACTS = json.loads((ROOT / 'facts.json').read_text(encoding='utf-8'))
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
NOW = datetime(2026, 11, 15, 1, 0, tzinfo=timezone.utc)
YES_NO = ['Yes', 'No']
FREE = FACTS['answers']['sponsorship_free_text']
FREE_TEXT = FREE['text']
FUTURE_FREE_TEXT = FREE['future_prefix'] + ' ' + FREE['text']
LETTER = ('Hi Acme team,\n\n'
          "I'd like to apply for your Junior Civil Drafter role on SEEK. Your advert asks for subdivision drawings in Civil 3D.\n\n"
          'In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks and '
          'stormwater drainage in AutoCAD and Civil 3D to Australian Standards.\n\n'
          "I live in Melton and can start two weeks after an offer. I have full working rights in Australia (Subclass 485 visa). "
          'Happy to chat whenever suits you.\n\n'
          'Kind regards,\nMarc Masarate')


def gate(question, options=None, facts=FACTS):
    return answers.answer(question, options or [], facts)


class GateCase(unittest.TestCase):
    def ok(self, result, answer, basis=None):
        self.assertEqual((result['status'], result['answer']), ('answered', answer), result)
        if basis:
            self.assertEqual(result['basis'], basis)

    def no(self, result):
        self.assertEqual((result['status'], result['answer']), ('unanswered', ''), result)
        self.assertTrue(result['why'], result)


class SponsorshipNowIsNo(GateCase):
    def test_present_tense_questions_are_no(self):
        for text in ('Do you require sponsorship to work in Australia?', 'Do you currently require visa sponsorship?',
                     'Do you require sponsorship to start?', 'Do you need sponsorship to work for us?',
                     'Do you require sponsorship to work in Australia now?', 'Are you currently in need of visa sponsorship?',
                     'Is visa sponsorship required for you to work in Australia?'):
            self.ok(gate(text, YES_NO), 'No', 'answers.future_visa_sponsorship')
            self.ok(gate(text), 'No')

    def test_a_present_question_never_gets_yes_and_needs_a_plain_no(self):
        self.ok(gate('Do you require sponsorship to work in Australia?', ['Yes', 'No', 'Not sure']), 'No')
        self.no(gate('Do you require sponsorship to work in Australia?', ['Yes', 'No, I have full working rights']))

    def test_to_start_is_now_not_a_start_date_question(self):
        self.ok(gate('Do you require visa sponsorship to commence work with us?', YES_NO), 'No')
        self.no(gate('Do you require sponsorship and can you start in two weeks?', YES_NO))   # still two questions


class SponsorshipInTheFutureIsYes(GateCase):
    def test_future_questions_are_yes(self):
        for text in ('Will you now or in the future require visa sponsorship?', 'Will you require sponsorship at any time during your employment?',
                     'Do you require employer sponsorship to work in Australia long term?', 'Will you require visa sponsorship?',
                     'Will you require sponsorship after your current visa expires?', 'Do you now or will you in the future require sponsorship?',
                     'Would you require sponsorship in the future?'):
            self.ok(gate(text, YES_NO), 'Yes', 'answers.future_visa_sponsorship')
            self.ok(gate(text), 'Yes')

    def test_the_option_that_says_yes_in_the_future(self):
        q_ = 'Will you now or in the future require sponsorship?'
        self.ok(gate(q_, ['Yes, now', 'Yes, in the future', 'No']), 'Yes, in the future')
        self.ok(gate(q_, ['Not now, but in the future', 'Yes, immediately', 'No']), 'Not now, but in the future')
        self.ok(gate(q_, ['Yes - but not now', 'No']), 'Yes - but not now')
        self.ok(gate(q_, ['Yes, after my current visa expires', 'No']), 'Yes, after my current visa expires')

    def test_refused_when_the_yes_options_do_not_fit_or_say_now(self):
        q_ = 'Will you now or in the future require sponsorship?'
        for options in (['Yes, now and in the future', 'No'], ['Yes, now', 'No'], ['Yes, I require sponsorship to start', 'No'],
                        ['Yes', 'Yes, now', 'No'], ['Yes', 'I require sponsorship now', 'No'], ['Yes, in the future', 'In the future', 'No'],
                        ['Yes - 482 visa', 'No'], ['No']):
            self.no(gate(q_, options))

    def test_the_cli_refuses_with_exit_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'q.json'
            path.write_text(json.dumps({'question': 'Will you require sponsorship?', 'options': ['Yes', 'Yes, now', 'No']}), encoding='utf-8')
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = q.main(['--dir', str(Path(tmp) / 'queue'), 'answer', '--from-file', str(path)])
            self.assertEqual(code, 5)
            self.assertIn('UNANSWERED', err.getvalue())


class SponsorshipFreeText(GateCase):
    def test_his_own_words(self):
        for text in ('Please outline your visa sponsorship requirements', 'What are your sponsorship requirements?',
                     'If you require sponsorship, please give details.'):
            self.ok(gate(text), FREE_TEXT, 'answers.sponsorship_free_text')
        self.assertEqual(FREE_TEXT, "I'd be glad to discuss this in person. Could you tell me about your sponsorship requirements?")

    def test_a_future_question_starts_yes_in_the_future(self):
        for text in ('Will you require sponsorship in the future? Please explain.', 'Describe any sponsorship you may need in the future.'):
            self.ok(gate(text), FUTURE_FREE_TEXT, 'answers.sponsorship_free_text')
        self.assertTrue(FUTURE_FREE_TEXT.startswith('Yes, in the future. '))

    def test_not_for_his_visa_itself_a_second_question_or_with_options(self):
        for text in ('Please describe your visa and sponsorship situation', 'What visa do you hold and will you require sponsorship?',
                     'Please state your visa status and sponsorship requirements'):
            self.no(gate(text))
        self.no(gate('Which best describes your sponsorship needs?', ['I do not need sponsorship', 'I will need sponsorship later']))

    def test_the_words_come_from_facts(self):
        f = copy.deepcopy(FACTS)
        f['answers'].pop('sponsorship_free_text')
        self.no(gate('Please outline your visa sponsorship requirements', facts=f))
        f = copy.deepcopy(FACTS)
        f['answers']['sponsorship_free_text']['text'] = 'Happy to talk about it.'
        self.ok(gate('Please outline your visa sponsorship requirements', facts=f), 'Happy to talk about it.')


class NotHisToAnswer(GateCase):
    def test_someone_elses_sponsorship_or_another_country(self):
        for text in ('Does your partner require sponsorship?', 'Will any of your family members require sponsorship?',
                     'Do you require sponsorship for your spouse?', 'Do you require sponsorship to work in New Zealand?',
                     'Will you require sponsorship to work in the UK in the future?', 'Do you require US visa sponsorship?',
                     'Will you require sponsorship to work overseas?'):
            self.no(gate(text, YES_NO))
            self.no(gate(text))

    def test_seeking_eligible_negated_or_joined_to_work_rights(self):
        for text in ('Are you seeking visa sponsorship?', 'Are you able to work in Australia without sponsorship?',
                     'Can you work without requiring sponsorship?', 'Are you eligible for employer sponsorship?',
                     'Are you an Australian citizen, permanent resident, or do you require sponsorship?',
                     'Do you hold permanent residency or require sponsorship?', 'Do you have full working rights or will you require sponsorship?'):
            self.no(gate(text, YES_NO))

    def test_older_facts_lines_still_send_the_future_to_the_owner(self):
        f = copy.deepcopy(FACTS)
        f['answers']['future_visa_sponsorship'] = ("Not answered here: if a form asks whether he will need sponsorship in the future, skip "
                                                   "and report (the owner decides this wording). 'Do you need sponsorship to work now?': No.")
        self.no(gate('Will you now or in the future require visa sponsorship?', YES_NO, f))
        self.no(gate('Will you require sponsorship in the future? Please explain.', facts=f))   # no "Yes, in the future" without the line
        self.ok(gate('Do you require sponsorship to work in Australia?', YES_NO, f), 'No')
        f['answers']['future_visa_sponsorship'] = "'Do you need sponsorship to work now?': No. 'Will you now or in the future require sponsorship?': No."
        self.ok(gate('Will you now or in the future require visa sponsorship?', YES_NO, f), 'No')   # read from facts, not fixed in code


class NeverVolunteered(unittest.TestCase):
    def test_letters_and_emails_with_no_sponsorship_needed_are_flagged(self):
        self.assertEqual(checks.letter_issues(LETTER), [])
        for phrase in ('no sponsorship needed', 'no sponsorship is needed', 'no sponsorship required', 'and I do not need sponsorship'):
            text = LETTER.replace('(Subclass 485 visa).', f'(Subclass 485 visa), {phrase}.')
            self.assertIn('letter mentions sponsorship or migration', checks.letter_issues(text), phrase)
            self.assertIn('email mentions sponsorship or migration', checks.email_issues('Junior Civil Drafter', text), phrase)
            self.assertTrue(checks.draft_issues({'cover_letter_text': text}), phrase)
        self.assertIn('email subject mentions residency or migration (facts.json -> never_mention): "sponsorship in the future"',
                      checks.email_issues('Drafter (sponsorship in the future)', LETTER))
        self.assertIn('mentions sponsorship or migration', checks.fact_issues('Full working rights in Australia (Subclass 485 visa), no sponsorship needed.'))

    def test_a_free_text_answer_may_name_it_only_when_the_question_asks(self):
        rights = 'What is your current working rights status in Australia?'
        flagged = lambda question, answer: [i for i in checks.draft_issues({'questions': [{'question': question, 'answer': answer}]})
                                            if 'sponsorship' in i]
        self.assertTrue(flagged(rights, 'I hold a Subclass 485 visa with full working rights. No sponsorship needed.'))
        self.assertTrue(flagged('Tell us about yourself.', 'I do not need sponsorship.'))
        self.assertEqual(flagged('Please outline your visa sponsorship requirements', FREE_TEXT), [])
        self.assertEqual(flagged('What visa conditions apply to you?', 'No sponsorship is needed.'), [])
        self.assertIn('mentions sponsorship or migration', checks.fact_issues('My migration plans are flexible.', sponsorship_asked=True))
        self.assertEqual(checks.fact_issues(FREE_TEXT, sponsorship_asked=True), [])

    def test_the_gates_own_answers_pass_the_draft_check(self):
        questions = [{'question': 'Please outline your visa sponsorship requirements', 'answer': FREE_TEXT, 'basis': 'answers.sponsorship_free_text'},
                     {'question': 'Will you now or in the future require visa sponsorship?', 'options': YES_NO, 'answer': 'Yes',
                      'basis': 'answers.future_visa_sponsorship'}]
        self.assertEqual(checks.draft_issues({'questions': questions}), [])
        questions[1]['answer'] = 'No'
        self.assertTrue(checks.draft_issues({'questions': questions}))

    def test_resumes_profile_and_work_rights_lines_say_nothing_of_sponsorship(self):
        for path in sorted((ROOT.parent / 'documents' / 'resume').glob('*.html')) + [ROOT / 'SEEK_PROFILE.md']:
            self.assertNotIn('sponsor', path.read_text(encoding='utf-8').lower(), path.name)
        for line in (FACTS['eligibility']['work_rights_short'], FACTS['eligibility']['work_rights'], FACTS['answers']['right_to_work']['free_text']):
            self.assertNotIn('sponsor', line.lower())


class SponsorshipSignal(unittest.TestCase):
    def test_offered_and_considered(self):
        for text in ('Sponsorship available.', 'Visa sponsorship is offered for this role.', 'We can sponsor the successful applicant.',
                     'Employer sponsored visa with a pathway to permanent residency.', 'We will provide 482 visa sponsorship.'):
            self.assertEqual(q.sponsorship_signal(text), 'offered', text)
        for text in ('Sponsorship may be considered.', 'Visa sponsorship is available for the right candidate.', 'Sponsorship negotiable.',
                     'We are open to sponsoring the right person.', 'Sponsorship will be considered for exceptional candidates.'):
            self.assertEqual(q.sponsorship_signal(text), 'considered', text)

    def test_negations_and_work_rights_bars_are_not_positive(self):
        for text in ('Sponsorship is not available.', 'No sponsorship.', 'We are unable to sponsor visas.', 'We cannot offer sponsorship at this time.',
                     'Applicants must be able to work in Australia without the need for sponsorship.', 'Visa sponsorship: Not available',
                     'This role does not offer visa sponsorship.', 'Applicants requiring sponsorship will not be considered.',
                     'Applicants who require sponsorship need not apply.', 'Visa sponsorship will not be provided.',
                     'You must have full working rights in Australia. Sponsorship available.', 'Australian citizens and permanent residents only.',
                     'Must hold unrestricted working rights.', 'Sponsorship is available. No sponsorship for graduate roles.',
                     'Great team, competitive salary.', 'We sponsor the local football club.', ''):
            self.assertEqual(q.sponsorship_signal(text), '', text)


class Regional(unittest.TestCase):
    def test_the_definition_and_its_source_are_recorded(self):
        rules = CONFIG['regional_areas']
        self.assertTrue(rules['source'].startswith('https://immi.homeaffairs.gov.au/'))
        self.assertTrue(rules['source_categories'].startswith('https://immi.homeaffairs.gov.au/'))
        self.assertEqual(rules['accessed'], '2026-11-15')
        self.assertEqual(set(rules['category_1_cities']), {'Sydney', 'Melbourne', 'Brisbane'})
        self.assertEqual(set(rules['category_2_cities']), {'Perth', 'Adelaide', 'Gold Coast', 'Sunshine Coast', 'Canberra', 'Newcastle',
                                                           'Lake Macquarie', 'Wollongong', 'Illawarra', 'Geelong', 'Hobart'})

    def test_postcode_categories_follow_the_table(self):
        rules = CONFIG['regional_areas']
        for state, postcode, category in (('NSW', 2500, 2), ('NSW', 2000, 1), ('NSW', 2150, 1), ('NSW', 2650, 3), ('VIC', 3000, 1),
                                          ('VIC', 3337, 1), ('VIC', 3220, 2), ('VIC', 3350, 3), ('VIC', 3809, 3), ('QLD', 4000, 1),
                                          ('QLD', 4810, 3), ('QLD', 4350, 3), ('QLD', 4217, 2), ('QLD', 4305, 2), ('WA', 6000, 2),
                                          ('WA', 6725, 3), ('SA', 5000, 2), ('TAS', 7250, 3), ('ACT', 2600, 2), ('NT', 800, 3)):
            self.assertEqual(q.postcode_category(state, postcode, rules), category, (state, postcode))

    def test_major_city_metro_areas_are_not_regional(self):
        for where in ('Sydney NSW', 'North Sydney, Sydney NSW', 'Parramatta NSW', 'Melbourne VIC (on site)', 'South Melbourne VIC',
                      'Keilor Park, Melbourne VIC', 'Melton VIC 3337', 'Williamstown VIC', 'VIC 3094 (Montmorency, north east Melbourne) VIC',
                      'Brisbane QLD', 'Carina, Brisbane QLD', 'Bowen Hills, Brisbane QLD', 'Roma Street, Brisbane QLD'):
            self.assertIs(q.regional(where, CONFIG), False, where)

    def test_regional_areas_per_the_definition(self):
        for where in ('Townsville, Northern QLD', 'Toowoomba QLD', 'Toowoomba, Toowoomba & Darling Downs QLD', 'Wollongong, Illawarra & South Coast NSW',
                      'Wollongong NSW', 'Norlane, Geelong VIC', 'Ballarat VIC', 'Gympie QLD (Gympie and Sunshine Coast region)', 'Perth WA',
                      'Port Adelaide, Adelaide SA', 'Hobart TAS', 'Canberra ACT', 'Darwin NT', 'Western Australia (laboratory network)',
                      'Wagga Wagga / Forbes, NSW', 'Lismore or Casuarina, Northern Rivers NSW', 'Gold Coast QLD',
                      'Officer VIC', 'Ipswich QLD 4305', 'Strathpine, Brisbane QLD'):   # the last three: regional by postcode
            self.assertIs(q.regional(where, CONFIG), True, where)

    def test_unknown_or_mixed_is_none(self):
        for where in ('', 'Remote', 'Australia wide', 'Melbourne or Geelong VIC', 'Southbank VIC'):
            self.assertIsNone(q.regional(where, CONFIG), where)
        self.assertIsNone(q.regional('Townsville QLD', {}))   # no definition, no guess

    def test_a_year_or_another_state_is_not_read_as_a_postcode_or_a_town(self):
        self.assertIs(q.regional('Wollongong NSW (2026 start)', CONFIG), True)
        self.assertIs(q.regional('Gladstone Park, Melbourne VIC', CONFIG), False)
        self.assertIs(q.regional('Warwick, Perth WA', CONFIG), True)


def draft(n, **kw):
    e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {n}', 'role': 'Junior Civil Drafter', 'location': 'Melbourne VIC',
         'url': f'https://www.seek.com.au/job/{n}', 'seek_id': str(n), 'listed_at': '2026-11-10', 'created_by': 'test'}
    e.update(kw)
    return e


class Ranking(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dir = self.root / 'queue'

    def add(self, e):
        return q.add(e, self.dir, FACTS, NOW, config=CONFIG)

    def test_add_sets_the_fields_from_the_draft_or_works_them_out(self):
        e = self.add(draft(1, sponsorship_signal='considered', regional=False, location='Townsville QLD'))
        self.assertEqual((e['sponsorship_signal'], e['regional']), ('considered', False))   # the screener's own reading stands
        e = self.add(draft(2, location='Toowoomba QLD', advert_text='Junior drafter. Visa sponsorship available.'))
        self.assertEqual((e['sponsorship_signal'], e['regional']), ('offered', True))
        self.assertNotIn('advert_text', e)
        self.assertNotIn('advert_text', json.loads((self.dir / 'open' / 'seek-2.json').read_text(encoding='utf-8')))
        e = self.add(draft(3, content_text='Sponsorship is not available for this role.'))
        self.assertEqual((e['sponsorship_signal'], e['regional']), ('', False))
        self.assertEqual(list(e)[:16], list(q.FIELDS)[:16])

    def test_add_and_check_refuse_other_values(self):
        for bad in ({'sponsorship_signal': 'yes'}, {'regional': 'yes'}, {'regional': 1}):
            with self.assertRaises(q.Refused):
                self.add(draft(9, **bad))
        e = q.fill(draft(10, sponsorship_signal='maybe'))
        self.assertTrue(any('sponsorship_signal' in p for p in q.validate(e, FACTS)))
        self.assertEqual(q.check_problems(q.load(self.dir), FACTS, NOW), [])

    def test_sponsorship_then_regional_ahead_of_lane(self):
        self.add(draft(1, location='Sydney NSW'))
        self.add(draft(2, location='Townsville QLD'))
        self.add(draft(3, location='Melbourne VIC', sponsorship_signal='considered'))
        self.add(draft(4, location='Sydney NSW', sponsorship_signal='offered'))
        self.add(draft(5, location='Ballarat VIC', sponsorship_signal='offered'))
        self.add(draft(6, lane='engineer', location='Toowoomba QLD', sponsorship_signal='offered'))   # D68: ahead of non-sponsor drafter jobs
        # Offered and considered are one group (the owner: "available or considered"): the closing date decides between them.
        self.add(draft(7, location='Cairns QLD', sponsorship_signal='considered', closes_at='2026-11-20', closes_source='advert'))
        order = [e['id'] for e in sorted((e for _, e in q.load(self.dir)), key=lambda e: q.sort_key(e, CONFIG))]
        self.assertEqual(order, ['seek-7', 'seek-5', 'seek-6', 'seek-3', 'seek-4', 'seek-2', 'seek-1'])
        self.assertEqual(q.next_entry('SEEK', self.dir, CONFIG, NOW, facts=FACTS)['id'], 'seek-7')

    def test_advertised_before_speculative_stays_first(self):
        spec = draft(7, route='EMAIL', seek_id='', url='https://example7.com.au/careers', role='Speculative enquiry: civil drafter',
                     application_type='SPECULATIVE_ENQUIRY', location='Townsville QLD', sponsorship_signal='offered',
                     email={'to': 'jobs@example7.com.au', 'subject': 'Civil drafter', 'body': 'Hello.', 'evidence_url': 'https://example7.com.au/careers'})
        e = q.fill(spec)
        plain = q.fill(draft(8, location='Sydney NSW'))
        self.assertLess(q.sort_key(plain, CONFIG), q.sort_key(e, CONFIG))

    def test_older_entries_are_ranked_by_their_location_without_editing_their_files(self):
        old = {k: v for k, v in q.fill(draft(11, location='Townsville, Northern QLD')).items() if k not in ('sponsorship_signal', 'regional')}
        path = self.dir / 'open' / 'seek-11.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(old), encoding='utf-8')
        before = path.read_bytes()
        (_, e), = q.load(self.dir)
        self.assertEqual(q.targeting(e, CONFIG), ('', True))
        self.assertEqual(q.check_problems(q.load(self.dir), FACTS, NOW), [])
        q.render(self.dir, CONFIG, NOW)
        self.assertEqual(path.read_bytes(), before)

    def test_render_shows_them(self):
        self.add(draft(1, location='Townsville QLD', sponsorship_signal='offered'))
        self.add(draft(2, location='Sydney NSW'))
        q.render(self.dir, CONFIG, NOW)
        text = (self.dir / 'APPLY_QUEUE.md').read_text(encoding='utf-8')
        self.assertIn('| # | Lane | Company | Role | Location | Target | Closes | Link | Note |', text)
        self.assertIn('| 1 | drafter | Acme 1 | Junior Civil Drafter | Townsville QLD | sponsorship offered, regional |', text)
        self.assertIn('| 2 | drafter | Acme 2 | Junior Civil Drafter | Sydney NSW | not regional |', text)



class ReviewFixes(GateCase):
    """15 Nov 2026 review: wordings that the first version answered wrongly or not at all."""

    def test_now_named_with_will_or_would_is_still_now(self):
        for text in ('Will you need sponsorship to start this role?', 'Would you require sponsorship to start in this role?',
                     'Will you need us to sponsor you now?'):
            self.ok(gate(text, YES_NO), 'No', 'answers.future_visa_sponsorship')

    def test_a_time_to_come_said_less_plainly_is_the_future(self):
        for text in ('Are you going to require sponsorship?', 'Do you anticipate requiring sponsorship?', 'Do you expect to need sponsorship?',
                     'Do you require sponsorship to remain in Australia?', 'Do you need employer sponsorship to stay in Australia?',
                     'Do you require sponsorship to continue working in Australia?', 'Do you anticipate needing visa sponsorship?'):
            self.ok(gate(text, YES_NO), 'Yes', 'answers.future_visa_sponsorship')
        self.no(gate('Do you currently require sponsorship to remain in Australia?', YES_NO))   # now and later at once

    def test_a_question_about_now_whose_options_offer_the_future_never_gets_no(self):
        present = 'Do you require sponsorship to work in Australia?'
        for options, want in ((['Yes, now', 'Yes, in the future', 'No'], 'Yes, in the future'), (['No', 'Yes, in the future'], 'Yes, in the future'),
                              (['Yes', 'Yes, in the future', 'No'], 'Yes, in the future'),
                              (['Yes', 'No', 'Not now, but in the future'], 'Not now, but in the future')):
            self.ok(gate(present, options), want, 'answers.future_visa_sponsorship')
            self.ok(gate('Will you now or in the future require sponsorship?', options), want)
        old = copy.deepcopy(FACTS)
        old['answers']['future_visa_sponsorship'] = "'Do you need sponsorship to work now?': No."
        self.no(gate(present, ['Yes, now', 'Yes, in the future', 'No'], old))   # no future answer in facts: the owner's, never No

    def test_a_plain_yes_beside_an_option_that_names_a_time_is_refused(self):
        q_ = 'Will you require sponsorship now or in the future?'
        for options in (['Not now but maybe in the future', 'No', 'Yes'], ["I don't require sponsorship now", 'Yes', 'No'],
                        ['No, not now', 'Yes', 'No']):
            self.no(gate(q_, options))

    def test_not_about_his_own_need_or_another_countrys_visa(self):
        for text in ('Does this role require sponsorship?', 'Will this role require sponsorship?', 'Do you require H-1B sponsorship?',
                     'Will you now, or in the future, require sponsorship for an employment visa (e.g. H-1B)?'):
            self.no(gate(text, YES_NO))
        self.no(gate('Is there anything we should know about your sponsorship needs?'))

    def test_present_wordings_never_yes_and_future_wordings_never_no(self):
        option_sets = ([], YES_NO, ['Yes', 'No', 'Not sure'], ['Yes, now', 'Yes, in the future', 'No'], ['Yes, now', 'No'])
        for lead in ('Do you', 'Do you currently'):
            for verb in ('require', 'need'):
                for tail in ('', ' to work in Australia', ' to work for us', ' to start', ' now'):
                    for options in option_sets:
                        r = gate(f'{lead} {verb} visa sponsorship{tail}?', options)
                        self.assertEqual(r['status'], 'answered', (lead, verb, tail, options))
                        self.assertIn(r['answer'], ('No', 'Yes, in the future'), (lead, verb, tail, options))
                        self.assertEqual(r['answer'] == 'No', 'Yes, in the future' not in options, (lead, verb, tail, options))
        for lead in ('Will you', 'Would you', 'Will you now or in the future', 'Are you going to', 'Do you expect to'):
            for tail in ('', ' in the future', ' at any time during your employment', ' long term', ' to remain in Australia'):
                for options in option_sets:
                    r = gate(f'{lead} require sponsorship{tail}?', options)
                    if options == ['Yes, now', 'No']:   # no option says Yes in the future, and No would be false
                        self.no(r)
                        continue
                    self.assertIn(r['answer'], ('Yes', 'Yes, in the future'), (lead, tail, options, r))


class ReviewFixesChecks(unittest.TestCase):
    def test_subjects_greetings_and_closings_are_read_too(self):
        for subject in ('Junior Civil Drafter, no sponsorship needed', 'Drafter (sponsorship not required)'):
            self.assertIn('email subject mentions sponsorship or migration', checks.email_issues(subject, LETTER), subject)
        self.assertEqual(checks.email_issues('Junior Civil Drafter', LETTER), [])
        letter = {'subject': 'Junior Civil Drafter, no sponsorship needed', 'greeting': 'Hi team, no sponsor needed',
                  'closing': 'Kind regards (sponsorship-free)'}
        found = checks.draft_issues({'cover_letter_text': LETTER, 'letter': letter})
        for part in ('letter subject', 'letter greeting', 'letter closing'):
            self.assertIn(f'{part} mentions sponsorship or migration', found)
        self.assertIn('letter mentions sponsorship or migration',
                      checks.letter_issues(LETTER.replace('(Subclass 485 visa).', '(Subclass 485 visa), unsponsored.')))

    def test_a_written_answer_to_a_sponsorship_question_is_the_owners_answer(self):
        def found(question, answer, options=None):
            return [i for i in checks.draft_issues({'questions': [{'question': question, 'options': options or [], 'answer': answer}]})
                    if 'sponsorship' in i]
        free = 'Please outline your visa sponsorship requirements'
        for answer in ('No sponsorship needed.', 'I need a 482 sponsorship to start.', 'I will need sponsorship after December 2027.'):
            self.assertTrue(found(free, answer), answer)
        self.assertEqual(found(free, FREE_TEXT), [])
        self.assertEqual(found('Do you require sponsorship to work in Australia?', 'No', YES_NO), [])
        self.assertTrue(found('Do you require sponsorship to work in Australia?', 'No, and I never will.', YES_NO))
        self.assertTrue(found('Does your partner require sponsorship?', 'No', YES_NO))   # not his to answer: the owner's

    def test_negations_further_from_the_word_are_not_positive(self):
        for text in ('We are unable to consider applicants who require sponsorship.', 'This role is not open to visa holders requiring sponsorship.',
                     'Unfortunately we are not in a position to consider applicants requiring visa sponsorship.', 'Sponsorship offered? No.',
                     'We proudly support and sponsor local community events.', 'We are happy to sponsor community events.'):
            self.assertEqual(q.sponsorship_signal(text), '', text)

    def test_positive_wordings_the_first_version_missed(self):
        for text, want in (('This role is eligible under the DAMA.', 'considered'), ('482 sponsorship considered.', 'considered'),
                           ('Visa sponsorship available for the right candidate.', 'considered'),
                           ('Applicants requiring sponsorship are welcome to apply.', 'considered'), ('Visa sponsorship: Yes', 'offered'),
                           ('We are an accredited sponsor.', 'offered'), ('Visa sponsorship available to join our team.', 'offered')):
            self.assertEqual(q.sponsorship_signal(text), want, text)

    def test_regional_against_the_home_affairs_table(self):
        for where in ('Parramatta, Sydney NSW', 'Penrith NSW', 'Melton VIC', 'Werribee, Melbourne VIC', 'Logan, Brisbane QLD', 'Sydney NSW 2000'):
            self.assertIs(q.regional(where, CONFIG), False, where)
        for where in ('Ipswich, Brisbane QLD', 'Newcastle NSW', 'Geelong VIC', 'Gold Coast QLD', 'Perth WA', 'Townsville QLD', 'Toowoomba QLD',
                      'Wollongong NSW', 'Canberra ACT', 'Hobart TAS', 'Cairns, Far North QLD'):
            self.assertIs(q.regional(where, CONFIG), True, where)
        for where in ('Ballarat or Melbourne VIC', 'Werribee / Geelong VIC', 'Sydney or Newcastle NSW'):   # alternatives that disagree
            self.assertIsNone(q.regional(where, CONFIG), where)


if __name__ == '__main__':
    unittest.main()
