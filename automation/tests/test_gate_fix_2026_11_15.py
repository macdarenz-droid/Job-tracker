"""15 Nov 2026: three real forms Grok held because the answer gate (automation/scripts/answers.py) had no answer, although
facts.json supports one. Offline.

A) SEEK, TTW (seek-95655998): the work-rights question whose only temporary option is 'I have temporary working rights',
   and 'How many years' experience do you have in your current occupation?', which Marc answered for that entry in his
   own words ('2 years', facts.json -> answers -> owner_answers) while the form shows ranges.
B) Employer portal, Coffey Testing (seek-95393367): the plain contact fields 'First', 'Last' and 'Personal Email'.

Each new rule is tested with the cases it must still refuse (exit 5 at the queue command).
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

_spec = importlib.util.spec_from_file_location('apply_queue_for_gate_fix', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)

FACTS = json.loads((SCRIPTS.parent / 'facts.json').read_text(encoding='utf-8'))
CONFIG = json.loads((SCRIPTS.parent / 'config.json').read_text(encoding='utf-8'))
NOW = datetime(2026, 11, 15, 1, 0, tzinfo=timezone.utc)
TTW = 'seek-95655998'
COFFEY = 'seek-95393367'

TTW_RTW = 'Do you have current working rights that allows you to work in the country to are applying to?'
TTW_RTW_OPTIONS = ['Yes', 'No - I need to apply for working rights', 'I have temporary working rights']
TTW_YEARS = "How many years' experience do you have in your current occupation?"
TTW_YEARS_OPTIONS = ['10+ years', '5 - 9 years', '1 - 5 Years', '0 - 1 years']
YES_NO = ['Yes', 'No']


def gate(question, options=None, facts=FACTS, **kw):
    return answers.answer(question, options or [], facts, **kw)


def with_owner_row(row, facts=FACTS):
    """facts with one more row in answers -> owner_answers."""
    f = copy.deepcopy(facts)
    f['answers'].setdefault('owner_answers', []).append(row)
    return f


def with_identity(facts=FACTS, **identity):
    f = copy.deepcopy(facts)
    f['identity'].update(identity)
    for k, v in identity.items():
        if v is None:
            f['identity'].pop(k)
    return f


class Case(unittest.TestCase):
    def ok(self, result, answer, basis=None):
        self.assertEqual((result['status'], result['answer']), ('answered', answer), result)
        if basis:
            self.assertEqual(result['basis'], basis)
        self.assertEqual(result['why'], '')

    def no(self, result):
        self.assertEqual((result['status'], result['answer']), ('unanswered', ''), result)
        self.assertTrue(result['why'], result)


class PlainTemporaryWorkRightsOption(Case):
    """facts.json -> answers -> right_to_work.choose: the graduate (Subclass 485) option; if none, the temporary visa option
    with no restriction on hours or industry. 'I have temporary working rights' is temporary and names no restriction."""

    def test_the_ttw_question_is_answered_with_the_temporary_option(self):
        for entry in (TTW, None):
            self.ok(gate(TTW_RTW, TTW_RTW_OPTIONS, entry=entry), 'I have temporary working rights', 'answers.right_to_work.choose')
        self.ok(gate('What is your current right to work status?', ['Australian citizen', 'Permanent resident', 'Temporary visa holder']),
                'Temporary visa holder')
        self.ok(gate(TTW_RTW, ['I am on a temporary visa with working rights', 'I require sponsorship']), 'I am on a temporary visa with working rights')

    def test_the_graduate_or_unrestricted_option_still_comes_first(self):
        self.ok(gate(TTW_RTW, TTW_RTW_OPTIONS + ['I have a graduate temporary work visa']), 'I have a graduate temporary work visa')
        # a graduate option that says more is refused, and the plain temporary option is never chosen instead of it
        self.no(gate(TTW_RTW, TTW_RTW_OPTIONS + ['Graduate visa 485, sponsorship required later']))
        # two unrestricted temporary options: refused, not settled by the plain one
        self.no(gate(TTW_RTW, ['Temporary visa with no restrictions', 'Temporary visa with full working rights', 'Temporary visa']))

    def test_an_option_that_says_more_than_temporary_is_not_chosen(self):
        for option in ('No - I have temporary working rights', 'Yes, I have temporary working rights', 'I have temporary working rights for 2 years',
                       'I have temporary working rights (student visa)', 'I have temporary working rights and require sponsorship',
                       'I have temporary working rights with restrictions', 'I have temporary working rights, limited to 48 hours a fortnight',
                       'I have a temporary working holiday visa', 'I have a temporary partner visa', 'Temporary bridging visa'):
            self.no(gate(TTW_RTW, ['Yes', 'No - I need to apply for working rights', option]))

    def test_a_form_that_splits_temporary_rights_is_refused(self):
        self.no(gate(TTW_RTW, TTW_RTW_OPTIONS + ['I have temporary working rights with restrictions']))   # two say temporary
        self.no(gate(TTW_RTW, TTW_RTW_OPTIONS + ['I have restricted working rights']))                    # another names a restriction
        self.no(gate(TTW_RTW, TTW_RTW_OPTIONS + ['I have limited work rights (e.g. 20 hours a week)']))

    def test_never_citizen_resident_sponsorship_or_a_bare_yes(self):
        for options in (['Yes', 'No'], ['Australian citizen', 'Permanent resident', 'I require sponsorship'],
                        ['Yes', 'No - I need to apply for working rights']):
            self.no(gate(TTW_RTW, options))


class WorkRightsOnlyHisOwnInAustralia(Case):
    """Review of 15 Nov 2026: facts.json -> answers -> right_to_work holds his own Australian work rights only. Work rights in
    another country or someone else's are never answered from it; a graduate option that says restrictions apply is not his."""

    def test_another_country_or_abroad_is_refused(self):
        graduate = ['Yes', 'No', 'Temporary graduate visa (485)']
        for text in ('Do you have working rights in New Zealand?', 'Do you have the right to work in the UK?',
                     'Are you legally authorised to work in Canada?', 'Do you have the legal right to work in Singapore?',
                     'Do you have the right to work in Australia and New Zealand?', 'Do you have working rights overseas?',
                     'Do you hold working rights outside Australia?', 'Do you have the right to work in a rail corridor?'):
            for options in (TTW_RTW_OPTIONS, graduate, ['Yes', 'No', 'Temporary'], []):
                self.no(gate(text, options))

    def test_someone_elses_work_rights_are_refused(self):
        for text in ('Does your partner have working rights in Australia?', 'Does your spouse hold working rights?',
                     'Do your dependants have working rights in Australia?'):
            for options in (TTW_RTW_OPTIONS, []):
                self.no(gate(text, options))

    def test_his_own_australian_rights_are_still_answered(self):
        self.ok(gate(TTW_RTW, TTW_RTW_OPTIONS, entry=TTW), 'I have temporary working rights')   # 'in the country to are applying to'
        self.ok(gate('What is your current working rights status in Australia?', TTW_RTW_OPTIONS), 'I have temporary working rights')
        self.ok(gate('Are you an Australian citizen, permanent resident or New Zealand citizen?', TTW_RTW_OPTIONS),
                'I have temporary working rights')
        self.ok(gate('Do you have the right to work in Australia?', YES_NO), 'Yes')
        self.ok(gate('Do you have working rights within Australia?', []), FACTS['answers']['right_to_work']['free_text'])

    def test_a_graduate_option_that_says_restrictions_apply_is_not_chosen(self):
        for option in ('485 visa with restrictions', 'Temporary Graduate visa (485) with restrictions', 'Graduate visa, with work restrictions'):
            self.no(gate('What visa do you hold?', ['Citizen', 'PR', option]))
            self.no(gate('What visa do you hold?', ['Citizen', option, 'I have temporary working rights']))   # never the plain one instead
        for option in ('485 visa with no restrictions', 'Temporary graduate visa without restrictions', 'Unrestricted temporary graduate visa',
                       'Temporary Graduate visa (485)'):
            self.ok(gate('What visa do you hold?', ['Citizen', 'PR', option]), option)


