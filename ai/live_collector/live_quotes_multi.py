"""Five independently authorized paper API accounts, 40 KRX trade subscriptions each."""
import argparse
from collections import Counter
from datetime import datetime
import json
import os
import re
from pathlib import Path
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from collector import KST, code_check, connect, error_details
from live_quotes import TR, DDL, Latest, parse, save_quotes

ROOT=Path(__file__).resolve().parents[1]
PAPER_REST='https://openapivts.koreainvestment.com:29443'
PAPER_WS='ws://ops.koreainvestment.com:31000'
TABLE='stock_live_quotes_paper'


def plan(path):
    symbols=json.loads(Path(path).read_text(encoding='utf-8-sig'))['symbols']
    codes=[code_check(s['stock_code']) for s in symbols]
    counts=Counter(s['exchange'] for s in symbols)
    if len(set(codes))!=200 or len(codes)!=200 or counts!={'KOSPI':100,'KOSDAQ':100}:
        raise ValueError('Require exactly 100 unique KOSPI and 100 unique KOSDAQ stocks')
    markets={m:sorted(s['stock_code'] for s in symbols if s['exchange']==m) for m in counts}
    return [dict(slot=i+1,codes=markets['KOSPI'][i*20:(i+1)*20]+markets['KOSDAQ'][i*20:(i+1)*20]) for i in range(5)]


def credentials():
    result=[]
    for i in range(1,6):
        key=os.getenv(f'KIS_PAPER_{i}_APP_KEY','').strip()
        secret=os.getenv(f'KIS_PAPER_{i}_APP_SECRET','').strip()
        if not key or not secret:
            raise ValueError(f'Set KIS_PAPER_{i}_APP_KEY and KIS_PAPER_{i}_APP_SECRET in .env.paper')
        result.append((key,secret))
    if len({k for k,_ in result})!=5:
        raise ValueError('Five distinct app keys required; duplicating one key does not add capacity')
    return result


def safe_details(exc):
    result={'error_type':type(exc).__name__}
    for name in ('http_status','kis_code'):
        value=getattr(exc,name,None)
        if value is not None:result[name]=value
    return result


class ApprovalError(RuntimeError):
    def __init__(self,http_status=None,body=None):
        super().__init__('Paper approval failed; response withheld')
        self.http_status=http_status if isinstance(http_status,int) else None
        code=body.get('msg_cd') if isinstance(body,dict) else None
        self.kis_code=code if isinstance(code,str) and re.fullmatch(r'[A-Z]{3}[0-9]{5}',code) else None


class ApprovalGate:
    """Serialize approval requests across all workers, including reconnects."""
    def __init__(self):
        self.lock=threading.Lock();self.last=0.
        self.connection_lock=threading.Lock()

    def get(self,key,secret,stop):
        with self.lock:
            if stop.wait(max(0,1.1-(time.monotonic()-self.last))):raise InterruptedError()
            self.last=time.monotonic()
            req=Request(PAPER_REST+'/oauth2/Approval',
                data=json.dumps(dict(grant_type='client_credentials',appkey=key,secretkey=secret)).encode(),
                headers={'Content-Type':'application/json'})
            try:
                with urlopen(req,timeout=20) as response:body=json.load(response)
            except HTTPError as exc:
                try:body=json.loads(exc.read(16384))
                except Exception:body=None
                raise ApprovalError(exc.code,body) from None
            except (ValueError,TypeError):raise ApprovalError() from None
            if not isinstance(body,dict):raise ApprovalError()
            approval=body.get('approval_key')
            if not isinstance(approval,str) or not approval:raise ApprovalError(body=body)
            return approval


