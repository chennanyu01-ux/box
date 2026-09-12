"""Conservative research defaults, not fitted probabilities or fee assertions."""
import math
DEFAULTS = {
    'history_hours': 504,
    'max_quote_age_seconds': 21600,
    'max_gap_seconds': 21600,
    'min_24h_points': 5,
    'min_decline_steps': 3,
    'min_persistence': 0.6,
    'min_peer_count': 5,
    'peer_limit': 30,
    'min_sell_count': 10,
    'min_bid_count': 10,
    'max_spread': 0.10,
    'max_band_premium': 0.15,
    'min_entry_score': 70,
    'max_distribution_risk': 40,
    'confirmation_seconds': 21600,
    'cooldown_days': 7,
    'exit_tolerance_seconds': 21600,
    'fee_rate': None,
    'slippage_rate': 0.005,
    'min_t7_return': 0.05,
    'max_t7_loss': 0.15,
    'min_calibration_samples': 30,
    'min_calibration_groups': 10,
    'max_calibration_age_days': 30,
    'walk_forward_train_days': 180,
    'walk_forward_test_days': 30,
    'embargo_days': 1,
    'decision_step_days': 7,
}


def settings(overrides=None):
    result = {**DEFAULTS, **(overrides or {})}
    for key, default in DEFAULTS.items():
        value = result[key]
        if value is None and key == 'fee_rate':
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} must be a finite number')
    for key in ('fee_rate', 'slippage_rate'):
        value = result[key]
        if value is None and key == 'fee_rate':
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value < 1:
            raise ValueError(f'{key} must be in [0, 1)')
    for key in ('max_quote_age_seconds', 'max_gap_seconds', 'exit_tolerance_seconds',
                'min_24h_points', 'min_decline_steps', 'min_peer_count', 'peer_limit',
                'min_calibration_samples', 'min_calibration_groups', 'decision_step_days',
                'walk_forward_train_days', 'walk_forward_test_days', 'confirmation_seconds'):
        if result[key] <= 0:
            raise ValueError(f'{key} must be positive')
    if result['cooldown_days'] < 7:
        raise ValueError('cooldown_days cannot be shorter than 7')
    if result['embargo_days'] < 0 or result['history_hours'] < 192:
        raise ValueError('embargo must be nonnegative and history must cover 8 days')
    if not 0 <= result['max_t7_loss'] < 1 or result['min_t7_return'] <= -1:
        raise ValueError('invalid T+7 return/loss limit')
    if not 0 <= result['min_persistence'] <= 1 or not 0 <= result['max_spread'] < 1:
        raise ValueError('invalid persistence/spread limit')
    if result['max_band_premium'] < 0 or result['max_calibration_age_days'] <= 0:
        raise ValueError('invalid band premium/calibration age')
    if result['min_calibration_samples'] < 3 or result['peer_limit'] < result['min_peer_count']:
        raise ValueError('insufficient calibration/peer limits')
    for key in ('peer_limit', 'decision_step_days', 'walk_forward_train_days', 'walk_forward_test_days'):
        if not float(result[key]).is_integer():
            raise ValueError(f'{key} must be an integer')
        result[key] = int(result[key])
    return result
