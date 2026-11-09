"""Synthetic offline fixtures only; no credentials or services required."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import health


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / 'journal.jsonl'
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps({'contributor_name': 'Grok AI', 'created_by': 'grok-job-search',
            'schedule': {'every_hours': 5}, 'code_file': '/never/read/secret', 'sending': {'channel': 'private@example.com'}}))
        self.now = health.date('2026-11-09T12:00:00Z')

    def write_events(self, *rows):
        self.journal.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')

    def event(self, rid='20261109T1000Z', at='2026-11-09T10:00:00Z', **extra):
        return dict(run_id=rid, at=at, **extra)

    def report(self, **kwargs):
        return health.build_report(self.journal, self.config, now=self.now, **kwargs)

    def test_conflict_branches_and_malformed_lines_are_excluded(self):
        self.journal.write_text('\n'.join(['<<<<<<< HEAD', json.dumps(self.event(stage='end', sent=1)),
            '=======', json.dumps(self.event(stage='end', sent=2)), '>>>>>>> other',
            '{broken private@example.com', '[]', json.dumps(self.event(stage='start'))]))
        report = self.report()
        self.assertEqual(report['journal']['valid_events'], 1)
        codes = [i['code'] for i in report['journal']['issues']]
        self.assertEqual(codes.count('CONFLICT_MARKER'), 3)
        self.assertEqual(codes.count('CONFLICT_CONTENT_EXCLUDED'), 2)
        self.assertIn('MALFORMED_JSON', codes)
        self.assertIn('INVALID_EVENT', codes)
        self.assertEqual(report['runner']['code'], 'NO_RECORDED_END')
        self.assertNotIn('private@example.com', json.dumps(report))

    def test_distinct_runs_latest_end_and_blocker_windows(self):
        self.write_events(self.event(stage='start'), self.event(stage='end', sent=0, send='skipped_no_lease'),
            self.event(at='2026-11-09T11:00:00Z', stage='end', sent=1, reason='HTTP 413 tracker full'),
            self.event(rid='20261001T0000Z', at='2026-10-01T00:00:00Z', stage='end', reason='413 tracker full'))
        report = self.report()
        self.assertEqual(report['journal']['distinct_runs'], 2)
        self.assertEqual(len(report['latest_distinct_runs']), 2)
        self.assertEqual(report['latest_distinct_runs'][0]['reported_counts']['sent'], 1)
        self.assertEqual(report['latest_distinct_runs'][0]['end_event_count'], 2)
        self.assertEqual(report['recent_blockers']['distinct_run_counts'], {'HTTP_413': 1, 'TRACKER_FULL': 1, 'SKIPPED_NO_LEASE': 1})
        self.assertEqual(report['runner']['code'], 'RECENT_RECORDED_END')

    def test_stale_future_and_invalid_dates(self):
        self.write_events(self.event(at='2026-10-01T00:00:00Z', stage='end'), self.event(at='bad', stage='end'))
        self.assertEqual(self.report()['runner']['code'], 'STALE_RECORDED_END')
        self.assertIn('INVALID_EVENT_DATE', [i['code'] for i in self.report()['journal']['issues']])
        self.write_events(self.event(at='2027-01-01T00:00:00Z', stage='end'))
        self.assertEqual(self.report()['runner']['code'], 'FUTURE_END_DATE')

    def test_snapshot_distinguishes_claims_from_evidence(self):
        self.write_events(self.event(stage='end', sent=10))
        snapshot = self.root / 'snapshot.json'
        snapshot.write_text(json.dumps({'state': {'applications': [
            {'id': 'a', 'status': 'SENT', 'sent_at': '2026-11-08', 'gmail_message_id': 'receipt'},
            {'id': 'b', 'status': 'SENT', 'email_body': 'private body'},
            {'id': 'c', 'status': 'MANUAL_APPLIED', 'applied_date': '2026-11-08'},
            {'id': 'd', 'status': 'INTERVIEW', 'interview_at': '2026-11-08', 'interview_event_id': 'evt'},
            {'id': 'e', 'status': 'REPLIED', 'reply_at': '2026-11-08', 'reply_message_id': 'reply'},
            {'id': 'f', 'status': 'PREPARED_NOT_SENT'},
            {'id': 'g', 'status': 'READY_JEREMIE_SEEK'},
            {'id': 'duplicate', 'status': 'SENT'}, {'id': 'duplicate', 'status': 'LEAD'}]}}))
        report = self.report(snapshot=snapshot)
        counts = report['tracker']['reported_current_status_counts']
        self.assertEqual({k: counts[k] for k in ('sent', 'applied', 'prepared', 'ready')}, {'sent': 2, 'applied': 1, 'prepared': 1, 'ready': 1})
        self.assertEqual(report['tracker']['evidence_backed_current_status_counts'], {'sent': 1, 'applied': 0, 'response': 1, 'interview': 1})
        self.assertEqual(report['tracker']['conflicting_record_ids_excluded'], 1)
        self.assertFalse(report['tracker']['verified_against_live_services'])
        self.assertNotIn('private body', json.dumps(report))

    def test_cli_does_not_write_read_secret_or_network(self):
        self.write_events(self.event(rid='private@example.com', stage='end', note='secret body'))
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        original = Path.read_text
        reads = []
        def guarded_read(path, *args, **kwargs):
            reads.append(path)
            self.assertIn(path, (self.journal, self.config))
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', guarded_read), mock.patch('socket.socket', side_effect=AssertionError('network')), contextlib.redirect_stdout(io.StringIO()) as out:
            health.main(['--journal', str(self.journal), '--config', str(self.config), '--now', '2026-11-09T12:00:00Z'])
        report = json.loads(out.getvalue())
        self.assertEqual(report['config']['contributor_name'], 'Grok AI')
        self.assertEqual(report['tracker']['code'], 'NO_SNAPSHOT')
        for secret in ('private@example.com', 'secret body', '/never/read/secret'):
            self.assertNotIn(secret, out.getvalue())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertEqual(len(reads), 2)

    def snapshot_report(self, state):
        path = self.root / 'snapshot.json'
        path.write_text(json.dumps(state))
        before = path.read_bytes()
        result = health.snapshot_counts(path)
        self.assertEqual(path.read_bytes(), before)
        return result

    def test_manual_origin_replaces_pending_and_keeps_history(self):
        automatic = {'key': 'job:a', 'company': 'Acme', 'role': 'Civil Engineer',
                     'status': 'READY_JEREMIE_SEEK', 'job_url': 'https://seek.com.au/job/1'}
        manual = dict(automatic, id='m1', key='manual:m1', origin_key='job:a',
                      status='MANUAL_APPLIED', applied_date='2026-11-08', application_method='SEEK')
        result = self.snapshot_report({'leads': [automatic], 'manual_entries': [manual]})
        self.assertEqual(result['reported_current_status_counts']['ready'], 0)
        self.assertEqual(result['reported_current_status_counts']['applied'], 1)
        self.assertEqual(result['automatic_records_replaced'], 1)
        self.assertEqual(result['input_records'], 2)
        self.assertEqual(result['effective_active_records'], 1)

    def test_manual_fallback_url_and_names_without_merging_other_roles(self):
        result = self.snapshot_report({'leads': [
            {'key': 'a', 'company': 'One', 'role': 'Civil', 'status': 'PREPARED_NOT_SENT', 'job_url': 'https://EXAMPLE.com/job/1/?tracking=x'},
            {'key': 'b', 'company': 'ACME Pty.', 'role': 'Civil Engineer', 'status': 'READY_JEREMIE_SEEK'},
            {'key': 'c', 'company': 'Acme Pty', 'role': 'Structural Engineer', 'status': 'READY_JEREMIE_SEEK'}],
            'manual_entries': [
            {'id': 'm1', 'company': 'Renamed', 'role': 'Civil', 'status': 'MANUAL_APPLIED', 'job_url': 'https://example.com/job/1'},
            {'id': 'm2', 'company': 'Acme Pty', 'role': 'Civil-Engineer', 'status': 'MANUAL_APPLIED'}]})
        self.assertEqual(result['automatic_records_replaced'], 2)
        self.assertEqual(result['reported_current_status_counts']['ready'], 1)
        self.assertEqual(result['reported_current_status_counts']['prepared'], 0)
        self.assertEqual(result['reported_current_status_counts']['applied'], 2)

    def test_malformed_and_conflicting_overlays_do_not_revive_pending(self):
        for manuals in ([{'id': 'm', 'origin_key': 'a', 'status': ['MANUAL_APPLIED']}],
                        [{'id': 'm1', 'origin_key': 'a', 'status': 'MANUAL_APPLIED'},
                         {'id': 'm2', 'origin_key': 'a', 'status': 'PREPARED_NOT_SENT'}],
                        [{'id': 'm', 'origin_key': 'a', 'status': 'MANUAL_APPLIED'},
                         {'id': 'm', 'origin_key': 'a', 'status': 'PREPARED_NOT_SENT'}]):
            with self.subTest(manuals=manuals):
                result = self.snapshot_report({'leads': [{'key': 'a', 'status': 'READY_JEREMIE_SEEK'}], 'manual_entries': manuals})
                self.assertEqual(result['effective_active_records'], 0)
                self.assertGreater(result['overlay_conflicting_records_excluded'], 0)
        result = self.snapshot_report({'leads': [{'key': 'a', 'status': 'READY_JEREMIE_SEEK'}],
            'manual_entries': [{'id': 'm', 'company': '', 'role': '', 'status': 'MANUAL_APPLIED'}]})
        self.assertEqual(result['automatic_records_replaced'], 0)
        self.assertEqual(result['malformed_manual_records_excluded'], 1)
        self.assertEqual(result['reported_current_status_counts']['applied'], 0)
        self.assertEqual(result['reported_current_status_counts']['ready'], 1)

    def test_distinct_manual_vacancies_with_same_names_remain_active(self):
        result = self.snapshot_report({'manual_entries': [
            {'id': 'm1', 'company': 'Acme', 'role': 'Civil Engineer',
             'job_url': 'https://example.com/vacancies/1', 'status': 'MANUAL_APPLIED'},
            {'id': 'm2', 'company': 'Acme', 'role': 'Civil Engineer',
             'job_url': 'https://example.com/vacancies/2', 'status': 'MANUAL_APPLIED'}]})
        self.assertEqual(result['effective_active_records'], 2)
        self.assertEqual(result['reported_current_status_counts']['applied'], 2)
        self.assertEqual(result['overlay_conflict_groups'], 0)
        self.assertEqual(result['overlay_conflicting_records_excluded'], 0)

    def test_distinct_manual_vacancies_replace_only_their_own_originals(self):
        originals = [{'key': 'a', 'company': 'Acme', 'role': 'Civil Engineer',
                      'job_url': 'https://example.com/vacancies/1', 'status': 'READY_JEREMIE_SEEK'},
                     {'key': 'b', 'company': 'Acme', 'role': 'Civil Engineer',
                      'job_url': 'https://example.com/vacancies/2', 'status': 'PREPARED_NOT_SENT'}]
        for with_origin in (True, False):
            with self.subTest(with_origin=with_origin):
                manuals = [dict(row, id='m' + row['key'], key='manual:m' + row['key'],
                                status='MANUAL_APPLIED') for row in originals]
                if with_origin:
                    for manual, original in zip(manuals, originals):
                        manual['origin_key'] = original['key']
                result = self.snapshot_report({'leads': originals, 'manual_entries': manuals})
                self.assertEqual(result['effective_active_records'], 2)
                self.assertEqual(result['automatic_records_replaced'], 2)
                self.assertEqual(result['reported_current_status_counts']['applied'], 2)
                self.assertEqual(result['reported_current_status_counts']['ready'], 0)
                self.assertEqual(result['reported_current_status_counts']['prepared'], 0)
                self.assertEqual(result['overlay_conflicting_records_excluded'], 0)

    def test_explicit_origin_never_broadens_to_matching_names_or_urls(self):
        rows = {'a': {'company': 'Acme', 'role': 'Civil', 'job_url': 'https://example.com/1'},
                'b': {'company': 'Acme', 'role': 'Civil', 'job_url': 'https://example.com/2'}}
        self.assertEqual(health._overlay_targets(dict(rows['b'], origin_key='a'), rows), {'a'})
        self.assertEqual(health._overlay_targets(dict(rows['b'], origin_key='missing'), rows), set())
        self.assertEqual(health._overlay_targets(dict(rows['a'], job_url='https://example.com/3'), rows), set())

    def test_query_vacancy_ids_and_scoped_ids_do_not_collide(self):
        rows = {'a': {'company': 'Acme', 'role': 'Civil', 'job_url': 'https://example.com/jobs?vid=1'},
                'b': {'company': 'Acme', 'role': 'Civil', 'job_url': 'https://example.com/jobs?vid=2'}}
        self.assertEqual(health._overlay_targets(dict(rows['a'], job_url='https://example.com/jobs?utm_source=test&vid=1'), rows), {'a'})
        self.assertEqual(health._overlay_targets(dict(rows['b']), rows), {'b'})
        different = {'job_id': '1', 'company': 'Other', 'role': 'Civil', 'job_url': 'https://other.example/jobs/1'}
        self.assertEqual(health._overlay_targets(different, {'a': dict(rows['a'], job_id='1')}), set())

    def test_seek_id_cannot_cross_match_a_different_id(self):
        rows = {'a': {'company': 'Acme', 'role': 'Civil', 'seek_id': '1'},
                'b': {'company': 'Acme', 'role': 'Civil', 'seek_id': '2'}}
        self.assertEqual(health._overlay_targets(dict(rows['a']), rows), {'a'})

    def test_application_precedence_and_inactive_scope(self):
        result = self.snapshot_report({'applications': [{'key': 'a', 'status': 'SENT'}],
            'leads': [{'key': 'a', 'status': 'READY_JEREMIE_SEEK'},
                      {'key': 'b', 'status': 'EXPIRED'}, {'key': 'c', 'status': 'PREPARED_NOT_SENT'}],
            'record_visibility': [{'record_key': 'c', 'deleted': 1}]})
        self.assertEqual(result['scope'], 'ACTIVE_EFFECTIVE_ROWS')
        self.assertEqual(result['effective_active_records'], 1)
        self.assertEqual(result['reported_current_status_counts']['sent'], 1)
        self.assertEqual(result['overlapping_collection_copies_suppressed'], 1)
        self.assertEqual(result['conflicting_record_ids_excluded'], 0)
        self.assertEqual(result['inactive_records_excluded'], 2)

    def test_real_reply_schema_is_receipt_not_human_response(self):
        ack = {'gmail_message_id': 'abc123', 'gmail_thread_id': 'thread123',
               'received_at': '2026-11-08T10:00:00Z', 'type': 'APPLICATION_ACKNOWLEDGEMENT',
               'action_required': False, 'from': 'private@example.com', 'summary': 'private text'}
        result = self.snapshot_report({'applications': [
            {'key': 'a', 'status': 'APPLICATION_UNDER_REVIEW', 'replies': [ack]},
            {'key': 'b', 'status': 'APPLICATION_UNDER_REVIEW'},
            {'key': 'c', 'status': 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED'},
            {'key': 'd', 'status': 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED', 'replies': [dict(ack, received_at='bad')]},
            {'key': 'e', 'status': 'APPLICATION_UNDER_REVIEW', 'replies': [dict(ack, gmail_message_id='')]}]})
        self.assertEqual(result['reported_current_status_counts']['under_review'], 3)
        self.assertEqual(result['reported_current_status_counts']['applied'], 2)
        self.assertEqual(result['evidence_backed_current_status_counts'],
                         {'applied': 1, 'sent': 0, 'response': 0, 'interview': 0})
        self.assertNotIn('private', json.dumps(result))

    def test_missing_inputs_and_bad_snapshot_are_explicit(self):
        self.assertEqual(self.report()['journal']['issues'][0]['code'], 'JOURNAL_UNREADABLE')
        bad = self.root / 'bad.json'
        bad.write_text('{}')
        self.assertEqual(self.report(snapshot=bad)['tracker']['code'], 'SNAPSHOT_UNREADABLE_OR_INVALID')
        self.journal.write_text('<<<<<<< HEAD\n{}\n')
        self.assertIn('UNCLOSED_CONFLICT', [i['code'] for i in self.report()['journal']['issues']])


if __name__ == '__main__':
    unittest.main()
