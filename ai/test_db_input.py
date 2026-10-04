import unittest
from unittest.mock import MagicMock,patch
import pandas as pd
from db_input import boundary,fetch_minutes,run_db,QUERY


class DBInputTests(unittest.TestCase):
    def test_weekend_and_future_rejected(self):
        for asof in (None,'2026-10-05 11:00','2026-10-02 15:20','2026-10-02 11:01'):
            with self.assertRaises(ValueError):
                boundary(asof,now='2026-10-04 12:00+09:00')

    def test_query_excludes_current_minute_and_rejects_stale(self):
        cutoff=boundary('2026-10-02 11:00',now='2026-10-04 12:00+09:00')
        conn=MagicMock(); cursor=conn.cursor.return_value.__enter__.return_value
        row=dict(stock_code='005930',timestamp='2026-10-02 10:59',open=10,high=11,low=9,close=10,volume=2)
        cursor.fetchall.return_value=[row]
        frame=fetch_minutes(conn,cutoff)
        self.assertEqual(len(frame),1)
        self.assertEqual(cursor.execute.call_args.args[0],QUERY)
        self.assertEqual(cursor.execute.call_args.args[1][2].hour,11)
        cursor.fetchall.return_value=[dict(row,timestamp='2026-10-02 10:58')]
        with self.assertRaisesRegex(ValueError,'stale'):
            fetch_minutes(conn,cutoff)

    def test_invalid_source_contract_never_connects(self):
        connect=MagicMock()
        with self.assertRaisesRegex(ValueError,'per-minute'):
            run_db('db-save',connect,MagicMock(),MagicMock(),as_of='2026-10-02 11:00')
        connect.assert_not_called()

    def test_inference_failure_never_writes(self):
        connect=MagicMock(); save=MagicMock()
        with patch('db_input.fetch_minutes',return_value=pd.DataFrame()), self.assertRaises(ValueError):
            run_db('db-save',connect,MagicMock(side_effect=ValueError('gap')),save,as_of='2026-10-02 11:00',minute_ohlcv=True)
        save.assert_not_called()

    def test_successful_db_replay_writes_model_result(self):
        connect=MagicMock(); save=MagicMock(return_value={'invest_opinion':'UP'})
        predict=MagicMock(return_value={'stock_code':'005930','direction':'UP'})
        with patch('db_input.fetch_minutes',return_value=pd.DataFrame()):
            result=run_db('db-save',connect,predict,save,as_of='2026-10-02 11:00',minute_ohlcv=True)
        self.assertTrue(result['db_saved'])
        self.assertEqual(save.call_args.args[1]['mode'],'historical_db_replay')


if __name__=='__main__': unittest.main()
