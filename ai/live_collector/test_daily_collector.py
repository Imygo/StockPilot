import unittest
from datetime import date
from unittest.mock import MagicMock, patch
import daily_collector as d


class DailyTests(unittest.TestCase):
    def test_period_and_chunks(self):
        lo,hi=d.period(today=date(2026,10,23))
        self.assertEqual((hi-lo).days,364)
        parts=list(d.chunks(lo,hi))
        self.assertEqual(sum((b-a).days+1 for a,b in parts),365)
        self.assertTrue(all((b-a).days<90 for a,b in parts))
        for end in ['2026-10-23','2026-10-24']:
            with self.assertRaises(ValueError): d.period(end=end,today=date(2026,10,23))

    def test_normalize(self):
        r=dict(stck_bsop_date='20261022',stck_oprc='100',stck_hgpr='110',
               stck_lwpr='90',stck_clpr='105',acml_vol='1234')
        lo=hi=date(2026,10,22)
        self.assertEqual(d.normalize([r,r],'005930',lo,hi),
                         [('005930',lo,100,110,90,105,1234)])
        with self.assertRaises(ValueError):d.normalize([r,dict(r,stck_clpr='106')],'005930',lo,hi)
        with self.assertRaises(ValueError):d.normalize([dict(r,stck_hgpr='95')],'005930',lo,hi)
        self.assertEqual(d.normalize([dict(r,stck_oprc='0',stck_hgpr='0',stck_lwpr='0',acml_vol='0')],'005930',lo,hi),[])

    def test_daily_request(self):
        with patch.dict('os.environ',{'KIS_APP_KEY':'test','KIS_APP_SECRET':'test'}):
            client=d.DailyKIS()
        client.auth=MagicMock();client.http=MagicMock(return_value={'output2':[]})
        client.daily('005930',date(2026,1,1),date(2026,3,1))
        self.assertEqual(client.tr_id,'FHKST03010100')
        self.assertEqual(client.http.call_args.kwargs['params']['FID_ORG_ADJ_PRC'],'1')

    def test_transaction(self):
        conn=MagicMock(); d.save(conn,[('row',)])
        conn.commit.assert_called_once()
        self.assertIn('ON DUPLICATE KEY UPDATE',conn.cursor.return_value.__enter__.return_value.executemany.call_args.args[0])
        conn.reset_mock()
        conn.cursor.return_value.__enter__.return_value.executemany.side_effect=RuntimeError('failure')
        with self.assertRaises(RuntimeError):d.save(conn,[('row',)])
        conn.rollback.assert_called_once();conn.commit.assert_not_called()

    def test_failure_continues(self):
        client=MagicMock();client.daily.side_effect=[RuntimeError('failure'),[]]
        with patch('builtins.print'):
            result=d.run(client,['005930','000660'],date(2026,1,1),date(2026,1,2),False)
        self.assertEqual(result,1);self.assertEqual(client.daily.call_count,2)


if __name__=='__main__': unittest.main()
