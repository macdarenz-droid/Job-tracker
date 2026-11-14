"""Round 2 review fixes (14 Nov 2026). Safety review F1 to F8 and privacy review F1, F2, F4 to F6. Every behaviour change
has a test that failed on commit 80b7dad and passes after the fix; the tests marked "guard" pass on 80b7dad too and hold
what must not change (the plain options still chosen, the tool's own line still reopening, no false hits) or, for
privacy F4, kill the mutants that went through the suite. Offline: temp folders only; the repository's own facts.json
is read as data."""
import copy
import json
import re
import unittest
from datetime import timedelta
from pathlib import Path

import test_recheck_fixes as base   # the same queue module, facts and helpers as the round-1 tests

q, answers, checks = base.q, base.answers, base.checks
Case, entry, gate, opts = base.Case, base.entry, base.gate, base.opts
FACTS, NOW, RUN, OTHER_RUN, YN = base.FACTS, base.NOW, base.RUN, base.OTHER_RUN, base.YN
SCRIPTS, TESTS = base.SCRIPTS, base.TESTS
RTW = 'Which of the following statements best describes your right to work in Australia?'
SEEK_RTW = ["I'm an Australian citizen", "I'm a permanent resident and/or NZ citizen", 'I have a family/partner visa with no restrictions',
            'I have a graduate temporary work visa', 'I have a holiday temporary work visa',
            'I have a temporary visa with restrictions on location (e.g. skilled regional visa 491)',
            'I have a temporary protection or safe haven visa', 'I have a temporary visa with no restrictions (e.g. doctoral student)',
            'I have a temporary visa with restrictions on industry (e.g. TSS visa)', 'I require sponsorship to work for a new employer (e.g. 482, 457)']
SALARY = base.SALARY
SAL2 = ['Less than $40k', '$40k - $60k', '$61k - $79k', '$80k - $99k', '$100k - $119k', '$120k+']
SIMILAR = "How many years' experience do you have in a similar role?"
YEARS = ['No experience', 'Less than 1 year', '1 year', '2 years', '3 years', 'More than 3 years']


def owner(rows):
    return base.with_owner_answers(rows)


def row(question, answer, **kw):
    return {'question': question, 'answer': answer, 'date': '2026-11-14', **kw}


# ------------------------------------------------------------------ safety F1: compound right-to-work options

class RightToWorkOptionsSayOnlyTheVisa(unittest.TestCase):
    def test_an_option_that_adds_to_the_visa_is_not_chosen(self):
        for question, options in (
                ('What is your visa status?', ['Australian Citizen', 'Permanent Resident', 'Temporary Graduate visa (485) with more than 2 years remaining', 'Other']),
                (RTW, ['Australian citizen or permanent resident', 'Temporary Graduate visa (subclass 485) - no sponsorship required now or in the future',
                       'Temporary visa - sponsorship will be required']),
                ('Which of the following best describes your right to work in Australia?',
                 ['Australian or NZ citizen', 'Permanent resident', 'Temporary visa with no restrictions, valid for at least 3 years', 'Temporary visa with restrictions']),
                (RTW, ["I'm an Australian citizen", 'I have a graduate temporary work visa and have applied for permanent residency', 'I require sponsorship']),
                ('Do you have the right to work in Australia?', ['Yes - citizen or PR', 'Yes - Temporary Graduate visa (485), no sponsorship needed now or in future', 'No']),
                (RTW, ['Temporary Graduate visa (subclass 485) - Post-Study Work stream', 'Other'])):
            r = gate(question, options)
            self.assertEqual((r['status'], r['answer']), ('unanswered', ''), (question, options))

    def test_a_compound_graduate_option_is_not_replaced_by_another(self):
        options = [o for o in SEEK_RTW if 'graduate' not in o] + ['Temporary Graduate visa (485) with more than 2 years remaining']
        self.assertEqual(gate(RTW, options)['status'], 'unanswered')

    def test_the_plain_options_are_still_chosen(self):   # guard
        self.assertEqual(gate(RTW, SEEK_RTW)['answer'], 'I have a graduate temporary work visa')
        self.assertEqual(gate(RTW, ['Australian citizen', 'Temporary Graduate visa (subclass 485)', 'Other'])['answer'],
                         'Temporary Graduate visa (subclass 485)')
        self.assertEqual(gate(RTW, [o for o in SEEK_RTW if 'graduate' not in o])['answer'],
                         'I have a temporary visa with no restrictions (e.g. doctoral student)')


