"""The rules of 13 Nov 2026 in the scripts: duplicates, statuses and form questions, writing checks,
the journal's end rows, compact JSON, the compact PDFs, and role lanes. Offline: nothing here calls a service."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import common  # noqa: E402
import answers as gate  # noqa: E402
import checks  # noqa: E402
import compact_pdf  # noqa: E402
import email_html  # noqa: E402
import journal  # noqa: E402
import publish  # noqa: E402
import seek  # noqa: E402
import tracker  # noqa: E402

CONFIG = common.CONFIG
STATUSES = CONFIG['statuses']
TODAY = datetime(2026, 11, 13, tzinfo=timezone.utc)


def days_ago(n):
    return (TODAY - timedelta(days=n)).strftime('%Y-%m-%d')


def index(*rows, receipts=()):
    with mock.patch.object(tracker, 'prior_outreach', return_value=list(receipts)):
        return tracker.dedupe_index({'applications': [], 'leads': [], 'manual_entries': list(rows)})


def dup(candidate, idx):
    return tracker.check_duplicate(candidate, idx, today=TODAY)


# ---------------------------------------------------------------------------------------------- 1. duplicates
class DuplicateRule(unittest.TestCase):
    ADVERT = {'company': 'Northgate Civil Design Pty Ltd', 'title': 'Junior Civil Drafter', 'url': 'https://www.seek.com.au/job/95900001'}

    def test_same_seek_id_is_always_a_duplicate(self):
        for status in ('PREPARED_NOT_SENT', 'READY_SEEK', 'READY_JEREMIE_SEEK', 'HELD_ELIGIBILITY_UNCONFIRMED', 'ASK_OWNER', 'SENT', 'EXPIRED'):
            idx = index({'company': 'Another Name', 'role': 'Another Title', 'status': status, 'job_url': 'https://au.seek.com/job/95900001?ref=x', 'created_at': '2025-01-01'})
            blocked, why, _ = dup(self.ADVERT, idx)
            self.assertTrue(blocked, status); self.assertIn('SEEK', why)
        blocked, _, _ = dup({'seek_id': '95900001', 'company': 'X', 'title': 'Y'}, idx)
        self.assertTrue(blocked)

    def test_same_url_is_always_a_duplicate(self):
        idx = index({'company': 'Harbourline', 'role': 'Cadet Drafter', 'status': 'READY_EMPLOYER_PORTAL', 'job_url': 'https://www.harbourline.example/careers/cadet-drafter/'})
        blocked, why, _ = dup({'company': 'Harbourline Consulting', 'title': 'Cadet Civil Drafter', 'url': 'https://harbourline.example/careers/cadet-drafter'}, idx)
        self.assertTrue(blocked); self.assertIn('URL', why)

    def test_unsubmitted_pack_for_the_same_employer_and_title_does_not_block_a_new_advert(self):
        # The defect: 94 to 107 adverts were thrown away because a pack nobody submitted existed for the employer.
        for status in ('LEAD', 'PREPARED_NOT_SENT', 'READY_SEEK', 'READY_EMPLOYER_PORTAL', 'READY_EMPLOYER_FORM', 'READY_JEREMIE_SEEK',
                       'READY_JEREMIE_EMPLOYER_PORTAL', 'HELD_MANDATORY_REQUIREMENTS', 'ASK_OWNER', 'EXPIRED'):
            idx = index({'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': status, 'job_url': 'https://www.seek.com.au/job/95000111', 'checked_at': days_ago(3), 'created_at': days_ago(3)})
            blocked, why, notes = dup(self.ADVERT, idx)
            self.assertFalse(blocked, status); self.assertEqual(why, 'new')
            self.assertTrue(any('unsubmitted lead' in n for n in notes), status)

    def test_every_real_submission_or_outcome_blocks_the_same_role_inside_the_window(self):
        for status in ('SENT', 'EOI_SENT', 'DELIVERY_FAILED', 'MANUAL_APPLIED', 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED', 'APPLICATION_UNDER_REVIEW', 'INTERVIEW', 'OFFER', 'REJECTED'):
            idx = index({'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': status, 'sent_at': days_ago(30) + 'T01:00:00Z', 'job_url': 'https://www.seek.com.au/job/95000111'})
            blocked, why, _ = dup(self.ADVERT, idx)
            self.assertTrue(blocked, status); self.assertIn(status, why); self.assertIn(days_ago(30), why)

    def test_the_block_runs_from_the_day_it_was_sent_not_the_day_the_lead_was_made(self):
        limit = CONFIG['limits']['repeat_block_days']  # 90 on 13 Nov 2026; the test follows whatever config says
        made_long_ago_sent_last_week = {'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': 'SENT', 'created_at': days_ago(200), 'checked_at': days_ago(200), 'sent_at': days_ago(7)}
        self.assertTrue(dup(self.ADVERT, index(made_long_ago_sent_last_week))[0])
        touched_yesterday_sent_long_ago = {'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': 'MANUAL_APPLIED', 'created_at': days_ago(1), 'updated_at': days_ago(1), 'applied_date': days_ago(limit + 1)}
        blocked, _, notes = dup(self.ADVERT, index(touched_yesterday_sent_long_ago))
        self.assertFalse(blocked); self.assertTrue(any('outside the repeat block' in n for n in notes))
        self.assertTrue(dup(self.ADVERT, index({'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': 'SENT', 'sent_at': days_ago(limit - 1)}))[0])
        self.assertFalse(tracker.check_duplicate(self.ADVERT, index({'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': 'SENT', 'sent_at': days_ago(40)}), repeat_block_days=30, today=TODAY)[0])

    def test_a_submission_with_no_date_blocks(self):
        blocked, why, _ = dup(self.ADVERT, index({'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': 'EOI_SENT'}))
        self.assertTrue(blocked); self.assertIn('no date', why)

    def test_a_different_role_at_an_employer_he_applied_to_is_allowed_with_a_note(self):
        idx = index({'company': 'Northgate Civil Design Pty Ltd', 'role': 'Graduate Civil Engineer', 'status': 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED', 'applied_date': days_ago(12)})
        blocked, why, notes = dup(self.ADVERT, idx)
        self.assertFalse(blocked); self.assertEqual(why, 'new')
        self.assertEqual(len(notes), 1)
        for part in ('applied before', 'different role', 'Graduate Civil Engineer', 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED', days_ago(12)):
            self.assertIn(part, notes[0])

    def test_seek_receipts_in_prior_outreach_count_as_submissions(self):
        receipts = [{'date': days_ago(20), 'company': 'Kestrel Land Consultants', 'role': 'Graduate Civil Engineer - Wodonga', 'gmail_message_id': 'abc'}]
        idx = index(receipts=receipts)
        blocked, why, _ = dup({'company': 'Kestrel Land Consultants Pty Ltd', 'title': 'Graduate Civil Engineer', 'seek_id': '95900002'}, idx)
        self.assertTrue(blocked); self.assertIn('Wodonga', why)  # a place added to the title is still the same role
        blocked, _, notes = dup({'company': 'Kestrel Land Consultants', 'title': 'Survey Draftsperson', 'seek_id': '95900003'}, idx)
        self.assertFalse(blocked); self.assertIn('Graduate Civil Engineer - Wodonga', notes[0])
        old = index(receipts=[{**receipts[0], 'date': days_ago(120)}])
        self.assertFalse(dup({'company': 'Kestrel Land Consultants', 'title': 'Graduate Civil Engineer', 'seek_id': '95900002'}, old)[0])

    def test_employer_name_normalisation_is_kept(self):
        idx = index({'company': 'Bramwell Australia Pty Ltd', 'role': 'Junior Civil Engineer', 'status': 'REJECTED', 'applied_date': days_ago(10)})
        for name in ('Bramwell Australia', 'BRAMWELL', 'Bramwell Group', 'The Bramwell Australia Pty. Ltd.'):
            self.assertTrue(dup({'company': name, 'title': 'Junior Civil Engineer', 'seek_id': '1'}, idx)[0], name)
        self.assertFalse(dup({'company': 'Bramley Civil Australia', 'title': 'Junior Civil Engineer', 'seek_id': '1'}, idx)[0])

    def test_same_role_reads_titles_loosely_but_not_too_loosely(self):
        self.assertTrue(tracker.same_role('Graduate Civil Engineer', 'Graduate Civil Engineer - Wodonga'))
        self.assertTrue(tracker.same_role('Engineering Technician (employer portal application received)', 'Engineering Technician'))
        self.assertTrue(tracker.same_role('Civil Site and Project Engineers', 'civil site and project engineer'))
        self.assertFalse(tracker.same_role('Civil Engineer', 'Civil Engineering Draftsperson'))
        self.assertFalse(tracker.same_role('Graduate Civil Engineer', 'Civil Engineer'))
        self.assertFalse(tracker.same_role('Engineer', 'Engineer - Geotechnical'))
        self.assertFalse(tracker.same_role('', ''))

    def test_a_speculative_enquiry_is_blocked_while_any_application_to_that_employer_is_in_the_window(self):
        idx = index({'company': 'Ashgrove Consulting', 'role': 'Graduate Civil Engineer', 'status': 'SENT', 'sent_at': days_ago(15)})
        speculative = {'company': 'Ashgrove Consulting', 'title': 'Speculative enquiry: junior civil drafter', 'url': 'https://ashgrove.example/careers', 'application_type': 'SPECULATIVE_ENQUIRY'}
        blocked, why, _ = dup(speculative, idx)
        self.assertTrue(blocked); self.assertIn('speculative', why)
        self.assertFalse(dup({**speculative, 'application_type': 'ADVERTISED_VACANCY'}, idx)[0])

    def test_add_records_writes_the_earlier_application_onto_the_new_record(self):
        state = {'applications': [{'company': 'Tallowood', 'role': 'Civil Site and Project Engineers', 'status': 'SENT', 'sent_at': '2026-10-07T00:00:00Z'}], 'leads': [], 'manual_entries': []}
        new = tracker.new_record({'company': 'Tallowood Civil', 'role': 'Trainee Laboratory Technician', 'status': STATUSES['ready_seek'], 'job_url': 'https://www.seek.com.au/job/95900009', 'notes': 'Lab at the depot.'})
        again = tracker.new_record({'company': 'Tallowood', 'role': 'Civil Site and Project Engineer', 'status': STATUSES['ready_seek'], 'job_url': 'https://www.seek.com.au/job/95900010'})
        with mock.patch.object(tracker, 'prior_outreach', return_value=[]), mock.patch.object(tracker, 'get_state', return_value=(4, state)), \
                mock.patch.object(tracker, 'put_state', return_value=(200, {'version': 5})), mock.patch.object(tracker, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = TODAY
            out = tracker.add_records([new, again])
        self.assertEqual(out['result']['added'], [new['id']])
        self.assertIn('already applied for this role', out['result']['skipped'][0][1])
        saved = state['manual_entries'][0]
        self.assertTrue(saved['notes'].startswith('Lab at the depot.'))
        self.assertIn('applied before, different role, allowed: Civil Site and Project Engineers · SENT · 2026-10-07', saved['notes'])
        self.assertEqual(new['notes'], 'Lab at the depot.')  # the caller's copy is left alone, so a retry adds the note once


# ------------------------------------------------------------------------------- 2. statuses, records, form questions
SEEK_QUESTIONS = ['Which of the following statements best describes your right to work in Australia?',
                  "How many years' experience do you have as a civil drafter?",
                  'Which of the following CAD software do you have experience with?',
                  "Do you have a current Australian driver's licence?",
                  "What's your expected annual base salary?"]


def pack(route='SEEK', questions=SEEK_QUESTIONS, **draft_extra):
    cand = {'seek_id': '95900020', 'source': 'seek', 'company': 'Wattlebrook Land Development', 'title': 'Junior Civil Drafter', 'location': 'Croydon VIC',
            'url': 'https://www.seek.com.au/job/95900020', 'listed_at': '2026-11-12T03:00:00Z', 'screening_questions': list(questions)}
    screen = {'open': True, 'percent': 78, 'mandatory_unmet': [], 'rationale': ['Junior role; AutoCAD and Civil 3D subdivision drawings match the Advanced Diploma.'],
              'gaps': ['12d is listed as desirable'], 'caution': 'Rough fit, not a forecast.', 'apply_instructions': 'Apply on SEEK'}
    contact = {'contact_confidence': 'published_inbox', 'recipient_email': 'careers@wattlebrook.example', 'recipient_role': 'Careers inbox',
               'contact_evidence_url': 'https://wattlebrook.example/careers', 'company_url': 'https://wattlebrook.example'}
    draft = {'route': route, 'subject': 'Junior Civil Drafter, Marc Masarate', 'email_body': 'Hello,\n\nShort note.\n\nKind regards,\nMarc Darenz Masarate',
             'letter': {'paragraphs': ['One.', 'Two.', 'Three.']}, 'notes': 'Advert asks for a resume and a short letter.', **draft_extra}
    return cand, screen, contact, draft


class StatusesAndRecords(unittest.TestCase):
    def test_new_status_names_come_from_config_and_legacy_names_still_read(self):
        self.assertEqual((STATUSES['ready_seek'], STATUSES['ready_portal'], STATUSES['ready_form'], STATUSES['ask_owner']),
                         ('READY_SEEK', 'READY_EMPLOYER_PORTAL', 'READY_EMPLOYER_FORM', 'ASK_OWNER'))
        self.assertEqual(publish.READY, {'SEEK': 'READY_SEEK', 'EMPLOYER_PORTAL': 'READY_EMPLOYER_PORTAL', 'EMPLOYER_FORM': 'READY_EMPLOYER_FORM'})
        for old, new in (('READY_JEREMIE_SEEK', 'READY_SEEK'), ('READY_JEREMIE_EMPLOYER_PORTAL', 'READY_EMPLOYER_PORTAL'), ('READY_JEREMIE_EMPLOYER_FORM', 'READY_EMPLOYER_FORM'),
                         ('READY_SEEK', 'READY_SEEK'), ('SENT', 'SENT'), (None, '')):
            self.assertEqual(common.canonical_status(old), new)
        self.assertNotIn('JEREMIE', (SCRIPTS / 'publish.py').read_text(encoding='utf-8').replace('READY_JEREMIE_*', ''))

    def test_one_channel_no_double_touch(self):
        cand, screen, contact, draft = pack('SEEK')
        self.assertEqual(publish.route_status(draft, contact, cand), ('READY_SEEK', 'SEEK'))
        rec = publish.build_record('r1', cand, screen, contact, draft)
        self.assertEqual(rec['status'], 'READY_SEEK')
        for field in ('recipient_email', 'contact_email', 'email_body', 'subject', 'contact_evidence_url'):
            self.assertNotIn(field, rec)
        self.assertNotIn('ouble touch', json.dumps(rec)); self.assertNotIn('Jeremie', json.dumps(rec))
        self.assertEqual(checks.record_issues({**rec, 'attachments': [{'kind': 'resume'}, {'kind': 'cover'}]}, require_uploaded=False), [])
        with_email = {**rec, 'attachments': [{'kind': 'resume'}, {'kind': 'cover'}], 'recipient_email': 'careers@wattlebrook.example', 'email_body': 'Hello,\n\nShort note.'}
        self.assertTrue(any('one channel' in i for i in checks.record_issues(with_email, require_uploaded=False)))
        self.assertEqual(publish.route_status({**draft, 'route': 'EMAIL'}, contact, cand), ('PREPARED_NOT_SENT', 'EMAIL'))
        self.assertEqual(publish.route_status({**draft, 'route': 'EMAIL'}, {'contact_confidence': 'none'}, cand), ('PREPARED_NOT_SENT', 'EMAIL'))  # never SEEK instead: see Routes

    def test_how_found_and_call_prep_are_written_once_and_fit_is_not_copied_into_the_score(self):
        cand, screen, contact, draft = pack('SEEK')
        rec = publish.build_record('r1', cand, screen, contact, draft)
        self.assertNotIn('how_found', rec); self.assertNotIn('call_prep', rec)
        self.assertEqual(rec['notes'].count('IF THEY CALL, LIKELY QUESTIONS'), 1)
        self.assertEqual(rec['notes'].count('Found on SEEK (listed 2026-11-12)'), 1)
        self.assertEqual(json.dumps(rec, ensure_ascii=False).count('Tell me about your site experience'), 1)
        self.assertEqual(rec['fit'], screen['rationale'])
        self.assertEqual(rec['match_score'], {'percent': 78, 'method': CONFIG['fit']['method'], 'caution': 'Rough fit, not a forecast.'})
        self.assertEqual(json.dumps(rec).count('Junior role; AutoCAD and Civil 3D subdivision drawings'), 1)

    def test_all_questions_answerable_is_ready(self):
        rec = publish.build_record('r1', *pack('SEEK'))
        self.assertEqual(rec['status'], 'READY_SEEK'); self.assertNotIn('ask_owner', rec)

    def test_a_question_with_no_standing_answer_makes_the_record_ask_owner_with_the_question(self):
        english = 'How would you rate your English language skills?'
        infrastructure = 'Do you have experience working on civil infrastructure projects?'
        rec = publish.build_record('r1', *pack('SEEK', SEEK_QUESTIONS + [english, infrastructure]))
        self.assertEqual(rec['status'], 'ASK_OWNER')
        self.assertEqual(rec['ask_owner']['then'], 'READY_SEEK')
        self.assertEqual([a['question'] for a in rec['ask_owner']['questions']], [english, infrastructure])
        self.assertIn('ASK OWNER: ' + english, rec['notes'])
        self.assertEqual(checks.record_issues({**rec, 'attachments': [{'kind': 'resume'}, {'kind': 'cover'}]}, require_uploaded=False), [])
        self.assertTrue(any('needs the question' in i for i in checks.record_issues({**rec, 'ask_owner': None}, require_uploaded=False)))
        self.assertTrue(any('READY_SEEK record still has an open question' in i for i in checks.record_issues({**rec, 'status': 'READY_SEEK'}, require_uploaded=False)))
        self.assertTrue(any('READY_SEEK record still has an open question' in i for i in checks.record_issues({**rec, 'status': 'READY_JEREMIE_SEEK'}, require_uploaded=False)))

    def test_questions_the_drafter_saw_on_a_portal_form_count_too(self):
        answers = [{'question': 'Which level are you applying for (Cadet, Graduate, Officer, Senior)?', 'answer': 'Graduate'}]
        rec = publish.build_record('r1', *pack('EMPLOYER_PORTAL', [], screening_answers=answers))
        self.assertEqual(rec['status'], 'ASK_OWNER'); self.assertEqual(rec['ask_owner']['then'], 'READY_EMPLOYER_PORTAL')

    def test_an_email_application_is_not_held_up_by_seek_form_questions(self):
        rec = publish.build_record('r1', *pack('EMAIL', SEEK_QUESTIONS + ['How would you rate your English language skills?']))
        self.assertEqual(rec['status'], 'PREPARED_NOT_SENT'); self.assertNotIn('ask_owner', rec)
        self.assertEqual(rec['recipient_email'], 'careers@wattlebrook.example')

    def test_an_unresolved_fact_on_an_email_application_asks_first_and_keeps_its_email(self):
        cand, screen, contact, draft = pack('EMAIL', [], subject='Junior Civil Drafter, Marc Masarate')
        screen['mandatory_unresolved'] = ['Advert asks for a manual licence']
        rec = publish.build_record('r1', cand, screen, contact, draft)
        self.assertEqual((rec['status'], rec['ask_owner']['then']), ('ASK_OWNER', 'PREPARED_NOT_SENT'))
        self.assertEqual(rec['ask_owner']['questions'][0]['question'], 'Advert asks for a manual licence')
        self.assertEqual(checks.record_issues({**rec, 'attachments': [{'kind': 'resume'}, {'kind': 'cover'}]}, require_uploaded=False), [])
        self.assertTrue(any('missing recipient_email' in i for i in checks.record_issues({**rec, 'recipient_email': ''}, require_uploaded=False)))

    def test_held_records_are_no_longer_made(self):
        self.assertFalse(hasattr(publish, 'publish_held')); self.assertFalse(hasattr(publish, 'held_record'))
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), mock.patch('sys.stderr', io.StringIO()):
            publish.main(['held', '20261113T0000Z'])
        self.assertTrue(publish.eligibility_issues({}, {'open': True, 'mandatory_unmet': ['Australian citizenship'], 'percent': 80}))


class PublishRun(unittest.TestCase):
    """publish.py build on a run folder, offline."""

    def run_folder(self, root, run_id, drafts):
        run = root / 'runs' / run_id
        for sid, (cand, screen, contact, draft) in drafts.items():
            common.write_json(run / 'extra' / f'{sid}.json', {**cand, 'id': sid})
            common.write_json(run / 'screen' / f'{sid}.json', screen)
            common.write_json(run / 'contacts' / f'{sid}.json', contact)
            common.write_json(run / 'drafts' / f'{sid}.json', draft)
        return run

    def test_build_writes_ready_and_ask_owner_and_reports_the_questions(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(publish, 'ROOT', Path(d)):
            ask = pack('SEEK', SEEK_QUESTIONS + ['Are you a current member of Engineers Australia?'])
            ask[0].update(company='Ironbark Consulting', seek_id='95900021', url='https://www.seek.com.au/job/95900021')
            run = self.run_folder(Path(d), '20261113T0100Z', {'95900020': pack('SEEK'), '95900021': ask})
            out = publish.publish('20261113T0100Z')
            self.assertEqual(out['rejected'], [])
            self.assertEqual(sorted(b[3] for b in out['built']), ['ASK_OWNER', 'READY_SEEK'])
            self.assertEqual(out['ask_owner'], [{'company': 'Ironbark Consulting', 'role': 'Junior Civil Drafter', 'questions': ['Are you a current member of Engineers Australia?']}])
            self.assertEqual(len(common.read_json(run / 'records.json')), 2)

    def test_a_letter_that_breaks_the_writing_rules_is_rejected_not_built(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(publish, 'ROOT', Path(d)):
            bad = pack('SEEK', letter={'paragraphs': ['I have not used 12d yet, and I have full working rights until December 2027.']})
            self.run_folder(Path(d), '20261113T0100Z', {'95900020': bad})
            out = publish.publish('20261113T0100Z')
            self.assertEqual(out['built'], [])
            issues = out['rejected'][0]['issues']
            self.assertTrue(any('letter volunteers a limit: "have not"' in i for i in issues))
            self.assertTrue(any('visa end date' in i for i in issues))

    def test_speculative_cap_comes_from_config_limits(self):
        cap = CONFIG['limits']['max_speculative_per_week']  # 3 on 13 Nov 2026
        with tempfile.TemporaryDirectory() as d, mock.patch.object(publish, 'ROOT', Path(d)):
            for i in range(cap - 1):  # two speculative enquiries built earlier this week, one long ago
                common.write_json(Path(d) / 'runs' / f'2026111{i}T0100Z' / 'records.json', [{'application_type': 'SPECULATIVE_ENQUIRY'}])
            common.write_json(Path(d) / 'runs' / '20261001T0100Z' / 'records.json', [{'application_type': 'SPECULATIVE_ENQUIRY'}] * 5)
            self.assertEqual(publish.speculative_this_week('20261113T0100Z'), cap - 1)
            drafts = {}
            for n in (1, 2):
                cand, screen, contact, draft = pack('EMAIL', [], application_type='SPECULATIVE_ENQUIRY', vacancy_status='NO_ADVERTISED_VACANCY_VERIFIED',
                                                    notes='No advertised vacancy: speculative enquiry to the published careers inbox.')
                cand.update(company=f'Consultancy {n}', seek_id=None, source='web', url=f'https://consultancy{n}.example/careers')
                contact.update(recipient_email=f'careers@consultancy{n}.example')
                drafts[f'spec{n}'] = (cand, {**screen, 'open': False, 'company_work_verified': True}, contact, draft)
            self.run_folder(Path(d), '20261113T0100Z', drafts)
            out = publish.publish('20261113T0100Z')
            self.assertEqual(len(out['built']), 1)  # the last one the cap allows this week
            self.assertIn(f'capped at {cap} a week', out['rejected'][0]['issues'][0])

    def test_no_script_or_test_uses_a_removed_limit(self):
        removed = ('target_new_records_min', 'max_new_records_per_run', 'max_emails_per_run', 'contact_research_max_per_run')
        for key in removed:
            self.assertNotIn(key, CONFIG['limits'])
        for path in list(SCRIPTS.glob('*.py')) + [p for p in HERE.glob('*.py') if p.name != 'test_rules.py']:
            text = path.read_text(encoding='utf-8')
            for key in removed:
                self.assertNotIn(key, text, path.name)
        self.assertIs(seek.LIMITS, CONFIG['limits']); self.assertIs(publish.LIMITS, CONFIG['limits'])
        with mock.patch.object(seek, 'sweep', return_value={'listings_seen': 0, 'prefilter_passed': 0, 'details_fetched': 0}) as sweep, mock.patch('sys.stderr', io.StringIO()):
            seek.main(['sweep', '--out', os.devnull])
        self.assertEqual(sweep.call_args[0][1], CONFIG['limits']['max_candidate_details_per_run'])


class StandingAnswers(unittest.TestCase):
    def test_common_seek_questions_map_to_a_line_of_facts_answers(self):
        for question, key in [
                ('Which of the following statements best describes your right to work in Australia?', 'right_to_work'),
                ('Are you legally entitled to work in Australia?', 'right_to_work'),
                ('How much notice are you required to give your current employer?', 'notice_period'),
                ("What's your expected annual base salary?", 'expected_salary'),
                ("Do you have a current Australian driver's licence?", 'drivers_licence'),
                ('Do you own or have regular access to a car?', 'own_car_or_regular_access'),
                ('Do you hold a Construction Induction Safety certificate (White Card)?', 'white_card'),
                ('Do you have a current Police Check (National Police Certificate) for employment?', 'police_check'),
                ('Are you willing to undergo a pre-employment medical check?', 'pre_employment_medical'),
                ('Are you willing to undergo pre-employment drug and alcohol screening?', 'drug_and_alcohol_screening'),
                ('Are you willing to relocate for this role?', 'willing_to_relocate'),
                ('Are you available to work FIFO / DIDO contracts?', 'willing_to_travel_or_fifo'),
                ('Have you completed a qualification in civil engineering?', 'qualification_questions'),
                ("How many years' experience do you have as a civil engineer?", 'years_of_experience'),
                ("How many years' experience do you have as an AutoCAD Draftsperson?", 'years_of_experience'),
                ('Which of the following CAD software do you have experience with?', 'software'),
                ('Do you have Engineering Drawing Interpretation experience?', 'experience_yes_no'),
                ('Do you have experience preparing and submitting tenders?', 'experience_yes_no'),
                ('Where are you located?', 'identity.location'),
                ('I acknowledge that the information I have provided is true and correct.', 'declarations_and_consents')]:
            self.assertEqual(checks.standing_answer(question), (key, None), question)

    def test_questions_only_the_owner_can_answer(self):
        for question in ['How would you rate your English language skills?',
                         'Do you have experience working on civil infrastructure projects?',
                         'Do you have experience using Microsoft Excel?',
                         'Which of the following Microsoft Office products are you experienced with?',
                         'Are you a current member of Engineers Australia?',
                         'Is your qualification/s recognised by Engineers Australia?',
                         'What interests you about joining STP Consultants.',
                         'What is your gender? Male Female',
                         'Please provide details of any medical conditions or pre-existing injuries.',
                         'If you are not an Australian Citizen, please provide the following information: Type of Visa Expiry Date Visa Number',
                         'Please confirm your Full legal name, Date of Birth (DD/MM), hourly rate, preferred engagement type (PAYG or ABN), and postcode']:
            key, problem = checks.standing_answer(question)
            self.assertTrue(problem, question)
        self.assertEqual([u['question'] for u in checks.unanswered_questions(SEEK_QUESTIONS + ['How would you rate your English language skills?'] * 2)],
                         ['How would you rate your English language skills?'])

    def test_a_conditional_answer_blocks_only_the_case_it_leaves_open(self):
        with facts_answers(OLDER):  # 'If the form asks full or probationary, or manual or automatic: not confirmed, skip and report.'
            self.assertEqual(checks.standing_answer("Do you hold a valid driver's licence?"), ('drivers_licence', None))
            self.assertTrue(checks.standing_answer('Are you licenced to drive a manual vehicle?')[1])
            self.assertTrue(checks.standing_answer("Do you hold a full, unrestricted driver's licence?")[1])
        with facts_answers({'drivers_licence': NEWER['drivers_licence']}):  # 'If the form asks manual or automatic: automatic. Never tick manual.'
            self.assertEqual(checks.standing_answer('Are you licenced to drive a manual vehicle?'), ('drivers_licence', None))
        with mock.patch.dict(checks.ANSWERS, {'english_self_rating': 'Fluent'}):
            self.assertEqual(checks.standing_answer('What is your level of English?'), ('english_self_rating', None))
        with mock.patch.dict(checks.ANSWERS, clear=True):
            self.assertIn('notice_period', checks.standing_answer('What is your notice period?')[1])

    def test_questions_command_reads_a_candidate_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'cand.json'
            common.write_json(path, {'screening_questions': SEEK_QUESTIONS})
            with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as stop:
                checks.main(['questions', str(path)])
            self.assertEqual(stop.exception.code, 0); self.assertIn('OK', out.getvalue())
            common.write_json(path, {'screening_questions': SEEK_QUESTIONS + ['How would you rate your English language skills?']})
            with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as stop:
                checks.main(['questions', str(path)])
            self.assertEqual(stop.exception.code, 1); self.assertIn('ask the owner: How would you rate your English', out.getvalue())


# ---------------------------------------------------------------------------------------------- 3. writing checks
GOOD_EMAIL = """Hello Sam,