class Status:
    def __init__(self,slots=range(1,6)):
        self.lock=threading.Lock()
        self.accounts={i:dict(state='starting',acknowledged=set(),seen={}) for i in slots}
        self.failure=False;self.db_ok=None

    def reset(self,slot,state):
        with self.lock:self.accounts[slot]=dict(state=state,acknowledged=set(),seen={})

    def ack(self,slot,code):
        with self.lock:self.accounts[slot]['acknowledged'].add(code)

    def received(self,slot,rows):
        with self.lock:
            for r in rows:self.accounts[slot]['seen'][r[0]]=time.monotonic()

    def fatal(self,slot,reason):
        self.reset(slot,'failed')
        with self.lock:
            self.failure=True;self.accounts[slot]['state']='failed'
        emit(event='paper_ws_failed',slot=slot,reason=reason)

    def snapshot(self):
        with self.lock:
            now=time.monotonic()
            accounts=[dict(slot=i,state=a['state'],acknowledged=len(a['acknowledged']),
                symbols_seen_since_connect=len(a['seen']),
                symbols_received_last_60s=sum(now-v<=60 for v in a['seen'].values())) for i,a in self.accounts.items()]
            missing=[a['slot'] for a in accounts if a['state']!='connected' or a['acknowledged']!=40]
            return dict(event='paper_ws_status',expected_symbols=40*len(self.accounts),
                subscription_complete=not missing,missing_slots=missing,
                missing_subscription_symbols=sum(40-a['acknowledged'] for a in accounts),
                acknowledged=sum(a['acknowledged'] for a in accounts),
                db_last_write_ok=self.db_ok,accounts=accounts)


def emit(**data):print(json.dumps(data,ensure_ascii=False),flush=True)


def handle(message,ws,slot,allowed,status,buffer):
    if isinstance(message,bytes):message=message.decode('utf-8')
    if message.startswith('{'):
        obj=json.loads(message);header=obj.get('header',{});body=obj.get('body',{})
        if header.get('tr_id')=='PINGPONG':ws.pong(message.encode());return
        if body.get('rt_cd') not in (None,'0'):
            # Never print server bodies: they can echo account identifiers/keys.
            raise ValueError('Subscription rejected; verify paper eligibility and session limits')
        if header.get('tr_id')==TR and body.get('rt_cd')=='0':
            code=header.get('tr_key')
            if code not in allowed:raise ValueError('Unexpected subscription acknowledgment')
            status.ack(slot,code)
    else:
        rows=parse(message,allowed,datetime.now(KST))
        buffer.put(rows);status.received(slot,rows)


def worker(group,credential,buffer,status,stop,gate,startup_done=None):
    import websocket
    slot=group['slot'];allowed=set(group['codes']);failures=0
    while not stop.is_set():
        ws=None;stage='approval';locked=False;delay=0
        try:
            status.reset(slot,'waiting_turn')
            while not stop.is_set():
                if gate.connection_lock.acquire(timeout=.5):
                    locked=True;break
            if stop.is_set():return
            status.reset(slot,'connecting')
            approval=gate.get(*credential,stop)
            if stop.is_set():return
            stage='connect'
            ws=websocket.create_connection(PAPER_WS,timeout=5)
            status.reset(slot,'connected')
            stage='subscribe'
            for code in group['codes']:
                if stop.is_set():return
                ws.send(json.dumps(dict(header=dict(approval_key=approval,custtype='P',tr_type='1',
                    **{'content-type':'utf-8'}),body=dict(input=dict(tr_id=TR,tr_key=code)))))
                if stop.wait(.15):return
            started=last_rx=time.monotonic()
            emit(event='paper_ws_connected',slot=slot,requested=len(allowed),notice='Subscriptions not yet confirmed')
            stage='receive'
            while not stop.is_set():
                if time.monotonic()-started>60:
                    with status.lock:acks=len(status.accounts[slot]['acknowledged'])
                    if acks!=len(allowed):raise TimeoutError('Subscription acknowledgment timeout')
                    failures=0
                try:message=ws.recv()
                except websocket.WebSocketTimeoutException:
                    if time.monotonic()-last_rx>90:raise ConnectionError()
                    continue
                if not message:raise ConnectionError()
                last_rx=time.monotonic()
                handle(message,ws,slot,allowed,status,buffer)
                with status.lock:acks=len(status.accounts[slot]['acknowledged'])
                if locked and acks==len(allowed):
                    gate.connection_lock.release();locked=False
                    emit(event='paper_ws_ready',slot=slot,acknowledged=acks)
                    if startup_done is not None:startup_done.set()
        except (ValueError,KeyError,TypeError) as exc:
            emit(event='paper_ws_error',slot=slot,stage=stage,**safe_details(exc))
            status.fatal(slot,'Subscription/schema validation failed; raw response withheld')
            return
        except InterruptedError:return
        except Exception as exc:
            failures+=1;status.reset(slot,'reconnecting')
            delay=60 if failures>=10 else min(30,2**min(failures,5))
            emit(event='paper_ws_disconnected',slot=slot,retry=failures,stage=stage,
                 retry_in_seconds=delay,**safe_details(exc))
        finally:
            if ws:
                try:ws.close()
                except Exception:pass
            if locked:gate.connection_lock.release()
            if startup_done is not None:startup_done.set()
            if stop.is_set():status.reset(slot,'stopped')
        if delay and stop.wait(delay):return


