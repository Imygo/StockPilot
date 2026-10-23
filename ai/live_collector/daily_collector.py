"""Completed KRX daily bars to MySQL. Default: preview, last 365 calendar days."""
import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from collector import KIS, now_kst, connect, code_check, error_details

API = '/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice'
DDL = '''CREATE TABLE IF NOT EXISTS daily_chart_data (
stock_code VARCHAR(15) NOT NULL, trade_date DATE NOT NULL,
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
close_price INT, volume BIGINT, change_amount DOUBLE, change_rate DOUBLE,
open_price INT, high_price INT, low_price INT,
PRIMARY KEY(stock_code,trade_date))'''
UPSERT = '''INSERT INTO daily_chart_data
(stock_code,trade_date,open_price,high_price,low_price,close_price,volume)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE open_price=VALUES(open_price),high_price=VALUES(high_price),
low_price=VALUES(low_price),close_price=VALUES(close_price),volume=VALUES(volume),
updated_at=CURRENT_TIMESTAMP'''


def period(start=None, end=None, today=None):
    today = today or now_kst().date()
    end = date.fromisoformat(end) if end else today-timedelta(days=1)
    start = date.fromisoformat(start) if start else end-timedelta(days=364)
    if not start <= end < today:
        raise ValueError('Require start <= end < today (KST); today is never imported')
    return start, end


def chunks(start, end):
    while start <= end:
        hi = min(start+timedelta(days=89), end)
        yield start, hi
        start = hi+timedelta(days=1)


def normalize(page, code, start, end):
    if not isinstance(page, list):
        raise ValueError('Missing daily output2 array')
    result = {}
    for r in page:
        day = datetime.strptime(r['stck_bsop_date'], '%Y%m%d').date()
        if not start <= day <= end:
            continue
        o,h,l,c,v = [int(r[k]) for k in
                     ('stck_oprc','stck_hgpr','stck_lwpr','stck_clpr','acml_vol')]
        # A suspended, non-trading day may carry a close but zero OHLC.
        # Do not manufacture a candle from it.
        if o == h == l == v == 0 and c >= 0:
            continue
        if min(o,h,l,c) <= 0 or v < 0 or not l <= min(o,c) <= max(o,c) <= h:
            raise ValueError('Invalid daily OHLCV')
        row = (code,day,o,h,l,c,v)
        if day in result and result[day] != row:
            raise ValueError('Conflicting daily duplicate')
        result[day] = row
    return [result[d] for d in sorted(result)]


class DailyKIS(KIS):
    tr_id = 'FHKST03010100'

    def daily(self, code, start, end):
        self.auth()
        body = self.http(API, params=dict(FID_COND_MRKT_DIV_CODE='J',
            FID_INPUT_ISCD=code, FID_INPUT_DATE_1=start.strftime('%Y%m%d'),
            FID_INPUT_DATE_2=end.strftime('%Y%m%d'), FID_PERIOD_DIV_CODE='D',
            FID_ORG_ADJ_PRC='1'))  # Original traded prices, not adjusted training prices.
        return normalize(body.get('output2'),code,start,end)


def inspect(connection):
    with connection.cursor() as cur:
        cur.execute('SHOW COLUMNS FROM daily_chart_data')
        cols = {r[0] for r in cur.fetchall()}
        if not {'stock_code','trade_date','open_price','high_price','low_price',
                'close_price','volume','updated_at'} <= cols:
            raise ValueError('daily_chart_data columns mismatch')
        cur.execute('SHOW INDEX FROM daily_chart_data')
        pk = [r[4] for r in sorted(cur.fetchall(),key=lambda r:r[3]) if r[2]=='PRIMARY']
        if pk != ['stock_code','trade_date']:
            raise ValueError('daily_chart_data primary key must be (stock_code, trade_date)')
    connection.rollback()


def save(connection, rows):
    try:
        with connection.cursor() as cur:
            if rows:
                cur.executemany(UPSERT,rows)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def run(client, codes, start, end, write):
    failures = 0
    for code in codes:
        total = 0
        for lo,hi in chunks(start,end):
            conn = None
            try:
                rows = client.daily(code,lo,hi)
                if write:
                    conn = connect()
                    inspect(conn)
                    save(conn,rows)
                total += len(rows)
                print(json.dumps(dict(event='daily_saved' if write else 'daily_preview',
                    stock_code=code,start=str(lo),end=str(hi),rows=len(rows),
                    first=str(rows[0][1]) if rows else None,
                    last=str(rows[-1][1]) if rows else None)),flush=True)
            except Exception as exc:
                failures += 1
                detail = error_details(exc)
                if detail.get('mysql_code') in (1146,1054):
                    detail['hint'] = 'Check daily_chart_data schema; run --init-db for missing table.'
                print(json.dumps(dict(stock_code=code,start=str(lo),end=str(hi),**detail)),flush=True)
            finally:
                if conn:
                    conn.close()
        print(json.dumps(dict(event='daily_symbol_finished',stock_code=code,rows_processed=total)),flush=True)
    print(json.dumps(dict(event='daily_finished',failed_chunks=failures,
        note='Rerun same dates to retry; existing rows are upserted, not duplicated.')),flush=True)
    return int(failures > 0)


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'),override=False)
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument('--symbols',help='Comma-separated symbols; default 005930')
    g.add_argument('--universe',help='JSON containing symbols[].stock_code')
    p.add_argument('--start'); p.add_argument('--end')
    p.add_argument('--write',action='store_true')
    p.add_argument('--init-db',action='store_true')
    p.add_argument('--check-db',action='store_true')
    p.add_argument('--request-delay',type=float,default=.6)
    a = p.parse_args()
    if a.init_db or a.check_db:
        conn = connect()
        try:
            if a.init_db:
                with conn.cursor() as cur: cur.execute(DDL)
                conn.commit()
            inspect(conn)
            print(json.dumps(dict(daily_schema_valid=True,created_if_missing=a.init_db)))
        finally: conn.close()
        return 0
    if a.request_delay < .5: p.error('request-delay must be >= 0.5 seconds')
    start,end = period(a.start,a.end)
    codes = ([s['stock_code'] for s in json.loads(Path(a.universe).read_text(encoding='utf-8-sig'))['symbols']]
             if a.universe else (a.symbols or '005930').split(','))
    codes = list(dict.fromkeys(code_check(c.strip()) for c in codes))
    if not codes: p.error('Empty universe')
    return run(DailyKIS(a.request_delay),codes,start,end,a.write)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except KeyboardInterrupt:
        print('Stopped. Committed chunks are preserved; rerun the same dates.')
        raise SystemExit(130)
    except Exception as exc:
        print(json.dumps(error_details(exc)))
        raise SystemExit(1)