I am applying for the Junior Civil Drafter role you advertised on SEEK. The advert asks for civil drawings in AutoCAD and Civil 3D for subdivision work.

I finished an Advanced Diploma of Civil Construction Design in February 2026, where I designed and documented road geometry, earthworks, pavement and stormwater drainage in AutoCAD and Civil 3D to Australian Standards. In 2019 and 2020 I worked on site in the Philippines as a field engineer, reviewing drawings and writing site reports.

I live in Melton. Full working rights in Australia (Subclass 485 visa), no sponsorship needed. I can start two weeks after an offer. I've attached my resume and cover letter.

Could we talk this week?

Kind regards,
Marc Darenz Masarate
0478 764 077
https://macdarenz-droid.github.io/Portfolio"""

GOOD_LETTER = [
    "I am applying for the Trainee Laboratory Technician role at your Geelong laboratory. Your advert says the work is sampling and testing soil, concrete and aggregates for subdivision and road projects, with training towards NATA sign-off.",
    "On site in the Philippines in 2019 and 2020 I carried out site inspections, safety checks and quality monitoring, tracked materials, and wrote site reports, material records and progress reports. In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed earthworks, pavements and stormwater drainage to Australian Standards, so I know what the test results are used for.",
    "I live in Melton and will relocate to Geelong for this role and can start two weeks after an offer. Full working rights in Australia (Subclass 485 visa), no sponsorship needed. I hold a White Card and a current Victorian driver's licence. Could I come in and meet the laboratory manager?",
]

