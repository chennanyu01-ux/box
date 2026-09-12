"""Rate-limited discovery plus focused observations; catalog includes every item type."""
import json
import re
import time
import db
from steamdt import SteamDTError
from domain import timestamp


def refresh_universe(client, conn, cfg):
    last = int(db.get_state(conn, 'universe_refreshed_at'))
    if time.time()-last < 86400 and db.enabled_items(conn):
        return {'items': len(db.enabled_items(conn)), 'status': 'CACHED'}
    attempted = int(db.get_state(conn, 'universe_requested_at'))
    if time.time()-attempted < 86400:
        raise SteamDTError('base catalog request quota reserved; retry after the daily interval')
    # Reserve the API slot even if the network request subsequently fails.
    db.set_state(conn, 'universe_requested_at', int(time.time()))
    items = client.base_info()
    db.upsert_items(conn, items)
    db.set_state(conn, 'universe_refreshed_at', int(time.time()))
    return {'items': len(items), 'status': 'REFRESHED'}


def universe(conn, cfg):
    include = [re.compile(x, re.I) for x in cfg.get('universe_include', [])]
    exclude = [re.compile(x, re.I) for x in cfg.get('universe_exclude', [])]
    return [name for name in db.enabled_items(conn)
            if (not include or any(r.search(name) for r in include))
            and not any(r.search(name) for r in exclude)]


def collect_batch(client, conn, cfg):
    names = universe(conn, cfg)
    if not names:
        raise RuntimeError('universe empty; run refresh-universe first')
    size = min(100, len(names), max(1, int(cfg.get('batch_size', 100))))
    remaining = max(61, cfg.get('batch_interval_seconds', 61))-(time.time()-float(db.get_state(conn, 'last_batch_at')))
    if remaining > 0:
        return {'status': 'RATE_LIMIT_WAIT', 'retry_after': remaining}
    cursor = int(db.get_state(conn, 'batch_cursor')) % len(names)
    chosen = [names[(cursor+i)%len(names)] for i in range(size)]
    db.set_state(conn, 'last_batch_at', int(time.time()))
    data = client.price_batch(chosen)
    count = db.insert_batch(conn, data)
    db.set_state(conn, 'batch_cursor', (cursor+size)%len(names))
    return {'status': 'COLLECTED', 'items': size, 'rows': count, 'universe_items': len(names),
            'estimated_sweep_hours': len(names)/size*max(61,cfg.get('batch_interval_seconds',61))/3600,
            'next_cursor': (cursor+size)%len(names)}


def collect_market(client, conn):
    data = client.broad_index()
    now = int(time.time())
    db.insert_market(conn, data['broadMarketIndex'], data['updateTime'], now, raw=data)
    added = 1
    # This two-column history shape was verified against the live API on 2026-09-12.
    # available_at is retrieval time; old observations are never made visible earlier.
    for point in data.get('historyMarketIndexList', []):
        if isinstance(point, list) and len(point) == 2:
            observed = timestamp(point[0])
            if observed is not None and observed <= now:
                db.insert_market(conn, point[1], observed, now, raw=point)
                added += 1
    return {'points': added, 'available_at': now}


def hot_names(conn, cfg, results=()):
    limit = min(30, max(0, int(cfg.get('hot_limit', 30))))
    if not limit:
        return []
    known = set(db.enabled_items(conn))
    seeds = [n for n in cfg.get('watch_names', []) if n in known]
    ranked = [r['marketHashName'] for r in sorted(results, key=lambda r: (
        r.get('data_quality', {}).get('fresh', False),
        r.get('buff_data_available', False),
        max(0, -(r.get('buff_sell_24h') or 0)) + max(0, r.get('buff_bid_24h') or 0),
        r['entry_score']), reverse=True) if r['marketHashName'] in known]
    cursor = int(db.get_state(conn, 'hot_cursor'))
    seed_limit = min(len(seeds), max(1, limit//3))
    selected_seeds = [seeds[(cursor+i)%len(seeds)] for i in range(seed_limit)] if seeds else []
    # Reserve discovery slots even when there are more historical seeds than the budget.
    discovery = [n for n in ranked if n not in selected_seeds]
    return list(dict.fromkeys(selected_seeds+discovery))[:limit]


def collect_hot(client, conn, cfg, results=()):
    names = hot_names(conn, cfg, results)
    rows, sampled = 0, 0
    for name in names:
        remaining = 1.2-(time.time()-float(db.get_state(conn, 'last_single_at')))
        if remaining > 0:
            time.sleep(remaining)
        db.set_state(conn, 'last_single_at', time.time())
        data = client.price_single(name)
        rows += db.insert_batch(conn, [{'marketHashName': name, 'dataList': data}])
        sampled += 1
    db.set_state(conn, 'hot_cursor', int(db.get_state(conn, 'hot_cursor'))+max(1,len(names)//3))
    return {'items': sampled, 'rows': rows}


def archive_kline(client, conn, name=None, kline_type=1):
    data = client.item_kline(name, kline_type, platform='BUFF') if name else client.broad_kline(kline_type)
    path = '/open/cs2/item/v1/kline' if name else '/open/cs2/broad/v1/kline'
    now = int(time.time())
    with conn:
        conn.execute('INSERT OR IGNORE INTO raw_responses VALUES(?,?,?,?)',
                     (path, json.dumps({'name': name, 'platform': 'BUFF' if name else None, 'type': kline_type}),
                      now, json.dumps(data, ensure_ascii=False)))
    return {'rows': len(data or []), 'available_at': now,
            'status': 'RAW_RESEARCH_ONLY', 'reason': 'K线未提供可验证的历史最高求购价和数量，禁止当作退出盘口'}
