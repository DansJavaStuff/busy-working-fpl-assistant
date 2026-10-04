import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from snapshot_collector import collect_if_due
from tools.snapshot_health import snapshot_health

NOW = datetime(2026, 10, 10, 10, 56, tzinfo=timezone.utc)
DEADLINE = '2026-10-10T11:00:00Z'
BOOTSTRAP = {'events': [{'id': 1, 'deadline_time': DEADLINE}], 'elements': [{'id': 1}]}


class CollectorCaptureTimingTests(unittest.TestCase):
    def collect(self, captured_at, fresh_deadline=DEADLINE):
        names = ['get_planning_gameweek', 'get_gameweek_deadline', 'get_entry_id',
                 'get_bootstrap', 'get_fixtures', 'get_my_team', 'get_entry',
                 'upsert_season', 'upsert_gameweek', 'snapshot_exists', 'save_snapshot']
        mocks = {name: MagicMock() for name in names}
        mocks['get_planning_gameweek'].return_value = 1
        mocks['get_gameweek_deadline'].return_value = {
            'locked': False, 'seconds_remaining': 290, 'deadline_iso': DEADLINE,
        }
        mocks['get_bootstrap'].side_effect = [BOOTSTRAP, {
            **BOOTSTRAP, 'events': [{'id': 1, 'deadline_time': fresh_deadline}],
        }]
        mocks['snapshot_exists'].return_value = False
        with patch.multiple('snapshot_collector', **mocks), patch('snapshot_collector.datetime') as clock:
            clock.now.return_value = captured_at
            clock.fromisoformat.side_effect = datetime.fromisoformat
            result = collect_if_due()
        return result, mocks['save_snapshot']

    def test_slow_fetch_is_late_at_completion(self):
        result, save = self.collect(NOW.replace(minute=59))
        self.assertFalse(result['on_time'])
        self.assertEqual(result['seconds_remaining'], 60)
        self.assertEqual(result['late_by_seconds'], 240)
        self.assertEqual(save.call_args.args[3]['seconds_remaining'], 60)

    def test_completed_before_deadline_is_saved_on_time(self):
        result, save = self.collect(NOW)
        self.assertTrue(result['on_time'])
        self.assertEqual(result['seconds_remaining'], 240)
        save.assert_called_once()

    def test_completion_at_or_after_deadline_is_discarded(self):
        for minute in (0, 1):
            with self.subTest(minute=minute):
                result, save = self.collect(NOW.replace(hour=11, minute=minute))
                self.assertEqual(result['status'], 'deadline_passed_during_collection')
                save.assert_not_called()

    def test_extended_deadline_does_not_label_early_checkpoint_on_time(self):
        result, save = self.collect(NOW, '2026-10-10T12:00:00Z')
        self.assertFalse(result['on_time'])
        self.assertEqual(result['seconds_remaining'], 3840)
        save.assert_called_once()

    def test_fresh_deadline_is_used(self):
        result, save = self.collect(NOW, '2026-10-10T10:55:00Z')
        self.assertEqual(result['status'], 'deadline_passed_during_collection')
        save.assert_not_called()


class SnapshotHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'history.db'
        with sqlite3.connect(self.db) as db:
            root = Path(__file__).resolve().parents[1]
            for migration in ('001_initial.sql', '003_collector_state.sql'):
                db.executescript((root / 'db/migrations' / migration).read_text())
            db.execute("INSERT INTO seasons(id, season_key) VALUES(1, '2026-27')")
            db.execute('INSERT INTO gameweeks(id, season_id, gameweek, deadline_time) VALUES(1,1,1,?)', (DEADLINE,))
            db.execute("INSERT INTO collector_state VALUES('predeadline', ?, 'saved',1,240,'SECRET')", (NOW.isoformat(),))

    def test_pending_missing_and_read_only(self):
        before = self.db.read_bytes()
        report = snapshot_health(self.db, NOW)
        self.assertEqual(report['collector']['health'], 'recent')
        coverage = report['coverage_by_entry'][0]
        self.assertEqual(coverage['t5m']['status'], 'missing')
        early = snapshot_health(self.db, NOW.replace(hour=9))
        self.assertEqual(early['coverage_by_entry'][0]['t60m']['status'], 'pending')
        self.assertEqual(early['collector']['health'], 'clock_ahead')
        self.assertNotIn('SECRET', json.dumps(report))
        self.assertEqual(self.db.read_bytes(), before)

    def test_recomputes_old_inaccurate_metadata_and_checks_payload(self):
        payload = {'on_time': True, 'deadline': DEADLINE, 'seconds_remaining': 290,
                   'entry': {'secret': 'PRIVATE'}}
        with sqlite3.connect(self.db) as db:
            db.execute('INSERT INTO snapshots(season_id,gameweek_id,snapshot_type,captured_at,source,payload_json) VALUES(1,1,?,?,?,?)',
                       ('pre_deadline_t5m', NOW.replace(minute=59).isoformat(), 'official_fpl_live', json.dumps(payload)))
        report = snapshot_health(self.db, NOW)
        snapshot = report['coverage_by_entry'][0]['t5m']['snapshots'][0]
        self.assertEqual(snapshot['timing'], 'outside_window')
        self.assertEqual(snapshot['seconds_remaining'], 60)
        self.assertFalse(snapshot['required_data_present'])
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_complete_payload_and_postdeadline_capture(self):
        payload = {'deadline': DEADLINE, 'bootstrap': BOOTSTRAP,
                   'fixtures': [{'id': 1}], 'current_team': {'picks': [{'element': 1}]},
                   'entry': {'id': 1}}
        with sqlite3.connect(self.db) as db:
            db.execute('INSERT INTO snapshots(season_id,gameweek_id,snapshot_type,captured_at,source,payload_json) VALUES(1,1,?,?,?,?)',
                       ('pre_deadline_t5m', NOW.replace(hour=11, minute=0).isoformat(), 'official_fpl_live', json.dumps(payload)))
        snapshot = snapshot_health(self.db, NOW)['coverage_by_entry'][0]['t5m']['snapshots'][0]
        self.assertEqual(snapshot['timing'], 'after_deadline')
        self.assertTrue(snapshot['required_data_present'])

    def test_stale_heartbeat(self):
        report = snapshot_health(self.db, NOW.replace(hour=12))
        self.assertEqual(report['collector']['health'], 'stale')

    def test_missing_database_is_not_created(self):
        missing = self.db.parent / 'missing.db'
        with self.assertRaises(sqlite3.OperationalError):
            snapshot_health(missing, NOW)
        self.assertFalse(missing.exists())
