"""Past-only empirical T+7 bid/band calibration, grouped to limit episode dominance."""
import hashlib
import json
from domain import DAY, quantile
from settings import settings

MODEL_VERSION = 't7-v2.0'


def config_hash(cfg):
    # All modelling/execution knobs, not display/collector settings.
    defaults = settings()
    values = {k: cfg.get(k, v) for k, v in defaults.items()}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:16]


def profile_key(stage, regime):
    return stage + ':' + regime


def fit_calibration(samples, as_of, cfg):
    mature = [s for s in samples if s['entry_at'] < as_of
              and s.get('label_known_at') is not None and s['label_known_at'] < as_of]
    profiles = {}
    for key in sorted({profile_key(s['stage'], s['regime']) for s in mature}):
        cohort = [s for s in mature if profile_key(s['stage'], s['regime']) == key]
        # Pick one earliest observation per item per 30d and cap each shared episode to one.
        independent = {}
        for s in sorted(cohort, key=lambda x: (x['entry_at'], x['name'])):
            independent.setdefault(s['group_id'], s)
        observations = list(independent.values())
        known = [s for s in observations if s.get('exit7_bid') is not None and s.get('band_mid')]
        ratios = [s['exit7_bid'] / s['band_mid'] for s in known]
        if not ratios:
            continue
        profiles[key] = {'samples': len(known), 'groups': len(independent), 'cohort_size': len(observations),
                         'coverage': len(known) / len(observations),
                         'losses': sum((s.get('return7') or 0) <= 0 for s in known),
                         'bid_over_band_q10': quantile(ratios, .10),
                         'bid_over_band_q50': quantile(ratios, .50),
                         'bid_over_band_q90': quantile(ratios, .90)}
    return {'model_version': MODEL_VERSION, 'config_hash': config_hash(cfg), 'fitted_at': as_of,
            'trained_until': max((s['label_known_at'] for s in mature), default=None),
            'method': 'past-only grouped empirical bid/band quantiles', 'profiles': profiles}


def forecast(calibration, stage, regime, band, as_of, cfg):
    if not calibration or not band:
        return None
    if (calibration.get('model_version') != MODEL_VERSION or calibration.get('config_hash') != config_hash(cfg)
            or calibration.get('trained_until') is None or calibration['trained_until'] >= as_of
            or calibration.get('fitted_at', as_of+1) > as_of
            or as_of-calibration['fitted_at'] > cfg['max_calibration_age_days']*DAY):
        return None
    profile = calibration.get('profiles', {}).get(profile_key(stage, regime))
    if (not profile or profile['samples'] < cfg['min_calibration_samples']
            or profile['groups'] < cfg['min_calibration_groups'] or profile['coverage'] < .9
            or profile.get('losses', 0) < 3):
        return None
    return {**profile, 'bid_q10': band['mid']*profile['bid_over_band_q10'],
            'bid_q50': band['mid']*profile['bid_over_band_q50'],
            'bid_q90': band['mid']*profile['bid_over_band_q90'],
            'fitted_at': calibration['fitted_at'],
            'note': '经验分位数，尚非保证成交或校准概率；含失败样本'}