# ------------------------------------------------------------------ safety F2: re-posts with plurals or other spellings

class SameRoleWithPluralsAndSpellings(Case):
    def test_the_reviewers_pairs_are_the_same_role(self):
        for a, b in (('Civil Engineer', 'Civil Engineers'), ('Graduate Civil Engineer', 'Graduate Civil Engineers - 2027 Intake'),
                     ('Civil Drafter', 'Civil Draftsperson'), ('Civil Draftsperson', 'Civil Draughtsperson'),
                     ('Graduate Civil Engineer', 'Civil Engineering Graduate'), ('Civil Engineer - Wollongong', 'Civil Engineer - Illawarra')):
            self.assertTrue(q.same_role(a, b) and q.same_role(b, a), (a, b))
        for a, b in (('Civil Drafter', 'Civil Designer'), ('Civil Engineer', 'Laboratory Technician'), ('Design Drafter', 'Civil Drafter'),
                     (' - Wollongong', ' - Illawarra')):
            self.assertFalse(q.same_role(a, b) or q.same_role(b, a), (a, b))

    def test_a_plural_repost_after_an_application_is_refused_and_never_handed_out(self):
        self.add(entry(1, company='Allen Price Pty Ltd', role='Civil Engineer'))
        q.mark(self.dir, 'seek-1', 'applied', 'Grok', NOW, kind='seek_confirmation_screen', ref='SEEK confirmation screen shown', facts=FACTS)
        with self.assertRaises(q.Refused) as r:
            self.add(entry(2, company='Allen Price', role='Civil Engineers'))
        self.assertIn('already applied for this company and role (seek-1)', str(r.exception))
        q.save(self.dir, q.fill(entry(3, company='Allen Price', role='Civil Draftsperson')))
        q.save(self.dir, q.fill(entry(4, company='Allen Price', role='Civil Engineers')))   # a second runner's push
        e3 = q.fill(entry(5, company='Allen Price', role='Civil Drafter'))
        ctx = q.hold_context([e for _, e in q.load(self.dir)], base.CONFIG, NOW + timedelta(hours=1))
        self.assertIn('already applied for this company and role (seek-1)', q.blockers(q.fill(entry(4, company='Allen Price', role='Civil Engineers')), ctx))
        self.assertTrue(q.same_job(e3, q.fill(entry(3, company='Allen Price', role='Civil Draftsperson'))))


# ------------------------------------------------------------------ safety F3: a $ the shell removed