class OwnerLengthOfTimePicksTheRangeHoldingIt(Case):
    """facts.json -> answers -> owner_answers, entry seek-95655998: '2 years'. The form shows ranges; the one option whose
    range holds 2 years is '1 - 5 Years'. Never a higher option, never on the edge of two, never for another entry."""

    def test_the_ttw_question_gets_the_range_holding_two_years(self):
        self.ok(gate(TTW_YEARS, TTW_YEARS_OPTIONS, entry=TTW), '1 - 5 Years', 'answers.owner_answers')
        self.ok(gate(TTW_YEARS, entry=TTW), '2 years', 'answers.owner_answers')   # free text: his own words

    def test_an_answer_scoped_to_another_entry_or_to_none_is_not_used(self):
        for entry in (None, 'seek-95636735', 'seek-1'):
            self.no(gate(TTW_YEARS, TTW_YEARS_OPTIONS, entry=entry))

    def test_a_number_on_the_edge_of_two_options_is_refused(self):
        for given in ('1 year', '5 years', '12 months', '60 months'):
            facts = with_owner_row({'question': TTW_YEARS, 'answer': given, 'date': '2026-11-15', 'entry': 'seek-2'})
            r = gate(TTW_YEARS, TTW_YEARS_OPTIONS, facts, entry='seek-2')
            self.no(r)
            self.assertIn('more than one', r['why'])

    def test_other_lengths_pick_only_the_range_that_holds_them(self):
        for given, want in (('18 months', '1 - 5 Years'), ('two years', '1 - 5 Years'), ('6 months', '0 - 1 years'), ('7 years', '5 - 9 years'),
                            ('12 years', '10+ years'), ('2 yrs', '1 - 5 Years'), ('1.5 years', '1 - 5 Years'), ('2 years.', '1 - 5 Years')):
            facts = with_owner_row({'question': TTW_YEARS, 'answer': given, 'date': '2026-11-15', 'entry': 'seek-2'})
            self.ok(gate(TTW_YEARS, TTW_YEARS_OPTIONS, facts, entry='seek-2'), want)

    def test_never_a_higher_option(self):
        options = ['Less than 1 year', '1-2 years', 'More than 2 years']
        facts = with_owner_row({'question': TTW_YEARS, 'answer': '2 years', 'date': '2026-11-15', 'entry': 'seek-2'})
        self.ok(gate(TTW_YEARS, options, facts, entry='seek-2'), '1-2 years')
        self.no(gate(TTW_YEARS, ['Less than 2 years', 'More than 2 years'], facts, entry='seek-2'))   # exactly 2 is in neither
        self.no(gate(TTW_YEARS, ['3-5 years', '5+ years'], facts, entry='seek-2'))                    # every option is higher

    def test_only_a_plain_length_his_own_words_and_readable_options(self):
        for given in ('About 2 years', '2+ years', '1-5 years', 'Two years in drafting', '2', 'No experience', 'Yes'):
            facts = with_owner_row({'question': TTW_YEARS, 'answer': given, 'date': '2026-11-15', 'entry': 'seek-2'})
            self.no(gate(TTW_YEARS, TTW_YEARS_OPTIONS, facts, entry='seek-2'))
        facts = with_owner_row({'question': TTW_YEARS, 'answer': '2 years', 'date': '2026-11-15', 'entry': 'seek-2'})
        self.no(gate(TTW_YEARS, ['Some', '1 - 5 Years', 'Lots'], facts, entry='seek-2'))   # an option that is not a length of time
        self.no(gate(TTW_YEARS, YES_NO, facts, entry='seek-2'))
        # a row that carries the options he saw is his choice among those words: it is not read as a number
        chose = with_owner_row({'question': TTW_YEARS, 'options': ['1 year', '2 years', '3 years'], 'answer': '2 years', 'date': '2026-11-15',
                                'entry': 'seek-2'})
        self.no(gate(TTW_YEARS, TTW_YEARS_OPTIONS, chose, entry='seek-2'))
        self.ok(gate(TTW_YEARS, ['1 year', '2 years', '3 years'], chose, entry='seek-2'), '2 years')

    def test_only_for_a_how_many_years_question(self):
        text = 'How long have you lived in Melbourne?'
        facts = with_owner_row({'question': text, 'answer': '2 years', 'date': '2026-11-15', 'entry': 'seek-2'})
        self.no(gate(text, TTW_YEARS_OPTIONS, facts, entry='seek-2'))


