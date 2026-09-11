import math, statistics
from collections import defaultdict


def pct(a,b):
    if a is None or b in (None,0): return 0.0
    return a/b-1.0


def clamp(x,a,b): return max(a,min(b,x))
def norm(x,a,b): return clamp((x-a)/(b-a),0.0,1.0) if b!=a else 0.0


def nearest(rows,ts):
    out=None
    for r in rows:
        if r['sampled_at']<=ts: out=r
        else: break
    return out


def _valid(rows, field):
    return [r[field] for r in rows if r.get(field) is not None]


def platform_features(rows,now):
    rows=sorted(rows,key=lambda r:r['sampled_at']); cur=rows[-1]
    old24=nearest(rows,now-86400); old7=nearest(rows,now-604800)
    def ch(field,old): return pct(cur[field],old[field]) if old else 0.0
    spread=1.0
    if cur['sell_price'] and cur['bid_price'] and cur['sell_price']>0:
        spread=(cur['sell_price']-cur['bid_price'])/cur['sell_price']

    w24=[r for r in rows if r['sampled_at']>=now-86400]
    prices=_valid(w24,'sell_price'); sells=_valid(w24,'sell_count'); bids=_valid(w24,'bid_count')
    peak=max(prices) if prices else cur['sell_price']
    trough=min(prices) if prices else cur['sell_price']
    price_range=pct(peak,trough) if peak and trough else 0.0
    drawdown=max(0.0,-pct(cur['sell_price'],peak)) if peak else 0.0
    refill=max(0.0,pct(cur['sell_count'],min(sells))) if sells and min(sells)>0 else 0.0
    bid_fade=max(0.0,-pct(cur['bid_count'],max(bids))) if bids and max(bids)>0 else 0.0

    return {
        'platform':cur['platform'],'sell_count':cur['sell_count'] or 0,'bid_count':cur['bid_count'] or 0,
        'spread':spread,'price24':ch('sell_price',old24),'price7':ch('sell_price',old7),
        'sell24':ch('sell_count',old24),'sell7':ch('sell_count',old7),
        'bid24':ch('bid_count',old24),'bid7':ch('bid_count',old7),
        'range24':price_range,'drawdown24':drawdown,'refill24':refill,'bid_fade24':bid_fade
    }


def score_item(rows,now=None):
    if not rows: return None
    now=now or max(r['sampled_at'] for r in rows); byp=defaultdict(list)
    for r in rows: byp[r['platform']].append(r)
    f=[platform_features(v,now) for v in byp.values() if len(v)>=2]
    if not f: return None

    med=lambda key: statistics.median([x[key] for x in f])
    squeeze24=statistics.median([-x['sell24'] for x in f]); squeeze7=statistics.median([-x['sell7'] for x in f])
    bidgrow24=med('bid24'); bidgrow7=med('bid7')
    price24=med('price24'); price7=med('price7'); spread=med('spread')
    range24=med('range24'); drawdown24=med('drawdown24'); refill24=med('refill24'); bidfade24=med('bid_fade24')
    confirm24=sum(1 for x in f if x['sell24']<=-0.12 and x['bid24']>=0.20)
    confirm7=sum(1 for x in f if x['sell7']<=-0.20 and x['bid7']>=0.30)
    liquidity=sum(x['sell_count']+x['bid_count'] for x in f)

    # Control / squeeze score. A large price gain alone does not cancel evidence of concentrated capital.
    manipulation=18*norm(squeeze24,.08,.55)+14*norm(squeeze7,.12,.70)
    manipulation+=14*norm(bidgrow24,.15,1.5)+10*norm(bidgrow7,.30,3.0)
    manipulation+=12*norm(confirm24,1,4)+8*norm(confirm7,1,4)
    manipulation+=8*(1-norm(spread,.03,.25))+6*norm(math.log1p(liquidity),math.log(8),math.log(500))
    manipulation+=6*norm(max(price24,0),.02,.35)+4*norm(max(price7,0),.08,1.5)
    if liquidity<10: manipulation-=10
    manipulation=clamp(manipulation,0,100)

    # Distribution risk: violent range, sell-side refill, bid retreat, drawdown and parabolic gains.
    distribution=20*norm(range24,.12,.65)+20*norm(refill24,.10,1.0)+16*norm(bidfade24,.10,.60)
    distribution+=16*norm(drawdown24,.08,.45)+14*norm(max(price24,0),.35,1.0)+14*norm(max(price7,0),1.0,4.0)
    distribution=clamp(distribution,0,100)

    # T+7 entry score rewards control while the move is still orderly and penalizes late-stage risk.
    stability=1-norm(abs(price24),.12,.45)
    gentle_momentum=norm(price24,.01,.18)
    entry=.65*manipulation+16*stability+9*gentle_momentum+8*(1-norm(spread,.03,.25))
    entry+=5*norm(math.log1p(liquidity),math.log(8),math.log(500))-.75*distribution
    entry-=18*norm(max(price24,0),.30,.90)+22*norm(max(price7,0),.80,3.0)
    if liquidity<10: entry-=10
    entry=clamp(entry,0,100)

    if distribution>=60:
        stage='DISTRIBUTION'
    elif manipulation>=60 and price24<.25:
        stage='ACCUMULATION'
    elif manipulation>=55:
        stage='MARKUP'
    else:
        stage='WATCH'

    if entry>=70 and manipulation>=55 and distribution<40:
        action='BUY_CANDIDATE'
    elif entry>=55 and manipulation>=45 and distribution<55:
        action='WATCH_BUY_ZONE'
    elif distribution>=60 or price7>1.5:
        action='AVOID'
    else:
        action='WATCH'

    return {
        'score':round(entry,2),'entry_score':round(entry,2),'manipulation_score':round(manipulation,2),
        'distribution_risk':round(distribution,2),'stage':stage,'action':action,'platforms':len(f),
        'confirming_platforms':confirm24,'confirming_platforms_7d':confirm7,
        'median_sell_24h':round(statistics.median([x['sell24'] for x in f]),4),
        'median_sell_7d':round(statistics.median([x['sell7'] for x in f]),4),
        'median_bid_24h':round(bidgrow24,4),'median_bid_7d':round(bidgrow7,4),
        'median_price_24h':round(price24,4),'median_price_7d':round(price7,4),
        'median_spread':round(spread,4),'median_range_24h':round(range24,4),
        'median_refill_24h':round(refill24,4),'median_bid_fade_24h':round(bidfade24,4),
        'liquidity_proxy':liquidity
    }
