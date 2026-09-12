"""Unified decision layer: BUFF execution, causal phase, separate evidence models."""
import math
from collections import defaultdict
from domain import DAY, asof_rows, pct
from settings import settings
from features import platform_features, accumulation_band, raw_scores
from state_machine import PhaseState, STAGES_CN
from attribution import classify
from context import residual
from calibration import MODEL_VERSION, forecast


def prepare(rows, now, cfg):
    clean = asof_rows(rows, now)
    grouped = defaultdict(list)
    for row in clean:
        grouped[row['platform']].append(row)
    features = {p: platform_features(v, now, cfg) for p, v in grouped.items()}
    return grouped, features


def score_item(rows, now=None, *, cfg=None, market=None, peers=None, evidence=(), calibration=None):
    if not rows:
        return None
    cfg = settings(cfg)
    now = max(r['sampled_at'] for r in rows) if now is None else now
    grouped, features = prepare(rows, now, cfg)
    buff = features.get('BUFF')
    result = {'as_of': now, 'model_version': MODEL_VERSION, 'score_basis': 'heuristic_not_probability',
              'score': 0, 'entry_score': 0,
              'manipulation_score': 0, 'distribution_risk': 0, 'stage': 'CALM', 'stage_cn': '平静',
              'action': 'WATCH_NO_BUFF', 'reference_platform': 'BUFF' if buff else None,
              'buff_data_available': bool(buff and buff.get('sell_price')),
              'buff_sell_price': buff.get('sell_price') if buff else None,
              'buff_bid_price': buff.get('bid_price') if buff else None,
              'buff_quote_at': buff.get('sampled_at') if buff else None,
              'buff_source_at': buff.get('source_update_time') if buff else None,
              'buy_price_max': None, 'no_chase_above': None, 't7_forecast': None,
              'reasons': [], 'blockers': [], 'platforms': len(features)}
    if not buff:
        result['blockers'] = ['NO_BUFF']
        result['reasons'] = ['缺少 BUFF 盘口，无法计算实际买入价和退出收益']
        return result
    market = market or {'available': False, 'return24': None, 'regime': 'UNKNOWN'}
    peers = peers or {'available': False, 'return24': None, 'inventory_change24': None, 'count': 0, 'names': []}
    confirmations = sum(f['fresh'] and f['sustained_contraction'] and (f['bid24'] or 0) > .1
                        for p, f in features.items() if p != 'BUFF')
    market_residual = residual(buff['price24'], market.get('return24'))
    peer_residual = residual(buff['price24'], peers.get('return24'))
    abnormal = min(market_residual, peer_residual) if market_residual is not None and peer_residual is not None else None
    inventory_residual = (peers['inventory_change24'] - buff['sell24']
                          if peers.get('inventory_change24') is not None and buff['sell24'] is not None else None)
    manipulation, entry, distribution = raw_scores(buff, confirmations, abnormal, inventory_residual)
    phase = PhaseState()
    buff_rows = grouped['BUFF']
    transitions = []
    for index, row in enumerate(buff_rows):
        f = platform_features(buff_rows[:index+1], row['sampled_at'], cfg)
        previous = phase.stage
        phase.advance(f, row['sampled_at'], cfg)
        if previous != phase.stage:
            transitions.append({'at': row['sampled_at'], 'from': previous, 'to': phase.stage})
    band = accumulation_band(buff_rows, now, cfg)
    cause = classify(evidence, now, buff, market.get('return24'), peers.get('return24'))
    # Social attention can reduce entry quality; it never supplies a positive return label.
    distribution = min(100, distribution + .25*cause['fomo_risk'])
    entry = max(0, entry - .25*cause['fomo_risk'] - .2*cause['event_risk'])
    if cause['category'] in ('VALVE_EVENT', 'SUPPLY_FUNDAMENTAL', 'MARKET_SECTOR'):
        manipulation *= .5
    blockers = []
    reasons = []
    if not buff['fresh']:
        blockers.append('STALE_OR_UNTIMED_BUFF')
    if buff['sell_price'] is None or buff['bid_price'] is None or buff['bid_price'] > buff['sell_price']:
        blockers.append('INVALID_BUFF_QUOTE')
    if not buff['adequate_24h'] or not buff['has_7d_baseline']:
        blockers.append('INSUFFICIENT_HISTORY')
    if not buff['sustained_contraction']:
        blockers.append('UNCONFIRMED_INVENTORY_PERSISTENCE')
    if (buff['sell_count'] or 0) < cfg['min_sell_count'] or (buff['bid_count'] or 0) < cfg['min_bid_count']:
        blockers.append('LOW_LIQUIDITY')
    if buff['spread'] is None or not 0 <= buff['spread'] <= cfg['max_spread']:
        blockers.append('WIDE_OR_INVALID_SPREAD')
    if not market.get('available'):
        blockers.append('NO_MARKET_BASELINE')
    if not peers.get('available'):
        blockers.append('INSUFFICIENT_PEERS')
    if market.get('regime') == 'RISK_OFF':
        blockers.append('MARKET_RISK_OFF')
    early = (phase.stage == 'ACCUMULATION' and now-phase.since >= cfg['confirmation_seconds']
             or phase.stage == 'IGNITION' and now-phase.since <= DAY)
    if not early:
        blockers.append('OUTSIDE_EARLY_ENTRY_PHASE')
    if distribution >= cfg['max_distribution_risk'] or phase.stage in ('DISTRIBUTION', 'CRASH', 'MARKUP'):
        blockers.append('LATE_PHASE_OR_DISTRIBUTION')
    if band is None:
        blockers.append('NO_ACCUMULATION_BAND')
    if cause['event_risk'] >= 50:
        blockers.append('EVENT_REQUIRES_SEPARATE_VALIDATION')
    if cfg['fee_rate'] is None:
        blockers.append('FEE_NOT_CONFIGURED')
    prediction = forecast(calibration, phase.stage, market.get('regime'), band, now, cfg)
    if prediction is None:
        blockers.append('NO_VALID_T7_CALIBRATION')
    ceiling = no_chase = None
    if prediction and cfg['fee_rate'] is not None and buff['sell_price']:
        keep = (1-cfg['fee_rate'])*(1-cfg['slippage_rate'])
        median_ceiling = prediction['bid_q50']*keep/(1+cfg['min_t7_return'])
        risk_ceiling = prediction['bid_q10']*keep/(1-cfg['max_t7_loss'])
        ceiling = min(median_ceiling, risk_ceiling, band['high']*(1+cfg['max_band_premium']))
        ceiling = math.floor(ceiling*100)/100
        no_chase = ceiling
        prediction = {**prediction, 'return7_q10': prediction['bid_q10']*keep/buff['sell_price']-1,
                      'return7_q50': prediction['bid_q50']*keep/buff['sell_price']-1}
        if buff['sell_price'] > ceiling or ceiling <= 0:
            blockers.append('ABOVE_T7_PRICE_CEILING')
    if entry < cfg['min_entry_score']:
        blockers.append('ENTRY_SCORE_TOO_LOW')
    if not result['buff_data_available']:
        action = 'WATCH_NO_BUFF'
    elif not blockers:
        action = 'BUY_CANDIDATE'
    elif 'LATE_PHASE_OR_DISTRIBUTION' in blockers or 'MARKET_RISK_OFF' in blockers:
        action = 'AVOID'
    elif early and band:
        action = 'WATCH_BUY_ZONE'
    else:
        action = 'WATCH'
    reasons.append(f"BUFF 库存持续性 {buff['persistence_score']:.2f}，连续窗口内下降 {buff['decline_steps']} 次；库存变化不等于成交")
    reasons.append('当前阶段：' + STAGES_CN[phase.stage])
    if band:
        reasons.append(f"BUFF 安静收缩区报价带 {band['low']:.2f}–{band['high']:.2f}，不是已证实的庄家成交成本")
    if prediction is None:
        reasons.append('缺少合格的历史 T+7 求购退出样本，暂不给出可买价格')
    result.update(score=round(entry, 2), entry_score=round(entry, 2),
                  manipulation_score=round(manipulation, 2), distribution_risk=round(distribution, 2),
                  stage=phase.stage, stage_cn=STAGES_CN[phase.stage], stage_since=phase.since,
                  phase_transitions=transitions, action=action, blockers=blockers, reasons=reasons,
                  buy_price_max=ceiling, no_chase_above=no_chase, t7_forecast=prediction,
                  accumulation_band=band, band_premium=pct(buff['sell_price'], band['mid']) if band else None,
                  buff_sell_count=buff['sell_count'], buff_bid_count=buff['bid_count'],
                  buff_price_24h=buff['price24'], buff_price_7d=buff['price7'],
                  buff_sell_24h=buff['sell24'], buff_bid_24h=buff['bid24'],
                  buff_spread=buff['spread'], persistence_score=buff['persistence_score'],
                  market=market, peers=peers, market_residual24=market_residual,
                  peer_residual24=peer_residual, inventory_residual24=inventory_residual,
                  confirming_platforms=confirmations, attribution=cause,
                  data_quality={'fresh': buff['fresh'], 'points24': buff['points24'],
                                'max_gap_seconds': buff['max_gap_seconds'], 'coverage24': buff['coverage24'],
                                'has_7d_baseline': buff['has_7d_baseline']},
                  execution={'entry': 'BUFF lowest ask', 'exit': 'BUFF highest bid at/after unlock',
                             'cooldown_days': cfg['cooldown_days'], 'quantity': 1,
                             'fee_rate': cfg['fee_rate'], 'slippage_rate': cfg['slippage_rate'],
                             'fill_assumption': 'top quote simulation; order depth and fills unverified'})
    return result
