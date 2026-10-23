from datetime import datetime, timedelta
import unittest
from unittest.mock import Mock
from collector import KST, normalize, KIS, save, UPSERT, error_details


def row(hour='100000', date='20261019', volume='7'):
    return dict(stck_bsop_date=date,stck_cntg_hour=hour,stck_oprc='100',stck_hgpr='105',
                stck_lwpr='99',stck_prpr='102',cntg_vol=volume,acml_vol='999999')


class CollectorTests(unittest.TestCase):
    def test_safe_mysql_error(self):
        import pymysql
        for code in (1045,1049,2003,9999):
            result=error_details(pymysql.err.OperationalError(code,'private-password-and-host'))
            self.assertEqual(result['mysql_code'],code)
            self.assertNotIn('private-password',str(result))

    def test_closed_minutes_and_per_minute_volume(self):
        cutoff=datetime(2026,10,19,10,2,tzinfo=KST);since=cutoff-timedelta(minutes=10)
        result=normalize([row(),row('100100'),row('100200'),row(date='20261016')],'005930',cutoff,since)
        self.assertEqual(len(result),2);self.assertEqual(result[0][-1],7)
        self.assertIsNone(result[0][1].tzinfo)
        self.assertEqual(result[0][1].minute,0)

    def test_invalid_and_duplicates(self):
        cutoff=datetime(2026,10,19,10,2,tzinfo=KST);since=cutoff-timedelta(minutes=10)
        self.assertEqual(len(normalize([row(),row()],'005930',cutoff,since)),1)
        with self.assertRaises(ValueError):normalize([row(),row(volume='8')],'005930',cutoff,since)
        bad=row();bad['stck_hgpr']='90'
        with self.assertRaises(ValueError):normalize([bad],'005930',cutoff,since)

    def test_page_progress_and_merge(self):
        client=object.__new__(KIS);client.auth=Mock()
        client.http=Mock(side_effect=[dict(output2=[row('100100'),row()]),dict(output2=[row('095900')])])
        cutoff=datetime(2026,10,19,10,2,tzinfo=KST)
        out=client.minutes('005930',cutoff-timedelta(minutes=3),cutoff)
        self.assertEqual(len(out),3)
        self.assertEqual(client.http.call_args_list[1].kwargs['params']['FID_INPUT_HOUR_1'],'095900')
        client.http=Mock(return_value=dict(output2=[row('100100')]))
        with self.assertRaises(ValueError):client.minutes('005930',cutoff-timedelta(minutes=4),cutoff)

    def test_commit_rollback_and_upsert(self):
        conn=Mock();cur=Mock();conn.cursor.return_value.__enter__=Mock(return_value=cur)
        conn.cursor.return_value.__exit__=Mock(return_value=False)
        rows=[('005930',datetime(2026,10,19,10),100,105,99,102,7)]
        save(conn,rows);cur.executemany.assert_called_once_with(UPSERT,rows);conn.commit.assert_called_once()
        cur.executemany.side_effect=RuntimeError('test failure')
        with self.assertRaises(RuntimeError):save(conn,rows)
        conn.rollback.assert_called_once()
        self.assertNotIn('ai_opinions',UPSERT)


if __name__=='__main__':unittest.main()
