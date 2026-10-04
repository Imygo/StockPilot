"""Existing MySQL minute rows -> unchanged Samsung model preprocessing."""
import pandas as pd

QUERY = '''SELECT stock_code, candle_start AS timestamp,
open_price AS open, high_price AS high, low_price AS low,
close_price AS close, volume
FROM minute_chart_data
WHERE stock_code = %s AND candle_start >= %s AND candle_start < %s
ORDER BY candle_start ASC'''


def boundary(as_of=None, now=None):
    current = pd.Timestamp.now(tz='Asia/Seoul') if now is None else pd.Timestamp(now)
    current = current.tz_localize('Asia/Seoul') if current.tzinfo is None else current.tz_convert('Asia/Seoul')
    cutoff = pd.Timestamp(as_of) if as_of else current.floor('5min')
    cutoff = cutoff.tz_localize('Asia/Seoul') if cutoff.tzinfo is None else cutoff.tz_convert('Asia/Seoul')
    if pd.isna(cutoff) or cutoff > current or cutoff != cutoff.floor('5min'):
        raise ValueError('Use a completed five-minute boundary in KST')
    if cutoff.dayofweek >= 5 or not '09:10' <= cutoff.strftime('%H:%M') <= '15:15':
        raise ValueError('Outside supported session; for weekend testing use --as-of with a historical weekday candle end')
    return cutoff


def fetch_minutes(connection, cutoff):
    start = cutoff.normalize()+pd.Timedelta(hours=9,minutes=5)
    with connection.cursor() as cursor:
        # DB DATETIME contract: Korean local minute START; do not include running minute.
        cursor.execute(QUERY,('005930',start.tz_localize(None).to_pydatetime(),cutoff.tz_localize(None).to_pydatetime()))
        rows = cursor.fetchall()
    if not rows:
        raise ValueError('No Samsung minute rows in DB for this date; populate minute_chart_data first')
    frame = pd.DataFrame(rows)
    required = ['stock_code','timestamp','open','high','low','close','volume']
    if not set(required).issubset(frame.columns) or frame[required].isna().any().any():
        raise ValueError('Missing/null minute OHLCV fields')
    times = pd.to_datetime(frame.timestamp)
    times = times.dt.tz_localize('Asia/Seoul') if times.dt.tz is None else times.dt.tz_convert('Asia/Seoul')
    if not times.eq(times.dt.floor('min')).all() or times.duplicated().any():
        raise ValueError('DB candle_start must be unique minute-start boundaries')
    if not frame.stock_code.eq('005930').all() or not ((times>=start)&(times<cutoff)).all():
        raise ValueError('Unexpected symbol or timestamp in query result')
    if times.max() != cutoff-pd.Timedelta(minutes=1):
        raise ValueError('Latest completed minute is missing; refusing stale prediction')
    frame['timestamp']=times
    frame['market']='J'
    return frame


def run_db(command, connect, predict, save, as_of=None, minute_ohlcv=False,
           ai_dir=None, artifacts=None):
    cutoff=boundary(as_of)
    if command != 'db-inspect' and not minute_ohlcv:
        raise ValueError('Confirm source uses KRX per-minute OHLCV (not daily OHLC/cumulative volume), then pass --minute-ohlcv')
    with connect() as connection:
        frame=fetch_minutes(connection,cutoff)
        connection.rollback()  # End read snapshot before inference.
    if command == 'db-inspect':
        return {'source':'minute_chart_data','stock_code':'005930','rows':len(frame),
                'first_minute':str(frame.timestamp.min()),'last_minute':str(frame.timestamp.max()),
                'requested_candle_end':str(cutoff),
                'last_rows':frame.tail(5).to_dict(orient='records'),
                'notice':'Row values cannot prove per-minute vs cumulative semantics. Check producer.'}
    result=predict(ai_dir=ai_dir,artifacts=artifacts,as_of=str(cutoff),input_frame=frame)
    result['mode']='historical_db_replay' if as_of else 'current_db_snapshot'
    result['source']='minute_chart_data'
    if command == 'db-save':
        # Never save a live result after its prediction interval has already expired.
        if not as_of and pd.Timestamp.now(tz='Asia/Seoul') >= cutoff+pd.Timedelta(minutes=5):
            raise ValueError('Prediction interval expired during inference; rerun')
        with connect() as connection:
            row=save(connection,result)
        return {'prediction':result,'db_row':row,'db_saved':True,
                'notice':'Latest opinion overwritten. updated_at is write time; historical replay is not live.'}
    return result
