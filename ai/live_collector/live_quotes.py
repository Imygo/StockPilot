"""Selected-stock KRX live quotes; isolated from AI minute candles."""
import argparse
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import threading
import time
from urllib.request import Request,urlopen
from collector import KST,BASE,code_check,connect,error_details

TR='H0STCNT0'
DDL='''CREATE TABLE IF NOT EXISTS stock_live_quotes (
stock_code VARCHAR(15) PRIMARY KEY, trade_time DATETIME NOT NULL,
price BIGINT NOT NULL, tick_volume BIGINT NOT NULL, cumulative_volume BIGINT NOT NULL,
change_amount BIGINT NOT NULL, change_rate DOUBLE NOT NULL, received_at DATETIME(6) NOT NULL
)'''
INSERT='''INSERT INTO stock_live_quotes
(stock_code,trade_time,price,tick_volume,cumulative_volume,change_amount,change_rate,received_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'''


def load_watchlist(path):
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    codes=sorted(set(code_check(s) for s in obj['symbols']))
    if len(codes)>40:raise ValueError('At most 40 live trade subscriptions; reserve other slots')
    return codes


def parse(message,allowed,received):
    parts=message.split('|',3)
    if len(parts)!=4 or parts[0]!='0' or parts[1]!=TR:return []
    count=int(parts[2]);values=parts[3].split('^')
    if count<1 or len(values)%count:raise ValueError('Invalid WS record count')
    width=len(values)//count
    if width not in (46,47):raise ValueError('Unexpected KRX trade field count')
    result=[]
    for i in range(count):
        r=values[i*width:(i+1)*width];code=code_check(r[0])
        if code not in allowed:continue
        ts=datetime.strptime(r[33]+r[1],'%Y%m%d%H%M%S').replace(tzinfo=KST)
        # Do not relabel yesterday's cached quote as live or accept a future clock.
        if ts.date()!=received.date() or ts>received+timedelta(seconds=5):continue
        price,tick,total=int(r[2]),int(r[12]),int(r[13])
        if price<=0 or min(tick,total)<0:raise ValueError('Invalid price/volume')
        if r[3] not in ('1','2','3','4','5'):raise ValueError('Invalid change sign')
        sign=-1 if r[3] in ('4','5') else 0 if r[3]=='3' else 1
        rate=abs(float(r[5]))*sign
        if not math.isfinite(rate):raise ValueError('Invalid change rate')
        result.append((code,ts.replace(tzinfo=None),price,tick,total,abs(int(r[4]))*sign,
                       rate,received.replace(tzinfo=None)))
    return result


def order(row):return row[1],row[4]


class Latest:
    def __init__(self):self.lock=threading.Lock();self.pending={}
    def put(self,rows):
        with self.lock:
            for row in rows:
                old=self.pending.get(row[0])
                if old is None or order(row)>order(old):self.pending[row[0]]=row
    def drain(self):
        with self.lock:
            rows=list(self.pending.values());self.pending.clear();return rows


def save_quotes(conn,rows,table="stock_live_quotes"):
    if table not in ("stock_live_quotes","stock_live_quotes_paper"):
        raise ValueError("Unsupported quotes table")
    # Preserve monotonic exchange time/cumulative volume even across process restarts.
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(f'SELECT trade_time,cumulative_volume FROM {table} WHERE stock_code=%s FOR UPDATE',(r[0],))
                old=cur.fetchone()
                if old is not None and order(r)<=tuple(old):continue
                if old is None:cur.execute(INSERT.replace("stock_live_quotes",table),r)
                else:
                    cur.execute(f'''UPDATE {table} SET trade_time=%s,price=%s,tick_volume=%s,
cumulative_volume=%s,change_amount=%s,change_rate=%s,received_at=%s WHERE stock_code=%s''',(*r[1:],r[0]))
        conn.commit()
    except Exception:conn.rollback();raise


def writer(buffer,stop,write):
    while not stop.wait(.5):
        rows=buffer.drain()
        if not rows:continue
        conn=None
        try:
            if write:conn=connect();save_quotes(conn,rows)
            print(json.dumps(dict(event='quotes_saved' if write else 'quotes_preview',symbols=len(rows),
                examples=[dict(stock_code=r[0],price=r[2],trade_time=str(r[1]),received_at=str(r[7])) for r in rows[:2]])),flush=True)
        except Exception as exc:
            buffer.put(rows);print(json.dumps(error_details(exc)),flush=True);stop.wait(3)
        finally:
            if conn:conn.close()


