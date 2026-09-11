import sys, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from scoring import score_item

class TestScoring(unittest.TestCase):
    def make_rows(self, squeeze=True):
        now=1_800_000_000; rows=[]
        for platform in ['A','B','C']:
            for h in [168,72,24,6,1,0]:
                t=now-h*3600
                if squeeze:
                    sell={168:120,72:110,24:100,6:82,1:72,0:65}[h]
                    bid={168:20,72:25,24:30,6:45,1:55,0:65}[h]
                    price={168:10,72:10.2,24:10.5,6:10.8,1:11,0:11.2}[h]
                else:
                    sell=100; bid=20; price=10
                rows.append({'market_hash_name':'x','platform':platform,'sampled_at':t,'sell_price':price,'sell_count':sell,'bid_price':price*0.96,'bid_count':bid})
        return rows, now
    def test_accumulation_scores_higher(self):
        a,now=self.make_rows(True); b,_=self.make_rows(False)
        self.assertGreater(score_item(a,now)['score'], score_item(b,now)['score'])
        self.assertIn(score_item(a,now)['stage'], ('ACCUMULATION','EARLY_MARKUP'))

if __name__=='__main__': unittest.main()
