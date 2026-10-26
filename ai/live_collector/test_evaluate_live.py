import unittest
from datetime import datetime,timedelta
from unittest.mock import MagicMock
import evaluate_live as e


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.t=datetime(2026,10,23,11,15)
        self.p=dict(stock_code='005930',model_sha256='model-a',candle_end=self.t,
            target_end=self.t+timedelta(minutes=5),created_at=self.t+timedelta(seconds=100),
            direction='UP',reference_close=100)
        self.minutes={self.t+timedelta(minutes=i):dict(open_price=100,high_price=110,
            low_price=90,close_price=101+i,volume=1) for i in range(5)}
        self.current=self.t+timedelta(minutes=6)

    def test_complete_close_and_no_future_bar(self):
        self.minutes[self.t+timedelta(minutes=5)]=dict(open_price=1,high_price=1,low_price=1,close_price=1,volume=0)
        r=e.assess(self.p,self.minutes,self.current)
        self.assertEqual(r['target_close'],105)
        self.assertEqual(r['actual'],'UP');self.assertTrue(r['correct'])
        self.assertEqual(r['creation_delay_seconds'],100)

    def test_pending_missing_and_invalid(self):
        self.assertEqual(e.assess(self.p,self.minutes,self.current-timedelta(seconds=1))['status'],'pending_target')
        self.minutes.pop(self.t+timedelta(minutes=2))
        self.assertEqual(e.assess(self.p,self.minutes,self.current)['status'],'missing_target_minutes')
        self.minutes[self.t+timedelta(minutes=2)]=dict(open_price=100,high_price=90,low_price=80,close_price=100,volume=1)
        self.assertEqual(e.assess(self.p,self.minutes,self.current)['status'],'invalid_target_minutes')

    def test_timing_and_horizon(self):
        for created in [self.t-timedelta(seconds=1),self.p['target_end']]:
            self.assertEqual(e.assess(dict(self.p,created_at=created),self.minutes,self.current)['status'],'invalid_prediction_timing')
        self.assertEqual(e.assess(dict(self.p,target_end=self.t+timedelta(minutes=15)),self.minutes,self.current)['status'],'invalid_prediction')

    def test_flat_down_and_denominators(self):
        up=e.assess(self.p,self.minutes,self.current)
        self.minutes[self.t+timedelta(minutes=4)]['close_price']=100
        flat=e.assess(self.p,self.minutes,self.current)
        self.assertEqual(flat['actual'],'FLAT');self.assertFalse(flat['correct'])
        self.minutes[self.t+timedelta(minutes=4)]['close_price']=99
        down=e.assess(dict(self.p,direction='DOWN'),self.minutes,self.current)
        missing=dict(up,status='missing_target_minutes')
        m=e.metrics([up,flat,down,missing])
        self.assertEqual(m['all_outcomes_accuracy'],2/3)
        self.assertEqual(m['nonzero_accuracy'],1)
        self.assertEqual(m['evaluated'],3)
        self.assertIsNone(e.metrics([])['all_outcomes_accuracy'])
        self.assertIsNone(e.metrics([flat])['nonzero_accuracy'])

    def test_models_and_rerun(self):
        a=e.assess(self.p,self.minutes,self.current)
        b=dict(a,model_sha256='model-b')
        report=e.report([a,b])
        self.assertEqual(len(report['models']),2)
        self.assertEqual(report,e.report([a,b]))
        self.assertEqual(report['models']['model-a']['by_creation_delay']['60_to_180s']['recorded'],1)

    def test_database_read_only(self):
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value={'current_kst':self.current}
        cur.fetchall.side_effect=[[self.p],[dict(v,stock_code='005930',candle_start=k) for k,v in self.minutes.items()]]
        rows=e.fetch_day(conn,self.t.date(),60)
        self.assertEqual(rows[0]['actual'],'UP')
        self.assertTrue(all(c.args[0].lstrip().startswith('SELECT') for c in cur.execute.call_args_list))
        conn.commit.assert_not_called();conn.rollback.assert_called_once()


if __name__=='__main__':unittest.main()
