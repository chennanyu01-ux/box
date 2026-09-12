"""Generate an honest data-readiness/backtest report, without any API requests."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import db
from radar import load_config, emit
from backtest import walk_forward
from settings import settings

parser = argparse.ArgumentParser()
parser.add_argument('--fee', type=float, required=True, help='explicit fee scenario; not a verified platform fee')
args = parser.parse_args()
sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
conn = db.connect(root/'radar.db')
try:
    now = int(time.time())
    span = conn.execute('SELECT MIN(sampled_at),MAX(sampled_at),COUNT(*),COUNT(DISTINCT name) FROM snapshots').fetchone()
    cfg = settings({**load_config(), 'fee_rate': args.fee})
    report = walk_forward(conn, span[0] or now-1, now, now, cfg)
    report['fee_scenario_only'] = args.fee
    report['data_readiness'] = {'first_sample_at':span[0], 'last_sample_at':span[1],
                              'snapshot_rows':span[2], 'sampled_items':span[3],
                              'catalog_items':len(db.enabled_items(conn))}
    emit(report, root/'reports/live_backtest_readiness.json')
    names = load_config()['watch_names'] + ['MP9 | Sand Dashed (Factory New)',
        'M4A4 | Buzz Kill (Minimal Wear)', "M4A1-S | Chantico's Fire (Minimal Wear)"]
    metadata = [db.item_meta(conn,name) for name in names]
    emit(metadata,root/'reports/verified_names.json')
    print(json.dumps({'status':report['status'],'data_readiness':report['data_readiness'],
                      'attempted_entries':report['attempted_entries'],
                      't7_observed':report['unfiltered_cohort']['horizons']['7']['observed'],
                      't7_missing_or_censored':report['unfiltered_cohort']['horizons']['7']['missing_or_censored'],
                      'names':metadata},ensure_ascii=False,indent=2))
finally:
    conn.close()
