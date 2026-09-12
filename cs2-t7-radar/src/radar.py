import argparse
import json
import os
import sys
import time
from pathlib import Path
import db
from steamdt import SteamDTClient, SteamDTError
from settings import settings
from engine import score_all, decision_report
from collector import refresh_universe, collect_batch, collect_market, collect_hot, archive_kline
from backtest import walk_forward
from domain import timestamp

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    return settings(json.loads(Path(path or ROOT/'config.json').read_text('utf-8')))


def emit(value, output=None):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Generated report output, never credentials.
        target.write_text(text+'\n', encoding='utf-8')
    else:
        print(text)


def cli_time(value):
    parsed = timestamp(value)
    if parsed is None:
        raise argparse.ArgumentTypeError('use UTC epoch seconds or timezone-aware ISO date')
    return parsed


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='BUFF CS2 T+7 radar')
    ap.add_argument('--db', default=os.getenv('RADAR_DB', str(ROOT/'radar.db')))
    ap.add_argument('--config')
    ap.add_argument('--fee', type=float, help='explicit seller fee fraction, e.g. 0.025 is a scenario assumption')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('refresh-universe')
    sub.add_parser('collect-once')
    sub.add_parser('collect-market')
    sub.add_parser('collect-hot')
    p = sub.add_parser('archive-kline')
    p.add_argument('--name')
    p.add_argument('--type', type=int, default=1)
    p = sub.add_parser('score')
    p.add_argument('--top', type=int, default=20)
    p.add_argument('--as-of', type=cli_time)
    p.add_argument('--calibration')
    p.add_argument('--output')
    p = sub.add_parser('backtest')
    p.add_argument('--start', type=cli_time, required=True)
    p.add_argument('--end', type=cli_time, required=True)
    p.add_argument('--as-of', type=cli_time)
    p.add_argument('--output')
    p.add_argument('--calibration-output')
    p = sub.add_parser('import-data')
    p.add_argument('path')
    sub.add_parser('status')
    p = sub.add_parser('run')
    p.add_argument('--calibration')
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.fee is not None:
        cfg = settings({**cfg, 'fee_rate': args.fee})
    conn = db.connect(args.db)
    try:
        if args.cmd == 'score':
            now = args.as_of or int(time.time())
            calibration = json.loads(Path(args.calibration).read_text('utf-8')) if args.calibration else None
            emit(decision_report(score_all(conn, cfg, now, calibration, persist=True), now, args.top), args.output)
        elif args.cmd == 'backtest':
            result = walk_forward(conn, args.start, args.end, args.as_of or int(time.time()), cfg)
            emit(result, args.output)
            if args.calibration_output:
                emit(result['latest_calibration'], args.calibration_output)
        elif args.cmd == 'status':
            span = conn.execute('SELECT COUNT(*),COUNT(DISTINCT name),MIN(sampled_at),MAX(sampled_at) FROM snapshots').fetchone()
            emit({'catalog_items': len(db.enabled_items(conn)), 'snapshot_rows': span[0],
                  'sampled_items': span[1], 'first_sample_at': span[2], 'last_sample_at': span[3],
                  'market_points': conn.execute('SELECT COUNT(*) FROM market_points').fetchone()[0],
                  'api_key_configured': bool(os.getenv('STEAMDT_API_KEY')), 'fee_rate': cfg['fee_rate']})
        elif args.cmd == 'import-data':
            # Receipt times must be original, auditable times. Retrospective sources use today's available_at.
            data = json.loads(Path(args.path).read_text('utf-8'))
            for batch in data.get('batches', []):
                if 'sampled_at' not in batch:
                    raise ValueError('import batches require original sampled_at')
                db.insert_batch(conn, batch['data'], batch['sampled_at'])
            for version in data.get('items', []):
                db.upsert_items(conn, version['data'], cli_time(str(version['available_at'])))
            for point in data.get('market', []):
                db.insert_market(conn, point['value'], point['observed_at'], point['available_at'])
            db.insert_evidence(conn, data.get('evidence', []))
            emit({'status': 'IMPORTED'})
        else:
            client = SteamDTClient()  # Offline commands need no API key.
            if args.cmd == 'refresh-universe':
                emit(refresh_universe(client, conn, cfg))
            elif args.cmd == 'collect-once':
                emit(collect_batch(client, conn, cfg))
            elif args.cmd == 'collect-market':
                emit(collect_market(client, conn))
            elif args.cmd == 'collect-hot':
                emit(collect_hot(client, conn, cfg, score_all(conn, cfg)))
            elif args.cmd == 'archive-kline':
                emit(archive_kline(client, conn, args.name, args.type))
            elif args.cmd == 'run':
                if not db.enabled_items(conn):
                    emit(refresh_universe(client, conn, cfg))
                while True:
                    started = time.time()
                    try:
                        emit(refresh_universe(client, conn, cfg))
                        emit(collect_batch(client, conn, cfg))
                        emit(collect_market(client, conn))
                        calibration = (json.loads(Path(args.calibration).read_text('utf-8'))
                                       if args.calibration else None)
                        results = score_all(conn, cfg, calibration=calibration)
                        emit(collect_hot(client, conn, cfg, results))
                        now = int(time.time())
                        results = score_all(conn, cfg, now, calibration, persist=True)
                        emit(decision_report(results, now, 10))
                    except (SteamDTError, OSError, ValueError) as error:
                        print('采集未完成:', str(error), file=sys.stderr)
                    time.sleep(max(1, max(61,cfg.get('batch_interval_seconds',61))-(time.time()-started)))
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, SteamDTError, OSError) as error:
        print('错误:', str(error), file=sys.stderr)
        sys.exit(2)
