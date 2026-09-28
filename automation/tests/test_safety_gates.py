"""Regression checks for duplicate batches and unverified preparation being published."""
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tracker
import publish
import checks
import render_pdf


class SafetyGates(unittest.TestCase):
    def test_equivalent_rows_in_same_batch_are_not_both_added(self):
        state = {'applications': [], 'leads': [], 'manual_entries': []}
        first = tracker.new_record({'company': 'Acme Civil', 'role': 'Junior Drafter', 'status': 'PREPARED_NOT_SENT', 'job_url': 'https://www.seek.com.au/job/123'})
        second = tracker.new_record({'company': 'Acme Civil Pty Ltd', 'role': 'Graduate Drafter', 'status': 'PREPARED_NOT_SENT', 'job_url': 'https://au.seek.com/job/123?source=x'})
        with mock.patch.object(tracker, 'get_state', return_value=(4, state)), mock.patch.object(tracker, 'put_state', return_value=(200, {'version': 5})):
            result = tracker.add_records([first, second])
        self.assertEqual(result['result']['added'], [first['id']])
        self.assertEqual(len(result['result']['skipped']), 1)
        self.assertEqual(len(state['manual_entries']), 1)
        self.assertNotIn('_skipped', second)

    def test_undated_or_old_uncertain_employer_stays_blocked(self):
        for date in ('', '2020-01-01'):
            idx = tracker.dedupe_index({'applications': [{'company': 'Acme Civil', 'role': 'Other', 'status': 'SEND_UNCERTAIN', 'sent_at': date}]})
            blocked, why, _ = tracker.check_duplicate({'company': 'Acme Civil', 'title': 'New role'}, idx)
            self.assertTrue(blocked)
            self.assertIn('unresolved', why)

    def test_ineligible_or_unverified_adverts_never_pass(self):
        good = {'open': True, 'mandatory_unmet': [], 'percent': 70}
        self.assertEqual(publish.eligibility_issues({}, good), [])
        for patch in ({'open': False}, {'open': None}, {'mandatory_unmet': ['Must know Pryda']}, {'mandatory_unmet': None}, {'percent': 59}):
            self.assertTrue(publish.eligibility_issues({}, {**good, **patch}))
        self.assertTrue(publish.eligibility_issues({'is_expired': True}, good))
        self.assertTrue(publish.eligibility_issues({'expires_at': '2020-01-01T00:00:00Z'}, good))
        spec = {'application_type': 'SPECULATIVE_ENQUIRY', 'vacancy_status': 'NO_ADVERTISED_VACANCY_VERIFIED'}
        self.assertEqual(publish.eligibility_issues({}, {**good, 'open': False, 'company_work_verified': True}, spec), [])

    def test_dry_build_records_cannot_be_published(self):
        with mock.patch.object(tracker, 'get_state') as get:
            with self.assertRaisesRegex(ValueError, 'dry-build'):
                tracker.add_records([{'preparation_only': True}])
            get.assert_not_called()

    def test_placeholder_document_hash_is_not_ready(self):
        bad = {'attachments': [{'kind': 'resume', 'stored_in': 'cloudflare_r2', 'sha256': 'pending'}]}
        self.assertTrue(any('attachment not in R2' in x for x in checks.record_issues(bad)))

    def test_upload_hash_must_match_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'resume.pdf'
            path.write_bytes(b'%PDF-test-exact-bytes')
            with mock.patch.object(tracker, 'request', return_value=(201, {'sha256': '0' * 64})):
                with self.assertRaisesRegex(RuntimeError, 'hash does not match'):
                    tracker.upload_document(path, 'resume')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with mock.patch.object(tracker, 'request', return_value=(201, {'sha256': digest})):
                self.assertEqual(tracker.upload_document(path, 'resume')['sha256'], digest)

    def test_runbook_nested_draft_renders_its_letter(self):
        html = render_pdf.letter_html({'letter': {'company': 'Acme', 'subject': 'Graduate role', 'paragraphs': ['Actual letter text.']}})
        self.assertIn('Actual letter text.', html)
        with self.assertRaisesRegex(ValueError, 'no paragraphs'):
            render_pdf.letter_html({})
