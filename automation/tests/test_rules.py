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
        self.assertEqual(publish.route_status(draft, contact), ('READY_SEEK', 'SEEK'))
        rec = publish.build_record('r1', cand, screen, contact, draft)
        self.assertEqual(rec['status'], 'READY_SEEK')
        for field in ('recipient_email', 'contact_email', 'email_body', 'subject', 'contact_evidence_url'):
            self.assertNotIn(field, rec)
        self.assertNotIn('ouble touch', json.dumps(rec)); self.assertNotIn('Jeremie', json.dumps(rec))
        self.assertEqual(checks.record_issues({**rec, 'attachments': [{'kind': 'resume'}, {'kind': 'cover'}]}, require_uploaded=False), [])
        with_email = {**rec, 'attachments': [{'kind': 'resume'}, {'kind': 'cover'}], 'recipient_email': 'careers@wattlebrook.example', 'email_body': 'Hello,\n\nShort note.'}
        self.assertTrue(any('one channel' in i for i in checks.record_issues(with_email, require_uploaded=False)))
        self.assertEqual(publish.route_status({**draft, 'route': 'EMAIL'}, contact), ('PREPARED_NOT_SENT', 'EMAIL'))
        self.assertEqual(publish.route_status({**draft, 'route': 'EMAIL'}, {'contact_confidence': 'none'}), ('READY_SEEK', 'SEEK'))

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
                ('Will you require visa sponsorship in the future?', 'right_to_work'),
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
                ('Have you completed a qualification in mechanical engineering?', 'qualification_questions'),
                ("How many years' experience do you have as a civil engineer?", 'years_of_experience'),
                ("How many years' experience do you have as an AutoCAD Draftsperson?", 'years_of_experience'),
                ('Which of the following CAD software do you have experience with?', 'software'),
                ('Do you have Engineering Drawing Interpretation experience?', 'experience_yes_no'),
                ('Do you have experience preparing and submitting tenders?', 'experience_yes_no'),
                ('Do you currently reside in Australia?', 'identity.location')]:
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
        licence = {'drivers_licence': 'Yes. If the form asks full or probationary, or manual or automatic: not confirmed, skip and report.'}
        with mock.patch.dict(checks.ANSWERS, licence):
            self.assertEqual(checks.standing_answer("Do you hold a valid driver's licence?"), ('drivers_licence', None))
            self.assertTrue(checks.standing_answer('Are you licenced to drive a manual vehicle?')[1])
            self.assertTrue(checks.standing_answer("Do you hold a full, unrestricted driver's licence?")[1])
        with mock.patch.dict(checks.ANSWERS, {'drivers_licence': "Yes, full Victorian driver's licence. If the form asks manual or automatic: automatic. Never tick manual."}):
            self.assertEqual(checks.standing_answer('Are you licenced to drive a manual vehicle?'), ('drivers_licence', None))
        with mock.patch.dict(checks.ANSWERS, {'english_self_rating': 'Fluent'}):
            self.assertEqual(checks.standing_answer('What is your level of English?'), ('english_self_rating', None))
        with mock.patch.dict(checks.ANSWERS, clear=True):
            self.assertIn('has no "notice_period"', checks.standing_answer('What is your notice period?')[1])

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
        letter = {'paragraphs': ['The advert asks about visa status. I hold a Subclass 485 Temporary Graduate visa with full working rights until December 2027. No sponsorship needed.']}
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
HEADINGS = ('Professional profile', 'Key capabilities', 'Current work in Australia', 'Relevant experience', 'Education',
            'Standards and methods (Advanced Diploma coursework)', 'Additional professional experience', 'Licences and work eligibility', 'Professional strengths')


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

    def test_job_title_with_a_dash_survives_in_the_resume(self):
        text = '\n'.join(pdf_pages(compact_pdf.resume_pdf(self.out('r.pdf'))))
        self.assertIn('Technical Support Representative - Microsoft Software', text)
        self.assertNotIn('Representative to Microsoft', text)
        self.assertIn('Mar 2020 to', text); self.assertIn('2014 to 2019', text)

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

    def test_no_page_of_the_resume_ends_with_a_heading_or_a_job_line(self):
        job_starts = [x['role'][:25] for x in common.FACTS['experience']] + [x['qualification'][:25] for x in common.FACTS['education']]
        for lane in ('drafter', 'technician', 'engineer'):
            for page in pdf_pages(compact_pdf.resume_pdf(self.out(f'{lane}.pdf'), lane=lane)):
                lines = [l.strip() for l in page.splitlines() if l.strip()]
                self.assertNotIn(lines[-1], HEADINGS, (lane, lines[-1]))
                self.assertFalse(any(lines[-1].startswith(s) or lines[-2].startswith(s) for s in job_starts), (lane, lines[-2:]))

    def test_company_line_is_printed_only_when_it_is_a_street_address(self):
        for line, wanted in [('Level 20, 2 Market Street, Sydney NSW', True), ('10 Cummins Drive, Somerton VIC 3062', True), ('PO Box 63, Gunnedah NSW 2380', True),
                             ('Unit 4/12-14 Smith St, Melton', True), ('Gunnedah NSW', False), ('', False), (None, False),
                             ('PCP Solutions is a Toowoomba civil earthworks and commercial plumbing business delivering large scale infrastructure works for Tier 1 contractors across South East Queensland.', False),
                             ('A consultancy of 20 road designers', False)]:
            self.assertEqual(compact_pdf.is_street_address(line), wanted, line)
        letter = {'recipient_name': 'Hiring Team', 'company': 'PCP Solutions Pty Ltd', 'subject': 'Graduate Civil Engineer, Toowoomba', 'paragraphs': ['One.'],
                  'company_line': 'PCP Solutions is a Toowoomba civil earthworks and commercial plumbing business delivering large scale infrastructure works.'}
        text = pdf_pages(compact_pdf.letter_pdf(letter, self.out('l1.pdf')))[0]
        self.assertIn('PCP Solutions Pty Ltd', text); self.assertNotIn('commercial plumbing business', text)
        text = pdf_pages(compact_pdf.letter_pdf({**letter, 'company_line': 'Level 20, 2 Market Street, Sydney NSW'}, self.out('l2.pdf')))[0]
        self.assertIn('Level 20, 2 Market Street, Sydney NSW', text)

    def test_current_australian_job_is_listed_first_and_not_as_civil_experience(self):
        text = '\n'.join(pdf_pages(compact_pdf.resume_pdf(self.out('r.pdf'))))
        order = [text.index(s) for s in ('Current work in Australia', 'Console Operator (casual)', 'Relevant experience', 'Project-in-Charge Engineer', 'Field Engineer', 'Additional professional experience', 'Technical Support Representative')]
        self.assertEqual(order, sorted(order))
        self.assertIn('May 2024 to present', text)
        self.assertEqual(text.count('Console Operator'), 1)

    def test_lane_headline_and_short_work_rights_line(self):
        titles = common.FACTS['identity']['titles']
        flat = lambda s: ' '.join(s.split())
        for lane in ('drafter', 'technician', 'engineer'):
            first = flat(pdf_pages(compact_pdf.resume_pdf(self.out(f'{lane}.pdf'), lane=lane))[0])
            self.assertIn(flat(titles[lane]), first)
            self.assertNotIn('Graduate Civil Engineer', first)
        text = flat('\n'.join(pdf_pages(compact_pdf.resume_pdf(self.out('r.pdf')))))
        self.assertLess(text.index('Full working rights in Australia (Subclass 485 visa), no sponsorship needed'), text.index('Professional profile'))
        self.assertEqual(text.count('December 2027'), 1)  # the end date stays in the eligibility section only
        self.assertGreater(text.index('December 2027'), text.index('Licences and work eligibility'))
        self.assertEqual(compact_pdf.headline('nonsense'), common.FACTS['identity']['title'])
        letter = flat(pdf_pages(compact_pdf.letter_pdf({'paragraphs': ['One.'], 'lane': 'technician'}, self.out('l.pdf')))[0])
        self.assertIn(flat(titles['technician']), letter)
        with redirect_stdout(io.StringIO()):
            compact_pdf.main(['resume', self.out('cli.pdf'), '--lane', 'engineer'])
        self.assertIn(flat(titles['engineer']), flat(pdf_pages(self.out('cli.pdf'))[0]))


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


if __name__ == '__main__':
    unittest.main()
