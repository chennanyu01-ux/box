"""Point-in-time benchmarks and leave-one-out matched peers."""
import math
import statistics
from domain import DAY, pct, at_or_before, fresh

def category(name, meta):
    if meta.get('category'):
        return meta['category']
    for prefix, kind in (('Sticker |', 'sticker'), ('Sealed Graffiti |', 'graffiti'),
                         ('Graffiti |', 'graffiti'), ('Charm |', 'charm'),
                         ('Patch |', 'patch'), ('Music Kit |', 'music_kit')):
        if name.startswith(prefix):
            return kind
    if 'Capsule' in name:
        return 'capsule'
    if ' | ' in name:
        return 'weapon_finish'
    if 'Case' in name:
        return 'case'
    return 'other'


def peer_bucket(name, meta, feature):
    return peer_type(name, meta), int(math.log2(feature['sell_price'])) if feature.get('sell_price') else 0


def peer_type(name, meta):
    kind = category(name, meta)
    if kind == 'weapon_finish':
        # Canonical identifier, not a translated label or future metadata.
        weapon = name.split(' | ')[0]
        wear = name.rsplit(' (', 1)[-1] if ' (' in name else 'unknown_wear'
        return kind + ':' + weapon + ':' + wear
    if kind == 'sticker':
        finish = next((x for x in ('Holo', 'Foil', 'Gold', 'Glitter', 'Lenticular')
                       if '('+x+')' in name), 'Paper')
        return kind + ':' + finish
    return kind


def collection_name(name, meta):
    if meta.get('collection_name'):
        return meta['collection_name']
    if category(name, meta) == 'sticker' and len(name.split(' | ')) >= 3:
        return name.split(' | ')[-1]  # E.g. Stockholm 2021, explicitly in canonical name.
    return None


def peer_context(name, feature, meta, pool, cfg):
    peers = []
    kind = peer_type(name, meta)
    for other_name, other in pool.items():
        if other_name == name:
            continue
        f, m = other['feature'], other['meta']
        if not f or not f['fresh'] or not f['adequate_24h'] or peer_type(other_name, m) != kind:
            continue
        if feature.get('sell_price') is None or f.get('sell_price') is None:
            continue
        ratios = [f['sell_price'] / feature['sell_price']]
        if not .5 <= ratios[0] <= 2:
            continue
        if not all(feature.get(k) and f.get(k) for k in ('sell_count', 'bid_count')):
            continue
        ratios += [f['sell_count']/feature['sell_count'], f['bid_count']/feature['bid_count']]
        if any(not .25 <= r <= 4 for r in ratios[1:]):
            continue
        if meta.get('supply') and m.get('supply'):
            ratios.append(m['supply']/meta['supply'])
            if not .25 <= ratios[-1] <= 4:
                continue
        if meta.get('liquidity') and m.get('liquidity'):
            ratios.append(m['liquidity']/meta['liquidity'])
            if not .25 <= ratios[-1] <= 4:
                continue
        collection, other_collection = collection_name(name, meta), collection_name(other_name, m)
        same_collection = bool(collection and collection == other_collection)
        if collection and not same_collection:
            continue
        distance = sum(abs(math.log(r)) for r in ratios) + (0 if same_collection else 1)
        peers.append((distance, other_name, f, same_collection))
    selected = sorted(peers, key=lambda r: (r[0], r[1]))[:cfg['peer_limit']]
    valid = len(selected) >= cfg['min_peer_count']
    returns = [p[2]['price24'] for p in selected if p[2]['price24'] is not None]
    inventories = [p[2]['sell24'] for p in selected if p[2]['sell24'] is not None]
    return {'count': len(selected), 'available': valid and len(returns) >= cfg['min_peer_count'],
            'names': [p[1] for p in selected],
            'return24': statistics.median(returns) if valid and returns else None,
            'inventory_change24': statistics.median(inventories) if valid and inventories else None,
            'same_collection_count': sum(p[3] for p in selected),
            'matching': 'type + BUFF price + listing/bid-count liquidity proxies; verified collection/supply when available',
            'supply_is_proxy': not bool(meta.get('supply'))}


def market_context(rows, now, cfg):
    normalized = []
    for r in rows:
        if r['available_at'] <= now and r['observed_at'] <= r['available_at'] and r['value'] > 0:
            normalized.append({'sampled_at': r['observed_at'], 'source_update_time': r['observed_at'],
                               'value': r['value']})
    normalized.sort(key=lambda r: r['sampled_at'])
    current = at_or_before(normalized, now, cfg['max_quote_age_seconds'])
    old = at_or_before(normalized, now-DAY, cfg['max_gap_seconds'])
    result = pct(current['value'], old['value']) if current and old else None
    regime = 'UNKNOWN' if result is None else ('RISK_OFF' if result < -.05 else 'RISK_ON' if result > .05 else 'NEUTRAL')
    return {'available': result is not None, 'return24': result, 'regime': regime,
            'method': 'log return residual, beta=1 (unfitted)', 'as_of': now}


def residual(item_return, benchmark_return):
    if item_return is None or benchmark_return is None or min(item_return, benchmark_return) <= -1:
        return None
    return math.log1p(item_return) - math.log1p(benchmark_return)
