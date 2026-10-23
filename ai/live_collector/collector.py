"""KRX completed minute OHLCV -> existing StockPilot MySQL table.

Default dry run. No orders, DDL, predictions or stock-master writes.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from http.client import RemoteDisconnected, IncompleteRead

KST = timezone(timedelta(hours=9))
BASE = 'https://openapi.koreainvestment.com:9443'
API = '/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice'
TR = 'FHKST03010200'
UPSERT = '''INSERT INTO minute_chart_data
(stock_code,candle_start,open_price,high_price,low_price,close_price,volume)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price),
low_price=VALUES(low_price),close_price=VALUES(close_price),volume=VALUES(volume),updated_at=CURRENT_TIMESTAMP'''


def now_kst():
    return datetime.now(KST)


def code_check(value):
    if not re.fullmatch(r'[0-9A-Z]{6}', value):
        raise ValueError('Expected six-character stock code')
    return value


def stamp(row):
    return datetime.strptime(str(row['stck_bsop_date'])+str(row['stck_cntg_hour']).zfill(6),
                             '%Y%m%d%H%M%S').replace(tzinfo=KST, second=0)


def normalize(page, code, cutoff, since):
    """Minute start in KST. Strictly before cutoff; only regular-session OHLCV."""
    rows = {}
    for r in page:
        t = stamp(r)
        if t.date() != cutoff.date() or not since <= t < cutoff:
            continue
        if not '0900' <= t.strftime('%H%M') < '1530':
            continue
        vals = [int(r[k]) for k in ('stck_oprc','stck_hgpr','stck_lwpr','stck_prpr','cntg_vol')]
        o,h,l,c,v = vals
        if min(o,h,l,c) <= 0 or v < 0 or not l <= min(o,c) <= max(o,c) <= h:
            raise ValueError('Invalid minute OHLCV; refusing this symbol batch')
        value = (code,t.replace(tzinfo=None),*vals)
        if t in rows and rows[t] != value:
            raise ValueError('Conflicting duplicate minute')
        rows[t] = value
    return [rows[k] for k in sorted(rows)]


class KIS:
    def __init__(self, delay=.6):
        self.key = os.getenv('KIS_APP_KEY',''); self.secret = os.getenv('KIS_APP_SECRET','')
        if not self.key or not self.secret: raise ValueError('Set KIS_APP_KEY and KIS_APP_SECRET')
        self.token = os.getenv('KIS_ACCESS_TOKEN',''); self.expires = time.monotonic()+3600 if self.token else 0
        self.delay = delay; self.last = 0.

    def http(self, path, params=None, payload=None):
        for attempt in range(4):
            time.sleep(max(0., self.delay-(time.monotonic()-self.last)))
            self.last = time.monotonic()
            headers={'Content-Type':'application/json; charset=utf-8'}
            if params is not None:
                headers.update(authorization='Bearer '+self.token,appkey=self.key,appsecret=self.secret,tr_id=TR,custtype='P')
            req=Request(BASE+path+('?' + urlencode(params) if params else ''),
                        data=json.dumps(payload).encode() if payload else None,headers=headers)
            try:
                with urlopen(req,timeout=30) as response: body=json.load(response)
                if params is not None and str(body.get('rt_cd')) != '0':
                    error=str(body.get('msg_cd','UNKNOWN'))
                    if error=='EGW00201' and attempt<3:
                        self.delay=min(2.,max(.6,self.delay*2))
                        time.sleep(2**attempt);continue
                    if error in ('EGW00123','EGW00121'):
                        self.expires=0
                    safe=error if re.fullmatch('[A-Za-z0-9_-]{1,32}',error) else 'UNKNOWN'
                    raise RuntimeError('KIS rejected quote: '+safe)
                return body
            except HTTPError as exc:
                if exc.code==429:self.delay=min(2.,max(.6,self.delay*2))
                if exc.code==401: self.expires=0
                if payload or exc.code not in (429,500,502,503,504) or attempt==3:
                    raise RuntimeError(f'KIS HTTP {exc.code}') from None
            except (URLError,TimeoutError,ConnectionError,RemoteDisconnected,IncompleteRead):
                if payload or attempt==3: raise RuntimeError('KIS connection failed') from None
            time.sleep(2**attempt)
        raise RuntimeError('KIS retries exhausted')

    def auth(self):
        if time.monotonic()<self.expires:return
        body=self.http('/oauth2/tokenP',payload=dict(grant_type='client_credentials',appkey=self.key,appsecret=self.secret))
        self.token=body.get('access_token','')
        if not self.token:raise RuntimeError('KIS token issuance failed')
        self.expires=time.monotonic()+max(1,int(body.get('expires_in',86400))-300)

    def minutes(self,code,since,cutoff):
        self.auth()
        # Never request a future time. Refetch the latest minutes on every sweep.
        cursor=cutoff-timedelta(minutes=1); result={}
        for _ in range(40):
            body=self.http(API,params=dict(FID_COND_MRKT_DIV_CODE='J',FID_INPUT_ISCD=code,
                FID_INPUT_HOUR_1=cursor.strftime('%H%M%S'),FID_PW_DATA_INCU_YN='Y',FID_ETC_CLS_CODE=''))
            page=body.get('output2')
            if not isinstance(page,list):raise ValueError('KIS output2 is not an array')
            if not page:break
            for row in normalize(page,code,cutoff,since):
                if row[1] in result and result[row[1]]!=row:raise ValueError('Conflicting pages')
                result[row[1]]=row
            oldest=min(stamp(r) for r in page)
            if oldest<=since:break
            new=oldest-timedelta(minutes=1)
            if new>=cursor:raise ValueError('KIS pagination made no progress')
            cursor=new
        else:raise ValueError('KIS pagination limit exceeded')
        return [result[k] for k in sorted(result)]


def connect():
    import pymysql
    return pymysql.connect(host=os.getenv('STOCKPILOT_DB_HOST','127.0.0.1'),
        port=int(os.getenv('STOCKPILOT_DB_PORT','3306')),user=os.getenv('STOCKPILOT_DB_USER','root'),
        password=os.getenv('STOCKPILOT_DB_PASSWORD',''),database=os.getenv('STOCKPILOT_DB_NAME','stockpilot_db'),
        charset='utf8mb4',autocommit=False,connect_timeout=10,read_timeout=30,write_timeout=30)


def error_details(exc):
    """Expose numeric DB codes, never raw database messages or credentials."""
    import pymysql
    if isinstance(exc,pymysql.MySQLError):
        code=exc.args[0] if exc.args and isinstance(exc.args[0],int) else None
        hints={
            1045:'Check STOCKPILOT_DB_USER/PASSWORD and MySQL account host permissions.',
            1044:'DB account lacks access to STOCKPILOT_DB_NAME.',
            1049:'Database does not exist; check STOCKPILOT_DB_NAME and import the project schema if needed.',
            1146:'minute_chart_data table is missing; check database/schema.',
            1054:'Column mismatch; check minute_chart_data schema.',
            1142:'DB account lacks required SELECT/INSERT/UPDATE permissions.',
            2003:'Cannot connect; check MySQL service, DB host and port.',
            2006:'MySQL connection lost; check server availability.',
            2013:'MySQL query connection lost or timed out.',
            1205:'DB lock timeout; check other writers.',
            1213:'DB deadlock; retry and check other writers.'}
        return dict(error=type(exc).__name__,mysql_code=code,
                    hint=hints.get(code,'Check MySQL server and DB configuration; raw error message withheld.'))
    return dict(error=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__)


def check_db():
    conn=None
    try:
        conn=connect();inspect_schema(conn)
        print(json.dumps(dict(db_connected=True,minute_schema_valid=True,writes=False)),flush=True)
        return 0
    except Exception as exc:
        print(json.dumps(error_details(exc)),flush=True);return 1
    finally:
        if conn:conn.close()


def save(connection,rows):
    try:
        with connection.cursor() as cur:
            if rows:cur.executemany(UPSERT,rows)
        connection.commit()
    except Exception:
        connection.rollback();raise


def inspect_schema(connection):
    with connection.cursor() as cur:
        cur.execute('SHOW COLUMNS FROM minute_chart_data'); cols={r[0] for r in cur.fetchall()}
        if not {'stock_code','candle_start','open_price','high_price','low_price','close_price','volume','updated_at'}<=cols:
            raise ValueError('minute_chart_data schema mismatch')
        cur.execute('SHOW INDEX FROM minute_chart_data'); indexes=cur.fetchall()
        unique={}
        for r in indexes:
            if r[1]==0:unique.setdefault(r[2],[]).append((r[3],r[4]))
        if not any([c for _,c in sorted(v)]==['stock_code','candle_start'] for v in unique.values()):
            raise ValueError('Require unique key (stock_code,candle_start)')
    connection.rollback()


def ai_cutoff(current, lag):
    value=current.replace(second=0,microsecond=0)-timedelta(minutes=lag)
    return value.replace(minute=(value.minute//5)*5)


def sweep(client,codes,write,backfill,lag,fixed_cutoff=None):
    failures=0
    for code in codes:
        conn=None
        try:
            current=now_kst();cutoff=fixed_cutoff or current.replace(second=0,microsecond=0)-timedelta(minutes=lag)
            start=current.replace(hour=9,minute=0,second=0,microsecond=0)
            if cutoff<=start:continue
            since=start if backfill else max(start,cutoff-timedelta(minutes=10))
            if write:
                conn=connect();inspect_schema(conn)
                if not backfill:
                    with conn.cursor() as cur:
                        cur.execute('SELECT MAX(candle_start) FROM minute_chart_data WHERE stock_code=%s AND candle_start >= %s AND candle_start < %s',
                                    (code,start.replace(tzinfo=None),cutoff.replace(tzinfo=None)))
                        latest=cur.fetchone()[0]
                    conn.rollback()
                    since=max(start,latest.replace(tzinfo=KST)-timedelta(minutes=3)) if latest else start
            rows=client.minutes(code,since,cutoff)
            if write:save(conn,rows)
            print(json.dumps(dict(stock_code=code,mode='saved' if write else 'dry_run',rows=len(rows),
                first=str(rows[0][1]) if rows else None,last=str(rows[-1][1]) if rows else None,
                cutoff=str(cutoff)),ensure_ascii=False),flush=True)
        except Exception as exc:
            failures+=1
            # Never print connection strings, credentials or raw API error bodies.
            print(json.dumps(dict(stock_code=code,**error_details(exc))),flush=True)
        finally:
            if conn:conn.close()
    return failures


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'),override=False)
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group()
    group.add_argument('--symbols',default=None,help='Comma-separated codes; default 005930')
    group.add_argument('--universe',help='Existing JSON with symbols[].stock_code')
    p.add_argument('--write',action='store_true');p.add_argument('--loop',action='store_true')
    p.add_argument('--check-db',action='store_true',help='Read-only DB connection/schema check; no KIS requests')
    p.add_argument('--backfill-today',action='store_true');p.add_argument('--interval',type=int,default=60)
    p.add_argument('--request-delay',type=float,default=.6);p.add_argument('--lag-minutes',type=int,default=1)
    p.add_argument('--ai-cycle',action='store_true',help='Collect one common completed 5m boundary per cycle; no extra 60s sleep')
    p.add_argument('--confirmed-fast-rest',action='store_true',help='Explicitly confirm your account permits >2 requests/sec before lowering request-delay')
    args=p.parse_args()
    if args.check_db:return check_db()
    minimum=.1 if args.confirmed_fast_rest else .5
    if args.interval<10 or args.request_delay<minimum or args.lag_minutes<1: p.error(f'Require interval>=10, request-delay>={minimum}, lag-minutes>=1')
    if args.ai_cycle and not args.loop:p.error('--ai-cycle requires --loop')
    codes=[s['stock_code'] for s in json.loads(Path(args.universe).read_text(encoding='utf-8'))['symbols']] if args.universe else (args.symbols or '005930').split(',')
    codes=list(dict.fromkeys(code_check(c.strip()) for c in codes))
    if not codes:p.error('Empty universe')
    client=KIS(args.request_delay)
    previous=None
    try:
        while True:
            current=now_kst();t=current.strftime('%H%M')
            if current.weekday()<5 and '0902'<=t<='1535':
                cutoff=ai_cutoff(current,args.lag_minutes) if args.ai_cycle else None
                if cutoff is not None and cutoff==previous:
                    time.sleep(2);continue
                started=time.monotonic()
                failures=sweep(client,codes,args.write,args.backfill_today,args.lag_minutes,cutoff)
                elapsed=time.monotonic()-started
                if cutoff is not None:
                    previous=cutoff
                    print(json.dumps(dict(event='ai_cycle_finished',candle_end=str(cutoff),
                        seconds=round(elapsed,2),failed_symbols=failures,request_delay=client.delay,
                        target_expired=now_kst()>=cutoff+timedelta(minutes=5))),flush=True)
                    continue
                if not args.loop:return 1 if failures else 0
            elif not args.loop:
                print('Outside weekday 09:02-15:35 KST; no collection.');return 0
            # Rest after the entire sweep. Public holidays return no current-day rows.
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('Stopped. Committed rows are preserved.');return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,RuntimeError) as exc:raise SystemExit(str(exc)) from None
