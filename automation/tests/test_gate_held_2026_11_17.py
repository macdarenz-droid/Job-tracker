"""17 Nov 2026: five held entries waited on form questions the answer gate (automation/scripts/answers.py) could not
answer, although facts.json settles four of them. Offline.

A) SEEK, Newton Denny Chapelle (seek-95487722) and Bench Excavation (seek-95773573): 'Have you completed a qualification
   in engineering?' with the options 'Yes, Certificate I' ... 'Yes, Doctoral Degree': the option naming the level of his
   highest engineering qualification, the Bachelor of Science in Civil Engineering: 'Yes, Bachelor Degree'. Never
   Honours, Master or higher, never a lower level.
B) McConnell Dowell (seek-95705736): 'I accept the Privacy Statement', its one option the same words: facts.json ->
   answers -> declarations_and_consents approves the employer's privacy policy. WSP
   (wsp-laboratory-technician-in-training-7909dd6d): 'I agree with the terms and conditions' (checked / unchecked):
   terms and conditions are not among the approved declarations, so it stays with the owner (exit 5).
C) Geotechnical Testing Services (seek-95734964): 'Do you have a Certificate III in Laboratory Skills?' (Yes / No): No.
   facts.json lists his credentials completely (qualification_questions -> 'any other named qualification': otherwise
   No), and the item shares no word with any of them. What he holds keeps its answer; experience, skills and software
   questions are not this rule's.

Each new rule is tested with the cases it must still refuse (exit 5 at the queue command).

D) The review of the same day (TheReview): the first credential rule said No to anything sharing no word with what he
   holds, so 'a BSc degree', 'an overseas degree', 'a CIC ticket', 'a WWCC certificate', 'an IELTS certificate' and
   'a Certificate III in Laboratory Skills or a Bachelor degree' were all No; it now names only two shapes (a qualification
   with a field of its own, a ticket TICKETS lists). A tick box ('checked') or an option repeating the declaration agreed
   to declarations that also asked for job alerts, a talent pool, details passed to partners or a check at his cost: they
   now agree only to a declaration that holds nothing but the approved subjects, and a further clause joined to an
   approved one goes to the owner whatever the option.
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

_spec = importlib.util.spec_from_file_location('apply_queue_for_gate_held', SCRIPTS / 'queue.py')
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)

FACTS = json.loads((SCRIPTS.parent / 'facts.json').read_text(encoding='utf-8'))
CONFIG = json.loads((SCRIPTS.parent / 'config.json').read_text(encoding='utf-8'))
NOW = datetime(2026, 11, 17, 1, 0, tzinfo=timezone.utc)
YES_NO = ['Yes', 'No']

ENGINEERING = 'Have you completed a qualification in engineering?'
LEVELS = ['Yes, Certificate I', 'Yes, Certificate II', 'Yes, Certificate III', 'Yes, Certificate IV', 'Yes, Diploma',
          'Yes, Advanced Diploma', 'Yes, Associate Degree', 'Yes, Bachelor Degree', 'Yes, Bachelor Degree (Honours)',
          'Yes, Graduate Certificate', 'Yes, Graduate Diploma', 'Yes, Masters Degree', 'Yes, Doctoral Degree',
          "I have a qualification in engineering that isn't listed", "I don't have a qualification in engineering"]
HIGHER = {'Yes, Bachelor Degree (Honours)', 'Yes, Graduate Certificate', 'Yes, Graduate Diploma', 'Yes, Masters Degree',
          'Yes, Doctoral Degree'}
PRIVACY = 'I accept the Privacy Statement'
TERMS = 'I agree with the terms and conditions'
TICK = ['checked', 'unchecked']
LAB = 'Do you have a Certificate III in Laboratory Skills?'
OTHER = 'answers.qualification_questions.any other named qualification'


def gate(question, options=None, facts=FACTS, **kw):
    return answers.answer(question, options or [], facts, **kw)


def changed(edit):
    f = copy.deepcopy(FACTS)
    edit(f)
    return f


class Case(unittest.TestCase):
    def ok(self, result, answer, basis=None):
        self.assertEqual(result['status'], 'answered', result)
        self.assertEqual(result['answer'], answer, result)
        if basis:
            self.assertEqual(result['basis'], basis, result)

    def no(self, result):
        self.assertEqual(result['status'], 'unanswered', result)
        self.assertEqual(result['answer'], '', result)
        self.assertTrue(result['why'], result)

    def never_no(self, result):
        """What he may hold is never answered No by the credential rule."""
        self.assertNotEqual(result['answer'], 'No', result)
        self.assertNotEqual(result['basis'], OTHER, result)


class EngineeringQualificationLevel(Case):
    def test_the_two_held_seek_questions_get_the_bachelor_option(self):
        self.ok(gate(ENGINEERING, LEVELS), 'Yes, Bachelor Degree', 'answers.qualification_questions.engineering')
        self.ok(gate(ENGINEERING, LEVELS, entry='seek-95773573'), 'Yes, Bachelor Degree')

    def test_the_level_follows_the_field_asked(self):
        self.ok(gate('Have you completed a qualification in civil engineering?', LEVELS), 'Yes, Bachelor Degree',
                'answers.qualification_questions.civil engineering')
        self.ok(gate('Have you completed a qualification in engineering drafting?', LEVELS), 'Yes, Advanced Diploma',
                'answers.qualification_questions.engineering drafting or design')
        self.ok(gate('Do you have a degree in civil engineering?', LEVELS), 'Yes, Bachelor Degree')

    def test_never_a_higher_option(self):
        for options in (LEVELS, [o for o in LEVELS if o != 'Yes, Bachelor Degree'],
                        ['Yes, Masters Degree', 'Yes, Doctoral Degree', "I don't have a qualification in engineering"],
                        ['Yes, Bachelor Degree (Honours)', 'Yes, Masters Degree', 'No']):
            self.assertNotIn(gate(ENGINEERING, options)['answer'], HIGHER, options)

    def test_without_his_own_level_on_screen_it_is_the_owners(self):
        self.no(gate(ENGINEERING, [o for o in LEVELS if o != 'Yes, Bachelor Degree']))   # no lower level instead
        self.no(gate(ENGINEERING, ['Yes, Masters Degree', 'Yes, Doctoral Degree', "I don't have a qualification in engineering"]))
        self.no(gate(ENGINEERING, ['Yes, Bachelor Degree', "Yes, Bachelor's degree", 'No']))   # two that say it
        self.no(gate(ENGINEERING, ['Yes - Bachelor degree or higher', 'No']))                   # says more than the level

    def test_a_field_he_has_no_qualification_in_is_not_answered_from_the_levels(self):
        self.no(gate('Have you completed a qualification in mechanical engineering?', LEVELS))
        self.no(gate('Have you completed a qualification in nursing?', LEVELS))

    def test_a_plain_yes_is_still_the_plain_yes(self):
        self.ok(gate(ENGINEERING, YES_NO), 'Yes')
        self.ok(gate(ENGINEERING, ['Yes', 'Yes, Bachelor Degree', 'No']), 'Yes')

    def test_the_level_comes_from_facts_education(self):
        no_degree = changed(lambda f: f.__setitem__('education', [e for e in f['education'] if 'Bachelor' not in e['qualification']]))
        self.no(gate(ENGINEERING, LEVELS, facts=no_degree))
        honours = changed(lambda f: f['education'][1].__setitem__('qualification', 'Bachelor of Science in Civil Engineering (Honours)'))
        self.ok(gate(ENGINEERING, LEVELS, facts=honours), 'Yes, Bachelor Degree (Honours)')
        not_engineering = changed(lambda f: f['answers']['qualification_questions'].__setitem__('engineering', 'Not on record: skip and report'))
        self.no(gate(ENGINEERING, LEVELS, facts=not_engineering))


class DeclarationsAsTheyAppearOnTheForm(Case):
    def test_mcconnell_privacy_statement_is_accepted(self):
        self.ok(gate(PRIVACY, [PRIVACY]), PRIVACY, 'answers.declarations_and_consents')
        self.ok(gate(PRIVACY + '.', [PRIVACY, 'I do not accept the Privacy Statement']), PRIVACY)

    def test_wsp_terms_and_conditions_stay_with_the_owner(self):
        r = gate(TERMS, TICK)
        self.no(r)
        self.assertIn('terms and conditions', r['why'])
        self.no(gate(TERMS, [TERMS]))
        self.no(gate('I agree to the Terms of Use', ['I agree']))
        self.no(gate('I declare that the information I have provided is true and correct and I agree to the terms and conditions', ['Yes']))

    def test_an_approved_tick_box_is_checked(self):
        self.ok(gate('I agree to the privacy policy', TICK), 'checked')
        self.ok(gate('I declare the information provided is true and correct', TICK), 'checked')

    def test_the_same_words_agree_only_for_an_approved_declaration_in_his_own_voice(self):
        for text in ('I consent to my details being shared with third parties', 'I agree to receive marketing emails',
                     'I consent to a medical assessment'):
            self.no(gate(text, [text]))
        self.no(gate('Do you accept the Privacy Statement?', [PRIVACY]))
        no_privacy = changed(lambda f: f['answers'].__setitem__(
            'declarations_and_consents', 'Yes to: a declaration that the information given is true and correct. Any other declaration '
            'or consent: skip and report.'))
        self.no(gate(PRIVACY, [PRIVACY], facts=no_privacy))


class CredentialsHeDoesNotHold(Case):
    def test_geotechnical_testing_services_certificate_is_no(self):
        self.ok(gate(LAB, YES_NO), 'No', OTHER)
        self.ok(gate(LAB), 'No', OTHER)

    def test_other_named_credentials_he_lacks(self):
        for text in ('Do you have a Certificate IV in Work Health and Safety?', 'Do you hold a current First Aid certificate?',
                     'Do you hold a forklift licence?', 'Do you hold a nuclear gauge licence?', 'Do you hold a Working at Heights ticket?',
                     'Do you have a Masters degree?', 'Do you have a Masters degree in civil engineering?', 'Do you have a Diploma of Surveying?',
                     'Do you hold a Cert III in Laboratory Skills or Cert IV in Laboratory Techniques?',
                     'Do you have a Certificate III in Laboratory Skills (MSL30122)?'):
            self.ok(gate(text, YES_NO), 'No', OTHER)

    def test_what_he_holds_keeps_its_answer(self):
        self.ok(gate('Do you have a White Card?', YES_NO), 'Yes', 'answers.white_card')
        self.ok(gate('Do you hold a Construction Induction Safety certificate (White Card)?', YES_NO), 'Yes', 'answers.white_card')
        self.ok(gate("Do you have a current Australian driver's licence?", YES_NO), 'Yes', 'answers.drivers_licence')
        self.ok(gate('Do you have a current police check?', YES_NO), 'Yes', 'answers.police_check')
        self.ok(gate("Do you have a manual driver's licence?", YES_NO), 'No', 'answers.manual_licence')
        for text in ('Do you have a Working with Children Check?', 'Do you have a Working with Children Check certificate?',
                     'Do you have an Advanced Diploma of Civil Construction Design?', 'Do you have an Advanced Diploma?',
                     'Do you have a Diploma of Civil Engineering?', 'Do you have a Certificate III in Civil Construction?',
                     'Do you have an engineering degree?', 'Do you have a degree?', 'Do you hold a Bachelor degree?',
                     'Do you have a university degree?', 'Do you hold a BSCE degree?', 'Do you hold a RII60520 qualification certificate?'):
            self.never_no(gate(text, YES_NO))

    def test_a_driving_licence_in_other_words_is_never_this_rule(self):
        for text in ('Do you have a manual licence?', 'Do you have a full licence?', 'Do you have a C class licence?',
                     'Do you have a NSW licence?', 'Do you have an automatic licence?', 'Do you have an open licence?',
                     'Do you have a Victorian licence?', 'Do you have a C licence?', 'Do you hold an HR licence?',
                     'Do you hold an MR licence?', 'Do you hold a truck licence?', 'Do you hold a heavy rigid licence?'):   # no class on record
            r = gate(text, YES_NO)
            self.never_no(r)
            self.assertNotEqual(r['answer'], 'Yes', r)   # not settled here either: unchanged, the owner's
            self.no(r)

    def test_a_join_with_something_he_lacks_is_not_answered_from_the_white_card(self):
        for text in ('Do you have a First Aid certificate and a White Card?', 'Do you hold a Certificate IV in WHS and a White Card?',
                     'Do you hold a White Card and a First Aid certificate?', 'Do you hold a forklift licence & White Card?'):
            self.no(gate(text, YES_NO))

    def test_experience_skills_and_software_are_not_this_rule(self):
        for text in ('Do you have laboratory skills?', 'Do you have experience in laboratory testing?',
                     'Do you have an AutoCAD certification?', 'Do you have a 12d Model licence?', 'Do you have a Revit certificate?',
                     'Do you have knowledge of licence conditions?', 'Do you have skills in certificate testing?'):
            r = gate(text, YES_NO)
            self.assertNotEqual(r['basis'], OTHER, (text, r))
            self.no(r)

    def test_an_alternative_left_open_stays_with_the_owner(self):
        for text in ('Do you have a Certificate III in Laboratory Skills or equivalent?',
                     'Do you have a Certificate III in Laboratory Skills, or are you willing to obtain one?',
                     'Do you have a Certificate III in Laboratory Skills or working towards one?',
                     'Do you have a Certificate III or higher?', 'Do you hold a related certificate?',
                     'Do you have a Certificate III in Laboratory Skills? If not, are you willing to obtain one?'):
            self.no(gate(text, YES_NO))

    def test_only_a_plain_no_option(self):
        self.no(gate(LAB, ['Yes', 'No - but willing to obtain']))
        self.no(gate(LAB, ['Yes', 'No', 'NO']))

    def test_only_while_facts_list_his_credentials_completely(self):
        unlisted = changed(lambda f: f['answers']['qualification_questions'].pop('any other named qualification'))
        self.no(gate(LAB, YES_NO, facts=unlisted))
        open_ended = changed(lambda f: f['answers']['qualification_questions'].__setitem__(
            'any other named qualification', 'Not on record: skip and report'))
        self.no(gate(LAB, YES_NO, facts=open_ended))
        holds_it = changed(lambda f: f['education'].append({'qualification': 'Certificate III in Laboratory Skills', 'completed': '2026'}))
        self.never_no(gate(LAB, YES_NO, facts=holds_it))


class TheReview(Case):
    """17 Nov 2026 review: questions that tried to make the new rules give an answer facts.json does not support."""

    def test_a_credential_described_abbreviated_or_not_a_qualification_is_never_no(self):
        for text in ('Do you have a Certificate III in Laboratory Skills or an Advanced Diploma?',
                     'Do you have a Certificate III in Laboratory Skills or a Bachelor degree?',
                     'Do you have a Certificate III in Laboratory Skills or a tertiary qualification?',
                     'Do you have an overseas degree?', 'Do you have a Philippine degree?', 'Do you have a foreign degree?',
                     'Do you have an international degree?', 'Do you have an Australian degree?', 'Do you have a STEM degree?',
                     'Do you have a 4 year degree?', 'Do you have a technical degree?', 'Do you have a uni degree?', 'Do you have a college degree?',
                     'Do you have a degree from an accredited university?', 'Do you have an AQF certificate?',
                     'Do you have an Australian qualification certificate?', 'Do you have a VET certificate?', 'Do you have a TAFE diploma?',
                     'Do you have a site ticket?', 'Do you have a site safety ticket?', 'Do you have a safety certificate?',
                     'Do you hold an OHS ticket?', 'Do you hold a WHS certificate?', 'Do you hold a BSc degree?', 'Do you hold a BS degree?',
                     'Do you hold a CE degree?', 'Do you hold an Adv Dip certificate?', 'Do you hold a CIC ticket?', 'Do you hold a GCIT ticket?',
                     'Do you hold a CPCWHS1001 certificate?', 'Do you hold a CPCCWHS1001 ticket?', 'Do you hold a WWC certificate?',
                     'Do you hold a WWCC certificate?', 'Do you hold a NPC certificate?', 'Do you have an IELTS certificate?',
                     'Do you have a PTE certificate?', 'Do you hold an English certificate?', 'Do you have a skills assessment certificate?',
                     'Do you have a VETASSESS accreditation?', 'Do you have a COVID vaccination certificate?', 'Do you have a birth certificate?',
                     'Do you have an insurance certificate?', 'Do you have a Year 12 certificate?', 'Do you have an Honours degree?',
                     'Do you have a Bachelor (Honours) degree?', 'Do you have an Excel certificate?', 'Do you have a SpaceGass licence?',
                     'Do you hold a Before You Dig certificate?', 'Do you have a work licence?', 'Do you have a Diploma?',
                     'Do you have a Certificate IV in Civil Construction?', 'Do you have a Certificate IV in AutoCAD?',
                     'Do you have a First Aid certificate and a forklift licence?', 'Do you have a First Aid certificate (CPCWHS1001)?'):
            self.never_no(gate(text, YES_NO))
            self.never_no(gate(text))

    def test_the_review_list(self):
        self.no(gate('Do you have a Certificate IV in Civil Construction?', YES_NO))   # shares his field: the owner's
        self.ok(gate('Do you hold a White Card?', YES_NO), 'Yes', 'answers.white_card')
        self.ok(gate('Do you have a forklift licence?', YES_NO), 'No', OTHER)
        self.ok(gate("Do you have a manual driver's licence?", YES_NO), 'No', 'answers.manual_licence')
        r = gate('Do you have experience with SpaceGass?', YES_NO)
        self.assertNotEqual(r['basis'], OTHER, r)   # the software rule's, not this one's
        for options in (['Yes, Master degree', 'Yes, Bachelor degree (Honours)', 'No'], ['Yes, Bachelor degree with Honours', 'No'],
                        ['Yes, Masters Degree', 'Yes, Doctoral Degree', 'No']):
            self.no(gate(ENGINEERING, options))
        self.ok(gate(ENGINEERING, ['Yes, Bachelor degree (Honours)', 'Yes, Bachelor degree', 'Yes, Master degree', 'No']), 'Yes, Bachelor degree')
        for options in (LEVELS, YES_NO):
            r = gate('Have you completed a qualification in structural engineering?', options)
            self.no(r)
        self.no(gate('Have you completed a qualification in civil/structural engineering?', LEVELS))
        self.no(gate('Have you completed a qualification in civil or structural engineering?', LEVELS))   # 'civil' alone is not named
        self.ok(gate('Have you completed a qualification in structural or civil engineering?', LEVELS), 'Yes, Bachelor Degree',
                'answers.qualification_questions.civil engineering')   # civil engineering is one of the two
        for text in ('Have you completed a qualification in postgraduate engineering?', 'Have you completed a postgraduate qualification in engineering?',
                     'Have you completed a qualification in engineering at Masters level?'):
            self.assertNotIn(gate(text, LEVELS)['answer'], HIGHER | {'Yes, Bachelor Degree'}, text)

    def test_a_qualification_in_a_field_he_answers_yes_to_is_never_no(self):
        # facts.json -> qualification_questions: 'engineering drafting or design': Yes (his Advanced Diploma)
        for text in ('Have you completed a qualification in drafting?', 'Have you completed a qualification in design?'):
            self.never_no(gate(text, YES_NO))

    def test_a_declaration_that_asks_for_more_is_the_owners_whatever_the_option(self):
        for text in ('I accept the Privacy Statement and agree to receive marketing communications',
                     'I accept the Privacy Statement and consent to receiving job alerts',
                     'I accept the Privacy Statement and subscribe to the newsletter',
                     'I accept the Privacy Statement and agree to be contacted about future opportunities',
                     'I accept the Privacy Statement and agree to join the talent community',
                     'I accept the Privacy Statement and consent to my data being given to our partners',
                     'I accept the Privacy Statement and consent to my details being passed to other employers',
                     'I accept the Privacy Statement and agree to my information being transferred to related entities',
                     'I accept the Privacy Statement and agree to work weekends', 'I accept the Privacy Statement and the Code of Conduct',
                     'I agree to a police check at my cost', 'I agree to pay for a police check', 'I consent to a police check and will pay the fee',
                     'I agree to a police check and a working with children check', 'I agree to the privacy policy and to being contacted by recruiters',
                     'I agree to the privacy policy and to receive our newsletter', 'I agree to the privacy policy and the website terms',
                     'I accept the privacy policy and the conditions of employment', 'I agree to the privacy policy and the user agreement',
                     'I declare the information I have provided is true and correct and agree to an online test',
                     'I declare the information I have provided is true and correct and I agree to a police check at my cost',
                     'I agree with the terms and conditions', 'I agree to the Terms of Use'):
            for options in ([text], ['I agree'], YES_NO, TICK, []):
                self.no(gate(text, options))

    def test_an_approved_declaration_alone_still_agrees(self):
        self.ok(gate(PRIVACY, TICK), 'checked')
        self.ok(gate('I agree to the privacy policy', ['I agree to the privacy policy']), 'I agree to the privacy policy')
        self.ok(gate('I declare the information provided is true and correct', ['I declare the information provided is true and correct']),
                'I declare the information provided is true and correct')
        self.ok(gate('I declare the information I have provided is true and correct and I consent to reference checks', ['I agree']), 'I agree')
        self.ok(gate('Do you agree with the privacy policy?', TICK), 'checked')
        self.ok(gate('I consent to a police check', TICK), 'checked')
        self.ok(gate('I acknowledge and agree to the privacy policy', ['I agree']), 'I agree')   # a verb-only clause adds nothing
        self.no(gate('I acknowledge and agree to work weekends and the privacy policy', ['I agree']))
        long = ('I acknowledge that all information I provided in this application is true and correct to the best of my knowledge and '
                'that any incorrect or misleading information may lead to disqualification, or if appointed, to termination of Employment?')
        self.ok(gate(long, TICK), 'checked')
        for options in (TICK, ['I agree'], YES_NO):   # more words than an approved declaration: the owner's
            self.no(gate('I accept the Privacy Statement of Acme Pty Ltd', options))
            self.no(gate('I agree to work weekends and the privacy policy', options))


class TheQueueCommand(unittest.TestCase):
    """queue.py answer ID --from-file FILE with each held entry's exact question and options, in a temporary queue: exit 0
    and the answer for four of them (the entry goes back to OPEN), exit 5 for WSP's terms and conditions."""

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

    def add(self, seek_id, question):
        e = {'lane': 'technician', 'route': 'SEEK', 'company': f'Acme {seek_id}', 'role': 'Trainee Technician', 'location': 'Melbourne VIC',
             'url': f'https://www.seek.com.au/job/{seek_id}', 'seek_id': str(seek_id), 'listed_at': '2026-11-10', 'created_by': 'test',
             'questions': [question]}
        return q.add(e, self.dir, FACTS, NOW)['id']

    def answer(self, entry_id, question, options):
        path = self.root / 'q.json'
        path.write_text(json.dumps({'question': question, 'options': options}), encoding='utf-8')
        return self.cli('answer', entry_id, '--from-file', str(path))

    def test_the_five_held_questions(self):
        for seek_id, question, options, want in ((95487722, ENGINEERING, LEVELS, 'Yes, Bachelor Degree'),
                                                 (95773573, ENGINEERING, LEVELS, 'Yes, Bachelor Degree'),
                                                 (95705736, PRIVACY, [PRIVACY], PRIVACY),
                                                 (95734964, LAB, YES_NO, 'No')):
            entry = self.add(seek_id, question)
            self.assertEqual(self.answer(entry, question, options)[:2], (0, want + '\n'), entry)
            e = q.find(self.dir, entry)[1]
            self.assertEqual((e['status'], e['ask_owner']), ('OPEN', ''), entry)
            self.assertEqual(q.validate(e, FACTS), [], entry)
        wsp = self.add(96985001, TERMS)
        code, out, err = self.answer(wsp, TERMS, TICK)
        self.assertEqual((code, out), (5, ''))
        self.assertIn('terms and conditions', err)
        self.assertEqual(q.find(self.dir, wsp)[1]['status'], 'ASK_OWNER')


if __name__ == '__main__':
    unittest.main()
