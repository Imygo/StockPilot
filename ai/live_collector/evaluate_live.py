"""Read-only evaluation of recorded live predictions against completed MySQL minute bars."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import time
from collector import connect, now_kst, error_details

CLASSES = ('DOWN', 'FLAT', 'UP')


def number(value):
    try:
        v = Decimal(str(value))
        if not v.is_finite(): raise ValueError('Nonfinite price')
        return v
    except InvalidOperation:
        raise ValueError('Invalid price') from None


def assess(p, minutes, current, lag=60):
    """Times are naive KST from DB; target close = last of 5 exact minute starts."""
    anchor, target, created = p['candle_end'], p['target_end'], p['created_at']
    result = dict(stock_code=p['stock_code'],model_sha256=p['model_sha256'],
        candle_end=str(anchor),target_end=str(target),created_at=str(created),
        predicted=p['direction'],status='invalid_prediction')
    if (target-anchor != timedelta(minutes=5) or anchor.second or anchor.microsecond
            or anchor.minute % 5 or anchor.date()!=target.date()
            or anchor.weekday()>=5 or not dt_time(9,10)<=anchor.time()<=dt_time(15,15)
            or p['direction'] not in ('UP','DOWN')):
        return result
    delay=(created-anchor).total_seconds()
    result['creation_delay_seconds']=delay
    result['remaining_seconds_at_creation']=(target-created).total_seconds()
    if not anchor <= created < target:
        result['status']='invalid_prediction_timing'
        return result
    try:
        reference=number(p['reference_close'])
        if reference<=0: return result
    except ValueError: return result
    if current < target+timedelta(seconds=lag):
        result['status']='pending_target'
        return result
    needed=[anchor+timedelta(minutes=i) for i in range(5)]
    if any(t not in minutes for t in needed):
        result['status']='missing_target_minutes'
        return result
    selected=[minutes[t] for t in needed]
    try:
        for r in selected:
            o,h,l,c,v=[number(r[k]) for k in ('open_price','high_price','low_price','close_price','volume')]
            if min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
                raise ValueError('Invalid OHLCV')
        close=number(selected[-1]['close_price'])
    except ValueError:
        result['status']='invalid_target_minutes'
        return result
    actual='UP' if close>reference else 'DOWN' if close<reference else 'FLAT'
    # Use the immutable reference actually recorded with the forecast, not a later revised bar.
    result.update(status='evaluated',actual=actual,correct=p['direction']==actual,
        reference_close=float(reference),target_close=float(close),
        return_bps=float((close/reference-1)*10000),
        target_source_sha256=hashlib.sha256(json.dumps(selected,sort_keys=True,default=str).encode()).hexdigest())
    return result


def metrics(rows):
    valid=[r for r in rows if r['status']=='evaluated']
    directional=[r for r in valid if r['actual']!='FLAT']
    correct=sum(r['correct'] for r in valid)
    cm=[[sum(r['actual']==a and r['predicted']==p for r in valid)
         for p in ('DOWN','UP')] for a in CLASSES]
    return dict(recorded=len(rows),status_counts=dict(Counter(r['status'] for r in rows)),
        evaluated=len(valid),flat=sum(r['actual']=='FLAT' for r in valid),
        correct=correct,all_outcomes_accuracy=correct/len(valid) if valid else None,
        nonzero_samples=len(directional),nonzero_accuracy=correct/len(directional) if directional else None,
        majority_nonzero_baseline=max((sum(r['actual']==a for r in directional) for a in ('DOWN','UP')),default=0)/len(directional) if directional else None,
        actual_class_order=list(CLASSES),predicted_class_order=['DOWN','UP'],confusion_matrix=cm,
        note='Flat is an incorrect UP/DOWN prediction in all_outcomes_accuracy. Missing/invalid/pending rows excluded and counted separately.')


def report(rows):
    groups=defaultdict(list)
    for r in rows: groups[r['model_sha256']].append(r)
    models={}
    for digest,items in groups.items():
        stocks=defaultdict(list);days=defaultdict(list);delays=defaultdict(list)
        for r in items:
            stocks[r['stock_code']].append(r)
            days[r['candle_end'][:10]].append(r)
            d=r.get('creation_delay_seconds',-1)
            bucket='invalid' if not 0<=d<300 else '0_to_60s' if d<60 else '60_to_180s' if d<180 else '180_to_300s'
            delays[bucket].append(r)
        models[digest]=dict(overall=metrics(items),by_stock={k:metrics(v) for k,v in stocks.items()},
            by_day={k:metrics(v) for k,v in days.items()},by_creation_delay={k:metrics(v) for k,v in delays.items()})
    return dict(models=models,details=rows,
        note='Observed stored predictions only; not coverage of every stock/time. Models are separated. Prices may be revised later; evaluation is recomputed. This measures direction from candle_end, not return after actual delivery or trading profit.')


def fetch_day(conn, day, lag):
    from pymysql.cursors import DictCursor
    start=datetime.combine(day,dt_time());end=start+timedelta(days=1)
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute('SELECT UTC_TIMESTAMP() + INTERVAL 9 HOUR AS current_kst')
            current=cur.fetchone()['current_kst']
            cur.execute('''SELECT stock_code,candle_end,target_end,created_at,direction,
reference_close,model_sha256 FROM ai_prediction_history
WHERE candle_end >= %s AND candle_end < %s ORDER BY candle_end,stock_code,model_sha256''',(start,end))
            predictions=cur.fetchall()
            if not predictions: return []
            cur.execute('''SELECT stock_code,candle_start,open_price,high_price,low_price,close_price,volume
FROM minute_chart_data WHERE candle_start >= %s AND candle_start < %s
ORDER BY stock_code,candle_start''',(start,end))
            minutes=defaultdict(dict)
            for r in cur.fetchall():
                if r['candle_start'] in minutes[r['stock_code']]:
                    raise ValueError('Duplicate minute timestamps; check DB unique key')
                minutes[r['stock_code']][r['candle_start']]=r
        return [assess(p,minutes[p['stock_code']],current,lag) for p in predictions]
    finally:
        conn.rollback()  # This tool never commits or modifies database records.


def cycle(start, end, lag, output=None):
    conn=connect()
    rows=[]
    try:
        day=start
        while day<=end:
            rows.extend(fetch_day(conn,day,lag))
            day+=timedelta(days=1)
    finally: conn.close()
    result=report(rows)
    result.update(start=str(start),end=str(end),generated_at=str(now_kst()),settlement_lag_seconds=lag)
    if output:
        p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix(p.suffix+'.tmp')
        tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(p)
    print(json.dumps(dict(event='live_accuracy',start=str(start),end=str(end),
        models={k:v['overall'] for k,v in result['models'].items()},
        recorded=len(rows),report_file=str(output) if output else None),ensure_ascii=False),flush=True)
    return result


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'),override=False)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',type=date.fromisoformat)
    p.add_argument('--end',type=date.fromisoformat)
    p.add_argument('--out',help='Optional JSON report; atomically replaced each cycle')
    p.add_argument('--loop',action='store_true')
    p.add_argument('--interval',type=int,default=60)
    p.add_argument('--lag-seconds',type=int,default=60)
    a=p.parse_args()
    if a.interval<10 or a.lag_seconds<60: p.error('interval >= 10 and lag-seconds >= 60 required')
    if a.start and a.end and a.start>a.end: p.error('start must be <= end')
    while True:
        try:
            # With no dates supplied, follow the current KST day even across midnight.
            end=a.end or now_kst().date();start=a.start or end
            if start>end or (end-start).days>366: raise ValueError('Require ordered range of at most 367 days')
            cycle(start,end,a.lag_seconds,a.out)
        except KeyboardInterrupt:
            print('Evaluation stopped; database unchanged.');return 0
        except Exception as exc:
            detail=error_details(exc)
            if detail.get('mysql_code') in (1146,1054): detail['hint']='Check ai_prediction_history and minute_chart_data schemas.'
            print(json.dumps(detail),flush=True)
            if not a.loop:return 1
        if not a.loop:return 0
        try: time.sleep(a.interval)
        except KeyboardInterrupt:return 0


if __name__=='__main__': raise SystemExit(main())
