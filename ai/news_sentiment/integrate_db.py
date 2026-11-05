"""Explicit additive StockPilot migration and optional verified-result import."""
import argparse
import json
import re
from pathlib import Path
from database import config, connect
from live_worker import error_summary,write_json

REQUIRED={'article_id','stock_code','model_version','stock_name','aspect','market','title','description',
          'url','published_at','text_hash','label','p_negative','p_neutral','p_positive','quality_json','created_at'}

def check_schema(cur):
    cur.execute('SHOW COLUMNS FROM news_target_predictions')
    columns={r[0] for r in cur.fetchall()}
    if not REQUIRED<=columns:raise ValueError('Existing news table is incompatible; no ALTER was performed')
    cur.execute('SHOW INDEX FROM news_target_predictions')
    indexes={}
    for row in cur.fetchall():
        if row[1]==0:indexes.setdefault(row[2],[]).append((row[3],row[4]))
    keys={tuple(col for _,col in sorted(v)) for v in indexes.values()}
    if ('article_id','stock_code','model_version') not in keys or ('text_hash','stock_code','model_version') not in keys:
        raise ValueError('Required unique keys missing; no ALTER was performed')

def migrate():
    import pymysql
    with pymysql.connect(**config()) as conn:
        with conn.cursor() as cur:
            # Confirm the target actually has the StockPilot stock schema before DDL.
            cur.execute('SELECT stock_code,stock_name,market,marketCap FROM stock LIMIT 0')
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='news_target_predictions'")
            exists=bool(cur.fetchone())
            if exists:check_schema(cur)
            else:
                cur.execute((Path(__file__).resolve().parent/'sql/schema.sql').read_text(encoding='utf-8-sig'))
                check_schema(cur)
        conn.commit()
    return 'existing_compatible' if exists else 'created'

def validate_rows(rows):
    if not isinstance(rows,list):raise ValueError('Expected predictions list')
    for row in rows:
        for field in ('article_id','text_hash','model_version'):
            if not re.fullmatch('[0-9a-f]{64}',row.get(field,'')):raise ValueError('Invalid result identity')
        if not re.fullmatch('[0-9A-Z]{6}',row.get('stock_code','')):raise ValueError('Invalid stock code')
        for key in ('stock_name','aspect','market','title','description','url','published_at','label'):
            if not isinstance(row.get(key),str):raise ValueError('Missing result field')
    return rows

def import_results(path):
    from multi_worker import TargetStore,combine
    rows=validate_rows(json.loads(Path(path).read_text(encoding='utf-8-sig')))
    versions={r['model_version'] for r in rows};saved=0;skipped=0
    store=TargetStore()
    try:
        store.acquire()
        for version in sorted(versions):
            group=combine([], [r for r in rows if r['model_version']==version])
            pending=store.pending(group,version);skipped+=len(group)-len(pending)
            for start in range(0,len(pending),64):
                batch=pending[start:start+64]
                store.acquire();store.save_verified(batch,batch,version);saved+=len(batch)
                print(f'기존 예측 결과 DB 저장·확인: {saved}건',flush=True)
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM news_target_predictions')
                total=cur.fetchone()[0]
        return dict(imported=saved,already_present=skipped,total_predictions=total)
    finally:store.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--import-json',type=Path)
    parser.add_argument('--receipt',default='data/integration-receipt.json')
    args=parser.parse_args()
    try:
        result=dict(state='ok',database=config()['database'],schema=migrate(),existing_tables_modified=False)
        if args.import_json:result.update(import_results(args.import_json))
        write_json(args.receipt,result);print(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        result=dict(state='error',error=error_summary(exc))
        write_json(args.receipt,result);print(json.dumps(result))
        raise SystemExit(1)
if __name__=='__main__':main()