class AdvertPayKeepsItsDollar(Case):
    def test_the_pay_missing_message_names_the_file_form(self):
        self.assertIn('"advert_pay" in the --from-file JSON', q.PAY_MISSING)
        self.assertIn("<<'EOF'", q.PAY_MISSING)
        self.assertNotIn('run again with --advert-pay', q.PAY_MISSING)

    def test_a_pay_without_its_dollar_is_refused_typed_or_from_a_file(self):
        self.add(entry(1))
        self.claim()
        before = self.files()
        for args in (['--advert-pay', '20,000 per year'],
                     ['--from-file', self.file('pay.json', {'question': SALARY, 'options': SAL2, 'advert_pay': '20,000 per year'})],
                     ['--from-file', self.file('pay2.json', {'advert_pay': '00,000 - 20,000'})]):
            code, out, err = self.cli('answer', 'seek-1', *(['--question', SALARY, *opts(SAL2)] if args[0] == '--advert-pay' else []), *args,
                                      '--by', 'Grok', '--run', RUN)
            self.assertEqual((code, out), (1, ''), args)
            self.assertIn('has figures but no $', err)
            self.assertIn("<<'EOF'", err)
            self.assertEqual(self.files(), before, args)
        code, out, _ = self.cli('answer', '--question', SALARY, *opts(SAL2), '--advert-pay', '50,000 per year')   # screening too
        self.assertEqual((code, out), (1, ''))
        code, out, err = self.cli('answer', 'seek-1', '--from-file', self.file('ok.json', {'question': SALARY, 'options': SAL2,
                                  'advert_pay': '$120,000 per year'}), '--by', 'Grok', '--run', RUN)
        self.assertEqual((code, out), (0, '$120k+\n'))
        self.assertIn('advert_pay stored: $120,000 per year', err)
        self.assertEqual(self.stored('seek-1')['advert_pay'], '$120,000 per year')

    def test_an_advert_with_no_dollar_is_written_with_aud(self):
        r = gate(SALARY, SAL2, pay='AUD 65-80k plus super')
        self.assertEqual(r['answer'], '$61k - $79k')
        self.assertEqual(q.pay_problem('AUD 65-80k plus super'), '')
        for pay in ('not stated', 'Competitive salary + super', 'Base + Super + 20% Site uplift', '$85,000 - $95,000 per year'):
            self.assertEqual(q.pay_problem(pay), '', pay)
        self.assertIn('has figures but no $', q.pay_problem('65-80k plus super'))

    def test_add_refuses_a_pay_or_salary_without_its_dollar(self):
        for kw in ({'advert_pay': '20,000 per year'}, {'salary': '5,000 - 0,000'}):
            with self.assertRaises(q.Refused) as r:
                self.add(entry(1, questions=[{'question': SALARY, 'options': SAL2}], **kw))
            self.assertIn('has figures but no $', str(r.exception))
        e = self.add(entry(1, questions=[{'question': SALARY, 'options': SAL2}], salary='AUD 65-80k plus super'))
        self.assertEqual(e['questions'][0]['answer'], '$61k - $79k')

    def test_salary_options_that_lost_their_dollar_are_refused(self):
        mangled = ['Less than 0k', '0k - 0k', '1k - 9k', '0k - 9k', '00k - 19k', '20k+']   # SAL2 typed in double quotes
        self.add(entry(1))
        self.claim()
        before = self.files()
        code, out, err = self.cli('answer', 'seek-1', '--question', SALARY, *opts(mangled), '--advert-pay', 'not stated', '--by', 'Grok', '--run', RUN)
        self.assertEqual((code, out), (1, ''))
        self.assertIn('the options of the salary question have figures but no $', err)
        self.assertEqual(self.files(), before)
        self.assertEqual(q.salary_options_problem(SALARY, ['40,000 - 60,000', '60,000 - 80,000', '80,000+']), '')   # written so on screen
        with self.assertRaises(q.Refused):
            self.add(entry(2, questions=[{'question': SALARY, 'options': mangled}], advert_pay='not stated'))


# ------------------------------------------------------------------ safety F4: already_applied after this pipeline's own hand-out

class AlreadyAppliedAfterTheHandOutCounts(Case):
    def test_without_at_on_a_handed_out_entry_it_is_refused(self):
        self.add(entry(1))
        self.claim()
        before = self.files()
        code, _, err = self.cli('mark', 'seek-1', 'applied', '--by', 'Grok', '--kind', 'already_applied', '--ref', 'SEEK job page shows applied',
                                '--run', OTHER_RUN, now=NOW + timedelta(minutes=12))
        self.assertEqual(code, 1)
        self.assertIn('give --at with the date the site shows he applied', err)
        self.assertEqual(self.files(), before)

    def test_dated_the_hand_out_day_it_keeps_the_spacing_the_caps_and_the_report(self):
        self.add(entry(1))
        self.add(entry(2, listed_at='2026-11-09'))
        self.claim()   # 12:00 Melbourne: session 1 submits, then crashes before the mark
        later = NOW + timedelta(minutes=13)
        code, out, err = self.cli('mark', 'seek-1', 'applied', '--by', 'Grok', '--kind', 'already_applied', '--ref', 'SEEK job page shows applied',
                                  '--at', '2026-11-13', '--run', OTHER_RUN, now=later)
        self.assertEqual((code, out.strip()), (0, 'seek-1: APPLIED'), err)
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', OTHER_RUN, now=later + timedelta(minutes=1))
        self.assertEqual(code, 3)   # the 20-minute SEEK spacing still runs from the hand-out
        self.assertIn('the last submission or start was 14 minutes ago', err)
        r = q.report(self.dir, later, 7)
        self.assertEqual((r['applied'], r['already_applied_found']), (1, 0))
        s = q.stats(self.dir, later)
        self.assertEqual((s['applied_total'], s['already_applied_total']), (1, 0))
        one = copy.deepcopy(base.CONFIG)
        one['limits']['seek_submissions_per_day'] = 1
        q.write_json(self.config, one)
        code, _, err = self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', OTHER_RUN, now=later + timedelta(minutes=40))
        self.assertEqual(code, 3)
        self.assertIn("the day's cap is reached (1 of 1", err)

    def test_dated_before_the_hand_out_it_is_still_left_out(self):   # guard
        self.add(entry(1))
        self.claim()
        self.assertEqual(self.cli('mark', 'seek-1', 'applied', '--by', 'Claude', '--kind', 'already_applied', '--ref', 'SEEK shows applied on 2 Oct 2026',
                                  '--at', '2026-10-02', now=NOW + timedelta(minutes=1))[0], 0)
        self.assertTrue(q.found_applied(self.stored('seek-1')))
        self.assertIsNone(q.submission_time(self.stored('seek-1')))


