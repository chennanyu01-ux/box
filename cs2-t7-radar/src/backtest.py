"""Executable-quote T+7 labels and chronological walk-forward evaluation.

No peak is a training success label. Missing bids remain censored observations.
One unit per hypothetical trade; no order-depth, fills or portfolio capacity claims.
"""
import statistics
from domain import DAY, asof_rows, at_or_before, fresh, quantile
from settings import settings
from calibration import fit_calibration, config_hash, MODEL_VERSION
import db


def _exit(rows, target, as_of, cfg):
    tolerance = cfg['exit_tolerance_seconds']
    for row in rows:
        if row['sampled_at'] < target or row['sampled_at'] > min(target+tolerance, as_of):
            continue
        if (fresh(row, row['sampled_at'], cfg['max_quote_age_seconds'])
                and row['source_update_time'] >= target and row.get('bid_price')
                and (row.get('bid_count') or 0) >= 1
                and (row.get('sell_price') is None or row['bid_price'] <= row['sell_price'])):
            return {'status': 'OBSERVED', 'target_at': target, 'at': row['sampled_at'],
                    'source_at': row['source_update_time'], 'bid_price': row['bid_price'],
                    'delay_seconds': row['sampled_at']-target}
    return {'status': 'RIGHT_CENSORED' if as_of < target+tolerance else 'MISSING_BID',
            'target_at': target, 'at': None, 'bid_price': None, 'net_return': None}


def _drawdown(values):
    if not values:
        return None
    peak, worst = values[0], 0
    for value in values:
        peak = max(peak, value)
        worst = max(worst, 1-value/peak)
    return worst


def simulate_trade(rows, entry_at, as_of, cfg=None, unlock_at=None):
    cfg = settings(cfg)
    if cfg['fee_rate'] is None:
        raise ValueError('set an explicit fee_rate for backtests; no assumed BUFF fee')
    if entry_at > as_of:
        raise ValueError('entry_at cannot be after evaluation as_of')
    clean = asof_rows(rows, as_of, 'BUFF')
    entry = at_or_before(clean, entry_at, cfg['max_quote_age_seconds'])
    if not entry or not fresh(entry, entry_at, cfg['max_quote_age_seconds']) or not entry['sell_price'] or (entry['sell_count'] or 0) < 1:
        return {'status': 'NO_EXECUTABLE_BUFF_ENTRY', 'entry_at': entry_at, 'horizons': {},
                'entry_price': None, 'label_known_at': None}
    if entry['bid_price'] and entry['bid_price'] > entry['sell_price']:
        return {'status': 'INVALID_BUFF_ENTRY', 'entry_at': entry_at, 'horizons': {},
                'entry_price': None, 'label_known_at': None}
    unlock = max(entry_at+cfg['cooldown_days']*DAY, unlock_at or 0)
    keep = (1-cfg['fee_rate'])*(1-cfg['slippage_rate'])
    def exit_result(target):
        value = _exit(clean, target, as_of, cfg)
        if value['bid_price'] is not None:
            value['net_return'] = value['bid_price']*keep/entry['sell_price']-1
        return value
    horizons = {}
    for days in (7, 14, 30):
        target = entry_at+days*DAY
        horizons[str(days)] = (exit_result(target) if target >= unlock else
                              {'status': 'LOCKED', 'target_at': target, 'at': None,
                               'bid_price': None, 'net_return': None})
    end = min(as_of, entry_at+30*DAY)
    marks = [r for r in clean if entry_at <= r['sampled_at'] <= end
             and fresh(r, r['sampled_at'], cfg['max_quote_age_seconds'])
             and r['bid_price'] and (r['bid_count'] or 0) > 0
             and (r['sell_price'] is None or r['bid_price'] <= r['sell_price'])]
    unlocked = [r for r in marks if r['sampled_at'] >= unlock and r['source_update_time'] >= unlock]
    locked = [r for r in marks if r['sampled_at'] < unlock]
    mark_values = [entry['sell_price']] + [r['bid_price']*keep for r in marks]
    unlocked_values = [r['bid_price']*keep for r in unlocked]
    times = [entry_at] + [r['sampled_at'] for r in marks] + [end]
    max_gap = max((b-a for a,b in zip(times,times[1:])), default=0)
    label_ready = entry_at+30*DAY+cfg['exit_tolerance_seconds']
    known_at = label_ready if as_of >= label_ready else None
    return {'status': 'SIMULATED', 'entry_at': entry_at, 'entry_quote_at': entry['sampled_at'],
            'entry_source_at': entry['source_update_time'], 'entry_price': entry['sell_price'],
            'reference_platform': 'BUFF', 'quantity': 1, 'unlock_at': unlock,
            'unlock': exit_result(unlock), 'horizons': horizons, 'label_known_at': known_at,
            'success_t7': (horizons['7']['net_return'] >= cfg['min_t7_return']
                           if horizons['7'].get('net_return') is not None else None),
            'mark_to_bid_max_drawdown': _drawdown(mark_values) if marks else None,
            'locked_mark_to_bid_max_drawdown': _drawdown([entry['sell_price']]+[r['bid_price']*keep for r in locked]) if locked else None,
            'unlocked_max_drawdown': _drawdown(unlocked_values),
            'max_executable_quote_return': (max(unlocked_values)/entry['sell_price']-1 if unlocked_values else None),
            'max_return_is_diagnostic_only': True,
            'path_coverage': {'complete_30d': as_of >= label_ready and max_gap <= cfg['max_gap_seconds'],
                              'max_gap_seconds': max_gap, 'observations': len(marks),
                              'note': '回撤与最大收益仅基于观察到的求购报价，稀疏采样可能低估风险'},
            'fee_rate': cfg['fee_rate'], 'slippage_rate': cfg['slippage_rate'],
            'fill_assumption': 'one-unit best-quote simulation, not verified order execution'}


