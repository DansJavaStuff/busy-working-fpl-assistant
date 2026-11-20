from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from snapshot_advice import frozen_advice
from snapshot_evaluation import OfficialOutcomes, assess_snapshot, evaluate_payload, snapshot_report

NOW = datetime(2026,11,20,tzinfo=timezone.utc)
DEADLINE = '2026-10-10T10:00:00Z'
CAPTURE = '2026-10-10T09:55:00Z'


def payload():
    picks = [{'element':i, 'position':i, 'is_captain':i==1,
              'is_vice_captain':i==2} for i in range(1,16)]
    players = [{'id':i, 'web_name':'Haaland' if i==2 else f'Player {i}',
                'ep_next':str(i), 'points_per_game':'2', 'minutes':90}
               for i in range(1,16)]
    return {'captured_at':CAPTURE, 'deadline':DEADLINE,
            'bootstrap':{'events':[{'id':1,'deadline_time':'2026-08-15T10:00:00Z'},
                                   {'id':6,'deadline_time':DEADLINE,'is_next':True}],
                         'elements':players,'teams':[{'id':1}]},
            'fixtures':[{'id':1,'event':6}], 'current_team':{'picks':picks},
            'entry':{'id':123456789, 'private':'PRIVATE'}}


def row(data=None):
    return {'id':1, 'snapshot_type':'pre_deadline_t5m', 'captured_at':CAPTURE,
            'gameweek':6, 'season_key':'2026-27',
            'payload_json':json.dumps(data if data is not None else payload())}


def live():
    return {'elements':[{'id':i,'stats':{'total_points':i-1,'minutes':90}}
                        for i in range(1,16)]}


class EvaluationTests(unittest.TestCase):
    def test_valid_capture_uses_recomputed_time_and_explicit_event(self):
        data=payload()
        data.update(on_time=False, seconds_remaining=-999)
        result,_=assess_snapshot(row(data),NOW)
        self.assertTrue(result['eligible'])
        self.assertEqual(result['timing'],'on_time')
        self.assertEqual(result['seconds_remaining'],300)

    def test_after_deadline_wrong_event_season_and_malformed_are_excluded(self):
        for mutate in (
            lambda p:p.update(deadline='2026-10-10T09:54:00Z'),
            lambda p:p['bootstrap']['events'][-1].update(is_next=False),
            lambda p:p['bootstrap']['events'][0].update(deadline_time='2025-08-15T10:00:00Z'),
            lambda p:p['current_team']['picks'].pop(),
            lambda p:p.update(captured_at='2026-10-10T09:54:00Z'),
        ):
            data=payload();mutate(data)
            self.assertFalse(assess_snapshot(row(data),NOW)[0]['eligible'])
        bad=row();bad['payload_json']='PRIVATE'
        result,_=assess_snapshot(bad,NOW)
        self.assertIn('malformed_payload_or_timestamp',result['issues'])
        self.assertNotIn('PRIVATE',str(result))

    def test_outside_window_and_future_capture(self):
        record=row();record['snapshot_type']='pre_deadline_t15m'
        result,_=assess_snapshot(record,NOW)
        self.assertEqual(result['timing'],'outside_window')
        self.assertTrue(result['eligible'])
        self.assertFalse(assess_snapshot(row(),datetime(2026,10,1,tzinfo=timezone.utc))[0]['eligible'])

    def test_metrics_pair_same_ids_without_filling_missing_outcomes(self):
        data=payload();results=live();results['elements'].pop()
        data['bootstrap']['elements'][0]['ep_next']='NaN'
        evaluation=evaluate_payload(data,results)
        owned=evaluation['cohorts']['owned_players']
        self.assertEqual(owned['matched_players'],13)
        self.assertEqual(owned['unmatched_players'],2)
        self.assertEqual(owned['captured_ep_next']['mae'],1)
        self.assertEqual(owned['captured_ep_next']['bias'],1)
        self.assertEqual(owned['captured_ppg_baseline']['n'],13)
        self.assertIsNone(evaluation['captain_player_comparison']['highest_captured_ep_next_in_snapshot_xi'])
        self.assertEqual(evaluation['saved_app_advice']['status'],'not_recorded')

    def test_captain_comparison_cannot_choose_bench_or_look_at_results(self):
        data=payload();results=live()
        results['elements'][1]['stats']['total_points']=100
        results['elements'][0]['stats']['minutes']=0
        result=evaluate_payload(data,results)['captain_player_comparison']
        self.assertEqual(result['highest_captured_ep_next_in_snapshot_xi']['player_id'],11)
        self.assertEqual(result['recorded_snapshot_captain']['actual_player_points'],0)
        self.assertEqual(result['haaland_if_in_snapshot_xi']['actual_player_points'],100)

    def test_zero_errors_and_no_matched_values_are_distinct(self):
        results=live()
        for p in results['elements']:p['stats']['total_points']=p['id']
        self.assertEqual(evaluate_payload(payload(),results)['cohorts']['all_players']['captured_ep_next']['mae'],0)
        self.assertIsNone(evaluate_payload(payload(),{'elements':[]})['cohorts']['all_players']['captured_ep_next'])


class DatabaseReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'history.db'
        with sqlite3.connect(self.db) as conn:
            conn.executescript((Path(__file__).resolve().parents[1]/'db/migrations/001_initial.sql').read_text())
            conn.execute("INSERT INTO seasons(id,season_key) VALUES(1,'2026-27')")
            for gw in (6,7,8,9):
                conn.execute('INSERT INTO gameweeks(id,season_id,gameweek,deadline_time) VALUES(?,1,?,?)',(gw,gw,DEADLINE))

    def save(self, gw=6, label='t5m', captured=CAPTURE, entry=123456789, data=None):
        data=deepcopy(data if data is not None else payload())
        data['captured_at']=captured
        data['bootstrap']['events'][-1]['id']=gw
        with sqlite3.connect(self.db) as conn:
            conn.execute('''INSERT INTO snapshots(season_id,gameweek_id,entry_id,snapshot_type,captured_at,source,payload_json)
                VALUES(1,?,?,?,?, 'official_fpl_live',?)''',
                (gw,entry,'pre_deadline_'+label,captured,json.dumps(data)))

    def test_readonly_no_api_latest_complete_selection_and_missing_week(self):
        self.save(label='baseline',captured='2026-09-24T21:31:39Z')
        self.save()
        bad=payload();bad['current_team']['picks'].pop()
        self.save(captured='2026-10-10T09:56:00Z',data=bad)
        self.save(gw=8)
        before=self.db.read_bytes()
        with patch('snapshot_evaluation.urlopen',side_effect=AssertionError('No API')):
            report=snapshot_report(self.db,now=NOW)
        self.assertEqual(before,self.db.read_bytes())
        self.assertEqual(report['weeks'][0]['selected_snapshot_id'],2)
        self.assertEqual(report['weeks'][1]['stored_snapshots'],0)
        self.assertEqual(report['summary']['gameweeks_with_eligible_snapshots'],2)
        self.assertNotIn('123456789',json.dumps(report))
        self.assertNotIn('PRIVATE',json.dumps(report))
        self.assertEqual(report['weeks'][0]['snapshots'][-1]['app_advice_status'],'not_recorded')

    def test_five_checkpoints_select_one_record_and_explicit_checkpoint(self):
        for label,captured in [('baseline','2026-10-10T08:00:00Z'),('t60m','2026-10-10T09:00:00Z'),
                               ('t15m','2026-10-10T09:45:00Z'),('t10m','2026-10-10T09:50:00Z'),('t5m',CAPTURE)]:
            self.save(label=label,captured=captured)
        calls=[]
        def loader(season,gw):
            calls.append((season,gw))
            return {'status':'ready','live':live(),'source':'official','retrieved_at':'today'}
        report=snapshot_report(self.db,now=NOW,outcome_loader=loader)
        self.assertEqual(calls,[('2026-27',6)])
        self.assertEqual(report['summary']['distinct_gameweeks_evaluated'],1)
        self.assertEqual(report['weeks'][0]['selected_snapshot_id'],5)
        specific=snapshot_report(self.db,now=NOW,checkpoint='t60m')
        self.assertEqual(specific['weeks'][0]['selected_snapshot_id'],2)

    def test_entry_separation_and_season_filter(self):
        self.save();self.save(entry=222)
        report=snapshot_report(self.db,now=NOW)
        self.assertEqual(len(report['weeks']),2)
        self.assertEqual({w['entry_group'] for w in report['weeks']},{1,2})
        self.assertEqual(snapshot_report(self.db,season='2025-26')['weeks'],[])

    def test_future_checkpoints_pending_and_invalid_outcome_handled(self):
        self.save(label='baseline',captured='2026-10-09T09:00:00Z')
        report=snapshot_report(self.db,now=datetime(2026,10,9,12,tzinfo=timezone.utc))
        self.assertEqual(report['weeks'][0]['checkpoint_status']['t5m'],'pending')
        bad=lambda *args:{'status':'ready','live':{'elements':[{},{}]}}
        self.assertEqual(snapshot_report(self.db,now=NOW,outcome_loader=bad)['weeks'][0]['outcome_status'],'invalid_outcome_data')

    def test_missing_database_is_not_created(self):
        missing=self.db.parent/'does-not-exist.db'
        with self.assertRaises(sqlite3.OperationalError):snapshot_report(missing)
        self.assertFalse(missing.exists())


