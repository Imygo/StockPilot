import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
AI_ROOT=HERE
UPSERT = '''INSERT INTO ai_opinions (stock_code, invest_opinion)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE invest_opinion = %s, updated_at = CURRENT_TIMESTAMP'''
SELECT = 'SELECT stock_code, invest_opinion, updated_at FROM ai_opinions WHERE stock_code = %s'

def connect():
    import pymysql
    from dotenv import load_dotenv
    # Never read or copy the parent KIS credentials file.
    load_dotenv(HERE/'.env',override=False)
    host = os.environ.get('STOCKPILOT_DB_HOST','127.0.0.1')
    if host not in ('localhost','127.0.0.1','::1'):
        raise ValueError('This test tool accepts only a local DB host')
    try:
        return pymysql.connect(
            host=host,port=int(os.environ.get('STOCKPILOT_DB_PORT','3306')),
            user=os.environ.get('STOCKPILOT_DB_USER','root'),
            password=os.environ.get('STOCKPILOT_DB_PASSWORD',''),
            database=os.environ.get('STOCKPILOT_DB_NAME','stockpilot_db'),
            charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,connect_timeout=10,read_timeout=15,write_timeout=15,
            init_command="SET SESSION time_zone = '+09:00'")
    except pymysql.MySQLError as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0],int) else 'unknown'
        raise RuntimeError(f'MySQL connection failed (code {code}); check local DB and ai-demo/.env') from None

def validate_prediction(result):
    if result.get('stock_code') != '005930' or result.get('direction') not in ('UP','DOWN_OR_FLAT'):
        raise ValueError('Only Samsung direction predictions may be saved')

def save_opinion(connection, result):
    validate_prediction(result)
    try:
        with connection.cursor() as cursor:
            cursor.execute(UPSERT,('005930',result['direction'],result['direction']))
            cursor.execute(SELECT,('005930',))
            row = cursor.fetchone()
            if not row or row['invest_opinion'] != result['direction']:
                raise RuntimeError('DB read-back verification failed')
        connection.commit()
        return row
    except Exception:
        connection.rollback()
        raise

def read_opinion(connection):
    with connection.cursor() as cursor:
        cursor.execute(SELECT,('005930',))
        return cursor.fetchone()

def select_bars(bars, as_of=None, now=None):
    import pandas as pd
    now = pd.Timestamp.now(tz='Asia/Seoul') if now is None else pd.Timestamp(now)
    now = now.tz_localize('Asia/Seoul') if now.tzinfo is None else now.tz_convert('Asia/Seoul')
    if as_of:
        cutoff = pd.Timestamp(as_of)
        cutoff = cutoff.tz_localize('Asia/Seoul') if cutoff.tzinfo is None else cutoff.tz_convert('Asia/Seoul')
        if cutoff != cutoff.floor('5min') or cutoff > now or cutoff.strftime('%H:%M') >= '15:20':
            raise ValueError('as-of must be a completed five-minute boundary before 15:20 KST')
        if cutoff not in bars.index:
            raise ValueError('Requested candle is missing/incomplete in the CSV')
    else:
        eligible = bars[(bars.index <= now) & (bars.index.strftime('%H:%M') < '15:20')]
        if eligible.empty:
            raise ValueError('No completed candle with a following supported interval')
        cutoff = eligible.index[-1]
    return bars.loc[:cutoff]

def prediction(ai_dir=AI_ROOT, csv=None, artifacts=None, as_of=None, input_frame=None):
    import numpy as np
    import pandas as pd
    import torch
    ai_dir = Path(ai_dir).resolve()
    sys.path.insert(0,str(ai_dir))
    from stockpilot_ai.data import candles, features, FEATURES
    from stockpilot_ai.model import CNNLSTM
    csv = Path(csv) if csv else ai_dir/'data/minutes.csv'
    artifacts = Path(artifacts) if artifacts else ai_dir/'artifacts/short-fixed'
    meta = json.loads((artifacts/'metadata.json').read_text(encoding='utf-8'))
    scaler = json.loads((artifacts/'scaler.json').read_text(encoding='utf-8'))
    if (meta.get('schema_version') != 2 or meta.get('stock_code') != '005930'
            or meta.get('market') != 'J' or meta.get('neutral_bps') != 0
            or meta.get('horizon_minutes') != 5 or meta['features'] != FEATURES
            or scaler['features'] != FEATURES):
        raise ValueError('Use Samsung v2 artifacts with neutral_bps=0, e.g. short-fixed')
    bars = select_bars(candles(input_frame if input_frame is not None else csv),as_of)
    lookback = meta['lookback']
    f = features(bars).iloc[-lookback:]
    if len(f) != lookback or not (f.index.to_series().diff().iloc[1:] == pd.Timedelta(minutes=5)).all():
        raise ValueError('Insufficient continuous candles for prediction')
    x = ((f.to_numpy()-scaler['mean'])/scaler['scale']).astype(np.float32)
    if not np.isfinite(x).all():
        raise ValueError('Insufficient feature warmup or invalid saved scaler')
    model = CNNLSTM(len(FEATURES))
    model.load_state_dict(torch.load(artifacts/'model.pt',map_location='cpu',weights_only=True))
    model.eval()
    with torch.no_grad():
        score = float(torch.sigmoid(model(torch.from_numpy(x[None]))-meta['logit_correction']).item())
    if not np.isfinite(score):
        raise ValueError('Non-finite model output')
    result = {'mode':'historical_csv_replay', 'stock_code':'005930',
              'direction':'UP' if score >= meta['decision_threshold'] else 'DOWN_OR_FLAT',
              'candle_end':str(f.index[-1]),'target_end':str(f.index[-1]+pd.Timedelta(minutes=5)),
              'model_version':artifacts.name,'score_up':score,
              'decision_threshold':meta['decision_threshold'],'probability_calibrated':False,
              'model_sha256':hashlib.sha256((artifacts/'model.pt').read_bytes()).hexdigest()}
    return result


def main():
    parser=argparse.ArgumentParser(description='Samsung binary model: DB minutes -> latest AI opinion')
    parser.add_argument('command',choices=['db-inspect','db-preview','db-save','show'])
    parser.add_argument('--as-of',help='Historical five-minute candle end, Korean time')
    parser.add_argument('--minute-ohlcv',action='store_true',help='Confirm actual KRX per-minute OHLCV, not daily/cumulative values')
    args=parser.parse_args()
    try:
        if args.command=='show':
            with connect() as connection:
                row=read_opinion(connection)
            result={'found':row is not None,'row':row}
        else:
            from db_input import run_db
            result=run_db(args.command,connect,prediction,save_opinion,
                          as_of=args.as_of,minute_ohlcv=args.minute_ohlcv,
                          ai_dir=HERE,artifacts=HERE/'artifacts/short-fixed')
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    except (ValueError,RuntimeError,ImportError,FileNotFoundError) as exc:
        parser.exit(1,str(exc)+'\n')
    except Exception as exc:
        code=exc.args[0] if exc.args and isinstance(exc.args[0],int) else 'unknown'
        parser.exit(1,f'{type(exc).__name__} (code {code}); check local database and model files.\n')


if __name__=='__main__': main()