class ContactFields(Case):
    """facts.json -> identity: name 'Marc Darenz Masarate' (short_name 'Marc'), email, phone."""

    def test_coffey_contact_fields(self):
        ident = FACTS['identity']
        for entry in (COFFEY, None):
            self.ok(gate('First', entry=entry), 'Marc', 'identity.name')
            self.ok(gate('Last', entry=entry), 'Masarate', 'identity.name')
            self.ok(gate('Personal Email', entry=entry), ident['email'], 'identity.email')

    def test_the_usual_labels_of_the_same_fields(self):
        ident = FACTS['identity']
        for label in ('First name', 'First Name:', 'First name *', 'Your first name', 'Given name', 'Forename', 'Applicant first name'):
            self.ok(gate(label), 'Marc')
        for label in ('Last name', 'Surname', 'Family name', 'Your surname', 'Last Name*'):
            self.ok(gate(label), 'Masarate')
        for label in ('Full name', 'Name', 'Your full name'):
            self.ok(gate(label), ident['name'])
        for label in ('Email', 'E-mail', 'Email address', 'Your email address'):
            self.ok(gate(label), ident['email'], 'identity.email')
        for label in ('Phone', 'Mobile', 'Mobile number', 'Phone number', 'Contact number', 'Mobile phone number'):
            self.ok(gate(label), ident['phone'], 'identity.phone')

    def test_labels_that_start_with_first_or_last_but_ask_something_else(self):
        for text in ('First aid', 'First Aid certificate', 'First Nations', 'Are you of First Nations descent?', 'Last day', 'Last employer',
                     'Last position held', 'First language', 'First preference', 'Have you done first principle build ups of pipework?',
                     'Have you attended an Interview with our recruitment team in the last 12 months?', 'Name some recent projects',
                     'Contact', 'Phone interview availability', 'Email preference'):
            r = gate(text, entry=COFFEY)
            self.assertNotIn(r['answer'], ('Marc', 'Masarate', FACTS['identity']['name'], FACTS['identity']['email'], FACTS['identity']['phone']), (text, r))

    def test_a_field_for_someone_else_never_gets_his_details(self):
        ident = FACTS['identity']
        mine = {'Marc', 'Masarate', ident['name'], ident['email'], ident['phone']}
        for text in ('Referee first name', 'Referee email', 'Referee phone', 'Manager name', 'Manager email', 'Supervisor first name',
                     'Emergency contact name', 'Emergency contact phone', 'Emergency contact number', 'Next of kin name', 'Employer name',
                     'Company name', 'Current employer', 'Employer email', 'Partner first name', "Referee's last name", 'Reference contact number',
                     'If you have been referred by a past/current TTW Employee, please specify their full name.', 'Name of your referee',
                     'Work email', 'Work phone', 'Home phone', 'Confirm email'):
            r = gate(text, entry=COFFEY)
            self.assertNotIn(r['answer'], mine, (text, r))
        for text in ('Manager email', 'Emergency contact phone', 'Employer name', 'Work email', 'Supervisor first name'):
            self.no(gate(text))

    def test_other_parts_of_the_name_stay_with_the_owner(self):
        self.ok(gate('Middle name'), 'Llanes', 'answers.owner_answers')
        for text in ('Preferred Name', 'Preferred first name', 'Legal name', 'Legal first name', 'Given names', 'First names',
                     'Given name(s)', 'Maiden name', 'Previous surname', 'Title'):
            self.no(gate(text))

    def test_with_options_on_screen_it_is_not_answered(self):
        self.no(gate('First', ['Marc', 'Other']))
        self.no(gate('Personal Email', ['Yes', 'No']))

    def test_the_name_is_split_only_when_the_facts_settle_it(self):
        self.no(gate('First', facts=with_identity(short_name='Darenz')))       # first word is not the name he goes by
        self.ok(gate('First', facts=with_identity(short_name=None)), 'Marc')
        for name in ('Marc', ''):
            for label in ('First', 'Last', 'Full name'):
                self.no(gate(label, facts=with_identity(name=name, short_name=None)))
        self.no(gate('Last', facts=with_identity(name='Juan dela Cruz', short_name='Juan')))   # the family name is two words
        self.no(gate('Last', facts=with_identity(name='Anna van Dijk', short_name='Anna')))
        self.no(gate('Personal Email', facts=with_identity(email='')))
        self.no(gate('Personal Email', facts=with_identity(email='not an address')))
        self.no(gate('Phone', facts=with_identity(phone=None)))