class PublicOutcomeTests(unittest.TestCase):
    def test_only_checked_matching_season_fetches_and_cached_once(self):
        bootstrap=payload()['bootstrap']
        bootstrap['events'][-1].update(finished=True,data_checked=True)
        calls=[]
        def fetch(path):
            calls.append(path)
            return bootstrap if path=='bootstrap-static/' else live()
        loader=OfficialOutcomes(fetch)
        self.assertEqual(loader('2025-26',6)['status'],'different_season')
        self.assertEqual(loader('2026-27',1)['status'],'pending_or_unchecked_results')
        self.assertEqual(loader('2026-27',6)['status'],'ready')
        loader('2026-27',6)
        self.assertEqual(calls,['bootstrap-static/','event/6/live/'])

    def test_finished_without_checked_flag_and_failed_fetch_stay_unscored(self):
        bootstrap=payload()['bootstrap']
        bootstrap['events'][-1].update(finished=True)
        def fetch(path):
            if path=='bootstrap-static/':return bootstrap
            raise OSError('PRIVATE')
        loader=OfficialOutcomes(fetch)
        self.assertEqual(loader('2026-27',6)['status'],'pending_or_unchecked_results')
        loader.events[6]['data_checked']=True
        result=loader('2026-27',6)
        self.assertEqual(result,{'status':'outcome_fetch_failed'})


class FrozenAdviceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'weekly_report.json'
        self.report={'gameweek':6,'generated_at':'2026-10-10T09:50:00Z','schema_version':5,
                     'current_starters':[{'id':i,'name':str(i),'proj_gw6':i} for i in range(1,12)],
                     'current_bench':[{'id':i,'name':str(i),'proj_gw6':i} for i in range(12,16)],
                     'captain':{'id':11},'vice':{'id':10},'approval':{'PRIVATE':'SECRET'}}
        self.report['recommended']={'squad':self.report['current_starters']+self.report['current_bench'],
                                    'transfers':0,'hit_cost':0}
        self.report['hold_lineup']={'captain':{'id':11}}

    def freeze(self):
        self.path.write_text(json.dumps(self.report))
        return frozen_advice(6,CAPTURE,payload()['current_team'],self.path)

    def test_copy_saved_advice_without_private_fields_or_writes_and_evaluate(self):
        advice=self.freeze()
        self.assertEqual(advice['status'],'saved')
        self.assertEqual(advice['age_at_capture_seconds'],300)
        self.assertIsNone(advice['model_version'])
        self.assertNotIn('SECRET',json.dumps(advice))
        before=self.path.read_bytes();self.freeze();self.assertEqual(before,self.path.read_bytes())
        data=payload();data['app_advice']=advice
        result=evaluate_payload(data,live())['saved_app_advice']
        self.assertEqual(result['owned_projection_error']['mae'],1)
        self.assertEqual(result['recommended_captain']['actual_player_points'],10)
        self.assertEqual(result['status'],'evaluated_saved_advice')
        data['app_advice']['generated_at']='2026-10-10T10:01:00Z'
        self.assertEqual(evaluate_payload(data,live())['saved_app_advice']['status'],'invalid_saved_advice')

    def test_missing_different_gameweek_squad_future_report_and_nan(self):
        self.assertEqual(frozen_advice(6,CAPTURE,payload()['current_team'],self.path)['status'],'no_saved_report')
        for field,value,status in [('gameweek',5,'different_gameweek'),
                                   ('generated_at','2026-10-10T10:01:00Z','invalid_report_time')]:
            old=self.report[field];self.report[field]=value
            self.assertEqual(self.freeze()['status'],status);self.report[field]=old
        self.report['current_bench'].pop()
        self.assertEqual(self.freeze()['status'],'different_owned_squad')
        self.report['current_bench'].append({'id':15,'name':'15','proj_gw6':float('nan')})
        self.assertEqual(self.freeze()['status'],'invalid_projection')

class CollectorAdviceIntegrationTests(unittest.TestCase):
    def test_collector_attaches_saved_advice_without_extra_api_or_solver_calls(self):
        from tests.test_snapshot_health import CollectorCaptureTimingTests, NOW as CAPTURE_NOW
        helper=CollectorCaptureTimingTests()
        with patch('snapshot_collector.frozen_advice', return_value={'status':'saved','marker':123}) as freeze:
            result, save=helper.collect(CAPTURE_NOW)
        self.assertEqual(result['status'],'saved')
        self.assertEqual(save.call_args.args[3]['app_advice'],{'status':'saved','marker':123})
        freeze.assert_called_once()