# ------------------------------------------------------------------ safety F5: an owner answer about one job stays with that job

class OwnerAnswersAboutOneJob(Case):
    def test_a_scoped_row_answers_its_entry_only(self):
        facts = owner([row(SIMILAR, 'Less than 1 year', options=YEARS, entry='seek-1')])
        r = answers.answer(SIMILAR, YEARS, facts, entry='seek-1')
        self.assertEqual((r['answer'], r['basis']), ('Less than 1 year', 'answers.owner_answers'))
        for other in ('seek-2', None):
            self.assertEqual(answers.answer(SIMILAR, YEARS, facts, entry=other)['status'], 'unanswered', other)
        self.add(entry(1, questions=[{'question': SIMILAR, 'options': YEARS}]))
        self.add(entry(2, questions=[{'question': SIMILAR, 'options': YEARS}]))
        q.write_json(self.facts, facts)
        self.assertEqual(self.cli('check')[0], 0)
        self.assertEqual(self.cli('answer', 'seek-1')[0], 0)
        self.assertEqual(self.cli('answer', 'seek-2')[0], 5)
        self.assertEqual((self.stored('seek-1')['status'], self.stored('seek-2')['status']), ('OPEN', 'ASK_OWNER'))

    def test_an_unscoped_row_about_one_job_or_its_pay_is_refused(self):
        self.add(entry(1))
        for question in (SIMILAR, SALARY, 'Do you have your own tools relevant to this role?', 'Tell us what motivated you to apply for this role?'):
            q.write_json(self.facts, owner([row(question, 'Yes')]))
            code, out, _ = self.cli('check')
            self.assertEqual(code, 1, question)
            self.assertIn('is about one job or its pay: add "entry"', out)
            self.assertEqual(answers.answer(question, [], owner([row(question, 'Yes')]))['status'], 'unanswered', question)

    def test_a_scoped_row_goes_before_an_unscoped_one_and_the_entry_must_be_an_id(self):
        question = 'Do you have experience with stormwater pit inspections?'
        facts = owner([row(question, 'No'), row(question, 'Yes', entry='seek-1')])
        self.assertEqual(answers.answer(question, YN, facts, entry='seek-1')['answer'], 'Yes')
        self.assertEqual(answers.answer(question, YN, facts, entry='seek-2')['answer'], 'No')
        self.assertEqual(answers.answer(question, YN, facts)['answer'], 'No')
        self.assertEqual(q.owner_answer_problems(facts), [])
        bad = q.owner_answer_problems(owner([row(question, 'Yes', entry='Seek 1')]))
        self.assertTrue(any('entry: the queue id' in x for x in bad), bad)


# ------------------------------------------------------------------ safety F6, privacy F1: no private detail in owner_answers

PRIVATE_ROWS = [row('What is your date of birth?', '3 March 1996'), row("What is your driver's licence number?", '032 456 789'),
                row('What is your Tax File Number?', '123 456 782'),
                row('Please describe any medical condition we should know about', 'Mild asthma, managed with an inhaler'),
                row('What is your residential address?', '12 Example Street, Melton VIC 3337')]


