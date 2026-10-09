from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch

from flask import Flask, render_template_string

from report_review import report_freshness, transfer_scenario_summary, weekly_report_review

NOW = datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc)


def player(i):
    return {'id': i, 'name': f'Player {i}', 'position': 'GKP' if i in (1, 12) else 'MID',
            'position_id': 1 if i in (1, 12) else 3, 'starter': i <= 11,
            'captain': i == 2, 'planning_gameweek': 6, 'proj_gw6': 5, 'price': 5, 'team': 'Club',
            'private_field': 'PRIVATE'}


def result(transfers, raw, hit):
    squad = [player(i) for i in range(1, 16)]
    return {'transfers': transfers, 'raw_score': raw, 'net_score': raw-hit,
            'hit_cost': hit, 'bank_after': 10, 'squad': squad,
            'vice_captain': squad[2], 'incoming': [], 'outgoing': []}


class ReportReviewTests(unittest.TestCase):
    def test_paid_transfer_gain_deducts_hit_once(self):
        summary = transfer_scenario_summary(result(2, 110, 4), result(0, 100, 0))
        self.assertEqual(summary['gross_gain'], 10)
        self.assertEqual(summary['gain'], 6)
        self.assertEqual(summary['score'], 106)

    def test_actual_table_renders_gross_and_net_columns(self):
        text = (Path(__file__).resolve().parents[1] / 'templates/index.html').read_text()
        start = text.index('    {% for scenario in report.scenarios %}')
        end = text.index('    {% endfor %}', start) + len('    {% endfor %}')
        app = Flask(__name__)
        scenario = transfer_scenario_summary(result(2, 110, 4), result(0, 100, 0))
        with app.app_context():
            html = render_template_string(text[start:end], report={
                'scenarios': [scenario], 'recommended': {'transfers': 2}})
        self.assertIn('+10.00', html)
        self.assertIn('+6.00', html)
        self.assertNotIn('+2.00', html)

    def test_old_report_table_uses_net_gain_compatibly(self):
        text = (Path(__file__).resolve().parents[1] / 'templates/index.html').read_text()
        start = text.index('    {% for scenario in report.scenarios %}')
        end = text.index('    {% endfor %}', start) + len('    {% endfor %}')
        app = Flask(__name__)
        scenario = transfer_scenario_summary(result(2, 110, 4), result(0, 100, 0))
        del scenario['gross_gain']
        with app.app_context():
            html = render_template_string(text[start:end], report={
                'scenarios': [scenario], 'recommended': {'transfers': 2}})
        self.assertIn('+10.00', html)
        self.assertIn('+6.00', html)

    def test_freshness_and_deadline_are_recomputed(self):
        report = {'generated_at': NOW.isoformat(), 'deadline_iso': (NOW + timedelta(days=6)).isoformat()}
        self.assertEqual(report_freshness(report, NOW)['status'], 'recent')
        self.assertEqual(report_freshness(report, NOW + timedelta(minutes=31))['status'], 'refresh_needed')
        report['generated_at'] = (NOW + timedelta(seconds=1)).isoformat()
        self.assertEqual(report_freshness(report, NOW)['status'], 'clock_ahead')
        report['deadline_iso'] = NOW.isoformat()
        self.assertTrue(report_freshness(report, NOW)['deadline_locked'])

    def test_unknown_or_naive_timestamps_are_not_recent(self):
        for stamp in (None, 'broken', '2026-10-04T18:00:00'):
            with self.subTest(stamp=stamp):
                state = report_freshness({'generated_at': stamp}, NOW)
                self.assertEqual(state['status'], 'unknown')
                self.assertTrue(state['deadline_locked'])


class ChipRefreshTests(unittest.TestCase):
    def test_explicit_chip_refresh_fails_before_analysis_if_live_data_unavailable(self):
        from chip_planner import build_chip_planner, build_chip_opportunity
        for build in (build_chip_planner, build_chip_opportunity):
            for failed_source in ('get_bootstrap', 'get_fixtures'):
                with self.subTest(build=build.__name__, failed_source=failed_source), \
                        patch('chip_planner.get_bootstrap') as bootstrap, \
                        patch('chip_planner.get_fixtures') as fixtures, \
                        patch('chip_planner.get_planning_gameweek') as planning:
                    {'get_bootstrap': bootstrap, 'get_fixtures': fixtures}[failed_source].side_effect = RuntimeError('offline')
                    with self.assertRaises(RuntimeError):
                        build(force_refresh=True)
                    bootstrap.assert_called_once_with(force_refresh=True, allow_stale=False)
                    if failed_source == 'get_fixtures':
                        fixtures.assert_called_once_with(force_refresh=True, allow_stale=False)
                    planning.assert_not_called()


class WeeklyReportIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # App import normally migrates its runtime DB; tests must never touch it.
        with patch('history_store.ensure_database'):
            cls.module = importlib.import_module('app')

    def build(self, force_refresh, paid_passes=True):
        squad = [player(i) for i in range(1, 16)]
        team = {'picks': [{'element': p['id'], 'position': i,
                         'is_captain': i == 2, 'is_vice_captain': i == 3}
                        for i, p in enumerate(squad, 1)],
                'transfers': {'limit': 1, 'made': 0, 'bank': 10}}
        deadline = NOW + timedelta(days=6)
        with patch.multiple(self.module,
                            get_planning_gameweek=lambda: 6,
                            get_gameweek_deadline=lambda gw: {'deadline': deadline, 'deadline_iso': deadline.isoformat(), 'locked': False},
                            get_my_team=lambda: team,
                            load_players=lambda: squad,
                            load_approval=lambda: None), \
                patch.object(self.module, 'get_bootstrap') as bootstrap, \
                patch.object(self.module, 'get_fixtures') as fixtures, \
                patch.object(self.module, 'cautious_paid_plan_check', return_value={
                    'passed': paid_passes, 'cautious_net_gain': 4 if paid_passes else 1,
                    'required_gain': 3, 'transfers': 2, 'hit_cost': 4}) as check, \
                patch.object(self.module, 'optimise_transfers', side_effect=[
                    result(0, 100, 0), result(1, 102, 0), result(2, 110, 4), None]):
            report = self.module.build_weekly_report(force_refresh=force_refresh)
        check.assert_called_once()
        return report, bootstrap, fixtures

    def test_paid_plan_falls_back_and_keeps_hold_lineup_when_check_fails(self):
        report, _, _ = self.build(False, paid_passes=False)
        self.assertEqual(report['recommended']['transfers'], 1)
        self.assertFalse(report['paid_plan_check']['passed'])
        self.assertEqual(len(report['hold_lineup']['starters']), 11)
        self.assertEqual(len(report['hold_lineup']['bench']), 4)
        self.assertEqual({p['id'] for p in report['hold_lineup']['starters'] + report['hold_lineup']['bench']}, set(range(1,16)))

    def test_live_refresh_and_report_metadata(self):
        report, bootstrap, fixtures = self.build(True)
        bootstrap.assert_called_once_with(force_refresh=True, allow_stale=False)
        fixtures.assert_called_once_with(force_refresh=True, allow_stale=False)
        self.assertEqual(report['recommended']['transfers'], 2)
        self.assertEqual(report['transfer_gain'], 6)
        self.assertEqual(report['scenarios'][2]['gross_gain'], 10)
        self.assertEqual(report_freshness(report)['status'], 'recent')
        review = weekly_report_review(report)
        self.assertEqual(review['captain']['name'], 'Player 2')
        self.assertNotIn('PRIVATE', str(review))
        self.assertNotIn('source_squad_ids', review)

    def test_normal_rebuild_does_not_force_network_refresh(self):
        _, bootstrap, fixtures = self.build(False)
        bootstrap.assert_not_called()
        fixtures.assert_not_called()

    def test_index_recomputes_lock_on_saved_report_and_shows_freshness(self):
        report, _, _ = self.build(False)
        report['deadline_iso'] = '2000-01-01T11:00:00Z'
        report['deadline_locked'] = False
        with self.module.app.test_client() as client, \
                patch.object(self.module, 'is_configured', return_value=True), \
                patch.object(self.module, 'load_weekly_report', return_value=report), \
                patch.object(self.module, 'load_approval', return_value=None), \
                patch.object(self.module, 'build_snapshot_status', return_value={
                    'state': None, 'checkpoints': [], 'analysis': {'comparisons': [], 'summary': {}}}):
            response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(report['deadline_locked'])
        self.assertIn('LOCKED', response.get_data(as_text=True))
        self.assertIn('Analysis freshness', response.get_data(as_text=True))

    def test_failed_refresh_preserves_saved_report_and_approval(self):
        with self.module.app.test_client() as client, \
                patch.object(self.module, 'is_configured', return_value=True), \
                patch.object(self.module, 'load_weekly_report', return_value={'constraints': {}}), \
                patch.object(self.module, 'build_weekly_report', side_effect=RuntimeError('PRIVATE')), \
                patch.object(self.module, 'clear_approval') as clear, \
                patch.object(self.module, 'save_weekly_report') as save, \
                patch.object(self.module.app.logger, 'exception'):
            response = client.post('/refresh')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('PRIVATE', response.get_data(as_text=True))
        clear.assert_not_called()
        save.assert_not_called()

    def test_failed_public_refresh_does_not_build_with_stale_data(self):
        with patch.object(self.module, 'get_bootstrap', side_effect=RuntimeError('offline')), \
                patch.object(self.module, 'load_players') as load:
            with self.assertRaises(RuntimeError):
                self.module.build_weekly_report(force_refresh=True)
        load.assert_not_called()