def walk_forward_splits(start, end, cfg):
    train_days, test_days = cfg['walk_forward_train_days'], cfg['walk_forward_test_days']
    fold = start+train_days*DAY
    while fold < end:
        yield {'train_start': max(start, fold-train_days*DAY),
               'fit_at': fold-cfg['embargo_days']*DAY,
               'test_start': fold, 'test_end': min(fold+test_days*DAY, end)}
        fold += test_days*DAY


def summarize(trades):
    report = {'observations': len(trades), 'horizons': {}}
    for horizon in ('7', '14', '30'):
        values = [t['horizons'].get(horizon, {}).get('net_return') for t in trades]
        available = [v for v in values if v is not None]
        report['horizons'][horizon] = {
            'observed': len(available), 'missing_or_censored': len(values)-len(available),
            'coverage': len(available)/len(values) if values else 0,
            'mean_net_return': statistics.mean(available) if available else None,
            'median_net_return': statistics.median(available) if available else None,
            'loss_rate_observed': sum(v<0 for v in available)/len(available) if available else None,
            'worst_net_return': min(available) if available else None,
            # Unknown outcomes are not silently discarded from this conservative bound.
            'nonpositive_or_unknown_rate': sum(v is None or v<=0 for v in values)/len(values) if values else None}
    drawdowns = [t['mark_to_bid_max_drawdown'] for t in trades if t.get('mark_to_bid_max_drawdown') is not None]
    report['worst_observed_mark_to_bid_drawdown'] = max(drawdowns) if drawdowns else None
    return report