class NoPrivateDetailInOwnerAnswers(Case):
    def test_each_private_row_stops_check_next_and_answer(self):
        self.add(entry(1))
        for one in PRIVATE_ROWS:
            q.write_json(self.facts, owner([one]))
            code, out, _ = self.cli('check')
            self.assertEqual(code, 1, one)
            self.assertIn('answers -> owner_answers row 1: question: asks for a private detail', out)
            before = self.files()
            self.assertEqual(self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)[0], 1, one)
            self.assertEqual(self.files(), before, one)
            self.assertEqual(self.cli('answer', '--question', one['question'])[0], 1, one)

    def test_the_gate_never_takes_a_private_answer_from_a_row(self):
        facts = owner(PRIVATE_ROWS)
        r = answers.answer('What is your date of birth?', [], facts)
        self.assertEqual(r['status'], 'unanswered')
        self.assertIn('only the owner can answer this', r['why'])
        for one in PRIVATE_ROWS:
            self.assertEqual(answers.answer(one['question'], [], facts)['status'], 'unanswered', one)
        ok = owner([row('Have you ever been dismissed from a job?', 'No')])
        self.assertEqual(answers.answer('Have you ever been dismissed from a job?', YN, ok)['answer'], 'No')
        self.assertEqual(q.owner_answer_problems(ok), [])

    def test_private_text_in_an_answer_to_another_question_is_refused(self):
        for answer_text, needle in (('Yes, born 15 March 1995', 'a whole date before 2012'), ('Yes: 123 456 782', 'a number of 6 or more digits'),
                                    ('Yes, 032-456-789', 'a number of 6 or more digits'), ('Yes, licence no. 032456789', 'a number of 6 or more digits')):
            bad = q.owner_answer_problems(owner([row('Can you provide proof of identity?', answer_text)]))
            self.assertTrue(any(needle in x for x in bad), (answer_text, bad))
        self.assertEqual(q.owner_answer_problems(owner([row('Can you provide proof of identity?', 'Yes, from 2026-11-14')])), [])

    def test_a_recompute_that_would_store_a_private_detail_saves_nothing(self):
        self.add(entry(1, questions=['Who is your referee?']))
        path, e = q.find(self.dir, 'seek-1')
        before = path.read_bytes()
        facts = owner([row('Who is your referee?', 'Sarah Lee on 0412 345 678')])   # check would refuse it first; the backstop
        with self.assertRaises(q.Refused) as r:
            q.refresh(self.dir, path, e, facts)
        self.assertIn('would put into the public queue file', str(r.exception))
        self.assertEqual(path.read_bytes(), before)


# ------------------------------------------------------------------ safety F7: only the tool's own line, word for word, is cleared

class OwnerQuestionsInTheToolsWording(Case):
    LINE = 'No standing answer for the advert line that asks for 3 years of Australian experience as essential: apply anyway?'

    def test_add_refuses_an_owner_question_in_the_tools_wording(self):
        with self.assertRaises(q.Refused) as r:
            self.add(entry(1, company='Lendlease', role='Civil Engineer', ask_owner=self.LINE))
        self.assertIn("write the owner question in your own words: 'No standing answer for'", str(r.exception))
        e = self.add(entry(2, questions=['Do you have Traffic Control experience?']))
        self.assertEqual(e['status'], 'ASK_OWNER')   # the tool's own line, as before

    def test_mark_ask_refuses_it_and_a_hand_written_one_is_never_reopened(self):
        self.add(entry(1))
        self.claim()
        before = self.files()
        code, _, err = self.cli('mark', 'seek-1', 'ask', '--by', 'Grok', '--run', RUN, '--question',
                                'No standing answer for the identity check the site asks for: go ahead or drop it?')
        self.assertEqual(code, 1)
        self.assertIn('write the owner question in your own words', err)
        self.assertEqual(self.files(), before)
        e = q.fill(entry(3, status='ASK_OWNER', ask_owner=self.LINE))   # a hand edit or an older file
        q.save(self.dir, e)
        q.apply_answers(e, FACTS)
        self.assertEqual((e['status'], e['ask_owner']), ('ASK_OWNER', self.LINE))
        self.assertEqual(self.cli('next', '--route', 'SEEK', now=NOW + timedelta(minutes=25))[0], 4)
        self.assertEqual(self.stored('seek-3')['status'], 'ASK_OWNER')
        code, _, err = self.cli('mark', 'seek-3', 'open', '--by', 'Claude', now=NOW + timedelta(minutes=26))
        self.assertEqual(code, 1)
        self.assertIn('Reopen it only with his answer', err)

    def test_the_tools_own_line_still_reopens(self):   # guard
        self.add(entry(1, questions=[{'question': base.STANDARDS, 'options': YN}]))
        self.assertTrue(self.stored('seek-1')['ask_owner'].startswith(q.QUESTION_LINE))
        q.write_json(self.facts, owner([row(base.STANDARDS, 'Yes', options=['Yes', 'No'])]))
        self.assertEqual(self.cli('answer', 'seek-1')[0], 0)
        self.assertEqual(self.stored('seek-1')['status'], 'OPEN')


