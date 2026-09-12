import copy
import json
import math
import unittest
from fixtures import quote, accumulation, config, benchmarks, calibration, NOW, DAY
from domain import asof_rows, timestamp, platform_name
from scoring import score_item
from features import platform_features, accumulation_band
from state_machine import PhaseState
from attribution import classify
from context import market_context, peer_context, residual


class DecisionInvariants(unittest.TestCase):
    def evaluate(self, rows=None, **options):
        cfg = config()
        market, peers = benchmarks()
        return score_item(rows or accumulation(), NOW, cfg=cfg, market=market, peers=peers,
                          calibration=options.pop('calibration', calibration(cfg)), **options)

    def test_full_early_structure_requires_past_calibration(self):
        signal = self.evaluate()
        self.assertEqual(signal['stage'], 'ACCUMULATION')
        self.assertEqual(signal['action'], 'BUY_CANDIDATE', signal['blockers'])
        self.assertGreaterEqual(signal['buy_price_max'], signal['buff_sell_price'])
        self.assertLessEqual(signal['buy_price_max'], signal['accumulation_band']['high']*1.15)
        uncalibrated = self.evaluate(calibration=None)
        self.assertNotEqual(uncalibrated['action'], 'BUY_CANDIDATE')
        self.assertIsNone(uncalibrated['buy_price_max'])

    def test_future_quotes_cannot_change_historical_signal(self):
        before = self.evaluate()
        rows = accumulation()+[quote(NOW+DAY, 1000, 999, 1, 1)]
        self.assertEqual(before, self.evaluate(rows))

    def test_no_cross_platform_prices_leak_into_buff(self):
        rows = accumulation()
        for row in rows:
            if row['platform'] != 'BUFF':
                row['sell_price'] *= 100
                row['bid_price'] *= 100
        first, changed = self.evaluate(), self.evaluate(rows)
        for field in ('buff_sell_price', 'buff_bid_price', 'buy_price_max', 'no_chase_above'):
            self.assertEqual(first[field], changed[field])

    def test_buff_market_is_not_buff163(self):
        rows = accumulation()
        for row in rows:
            if row['platform'] == 'BUFF':
                row['platform'] = 'BUFF.MARKET'
        result = self.evaluate(rows)
        self.assertEqual(result['action'], 'WATCH_NO_BUFF')
        self.assertIsNone(result['buff_sell_price'])
        self.assertIsNone(result.get('buff_price_24h'))

    def test_stale_or_missing_source_time_cannot_buy(self):
        for source in (None, NOW-2*DAY):
            rows = accumulation()
            for row in rows:
                if row['platform'] == 'BUFF':
                    row['source_update_time'] = source
            signal = self.evaluate(rows)
            self.assertNotEqual(signal['action'], 'BUY_CANDIDATE')

    def test_repeated_source_update_is_one_observation(self):
        rows = [quote(NOW-i*60) for i in range(100)]
        for row in rows:
            row['source_update_time'] = NOW-6000
        self.assertEqual(len(asof_rows(rows, NOW)), 1)
        self.assertNotEqual(self.evaluate(rows)['action'], 'BUY_CANDIDATE')

    def test_fresh_current_quote_cannot_validate_untimed_history(self):
        rows = accumulation()
        for row in rows:
            if row['platform'] == 'BUFF' and row['sampled_at'] < NOW:
                row['source_update_time'] = None
        self.assertIn('INSUFFICIENT_HISTORY', self.evaluate(rows)['blockers'])

    def test_invalid_bid_and_ask_never_buy_or_emit_nan(self):
        for invalid in (0, None, -1, float('nan'), float('inf')):
            rows = accumulation()
            for row in rows:
                if row['sampled_at'] == NOW and row['platform'] == 'BUFF':
                    row['sell_price'] = invalid
            result = self.evaluate(rows)
            self.assertNotEqual(result['action'], 'BUY_CANDIDATE')
            json.dumps(result, allow_nan=False)

    def test_crossed_book_cannot_buy(self):
        rows = accumulation()
        rows[-3]['bid_price'] = 100
        result = self.evaluate(rows)
        self.assertIn('INVALID_BUFF_QUOTE', result['blockers'])

    def test_future_and_wrong_version_calibration_rejected(self):
        for field, value in (('fitted_at', NOW+1), ('trained_until', NOW),
                             ('config_hash', 'wrong'), ('model_version', 'wrong')):
            fitted = calibration(config())
            fitted[field] = value
            self.assertIn('NO_VALID_T7_CALIBRATION', self.evaluate(calibration=fitted)['blockers'])

    def test_unverified_social_claims_never_become_high_weight_truth(self):
        f = platform_features(asof_rows(accumulation(), NOW, 'BUFF'), NOW, config())
        claims = [{'id': str(i), 'url': f'https://example.com/{i}', 'published_at': NOW-1,
                   'available_at': NOW, 'kind': 'claim', 'verified': True} for i in range(20)]
        self.assertEqual(classify(claims, NOW, f)['manipulation_training_weight'], 0)

    def test_future_social_evidence_does_not_change_signal(self):
        future = {'id': 'f', 'url': 'https://example.com/f', 'published_at': NOW-1,
                  'available_at': NOW+1, 'kind': 'social_fomo'}
        self.assertEqual(self.evaluate(), self.evaluate(evidence=[future]))

    def test_fomo_can_only_raise_risk_and_reduce_entry(self):
        evidence = [{'id': str(i), 'url': f'https://example.com/{i}', 'published_at': NOW-1,
                     'available_at': NOW, 'kind': 'social_fomo'} for i in range(10)]
        before, after = self.evaluate(), self.evaluate(evidence=evidence)
        self.assertLess(after['entry_score'], before['entry_score'])
        self.assertGreater(after['distribution_risk'], before['distribution_risk'])