def walk_forward(conn, start, end, as_of, cfg=None):
    from engine import score_all
    cfg = settings(cfg)
    if cfg['fee_rate'] is None:
        raise ValueError('fee_rate is required')
    if end <= start or end > as_of:
        raise ValueError('require start < end <= as_of')
    decisions, labels, samples = {}, {}, []
    for when in range(start, end, int(cfg['decision_step_days']*DAY)):
        current = score_all(conn, cfg, when)
        decisions[when] = current
        for signal in current:
            name = signal['marketHashName']
            future = db.series(conn, name, (as_of-when)/3600+24, as_of)
            label = simulate_trade(future, when, as_of, cfg)
            labels[(when,name)] = label
            if label['entry_price'] is None:
                continue
            band = signal.get('accumulation_band')
            group = (signal.get('collection_name') or name) + ':' + str(when//(30*DAY))
            sample = {'name': name, 'entry_at': when, 'stage': signal['stage'],
                      'regime': signal.get('market', {}).get('regime', 'UNKNOWN'),
                      'group_id': group, 'label_known_at': label['label_known_at'],
                      'band_mid': band['mid'] if band else None,
                      'exit7_bid': label['horizons'].get('7', {}).get('bid_price'),
                      'return7': label['horizons'].get('7', {}).get('net_return')}
            samples.append(sample)
    folds, out_of_sample, controls = [], [], []
    last_selected_at = {}
    for split in walk_forward_splits(start, end, cfg):
        train = [s for s in samples if split['train_start'] <= s['entry_at'] < split['fit_at']
                 and s['label_known_at'] is not None and s['label_known_at'] < split['fit_at']]
        calibration = fit_calibration(train, split['fit_at'], cfg)
        selected, fold_controls, control_keys = [], [], set()
        for when in sorted(t for t in decisions if split['test_start'] <= t < split['test_end']):
            rescored = score_all(conn, cfg, when, calibration)
            for signal in rescored:
                if signal['action'] != 'BUY_CANDIDATE':
                    continue
                name = signal['marketHashName']
                # A full 30d gap also applies across fold boundaries.
                if when-last_selected_at.get(name, -10**15) < 30*DAY:
                    continue
                last_selected_at[name] = when
                label = {**labels[(when,name)], 'name': name, 'decision_at': when}
                selected.append(label)
                for peer in signal.get('peers', {}).get('names', []):
                    key = (peer, when)
                    if key in control_keys or (when,peer) not in labels:
                        continue
                    control_keys.add(key)
                    fold_controls.append({**labels[(when,peer)], 'name': peer, 'matched_at': when})
        out_of_sample.extend(selected)
        controls.extend(fold_controls)
        folds.append({**split, 'mature_training_observations': len(train),
                      'training_label_max_at': max((s['label_known_at'] for s in train), default=None),
                      'calibration': calibration, 'selected': summarize(selected),
                      'matched_controls': summarize(fold_controls)})
    latest = fit_calibration([s for s in samples if s['entry_at'] >= as_of-cfg['walk_forward_train_days']*DAY],
                             as_of, cfg)
    executable = [value for value in labels.values() if value.get('entry_price') is not None]
    return {'model_version': MODEL_VERSION, 'config_hash': config_hash(cfg), 'as_of': as_of,
            'status': ('EVALUATED' if out_of_sample else 'NO_VALIDATED_SIGNALS')
                      if folds and any(t['label_known_at'] for t in executable) else 'INSUFFICIENT_HISTORY',
            'folds': folds, 'out_of_sample': summarize(out_of_sample), 'matched_controls': summarize(controls),
            'unfiltered_cohort': summarize(executable), 'attempted_entries': len(labels),
            'non_executable_entries': len(labels)-len(executable),
            'negative_outcomes': sum((s['return7'] is not None and s['return7']<=0) for s in samples),
            'cohort_observations': samples,
            'out_of_sample_trades': out_of_sample,
            'matched_control_trades': controls,
            'latest_calibration': latest,
            'limitations': ['历史全样本取自当时采集范围，无法消除采集之前的存活/选择偏差',
                           '没有 BUFF 求购历史的退出保留为缺失，不用 K 线高价补齐',
                           '冻结启发式规则；训练仅用已成熟标签，测试期不调参',
                           '同品至少间隔30日才重复选入测试统计；统计为单笔观察，不是可叠加的组合收益',
                           '没有实际成交/深度，结果是含手续费滑点的单件盘口模拟']}