# ------------------------------------------------------------------ safety F8: only the session that started it fills the form

class AnswerOnlyForTheSessionThatStartedIt(Case):
    def test_another_session_or_no_session_gets_no_answer_and_no_recompute(self):
        self.add(entry(1))
        self.claim()
        later = NOW + timedelta(minutes=30)
        before = self.files()
        licence = "Do you have a current Australian driver's licence?"
        for extra in (['--by', 'Grok', '--run', '20261113T013000Z'], []):
            code, out, err = self.cli('answer', 'seek-1', '--question', licence, *opts(YN), *extra, now=later)
            self.assertEqual((code, out), (1, ''), extra)
            self.assertIn('Do not fill or submit its form (answer refused; nothing changed).', err)
        self.assertEqual(self.cli('answer', 'seek-1', now=later)[0], 1)   # a recompute under way: refused too
        self.assertEqual(self.files(), before)
        code, out, _ = self.cli('answer', 'seek-1', '--question', licence, *opts(YN), '--by', 'Grok', '--run', RUN, now=later)
        self.assertEqual((code, out), (0, 'Yes\n'))


# ------------------------------------------------------------------ privacy F2: the console job's employer, read from facts

class ConsoleJobByItsEmployer(unittest.TestCase):
    FAKE = {'experience': [{'role': 'Console Operator (casual)', 'employer': 'bp service station (Acme Fuel Group), Melbourne VIC'},
                           {'role': 'Field Engineer', 'employer': 'Somewhere Else Pty Ltd, Philippines'}]}

    def test_a_letter_naming_the_employer_as_civil_experience_is_flagged(self):
        pattern = checks.console_pattern(self.FAKE)
        for sentence in ('My work at Acme Fuel Group has given me civil site experience.',
                         'At Acme Fuel I coordinate contractor deliveries and site inspections.',
                         'My role with Acme Fuel Group includes coordinating infrastructure deliveries.'):
            self.assertTrue(checks.console_job_as_civil(sentence, pattern), sentence)
        for sentence in ('I work casually at Acme Fuel Group while studying.', 'I worked with a group of engineers on drainage design in 2019.'):
            self.assertFalse(checks.console_job_as_civil(sentence, pattern), sentence)
        self.assertFalse(checks.console_job_as_civil('Somewhere Else gave me site experience.', pattern))   # not the console job

    def test_the_repository_facts_name_is_caught_without_being_in_code(self):
        names = re.findall(r'\(([^)]*)\)', FACTS['experience'][0]['employer'])
        if not names:
            self.skipTest('facts.json names no employer in brackets for the console job')
        letter = base.LETTER.replace('Could we talk this week?', f'My work at {names[0]} has given me experience coordinating civil site '
                                     'deliveries and inspections. Could we talk this week?')
        self.assertIn('letter presents the casual console operator job as civil experience (facts: it is current Australian work, nothing more)',
                      checks.letter_issues(letter))


# ------------------------------------------------------------------ privacy F4: the gaps the mutants went through

