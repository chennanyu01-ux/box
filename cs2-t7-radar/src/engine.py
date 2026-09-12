"""Common live/replay scoring path, including point-in-time peer membership."""
from collections import defaultdict
import db
from context import market_context, peer_context, peer_bucket, collection_name
from scoring import score_item, prepare
from settings import settings


def score_all(conn, cfg=None, as_of=None, calibration=None, persist=False):
    import time
    cfg = settings(cfg)
    now = int(time.time()) if as_of is None else as_of
    market = market_context(db.market_series(conn, now, cfg['history_hours']), now, cfg)
    pool, buckets, series = {}, defaultdict(dict), {}
    for name in db.candidates(conn, cfg['history_hours'], now):
        rows = db.series(conn, name, cfg['history_hours'], now)
        series[name] = rows
        _, features = prepare(rows, now, cfg)
        feature = features.get('BUFF')
        meta = db.item_meta(conn, name, now)
        if feature:
            entry = {'feature': feature, 'meta': meta}
            pool[name] = entry
            buckets[peer_bucket(name, meta, feature)][name] = entry
    results = []
    for name, rows in series.items():
        meta = db.item_meta(conn, name, now)
        peers = None
        if name in pool:
            feature = pool[name]['feature']
            kind, band = peer_bucket(name, meta, feature)
            neighbors = {}
            for price_band in (band-1, band, band+1):
                neighbors.update(buckets.get((kind, price_band), {}))
            peers = peer_context(name, feature, meta, neighbors, cfg)
        result = score_item(rows, now, cfg=cfg, market=market, peers=peers,
                            evidence=db.evidence_at(conn, name, now), calibration=calibration)
        if result:
            result.update(marketHashName=name, name_cn=meta.get('display') or name,
                          name_source='SteamDT' if meta.get('display') else 'marketHashName',
                          buff_item_id=meta.get('buff_item_id') or None,
                          collection_name=collection_name(name, meta))
            results.append(result)
            if persist:
                db.save_decision(conn, name, result)
    return sorted(results, key=lambda r: (r['action'] == 'BUY_CANDIDATE', r['entry_score']), reverse=True)


def decision_report(results, as_of, top=20):
    buys = [r for r in results if r['action'] == 'BUY_CANDIDATE']
    return {'as_of': as_of, 'decision': '有通过条件的候选' if buys else '今天没有值得买的',
            'reason': '候选需复核 BUFF 实时盘口和实际解锁时间' if buys else
                      '本次已采样范围内，没有商品通过全部 T+7 数据、价格和风险门槛',
            'sampled_items': len(results), 'buy_candidates_count': len(buys),
            'buy_candidates': buys[:top], 'watchlist': [r for r in results if r['action'] != 'BUY_CANDIDATE'][:top],
            'coverage_note': '这是已采样商品的判断，不代表已完整检查全市场；缺数据不等于没有异动'}