class InventoryAndContext(unittest.TestCase):
    def test_relisting_oscillation_loses_to_persistent_squeeze(self):
        clean = asof_rows(accumulation(), NOW, 'BUFF')
        fake = copy.deepcopy(clean)
        values = [200, 80, 195, 75, 190, 70, 180, 65, 60]
        for row, value in zip(fake[-9:], values):
            row['sell_count'] = value
        a = platform_features(clean, NOW, config())
        b = platform_features(fake, NOW, config())
        self.assertTrue(a['sustained_contraction'])
        self.assertFalse(b['sustained_contraction'])
        self.assertLess(b['persistence_score'], a['persistence_score'])

    def test_single_withdrawal_is_not_persistent_accumulation(self):
        rows = [quote(NOW-DAY+i*10800, sell=200 if i<8 else 60) for i in range(9)]
        f = platform_features(rows, NOW, config())
        self.assertEqual(f['persistence_score'], 1)
        self.assertFalse(f['sustained_contraction'])
        self.assertIsNone(accumulation_band(rows, NOW, config()))

    def test_missing_baseline_stays_missing(self):
        f = platform_features([quote(NOW-60), quote(NOW)], NOW, config())
        self.assertIsNone(f['price24'])
        self.assertIsNone(f['price7'])

    def test_late_download_of_market_history_visible_only_after_receipt(self):
        rows = [{'available_at': NOW, 'observed_at': NOW-DAY, 'value': 100},
                {'available_at': NOW, 'observed_at': NOW, 'value': 110}]
        self.assertAlmostEqual(market_context(rows, NOW, config())['return24'], .1)
        self.assertFalse(market_context(rows, NOW-1, config())['available'])
        self.assertAlmostEqual(residual(.1, .1), 0)

    def test_peers_leave_target_out_and_do_not_use_future_meta(self):
        f = platform_features(asof_rows(accumulation(), NOW, 'BUFF'), NOW, config())
        pool = {f'Sticker | p{i}': {'feature': f, 'meta': {}} for i in range(6)}
        pool['Sticker | target'] = {'feature': f, 'meta': {}}
        result = peer_context('Sticker | target', f, {}, pool, config())
        self.assertEqual(result['count'], 6)
        self.assertNotIn('Sticker | target', result['names'])
        self.assertTrue(result['supply_is_proxy'])

    def test_epoch_milliseconds_and_aware_iso(self):
        self.assertEqual(timestamp(NOW*1000), NOW)
        self.assertIsNone(timestamp('2026-09-12T12:00:00'))
        self.assertEqual(platform_name('buff163'), 'BUFF')
        self.assertNotEqual(platform_name('notbuff'), 'BUFF')


class StateMachineTests(unittest.TestCase):
    def feature(self, **changes):
        return {'price24': .08, 'price7': .1, 'drawdown24': 0, 'bid_fade24': 0,
                'refill24': 0, 'adequate_24h': True, 'sustained_contraction': True,
                'bid24': .3, **changes}

    def test_full_progression_and_no_same_tick_confirmation(self):
        state, cfg = PhaseState(), config()
        state.advance(self.feature(), NOW, cfg)
        state.advance(self.feature(), NOW, cfg)
        self.assertEqual(state.stage, 'CALM')
        state.advance(self.feature(), NOW+21600, cfg)
        self.assertEqual(state.stage, 'ACCUMULATION')
        state.advance(self.feature(price24=.15), NOW+43200, cfg)
        state.advance(self.feature(price24=.15), NOW+64800, cfg)
        self.assertEqual(state.stage, 'IGNITION')
        state.advance(self.feature(price24=.4), NOW+86400, cfg)
        state.advance(self.feature(price24=.4), NOW+108000, cfg)
        self.assertEqual(state.stage, 'MARKUP')
        state.advance(self.feature(refill24=.6, bid_fade24=.6), NOW+108001, cfg)
        self.assertEqual(state.stage, 'DISTRIBUTION')
        state.advance(self.feature(drawdown24=.4, bid_fade24=.7), NOW+108002, cfg)
        self.assertEqual(state.stage, 'CRASH')
        state.advance(self.feature(), NOW+130000, cfg)
        self.assertEqual(state.stage, 'CRASH')