def writer(buffer,stop,status,write):
    failures=0
    while not stop.wait(.5):
        rows=buffer.drain()
        if not rows:continue
        conn=None
        try:
            if write:
                conn=connect();save_quotes(conn,rows,TABLE)
                with status.lock:status.db_ok=True
            failures=0
            emit(event='paper_quotes_saved' if write else 'paper_quotes_preview',symbols=len(rows),table=TABLE)
        except Exception as exc:
            buffer.put(rows);failures+=1
            with status.lock:status.db_ok=False
            detail=error_details(exc)
            if detail.get('mysql_code') in (1146,1054):detail['hint']='Check stock_live_quotes_paper; run --init-db'
            emit(event='paper_db_error',**detail)
            if failures>=10:
                with status.lock:status.failure=True
                stop.set();return
            stop.wait(3)
        finally:
            if conn:conn.close()
    remaining=len(buffer.drain())
    if remaining:emit(event='paper_shutdown_unsaved_latest',symbols=remaining)


def run(groups,keys,write):
    stop=threading.Event();buffer=Latest();status=Status(g['slot'] for g in groups);gate=ApprovalGate()
    threads=[]
    try:
        writer_thread=threading.Thread(target=writer,args=(buffer,stop,status,write),daemon=True)
        writer_thread.start();threads.append(writer_thread)
        for g,k in zip(groups,keys):
            if stop.is_set():break
            startup_done=threading.Event()
            t=threading.Thread(target=worker,args=(g,k,buffer,status,stop,gate,startup_done),daemon=True)
            t.start();threads.append(t)
            next_report=time.monotonic()+10
            while not stop.is_set() and not startup_done.wait(1):
                if time.monotonic()>=next_report:
                    emit(**status.snapshot());next_report=time.monotonic()+10
        while not stop.wait(10):emit(**status.snapshot())
    except KeyboardInterrupt:pass
    finally:
        stop.set()
        for t in threads:t.join(timeout=25)
        for slot in status.accounts:
            if status.accounts[slot]['state']!='failed':status.reset(slot,'stopped')
    emit(**status.snapshot())
    return int(status.failure)


def select_slots(groups,keys,slots):
    selected=set(slots)
    if not selected or not selected.issubset({1,2,3,4,5}):
        raise ValueError('Select slots from 1 to 5')
    pairs=[(g,k) for g,k in zip(groups,keys) if g['slot'] in selected]
    return [g for g,k in pairs],[k for g,k in pairs]


def main():
    from dotenv import load_dotenv
    folder=Path(__file__).resolve().parent
    load_dotenv(folder/'.env',override=False) # Shared DB settings; no credential substitution.
    load_dotenv(folder/'.env.paper',override=False)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--universe',default=str(ROOT/'data/top200-20261012.json'))
    parser.add_argument('--check-plan',action='store_true',help='Offline: no credentials, API or DB required')
    parser.add_argument('--check-config',action='store_true',help='Offline: also validate five distinct app keys')
    parser.add_argument('--init-db',action='store_true')
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--slots',nargs='+',type=int,choices=range(1,6),default=list(range(1,6)),
        help='Run selected account slots for isolation testing; default all five')
    a=parser.parse_args()
    if a.init_db:
        conn=connect()
        try:
            with conn.cursor() as cur:cur.execute(DDL.replace('stock_live_quotes',TABLE))
            conn.commit();emit(event='paper_table_ready',table=TABLE)
        finally:conn.close()
        return 0
    groups=plan(a.universe)
    emit(event='paper_subscription_plan',groups=groups,markets={'KOSPI':100,'KOSDAQ':100},table=TABLE)
    if a.check_plan:return 0
    keys=credentials()
    if a.check_config:
        emit(event='paper_config_valid',distinct_app_keys=5,notice='Local validation only; account eligibility not verified')
        return 0
    groups,keys=select_slots(groups,keys,a.slots)
    emit(event='paper_active_slots',slots=[g['slot'] for g in groups],
         expected_symbols=sum(len(g['codes']) for g in groups))
    return run(groups,keys,a.write)


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        # Configuration messages contain only fixed env names, never secret values.
        if isinstance(exc,ValueError):emit(error=str(exc))
        else:emit(error=type(exc).__name__)
        raise SystemExit(1)
