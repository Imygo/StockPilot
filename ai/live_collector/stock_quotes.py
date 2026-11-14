"""Refresh stock-list quotes. Preview by default; --write enables DB updates."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import time
import collector
from register_stocks import load_symbols

BASE = Path(__file__).resolve().parent
SERVERS = {'paper': 'https://openapivts.koreainvestment.com:29443',
           'live': 'https://openapi.koreainvestment.com:9443'}
FIELDS = ('current_price', 'marketCap', 'change_amount', 'change_rate', 'volume')

def integer(value):
    n = Decimal(str(value))
    if not n.is_finite() or n != n.to_integral_value():
        raise ValueError('Invalid integer quote')
    return int(n)

def quote_values(row):
    price, cap, volume = (integer(row[k]) for k in ('stck_prpr', 'hts_avls', 'acml_vol'))
    amount, rate = (Decimal(str(row[k])) for k in ('prdy_vrss', 'prdy_ctrt'))
    if price <= 0 or min(cap, volume) < 0 or not amount.is_finite() or not rate.is_finite():
        raise ValueError('Invalid quote')
    sign = str(row.get('prdy_vrss_sign', ''))
    if sign in ('4', '5'): amount, rate = -abs(amount), -abs(rate)
    elif sign in ('1', '2'): amount, rate = abs(amount), abs(rate)
    elif sign != '3': raise ValueError('Unknown change sign')
    # KIS hts_avls and the existing UI both use units of KRW 100 million.
    return price, cap, float(amount), float(rate), volume

def save_quote(conn, code, row):
    values = quote_values(row)
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE stock SET current_price=%s,marketCap=%s,change_amount=%s,'
                        'change_rate=%s,volume=%s,updated_at=CURRENT_TIMESTAMP WHERE stock_code=%s',
                        (*values, code))
            cur.execute('SELECT '+','.join(FIELDS)+' FROM stock WHERE stock_code=%s', (code,))
            saved = cur.fetchone()
            if saved is None or any(abs(Decimal(str(a))-Decimal(str(b))) > Decimal('0.000001')
                                    for a, b in zip(saved, values)):
                raise RuntimeError('Quote read-back mismatch or missing stock')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise

def make_api(environment):
    collector.BASE = SERVERS[environment]
    api = collector.KIS(delay=1.1)
    # A token inherited from a different server must not be reused.
    api.token = ''; api.expires = 0
    api.tr_id = 'FHKST01010100'
    return api

def run_cycle(conn, api, codes):
    with conn.cursor() as cur:
        cur.execute('SELECT stock_code FROM stock')
        existing = {r[0] for r in cur.fetchall()}
    conn.rollback()
    if set(codes) - existing:
        raise ValueError('Run register_stocks.py --write first')
    # Authenticate once, outside the symbol loop: do not retry auth for every stock.
    api.auth()
    saved = 0; errors = []; consecutive_errors = 0
    for code in codes:
        try:
            api.auth()  # Reuses in-memory token until its expiry.
            body = api.http('/uapi/domestic-stock/v1/quotations/inquire-price',
                            params=dict(FID_COND_MRKT_DIV_CODE='J', FID_INPUT_ISCD=code))
            save_quote(conn, code, body['output'])
            saved += 1; consecutive_errors = 0
        except Exception as exc:
            conn.rollback()
            errors.append(dict(stock_code=code, error=type(exc).__name__))
            consecutive_errors += 1
            if consecutive_errors >= 3: break
        if (saved + len(errors)) % 10 == 0:
            print(json.dumps(dict(saved=saved, failed=len(errors), total=len(codes))), flush=True)
    return dict(state='ok' if saved == len(codes) else 'partial', requested=len(codes),
                saved_and_verified=saved, errors=errors)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--universe', type=Path, default=BASE.parent/'data/top200-20261012.json')
    p.add_argument('--environment', choices=SERVERS, default='paper')
    p.add_argument('--write', action='store_true')
    p.add_argument('--loop', action='store_true')
    p.add_argument('--interval', type=int, default=300)
    args = p.parse_args()
    if args.interval < 300 or (args.loop and not args.write):
        p.error('Require interval >= 300 seconds; --loop requires --write')
    try:
        rows, snapshot = load_symbols(args.universe)
        codes = [r[0] for r in rows]
        if not args.write:
            print(json.dumps(dict(mode='preview', stocks=len(codes), environment=args.environment,
                                  snapshot=snapshot, db_accessed=False, api_called=False)))
            return 0
        from dotenv import load_dotenv
        load_dotenv(BASE/'.env', override=False)
        api = make_api(args.environment)
        while True:
            start = time.monotonic()
            conn = collector.connect()
            try: result = run_cycle(conn, api, codes)
            finally: conn.close()
            print(json.dumps(result), flush=True)
            # Stop on errors rather than repeatedly hammering credentials/DB/API.
            if result['state'] != 'ok': return 1
            if not args.loop: return 0
            time.sleep(max(1, args.interval-(time.monotonic()-start)))
    except KeyboardInterrupt:
        print('Stopped'); return 0
    except Exception as exc:
        print(json.dumps(dict(state='error', error=type(exc).__name__,
                              hint='Check API key/server pairing and DB settings. After auth failure wait at least 60s before retrying.')))
        return 1

if __name__ == '__main__': raise SystemExit(main())
