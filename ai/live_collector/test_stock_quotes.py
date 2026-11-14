import sqlite3
import unittest
from unittest.mock import patch
from test_register_stocks import Cursor
from stock_quotes import quote_values, save_quote, run_cycle, make_api, SERVERS

ROW = dict(stck_prpr='50000', hts_avls='3000000', acml_vol='5678',
           prdy_vrss='100', prdy_ctrt='0.2', prdy_vrss_sign='5')

class Conn:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE stock(stock_code TEXT PRIMARY KEY,stock_name TEXT,current_price INT,marketCap INT,change_amount REAL,change_rate REAL,volume INT,updated_at TEXT)')
        self.db.execute("INSERT INTO stock(stock_code,stock_name) VALUES('005930','Samsung')")
        self.db.commit()
    def cursor(self):
        class C(Cursor):
            def execute(self,sql,params=()):return super().execute(sql,params)
            def fetchall(self):return self.c.fetchall()
        return C(self.db.cursor())
    def commit(self):self.db.commit()
    def rollback(self):self.db.rollback()

class Tests(unittest.TestCase):
    def test_update_preserves_name_sign_and_cap_units(self):
        c=Conn()
        try:
            save_quote(c,'005930',ROW)
            self.assertEqual(c.db.execute('SELECT stock_name,current_price,marketCap,change_amount,change_rate,volume FROM stock').fetchone(),
                             ('Samsung',50000,3000000,-100,-.2,5678))
        finally:c.db.close()

    def test_bad_value_and_missing_stock_do_not_write(self):
        c=Conn()
        try:
            with self.assertRaises(ValueError):save_quote(c,'005930',dict(ROW,stck_prpr='NaN'))
            with self.assertRaises(RuntimeError):save_quote(c,'000660',ROW)
            self.assertIsNone(c.db.execute('SELECT current_price FROM stock').fetchone()[0])
        finally:c.db.close()

    def test_readback_failure_rolls_back(self):
        c=Conn()
        try:
            c.db.execute('CREATE TRIGGER corrupt AFTER UPDATE ON stock BEGIN UPDATE stock SET current_price=1 WHERE stock_code=NEW.stock_code; END')
            with self.assertRaises(RuntimeError):save_quote(c,'005930',ROW)
            self.assertIsNone(c.db.execute('SELECT current_price FROM stock').fetchone()[0])
        finally:c.db.close()

    def test_auth_failure_stops_before_quote_requests(self):
        c=Conn()
        try:
            from unittest.mock import Mock
            api=Mock();api.auth.side_effect=RuntimeError('auth')
            with self.assertRaises(RuntimeError):run_cycle(c,api,['005930'])
            api.auth.assert_called_once();api.http.assert_not_called()
        finally:c.db.close()

    def test_explicit_server_and_no_inherited_token(self):
        with patch('collector.KIS') as kis,patch('collector.BASE'):
            import collector
            for env in SERVERS:
                api=make_api(env)
                self.assertEqual(collector.BASE,SERVERS[env])
                self.assertEqual(api.token,'')
                self.assertEqual(api.expires,0)

if __name__=='__main__':unittest.main()