# The letter the loop prepared on 13 Nov 2026 for PCP Solutions (runs/20261113T0714Z/drafts/pcp_L.json), last two paragraphs.
OLD_STYLE = [
    "I have not worked on water infrastructure yet, and I would learn your Integrated Management System and Tier 1 reporting from the team. I live in Melton, hold a White Card and an Australian driver's licence, have full working rights to December 2027 on a Subclass 485 visa, am available for regional site work and am open to discussing relocation to Toowoomba.",
    "My resume is attached, and I would welcome the chance to talk about the role.",
]


class WritingRules(unittest.TestCase):
    def test_limits_are_the_ones_in_config(self):
        self.assertEqual((checks.TONE['max_email_words'], checks.TONE['max_cover_letter_words']), (130, 200))

    def test_a_plain_email_and_letter_pass_every_check(self):
        self.assertLessEqual(checks.words(GOOD_EMAIL), 130)
        self.assertEqual(checks.tone_issues(GOOD_EMAIL, 'email') + checks.fact_issues(GOOD_EMAIL), [])
        letter = '\n'.join(GOOD_LETTER)
        self.assertLessEqual(checks.words(letter), 200)
        self.assertEqual(checks.tone_issues(letter, 'letter') + checks.fact_issues(letter), [])
        self.assertEqual(checks.draft_issues({'email_body': GOOD_EMAIL, 'subject': 'Junior Civil Drafter, Marc Masarate',
                                              'letter': {'subject': 'Trainee Laboratory Technician', 'greeting': 'Hello Sam,', 'paragraphs': GOOD_LETTER}}), [])

    def test_email_over_130_words_and_letter_over_200_words_fail(self):
        extra = ' I also prepared cost estimates and bills of quantities, compared design options in writing, and lodged Before You Dig Australia enquiries.'
        long_email = GOOD_EMAIL.replace('Could we talk this week?', extra.strip() + ' Could we talk this week?')
        self.assertGreater(checks.words(long_email), 130)
        self.assertTrue(any(i.startswith('too long') and 'limit 130' in i for i in checks.tone_issues(long_email, 'email')))
        long_letter = '\n'.join(GOOD_LETTER) + extra * 4
        self.assertGreater(checks.words(long_letter), 200)
        self.assertTrue(any('limit 200' in i for i in checks.tone_issues(long_letter, 'letter')))
        self.assertFalse(any('too long' in i for i in checks.tone_issues(long_letter, 'answer')))  # a form answer has no word limit

    def test_a_link_counts_as_one_word(self):
        self.assertEqual(checks.words('My drawings are at https://macdarenz-droid.github.io/Portfolio and my email is macdarenz@gmail.com'), 10)

    def test_banned_phrases_and_characters(self):
        text = 'Dear Hiring Manager, please find attached my résumé. I am a highly motivated team player with a proven track record – and extensive experience — in drafting.'
        issues = checks.tone_issues(text, 'letter')
        for phrase in ('dear hiring manager', 'please find attached', 'i am a highly', 'team player', 'proven track record', 'extensive experience'):
            self.assertIn(f'banned phrase: "{phrase}"', issues)
        self.assertEqual(sum(i.startswith('banned character') for i in issues), 2)
        for phrase in CONFIG['tone']['banned_phrases']:
            self.assertTrue(any(phrase in i for i in checks.tone_issues(f'Some words, {phrase.upper()} and more.', 'answer')), phrase)

    def test_every_volunteered_limit_pattern_fails_in_email_letter_and_answer(self):
        patterns = CONFIG['tone']['no_volunteered_limits']['flag_patterns']
        self.assertTrue(patterns)
        for pattern in patterns:
            text = f'I drafted roads in Civil 3D. In that area I {pattern.upper()} the software.'
            for kind in ('email', 'letter', 'answer'):
                self.assertTrue(any(f'"{pattern}"' in i for i in checks.tone_issues(text, kind)), (pattern, kind))

    def test_real_sentences_that_volunteer_a_limit_fail(self):
        for sentence, pattern in [
                ("I haven't used Pryda software yet, so I would need to learn it, and I'd put the hours in.", "haven't"),
                ('I haven’t used survey instruments on a job.', "haven't"),  # curly apostrophe
                ('To be straightforward about the gaps: I have not drafted timber trusses commercially.', 'have not'),
                ('My drafting so far is from study only.', 'from study only'),
                ("I'm based in Melton and open to discussing relocation to Sydney.", 'open to discussing'),
                ('Although I studied surveying in my degree, my design work is in Civil 3D.', 'although i'),
                ('My software experience is academic, not commercial.', 'academic, not'),
                ('Revit would be new to me in a production setting.', 'new to me'),
                ('I do not have 12d experience.', 'i do not have')]:
            self.assertIn(f'volunteers a limit: "{pattern}" (say what he has done; never what he lacks)', checks.tone_issues(sentence, 'letter'), sentence)
        issues = ['letter ' + i for i in checks.tone_issues('\n'.join(OLD_STYLE), 'letter')]
        for needle in ('"have not"', '"open to discussing"', '"to december 2027"', 'visa end date', 'would welcome the chance'):
            self.assertTrue(any(needle in i for i in issues), needle)

    def test_visa_end_date_needs_the_advert_to_ask(self):
        for text in ('I have full working rights until December 2027 on a Subclass 485 visa.', 'Work rights: Subclass 485, to Dec 2027.', 'My visa expires in december 2027.'):
            for kind in ('email', 'letter'):
                self.assertTrue(any('visa end date' in i for i in checks.tone_issues(text, kind)), text)
                self.assertEqual(checks.tone_issues(text, kind, visa_asked=True), [], text)
        letter = {'paragraphs': ['The advert asks about visa status. I hold a Subclass 485 Temporary Graduate visa with full working rights until December 2027. No sponsorship needed.',
                                 GOOD_LETTER[1], GOOD_LETTER[2]]}
        self.assertTrue(any('visa end date' in i for i in checks.draft_issues({'letter': letter})))
        self.assertTrue(any('visa end date' in i for i in checks.draft_issues({'letter': letter, 'advert_asks_about_visa': 'yes'})))  # only a real true counts
        self.assertEqual(checks.draft_issues({'letter': letter, 'advert_asks_about_visa': True}), [])
        self.assertEqual(checks.draft_issues({'email_body': 'Hello,\n\n' + letter['paragraphs'][0] + '\n\nKind regards,\nMarc Darenz Masarate', 'advert_asks_about_visa': True}), [])
        # Asking does not excuse the other limits.
        self.assertTrue(checks.tone_issues('I have not worked in Australia and my visa runs until December 2027.', 'letter', visa_asked=True))

    def test_short_work_rights_line_is_not_a_sponsorship_request(self):
        short = common.FACTS['eligibility']['work_rights_short']
        self.assertEqual(checks.tone_issues(short, 'letter') + checks.fact_issues(short), [])
        self.assertIn('mentions sponsorship or migration', checks.fact_issues('I would need employer sponsorship after 2027.'))
        self.assertIn('claims permanent residency', checks.fact_issues('I am a permanent resident, no sponsorship needed.'))

    def test_existing_truth_checks_are_kept(self):
        text = ('I have 3 years of commercial drafting experience with 12d and OpenRoads. I am an Australian citizen and a chartered engineer (CPEng). '
                'In 2021 I delivered a AUD 5 million road project and gained Australian site experience. I completed an internship with honours.')
        issues = checks.fact_issues(text)
        for needle in ('names software not in facts: 12d', 'names software not in facts: OpenRoads', 'claims years of professional experience', 'claims citizenship',
                       'claims a professional registration', 'year not in facts: 2021', 'amount not in facts: AUD 5 million', 'claims Australian work experience',
                       'claims an internship', 'claims honours'):
            self.assertIn(needle, issues)
        self.assertEqual(checks.fact_issues('I worked on a community hall renovation worth about PHP 1 million (AUD 22,000+) in 2019.'), [])
        self.assertTrue(any('portfolio link' in i for i in checks.tone_issues('My drawings are at macdarenz-droid.github.io/Portfolio.', 'email')))
        self.assertEqual(checks.tone_issues('My drawings are at https://macdarenz-droid.github.io/Portfolio.', 'email'), [])

    def test_console_operator_job_is_not_civil_experience(self):
        claim = 'presents the casual console operator job as civil experience (facts: it is current Australian work, nothing more)'
        for bad in ('My current role as a console operator at bp Rockbank has given me Australian construction industry experience.',
                    'As a console operator, I gained site experience coordinating deliveries and contractors.',
                    'I have two years of experience in civil works support through my service station role.'):
            self.assertIn(claim, checks.fact_issues(bad), bad)
        for fine in ('Since May 2024 I have worked as a casual console operator at bp Rockbank alongside full-time study in the Advanced Diploma of Civil Construction Design.',
                     'I work as a casual console operator at bp Rockbank, and my site experience is from the Philippines in 2019 and 2020.',
                     'My site experience is from the Philippines. I now work casually as a console operator in Rockbank.'):
            self.assertEqual(checks.fact_issues(fine), [], fine)

    def test_letter_shape_and_subject_lines(self):
        four = {'paragraphs': GOOD_LETTER + ['My resume is attached.']}
        self.assertTrue(any('4 paragraphs' in i for i in checks.draft_issues({'letter': four})))
        dashed = checks.draft_issues({'letter': {'subject': 'Junior Estimator – Water, Sewer & Drainage', 'greeting': 'Dear Hiring Manager,', 'paragraphs': GOOD_LETTER}})
        self.assertTrue(any(i.startswith('letter subject banned character') for i in dashed))
        self.assertTrue(any(i.startswith('letter greeting banned phrase') for i in dashed))

    def test_free_text_form_answers(self):
        draft = {'screening_answers': [
            {'question': 'Knowledge or experience in civil design and/or surveying', 'answer': 'Civil design in AutoCAD and Civil 3D (Advanced Diploma coursework). Surveying: I have not used survey equipment on a job yet.'},
            {'question': 'Current NSW Class C Driver’s Licence', 'answer': 'I hold a current Victorian driver’s licence. [Marc to confirm the NSW Class C step if relocating.]'},
            {'question': 'What is your current working rights status in Australia?', 'answer': common.FACTS['answers']['right_to_work']['free_text']},
            {'question': 'Microsoft Office skills', 'answer': 'Yes'},
            {'question': "What's your expected annual base salary?", 'answer': '$70,000'},
            {'question': 'Which software have you used?', 'answer': 'AutoCAD, Civil 3D, Revit and Tekla.'}]}
        issues = checks.draft_issues(draft)
        self.assertTrue(any('surveying' in i and '"have not"' in i for i in issues))
        self.assertTrue(any('Class C' in i and 'square brackets' in i for i in issues))
        self.assertTrue(any('names software not in facts: Tekla' in i for i in issues))
        self.assertFalse(any('working rights status' in i for i in issues))  # the form asked, so the end date may be given
        self.assertEqual(len(issues), 3)
        self.assertTrue(any(i.startswith('amount not in facts: $70,000') for i in checks.fact_issues('I managed a $70,000 budget.')))  # still a claim anywhere else

    def test_queue_entry_names_are_read_too(self):
        entry = {'cover_letter_text': '\n\n'.join(GOOD_LETTER[:2] + ['I live in Melton. Full working rights in Australia (Subclass 485 visa), no sponsorship needed.']),
                 'relocation_line': 'I will relocate to Geelong for this role and can start two weeks after an offer.',
                 'email': {'body': GOOD_EMAIL}, 'questions': [{'question': 'How much notice are you required to give?', 'answer': '2 weeks'}]}
        body, paragraphs, answers = checks.draft_parts(entry)
        self.assertEqual(body, GOOD_EMAIL); self.assertEqual(len(paragraphs), 3); self.assertTrue(paragraphs[-1].endswith('after an offer.'))
        self.assertEqual(answers, [('How much notice are you required to give?', '2 weeks')])
        self.assertEqual(checks.draft_issues(entry), [])
        self.assertTrue(checks.draft_issues({**entry, 'cover_letter_text': 'I have not drafted commercially.'}))
        self.assertIn('Hello Sam,<br>', email_html.html_body(email_html.email_text(entry)))

    def test_draft_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'draft.json'
            common.write_json(path, {'email_body': GOOD_EMAIL, 'letter': {'paragraphs': GOOD_LETTER}})
            with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as stop:
                checks.main(['draft', str(path)])
            self.assertEqual((stop.exception.code, out.getvalue().strip()), (0, 'OK'))
            common.write_json(path, {'letter': {'paragraphs': OLD_STYLE}})
            with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as stop:
                checks.main(['draft', str(path)])
            self.assertEqual(stop.exception.code, 1); self.assertIn('- letter volunteers a limit: "open to discussing"', out.getvalue())


# ---------------------------------------------------------------------------------------------- 4. journal
END = dict(queue_open=7, applied=4, emails_sent=1, seek_submitted=3, portal_submitted=0, expired_unsubmitted=0, replies=1, interviews=0,
           new_adverts_screened=22, queued=5, rejected=16, ask_owner=1, nothing_new=False)


