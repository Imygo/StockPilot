import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
import live_quotes_multi as m
from live_quotes import save_quotes,Latest


class MultiTests(unittest.TestCase):
    def test_retry_beyond_ten_preserves_other_account(self):
        import threading
        stop=threading.Event();status=m.Status([1,2]);status.reset(1,'connected')
        for i in range(40):status.ack(1,str(i))
        gate=m.ApprovalGate();gate.get=MagicMock(side_effect=ConnectionError('SECRET'))
        waits=[]
        def wait(seconds):
            waits.append(seconds)
            if len(waits)==11:stop.set()
            return stop.is_set()
        with patch.object(stop,'wait',side_effect=wait),patch.object(m,'emit'):
            m.worker({'slot':2,'codes':['005930']},('key','secret'),Latest(),status,stop,gate)
        self.assertEqual(gate.get.call_count,11)
        self.assertEqual(waits[-2:],[60,60])
        report=status.snapshot()
        self.assertEqual(report['acknowledged'],40)
        self.assertEqual(report['missing_slots'],[2])
        self.assertEqual(report['missing_subscription_symbols'],40)
        self.assertFalse(report['subscription_complete'])
        self.assertFalse(status.failure)
        self.assertFalse(gate.connection_lock.locked())

    def test_connection_gate_held_until_all_acknowledged(self):
        import threading
        stop=threading.Event();done=threading.Event();gate=m.ApprovalGate()
        gate.get=MagicMock(return_value='PRIVATE');status=m.Status([3]);ws=MagicMock()
        codes=[f'{i:06d}' for i in range(40)];count=0
        def recv():
            nonlocal count
            if count==40:
                self.assertFalse(gate.connection_lock.locked())
                self.assertTrue(done.is_set())
                stop.set();return ''
            self.assertTrue(gate.connection_lock.locked())
            self.assertFalse(done.is_set())
            code=codes[count];count+=1
            return json.dumps({'header':{'tr_id':m.TR,'tr_key':code},'body':{'rt_cd':'0'}})
        ws.recv.side_effect=recv
        with patch('websocket.create_connection',return_value=ws),patch.object(stop,'wait',side_effect=lambda s: stop.is_set()),patch.object(m,'emit') as output:
            m.worker({'slot':3,'codes':codes},('k','s'),Latest(),status,stop,gate,done)
        self.assertEqual(count,40)
        self.assertTrue(any(c.kwargs.get('event')=='paper_ws_ready' for c in output.call_args_list))
        ws.close.assert_called_once()

    def test_isolated_slot_preserves_credential_mapping_and_status(self):
        groups=[{'slot':i,'codes':[]} for i in range(1,6)]
        keys=[('key'+str(i),'secret'+str(i)) for i in range(1,6)]
        chosen,credentials=m.select_slots(groups,keys,[3])
        self.assertEqual(chosen,[groups[2]])
        self.assertEqual(credentials,[keys[2]])
        status=m.Status(g['slot'] for g in chosen)
        status.ack(3,'005930')
        report=status.snapshot()
        self.assertEqual(report['expected_symbols'],40)
        self.assertEqual(report['acknowledged'],1)
        self.assertEqual([a['slot'] for a in report['accounts']],[3])
        self.assertEqual(m.select_slots(groups,keys,[5,1,1]),([groups[0],groups[4]],[keys[0],keys[4]]))
        with self.assertRaises(ValueError):m.select_slots(groups,keys,[6])

    def test_approval_http_error_is_redacted(self):
        import io
        import threading
        from urllib.error import HTTPError
        error=HTTPError('https://example.test',403,'SECRET',{},io.BytesIO(
            b'{"msg_cd":"EGW00123","msg1":"SECRET","appkey":"SECRET"}'))
        with patch.object(m,'urlopen',side_effect=error):
            with self.assertRaises(m.ApprovalError) as caught:
                m.ApprovalGate().get('PRIVATE_KEY','PRIVATE_SECRET',threading.Event())
        self.assertEqual(m.safe_details(caught.exception),
            {'error_type':'ApprovalError','http_status':403,'kis_code':'EGW00123'})
        self.assertNotIn('SECRET',str(caught.exception))
        self.assertNotIn('kis_code',m.safe_details(m.ApprovalError(body={'msg_cd':'PRIVATE_KEY'})))

    def test_retry_reports_approval_stage_without_secret(self):
        import threading
        stop=threading.Event();gate=MagicMock()
        gate.get.side_effect=m.ApprovalError(403,{'msg_cd':'EGW00123','msg1':'SECRET'})
        def end_after_retry(seconds):
            stop.set();return True
        with patch.object(stop,'wait',side_effect=end_after_retry),patch.object(m,'emit') as output:
            m.worker({'slot':2,'codes':['005930']},('SECRET','SECRET'),Latest(),m.Status(),stop,gate)
        event=output.call_args.kwargs
        self.assertEqual(event['stage'],'approval')
        self.assertEqual(event['slot'],2)
        self.assertEqual(event['http_status'],403)
        self.assertNotIn('SECRET',str(output.call_args_list))

    def test_partition_exact_and_invalid(self):
        syms=[dict(stock_code=f'{i:06d}',exchange='KOSPI' if i<100 else 'KOSDAQ') for i in range(200)]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'u.json';p.write_text(json.dumps({'symbols':syms}))
            groups=m.plan(p)
            self.assertEqual([len(g['codes']) for g in groups],[40]*5)
            self.assertEqual(len(set(c for g in groups for c in g['codes'])),200)
            for g in groups:self.assertEqual(sum(int(c)<100 for c in g['codes']),20)
            syms[-1]=syms[0];p.write_text(json.dumps({'symbols':syms}))
            with self.assertRaises(ValueError):m.plan(p)

    def test_credentials_not_defaulted_and_duplicate_refused(self):
        env={f'KIS_PAPER_{i}_{name}':f'test_{name}_{i}' for i in range(1,6) for name in ('APP_KEY','APP_SECRET')}
        with patch.dict(os.environ,env,clear=True):self.assertEqual(len(m.credentials()),5)
        env['KIS_PAPER_5_APP_KEY']=env['KIS_PAPER_1_APP_KEY']
        with patch.dict(os.environ,env,clear=True):
            with self.assertRaisesRegex(ValueError,'distinct'):m.credentials()
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'KIS_PAPER_1'):m.credentials()

    def test_acknowledgments_and_heartbeat(self):
        status=m.Status();buffer=Latest();ws=MagicMock()
        ack=json.dumps({'header':{'tr_id':m.TR,'tr_key':'005930'},'body':{'rt_cd':'0'}})
        m.handle(ack,ws,1,{'005930'},status,buffer)
        m.handle(ack,ws,1,{'005930'},status,buffer)
        self.assertEqual(status.snapshot()['acknowledged'],1)
        m.handle(json.dumps({'header':{'tr_id':'PINGPONG'}}),ws,1,{'005930'},status,buffer)
        ws.pong.assert_called_once()
        rejected=json.dumps({'header':{'tr_id':m.TR},'body':{'rt_cd':'1','msg1':'SECRET'}})
        with self.assertRaises(ValueError) as err:m.handle(rejected,ws,1,{'005930'},status,buffer)
        self.assertNotIn('SECRET',str(err.exception))
        status.reset(1,'reconnecting');self.assertEqual(status.snapshot()['acknowledged'],0)

    def test_paper_db_isolation_and_table_whitelist(self):
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value=None
        row=('005930','2026-10-26 11:00:00',100,1,10,0,0,'2026-10-26 11:00:01')
        save_quotes(conn,[row],m.TABLE)
        for call in cur.execute.call_args_list:self.assertIn('stock_live_quotes_paper',call.args[0])
        conn.commit.assert_called_once()
        with self.assertRaises(ValueError):save_quotes(conn,[row],'arbitrary_table')

    def test_worker_rejection_stops_group_without_raw_error(self):
        import threading
        group={'slot':1,'codes':[f'{i:06d}' for i in range(40)]}
        ws=MagicMock();ws.recv.return_value=json.dumps({'body':{'rt_cd':'1','msg1':'secret_value'}})
        stop=threading.Event();status=m.Status();gate=MagicMock();gate.get.return_value='private_approval'
        # Avoid subscription spacing in this isolated mocked network test.
        original_wait=stop.wait
        with patch('websocket.create_connection',return_value=ws),patch.object(stop,'wait',side_effect=lambda seconds: original_wait(0)),patch('builtins.print') as output:
            m.worker(group,('key','secret'),Latest(),status,stop,gate)
        self.assertFalse(stop.is_set());self.assertTrue(status.failure)
        self.assertEqual(status.snapshot()['accounts'][0]['state'],'failed')
        self.assertEqual(ws.send.call_count,40);ws.close.assert_called_once()
        self.assertNotIn('secret_value',str(output.call_args_list))
        self.assertNotIn('private_approval',str(output.call_args_list))

    def test_status_separates_recent_trades_from_subscriptions(self):
        status=m.Status();status.ack(1,'005930');status.received(1,[('005930',)])
        with patch('live_quotes_multi.time.monotonic',return_value=0):
            status.accounts[1]['seen']['005930']=-100
            row=status.snapshot()['accounts'][0]
        self.assertEqual(row['acknowledged'],1)
        self.assertEqual(row['symbols_seen_since_connect'],1)
        self.assertEqual(row['symbols_received_last_60s'],0)


if __name__=='__main__':unittest.main()
