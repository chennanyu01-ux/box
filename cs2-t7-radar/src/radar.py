import argparse, json, os, re, time
from pathlib import Path
from steamdt import SteamDTClient
import db
from scoring import score_item

ROOT = Path(__file__).resolve().parents[1]

def load_config():
    return json.loads((ROOT/'config.json').read_text('utf-8'))

def refresh_universe(client, conn, cfg):
    items = client.base_info()
    inc = [re.compile(x, re.I) for x in cfg['universe_include']]
    exc = [re.compile(x, re.I) for x in cfg.get('universe_exclude',[])]
    chosen=[]
    for x in items:
        mh=x.get('marketHashName','')
        if inc and not any(r.search(mh) for r in inc): continue
        if any(r.search(mh) for r in exc): continue
        chosen.append(x)
    db.upsert_items(conn, chosen)
    db.set_state(conn,'universe_refreshed_at',int(time.time()))
    return len(chosen)

def collect_batch(client, conn, cfg):
    items=db.enabled_items(conn)
    if not items: raise RuntimeError('universe empty; run refresh-universe first')
    size=cfg.get('batch_size',100)
    cursor=int(db.get_state(conn,'batch_cursor','0')) % len(items)
    batch=items[cursor:cursor+size]
    if len(batch)<size: batch += items[:size-len(batch)]
    data=client.price_batch(batch)
    count=db.insert_batch(conn,data)
    db.set_state(conn,'batch_cursor',(cursor+size)%len(items))
    return {'items':len(batch),'rows':count,'next_cursor':(cursor+size)%len(items)}

def score_all(conn, cfg):
    results=[]
    now=int(time.time())
    for mh in db.latest_candidates(conn,168):
        s=score_item(db.series(conn,mh,168),now)
        if s:
            s['marketHashName']=mh
            results.append(s)
    results.sort(key=lambda x:x['score'],reverse=True)
    return results

def main():
    ap=argparse.ArgumentParser(description='CS2 T+7 accumulation radar')
    ap.add_argument('--db', default=os.getenv('RADAR_DB', str(ROOT/'radar.db')))
    sub=ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('refresh-universe')
    sub.add_parser('collect-once')
    p=sub.add_parser('score'); p.add_argument('--top',type=int,default=20)
    sub.add_parser('run')
    args=ap.parse_args(); cfg=load_config(); conn=db.connect(args.db); client=SteamDTClient()
    if args.cmd=='refresh-universe': print(json.dumps({'universe':refresh_universe(client,conn,cfg)},ensure_ascii=False))
    elif args.cmd=='collect-once': print(json.dumps(collect_batch(client,conn,cfg),ensure_ascii=False))
    elif args.cmd=='score': print(json.dumps(score_all(conn,cfg)[:args.top],ensure_ascii=False,indent=2))
    elif args.cmd=='run':
        if not db.enabled_items(conn):
            print('refreshing universe...'); print(refresh_universe(client,conn,cfg))
        while True:
            try:
                print(time.strftime('%F %T'), collect_batch(client,conn,cfg))
                top=score_all(conn,cfg)[:10]
                print(json.dumps(top,ensure_ascii=False))
            except Exception as e:
                print('collector error:',repr(e))
            time.sleep(cfg.get('batch_interval_seconds',61))
if __name__=='__main__': main()
