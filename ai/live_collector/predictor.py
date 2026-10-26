"""Frozen binary market XGBoost: MySQL minutes -> auditable live predictions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI))
from stockpilot_ai.data import candles, features
from stockpilot_ai.multi_data import MULTI_FEATURES
from stockpilot_ai.inference import encode
from stockpilot_ai.inference import matrix
from stockpilot_ai import market_features as market
from collector import connect, error_details

DDL = '''CREATE TABLE IF NOT EXISTS ai_prediction_history (
stock_code VARCHAR(15) NOT NULL, candle_end DATETIME NOT NULL,
model_sha256 CHAR(64) NOT NULL, target_end DATETIME NOT NULL,
direction VARCHAR(8) NOT NULL, score_up DOUBLE NOT NULL,
reference_close DOUBLE NOT NULL, created_at DATETIME NOT NULL,
input_sha256 CHAR(64) NOT NULL, model_version VARCHAR(100) NOT NULL,
PRIMARY KEY(stock_code,candle_end,model_sha256), INDEX(target_end)
)'''
INSERT = '''INSERT IGNORE INTO ai_prediction_history
(stock_code,candle_end,model_sha256,target_end,direction,score_up,reference_close,
created_at,input_sha256,model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''


def now(): return pd.Timestamp.now(tz='Asia/Seoul')
def naive(t): return t.tz_localize(None).to_pydatetime()


def live_boundary(current):
    t=current.floor('5min')
    # Training anchors had 30 minutes of future data within the session.
    if t.dayofweek>=5 or not '11:00'<=t.strftime('%H:%M')<='14:50':
        raise ValueError('WAIT: supported prediction anchors are weekdays 11:00-14:50 KST')
    return t


def window(bars, cutoff, lookback):
    b=bars[bars.index<=cutoff]
    if b.empty or b.index[-1]!=cutoff: raise ValueError('Latest completed five-minute bar missing')
    f=features(b)[MULTI_FEATURES].to_numpy(dtype=np.float32)
    if len(f)<lookback:raise ValueError('Insufficient lookback')
    if not b.index[-lookback:].to_series().diff().dropna().eq(pd.Timedelta(minutes=5)).all():
        raise ValueError('Gap inside lookback')
    return encode(f[-lookback:][None,:,:]).astype(np.float32)


def load(artifacts, universe):
    from xgboost import XGBClassifier
    root=Path(artifacts)
    meta=json.loads((root/'metadata.json').read_text(encoding='utf-8'))
    priors=json.loads((root/'baseline.json').read_text(encoding='utf-8'))
    trained=json.loads((root/'universe.json').read_text(encoding='utf-8'))['symbols']
    symbols=json.loads(Path(universe).read_text(encoding='utf-8'))['symbols']
    if meta.get('schema_version')!='binary-market-research-v1' or meta['features']!=MULTI_FEATURES or meta['classes']!=['DOWN','UP']:
        raise ValueError('Unsupported model metadata')
    if meta['horizon_minutes']!=5 or meta['input_encoding']!='44_window_summary_plus_train_up_prior_exchange_32_market':
        raise ValueError('Unsupported model horizon/encoding')
    if len(symbols)!=200 or {s['stock_code'] for s in symbols}!=set(meta['market_context_symbols']):
        raise ValueError('Market universe must exactly match original 200 stocks')
    exchanges={s['stock_code']:s['exchange'] for s in symbols}
    if any(s['exchange']!=exchanges.get(s['stock_code']) for s in trained) or set(priors)!={s['stock_code'] for s in trained}:
        raise ValueError('Training universe/prior mismatch')
    model=XGBClassifier();model.load_model(root/'model.ubj');model.set_params(n_jobs=2)
    if model.n_features_in_!=78:raise ValueError('Expected 78 model inputs')
    # Include metadata/prior in identity, not just tree bytes.
    digest=hashlib.sha256()
    for name in ('model.ubj','metadata.json','baseline.json','universe.json'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return model,meta,priors,symbols,digest.hexdigest(),root.parent.name+'/'+root.name


def fetch(connection, cutoff, symbols):
    codes=[s['stock_code'] for s in symbols]
    placeholders=','.join(['%s']*len(codes))
    query=f'''SELECT stock_code,candle_start,open_price,high_price,low_price,close_price,volume
FROM minute_chart_data WHERE stock_code IN ({placeholders})
AND candle_start >= %s AND candle_start < %s ORDER BY stock_code,candle_start'''
    with connection.cursor() as cur:
        cur.execute(query,(*codes,naive(cutoff.normalize()+pd.Timedelta(hours=9,minutes=5)),naive(cutoff)))
        rows=cur.fetchall()
    connection.rollback()
    return pd.DataFrame(rows,columns=['stock_code','timestamp','open','high','low','close','volume'])


def inputs(frame,cutoff,meta,priors,symbols):
    own={};bars_by={};skipped={}
    for code,block in frame.groupby('stock_code'):
        block=block.copy();block['market']='J'
        try:
            b=candles(block,stock_code=code);b=b[b.index<=cutoff]
            own[code]=market.returns(b);bars_by[code]=b
        except ValueError as exc:skipped[code]=str(exc)
    if not own:raise ValueError('WAIT: no usable minute data')
    context=market.aggregate(own,symbols)
    if cutoff not in context.index:raise ValueError('WAIT: market snapshot absent')
    coverage={f'{m}_{h}':float(context.loc[cutoff,f'{m}_coverage_{h}']) for m in market.MARKETS for h in market.HORIZONS}
    if min(coverage.values())<.8:raise ValueError('WAIT: market coverage below 80%: '+json.dumps(coverage))
    xx=[];items=[]
    for s in symbols:
        code=s['stock_code']
        if code not in priors:continue
        try:
            if code not in bars_by:raise ValueError('No data')
            b=bars_by[code];x=window(b,cutoff,meta['lookback'])
            z=market.encode(context,own,code,s['exchange'],[str(cutoff)])
            value=matrix(x,z,float(priors[code]),s['exchange'])
            if not np.isfinite(value).all():raise ValueError('Nonfinite input')
            xx.append(value);items.append(dict(stock_code=code,reference_close=float(b.loc[cutoff,'close']),
                                               input_sha256=hashlib.sha256(value.tobytes()).hexdigest()))
        except ValueError as exc:skipped[code]=str(exc)
    if not xx:raise ValueError('WAIT: no eligible prediction stocks')
    return np.concatenate(xx),items,coverage,skipped


def persist(connection,rows,cutoff,digest,version,audit=None):
    target=cutoff+pd.Timedelta(minutes=5)
    created=now()
    if not cutoff<=created<target:raise ValueError('Expired prediction; no writes')
    saved=0
    try:
        with connection.cursor() as cur:
            # DB-server clock also checked; prevents writing through a stale local clock.
            cur.execute('SELECT UTC_TIMESTAMP() + INTERVAL 9 HOUR')
            db_now=pd.Timestamp(cur.fetchone()[0]).tz_localize('Asia/Seoul')
            if not cutoff<=db_now<target:raise ValueError('DB clock outside prediction interval')
            if audit is not None:
                from snapshots import claim_run
                if not claim_run(cur,naive(cutoff),digest,naive(created),audit):
                    connection.rollback()
                    return 0
            for r in rows:
                cur.execute(INSERT,(r['stock_code'],naive(cutoff),digest,naive(target),r['direction'],r['score_up'],
                    r['reference_close'],naive(created),r['input_sha256'],version))
                if cur.rowcount==1:
                    # Only a newly recorded prediction updates the legacy latest opinion.
                    cur.execute('''INSERT INTO ai_opinions(stock_code,invest_opinion,updated_at)
VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE invest_opinion=VALUES(invest_opinion),updated_at=VALUES(updated_at)''',
                                (r['stock_code'],r['direction'],naive(created)))
                    saved+=1
        if now()>=target:raise ValueError('Expired while saving; transaction rolled back')
        if audit is not None:
            with connection.cursor() as cur:
                cur.execute('SELECT UTC_TIMESTAMP(6) + INTERVAL 9 HOUR')
                if pd.Timestamp(cur.fetchone()[0]).tz_localize('Asia/Seoul')>=target:
                    raise ValueError('Expired on DB server; transaction rolled back')
        connection.commit()
    except Exception:connection.rollback();raise
    return saved


def cycle(bundle,write=False,require_snapshot=False):
    model,meta,priors,symbols,digest,version=bundle
    cutoff=live_boundary(now());connection=connect()
    try:
        snapshot_info=None
        if require_snapshot:
            from snapshots import read
            # A committed batch is immutable; do not recompute or append late stocks.
            with connection.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM ai_prediction_history WHERE candle_end=%s AND model_sha256=%s',
                            (naive(cutoff),digest))
                already_saved=cur.fetchone()[0]
            connection.rollback()
            if already_saved:
                print(json.dumps(dict(event='prediction_already_saved',candle_end=str(cutoff),predictions=already_saved,new_rows_saved=0)),flush=True)
                return
            data,snapshot_info=read(connection,naive(cutoff),[s['stock_code'] for s in symbols])
            frame=pd.DataFrame(data,columns=['stock_code','timestamp','open','high','low','close','volume'])
            frame['timestamp']=pd.to_datetime(frame['timestamp'])
        else:
            frame=fetch(connection,cutoff,symbols)
        x,items,coverage,skipped=inputs(frame,cutoff,meta,priors,symbols)
        p=model.predict_proba(x)[:,1]
        for item,score in zip(items,p):
            item.update(score_up=float(score),direction='UP' if score>=meta['decision_threshold'] else 'DOWN')
        if now()>=cutoff+pd.Timedelta(minutes=5):raise ValueError('Expired during inference')
        audit=None
        if snapshot_info is not None:
            audit=dict(snapshot_info,market_coverage=coverage,skipped=skipped,
                feature_encoding=meta['input_encoding'],inputs=[dict(stock_code=item['stock_code'],
                    input_sha256=item['input_sha256'],values=vector.tolist()) for item,vector in zip(items,x)])
        saved=persist(connection,items,cutoff,digest,version,audit) if write else 0
        print(json.dumps(dict(candle_end=str(cutoff),target_end=str(cutoff+pd.Timedelta(minutes=5)),
            predictions=len(items),new_rows_saved=saved,mode='saved' if write else 'dry_run',
            market_coverage=coverage,snapshot=snapshot_info,skipped=skipped,examples=items[:3],probability_calibrated=False)),flush=True)
    finally:connection.close()


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'),override=False)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts',default=str(AI/'artifacts/top200-binary-v1/xgboost'))
    p.add_argument('--universe',default=str(AI/'data/top200-20261012.json'))
    p.add_argument('--require-snapshot',action='store_true',help='Only predict from immutable completed collection snapshots')
    p.add_argument('--init-db',action='store_true');p.add_argument('--write',action='store_true')
    p.add_argument('--loop',action='store_true');p.add_argument('--interval',type=int,default=20)
    args=p.parse_args()
    if args.interval<10:p.error('interval must be >=10')
    if args.init_db:
        conn=connect()
        try:
            from snapshots import SNAPSHOT_DDL,AUDIT_DDL
            with conn.cursor() as cur:
                for ddl in (DDL,SNAPSHOT_DDL,AUDIT_DDL):cur.execute(ddl)
            conn.commit();print('Prediction history, market snapshots and prediction runs ready. Existing tables not altered.')
        finally:conn.close()
        return
    bundle=load(args.artifacts,args.universe)
    try:
        while True:
            try:cycle(bundle,args.write,args.require_snapshot)
            except Exception as exc:
                detail=error_details(exc)
                if args.require_snapshot and detail.get('mysql_code') in (1146,1054):
                    detail['hint']='Check snapshot/history/run schemas; run predictor.py --init-db first.'
                print(json.dumps(detail),flush=True)
                if not args.loop:return 1
            if not args.loop:return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:print('Prediction loop stopped.');return 0


if __name__=='__main__':raise SystemExit(main())
