"""Offline regression tests. No tracker, mailbox or credentials are accessed."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import checks
import common
import publish
import render_pdf
import seek
import tracker


class ReliabilityTests(unittest.TestCase):
    def test_missing_or_malformed_mandatory_check_is_not_clear(self):
        good = {'open': True, 'mandatory_unmet': [], 'mandatory_unresolved': [], 'percent': 70}
        self.assertEqual(publish.eligibility_issues({}, good), [])
        for key in ('mandatory_unmet', 'mandatory_unresolved'):
            for value in (None, False, '', {}, ['Unknown licence']):
                self.assertTrue(publish.eligibility_issues({}, {**good, key: value}))
            missing = dict(good)
            missing.pop(key)
            self.assertTrue(publish.eligibility_issues({}, missing))

    def test_final_record_retains_mandatory_evidence(self):
        screen = {'mandatory_unmet': [], 'mandatory_unresolved': ['Licence unknown']}
        rec = publish.build_record('test', {'company': 'Example', 'title': 'Junior Civil'}, screen, {}, {})
        self.assertEqual(rec['mandatory_unmet'], [])
        self.assertEqual(rec['mandatory_unresolved'], ['Licence unknown'])
        self.assertTrue(any('mandatory_unmet' in issue for issue in checks.record_issues(rec)))

    def test_invalid_draft_is_rejected_before_render_or_upload(self):
        screen = {'open': True, 'mandatory_unmet': [], 'mandatory_unresolved': [], 'percent': 70,
                  'rationale': 'Junior role', 'gaps': ['Academic software']}
        candidate = {'company': 'Example', 'title': 'Junior Civil Drafter', 'url': 'https://example.com/job'}
        draft = {'company': 'Example', 'role': 'Junior Civil Drafter', 'route': 'SEEK',
                 'email_body': 'I am a permanent resident.', 'letter': {'paragraphs': ['Short letter.']}}
        with tempfile.TemporaryDirectory() as folder, \
             mock.patch.object(publish, 'load_run', return_value=(Path(folder), {'1': candidate}, {'1': screen}, {}, {'1': draft})), \
             mock.patch.object(render_pdf, 'render_letter') as render, \
             mock.patch.object(tracker, 'upload_document') as upload, \
             mock.patch.object(tracker, 'add_records') as add:
            result = publish.publish('test', go=True)
            self.assertEqual(result['built'], [])
            self.assertTrue(result['rejected'])
            render.assert_not_called()
            upload.assert_not_called()
            add.assert_not_called()

    def test_runner_override_is_explicit_and_leaves_default_unchanged(self):
        saved = {'contributor_name': 'Grok AI', 'created_by': 'grok-job-search', 'code_file': 'existing'}
        self.assertEqual(common.configure_runner(copy.deepcopy(saved), ''), saved)
        codex = common.configure_runner(copy.deepcopy(saved), 'codex')
        self.assertEqual(codex['created_by'], 'codex-job-search')
        self.assertEqual(codex['contributor_name'], 'Codex')
        self.assertEqual(codex['code_file'], saved['code_file'])
        with self.assertRaises(ValueError):
            common.configure_runner({}, 'unknown-runner')

    def test_capacity_matches_wire_encoding_and_does_not_write(self):
        state = {'notes': '\u00e9' * 4}
        expected = len(json.dumps({'expected_version': 2, 'state': state}).encode('utf-8'))
        self.assertEqual(tracker.state_capacity(2, state)['request_bytes'], expected)
        with mock.patch.object(tracker, 'get_state', return_value=(2, state)), \
             mock.patch.object(tracker, 'MAX_STATE_BYTES', expected - 1), \
             mock.patch.object(tracker, 'put_state') as put:
            with self.assertRaisesRegex(RuntimeError, 'capacity blocked before write'):
                tracker._guarded(lambda current: {'changed': True})
            put.assert_not_called()

    def test_explicit_pdf_backend_does_not_launch_browser(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.dict(os.environ, {'JOB_SEARCH_PDF_BACKEND': 'reportlab'}), \
             mock.patch.object(render_pdf, 'chrome_path') as chrome, \
             mock.patch.object(render_pdf, 'render_letter_reportlab', return_value='output') as render:
            self.assertEqual(render_pdf.render_letter({'paragraphs': ['Example']}, Path(directory) / 'out.pdf'), 'output')
            chrome.assert_not_called()
            render.assert_called_once()

    def test_junior_support_titles_reach_full_advert_screen(self):
        for title in ('Junior Civil Project Manager', 'Junior Estimator / Contract Administrator'):
            self.assertTrue(seek.prefilter({'title': title})[0], title)
        for title in ('Senior Civil Project Manager', 'Civil Project Manager', 'Junior Software Engineering Manager'):
            self.assertFalse(seek.prefilter({'title': title})[0], title)


if __name__ == '__main__':
    unittest.main()
