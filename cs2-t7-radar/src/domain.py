"""Shared point-in-time, numeric and venue rules. All timestamps are UTC seconds."""
import math
from datetime import datetime

DAY = 86400
BUFF_ALIASES = {'buff', 'buff163', 'buff.163.com', '网易buff'}


def platform_name(value):
    text = str(value or '').strip()
    lowered = text.casefold()
    if lowered in BUFF_ALIASES:
        return 'BUFF'
    if lowered in ('youpin', 'yyyp', 'uu', '悠悠', '悠悠有品'):
        return 'YOUPIN'
    if lowered in ('c5', 'c5game', 'c5game.com'):
        return 'C5'
    return text.upper()


def number(value, positive=False):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        return None
    return result


def timestamp(value):
    if isinstance(value, str) and not value.replace('.', '', 1).isdigit():
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return None
            return int(parsed.timestamp())
        except ValueError:
            return None
    value = number(value, positive=True)
    if value is None:
        return None
    return int(value / 1000 if value >= 100_000_000_000 else value)


def pct(current, previous):
    if current is None or previous is None or previous <= 0:
        return None
    return current / previous - 1


def clamp(value, low=0, high=1):
    return max(low, min(high, value))


def norm(value, low, high):
    return 0 if value is None else clamp((value - low) / (high - low))


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * q
    left = int(index)
    return values[left] + (values[min(left + 1, len(values) - 1)] - values[left]) * (index - left)


def asof_rows(rows, as_of, venue=None):
    """First observation of a source update: a re-poll is not new evidence.

    Missing source times remain inspectable but cannot pass the buy gate.
    Never move a late-arriving quote to its earlier provider timestamp.
    """
    out, seen = [], set()
    for original in sorted(rows, key=lambda r: r['sampled_at']):
        row = dict(original)
        sampled = timestamp(row.get('sampled_at'))
        source = timestamp(row.get('source_update_time'))
        platform = platform_name(row.get('platform'))
        if sampled is None or sampled > as_of or (source is not None and source > sampled):
            continue
        if venue and platform != venue:
            continue
        key = (platform, source if source is not None else sampled)
        if key in seen:
            continue
        seen.add(key)
        row.update(platform=platform, sampled_at=sampled, source_update_time=source)
        for field in ('sell_price', 'bid_price', 'sell_count', 'bid_count'):
            row[field] = number(row.get(field), positive=field.endswith('price'))
        out.append(row)
    return out


def fresh(row, now, max_age, require_source=True):
    if not row or now - row['sampled_at'] > max_age or row['sampled_at'] > now:
        return False
    source = row.get('source_update_time')
    if source is None:
        return not require_source
    return 0 <= now - source <= max_age


def at_or_before(rows, target, max_age):
    candidates = [r for r in rows if r['sampled_at'] <= target]
    if not candidates:
        return None
    row = candidates[-1]
    return row if fresh(row, target, max_age, require_source=False) else None
