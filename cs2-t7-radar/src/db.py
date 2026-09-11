import sqlite3, time


def connect(path):
    c=sqlite3.connect(path); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS items(name TEXT PRIMARY KEY, display TEXT, buff_item_id TEXT, enabled INTEGER DEFAULT 1)')
    cols={r['name'] for r in c.execute('PRAGMA table_info(items)')}
    if 'buff_item_id' not in cols:
        c.execute('ALTER TABLE items ADD COLUMN buff_item_id TEXT')
    c.execute('CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY, name TEXT, platform TEXT, sampled_at INTEGER, sell_price REAL, sell_count INTEGER, bid_price REAL, bid_count INTEGER, source_update_time INTEGER)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_snap_name_time ON snapshots(name,sampled_at)')
    c.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT)')
    c.commit(); return c


def _buff_item_id(item):
    for p in item.get('platformList') or []:
        if 'buff' in str(p.get('name','')).lower():
            return str(p.get('itemId',''))
    return ''


def upsert_items(c,items):
    rows=[(x['marketHashName'],x.get('name',''),_buff_item_id(x),1) for x in items]
    c.executemany('INSERT OR REPLACE INTO items(name,display,buff_item_id,enabled) VALUES(?,?,?,?)',rows); c.commit()


def enabled_items(c): return [r['name'] for r in c.execute('SELECT name FROM items WHERE enabled=1 ORDER BY name')]


def item_meta(c,name):
    r=c.execute('SELECT name,display,buff_item_id FROM items WHERE name=?',(name,)).fetchone()
    return dict(r) if r else {'name':name,'display':'','buff_item_id':''}


def insert_batch(c,data,sampled_at=None):
    t=sampled_at or int(time.time()); rows=[]
    for item in data or []:
        for p in item.get('dataList') or []:
            rows.append((item.get('marketHashName'),p.get('platform',''),t,p.get('sellPrice'),p.get('sellCount'),p.get('biddingPrice'),p.get('biddingCount'),p.get('updateTime')))
    c.executemany('INSERT INTO snapshots(name,platform,sampled_at,sell_price,sell_count,bid_price,bid_count,source_update_time) VALUES(?,?,?,?,?,?,?,?)',rows); c.commit(); return len(rows)


def get_state(c,key,default='0'):
    r=c.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone(); return default if not r else r['value']


def set_state(c,key,value):
    c.execute('INSERT OR REPLACE INTO state(key,value) VALUES(?,?)',(key,str(value))); c.commit()


def candidates(c,hours=168):
    cutoff=int(time.time())-hours*3600
    return [r['name'] for r in c.execute('SELECT DISTINCT name FROM snapshots WHERE sampled_at>=?',(cutoff,))]


def series(c,name,hours=168):
    cutoff=int(time.time())-hours*3600
    return c.execute('SELECT name AS market_hash_name,platform,sampled_at,sell_price,sell_count,bid_price,bid_count FROM snapshots WHERE name=? AND sampled_at>=? ORDER BY sampled_at',(name,cutoff)).fetchall()
