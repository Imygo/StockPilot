import json
import tempfile
import unittest
from pathlib import Path
from shared_universe import load_universe
from multi_worker import normalize, run_cycle
from test_multistock import STOCKS, ITEM, Predictor, Store, NoBudget

class SharedUniverseTests(unittest.TestCase):
    def symbols(self):
        return [dict(stock_code=f'{i:06}', name=f'회사{i}', exchange='KOSPI' if i < 100 else 'KOSDAQ') for i in range(200)]

    def load(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'universe.json'
            path.write_text(json.dumps(dict(symbols=rows)),encoding='utf-8')
            return load_universe(path)

    def test_preserves_exact_members_and_preferred_share_codes(self):
        rows=self.symbols()
        rows[0]['name']='삼성전자';rows[1]['name']='삼성전자우'
        result=self.load(rows)['stocks']
        self.assertEqual([(r['stock_code'],r['stock_name'],r['market']) for r in result],
                         [(r['stock_code'],r['name'],r['exchange']) for r in rows])
        self.assertEqual(result[1]['aspect'],'삼성전자')
        self.assertNotEqual(result[0]['stock_code'],result[1]['stock_code'])

    def test_invalid_lists_fail_closed(self):
        for kind in ('missing','duplicate','market','name'):
            rows=self.symbols()
            if kind=='missing':rows.pop()
            if kind=='duplicate':rows[1]['stock_code']=rows[0]['stock_code']
            if kind=='market':rows[0]['exchange']='KOSDAQ'
            if kind=='name':rows[0]['name']=' '
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.load(rows)
        with self.assertRaises(FileNotFoundError):load_universe('no-such-universe-file.json')

    def test_excluded_pending_is_not_saved_and_can_rejoin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            path.joinpath('pending.json').write_text(json.dumps([normalize(ITEM,s) for s in STOCKS]),encoding='utf-8')
            store=Store()
            fetcher=lambda *args,**kwargs:[]
            first=run_cycle(path,Predictor(),store,STOCKS[:1],NoBudget(),fetcher)
            self.assertEqual(first['predicted_and_saved'],1)
            self.assertEqual(first['excluded_pending'],1)
            self.assertEqual({r[1] for r in store.saved},{STOCKS[0]['stock_code']})
            second=run_cycle(path,Predictor(),store,STOCKS,NoBudget(),fetcher)
            self.assertEqual(second['predicted_and_saved'],1)
            self.assertEqual(second['excluded_pending'],0)
            self.assertEqual(len(store.saved),2)

if __name__=='__main__':unittest.main()
