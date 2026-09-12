"""Evidence classification is separate from price prediction and outcome labels."""
from urllib.parse import urlparse
from domain import DAY, timestamp, norm

CATEGORIES = ('CONCENTRATED_CAPITAL', 'SUPPLY_FUNDAMENTAL', 'VALVE_EVENT',
              'MARKET_SECTOR', 'SOCIAL_FOMO', 'ILLIQUID_SPIKE', 'UNKNOWN')


def validate_evidence(record):
    row = dict(record)
    for key in ('id', 'url', 'published_at', 'available_at', 'kind'):
        if not row.get(key):
            raise ValueError(f'evidence missing {key}')
    for key in ('published_at', 'available_at'):
        row[key] = timestamp(row[key])
        if row[key] is None:
            raise ValueError(f'invalid evidence {key}')
    if row['published_at'] > row['available_at']:
        raise ValueError('evidence cannot be known before publication')
    if urlparse(row['url']).scheme not in ('https', 'http'):
        raise ValueError('evidence requires a public source URL')
    if row['kind'] not in ('official_event', 'supply_change', 'inventory_observation', 'social_fomo', 'claim'):
        raise ValueError('unknown evidence kind')
    if row.get('confidence', 0) < 0 or row.get('confidence', 0) > 1:
        raise ValueError('confidence must be in [0,1]')
    return row


def classify(evidence, as_of, feature, market_return=None, peer_return=None):
    visible = [validate_evidence(r) for r in evidence
               if timestamp(r.get('available_at')) is not None
               and timestamp(r.get('published_at')) is not None
               and timestamp(r['available_at']) <= as_of and timestamp(r['published_at']) <= as_of]
    recent = [r for r in visible if as_of-r['published_at'] <= 7*DAY]
    # Same repost/URL cluster is one observation. Engagement totals are not historical heat.
    unique = {r.get('independence_group') or r['url']: r for r in recent}
    recent = list(unique.values())
    def official_url(url):
        parsed = urlparse(url)
        if parsed.hostname in ('www.counter-strike.net', 'counter-strike.net'):
            return parsed.path.startswith('/newsentry/')
        if parsed.hostname == 'store.steampowered.com':
            return parsed.path.startswith('/news/app/730/view/')
        if parsed.hostname == 'steamcommunity.com':
            return parsed.path.startswith(('/ogg/730/announcements/detail/', '/games/CSGO/announcements/detail/'))
        return False
    official = [r for r in recent if r['kind'] == 'official_event' and r.get('verified') is True
                and official_url(r['url'])]
    supply = [r for r in recent if r['kind'] == 'supply_change' and r.get('verified') is True]
    objective = [r for r in recent if r['kind'] == 'inventory_observation'
                 and r.get('verified') is True and r.get('metrics') and r.get('independence_group')]
    fomo = [r for r in recent if r['kind'] == 'social_fomo']
    heat = 100 * norm(len(fomo), 1, 8)
    category, confidence = 'UNKNOWN', 0.0
    if min(feature.get('sell_count') or 0, feature.get('bid_count') or 0) < 3:
        category, confidence = 'ILLIQUID_SPIKE', .7
    elif official:
        category, confidence = 'VALVE_EVENT', .9
    elif supply:
        category, confidence = 'SUPPLY_FUNDAMENTAL', .8
    elif (market_return is not None and peer_return is not None
          and max(market_return, peer_return) > .08
          and abs((feature['price24'] or 0) - peer_return) < .05):
        category, confidence = 'MARKET_SECTOR', .7
    elif len(objective) >= 2 and feature['sustained_contraction']:
        category, confidence = 'CONCENTRATED_CAPITAL', .8
    elif heat >= 30:
        category, confidence = 'SOCIAL_FOMO', .6
    # Only independently verified observations can supply a high-weight causal label.
    weight = confidence if category == 'CONCENTRATED_CAPITAL' and confidence >= .8 else 0
    return {'category': category, 'confidence': confidence, 'manipulation_training_weight': weight,
            'fomo_risk': heat, 'event_risk': 80 if official else (50 if supply else 0),
            'visible_evidence_ids': [r['id'] for r in recent],
            'objective_sources': len(objective),
            'note': '归因是证据支持的推断，不是资金身份认定'}
