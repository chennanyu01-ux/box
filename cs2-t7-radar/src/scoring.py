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

def platform_features(rows,now):
    rows=sorted(rows,key=lambda r:r['sampled_at']); cur=rows[-1]
    old24=nearest(rows,now-86400); old7=nearest(rows,now-604800)
    def ch(field,old): return pct(cur[field],old[field]) if old else 0.0
    spread=1.0
    if cur['sell_price'] and cur['bid_price'] and cur['sell_price']>0:
        spread=(cur['sell_price']-cur['bid_price'])/cur['sell_price']
    return {'platform':cur['platform'],'sell_count':cur['sell_count'] or 0,'bid_count':cur['bid_count'] or 0,'spread':spread,
            'price24':ch('sell_price',old24),'price7':ch('sell_price',old7),'sell24':ch('sell_count',old24),'bid24':ch('bid_count',old24)}

def score_item(rows,now=None):
    if not rows: return None
    now=now or max(r['sampled_at'] for r in rows); byp=defaultdict(list)
    for r in rows: byp[r['platform']].append(r)
    f=[platform_features(v,now) for v in byp.values() if len(v)>=2]
    if not f: return None
    squeeze=statistics.median([-x['sell24'] for x in f]); bidgrow=statistics.median([x['bid24'] for x in f])
    price24=statistics.median([x['price24'] for x in f]); price7=statistics.median([x['price7'] for x in f])
    spread=statistics.median([x['spread'] for x in f]); confirm=sum(1 for x in f if x['sell24']<=-0.12 and x['bid24']>=0.20)
    liquidity=sum(x['sell_count']+x['bid_count'] for x in f)
    score=24*norm(squeeze,.08,.55)+20*norm(bidgrow,.15,1.5)+14*norm(confirm,1,4)+10*(1-norm(spread,.03,.25))
    score+=8*norm(math.log1p(liquidity),math.log(8),math.log(500))+14*(1-norm(abs(price24),.08,.35))+10*norm(price24,.02,.22)
    if price24>.30: score-=18*norm(price24,.30,.90)
    if price7>.80: score-=25*norm(price7,.80,3.0)
    if liquidity<10: score-=10
    score=clamp(score,0,100)
    stage='ACCUMULATION' if score>=72 and price24<.25 else 'EARLY_MARKUP' if score>=65 and price24<.45 else 'CHASE_RISK' if price24>.45 or price7>1 else 'WATCH'
    return {'score':round(score,2),'stage':stage,'platforms':len(f),'confirming_platforms':confirm,'median_sell_24h':round(statistics.median([x['sell24'] for x in f]),4),'median_bid_24h':round(bidgrow,4),'median_price_24h':round(price24,4),'median_price_7d':round(price7,4),'median_spread':round(spread,4),'liquidity_proxy':liquidity}
