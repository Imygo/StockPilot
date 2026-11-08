import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from market_universe import parse_master, MASTER
from multi_worker import normalize, combine, run_cycle, Budget, BudgetExceeded

STOCKS=[dict(stock_code='005930',stock_name='삼성전자',aspect='삼성전자',query='삼성전자',market='KOSPI'),dict(stock_code='000660',stock_name='SK하이닉스',aspect='SK하이닉스',query='SK하이닉스',market='KOSPI')]
ITEM=dict(title='삼성전자와 SK하이닉스 실적 발표',description='기업별 실적 분석',originallink='https://example.org/1',pubDate='Thu, 05 Nov 2026 09:00:00 +0900')
class Predictor:
    version='test'
    def predict(self,rows):return [dict(label='neutral',negative=.1,neutral=.8,positive=.1) for r in rows]
class Store:
    def __init__(self):self.saved=set();self.fail=False
    def acquire(self):pass
    def pending(self,rows,version):return [r for r in rows if (r['article_id'],r['stock_code'],version) not in self.saved]
    def save_verified(self,rows,preds,version):
        if self.fail:raise RuntimeError('save failed')
        self.saved.update((r['article_id'],r['stock_code'],version) for r in rows)
class NoBudget:
    def charge(self):pass
class Tests(unittest.TestCase):
    def test_market_cap_not_volume(self):
        for market,(_,width,offset) in MASTER.items():
            lines=[]
            for code,cap in [('000001',10),('000002',200),('000003',50)]:
                tail=list(' '*width);tail[:2]='ST';tail[offset:offset+9]=f'{cap:09}'
                lines.append(code.ljust(9)+'KR1234567890'+'회사'+''.join(tail))
            rows=parse_master('\n'.join(lines).encode('cp949'),market)
            self.assertEqual([r['stock_code'] for r in rows],['000002','000003','000001'])
    def test_shared_article_keeps_both_targets(self):
        rows=[normalize(ITEM,s) for s in STOCKS]
        self.assertEqual(len(combine(rows,rows)),2)
        self.assertNotEqual(rows[0]['aspect'],rows[1]['aspect'])
    def test_repeat_and_new_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store();predictor=Predictor()
            f=lambda *a,**kw:[ITEM]
            self.assertEqual(run_cycle(tmp,predictor,store,STOCKS,NoBudget(),f)['predicted_and_saved'],2)
            self.assertEqual(run_cycle(tmp,predictor,store,STOCKS,NoBudget(),f)['predicted_and_saved'],0)
            predictor.version='new'
            self.assertEqual(run_cycle(tmp,predictor,store,STOCKS,NoBudget(),f)['predicted_and_saved'],2)
    def test_failed_storage_queue_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store();store.fail=True
            with self.assertRaises(RuntimeError):run_cycle(tmp,Predictor(),store,STOCKS,NoBudget(),lambda *a,**kw:[ITEM])
            self.assertEqual(len(json.loads(Path(tmp,'pending.json').read_text(encoding='utf-8'))),2)
            store.fail=False
            result=run_cycle(tmp,Predictor(),store,STOCKS,NoBudget(),lambda *a,**kw:[])
            self.assertEqual(result['predicted_and_saved'],2)
    def test_bad_target_rejected(self):
        self.assertIsNone(normalize(dict(ITEM,title='다른회사',description='소식'),STOCKS[0]))
    def test_budget_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp,'budget.json');Budget(path,limit=1).charge()
            with self.assertRaises(BudgetExceeded):Budget(path,limit=1).charge()
    def test_all_200_stocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            stocks=[dict(STOCKS[0],stock_code=f'{i:06}') for i in range(200)]
            result=run_cycle(tmp,Predictor(),Store(),stocks,NoBudget(),lambda *a,**kw:[ITEM])
            self.assertEqual(result['predicted_and_saved'],200)
            self.assertEqual(result['fetched_stocks'],200)

if __name__=='__main__':unittest.main()
