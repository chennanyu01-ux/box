import copy
import unittest
from fixtures import quote, config, NOW, DAY
from backtest import simulate_trade, summarize, walk_forward_splits
from calibration import fit_calibration


class ExecutableReturns(unittest.TestCase):
    def rows(self):
        return [quote(NOW, 100, 95), quote(NOW+3*DAY, 600, 500),
                quote(NOW+7*DAY, 150, 90), quote(NOW+7*DAY+60, 1000, 200),
                quote(NOW+14*DAY, 160, 120), quote(NOW+30*DAY, 180, 140)]

    def test_t7_first_bid_not_hindsight_peak_or_ask(self):
        result = simulate_trade(self.rows(), NOW, NOW+31*DAY, config())
        self.assertEqual(result['entry_price'], 100)
        self.assertEqual(result['horizons']['7']['bid_price'], 90)
        self.assertAlmostEqual(result['horizons']['7']['net_return'], 90*.975*.995/100-1)
        self.assertFalse(result['success_t7'])
        self.assertAlmostEqual(result['max_executable_quote_return'], 200*.975*.995/100-1)
        self.assertEqual(result['horizons']['14']['bid_price'], 120)
        self.assertEqual(result['horizons']['30']['bid_price'], 140)

    def test_cold_period_high_quote_is_never_an_exit(self):
        rows = [quote(NOW, 100, 90), quote(NOW+6*DAY, 1000, 900)]
        result = simulate_trade(rows, NOW, NOW+31*DAY, config())
        self.assertIsNone(result['max_executable_quote_return'])
        self.assertEqual(result['horizons']['7']['status'], 'MISSING_BID')

    def test_no_buff_never_produces_realized_returns(self):
        rows = self.rows()
        for row in rows:
            row['platform'] = 'C5'
        result = simulate_trade(rows, NOW, NOW+31*DAY, config())
        self.assertEqual(result['status'], 'NO_EXECUTABLE_BUFF_ENTRY')

    def test_zero_bid_count_and_missing_bids_remain_missing(self):
        rows = self.rows()
        for row in rows[1:]:
            row['bid_count'] = 0
        result = simulate_trade(rows, NOW, NOW+31*DAY, config())
        self.assertEqual(result['horizons']['7']['status'], 'MISSING_BID')
        self.assertIsNone(result['success_t7'])

    def test_asof_censors_future_and_extending_data_cannot_change_t7(self):
        early = simulate_trade(self.rows(), NOW, NOW+5*DAY, config())
        self.assertEqual(early['horizons']['7']['status'], 'RIGHT_CENSORED')
        a = simulate_trade(self.rows(), NOW, NOW+8*DAY, config())
        b = simulate_trade(self.rows()+[quote(NOW+40*DAY, 9999, 9000)], NOW, NOW+50*DAY, config())
        self.assertEqual(a['horizons']['7'], b['horizons']['7'])
        self.assertIsNone(a['label_known_at'])

    def test_quote_before_unlock_repolled_after_unlock_is_not_new_exit(self):
        rows = [quote(NOW, 100, 95), quote(NOW+7*DAY, 150, 120)]
        rows[-1]['source_update_time'] = NOW+7*DAY-3600
        result = simulate_trade(rows, NOW, NOW+31*DAY, config())
        self.assertEqual(result['horizons']['7']['status'], 'MISSING_BID')

    def test_late_quotes_respect_tolerance_and_report_delay(self):
        rows = [quote(NOW,100,95), quote(NOW+7*DAY+3600,110,105)]
        result = simulate_trade(rows, NOW, NOW+31*DAY, config())
        self.assertEqual(result['horizons']['7']['delay_seconds'], 3600)
        rows[-1]['sampled_at'] += DAY
        rows[-1]['source_update_time'] += DAY
        result = simulate_trade(rows, NOW, NOW+31*DAY, config())
        self.assertEqual(result['horizons']['7']['status'], 'MISSING_BID')

    def test_actual_later_unlock_overrides_seven_day_approximation(self):
        rows = self.rows()+[quote(NOW+9*DAY,120,100)]
        result = simulate_trade(rows, NOW, NOW+31*DAY, config(), unlock_at=NOW+9*DAY)
        self.assertEqual(result['horizons']['7']['status'], 'LOCKED')
        self.assertEqual(result['unlock']['at'], NOW+9*DAY)

    def test_missing_outcomes_count_in_coverage(self):
        result = simulate_trade([quote(NOW)], NOW, NOW+31*DAY, config())
        summary = summarize([result])['horizons']['7']
        self.assertEqual(summary['coverage'], 0)
        self.assertEqual(summary['missing_or_censored'], 1)
        self.assertIsNone(summary['mean_net_return'])

    def test_fee_is_explicit_and_cooldown_cannot_be_disabled(self):
        with self.assertRaises(ValueError):
            simulate_trade(self.rows(), NOW, NOW+31*DAY)
        with self.assertRaises(ValueError):
            config(cooldown_days=0)
        with self.assertRaises(ValueError):
            config(fee_rate=float('nan'))


class TemporalSplits(unittest.TestCase):
    def test_label_end_must_precede_fit_cutoff(self):
        samples = [{'name': str(i), 'entry_at': NOW-40*DAY, 'stage': 'ACCUMULATION',
                    'regime': 'NEUTRAL', 'group_id': str(i), 'label_known_at': t,
                    'band_mid': 10, 'exit7_bid': price, 'return7': .1}
                   for i,(t,price) in enumerate(((NOW-1,11),(NOW,1000),(NOW+1,9999)))]
        result = fit_calibration(samples, NOW, config())
        self.assertEqual(result['trained_until'], NOW-1)
        profile = result['profiles']['ACCUMULATION:NEUTRAL']
        self.assertEqual(profile['samples'], 1)
        self.assertEqual(profile['bid_over_band_q50'], 1.1)

    def test_shared_episode_cannot_dominate_training(self):
        samples = [{'name': str(i), 'entry_at': NOW-40*DAY+i, 'stage': 'CALM',
                    'regime': 'NEUTRAL', 'group_id': 'one_wave', 'label_known_at': NOW-1,
                    'band_mid': 10, 'exit7_bid': 10+i, 'return7': 0} for i in range(100)]
        result = fit_calibration(samples, NOW, config())
        self.assertEqual(result['profiles']['CALM:NEUTRAL']['samples'], 1)

    def test_rolling_splits_have_embargo_and_nonoverlapping_test_periods(self):
        splits = list(walk_forward_splits(NOW, NOW+300*DAY, config()))
        self.assertEqual(len(splits), 4)
        for split in splits:
            self.assertLess(split['fit_at'], split['test_start'])
        for a,b in zip(splits,splits[1:]):
            self.assertEqual(a['test_end'], b['test_start'])