class TheQueueCommand(unittest.TestCase):
    """queue.py answer ID --from-file FILE on entries like the two held ones, in a temporary queue: the printed answer, exit 0,
    and an entry with no other open question goes back to OPEN."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dir, self.config, self.facts, self.prior = (self.root / 'queue', self.root / 'config.json', self.root / 'facts.json',
                                                         self.root / 'prior.json')
        q.write_json(self.config, CONFIG)
        q.write_json(self.facts, FACTS)
        q.write_json(self.prior, {'entries': []})

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = q.main(['--dir', str(self.dir), '--config', str(self.config), '--facts', str(self.facts), '--prior', str(self.prior),
                               '--now', q.iso(NOW), *args])
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def add(self, seek_id, questions, **kw):
        e = {'lane': 'drafter', 'route': 'SEEK', 'company': f'Acme {seek_id}', 'role': 'Trainee Civil Drafter', 'location': 'Melbourne VIC',
             'url': f'https://www.seek.com.au/job/{seek_id}', 'seek_id': str(seek_id), 'listed_at': '2026-11-10', 'created_by': 'test',
             'questions': questions}
        e.update(kw)
        return q.add(e, self.dir, FACTS, NOW)

    def answer(self, entry_id, question, options=None):
        path = self.root / 'q.json'
        path.write_text(json.dumps({'question': question, 'options': options or []}), encoding='utf-8')
        return self.cli('answer', entry_id, '--from-file', str(path))

    def test_ttw_questions(self):
        e = self.add(95655998, [TTW_RTW, TTW_YEARS])
        self.assertEqual(e['id'], TTW)
        self.assertEqual(self.answer(TTW, TTW_RTW, TTW_RTW_OPTIONS)[:2], (0, 'I have temporary working rights\n'))
        self.assertEqual(self.answer(TTW, TTW_YEARS, TTW_YEARS_OPTIONS)[:2], (0, '1 - 5 Years\n'))
        self.assertEqual(q.find(self.dir, TTW)[1]['status'], 'OPEN')
        other = self.add(95000001, [TTW_YEARS])   # the same question on another entry: his '2 years' was for TTW only
        code, out, err = self.answer(other['id'], TTW_YEARS, TTW_YEARS_OPTIONS)
        self.assertEqual((code, out), (5, ''))
        self.assertIn('UNANSWERED', err)

    def test_coffey_contact_fields(self):
        e = self.add(95393367, ['First', 'Last', 'Personal Email'])
        self.assertEqual(e['id'], COFFEY)
        for question, want in (('First', 'Marc'), ('Last', 'Masarate'), ('Personal Email', FACTS['identity']['email'])):
            self.assertEqual(self.answer(COFFEY, question)[:2], (0, want + '\n'))
        self.assertEqual(q.find(self.dir, COFFEY)[1]['status'], 'OPEN')
        self.assertEqual(q.validate(q.find(self.dir, COFFEY)[1], FACTS), [])   # his own email and name may stand in the public queue
        code, out, _ = self.answer(COFFEY, 'Referee email')
        self.assertNotIn(FACTS['identity']['email'], out)
        code, out, _ = self.answer(COFFEY, 'Emergency contact phone')
        self.assertEqual((code, out), (5, ''))


if __name__ == '__main__':
    unittest.main()