class JournalRows(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.patches = [mock.patch.object(journal, 'JOURNAL', root / 'journal.jsonl'), mock.patch.object(journal, 'RUNS', root / 'runs')]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.dir.cleanup()

    def test_end_row_with_the_defined_fields_is_written(self):
        self.assertEqual(len(journal.END_FIELDS), 14)
        row = journal.note('20261113T2100Z', stage='end', note='SEEK 3, email 1.', **END)
        self.assertEqual(journal.last(1), [row])
        self.assertEqual({k: row[k] for k in END}, END)
        journal.note('20261114T2100Z', stage='end', **{**END, 'replies': None, 'interviews': None})  # this runner has no Gmail

    def test_unknown_field_is_refused_and_the_error_lists_the_allowed_ones(self):
        with self.assertRaises(ValueError) as err:
            journal.note('r', stage='end', duplicates=78, send='skipped_no_gmail', **END)
        message = str(err.exception)
        self.assertIn('unknown field(s): duplicates, send', message)
        for name in journal.END_FIELDS:
            self.assertIn(name, message)
        self.assertEqual(journal.rows(), [])

    def test_old_names_cannot_be_written(self):
        for old in ('new', 'prepared', 'ready', 'held', 'sent'):
            with self.assertRaises(ValueError) as err:
                journal.note('r', stage='end', **{**END, old: 2})
            self.assertIn(f'{old}: old names, read from old rows only', str(err.exception))

    def test_missing_or_wrong_values_are_refused(self):
        with self.assertRaises(ValueError) as err:
            journal.note('r', stage='end', **{k: v for k, v in END.items() if k not in ('applied', 'interviews')})
        self.assertIn('missing field(s): applied, interviews', str(err.exception))
        for bad in ({'applied': '4'}, {'applied': -1}, {'applied': 2.5}, {'applied': True}, {'nothing_new': 'no'}):
            with self.assertRaises(ValueError):
                journal.note('r', stage='end', **{**END, **bad})

    def test_other_stages_stay_free_form(self):
        journal.note('r', stage='start')
        journal.note('r', stage='discover', widened_to=7, anything='goes')
        self.assertEqual(len(journal.rows()), 2)

    def test_command_line_refuses_with_the_message(self):
        with self.assertRaises(SystemExit) as stop:
            journal.main(['note', 'r', 'stage=end', 'new=2', 'held=1'])
        self.assertIn('Allowed: queue_open, applied', str(stop.exception.code))
        with redirect_stdout(io.StringIO()) as out:
            journal.main(['note', 'r', 'stage=end', 'note=All quiet.'] + [f'{k}={json.dumps(v)}' for k, v in END.items()])
        self.assertEqual(json.loads(out.getvalue())['seek_submitted'], 3)

    def test_weekly_totals_by_iso_week_in_melbourne_time_and_old_rows_still_read(self):
        lines = [
            '<<<<<<< HEAD',  # the real journal has three merge-conflict marker lines; they are skipped
            json.dumps({'run_id': 'a', 'at': '2026-09-28T05:54:39.000Z', 'stage': 'end', 'new': 37, 'prepared': 1, 'ready': 2, 'held': 0, 'sent': 1}),
            json.dumps({'run_id': 'b', 'at': '2026-09-29T05:00:00.000Z', 'stage': 'start'}),
            json.dumps({'run_id': 'c', 'at': '2026-11-08T20:30:00.000Z', 'stage': 'end', **END}),  # Sunday evening UTC is Monday 9 Nov in Melbourne: week 46
            json.dumps({'run_id': 'd', 'at': '2026-11-13T02:00:00.000Z', 'stage': 'end', **{**END, 'queue_open': 3, 'applied': 2, 'seek_submitted': 2, 'emails_sent': 0, 'replies': None, 'nothing_new': True}}),
        ]
        journal.JOURNAL.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        weeks = journal.weekly()
        self.assertEqual([w['week'] for w in weeks], ['2026-W40', '2026-W46'])
        self.assertEqual({k: weeks[0][k] for k in ('ticks', 'applied', 'emails_sent', 'seek_submitted', 'queued')}, {'ticks': 1, 'applied': 1, 'emails_sent': 1, 'seek_submitted': 0, 'queued': 0})
        w46 = weeks[1]
        self.assertEqual((w46['ticks'], w46['applied'], w46['seek_submitted'], w46['emails_sent'], w46['replies'], w46['new_adverts_screened'], w46['nothing_new']), (2, 6, 5, 1, 1, 44, 1))
        self.assertEqual(w46['queue_open'], 3)  # the last reading of the week, not a sum
        with redirect_stdout(io.StringIO()) as out:
            journal.main(['weekly'])
        self.assertIn('2026-W46  ticks 2  applied 6 (seek 5, email 1, portal 0)  replies 1  interviews 0', out.getvalue())
        with redirect_stdout(io.StringIO()) as out:
            journal.main(['weekly', '--json'])
        self.assertEqual(json.loads(out.getvalue().splitlines()[-1])['applied'], 6)


# ---------------------------------------------------------------------------------------------- 5. compact JSON
class CompactJson(unittest.TestCase):
    RECORD = {'company': 'Acme Civil', 'notes': 'How GROK AI found this\n• What are your work rights? → Subclass 485 visa', 'gaps': ['12d', 'café “site” work'], 'match_score': {'percent': 72}}

    def test_no_padding_and_no_unicode_escapes(self):
        text = common.compact_json(self.RECORD)
        self.assertNotIn(': ', text.replace('rights? → Subclass', '')); self.assertNotIn(', "', text); self.assertNotIn('\\u', text)
        self.assertIn('→', text); self.assertIn('•', text)
        self.assertEqual(json.loads(text), self.RECORD)
        self.assertLess(len(text.encode('utf-8')), len(json.dumps(self.RECORD).encode('utf-8')))

    def test_http_helper_sends_the_compact_body(self):
        sent = []

        class Reply:
            status = 200
            def read(self): return b'{"version": 8}'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(request, timeout=None):
            sent.append(request)
            return Reply()
        payload = {'expected_version': 7, 'state': {'manual_entries': [self.RECORD]}}
        with mock.patch.object(common.urllib.request, 'urlopen', fake_urlopen):
            status, body = common.http('https://tracker.invalid/api/state', data=payload, method='PUT', headers={'Content-Type': 'application/json'})
        self.assertEqual((status, body), (200, {'version': 8}))
        self.assertEqual(sent[0].data, common.compact_json(payload).encode('utf-8'))
        self.assertEqual(json.loads(sent[0].data.decode('utf-8')), payload)
        with mock.patch.object(common.urllib.request, 'urlopen', fake_urlopen):  # a lone surrogate cannot be UTF-8: escapes are used instead of failing
            common.http('https://tracker.invalid/api/state', data={'notes': 'bad \ud83d char'}, method='PUT')
        self.assertEqual(json.loads(sent[1].data.decode('utf-8')), {'notes': 'bad \ud83d char'})

    def test_saving_on_a_built_record(self):
        rec = publish.build_record('r1', *pack('SEEK'))
        old, new = len(json.dumps(rec).encode('utf-8')), len(common.compact_json(rec).encode('utf-8'))
        self.assertLess(new, old)
        self.assertGreater((old - new) / old, 0.015)  # measured on real records: about 2 percent


# ---------------------------------------------------------------------------------------------- 6. compact PDFs


def pdf_pages(path):
    doc = compact_pdf.pymupdf.open(path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return pages


class CompactPdf(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.out = lambda name: os.path.join(self.dir.name, name)

    def tearDown(self):
        self.dir.cleanup()

    def test_en_dash_becomes_to_only_between_dates(self):
        for raw, want in [('Feb 2024 – Feb 2026', 'Feb 2024 to Feb 2026'), ('2014–2019', '2014 to 2019'), ('May 2024 – present', 'May 2024 to present'),
                          ('Mar 2020 – Apr 2022', 'Mar 2020 to Apr 2022'), ('March 2020–April 2022', 'March 2020 to April 2022'),
                          ('Technical Support Representative – Microsoft Software', 'Technical Support Representative - Microsoft Software'),
                          ('Junior Estimator – Water, Sewer & Drainage', 'Junior Estimator - Water, Sewer & Drainage'),
                          ('Coordinated 10–15 workers each day', 'Coordinated 10-15 workers each day'), ('an aside — like this', 'an aside, like this'),
                          ('Technical Support Representative – Microsoft Software  ·  Concentrix, Philippines  ·  Mar 2020 – Apr 2022',
                           'Technical Support Representative - Microsoft Software  ·  Concentrix, Philippines  ·  Mar 2020 to Apr 2022')]:
            self.assertEqual(compact_pdf.clean(raw), want)

    def test_heading_moves_to_the_next_page_with_its_first_item(self):
        first = 'Designed and documented road geometry, earthworks, pavement systems and stormwater drainage. ' * 3
        for with_room, pages_wanted in ((False, [1, 2]), (True, [2, 2])):
            sh = compact_pdf.Sheet(self.out(f'h{with_room}.pdf'))
            sh.text('Earlier section.')
            sh.y = compact_pdf.A4.height - compact_pdf.B - 30  # room for the heading line, not for the paragraph under it
            sh.heading('Education', room=sh.height(first, gap=6) if with_room else 0)
            sh.text(first, gap=6)
            sh.save()
            pages = pdf_pages(sh.path)
            where = [next(i + 1 for i, t in enumerate(pages) if needle in t) for needle in ('Education', 'Designed and documented')]
            self.assertEqual(where, pages_wanted)  # without room the heading is stranded on page 1: the old defect

    def test_entry_keeps_heading_role_line_and_first_bullet_together(self):
        sh = compact_pdf.Sheet(self.out('e.pdf'))
        sh.y = compact_pdf.A4.height - compact_pdf.B - 45
        sh.entry('Field Engineer  ·  Grand Travaux, Philippines  ·  Sep 2019 – Feb 2020', ['Assisted with site inspections, daily coordination and quality checks.', 'Tracked procurement.'], heading='Relevant experience')
        sh.save()
        pages = pdf_pages(sh.path)
        self.assertEqual(len(pages), 2); self.assertEqual(pages[0].strip(), '')
        self.assertLess(pages[1].index('Relevant experience'), pages[1].index('Field Engineer')); self.assertIn('Assisted with site inspections', pages[1])

    # Retired 14 Nov 2026 with compact_pdf.py's resume and letter commands: an email attaches
    # documents/resume/Marc_Masarate_Resume_<Variant>.pdf and the letter from letter_pdf.py (tests/test_letter_pdf.py).


# ---------------------------------------------------------------------------------------------- 7. prefilter and lanes
# Real advert titles from automation/runs/*/candidates*.json (candidates, not_detailed and rejected_titles).
REAL_TITLES = {
    'drafter': ['Civil Drafter', 'Cadet Civil Drafter', 'Junior Civil Drafter - Perth', 'Trainee Civil Drafter', 'Civil Engineering Draftsperson',
                'Civil Designer – Subdivision & Land Development', 'Civil Design Drafter', 'Junior Structural Draftsperson', 'Trainee Structural Drafter',
                'Civil Drafter - Junior to Mid Level', 'Road Designer', 'Junior Draftsperson', 'Draftsperson', 'CAD Drafter', 'Civil / Structural Draftsperson',
                'Technical Officer CAD or Trainee CAD Technician', 'Cadet Drafter (Civil) - Urban Transport', 'Civil Engineer/Civil Drafter'],
    'technician': ['Construction Materials Testing Technician - Entry-Level', 'Trainee Soil Technicians', 'Geotechnical Laboratory Technician', 'Soil Technician',
                   'Concrete Tester - Fifo', 'Cadet Laboratory Technician', 'Trainee Laboratory Technician', 'Laboratory Technician', 'Civil Engineering Technician',
                   'Technical Officer (Civil)', 'GEOTECHNICIAN/SOIL TESTER', 'CMT Technician - FIFO/DIDO', 'Civil Engineering Assistant',
                   'Lab Technician- Construction Material Testing', 'Asphalt laboratory technician', 'Trainee Laboratory & Field Technicians', 'Engineering Technical Officer'],
    'engineer': ['Graduate Civil Engineer', 'Junior Civil Engineer', 'Graduate Site Engineer', 'Cadet Civil Engineer', 'Junior Project Engineer', 'Graduate Engineer',
                 'Graduate Civil Engineer - Wodonga', 'Cadet Site Engineer', 'Junior Civil Site Engineer', 'Graduate Engineer - Full Time'],
    None: [  # estimator, project coordinator, steel detailer, non-civil laboratories, graduate programs, senior roles ...
        'Junior Estimator', 'Assistant Estimator', 'CAD Drafter / Estimator', 'Junior Project Coordinator', 'Construction Project Coordinator',
        'Steel Detailer', 'Junior Steel Detailer', 'Structural Steel Detailer', 'Structural Steel Draftsperson - Tekla Specialist',
        'Medical Laboratory Technician', 'Dental Laboratory Technician-Chatswood', 'Laboratory Tester (Chemistry Pharmaceutical)', 'Graduate Speech Pathologist - Gold Coast',
        '2027 Engineering Graduate Program', '2027 Graduate Program', '2027 CIMIC Group Graduate Program - UGL',
        'Senior Civil Engineer', 'Senior Laboratory Technician', 'Senior Lab Technician', 'Principal Civil Designer', 'Lead Drafter', 'Design Drafting Leader',
        'Snr Structural Modeller & Structural Modeller', 'Sr Project Manager', 'BIM Specialist', 'Civil Delivery Technical Specialist',
        'Laboratory Supervisor', 'Laboratory Manager', 'Civil Project Manager', 'Laboratory Coordinator',
        'Asphalt Labourer', 'Traffic Controller', 'Survey Assistant', 'Document Controller', 'Junior Project Administrator', 'Administration & Drafting Trainee',
        'Undergraduate Engineer', 'Engineering Assistant - Internship', 'Trainee Surveyor', 'Quantity Surveyor',
        'Structural Engineer', 'Geotechnical Engineer', 'Electrical Engineer', 'Junior Manufacturing Engineer', 'Junior Machine Learning Engineer', 'Graduate Mechatronics Engineer (February Start)',
        'Pest Control Technician - Trainee', 'Trainee Water Treatment Technician', 'Junior Service Technician', 'Non-Destructive Testing Technician and Trainee',
        'Engineering Technician – Automotive', '3D Sheetmetal Draftsperson', 'Designer / Drafter (Façade)', 'Graphic Designer',
        # General titles that need the advert text before they get a lane:
        'Site Engineer', 'Project Engineer', 'Civil Engineer', 'Trainee Technician', 'Junior Field Technician'],
}


class Lanes(unittest.TestCase):
    def test_lane_for_real_titles(self):
        self.assertGreaterEqual(sum(len(v) for v in REAL_TITLES.values()), 40)
        for lane, titles in REAL_TITLES.items():
            for title in titles:
                self.assertEqual(seek.lane_for(title), lane, title)
                self.assertEqual(seek.lane_for(title, None), lane, title)

    def test_the_listed_titles_really_are_in_the_run_folders(self):
        seen = set()
        for path in (HERE.parent / 'runs').glob('*/candidates*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except ValueError:
                continue
            for key in ('candidates', 'not_detailed', 'rejected_titles'):
                rows = data.get(key) if isinstance(data, dict) else None
                seen.update(r['title'].strip() for r in rows or [] if isinstance(r, dict) and r.get('title'))
        if not seen:
            self.skipTest('run folders are not in this checkout')
        missing = [t for titles in REAL_TITLES.values() for t in titles if t not in seen]
        self.assertEqual(missing, [])

    def test_pathology_laboratory_technician_has_no_lane(self):
        # No advert with exactly this title is in the run folders; the brief names it, so it is written here.
        for title in ('Pathology Laboratory Technician', 'Trainee Pathology Lab Technician', 'Pathology Collector / Laboratory Assistant'):
            self.assertIsNone(seek.lane_for(title), title)
            self.assertFalse(seek.prefilter({'title': title, 'classifications': []})[0], title)

    def test_senior_words_the_config_list_lacks_get_no_lane(self):
        # Review finding: 'Snr Structural Modeller & Structural Modeller' (a real title) came back as drafter.
        for title in ('Snr Structural Modeller & Structural Modeller', 'Sr. Civil Drafter', 'Civil Designer - 12d Specialist', 'Specialist Soil Testing Technician'):
            self.assertIsNone(seek.lane_for(title), title)
            self.assertIsNone(seek.lane_for(title, 'Civil drawings in AutoCAD and Civil 3D. Soil and concrete testing. Graduates welcome.'), title)
        self.assertEqual(seek.lane_for('Civil Drafter - Junior to Mid Level'), 'drafter')  # a real junior advert stays

    def test_lanes_and_their_order_come_from_config(self):
        ranked = sorted((v['rank'], k) for k, v in CONFIG['lanes'].items() if isinstance(v, dict) and 'rank' in v)
        self.assertEqual([k for _, k in ranked], ['drafter', 'technician', 'engineer'])
        self.assertEqual(set(seek.LANE_TITLE), {'drafter', 'technician', 'engineer'})
        self.assertEqual(seek.lane_for('Graduate Civil Engineer / Concrete Field Technician'), 'technician')  # lane 2 before lane 3
        self.assertEqual(seek.lane_for('Civil Engineer/Civil Drafter'), 'drafter')  # lane 1 first

    def test_the_advert_text_decides_a_general_title(self):
        civil = 'Prepare civil drawings in AutoCAD and Civil 3D for subdivision, stormwater drainage and earthworks under our engineers.'
        homes = 'Draft working drawings for custom homes and renovations in ArchiCAD. Liaise with our sales consultants and estimators.'
        self.assertEqual(seek.lane_for('Draftsperson', civil), 'drafter')
        self.assertIsNone(seek.lane_for('Draftsperson', homes))
        self.assertEqual(seek.lane_for('Cadet Designer', civil), 'drafter')
        self.assertIsNone(seek.lane_for('Cadet Designer'))
        testing = 'Full training provided. You will sample and test soil, concrete and aggregates in our NATA accredited laboratory and in the field.'
        self.assertEqual(seek.lane_for('Trainee Technician', testing), 'technician')
        self.assertEqual(seek.lane_for('Junior Field Technician', testing), 'technician')
        self.assertIsNone(seek.lane_for('Trainee Technician', 'Install and service security alarms and CCTV. Training provided.'))
        self.assertIsNone(seek.lane_for('Laboratory Technician', 'Prepare specimens and run assays in our pathology collection centre.'))
        council = 'Support the design, inspection and maintenance of roads, footpaths and drainage for the Shire. Civil engineering diploma desirable.'
        self.assertEqual(seek.lane_for('Engineering Technical Officer', council), 'technician')
        self.assertEqual(seek.lane_for('Graduate Engineer', 'Join our construction team delivering tunnels and civil structures.'), 'engineer')
        self.assertIsNone(seek.lane_for('Graduate Engineer', 'Seeking a graduate process engineer for our advanced water treatment plant.'))

    def test_a_bare_engineer_title_needs_a_welcome_and_no_two_years(self):
        welcome = 'Civil contractor seeking a site engineer for subdivision works. Recent graduates welcome; 0-1 years experience is fine.'
        self.assertEqual(seek.lane_for('Site Engineer', welcome), 'engineer')
        self.assertEqual(seek.lane_for('Project Engineer', 'Entry level role on civil projects. Training provided.'), 'engineer')
        self.assertIsNone(seek.lane_for('Site Engineer', 'Civil contractor seeking a site engineer. Minimum 3 years experience on subdivision works. Graduates welcome to apply for other roles.'))
        self.assertIsNone(seek.lane_for('Site Engineer', 'Entry level considered. You have 2+ years of civil site experience.'))
        self.assertIsNone(seek.lane_for('Site Engineer', 'Experienced site engineer for a tier one civil contractor. You will mentor junior engineers.'))
        self.assertEqual(seek.lane_for('Graduate Site Engineer', 'Minimum 3 years experience.'), 'engineer')  # the title says graduate; fit scoring deals with the years


    def test_sweep_digest_and_the_lane_command_carry_the_lane(self):
        listing = {'id': 95900030, 'title': 'Trainee Technician', 'companyName': 'Ground Test Labs', 'locations': [{'label': 'Geelong VIC'}], 'listingDate': '2026-11-12T00:00:00Z',
                   'classifications': [{'classification': {'description': 'Engineering'}, 'subclassification': {'description': 'Laboratory & Technical Services'}}]}
        detail = {'source': 'seek', 'seek_id': '95900030', 'title': 'Trainee Technician', 'company': 'Ground Test Labs', 'url': 'https://www.seek.com.au/job/95900030',
                  'content_text': 'Full training provided. Sample and test soil, concrete and aggregates in our NATA laboratory.'}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(seek, 'search', return_value={'data': [listing], 'totalCount': 1}), \
                mock.patch.object(seek, 'details', return_value=dict(detail)), mock.patch.object(seek.time, 'sleep'):
            run = Path(d) / 'runs' / '20261113T0100Z'
            result = seek.sweep(3, 5, run / 'candidates.json', keyword_sets=['soil technician'])
            self.assertEqual(result['candidates'][0]['lane'], 'technician')
            seek.digest(run, 10)
            self.assertEqual(common.read_json(run / 'screen_input.json')['candidates'][0]['lane'], 'technician')
            advert = Path(d) / 'advert.txt'
            advert.write_text(detail['content_text'], encoding='utf-8')
            for argv, want in ((['lane', 'Trainee Technician', '--text-file', str(advert)], 'technician'), (['lane', 'Trainee Technician'], 'none'), (['lane', 'Junior Civil Drafter'], 'drafter')):
                with redirect_stdout(io.StringIO()) as out:
                    seek.main(argv)
                self.assertEqual(out.getvalue().strip(), want)


class PrefilterWords(unittest.TestCase):
    def listing(self, title):
        return {'title': title, 'classifications': ['Civil/Structural Engineering (Engineering)']}

    def test_laboratory_titles_are_kept_now(self):
        self.assertNotIn('laboratory', CONFIG['prefilter']['title_exclude_any'])
        for title in ('Laboratory Technician', 'Geotechnical Laboratory Technician', 'Soils & Concrete Laboratory Technician', 'Cadet Laboratory Technician', 'Laboratory Assistant - Downer'):
            self.assertTrue(seek.prefilter(self.listing(title))[0], title)
        for title in ('Medical Laboratory Technician', 'School Laboratory Technician', 'Food Laboratory Technician', 'Laboratory Technician - Water Quality'):
            self.assertFalse(seek.prefilter(self.listing(title))[0], title)
        self.assertFalse(seek.prefilter(self.listing('VC / Collaboration Engineer - Network'))[0])
        self.assertEqual(seek.prefilter(self.listing('Project Officer TAFE WA NTN Collaboration Hub')), (False, 'title has no junior/civil signal'))

    def test_a_space_in_a_config_word_means_a_word_boundary(self):
        def found(term, title):
            return seek.term_in(term, seek.plain(title))
        for title in ('Lab Technician', 'Soils Lab/Field Assistant', 'Trainee - Lab', 'LAB & FIELD TECHNICIAN', 'Quarry Lab Technician'):
            self.assertTrue(found(' lab ', title), title)
        for title in ('Laboratory Technician', 'Collaboration Engineer', 'Asphalt Labourer', 'Elaborate Designs Drafter', 'Fablab Officer'):
            self.assertFalse(found(' lab ', title), title)
        self.assertTrue(found('laboratory', 'Geotechnical Laboratory Technician')); self.assertFalse(found('laboratory', 'Collaboration Lead'))
        self.assertTrue(found('lead ', 'Team Lead')); self.assertTrue(found('lead ', 'Lead/Senior Drafter')); self.assertFalse(found('lead ', 'Leading Hand'))
        self.assertTrue(found(' intern ', 'Engineering Intern')); self.assertFalse(found(' intern ', 'International Graduate Engineer'))
        self.assertTrue(found('entry-level', 'Entry Level Drafter')); self.assertTrue(found('entry level', 'Entry-Level Drafter'))
        self.assertTrue(found('5+ years', 'Site Engineer (5+ Years)')); self.assertTrue(found('draughts', 'Draughtsman')); self.assertTrue(found('facade', 'Designer / Drafter (Façade)'))
        self.assertFalse(found('  ', 'anything'))

    def test_a_spaced_word_added_to_config_works_in_the_prefilter(self):
        pre = {**CONFIG['prefilter'], 'title_include_any': [' lab '], 'title_exclude_any': ['senior', 'lead ']}
        with mock.patch.object(seek, 'PRE', pre):
            self.assertTrue(seek.prefilter(self.listing('Soils Lab Assistant'))[0])
            self.assertEqual(seek.prefilter(self.listing('Collaboration Assistant')), (False, 'title has no junior/civil signal'))
            self.assertEqual(seek.prefilter(self.listing('Lab Team Lead')), (False, 'title excludes: lead'))



# ============================================================================== review round (13 Nov 2026)
# Each class below is one finding of the adversarial review of commit dfd241f: the test failed on that commit.
ATTACHED = [{'kind': 'resume'}, {'kind': 'cover'}]
# The two states of facts.json -> answers that matter here: this checkout's, and the orchestrator's newer lines
# (full licence confirmed, a manual-licence line, future sponsorship and Engineers Australia left to the owner).
OLDER = {'drivers_licence': 'Yes. If the form asks full or probationary, or manual or automatic: not confirmed, skip and report.'}
NEWER = {'drivers_licence': "Yes, full Victorian driver's licence. If the form asks manual or automatic: automatic. Never tick manual.",
         'manual_licence': 'No (automatic)',
         'future_visa_sponsorship': "Not answered here: if a form asks whether he will need sponsorship in the future, skip and report (the owner decides this wording). 'Do you need sponsorship to work now?': No.",
         'engineers_australia_membership_or_recognition': 'Not on record: skip and report. Never tick member, eligible or assessed.'}


def facts_answers(lines):
    """checks.ANSWERS as this checkout has it, with the given lines and without the other state's extra keys."""
    base = {k: v for k, v in checks.ANSWERS.items() if k not in NEWER}
    return mock.patch.dict(checks.ANSWERS, {**base, **lines}, clear=True)


def build_run(drafts, run_id='20261113T0100Z'):
    """publish.py build on a temporary run folder. A contact of None means no contacts file. Returns (result, records)."""
    with tempfile.TemporaryDirectory() as d, mock.patch.object(publish, 'ROOT', Path(d)):
        run = Path(d) / 'runs' / run_id
        for sid, (cand, screen, contact, draft) in drafts.items():
            common.write_json(run / 'extra' / f'{sid}.json', {**cand, 'id': sid})
            common.write_json(run / 'screen' / f'{sid}.json', screen)
            if contact is not None:
                common.write_json(run / 'contacts' / f'{sid}.json', contact)
            common.write_json(run / 'drafts' / f'{sid}.json', draft)
        return publish.publish(run_id), common.read_json(run / 'records.json')


# The form answers of two real drafts, as the drafters wrote them.
FYFE = [{'q': 'Fyfe careers page questions',  # runs/20261110T1414Z/drafts/fyfe.json, route EMPLOYER_PORTAL
         'a': 'Not visible before applying; answer from the resume and cover letter. Work rights: Subclass 485, full working rights to December 2027 (not PR or citizen). Salary and start date: Marc to answer.'}]
OCTOBER = {'Which of the following statements best describes your right to work in Australia?': 'Temporary visa with full working rights: Subclass 485, full working rights until December 2027.',
           "What's your expected annual base salary?": 'Marc to answer (no salary figure is on record for this role).',  # runs/20261012T0012Z/drafts/95191525.json
           'How would you rate your English language skills?': 'Fluent'}


class FormAnswerShapes(unittest.TestCase):
    """P2-1: answers written as {q, a} or as one {question: answer} object were invisible to the checks and the gate."""

    def test_the_three_shapes_real_drafts_use_read_the_same(self):
        want = [{'question': 'Why us?', 'answer': 'I have not used 12d yet.', 'basis': ''}]
        for shape in ([{'question': 'Why us?', 'answer': 'I have not used 12d yet.'}], [{'q': 'Why us?', 'a': 'I have not used 12d yet.'}], {'Why us?': 'I have not used 12d yet.'}):
            self.assertEqual(checks.answer_items({'screening_answers': shape}), (want, None), shape)
            self.assertEqual(checks.form_questions({'screening_answers': shape}), ['Why us?'], shape)
            self.assertEqual(checks.draft_parts({'screening_answers': shape})[2], [('Why us?', 'I have not used 12d yet.')], shape)
            self.assertTrue(any('"have not"' in i for i in checks.draft_issues({'screening_answers': shape})), shape)
        self.assertEqual(checks.answer_items({'questions': [{'question': 'Notice?', 'options': [], 'answer': '2 weeks', 'basis': 'answers.notice_period', 'status': 'answered'}]}),
                         ([{'question': 'Notice?', 'answer': '2 weeks', 'basis': 'answers.notice_period'}], None))  # a queue entry
        self.assertEqual(checks.answer_items({}), ([], None)); self.assertEqual(checks.answer_items({'screening_answers': None, 'questions': []}), ([], None))

    def test_real_november_answers_written_as_q_and_a_are_checked_and_gated(self):
        issues = checks.draft_issues({'route': 'EMPLOYER_PORTAL', 'screening_answers': FYFE})
        for needle in ('volunteers a limit: "to december 2027"', 'visa end date', 'claims PR', 'is a placeholder, not an answer'):
            self.assertTrue(any(needle in i for i in issues), needle)
        self.assertEqual([u['question'] for u in checks.unanswered_questions(checks.form_questions({'screening_answers': FYFE}))], ['Fyfe careers page questions'])
        out, records = build_run({'fyfe': pack('EMPLOYER_PORTAL', [], screening_answers=FYFE)})
        self.assertEqual([b[3] for b in out['built']], ['ASK_OWNER'])  # it was READY_EMPLOYER_PORTAL with no issues
        self.assertEqual(out['ask_owner'][0]['questions'], ['Fyfe careers page questions'])
        self.assertEqual(records[0]['screening_answers'], [{'question': 'Fyfe careers page questions'}])  # a placeholder is not kept as a proposal
        self.assertNotIn('Marc to answer', json.dumps(records[0]))

    def test_october_answers_written_as_one_object_are_checked_and_gated(self):
        issues = checks.draft_issues({'screening_answers': OCTOBER})
        self.assertTrue(any('expected annual base salary' in i and 'placeholder' in i for i in issues))
        self.assertFalse(any('right to work' in i for i in issues))  # the form asks about work rights, so the end date may be given
        rec = publish.build_record('r1', *pack('SEEK', [], screening_answers=OCTOBER))
        self.assertEqual(rec['status'], 'ASK_OWNER')
        self.assertEqual([a['question'] for a in rec['ask_owner']['questions']], ['How would you rate your English language skills?'])

    def test_answers_in_a_shape_nobody_can_read_are_refused_not_skipped(self):
        for bad in ('see the notes', [['Why us?', 'Because.']], [{'text': 'Why us?', 'reply': 'Because.'}], [{'question': '', 'answer': 'Yes'}], 7):
            items, problem = checks.answer_items({'screening_answers': bad})
            self.assertTrue(problem, bad); self.assertIn('cannot be read', problem)
            self.assertTrue(any('cannot be read' in i for i in checks.draft_issues({'screening_answers': bad})), bad)
            out, records = build_run({'x': pack('SEEK', screening_answers=bad)})
            self.assertEqual((out['built'], records), ([], [])); self.assertIn('cannot be read', out['rejected'][0]['issues'][0])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'draft.json'
            common.write_json(path, {'screening_answers': 'see the notes'})
            with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as stop:
                checks.main(['questions', str(path)])
            self.assertEqual(stop.exception.code, 1); self.assertIn('cannot be read', out.getvalue())

    def test_an_answer_that_is_not_text_is_an_issue(self):
        self.assertTrue(any('is not text' in i for i in checks.draft_issues({'screening_answers': [{'q': 'Years of experience', 'a': 3}]})))
        self.assertEqual(checks.draft_issues({'screening_answers': [{'q': 'Years of experience', 'a': None}, {'q': 'Notice period', 'a': ''}]}), [])

    def test_every_real_draft_with_answers_is_seen(self):
        drafts = [p for p in (HERE.parent / 'runs').glob('*/drafts/*.json')]
        if not drafts:
            self.skipTest('run folders are not in this checkout')
        with_answers = 0
        for path in drafts:
            draft = json.loads(path.read_text(encoding='utf-8'))
            raw = draft.get('screening_answers')
            if not raw:
                continue
            with_answers += 1
            items, problem = checks.answer_items(draft)
            self.assertIsNone(problem, path.name)
            self.assertEqual(len(items), len(raw), path.name)
            self.assertTrue(all(i['question'] for i in items), path.name)
        self.assertGreater(with_answers, 50)  # 90 of the 221 real drafts carry answers, in three shapes


# Real SEEK form questions from automation/runs/*/candidates*.json and what the gate must say about each:
# the line of facts.json -> answers it reads, or None in place of the line when the owner must be asked.
SETTLED = [
    ('Which of the following statements best describes your right to work in Australia?', 'answers.right_to_work.free_text'),  # with no options: the text
    ('Are you a Citizen/Permanent Resident of Australia?', 'answers.right_to_work.free_text'),
    ('Visa Status', 'answers.right_to_work.free_text'),
    ('How much notice are you required to give your current employer?', 'answers.notice_period'),
    ('When can you commence in a full time capacity?', 'eligibility.availability'),  # 'Two weeks after an offer'
    ("What's your expected annual base salary?", 'answers.expected_salary.rule'),
    ('I acknowledge that all information I provided in this application is true and correct to the best of my knowledge and that any incorrect or misleading information may lead to disqualification, or if appointed, to termination of Employment?', 'answers.declarations_and_consents'),
    ('Do you agree with the privacy policy?', 'answers.declarations_and_consents'),
    ("Do you have a current Australian driver's licence?", 'answers.drivers_licence'),
    ("Do you hold a current Class C drivers' license?", 'answers.drivers_licence'),
    ('Do you own or have regular access to a car?', 'answers.own_car_or_regular_access'),
    ('Do you have reliable access to transport for travelling to workplaces or project sites where public transport may not be available?', 'answers.own_car_or_regular_access'),
    ('Do you hold a Construction Induction Safety certificate (White Card)?', 'answers.white_card'),
    ('Do you have a current Police Check (National Police Certificate) for employment?', 'answers.police_check'),
    ('Are you willing to undergo pre-employment drug and alcohol screening?', 'answers.drug_and_alcohol_screening'),
    ('Are you willing to undergo a pre-employment medical check?', 'answers.pre_employment_medical'),
    ('Are you willing to relocate for this role?', 'answers.willing_to_relocate'),
    ('Are you available to work FIFO / DIDO contracts?', 'answers.willing_to_travel_or_fifo'),
    ('Do you have Engineering Drawing Interpretation experience?', 'answers.experience_yes_no.engineering drawing interpretation'),
    ('Do you have experience preparing and submitting tenders?', 'answers.experience_yes_no.preparing and submitting tenders'),
    ('Have you completed a qualification in civil engineering?', 'answers.qualification_questions.civil engineering'),
    ('Have you completed a qualification in engineering?', 'answers.qualification_questions.engineering'),
    ('Have you completed a qualification in engineering drafting / engineering design?', 'answers.qualification_questions.engineering drafting or design'),
    ("How many years' experience do you have as a civil engineer?", 'answers.years_of_experience.civil engineer, site engineer, project engineer, construction industry'),
    ("How many years' experience do you have as a Civil Site Engineer?", 'answers.years_of_experience.civil engineer, site engineer, project engineer, construction industry'),
    ("How many years' experience do you have in the construction industry?", 'answers.years_of_experience.civil engineer, site engineer, project engineer, construction industry'),
    ("How many years' experience do you have as a civil drafter?", 'answers.years_of_experience.drafter, draftsperson, designer, CAD'),
    ("How many years' experience do you have as a Civil Engineering Technician?", 'answers.years_of_experience.laboratory, materials testing, technician, estimator, project coordinator, project management, any other role'),
    ("How many years' experience do you have as a Civil Estimator?", 'answers.years_of_experience.laboratory, materials testing, technician, estimator, project coordinator, project management, any other role'),
    ('Which of the following CAD software do you have experience with?', 'answers.software.CAD'),
    ('Do you have experience using Bluebeam?', 'answers.software.other'),
    ('Are you currently studying?', 'answers.currently_studying'),
]
ASK = [
    # Settled by checks.py's old rules, left to the owner by the one gate (answers.py, 14 Nov 2026): it answers only what a
    # line of facts.json clearly covers.
    'Please provide your salary or hourly rate expectations:',  # names an hourly rate: not on record
    'This position includes providing on-site servicing at our clients premises in Melbourne. Do you have a car license and car?',  # two things at once
    "Do you have a heavy vehicle driver's licence?",
    'Do you have experience in a FIFO/DIDO role?',  # experience, not willingness; 'anything else' is not a standing answer
    'Do you have mine site experience?',
    'Have you completed a qualification in mechanical engineering?',  # shares 'engineering' with his degree: not guessed
    'Have you completed a qualification in structural engineering?',
    'Which of the following best describes your highest qualification - relevant to the position of Structural Revit Drafter?',
    'Do you have a current Working With Children (WWC) Check?',
    'How many years experience in Civil Engineering Design do you have?',  # a field no row names
    "How many years' experience do you have as an Engineering Cadet?",  # an engineering word: not the 'any other role' row
    'Do you have experience using "Expert Estimation" and MS Project?',  # a tool nobody listed
    'Do you currently reside in Australia?',  # location is free text only
    'Do you live in Perth?',
    'Preferred Name',
    'Will you require visa sponsorship in the future?',  # was right_to_work, settled
    'Do you have experience working on civil infrastructure projects?',
    'How many years of civil infrastructure construction experience do you have, and which of the following have you personally overseen or certified: bulk earthworks, rail formation, reinforced concrete bridges and box culverts?',
    'How many years of Infrastructure Civil Engineering experience do you have?',
    "What's your expected hourly rate?",  # was expected_salary: the standing answer is an annual band
    'What is your current rate and what are you looking for?',
    'How far are you willing to travel for work?',  # was willing_to_travel_or_fifo: 'Yes' is not a distance
    'How many years post grad are you?',  # was years_of_experience: 'lowest option (no paid role)'
    "How many years' experience do you have in your current occupation?",
    'Please specify the number of years of relevant experience you have:',
    'Tell us about yourself, your degree and what led you to study engineering.',  # was qualification_questions
    'Can you outline your direct experience in road design and usage as a user of 12D?',  # was software
    'Are you a current member of Engineers Australia?',
    'Have you completed a Bachelor of Engineering that is accredited by Engineers Australia?',
    'Are you able to obtain a National Police Check and other related security clearances required for this role?',  # was police_check
    'Do you hold Australian Security Clearance?',
    'Do you have a valid WA drivers licence?',  # was drivers_licence: his licence is Victorian
    'How would you rate your English language skills?',
    'Do you have experience using Microsoft Excel?',
    'Which of the following types of infrastructure project do you have experience with?',
    'Do you own a suitable Personal Protective Equipment or PPE (safety boots, 100% cotton sleeved shirt, 100% cotton long trouser and Hard Hat with brim attachment)?',
    'Which role are you applying for?',
    'What is your gender? Male Female',
    'If you are on a Visa, please indicate your Visa number (eg. 190, 485) and the expiry date.',
]


class GateFailsClosed(unittest.TestCase):
    """P2-2: the standing-answer gate cleared questions that facts.json leaves open or has no line for."""

    def test_the_questions_the_review_found_cleared(self):
        for lines in (OLDER, NEWER):
            with facts_answers(lines):
                key, problem = checks.standing_answer('Will you require visa sponsorship in the future?')
                self.assertEqual(key, 'future_visa_sponsorship'); self.assertTrue(problem)
                # now, not later: No, only where facts.json says so ('Do you need sponsorship to work now?': No, the newer line)
                self.assertEqual(checks.standing_answer('Do you require sponsorship to work in Australia?'),
                                 ('future_visa_sponsorship', None) if lines is NEWER else ('future_visa_sponsorship', 'a sponsorship question facts.json does not answer'))
                key, problem = checks.standing_answer('Do you have experience in a FIFO/DIDO role?')   # not the 'Yes' of willing_to_travel_or_fifo
                self.assertTrue(problem)
                key, problem = checks.standing_answer('Do you have experience in civil infrastructure?')
                self.assertEqual(key, 'experience_yes_no'); self.assertTrue(problem)
                self.assertTrue(checks.standing_line("Do you have a heavy vehicle driver's licence?")[2])   # one gate: a licence class is the owner's
                self.assertEqual(checks.standing_answer('I acknowledge that all information I provided is true and correct and that misleading information may lead to disqualification?'),
                                 ('declarations_and_consents', None))
                rec = publish.build_record('r1', *pack('SEEK', SEEK_QUESTIONS + ['Will you require visa sponsorship in the future?', 'Do you have experience in a FIFO/DIDO role?',
                                                                               'Do you have experience in civil infrastructure?']))
                self.assertEqual(rec['status'], 'ASK_OWNER')  # it was READY_SEEK with no ask_owner under both states of facts.json
                self.assertEqual([a['question'] for a in rec['ask_owner']['questions']], ['Will you require visa sponsorship in the future?', 'Do you have experience in a FIFO/DIDO role?',
                                                                                         'Do you have experience in civil infrastructure?'])

    def test_licence_questions_follow_what_the_licence_line_says(self):
        open_licence, manual = "Do you hold a current open driver's licence?", 'Are you licenced to drive a manual vehicle?'
        with facts_answers(OLDER):  # full or probationary, manual or automatic: not confirmed
            for question in (open_licence, "Do you hold a full, unrestricted driver's licence?", 'Do you hold a provisional (P plate) licence?', manual, "Do you hold a current manual driver's licence?"):
                key, problem = checks.standing_answer(question)
                self.assertEqual(key, 'drivers_licence', question); self.assertTrue(problem, question)
            self.assertEqual(checks.standing_answer("Do you have a current Australian driver's licence?"), ('drivers_licence', None))
        with facts_answers(NEWER):  # full licence confirmed; automatic
            self.assertEqual(checks.standing_answer(open_licence), ('drivers_licence', None))
            self.assertEqual(checks.standing_line(manual), ('answers.manual_licence', 'No', None))   # the answer to give, from 'No (automatic)'
        for lines in (OLDER, NEWER):  # his licence is Victorian: another state's licence is the owner's call
            with facts_answers(lines):
                for question in ('Do you have a valid WA drivers licence?', "Do you hold a current Queensland driver's licence?", 'Current NSW Class C Driver’s Licence'):
                    self.assertTrue(checks.standing_answer(question)[1], question)

    def test_every_line_of_facts_answers_has_a_rule(self):
        lines = {k for k in common.FACTS['answers'] if not k.startswith('_')}
        self.assertEqual(sorted(lines - checks.rule_keys()), ['free_text_cover_letter'])   # the letter is pasted from the entry, not a form answer
        self.assertLessEqual(set(NEWER), checks.rule_keys())  # the orchestrator's newer keys
        self.assertLessEqual({'qualification_questions', 'years_of_experience', 'software', 'experience_yes_no'}, checks.rule_keys())

    def test_real_questions_reach_the_right_line_or_the_owner(self):
        self.assertGreaterEqual(len(SETTLED) + len(ASK), 60)
        for lines in (OLDER, NEWER):
            with facts_answers(lines):
                for question, basis in SETTLED:
                    self.assertEqual(checks.standing_line(question)[::2], (basis, None), question)
                    self.assertTrue(checks.standing_line(question)[1], question)
                for question in ASK:
                    self.assertTrue(checks.standing_line(question)[2], question)
                self.assertEqual([u['question'] for u in checks.unanswered_questions([q for q, _ in SETTLED] + ASK)], ASK)

    def test_the_listed_questions_really_are_in_the_run_folders(self):
        seen = set()
        for path in (HERE.parent / 'runs').glob('*/candidates*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except ValueError:
                continue
            for cand in (data.get('candidates') if isinstance(data, dict) else None) or []:
                seen.update(' '.join(q.split()) for q in cand.get('screening_questions') or [] if isinstance(q, str))
        if not seen:
            self.skipTest('run folders are not in this checkout')
        self.assertEqual([q for q in [q for q, _ in SETTLED] + ASK if q not in seen], [])

    def test_a_named_line_is_matched_by_what_it_names_not_by_a_word_inside_another(self):
        line = lambda question: checks.standing_line(question)[1]
        self.assertTrue(line('Have you completed a qualification in civil engineering?').startswith('Yes: Bachelor'))
        self.assertTrue(line('Do you hold a Bachelor’s degree in civil engineering or an equivalent qualification?').startswith('Yes: Bachelor'))
        self.assertTrue(line('Have you completed a qualification in engineering drafting / engineering design?').startswith('Yes: Advanced Diploma'))
        for field in ('mechanical engineering', 'structural engineering', 'engineering - fabrication', 'environmental engineering', 'construction management'):
            self.assertEqual(line(f'Have you completed a qualification in {field}?'), '', field)  # 'engineering: Yes' is not the answer, and No is not guessed
        self.assertIn('11 months', line("How many years' experience do you have as a civil engineer?"))
        for role in ('Civil Engineering Technician', 'Civil Estimator'):
            self.assertEqual(line(f"How many years' experience do you have as a {role}?"), 'None: no paid role of this kind', role)
        for role in ('Engineering Cadet', 'structural engineer'):   # an engineering title or word: neither 11 months nor 'none'
            self.assertEqual(line(f"How many years' experience do you have as a {role}?"), '', role)
        self.assertEqual(line('How many years experience in Civil Engineering Design do you have?'), '')
        self.assertEqual(line('Which of the following CAD software do you have experience with?'), 'AutoCAD, Civil 3D, Revit')
        self.assertEqual(line('Do you have experience using Bluebeam?'), 'No')

    def test_a_standing_yes_or_a_months_claim_never_lands_on_a_question_that_asks_something_else(self):
        # Found while fixing: 'Yes, current National Police Certificate' is not the answer to 'Do you have a criminal record?'.
        for trap in ('Do you have a criminal record?', 'Do you have any criminal convictions?', 'Do you use drugs?', 'Have you used illicit drugs in the last six months?',
                     "Have you ever had your driver's licence suspended?", "Do you have any demerit points on your driver's licence?", 'Has your White Card ever been cancelled?',
                     'Is there any reason you could not pass a pre-employment medical?', 'Have you ever been dismissed from a job?', 'Are you able to perform manual handling tasks?',
                     "How many years' experience do you have as a civil engineer in Australia?"):
            key, problem = checks.standing_answer(trap)
            self.assertTrue(problem, trap)
        for question, key in (('Are you willing to undertake Criminal History Screening?', 'police_check'), ('Are you willing to complete a Police Check?', 'police_check'),
                              ('Are you willing to undergo a Pre-Employment Drug & Alcohol Screen?', 'drug_and_alcohol_screening'), ('Are you willing to undergo a drug test?', 'drug_and_alcohol_screening')):
            self.assertEqual(checks.standing_answer(question), (key, None), question)
        line = lambda question: checks.standing_line(question)[1]
        self.assertEqual(line('Do you have Engineering Drawing Interpretation experience?'), 'Yes')
        for more in ('Do you have 3+ years of Engineering Drawing Interpretation experience?', 'Do you have at least 2 years experience carrying out site inspections?',
                     'Do you have Engineering Drawing Interpretation experience in Australia?', 'Do you have extensive experience preparing and submitting tenders?'):
            self.assertEqual(line(more), '', more)  # the 'anything else' row is not a standing answer: the owner's
        self.assertEqual(line("Do you hold an Australian Bachelor's degree in civil engineering?"), '')
        self.assertEqual(line('Have you completed a qualification in civil engineering with honours?'), '')
        for plain in ('civil engineer', 'Civil Site Engineer', 'Assistant Civil Engineer', 'Junior Project Engineer', 'Construction Site Engineer'):
            self.assertIn('11 months', line(f"How many years' experience do you have as a {plain}?"), plain)
        for other in ('Rail Project Engineer', 'Senior Site Engineer', 'Structural Civil Engineer', 'Structural Site Engineer', 'Water and Wastewater Engineer'):
            self.assertEqual(line(f"How many years' experience do you have as a {other}?"), '', other)  # an engineering title facts.json does not cover
        self.assertEqual(line('How many years of Site Engineering experience do you have?'), '')   # a field no row names
        self.assertEqual(line('How many years of experience do you have in the Civil Engineering Industry?'), '')

    def test_one_new_line_in_facts_settles_its_questions(self):
        for question, key, answer in [("What's your expected hourly rate?", 'expected_hourly_rate', '35 to 40 dollars an hour'),
                                      ('Will you require visa sponsorship in the future?', 'future_visa_sponsorship', 'No'),
                                      ('How would you rate your English language skills?', 'english_self_rating', 'Fluent'),
                                      ('Are you a current member of Engineers Australia?', 'engineers_australia_membership_or_recognition', 'No')]:
            self.assertIn(key, checks.standing_answer(question)[1] or '', question)
            with mock.patch.dict(checks.ANSWERS, {key: answer}):
                self.assertEqual(checks.standing_line(question), ('answers.' + key, answer, None), question)
        with mock.patch.dict(checks.ANSWERS, {'experience_yes_no': {**checks.ANSWERS['experience_yes_no'], 'mine site': 'Not on record: skip and report'}}):
            self.assertTrue(checks.standing_answer('Do you have mine site experience?')[1])


class AnswersOnTheRecord(unittest.TestCase):
    """P2-3: a READY record carried the drafter's answers unchecked ('Yes' to citizenship, '3 years', '$95k', 'Marc to confirm')."""
    WRONG = [{'question': "How many years' experience do you have as a civil drafter?", 'answer': '3 years'},
             {'question': 'Which of the following statements best describes your right to work in Australia?', 'answer': 'Yes'},
             {'question': "What's your expected annual base salary?", 'answer': '$95k'},
             {'question': "Do you have a current Australian driver's licence?", 'answer': 'Marc to confirm'}]

    def test_a_ready_record_carries_the_lines_of_facts_json_not_the_drafters_answers(self):
        out, records = build_run({'x': pack('SEEK', screening_answers=self.WRONG)})
        self.assertEqual(([b[3] for b in out['built']], out['rejected']), (['READY_SEEK'], []))
        answers = records[0]['screening_answers']
        self.assertEqual([a['question'] for a in answers], SEEK_QUESTIONS)  # every form question, in the advert's order
        for a in answers:
            self.assertEqual((a['basis'], a['answer']), checks.standing_line(a['question'])[:2], a['question'])
            self.assertEqual(gate.answer(a['question'], [], common.FACTS)['answer'], a['answer'])   # the one gate's answer
            self.assertIsNotNone(checks.fact_at(a['basis']))
        text = json.dumps(answers)
        for wrong in ('3 years', '$95k', 'Marc to confirm'):
            self.assertNotIn(wrong, text)
        self.assertNotEqual({a['question']: a for a in answers}[SEEK_QUESTIONS[0]]['answer'], 'Yes')   # the drafter's 'Yes' to work rights is not kept
        by_question = {a['question']: a for a in answers}
        self.assertEqual(by_question[SEEK_QUESTIONS[0]]['answer'], common.FACTS['answers']['right_to_work']['free_text'])
        self.assertEqual(by_question[SEEK_QUESTIONS[0]]['basis'], 'answers.right_to_work.free_text')
        self.assertTrue(by_question[SEEK_QUESTIONS[1]]['answer'].startswith('No paid drafting role.'))
        self.assertEqual(by_question[SEEK_QUESTIONS[4]]['answer'], '65000 to 75000')
        self.assertEqual(checks.record_issues({**records[0], 'attachments': ATTACHED}, require_uploaded=False), [])

    def test_the_record_check_refuses_an_answer_that_is_not_the_standing_line(self):
        rec = {**publish.build_record('r1', *pack('SEEK')), 'attachments': ATTACHED}
        self.assertEqual(checks.record_issues(rec, require_uploaded=False), [])
        edited = [dict(a) for a in rec['screening_answers']]
        edited[0]['answer'] = 'Australian citizen'
        issues = checks.record_issues({**rec, 'screening_answers': edited}, require_uploaded=False)
        self.assertTrue(any('form answer is not the standing answer in facts.json' in i and 'best describes your right' in i for i in issues))
        moved = [dict(a) for a in rec['screening_answers']]
        moved[1]['basis'] = 'answers.years_of_experience.civil engineer, site engineer, project engineer, construction industry'  # eleven months claimed for a drafter question
        self.assertTrue(any('not the standing answer' in i for i in checks.record_issues({**rec, 'screening_answers': moved}, require_uploaded=False)))
        typed = rec['screening_answers'] + [{'question': 'Are you an Australian citizen or permanent resident?', 'answer': 'Yes'}]
        issues = checks.record_issues({**rec, 'screening_answers': typed}, require_uploaded=False)
        self.assertTrue(any('carries a form answer that is not from facts.json' in i for i in issues))
        old_style = {**rec, 'screening_answers': self.WRONG}  # a record made before this change
        self.assertTrue(any('not from facts.json' in i for i in checks.record_issues(old_style, require_uploaded=False)))
        asked = {**rec, 'advert': {**rec['advert'], 'screening_questions': SEEK_QUESTIONS + ['How would you rate your English language skills?']}}
        self.assertTrue(any('READY_SEEK record has a form question with no standing answer (it must be ASK_OWNER)' in i for i in checks.record_issues(asked, require_uploaded=False)))

    def test_written_answers_that_contradict_facts_fail_the_draft_check(self):
        def issues(question, answer, **extra):
            return checks.draft_issues({'screening_answers': [{'question': question, 'answer': answer}], **extra})
        for question, answer, needle in [
                ("How many years' experience do you have as a civil drafter?", '3 years', 'gives "3 years" where facts.json -> answers -> years_of_experience says'),
                ("How many years' experience do you have as a civil engineer?", 'About 1 year on site in the Philippines', 'gives "1 year"'),
                ('How many years experience in Civil Design do you have?', 'Several years of design work', 'gives "Several years"'),
                ("What's your expected annual base salary?", '$95k', 'salary figure $95k is outside the standing band $65,000 to $75,000'),
                ("What's your expected annual base salary?", '$35 an hour', 'hourly or daily figure ($35)'),
                ("Do you have a current Australian driver's licence?", 'Marc to confirm', 'is a placeholder, not an answer'),
                ('How much notice are you required to give your current employer?', 'MARC TO ANSWER (no notice period on record).', 'is a placeholder, not an answer'),
                ('How much notice are you required to give your current employer?', "None, I'm ready to go now", 'does not give the standing answer in facts.json -> answers -> notice_period: 2 weeks'),
                ('Are you an Australian citizen or permanent resident?', 'Yes', 'says yes to a question that claims citizenship'),
                ('Do you have experience using 12d?', 'Yes', 'says yes to software not in facts: 12d'),
                ('Are you registered as a Registered Professional Engineer of Queensland (RPEQ)?', 'Yes', 'says yes to a question that claims a professional registration'),
                ('Do you have experience preparing and submitting tenders?', 'Yes', 'says yes where facts.json -> answers -> experience_yes_no says: No'),
                ('Are you currently studying?', 'Yes, part time', 'says yes where facts.json -> answers -> currently_studying says: No'),
                ('Do you hold a Construction Induction Safety certificate (White Card)?', 'No', 'says no where facts.json -> answers -> white_card says: Yes'),
                ('Do you own or have regular access to a car?', 'I have no car at the moment', 'says no where facts.json -> answers -> own_car_or_regular_access says: Yes')]:
            self.assertTrue(any(needle in i for i in issues(question, answer)), (question, answer, issues(question, answer)))
        for question, answer in [("How many years' experience do you have as a civil engineer?", 'Less than 1 year (11 months on site, April 2019 to February 2020)'),
                                 ("How many years' experience do you have as a civil drafter?", '0 to 1 years'),
                                 ("What's your expected annual base salary?", '$70,000'), ("What's your expected annual base salary?", '$65,000 to $75,000'),
                                 ('How much notice are you required to give your current employer?', 'Two weeks'),
                                 ('Do you have any experience using Revit, AutoCAD, 12D?', 'Yes'),  # true: Revit and AutoCAD
                                 ('Do you have the right to work in Australia? Please note if you are an Australian citizen / permanent resident or NZ citizen you should answer YES to this question.', 'Yes'),
                                 ('Do you have experience preparing and submitting tenders?', 'No'), ("Do you have a current Australian driver's licence?", 'Yes'),
                                 ("Do you have a current Australian driver's licence?", "I hold a current Victorian driver's licence."),
                                 ('Are you an Australian citizen or permanent resident?', 'No'),
                                 ('What is your current working rights status in Australia?', 'I hold a Subclass 485 Temporary Graduate visa with full working rights. No sponsorship needed.')]:
            self.assertEqual(issues(question, answer), [], (question, answer))
        # The advert's own figure may be given when the draft carries the advert's pay text.
        self.assertEqual(issues("What's your expected annual base salary?", '$80,000', advert_pay='$80,000 to $115,000 plus super'), [])
        self.assertTrue(issues("What's your expected annual base salary?", '$95,000', advert_pay='$80,000 to $115,000 plus super'))

    def test_an_open_question_keeps_the_drafters_proposal_for_the_owner_and_a_placeholder_is_dropped(self):
        why = 'What interests you about joining STP Consultants.'
        given = [{'q': why, 'a': 'Your subdivision and road design work in Perth is the work my Advanced Diploma trained me for.'},
                 {'q': 'How would you rate your English language skills?', 'a': '[Marc to confirm]'},
                 {'q': "How many years' experience do you have as a civil drafter?", 'a': '3 years'}]
        rec = publish.build_record('r1', *pack('SEEK', screening_answers=given))
        self.assertEqual(rec['status'], 'ASK_OWNER')
        by_question = {a['question']: a for a in rec['screening_answers']}
        self.assertEqual(by_question[why], {'question': why, 'draft_answer': given[0]['a']})
        self.assertEqual(by_question['How would you rate your English language skills?'], {'question': 'How would you rate your English language skills?'})
        self.assertEqual(by_question[given[2]['q']]['basis'], 'answers.years_of_experience.drafter, draftsperson, designer, CAD')
        self.assertEqual(checks.record_issues({**rec, 'attachments': ATTACHED}, require_uploaded=False), [])
        # A proposal is still text written for him: it is checked like any other.
        bad = publish.build_record('r1', *pack('SEEK', screening_answers=[{'q': why, 'a': 'I have not used 12d yet, but I am eager to learn.'}]))
        self.assertTrue(any('"have not"' in i for i in checks.record_issues({**bad, 'attachments': ATTACHED}, require_uploaded=False)))

    def test_an_email_application_carries_no_form_answers(self):
        rec = publish.build_record('r1', *pack('EMAIL', SEEK_QUESTIONS, screening_answers=self.WRONG))
        self.assertEqual((rec['status'], rec['screening_answers']), ('PREPARED_NOT_SENT', []))

    def test_an_answer_with_a_basis_must_agree_with_that_line(self):
        entry = {'questions': [{'question': "Do you have a current Australian driver's licence?", 'options': [], 'answer': 'Yes', 'basis': 'answers.drivers_licence', 'status': 'answered'},
                               {'question': "What's your expected annual base salary?", 'answer': '65000 to 75000', 'basis': 'answers.expected_salary.rule'},
                               {'question': 'How would you rate your English language skills?', 'options': [], 'answer': '', 'basis': '', 'status': 'unanswered'}]}
        self.assertEqual(checks.draft_issues(entry), [])
        entry['questions'][0]['answer'] = 'No'
        self.assertTrue(any('contradicts facts.json -> answers.drivers_licence' in i for i in checks.draft_issues(entry)))
        entry['questions'][0].update(answer='Yes', basis='answers.forklift_licence')
        self.assertTrue(any('names a basis that is not in facts.json' in i for i in checks.draft_issues(entry)))
        self.assertEqual(checks.fact_at('answers.software.CAD'), checks.ANSWERS['software']['CAD']); self.assertIsNone(checks.fact_at('answers.software.Tekla')); self.assertIsNone(checks.fact_at(''))


class Routes(unittest.TestCase):
    """P2-4: an email draft with no contacts file was published as READY_SEEK for an advert that is not on SEEK."""

    def employer_site_draft(self, **draft_extra):
        cand, screen, contact, draft = pack('EMAIL', [])
        cand.update(source='employer site', seek_id=None, url='https://pcpsolutions.example/careers/junior-drafter')
        screen['apply_instructions'] = 'Email your resume to admin@pcpsolutions.example'
        draft.update(recipient_email='admin@pcpsolutions.example', recipient_role='Office', contact_evidence_url='https://pcpsolutions.example/careers/junior-drafter', **draft_extra)
        return cand, screen, draft

    def test_an_email_draft_with_no_published_address_is_rejected_never_moved_to_seek(self):
        cand, screen, draft = self.employer_site_draft()
        for contact in (None, {'contact_confidence': 'none'}, {'contact_confidence': 'guessed', 'recipient_email': 'admin@pcpsolutions.example'}):
            out, records = build_run({'pcp': (cand, screen, contact, draft)})
            self.assertEqual((out['built'], records), ([], []), contact)  # it was built as READY_SEEK, route SEEK, with a non-SEEK job_url
            self.assertEqual(out['rejected'][0]['status'], 'PREPARED_NOT_SENT')
            self.assertIn('recipient is neither a published direct contact nor a published application inbox', out['rejected'][0]['issues'])
        published = {'contact_confidence': 'published_inbox', 'recipient_email': 'admin@pcpsolutions.example', 'recipient_role': 'Office', 'contact_evidence_url': 'https://pcpsolutions.example/careers/junior-drafter'}
        out, records = build_run({'pcp': (cand, screen, published, draft)})
        self.assertEqual([b[3] for b in out['built']], ['PREPARED_NOT_SENT']); self.assertEqual(records[0]['application_route'], 'EMAIL')
        self.assertEqual(records[0]['recipient_email'], 'admin@pcpsolutions.example')

    def test_an_address_other_than_the_one_the_employer_publishes_is_not_a_published_address(self):
        cand, screen, draft = self.employer_site_draft(recipient_name='Sam Lee')
        published = {'contact_confidence': 'published_inbox', 'recipient_email': 'careers@pcpsolutions.example', 'recipient_role': 'Careers inbox', 'contact_evidence_url': 'https://pcpsolutions.example/careers'}
        out, records = build_run({'pcp': (cand, screen, published, draft)})  # the draft writes to admin@, the research found careers@
        self.assertEqual(records, []); self.assertIn('recipient is neither a published direct contact nor a published application inbox', out['rejected'][0]['issues'])
        out, records = build_run({'pcp': (cand, screen, published, {**draft, 'recipient_email': 'Careers@PCPsolutions.example'})})
        self.assertEqual([b[3] for b in out['built']], ['PREPARED_NOT_SENT'])

    def test_a_draft_with_no_route_goes_by_its_address_or_its_seek_job_or_nowhere(self):
        cand, screen, draft = self.employer_site_draft(route=None)
        self.assertEqual(publish.route_status(draft, None, cand), ('PREPARED_NOT_SENT', 'EMAIL'))  # it carries an address: an email application
        out, _ = build_run({'pcp': (cand, screen, None, draft)})
        self.assertIn('recipient is neither a published direct contact nor a published application inbox', out['rejected'][0]['issues'])
        with self.assertRaisesRegex(ValueError, 'names no route .* not a SEEK job'):
            publish.route_status({**draft, 'recipient_email': ''}, None, cand)
        out, records = build_run({'pcp': (cand, screen, None, {**draft, 'recipient_email': ''})})
        self.assertEqual(records, []); self.assertIn('names no route', out['rejected'][0]['issues'][0])
        seek_cand = pack('SEEK')[0]
        self.assertEqual(publish.route_status({'route': None}, None, seek_cand), ('READY_SEEK', 'SEEK'))
        self.assertEqual(publish.route_status({'route': ' '}, None, {'url': 'https://au.seek.com/job/95900020?ref=x'}), ('READY_SEEK', 'SEEK'))

    def test_only_the_four_route_names_are_taken(self):
        seek_cand = pack('SEEK')[0]
        for route in ('SEEK quick apply', 'SEEK link-out to the council careers portal', 'Employer portal (iCIMS req 9300)', 'PHONE', 'EMAIL or SEEK'):  # the first three are in real drafts
            with self.assertRaisesRegex(ValueError, 'is not one of EMAIL, SEEK, EMPLOYER_PORTAL, EMPLOYER_FORM'):
                publish.route_status({'route': route}, None, seek_cand)
            out, records = build_run({'x': pack(route)})
            self.assertEqual(records, []); self.assertIn(repr(route), out['rejected'][0]['issues'][0])
        for route, status in (('seek', 'READY_SEEK'), ('employer_portal', 'READY_EMPLOYER_PORTAL'), ('EMPLOYER_FORM', 'READY_EMPLOYER_FORM'), (' email ', 'PREPARED_NOT_SENT')):
            self.assertEqual(publish.route_status({'route': route}, None, seek_cand)[0], status)

    def test_route_seek_needs_a_seek_job(self):
        cand, screen, draft = self.employer_site_draft(route='SEEK')
        with self.assertRaisesRegex(ValueError, 'route SEEK needs a SEEK job'):
            publish.route_status(draft, None, cand)
        self.assertEqual(publish.route_status({**draft, 'route': 'EMPLOYER_PORTAL'}, None, cand), ('READY_EMPLOYER_PORTAL', 'EMPLOYER_PORTAL'))
        self.assertTrue(publish.on_seek({'seek_id': '95900020', 'source': 'seek'}, {})); self.assertTrue(publish.on_seek({}, {'job_url': 'https://www.seek.com.au/job/95900020'}))
        self.assertFalse(publish.on_seek({'seek_id': 'pcp', 'source': 'employer site', 'url': 'https://pcpsolutions.example/careers'}, {}))


class ReviewMinorFindings(unittest.TestCase):
    def test_the_channel_of_a_record_is_its_route_not_its_status(self):  # P2-5
        rec = {**publish.build_record('r1', *pack('EMAIL', [])), 'attachments': ATTACHED}
        for status in ('PREPARED_NOT_SENT', 'SENDING', 'SENT', 'SEND_UNCERTAIN', 'DELIVERY_FAILED'):
            self.assertEqual(checks.record_issues({**rec, 'status': status}, require_uploaded=False), [], status)  # SENDING gave a false 'one channel' issue
        blank = {**rec, 'status': 'SENDING', 'recipient_email': '', 'contact_confidence': 'none', 'contact_evidence_url': ''}
        issues = checks.record_issues(blank, require_uploaded=False)
        for needle in ('missing recipient_email', 'missing contact_evidence_url', 'recipient is neither a published direct contact nor a published application inbox'):
            self.assertIn(needle, issues)  # these checks were skipped once the status was SENDING
        self.assertFalse(any('one channel' in i for i in issues))
        for status in ('READY_SEEK', 'READY_JEREMIE_SEEK', 'READY_EMPLOYER_PORTAL'):  # a READY record that carries an email: the retired double touch
            self.assertTrue(any('one channel' in i for i in checks.record_issues({**rec, 'status': status}, require_uploaded=False)), status)
        no_route = {k: v for k, v in rec.items() if k != 'application_route'}  # an older record without the field
        self.assertEqual(checks.record_issues({**no_route, 'status': 'SENT'}, require_uploaded=False), [])
        self.assertIn('missing recipient_email', checks.record_issues({**no_route, 'recipient_email': ''}, require_uploaded=False))

    def test_a_queue_entry_that_asks_in_one_line_of_text_does_not_crash_the_record_check(self):
        entry = {'company': 'Griffith City Council', 'role': 'Graduate Traffic and Design Engineer', 'status': 'ASK_OWNER', 'route': 'EMPLOYER_PORTAL',
                 'ask_owner': 'Griffith City Council asks for an engineering degree acceptable to Engineers Australia: is yours?', 'questions': []}
        issues = checks.record_issues(entry, require_uploaded=False)  # AttributeError before: 'str' object has no attribute 'get'
        self.assertFalse(any('needs the question' in i for i in issues))
        self.assertTrue(any('needs the question' in i for i in checks.record_issues({**entry, 'ask_owner': ''}, require_uploaded=False)))

    def test_console_job_claims_worded_without_the_word_experience(self):  # P2-6
        claim = 'presents the casual console operator job as civil experience (facts: it is current Australian work, nothing more)'
        for bad in ('At bp I have gained hands-on site engineering experience since 2024.',
                    'As a console operator I coordinate site works and inspect civil drainage installations.',
                    'I work as a console operator, which has built my civil construction skills on Australian sites.',
                    'My Australian work since May 2024 has given me experience on civil sites.',
                    'Since May 2024 I have worked in Australia in a civil construction support role.',
                    'My current job in Rockbank has given me construction site experience.',
                    'I currently work in a design and drafting support role at Rampage Group.'):
            self.assertIn(claim, checks.fact_issues(bad), bad)
        for fine in ('Since May 2024 I have worked as a casual console operator at bp Rockbank alongside full-time study in the Advanced Diploma of Civil Construction Design.',
                     'I have worked as a console operator at a service station since May 2024 while studying civil design.',
                     'I bring site inspection experience from the Philippines and current Australian work as a console operator.',
                     'I currently work as a casual console operator. My civil site experience is from 2019.',
                     'I work casually at a service station in Rockbank while looking for my first civil drafting role in Australia.',
                     'My current job is casual console operator work at bp Rockbank.',
                     'I currently work casually as a console operator and want to return to site engineering.',
                     'Since February 2024 I have designed road geometry, earthworks and stormwater drainage in the Advanced Diploma.',
                     GOOD_EMAIL, '\n'.join(GOOD_LETTER)):
            self.assertNotIn(claim, checks.fact_issues(fine), fine)

    def test_duplicate_rule_blocks_where_the_record_does_not_say(self):  # P2-7
        # 1. A SEEK link-out: the record's URL is the employer's page, its seek_id is the SEEK job.
        idx = index({'company': 'Shire of Bramble', 'role': 'Technical Officer', 'status': 'READY_EMPLOYER_PORTAL', 'seek_id': '95900999', 'job_url': 'https://bramble.example/jobs/tech-officer'})
        blocked, why, _ = dup({'company': 'Bramble Shire Council', 'title': 'Engineering Technical Officer', 'seek_id': '95900999', 'url': 'https://www.seek.com.au/job/95900999'}, idx)
        self.assertTrue(blocked); self.assertIn('same SEEK job', why)
        self.assertTrue(dup({'company': 'X', 'title': 'Y', 'url': 'https://au.seek.com/job/95900999'}, index({'company': 'Z', 'role': 'W', 'status': 'LEAD', 'seek_id': 95900999}))[0])
        # 2. A receipt that does not name the role (a real entry of prior_outreach.json).
        receipt = {'date': days_ago(24), 'company': 'Gamuda', 'role': 'employer portal application receipt (position name blank in the email)', 'gmail_message_id': 'g1'}
        blocked, why, _ = dup({'company': 'Gamuda Australia', 'title': 'Graduate Engineer', 'seek_id': '95900998'}, index(receipts=[receipt]))
        self.assertTrue(blocked); self.assertIn('does not say for which role', why)
        blocked, _, notes = dup({'company': 'Gamuda Australia', 'title': 'Graduate Engineer', 'seek_id': '95900998'}, index(receipts=[{**receipt, 'date': days_ago(200)}]))
        self.assertFalse(blocked); self.assertIn('role not recorded, outside the repeat block', notes[0])
        for role, unknown in (('', True), ('email to workers@alphacps.example', True), ('graduate application via the employer portal (reply in thread)', True),
                              ('Engineering Technician (employer portal application received)', False), ('Graduate Civil Engineer', False), ('Civil Engineering Opportunities', False)):
            self.assertEqual(tracker.role_unknown(role), unknown, role)
        # 3. A date the window cannot be measured from.
        applied = {'company': 'Northgate Civil Design', 'role': 'Junior Civil Drafter', 'status': 'MANUAL_APPLIED'}
        advert = DuplicateRule.ADVERT
        day_first = TODAY - timedelta(days=1)
        blocked, why, _ = dup(advert, index({**applied, 'applied_date': day_first.strftime('%d/%m/%Y')}))
        self.assertTrue(blocked); self.assertIn(day_first.strftime('%Y-%m-%d'), why)  # read as text it looked older than the window
        blocked, why, _ = dup(advert, index({**applied, 'applied_date': 'last Tuesday'}))
        self.assertTrue(blocked); self.assertIn('date not readable', why)
        self.assertFalse(dup(advert, index({**applied, 'applied_date': (TODAY - timedelta(days=200)).strftime('%d/%m/%Y')}))[0])
        self.assertEqual([tracker.day(x) for x in ('2026-11-12', '2026-11-12T03:00:00.000Z', '12/11/2026', '1.2.2026', '', None, 'soon', '2026-13-45', '31/02/2026')],
                         ['2026-11-12', '2026-11-12', '2026-11-12', '2026-02-01', '', '', None, None, None])
        # A status typed by hand in another case is still a submission.
        self.assertTrue(dup(advert, index({**applied, 'status': ' Sent ', 'sent_at': days_ago(3)}))[0])

    def test_letter_shape_cannot_be_passed_by_formatting(self):  # P2-8
        self.assertTrue(any('4 paragraphs' in i for i in checks.draft_issues({'letter': {'paragraphs': ['One.\n\nTwo.\n\nThree.\n\nFour.']}})))
        self.assertTrue(any('5 paragraphs' in i for i in checks.draft_issues({'cover_letter_text': 'Para one.\nPara two.\nPara three.\nPara four.\nPara five.'})))
        self.assertEqual(checks.draft_issues({'cover_letter_text': 'One.\n\nTwo, with\na line break.\n\nThree.'}), [])
        self.assertEqual(checks.draft_issues({'letter': {'paragraphs': GOOD_LETTER}}), [])

    def test_the_subject_of_a_queue_entry_email_is_checked(self):  # P2-8
        entry = {'email': {'subject': 'Junior Drafter – application', 'body': 'Hello,\n\nShort note.\n\nMarc'}}
        self.assertTrue(any(i.startswith('email subject banned character') for i in checks.draft_issues(entry)))
        self.assertEqual(checks.draft_issues({'email': {'subject': 'Junior Drafter application, Marc Masarate', 'body': 'Hello,\n\nShort note.\n\nMarc'}}), [])
        closing = checks.draft_issues({'letter': {'paragraphs': ['One.', 'Two.', 'Three.'], 'closing': 'Yours — Marc'}})  # the closing line is printed in the letter too
        self.assertTrue(any(i.startswith('letter closing banned character') for i in closing))
        self.assertEqual(checks.draft_issues({'letter': {'paragraphs': ['One.', 'Two.', 'Three.'], 'closing': 'Kind regards,'}}), [])
        self.assertTrue(any('has 1 paragraphs' in i for i in checks.draft_issues({'letter': {'paragraphs': ['One.']}})))   # exactly three

    def test_the_visa_end_date_however_it_is_written(self):  # P2-8
        for text in ('I hold a Subclass 485 visa valid through 2027.', 'My visa runs until 12/2027.', 'Full working rights until Dec. 2027.',
                     'Full working rights until the end of 2027.', 'My 485 visa ends in December\n2027.', 'My visa expires in 2027.', 'I can work here through late 2027.'):
            self.assertTrue(any('visa end date' in i for i in checks.tone_issues(text, 'letter')), text)
            self.assertFalse(any('visa end date' in i for i in checks.tone_issues(text, 'letter', visa_asked=True)), text)
        for text in (common.FACTS['eligibility']['work_rights_short'], 'I am applying through SEEK for your 2027 graduate intake.', 'I finished the Advanced Diploma in February 2026.',
                     'Your 2027 program on the North East Link is why I am writing.'):
            self.assertFalse(any('visa end date' in i for i in checks.tone_issues(text, 'letter')), text)

    def test_limit_patterns_match_whole_words(self):  # P2-8
        for fine in ('I have nothing but respect for your road projects.', 'I have noted your work on the Melton Highway upgrade.', 'Although it rained, the pour went ahead.',
                     'Your notice says the role starts in January.'):
            self.assertEqual([i for i in checks.tone_issues(fine, 'letter') if 'volunteers' in i], [], fine)
        for bad, pattern in (('I have not used 12d.', 'have not'), ('Although I studied surveying, my design work is in Civil 3D.', 'although i'), ('I have not, so far, worked in a laboratory.', 'have not')):
            self.assertTrue(any(f'"{pattern}"' in i for i in checks.tone_issues(bad, 'letter')), bad)

    def test_an_end_row_written_with_another_case_or_a_space_is_still_checked(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(journal, 'JOURNAL', Path(d) / 'journal.jsonl'):
            for stage in ('END', ' end', 'End '):
                with self.assertRaises(ValueError):
                    journal.note('r', stage=stage, new=2, held=1)  # it was written unchecked and then ignored by weekly
            row = journal.note('r', stage=' END ', **END)
            self.assertEqual(row['stage'], 'end'); self.assertEqual(journal.weekly()[0]['applied'], END['applied'])


if __name__ == '__main__':
    unittest.main()
