"""Causal BUFF features. Inventory changes describe listings, never trade volume."""
import statistics
from domain import DAY, pct, norm, clamp, quantile, fresh, at_or_before


def platform_features(rows, now, cfg):
    rows = [r for r in rows if r['sampled_at'] <= now]
    if not rows:
        return None
    cur = rows[-1]
    old24 = at_or_before(rows, now - DAY, cfg['max_gap_seconds'])
    old7 = at_or_before(rows, now - 7 * DAY, cfg['max_gap_seconds'])
    w24 = [r for r in rows if now - DAY <= r['sampled_at'] <= now]
    if old24 and (not w24 or old24['sampled_at'] < w24[0]['sampled_at']):
        w24.insert(0, old24)
    def change(field, old):
        return pct(cur[field], old[field]) if old else None
    prices = [r['sell_price'] for r in w24 if r['sell_price'] is not None]
    sells = [r['sell_count'] for r in w24 if r['sell_count'] is not None]
    bids = [r['bid_count'] for r in w24 if r['bid_count'] is not None]
    deltas = [b - a for a, b in zip(sells, sells[1:])]
    decreases = [-v for v in deltas if v < 0]
    variation = sum(abs(v) for v in deltas)
    persistence = max(0, (sells[0] - sells[-1]) / variation) if variation else 0
    gaps = [b['sampled_at'] - a['sampled_at'] for a, b in zip(w24, w24[1:])]
    gap = max(gaps, default=DAY * 2)
    coverage = min(DAY, now - w24[0]['sampled_at']) / DAY if w24 else 0
    complete = (len(sells) == len(w24) and len(bids) == len(w24) and len(prices) == len(w24)
                and all(fresh(r, r['sampled_at'], cfg['max_quote_age_seconds']) for r in w24))
    adequate = (complete and len(w24) >= cfg['min_24h_points'] and coverage >= .9
                and gap <= cfg['max_gap_seconds'] and old24 is not None)
    decline_steps = len(decreases)
    largest_drop_share = max(decreases, default=0) / sum(decreases) if decreases else 0
    sustained = adequate and decline_steps >= cfg['min_decline_steps'] and persistence >= cfg['min_persistence']
    # A single dominant drop can be a withdrawal even with a perfect net/variation ratio.
    sustained = sustained and largest_drop_share <= .65
    spread = pct(cur['bid_price'], cur['sell_price'])
    refill = max(0, pct(cur['sell_count'], min(sells)) or 0) if sells else None
    bid_fade = max(0, -(pct(cur['bid_count'], max(bids)) or 0)) if bids else None
    drawdown = max(0, -(pct(cur['sell_price'], max(prices)) or 0)) if prices else None
    return {
        **cur, 'price24': change('sell_price', old24), 'price7': change('sell_price', old7),
        'sell24': change('sell_count', old24), 'sell7': change('sell_count', old7),
        'bid24': change('bid_count', old24), 'bid7': change('bid_count', old7),
        'spread': -spread if spread is not None else None,
        'range24': pct(max(prices), min(prices)) if prices else None,
        'drawdown24': drawdown, 'refill24': refill, 'bid_fade24': bid_fade,
        'persistence_score': persistence, 'inventory_variation': variation,
        'decline_steps': decline_steps, 'largest_drop_share': largest_drop_share,
        'sustained_contraction': sustained, 'adequate_24h': adequate,
        'points24': len(w24), 'max_gap_seconds': gap, 'coverage24': coverage,
        'has_7d_baseline': old7 is not None and fresh(old7, now-7*DAY, cfg['max_gap_seconds']),
        'fresh': fresh(cur, now, cfg['max_quote_age_seconds']),
    }


def accumulation_band(rows, now, cfg):
    """Last contiguous quiet squeeze, using quoted asks rather than inferred fills."""
    segments, current = [], []
    window = [r for r in rows if now - 7 * DAY <= r['sampled_at'] <= now]
    for left, right in zip(window, window[1:]):
        fields = ('sell_count', 'bid_count', 'sell_price', 'bid_price')
        valid = all(left[k] is not None and right[k] is not None for k in fields)
        quiet = (valid and right['sampled_at'] - left['sampled_at'] <= cfg['max_gap_seconds']
                 and right['sell_count'] <= left['sell_count']
                 and right['bid_count'] >= left['bid_count'] > 0
                 and -.02 <= (pct(right['sell_price'], left['sell_price']) or 0) <= .03
                 and right['bid_price'] >= .9 * right['sell_price'])
        if quiet:
            if not current:
                current = [left]
            current.append(right)
        else:
            if current:
                segments.append(current)
            current = []
    if current:
        segments.append(current)
    for segment in reversed(segments):
        if now - segment[-1]['sampled_at'] > 3 * DAY:
            continue
        declines = [a['sell_count'] - b['sell_count'] for a, b in zip(segment, segment[1:])]
        steps = [d for d in declines if d > 0]
        if (len(steps) < cfg['min_decline_steps'] or segment[-1]['sampled_at'] - segment[0]['sampled_at'] < DAY
                or max(steps) > .65 * sum(steps)
                or (pct(segment[-1]['sell_count'], segment[0]['sell_count']) or 0) > -.08
                or (pct(segment[-1]['sell_price'], segment[0]['sell_price']) or 0) > .20):
            continue
        prices = [r['sell_price'] for r in segment]
        low, high = quantile(prices, .25), quantile(prices, .75)
        return {'low': low, 'high': high, 'mid': statistics.median(prices),
                'started_at': segment[0]['sampled_at'], 'ended_at': segment[-1]['sampled_at'],
                'points': len(segment), 'decline_steps': len(steps),
                'basis': 'BUFF quiet-squeeze ask band; not actual participant cost'}
    return None


def raw_scores(f, confirmations=0, abnormal_return=None, inventory_residual=None):
    sustained = float(f['sustained_contraction'])
    squeeze = max(0, -(f['sell24'] or 0))
    m = 30 * norm(squeeze, .05, .4) * sustained
    m += 20 * norm(f['bid24'], .05, 1) + 15 * f['persistence_score'] * sustained
    m += 10 * norm(confirmations, 0, 2)
    m += 15 * norm(abnormal_return, .01, .15)
    m += 10 * norm(inventory_residual, .05, .3)
    d = 25 * norm(f['refill24'], .1, .7) + 25 * norm(f['bid_fade24'], .1, .6)
    d += 25 * norm(f['drawdown24'], .08, .35) + 15 * norm(f['range24'], .2, .8)
    d += 10 * norm(f['price7'], .8, 3)
    stability = 1 - norm(abs(f['price24'] or 0), .12, .4)
    entry = .75 * m + 15 * stability + 10 * (1 - norm(f['spread'], .03, .15)) - .8 * d
    entry -= 20 * norm(f['price24'], .25, .7) + 20 * norm(f['price7'], .7, 2)
    return clamp(m, 0, 100), clamp(entry, 0, 100), clamp(d, 0, 100)
