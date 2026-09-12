from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from domain import DAY
from settings import settings
from calibration import fit_calibration

NOW = 1_800_000_000


def quote(at, ask=10, bid=9.6, sell=200, bids=100, platform='BUFF', name='x'):
    return {'market_hash_name': name, 'platform': platform, 'sampled_at': at,
            'source_update_time': at, 'sell_price': ask, 'bid_price': bid,
            'sell_count': sell, 'bid_count': bids}


def accumulation(now=NOW, name='x'):
    result = []
    for hours in range(192, -1, -3):
        progress = max(0, 48-hours)/48
        ask = 10+.5*progress
        for platform in ('BUFF', 'C5', 'YOUPIN'):
            result.append(quote(now-hours*3600, ask, ask*.97, 200-120*progress,
                                100+180*progress, platform, name))
    return result


def config(**values):
    return settings({'fee_rate': .025, **values})


def benchmarks():
    return ({'available': True, 'return24': 0, 'regime': 'NEUTRAL'},
            {'available': True, 'return24': 0, 'inventory_change24': 0,
             'count': 10, 'names': [f'peer{i}' for i in range(10)]})


def calibration(cfg, now=NOW):
    # Synthetic training fixtures with profitable and losing T+7 entries.
    samples = [{'name': f'train{i}', 'entry_at': now-90*DAY+i*DAY,
                'stage': 'ACCUMULATION', 'regime': 'NEUTRAL', 'group_id': f'episode{i}',
                'label_known_at': now-60*DAY+i*DAY, 'band_mid': 10,
                'exit7_bid': 9.9 if i < 4 else 13, 'return7': -.06 if i < 4 else .20}
               for i in range(40)]
    return fit_calibration(samples, now-DAY, cfg)