class GapsTheMutantsFound(Case):   # guards: each kills one surviving mutant
    def test_a_from_file_question_is_screened_like_a_typed_one(self):   # (a)
        self.add(entry(7))
        before = self.files()
        path = self.file('qf.json', {'question': 'Please confirm your referee at sarah.lee@example.com may be contacted', 'options': YN})
        code, out, err = self.cli('answer', 'seek-7', '--from-file', path)
        self.assertEqual((code, out), (1, ''))
        self.assertIn('an email address', err)
        self.assertEqual(self.files(), before)

    def test_owner_answer_options_are_screened(self):   # (b)
        self.add(entry(1))
        q.write_json(self.facts, owner([row('Who may we contact?', 'Sarah Lee', options=['Sarah Lee (sarah.lee@example.com)', 'Sarah Lee'])]))
        code, out, _ = self.cli('check')
        self.assertEqual(code, 1)
        self.assertIn('the option holds an email address', out)

    def test_manual_or_automatic_takes_only_a_plain_option(self):   # (c)
        r = gate("Is your driver's licence manual or automatic?", ['Automatic, and I can tow a trailer', 'Manual'])
        self.assertEqual(r['status'], 'unanswered')

    def test_the_gate_ignores_a_malformed_row_when_called_directly(self):   # (d)
        facts = owner([{'question': base.STANDARDS, 'options': YN, 'answer': 'Maybe', 'date': 'soon'}])
        r = answers.answer(base.STANDARDS, YN, facts)
        self.assertEqual((r['status'], r['basis']), ('unanswered', 'answers.owner_answers'))

    def test_right_to_work_yes_needs_full_working_rights_in_facts(self):   # (e)
        facts = copy.deepcopy(FACTS)
        facts['answers']['right_to_work']['free_text'] = 'Temporary Graduate visa (Subclass 485), limited to 20 hours a week'
        self.assertEqual(gate('Do you have the right to work in Australia?', YN, facts)['status'], 'unanswered')

    def test_no_private_words_in_any_script_or_test(self):
        words = ('rock' + 'bank', 'ram' + 'page', '19 ' + 'march', '23 ' + 'march', 'for his ' + 'visa')
        for path in sorted(SCRIPTS.glob('*.py')) + sorted(TESTS.glob('*.py')):
            text = path.read_text(encoding='utf-8').lower()
            for word in words:
                self.assertNotIn(word, text, path.name)


# ------------------------------------------------------------------ privacy F5: codes in notes and codes in short groups

class CodesInNotesAndGroups(Case):
    def test_a_mark_note_with_a_code_is_refused(self):
        self.add(entry(7))
        self.cli('next', '--route', 'SEEK', '--by', 'Grok', '--run', RUN)
        before = self.files()
        for note in ('portal showed confirmation code KX92QZ then froze', 'portal showed KX-92-QZ then froze', 'form said Q3 then froze'):
            code, _, err = self.cli('mark', 'seek-7', 'uncertain', '--by', 'Grok', '--note', note)
            self.assertEqual(code, 1, note)
            self.assertIn('a code mixing letters and digits', err)
        self.assertEqual(self.files(), before)
        for note in ('browser closed after the Civil 3D question', 'the same job as seek-1, closed at 10:05 on 14 Nov 2026'):
            self.assertEqual(q.text_problems(self.stored('seek-7'), note, FACTS, codes=True), [], note)
        self.assertIn('holds a code mixing letters and digits', q.note_problems('confirmation XQ-KZ-77 shown'))

    def test_a_ref_in_short_groups_is_refused(self):
        for ref in ('Your reference: KX-92-QZ', 'confirmation code KX 92 QZ', 'code QZ-47 shown', 'confirmation XQ-KZ-77 shown'):
            self.assertTrue(q.ref_problems('portal_confirmation', ref), ref)
        for ref in ('SEEK confirmation screen shown', 'SEEK shows applied on 2 Oct', 'SEEK receipt email 14 Nov 2026 10:05',
                    'SEEK receipt email of 2026-11-14', 'portal confirmation 1st Nov 2026, 9am', 'SEEK applied list, 3 applications shown'):
            self.assertEqual(q.ref_problems('seek_receipt_email', ref), [], ref)


# ------------------------------------------------------------------ privacy F6: staying on in Australia

class StayingOnInAustralia(unittest.TestCase):
    BASE = base.ResidencyTalk.BASE

    def test_the_reviewers_sentences_are_flagged(self):
        for sentence in ('This job would help me stay in Australia longer.', 'I need a skilled job in my nominated occupation.',
                         'I hope to stay on in Australia after my visa.', 'A job like this would help me remain in Australia long term.',
                         'I plan to settle in Australia for good.'):
            issues = checks.letter_issues(self.BASE.format(sentence))
            self.assertTrue(any('residency or migration' in i for i in issues), (sentence, issues))

    def test_no_false_hits(self):   # guard
        for sentence in ('I live in Melton VIC and can start two weeks after an offer.', 'I was nominated for a student award.'):
            issues = checks.letter_issues(self.BASE.format(sentence))
            self.assertFalse(any('residency or migration' in i for i in issues), (sentence, issues))


if __name__ == '__main__':
    unittest.main()
