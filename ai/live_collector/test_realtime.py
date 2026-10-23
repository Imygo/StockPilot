from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
from collector import KST,ai_cutoff
from live_quotes import parse,Latest,save_quotes,load_watchlist


def packet(code='005930',hour='110001',volume=100,price=1000):
    r=['0']*47;r[0]=code;r[1]=hour;r[2]=str(price);r[3]='5';r[4]='10';r[5]='1.0'
    r[12]='2';r[13]=str(volume);r[33]='20261023'
    return '^'.join(r)


class RealtimeTests(unittest.TestCase):
    def test_multiple_records_and_sign(self):
        msg='0|H0STCNT0|002|'+packet()+'^'+packet('000660')
        rows=parse(msg,{'005930','000660'},datetime(2026,10,23,11,0,2,tzinfo=KST))
        self.assertEqual(len(rows),2);self.assertEqual(rows[0][5],-10);self.assertEqual(rows[0][6],-1.)
        self.assertEqual(rows[0][3:5],(2,100))

    def test_invalid_and_wrong_day(self):
        msg='0|H0STCNT0|001|'+packet()
        self.assertEqual(parse(msg,{'005930'},datetime(2026,10,24,11,tzinfo=KST)),[])
        self.assertEqual(parse(msg,{'000660'},datetime(2026,10,23,11,1,tzinfo=KST)),[])
        with self.assertRaises(ValueError):parse('0|H0STCNT0|002|x',set(),datetime.now(KST))

    def test_buffer_and_database_order(self):
        t=datetime(2026,10,23,11,1,tzinfo=KST)
        old=parse('0|H0STCNT0|001|'+packet(volume=100),{'005930'},t)[0]
        new=parse('0|H0STCNT0|001|'+packet(volume=110),{'005930'},t)[0]
        buffer=Latest();buffer.put([new,old]);self.assertEqual(buffer.drain(),[new]);self.assertEqual(buffer.drain(),[])
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value=(new[1],new[4]);save_quotes(conn,[old])
        self.assertEqual(cur.execute.call_count,1);conn.commit.assert_called_once()
        conn.reset_mock();cur.fetchone.return_value=None;save_quotes(conn,[new])
        self.assertTrue(any('INSERT INTO stock_live_quotes' in str(call) for call in cur.execute.call_args_list))
        conn.reset_mock();cur.execute.side_effect=RuntimeError('failure')
        with self.assertRaises(RuntimeError):save_quotes(conn,[new])
        conn.rollback.assert_called_once();conn.commit.assert_not_called()

    def test_limits_and_cadence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'watch.json';p.write_text(json.dumps(dict(symbols=['005930','005930'])))
            self.assertEqual(load_watchlist(p),['005930'])
            p.write_text(json.dumps(dict(symbols=[f'{i:06d}' for i in range(41)])))
            with self.assertRaises(ValueError):load_watchlist(p)
        t=datetime(2026,10,23,11,0,59,tzinfo=KST)
        self.assertEqual(ai_cutoff(t,1).strftime('%H:%M'),'10:55')
        self.assertEqual(ai_cutoff(t.replace(minute=1,second=0),1).strftime('%H:%M'),'11:00')


if __name__=='__main__':unittest.main()
