"""Append-only observations and additive migrations; no destructive history refresh."""
import json
import sqlite3
import time
from domain import platform_name, timestamp, number


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS items(name TEXT PRIMARY KEY, display TEXT,
            buff_item_id TEXT, enabled INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY, name TEXT,
            platform TEXT, sampled_at INTEGER, sell_price REAL, sell_count INTEGER,
            bid_price REAL, bid_count INTEGER, source_update_time INTEGER);
        CREATE INDEX IF NOT EXISTS idx_snap_name_time ON snapshots(name,sampled_at);
        CREATE INDEX IF NOT EXISTS idx_snap_time ON snapshots(sampled_at,name);
        CREATE INDEX IF NOT EXISTS idx_snap_name_platform_time ON snapshots(name,platform,sampled_at,id);
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS item_versions(name TEXT, available_at INTEGER,
            display TEXT, buff_item_id TEXT, category TEXT, collection_name TEXT,
            supply REAL, liquidity REAL, enabled INTEGER, raw_json TEXT,
            PRIMARY KEY(name, available_at));
        CREATE TABLE IF NOT EXISTS market_snapshots(available_at INTEGER, observed_at INTEGER,
            value REAL, source TEXT, raw_json TEXT, PRIMARY KEY(available_at,source));
        CREATE TABLE IF NOT EXISTS market_points(available_at INTEGER, observed_at INTEGER,
            value REAL, source TEXT, raw_json TEXT, PRIMARY KEY(available_at,observed_at,source));
        INSERT OR IGNORE INTO market_points SELECT * FROM market_snapshots;
        CREATE TABLE IF NOT EXISTS raw_responses(path TEXT, request_key TEXT, available_at INTEGER,
            payload TEXT, PRIMARY KEY(path,request_key,available_at));
        CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, name TEXT,
            published_at INTEGER, available_at INTEGER, payload TEXT);
        CREATE TABLE IF NOT EXISTS decisions(name TEXT, as_of INTEGER, model_version TEXT,
            payload TEXT, PRIMARY KEY(name,as_of,model_version));
    ''')
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(items)')}
    if 'buff_item_id' not in cols:
        conn.execute('ALTER TABLE items ADD COLUMN buff_item_id TEXT')
    conn.execute('PRAGMA user_version=2')
    conn.commit()
    return conn


def _buff_item_id(item):
    return next((str(p.get('itemId') or '') for p in item.get('platformList', [])
                 if platform_name(p.get('name')) == 'BUFF'), '')


def upsert_items(conn, items, available_at=None):
    now = int(time.time()) if available_at is None else available_at
    with conn:
        for item in items:
            name = item.get('marketHashName')
            if not name:
                continue
            display, buff_id = item.get('name') or '', _buff_item_id(item)
            conn.execute('''INSERT INTO items(name,display,buff_item_id) VALUES(?,?,?)
                ON CONFLICT(name) DO UPDATE SET display=excluded.display,
                buff_item_id=excluded.buff_item_id''', (name, display, buff_id))
            enabled = conn.execute('SELECT enabled FROM items WHERE name=?', (name,)).fetchone()[0]
            conn.execute('INSERT OR IGNORE INTO item_versions VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (name, now, display, buff_id, item.get('category'), item.get('collection'),
                          number(item.get('supply')), number(item.get('liquidity')), enabled,
                          json.dumps(item, ensure_ascii=False)))


def enabled_items(conn):
    return [r[0] for r in conn.execute('SELECT name FROM items WHERE enabled=1 ORDER BY name')]


def item_meta(conn, name, as_of=None):
    if as_of is not None:
        row = conn.execute('''SELECT * FROM item_versions WHERE name=? AND available_at<=?
            ORDER BY available_at DESC LIMIT 1''', (name, as_of)).fetchone()
    else:
        row = conn.execute('SELECT * FROM items WHERE name=?', (name,)).fetchone()
    return dict(row) if row else {'name': name, 'display': '', 'buff_item_id': ''}


def insert_batch(conn, data, sampled_at=None):
    now = int(time.time()) if sampled_at is None else timestamp(sampled_at)
    if now is None:
        raise ValueError('invalid sampled_at')
    rows = []
    for item in data or []:
        name = item.get('marketHashName')
        if not name:
            continue
        for row in item.get('dataList') or []:
            platform = platform_name(row.get('platform'))
            source = timestamp(row.get('updateTime'))
            if not platform or (source and source > now):
                continue
            values = [number(row.get(field), positive='Price' in field)
                      for field in ('sellPrice', 'sellCount', 'biddingPrice', 'biddingCount')]
            rows.append((name, platform, now, *values, source))
    with conn:
        conn.executemany('''INSERT INTO snapshots(name,platform,sampled_at,sell_price,sell_count,
            bid_price,bid_count,source_update_time) VALUES(?,?,?,?,?,?,?,?)''', rows)
    return len(rows)


def insert_market(conn, value, observed_at, available_at, source='SteamDT', raw=None):
    value, observed_at, available_at = number(value, True), timestamp(observed_at), timestamp(available_at)
    if value is None or observed_at is None or available_at is None or observed_at > available_at:
        raise ValueError('market data needs a positive value and observed_at <= available_at')
    with conn:
        conn.execute('INSERT OR IGNORE INTO market_points VALUES(?,?,?,?,?)',
                     (available_at, observed_at, value, source, json.dumps(raw, ensure_ascii=False)))


def market_series(conn, as_of, hours=504):
    return [dict(r) for r in conn.execute('''SELECT * FROM market_points
        WHERE available_at<=? AND available_at>=? ORDER BY available_at''',
        (as_of, as_of - hours * 3600))]


def insert_evidence(conn, records):
    from attribution import validate_evidence
    with conn:
        for record in records:
            record = validate_evidence(record)
            conn.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?)',
                         (record['id'], record.get('name'), record['published_at'],
                          record['available_at'], json.dumps(record, ensure_ascii=False)))


def evidence_at(conn, name, as_of):
    return [json.loads(r[0]) for r in conn.execute('''SELECT payload FROM evidence
        WHERE (name=? OR name IS NULL) AND published_at<=? AND available_at<=?''',
        (name, as_of, as_of))]


def get_state(conn, key, default='0'):
    row = conn.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
    return default if row is None else row[0]


def set_state(conn, key, value):
    with conn:
        conn.execute('INSERT OR REPLACE INTO state VALUES(?,?)', (key, str(value)))


def candidates(conn, hours=504, as_of=None):
    now = int(time.time()) if as_of is None else as_of
    return [r[0] for r in conn.execute('''SELECT DISTINCT name FROM snapshots
        WHERE sampled_at>=? AND sampled_at<=? ORDER BY name''', (now-hours*3600, now))]


def series(conn, name, hours=504, as_of=None):
    now = int(time.time()) if as_of is None else as_of
    cutoff = now - hours * 3600
    return [dict(r) for r in conn.execute('''SELECT name AS market_hash_name,* FROM snapshots
        WHERE name=? AND sampled_at<=? AND (sampled_at>=? OR id IN
        (SELECT id FROM snapshots s WHERE s.name=? AND s.sampled_at<? AND NOT EXISTS
         (SELECT 1 FROM snapshots newer WHERE newer.name=s.name AND newer.platform=s.platform
          AND newer.sampled_at<? AND (newer.sampled_at>s.sampled_at OR
              (newer.sampled_at=s.sampled_at AND newer.id>s.id)))))
        ORDER BY sampled_at,id''', (name, now, cutoff, name, cutoff, cutoff))]


def save_decision(conn, name, result):
    with conn:
        conn.execute('INSERT OR IGNORE INTO decisions VALUES(?,?,?,?)',
                     (name, result['as_of'], result['model_version'],
                      json.dumps(result, ensure_ascii=False, allow_nan=False)))
