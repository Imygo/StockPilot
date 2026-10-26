import hashlib
import unittest
from datetime import datetime,timedelta
from unittest.mock import MagicMock,patch
import numpy as np
import pandas as pd
import snapshots as s
import predictor as p


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.cutoff=datetime(2026,10,23,11,15)
        self.conn=MagicMock()
        self.cur=self.conn.cursor.return_value.__enter__.return_value
        self.data=[('005930',self.cutoff-timedelta(minutes=1),100,101,99,100,7)]

    def test_payload_roundtrip_hash_and_corruption(self):
        blob,digest=s.encode_payload(self.data)
        self.assertEqual(s.decode_payload(blob,digest)[0][-1],7)
        with self.assertRaises(ValueError):s.decode_payload(blob,'bad')
        self.assertEqual(s.universe_hash(['b','a','a']),s.universe_hash(['a','b']))

    def test_no_snapshot_on_failed_or_expired_cycle(self):
        self.assertEqual(s.publish(self.conn,self.cutoff,['005930'],1)['reason'],'collection_failed')
        self.conn.cursor.assert_not_called()
        self.cur.fetchone.return_value=(self.cutoff+timedelta(minutes=5),)
        self.assertEqual(s.publish(self.conn,self.cutoff,['005930'])['reason'],'outside_prediction_interval')
        self.conn.commit.assert_not_called()
        self.assertFalse(any('INSERT' in c.args[0] for c in self.cur.execute.call_args_list))

    def test_publish_first_snapshot_only_and_rollback(self):
        self.cur.fetchone.return_value=(self.cutoff+timedelta(seconds=90),)
        self.cur.fetchall.return_value=self.data;self.cur.rowcount=1
        result=s.publish(self.conn,self.cutoff,['005930'])
        self.assertTrue(result['new_snapshot']);self.conn.commit.assert_called_once()
        call=self.cur.execute.call_args
        self.assertIn('INSERT IGNORE',call.args[0])
        self.assertNotIn('UPDATE',call.args[0])
        self.conn.reset_mock();self.cur.execute.side_effect=RuntimeError('failure')
        with self.assertRaises(RuntimeError):s.publish(self.conn,self.cutoff,['005930'])
        self.conn.commit.assert_not_called();self.conn.rollback.assert_called()

    def test_read_frozen_payload_without_mutable_minutes(self):
        blob,digest=s.encode_payload(self.data)
        self.cur.fetchone.return_value=(self.cutoff+timedelta(seconds=90),digest,1,1,blob)
        rows,info=s.read(self.conn,self.cutoff,['005930'])
        self.assertEqual(rows[0][-1],7);self.assertEqual(info['collection_delay_seconds'],90)
        self.assertFalse(any('minute_chart_data' in c.args[0] for c in self.cur.execute.call_args_list))
        self.cur.fetchone.return_value=None
        with self.assertRaisesRegex(ValueError,'WAIT'):s.read(self.conn,self.cutoff,['005930'])

    def test_future_minute_refused(self):
        blob,digest=s.encode_payload([('005930',self.cutoff,100,101,99,100,7)])
        self.cur.fetchone.return_value=(self.cutoff+timedelta(seconds=90),digest,1,1,blob)
        with self.assertRaisesRegex(ValueError,'out-of-range'):s.read(self.conn,self.cutoff,['005930'])

    def test_claim_never_appends_to_existing_history(self):
        self.cur.fetchone.return_value=(199,)
        self.assertFalse(s.claim_run(self.cur,self.cutoff,'hash',self.cutoff,{}))
        self.assertFalse(any('INSERT' in c.args[0] for c in self.cur.execute.call_args_list))

    def test_json_input_roundtrip_preserves_hash(self):
        import json
        x=np.linspace(-.3,.5,78,dtype=np.float32)
        reconstructed=np.array(json.loads(json.dumps(x.tolist())),dtype=np.float32)
        self.assertEqual(hashlib.sha256(x.tobytes()).hexdigest(),hashlib.sha256(reconstructed.tobytes()).hexdigest())

    def test_audit_and_predictions_atomic_expiry_and_failure(self):
        cutoff=pd.Timestamp(self.cutoff,tz='Asia/Seoul')
        self.cur.fetchone.return_value=(self.cutoff+timedelta(seconds=90),);self.cur.rowcount=1
        row=dict(stock_code='005930',direction='UP',score_up=.6,reference_close=100.,input_sha256='b'*64)
        with patch('predictor.now',return_value=cutoff+pd.Timedelta(seconds=90)),patch('snapshots.claim_run',return_value=True):
            self.assertEqual(p.persist(self.conn,[row],cutoff,'a'*64,'test',{}),1)
        self.conn.commit.assert_called_once()
        self.conn.reset_mock()
        with patch('predictor.now',return_value=cutoff+pd.Timedelta(seconds=90)),patch('snapshots.claim_run',side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):p.persist(self.conn,[row],cutoff,'a'*64,'test',{})
        self.conn.rollback.assert_called_once();self.conn.commit.assert_not_called()
        self.conn.reset_mock()
        self.cur.fetchone.side_effect=[(self.cutoff+timedelta(seconds=90),),(self.cutoff+timedelta(minutes=5),)]
        with patch('predictor.now',return_value=cutoff+pd.Timedelta(seconds=90)),patch('snapshots.claim_run',return_value=True):
            with self.assertRaisesRegex(ValueError,'Expired'):p.persist(self.conn,[row],cutoff,'a'*64,'test',{})
        self.conn.rollback.assert_called_once();self.conn.commit.assert_not_called()

    def test_cycle_wait_does_not_predict_or_read_mutable_table(self):
        model=MagicMock()
        with patch('predictor.now',return_value=pd.Timestamp(self.cutoff,tz='Asia/Seoul')+pd.Timedelta(seconds=90)),patch('predictor.connect',return_value=self.conn),patch('snapshots.read',side_effect=ValueError('WAIT: completed market snapshot absent')),patch('predictor.fetch') as fetch:
            self.cur.fetchone.return_value=(0,)
            with self.assertRaisesRegex(ValueError,'WAIT'):
                p.cycle((model,{}, {},[{'stock_code':'005930'}],'hash','version'),True,True)
        model.predict_proba.assert_not_called();fetch.assert_not_called();self.conn.commit.assert_not_called()


if __name__=='__main__':unittest.main()
