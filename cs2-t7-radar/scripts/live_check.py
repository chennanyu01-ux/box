"""Finite live read-only API check; data stays in the ignored local database."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from radar import load_config
from steamdt import SteamDTClient, SteamDTError
from collector import collect_hot, collect_market, archive_kline, collect_batch
from engine import score_all, decision_report
import db

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
conn, client, cfg = db.connect(root/'radar.db'), SteamDTClient(), load_config()
try:
    print(json.dumps({'batch': collect_batch(client, conn, cfg)}))
    print(json.dumps({'market': collect_market(client, conn)}))
    print(json.dumps({'hot': collect_hot(client, conn, cfg, score_all(conn, cfg))}))
    for name in (None, 'Sticker | Mastermind (Holo)', 'Sticker | Enemy Spotted (Holo)'):
        try:
            print(json.dumps({'kline_name': name, **archive_kline(client, conn, name)}, ensure_ascii=False))
        except SteamDTError as error:
            print(str(error))
        time.sleep(.6)
    result = decision_report(score_all(conn, cfg, persist=True), int(time.time()))
    reports = root/'reports'
    reports.mkdir(exist_ok=True)
    (reports/'live_decisions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('decision','sampled_items','buy_candidates_count')}, ensure_ascii=False))
finally:
    conn.close()
