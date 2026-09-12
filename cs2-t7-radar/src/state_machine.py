"""Replayable state with dwell confirmation; only risk transitions are immediate."""
from dataclasses import dataclass
from domain import DAY

STAGES_CN = {'CALM': '平静', 'ACCUMULATION': '吸筹', 'IGNITION': '点火',
             'MARKUP': '主升', 'DISTRIBUTION': '派发', 'CRASH': '崩盘'}


@dataclass
class PhaseState:
    stage: str = 'CALM'
    since: int = 0
    pending: str = ''
    pending_since: int = 0
    last_at: int = 0

    def advance(self, f, now, cfg):
        if now <= self.last_at:
            return
        if not self.since:
            self.since = now
        self.last_at = now
        price = f['price24'] or 0
        crash = (f['drawdown24'] or 0) >= .30 and (f['bid_fade24'] or 0) >= .30
        distribution = ((f['refill24'] or 0) >= .25 and (f['bid_fade24'] or 0) >= .25)
        if crash:
            target = 'CRASH'
        elif distribution:
            target = 'DISTRIBUTION'
        elif self.stage in ('CRASH', 'DISTRIBUTION'):
            # No direct transition from a dump to a buyable phase.
            target = 'CALM' if now - self.since >= 2 * DAY and abs(price) < .08 else self.stage
        elif not f['adequate_24h']:
            self.pending = ''
            return
        elif self.stage == 'CALM':
            target = 'ACCUMULATION' if f['sustained_contraction'] and (f['bid24'] or 0) >= .10 and -.05 <= price <= .15 else 'CALM'
            if price > .30:
                target = 'MARKUP'
        elif self.stage == 'ACCUMULATION':
            if .10 <= price <= .30 and f['sustained_contraction']:
                target = 'IGNITION'
            elif price > .30 or (f['price7'] or 0) > .8:
                target = 'MARKUP'
            else:
                target = 'ACCUMULATION' if f['sustained_contraction'] else 'CALM'
        elif self.stage == 'IGNITION':
            target = 'MARKUP' if price > .30 or now-self.since > DAY else 'IGNITION'
            if not f['sustained_contraction'] and price < .05:
                target = 'CALM'
        else:
            target = 'CALM' if abs(price) < .05 and now-self.since >= 3*DAY else 'MARKUP'
        if target == self.stage:
            self.pending = ''
            return
        if target in ('CRASH', 'DISTRIBUTION'):
            self.stage, self.since, self.pending = target, now, ''
            return
        if self.pending != target:
            self.pending, self.pending_since = target, now
        elif now - self.pending_since >= cfg['confirmation_seconds']:
            self.stage, self.since, self.pending = target, now, ''
