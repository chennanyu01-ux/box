import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fixtures import quote, config, NOW, DAY
import db
from collector import collect_batch, hot_names, refresh_universe, collect_market
from features import platform_features
from domain import asof_rows
from engine import score_all
from backtest import walk_forward
from steamdt import SteamDTError


class FakeClient:
    def __init__(self):
        self.calls = []

    def price_batch(self, names):
        self.calls.append(names)
        return []

    def base_info(self):
        self.calls.append('base')
        return [{'marketHashName': 'Sticker | A', 'name': '官方中文名'}]

    def broad_index(self):
        return {'broadMarketIndex': 110, 'updateTime': NOW,
                'historyMarketIndexList': [[NOW-DAY, 100], [NOW-3600, 109]]}


class StorageAndCollector(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(':memory:')

    def tearDown(self):
        self.conn.close()

    def test_future_snapshot_and_future_name_do_not_enter_past_view(self):
        db.upsert_items(self.conn, [{'marketHashName': 'x', 'name': '旧名称'}], NOW-DAY)
        db.upsert_items(self.conn, [{'marketHashName': 'x', 'name': '未来名称'}], NOW+DAY)
        for at in (NOW-1, NOW+1):
            db.insert_batch(self.conn, [{'marketHashName': 'x', 'dataList': [
                {'platform':'BUFF', 'sellPrice':10, 'biddingPrice':9, 'sellCount':30,
                 'biddingCount':20, 'updateTime':at}]}], at)
        self.assertEqual(db.item_meta(self.conn,'x',NOW)['display'], '旧名称')
        self.assertEqual(len(db.series(self.conn,'x',as_of=NOW)), 1)
        result = score_all(self.conn,config(),NOW)
        self.assertEqual(result[0]['name_cn'], '旧名称')

    def test_refresh_preserves_disable_and_old_snapshots(self):
        db.upsert_items(self.conn,[{'marketHashName':'x','name':'原名'}],NOW-DAY)
        self.conn.execute('UPDATE items SET enabled=0 WHERE name=?',('x',))
        db.upsert_items(self.conn,[{'marketHashName':'x','name':'新名'}],NOW)
        self.assertNotIn('x',db.enabled_items(self.conn))

    def test_left_anchor_survives_irregular_seven_day_window(self):
        for at in (NOW-7*DAY-3600,NOW):
            db.insert_batch(self.conn,[{'marketHashName':'x','dataList':[{
                'platform':'BUFF','sellPrice':10,'sellCount':100,'biddingPrice':9,
                'biddingCount':10,'updateTime':at}]}],at)
        rows = asof_rows(db.series(self.conn,'x',168,NOW), NOW, 'BUFF')
        self.assertEqual(len(rows),2)
        self.assertTrue(platform_features(rows,NOW,config())['has_7d_baseline'])

    def test_small_universe_batch_does_not_duplicate_names(self):
        db.upsert_items(self.conn,[{'marketHashName':x} for x in ('a','b','c')],NOW)
        fake = FakeClient()
        with patch('collector.time.time',return_value=NOW):
            result = collect_batch(fake,self.conn,config())
            again = collect_batch(fake,self.conn,config())
        self.assertEqual(fake.calls,[['a','b','c']])
        self.assertEqual(result['items'],3)
        self.assertEqual(again['status'],'RATE_LIMIT_WAIT')

    def test_hot_queue_leaves_room_for_new_discoveries(self):
        names = [f'Sticker | {i}' for i in range(30)]
        db.upsert_items(self.conn,[{'marketHashName':n} for n in names],NOW)
        cfg = config(watch_names=names[:20],hot_limit=9)
        ranked = [{'marketHashName':n,'entry_score':80,'buff_data_available':True,
                   'data_quality':{'fresh':True}} for n in names[20:]]
        selected = hot_names(self.conn,cfg,ranked)
        self.assertEqual(len(selected),9)
        self.assertEqual(len(set(selected)&set(names[20:])),6)

    def test_market_history_is_not_backdated_to_availability(self):
        with patch('collector.time.time',return_value=NOW):
            collect_market(FakeClient(), self.conn)
        self.assertEqual(len(db.market_series(self.conn,NOW)),3)
        self.assertEqual(db.market_series(self.conn,NOW-1),[])

    def test_legacy_migration_is_additive_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'legacy.db'
            conn = sqlite3.connect(path)
            conn.execute('CREATE TABLE items(name TEXT PRIMARY KEY,display TEXT,enabled INTEGER DEFAULT 1)')
            conn.execute('INSERT INTO items VALUES(?,?,?)',('x','已有名字',0))
            conn.commit()
            conn.close()
            for _ in range(2):
                migrated = db.connect(path)
                row = migrated.execute('SELECT * FROM items').fetchone()
                self.assertEqual(row['display'],'已有名字')
                self.assertEqual(row['enabled'],0)
                self.assertIn('buff_item_id',row.keys())
                migrated.close()

    def test_failed_catalog_request_is_not_claimed_as_successful_cache(self):
        fake = FakeClient()
        with patch.object(fake,'base_info',side_effect=SteamDTError('network')):
            with self.assertRaises(SteamDTError):
                refresh_universe(fake,self.conn,config())
        self.assertEqual(db.get_state(self.conn,'universe_refreshed_at'),'0')


class OfflineAndReplay(unittest.TestCase):
    def test_score_cli_needs_no_api_key(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ)
            env.pop('STEAMDT_API_KEY',None)
            output = subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).resolve().parents[1]/'src/radar.py'),
                                     '--db',str(Path(folder)/'radar.db'),'score'],env=env,
                                    capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(output.returncode,0,output.stderr)
            self.assertEqual(json.loads(output.stdout)['decision'],'今天没有值得买的')

    def test_walk_forward_keeps_losers_and_purges_unmatured_training_labels(self):
        conn = db.connect(':memory:')
        names = [f'Sticker | synthetic-{i}' for i in range(6)]
        db.upsert_items(conn,[{'marketHashName':n} for n in names],NOW-DAY)
        for step in range(361):
            at = NOW+step*21600
            batch = [{'marketHashName':name,'dataList':[{'platform':'BUFF',
                      'sellPrice':10,'biddingPrice':9,'sellCount':200,'biddingCount':100,'updateTime':at}]}
                     for name in names]
            db.insert_batch(conn,batch,at)
            db.insert_market(conn,100,at,at)
        cfg = config(walk_forward_train_days=35,walk_forward_test_days=21)
        report = walk_forward(conn,NOW,NOW+80*DAY,NOW+90*DAY,cfg)
        self.assertGreater(report['negative_outcomes'],0)
        self.assertGreater(report['unfiltered_cohort']['horizons']['7']['coverage'],0)
        self.assertGreater(len(report['folds']),1)
        for fold in report['folds']:
            if fold['training_label_max_at']:
                self.assertLess(fold['training_label_max_at'],fold['fit_at'])
        self.assertEqual(report['out_of_sample']['observations'],0)
        self.assertEqual(report['status'],'NO_VALIDATED_SIGNALS')
        conn.close()
