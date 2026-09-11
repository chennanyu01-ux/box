import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from scoring import score_item


class TestScoring(unittest.TestCase):
    def make_rows(self, mode='accumulation', include_buff=True):
        now=1_800_000_000; rows=[]
        platforms=['BUFF','C5','YYYP'] if include_buff else ['A','B','C']
        for platform in platforms:
            for h in [168,72,24,6,1,0]:
                t=now-h*3600
                if mode=='accumulation':
                    sell={168:120,72:110,24:100,6:82,1:72,0:65}[h]
                    bid={168:20,72:25,24:30,6:45,1:55,0:65}[h]
                    price={168:10,72:10.2,24:10.5,6:10.8,1:11,0:11.2}[h]
                elif mode=='blowoff':
                    sell={168:120,72:100,24:75,6:42,1:66,0:72}[h]
                    bid={168:25,72:45,24:70,6:115,1:58,0:42}[h]
                    price={168:10,72:13,24:19,6:35,1:23,0:25}[h]
                else:
                    sell=100; bid=20; price=10
                rows.append({'market_hash_name':'x','platform':platform,'sampled_at':t,
                             'sell_price':price,'sell_count':sell,'bid_price':price*0.96,'bid_count':bid})
        return rows, now

    def test_accumulation_is_buyable(self):
        a,now=self.make_rows('accumulation'); flat,_=self.make_rows('flat')
        sa=score_item(a,now); sf=score_item(flat,now)
        self.assertEqual(sa['reference_platform'],'BUFF')
        self.assertTrue(sa['buff_data_available'])
        self.assertGreater(sa['manipulation_score'],sf['manipulation_score'])
        self.assertGreater(sa['entry_score'],sf['entry_score'])
        self.assertEqual(sa['stage'],'ACCUMULATION')
        self.assertEqual(sa['action'],'BUY_CANDIDATE')

    def test_blowoff_is_not_a_t7_entry(self):
        a,now=self.make_rows('accumulation'); b,_=self.make_rows('blowoff')
        sa=score_item(a,now); sb=score_item(b,now)
        self.assertGreater(sb['distribution_risk'],sa['distribution_risk'])
        self.assertLess(sb['entry_score'],sa['entry_score'])
        self.assertEqual(sb['stage'],'DISTRIBUTION')
        self.assertEqual(sb['action'],'AVOID')

    def test_no_buy_signal_without_buff(self):
        a,now=self.make_rows('accumulation',False)
        s=score_item(a,now)
        self.assertFalse(s['buff_data_available'])
        self.assertEqual(s['action'],'WATCH_NO_BUFF')
        self.assertLessEqual(s['entry_score'],49)


if __name__=='__main__': unittest.main()
