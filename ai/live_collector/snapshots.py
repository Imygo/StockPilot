"""Immutable, compressed minute snapshots and transactional prediction audit."""
import hashlib
import json
import zlib
from datetime import datetime, timedelta

SNAPSHOT_DDL = '''CREATE TABLE IF NOT EXISTS ai_market_snapshots (
candle_end DATETIME NOT NULL, universe_sha256 CHAR(64) NOT NULL,
completed_at DATETIME(6) NOT NULL, snapshot_sha256 CHAR(64) NOT NULL,
symbol_count INT NOT NULL, row_count INT NOT NULL, payload MEDIUMBLOB NOT NULL,
PRIMARY KEY(candle_end,universe_sha256)) ENGINE=InnoDB'''
AUDIT_DDL = '''CREATE TABLE IF NOT EXISTS ai_prediction_runs (
candle_end DATETIME NOT NULL, model_sha256 CHAR(64) NOT NULL,
snapshot_sha256 CHAR(64) NOT NULL, collection_completed_at DATETIME(6) NOT NULL,
created_at DATETIME(6) NOT NULL, prediction_count INT NOT NULL,
audit_json JSON NOT NULL, PRIMARY KEY(candle_end,model_sha256)) ENGINE=InnoDB'''
MAX_RAW = 32 * 1024 * 1024


def universe_hash(codes):
    return hashlib.sha256(json.dumps(sorted(set(codes)),separators=(',',':')).encode()).hexdigest()


def encode_payload(rows):
    raw=json.dumps(rows,default=str,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>MAX_RAW: raise ValueError('Snapshot exceeds 32 MiB uncompressed limit')
    blob=zlib.compress(raw)
    # Remain below conservative MySQL packet limits, fail instead of truncating.
    if len(blob)>3*1024*1024: raise ValueError('Compressed snapshot exceeds 3 MiB limit')
    return blob,hashlib.sha256(raw).hexdigest()


def decode_payload(blob,digest):
    decoder=zlib.decompressobj()
    raw=decoder.decompress(blob,MAX_RAW+1)
    if len(raw)>MAX_RAW or not decoder.eof or decoder.unused_data:
        raise ValueError('Invalid or oversized snapshot payload')
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Snapshot checksum mismatch')
    rows=json.loads(raw)
    if not isinstance(rows,list):raise ValueError('Invalid snapshot rows')
    return rows


def publish(conn,cutoff,codes,failures=0):
    """Called only after every symbol request/commit finishes. First snapshot wins."""
    cutoff=cutoff.replace(tzinfo=None)
    if failures: return dict(event='snapshot_skipped',reason='collection_failed',failed_symbols=failures)
    codes=sorted(set(codes))
    if not codes:raise ValueError('Empty snapshot universe')
    target=cutoff+timedelta(minutes=5)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT UTC_TIMESTAMP(6) + INTERVAL 9 HOUR')
            current=cur.fetchone()[0]
            if not cutoff<=current<target:
                return dict(event='snapshot_skipped',reason='outside_prediction_interval')
            placeholders=','.join(['%s']*len(codes))
            cur.execute(f'''SELECT stock_code,candle_start,open_price,high_price,low_price,close_price,volume
FROM minute_chart_data WHERE stock_code IN ({placeholders}) AND candle_start >= %s AND candle_start < %s
ORDER BY stock_code,candle_start''',(*codes,cutoff.replace(hour=9,minute=5,second=0,microsecond=0),cutoff))
            rows=cur.fetchall()
            blob,digest=encode_payload(rows)
            cur.execute('SELECT UTC_TIMESTAMP(6) + INTERVAL 9 HOUR')
            completed=cur.fetchone()[0]
            if not cutoff<=completed<target:
                return dict(event='snapshot_skipped',reason='expired_during_freeze')
            cur.execute('''INSERT IGNORE INTO ai_market_snapshots
(candle_end,universe_sha256,completed_at,snapshot_sha256,symbol_count,row_count,payload)
VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                (cutoff,universe_hash(codes),completed,digest,len(codes),len(rows),blob))
            inserted=cur.rowcount==1
        conn.commit()
        return dict(event='snapshot_ready',candle_end=str(cutoff),new_snapshot=inserted,
                    rows=len(rows),collection_delay_seconds=(completed-cutoff).total_seconds())
    except Exception:
        conn.rollback();raise
    finally:
        conn.rollback()  # Close read transactions on early returns too.


def read(conn,cutoff,codes):
    cutoff=cutoff.replace(tzinfo=None)
    with conn.cursor() as cur:
        cur.execute('''SELECT completed_at,snapshot_sha256,symbol_count,row_count,payload
FROM ai_market_snapshots WHERE candle_end=%s AND universe_sha256=%s''',
                    (cutoff,universe_hash(codes)))
        row=cur.fetchone()
    conn.rollback()
    if row is None:raise ValueError('WAIT: completed market snapshot absent')
    completed,digest,count,n,blob=row
    if count!=len(set(codes)) or not cutoff<=completed<cutoff+timedelta(minutes=5):
        raise ValueError('Invalid snapshot metadata')
    rows=decode_payload(blob,digest)
    if len(rows)!=n:raise ValueError('Snapshot row count mismatch')
    allowed=set(codes)
    for r in rows:
        if len(r)!=7 or r[0] not in allowed:raise ValueError('Invalid snapshot stock/columns')
        t=datetime.fromisoformat(r[1])
        if not cutoff.replace(hour=9,minute=5,second=0,microsecond=0)<=t<cutoff:
            raise ValueError('Snapshot contains out-of-range minute')
    return rows,dict(snapshot_sha256=digest,collection_completed_at=str(completed),
                     collection_delay_seconds=(completed-cutoff).total_seconds())


def claim_run(cur,cutoff,digest,created,audit):
    """Same transaction as all predictions; a failed/expired write rolls this back."""
    cur.execute('''SELECT COUNT(*) FROM ai_prediction_history
WHERE candle_end=%s AND model_sha256=%s''',(cutoff,digest))
    if cur.fetchone()[0]: return False  # Never append new input snapshots to a legacy batch.
    cur.execute('''INSERT IGNORE INTO ai_prediction_runs
(candle_end,model_sha256,snapshot_sha256,collection_completed_at,created_at,prediction_count,audit_json)
VALUES (%s,%s,%s,%s,%s,%s,%s)''',
        (cutoff,digest,audit['snapshot_sha256'],audit['collection_completed_at'],created,
         len(audit['inputs']),json.dumps(audit,allow_nan=False,separators=(',',':'))))
    return cur.rowcount==1