def approval():
    key=os.getenv('KIS_APP_KEY','');secret=os.getenv('KIS_APP_SECRET','')
    if not key or not secret:raise ValueError('Set KIS_APP_KEY / KIS_APP_SECRET in .env')
    req=Request(BASE+'/oauth2/Approval',data=json.dumps(dict(grant_type='client_credentials',appkey=key,secretkey=secret)).encode(),headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=30) as response:body=json.load(response)
    except Exception:raise RuntimeError('WebSocket approval request failed') from None
    if not body.get('approval_key'):raise RuntimeError('No WebSocket approval key')
    return body['approval_key']


def subscribe(ws,key,code,action):
    ws.send(json.dumps(dict(header=dict(approval_key=key,custtype='P',tr_type=action,**{'content-type':'utf-8'}),
                            body=dict(input=dict(tr_id=TR,tr_key=code)))))
    time.sleep(.15)


def run(watchlist,write):
    import websocket
    load_watchlist(watchlist)
    buffer=Latest();stop=threading.Event();thread=threading.Thread(target=writer,args=(buffer,stop,write),daemon=True);thread.start()
    failures=0
    try:
        while True:
            ws=None
            try:
                key=approval();ws=websocket.create_connection('ws://ops.koreainvestment.com:21000',timeout=10)
                active=set();checked=0.;last_rx=time.monotonic();connected=last_rx
                print(json.dumps(dict(event='ws_connected',notice='Waiting for subscription acknowledgments/trades')),flush=True)
                while True:
                    if time.monotonic()-checked>=2:
                        try:desired=set(load_watchlist(watchlist))
                        except (ValueError,KeyError,OSError,TypeError):
                            print('Invalid watchlist; keeping previous subscriptions',flush=True);desired=active
                        for code in sorted(active-desired):subscribe(ws,key,code,'0')
                        for code in sorted(desired-active):subscribe(ws,key,code,'1')
                        active=desired;checked=time.monotonic()
                    try:message=ws.recv()
                    except websocket.WebSocketTimeoutException:
                        if time.monotonic()-last_rx>90:raise ConnectionError('No heartbeat')
                        continue
                    if not message:raise ConnectionError('Disconnected')
                    last_rx=time.monotonic()
                    if message.startswith('{'):
                        obj=json.loads(message)
                        if obj.get('header',{}).get('tr_id')=='PINGPONG':ws.pong(message.encode());continue
                        body=obj.get('body',{})
                        if body.get('rt_cd') not in (None,'0'):raise ValueError('Subscription rejected; check account/session/subscription limits')
                        print(json.dumps(dict(event='subscription_ack',stock_code=obj.get('header',{}).get('tr_key'))),flush=True)
                    else:
                        rows=parse(message,active,datetime.now(KST));buffer.put(rows)
                    if time.monotonic()-connected>60:failures=0
            except ValueError as exc:
                # Schema/subscription errors need operator attention, not an infinite retry storm.
                print(json.dumps(dict(error=str(exc))),flush=True);return 1
            except KeyboardInterrupt:return 0
            except Exception as exc:
                failures+=1
                print(json.dumps(dict(event='ws_disconnected',error=type(exc).__name__,retry=failures)),flush=True)
                if failures>=10:return 1
                time.sleep(min(30,2**failures))
            finally:
                if ws:ws.close()
    finally:
        stop.set();thread.join(timeout=35)


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'),override=False)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--watchlist',default=str(Path(__file__).with_name('watchlist.json')))
    p.add_argument('--write',action='store_true');p.add_argument('--init-db',action='store_true')
    args=p.parse_args()
    if args.init_db:
        conn=connect()
        try:
            with conn.cursor() as cur:cur.execute(DDL)
            conn.commit();print('stock_live_quotes ready; existing minute tables unchanged.')
        finally:conn.close()
        return 0
    return run(args.watchlist,args.write)


if __name__=='__main__':raise SystemExit(main())
