import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from register_stocks import load_symbols,register

class Cursor:
    def __init__(self,cursor):self.c=cursor
    def __enter__(self):return self
    def __exit__(self,*args):self.c.close()
    def execute(self,sql,params):return self.c.execute(sql.replace('%s','?'),params)
    @property
    def rowcount(self):return self.c.rowcount
    def fetchone(self):return self.c.fetchone()
class Connection:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE stock(stock_code TEXT PRIMARY KEY,stock_name TEXT,market TEXT,current_price INTEGER)')
    def cursor(self):return Cursor(self.db.cursor())
    def commit(self):self.db.commit()
    def rollback(self):self.db.rollback()
class Tests(unittest.TestCase):
    def test_missing_insert_repeat_and_existing_preserved(self):
        c=Connection()
        c.db.execute("INSERT INTO stock VALUES ('005930','기존 이름','KOSPI',67890)");c.commit()
        rows=[('005930','삼성전자','KOSPI'),('000660','SK하이닉스','KOSPI')]
        first=register(c,rows);second=register(c,rows)
        self.assertEqual(first['inserted'],1);self.assertEqual(second['inserted'],0)
        self.assertEqual(c.db.execute("SELECT stock_name,current_price FROM stock WHERE stock_code='005930'").fetchone(),('기존 이름',67890))
        self.assertIsNone(c.db.execute("SELECT current_price FROM stock WHERE stock_code='000660'").fetchone()[0])
        c.db.close()
    def test_failure_rolls_back_batch(self):
        c=Connection()
        c.db.execute("CREATE TRIGGER reject_test BEFORE INSERT ON stock WHEN new.stock_code='000002' BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):register(c,[('000001','첫째','KOSPI'),('000002','둘째','KOSPI')])
        self.assertEqual(c.db.execute('SELECT COUNT(*) FROM stock').fetchone()[0],0);c.db.close()
    def test_universe_validation(self):
        rows=[dict(stock_code=f'{i:06}',name=f'종목{i}',exchange='KOSPI' if i<100 else 'KOSDAQ') for i in range(200)]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'universe.json'
            p.write_text(json.dumps(dict(symbols=rows)),encoding='utf-8')
            self.assertEqual(len(load_symbols(p)[0]),200)
            rows[1]['stock_code']=rows[0]['stock_code']
            p.write_text(json.dumps(dict(symbols=rows)),encoding='utf-8')
            with self.assertRaises(ValueError):load_symbols(p)
if __name__=='__main__':unittest.main()

