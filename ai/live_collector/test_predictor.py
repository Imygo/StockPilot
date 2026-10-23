import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from predictor import window, inputs, live_boundary, persist


def bars():
    index=pd.date_range('2026-10-23 09:10',periods=30,freq='5min',tz='Asia/Seoul')
    c=np.arange(30)+100.
    return pd.DataFrame(dict(open=c,high=c+1,low=c-1,close=c,volume=100),index=index)


class LiveTests(unittest.TestCase):
    def test_causal_window(self):
        b=bars();cutoff=b.index[24];a=window(b,cutoff,12)
        b.loc[b.index>cutoff,'close']=9999
        np.testing.assert_array_equal(a,window(b,cutoff,12))
        self.assertEqual(a.shape,(1,44))
        with self.assertRaises(ValueError):window(b.drop(index=cutoff),cutoff,12)
        with self.assertRaises(ValueError):window(b.drop(index=b.index[20]),cutoff,12)

    def test_session(self):
        t=pd.Timestamp('2026-10-23 11:02',tz='Asia/Seoul')
        self.assertEqual(live_boundary(t),t.floor('5min'))
        for t in ('2026-10-24 11:02','2026-10-23 10:59','2026-10-23 14:55'):
            with self.assertRaises(ValueError):live_boundary(pd.Timestamp(t,tz='Asia/Seoul'))

    def test_missing_market_does_not_predict(self):
        b=bars();code='005930'
        ts=pd.date_range('2026-10-23 09:05',periods=145,freq='min',tz='Asia/Seoul')
        frame=pd.DataFrame(dict(timestamp=ts,open=100,high=101,low=99,close=100,volume=10))
        frame['stock_code']=code
        symbols=[dict(stock_code=code,exchange='KOSPI'),dict(stock_code='000001',exchange='KOSDAQ')]
        with self.assertRaisesRegex(ValueError,'coverage'):
            inputs(frame,b.index[24],dict(lookback=12),{code:.5},symbols)

    def test_expired_and_duplicate(self):
        cutoff=pd.Timestamp('2026-10-23 11:00',tz='Asia/Seoul')
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value=(cutoff.tz_localize(None).to_pydatetime(),)
        cur.rowcount=0
        row=dict(stock_code='005930',direction='UP',score_up=.6,reference_close=100.,input_sha256='b'*64)
        with patch('predictor.now',return_value=cutoff+pd.Timedelta(minutes=1)):
            self.assertEqual(persist(conn,[row],cutoff,'a'*64,'test'),0)
        self.assertFalse(any('ai_opinions' in str(call) for call in cur.execute.call_args_list))
        conn.reset_mock()
        with patch('predictor.now',return_value=cutoff+pd.Timedelta(minutes=5)):
            with self.assertRaises(ValueError):persist(conn,[row],cutoff,'a'*64,'test')
        conn.cursor.assert_not_called()

    def test_new_prediction_commits_and_expiry_rolls_back(self):
        cutoff=pd.Timestamp('2026-10-23 11:00',tz='Asia/Seoul')
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value=(cutoff.tz_localize(None).to_pydatetime(),);cur.rowcount=1
        row=dict(stock_code='005930',direction='UP',score_up=.6,reference_close=100.,input_sha256='b'*64)
        with patch('predictor.now',return_value=cutoff+pd.Timedelta(minutes=1)):
            self.assertEqual(persist(conn,[row],cutoff,'a'*64,'test'),1)
        conn.commit.assert_called_once()
        self.assertTrue(any('ai_opinions' in str(call) for call in cur.execute.call_args_list))
        conn.reset_mock()
        with patch('predictor.now',side_effect=[cutoff+pd.Timedelta(minutes=1),cutoff+pd.Timedelta(minutes=5)]):
            with self.assertRaises(ValueError):persist(conn,[row],cutoff,'a'*64,'test')
        conn.rollback.assert_called_once();conn.commit.assert_not_called()


if __name__=='__main__':unittest.main()
