"""Shared stock universe -> news inference -> configured StockPilot DB."""
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
from news import fetch, clean, canonical_url, digest
from database import connect
from live_worker import Store as LockStore, write_json, error_summary, write_report
from shared_universe import DEFAULT_UNIVERSE, load_universe

class BudgetExceeded(RuntimeError): pass

class Budget:
    def __init__(self,path,limit=22000):
        self.path=Path(path);self.limit=limit;self.last=0
    def charge(self):
        time.sleep(max(0,.3-(time.monotonic()-self.last)))
        now=time.time()
        used=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
        used=[x for x in used if x>now-86400]
        if len(used)>=self.limit: raise BudgetExceeded('Rolling 24-hour request budget reached')
        write_json(self.path,used+[now]);self.last=time.monotonic()

def normalize(item,stock):
    title,description=clean(item.get('title')),clean(item.get('description'))
    if not title or stock['aspect'].casefold() not in (title+' '+description).casefold(): return None
    url=canonical_url(item.get('originallink') or item.get('link',''))
    dt=parsedate_to_datetime(item['pubDate'])
    if dt.tzinfo is None: raise ValueError('Missing timezone')
    return dict(article_id=digest(url),title=title,description=description,url=url,
                published_at=dt.astimezone(timezone.utc).isoformat(),text_hash=digest(title+'\n'+description),
                **{k:stock[k] for k in ('stock_code','stock_name','aspect','market')})

def combine(existing,incoming):
    result=[];ids=set();hashes=set()
    for row in list(existing)+list(incoming):
        key=(row['article_id'],row['stock_code']);h=(row['text_hash'],row['stock_code'])
        if key not in ids and h not in hashes:
            result.append(row);ids.add(key);hashes.add(h)
    return result

class TargetStore(LockStore):
    def pending(self,rows,version):
        result=[]
        with connect() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute('''SELECT 1 FROM news_target_predictions WHERE stock_code=%s AND model_version=%s
                        AND (article_id=%s OR text_hash=%s) LIMIT 1''',
                        (row['stock_code'],version,row['article_id'],row['text_hash']))
                    if not cur.fetchone(): result.append(row)
        return result
    def save_verified(self,rows,predictions,version):
        if len(rows)!=len(predictions) or not version or len(version)>64: raise ValueError('Invalid prediction batch')
        with connect() as conn:
            try:
                with conn.cursor() as cur:
                    for row,pred in zip(rows,predictions):
                        probs=[float(pred[k]) for k in ('negative','neutral','positive')]
                        if pred['label'] not in ('negative','neutral','positive') or any(not math.isfinite(x) or not 0<=x<=1 for x in probs) or abs(sum(probs)-1)>1e-5:
                            raise ValueError('Invalid prediction')
                        dt=datetime.fromisoformat(row['published_at']).astimezone(timezone.utc).replace(tzinfo=None)
                        cur.execute('''INSERT INTO news_target_predictions
                            (article_id,stock_code,model_version,stock_name,aspect,market,title,description,url,published_at,text_hash,
                             label,p_negative,p_neutral,p_positive,quality_json)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON DUPLICATE KEY UPDATE article_id=article_id''',
                            (row['article_id'],row['stock_code'],version,row['stock_name'],row['aspect'],row['market'],row['title'],row['description'],row['url'],dt,row['text_hash'],pred['label'],*probs,json.dumps(pred.get('quality',{}),ensure_ascii=False)))
                        cur.execute('''SELECT label,p_negative,p_neutral,p_positive FROM news_target_predictions
                            WHERE stock_code=%s AND model_version=%s AND (article_id=%s OR text_hash=%s)''',
                            (row['stock_code'],version,row['article_id'],row['text_hash']))
                        found=cur.fetchone()
                        if not found or found[0]!=pred['label'] or any(abs(found[i+1]-v)>1e-6 for i,v in enumerate(probs)):
                            raise RuntimeError('Prediction read-back mismatch')
                conn.commit()
            except BaseException:
                conn.rollback();raise
        # Commit success is required before the queue is cleared.

def run_cycle(directory,predictor,store,stocks,budget,fetcher=fetch):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    queue_path=directory/'pending.json'
    queue=json.loads(queue_path.read_text(encoding='utf-8')) if queue_path.exists() else []
    errors=[];invalid=0;capped=[];fetched=0
    store.acquire()
    # Keep excluded queued rows on disk, but never predict/store them for this universe.
    excluded_path=directory/'pending-excluded.json'
    excluded=json.loads(excluded_path.read_text(encoding='utf-8')) if excluded_path.exists() else []
    all_queued=combine(queue,excluded)
    active_codes={s['stock_code'] for s in stocks}
    queue=[r for r in all_queued if r['stock_code'] in active_codes]
    excluded=[r for r in all_queued if r['stock_code'] not in active_codes]
    # Persist active rows before replacing the excluded file, to preserve reactivated rows on interruption.
    write_json(queue_path,all_queued)
    write_json(excluded_path,excluded)
    write_json(queue_path,queue)
    print(f'뉴스 수집 시작: {len(stocks)}종목',flush=True)
    # Resume after the last requested stock if a previous run stopped mid-sweep.
    cursor_path=directory/'cursor.json'
    start=json.loads(cursor_path.read_text(encoding='utf-8')) if cursor_path.exists() else 0
    for i in range(len(stocks)):
        index=(start+i)%len(stocks);stock=stocks[index]
        try:
            items=fetcher(1,100,query_text=stock['query'],before_request=budget.charge)
            fetched+=1;incoming=[]
            if len(items)==100:capped.append(stock['stock_code'])
            for item in items:
                try:
                    row=normalize(item,stock)
                    if row:incoming.append(row)
                except (ValueError,KeyError,TypeError,OverflowError):invalid+=1
            queue=combine(queue,incoming)
            write_json(queue_path,queue)
        except Exception as exc:
            errors.append(dict(stock_code=stock['stock_code'],**error_summary(exc)))
            if isinstance(exc,BudgetExceeded):break
        write_json(cursor_path,(index+1)%len(stocks))
        if (i+1)%10==0 or i+1==len(stocks):
            print(f'뉴스 조회 {i+1}/{len(stocks)}종목 · 대기 {len(queue)}건 · 오류 {len(errors)}건',flush=True)
    print(f'기존 DB 결과와 중복 확인 중: {len(queue)}건',flush=True)
    pending=store.pending(queue,predictor.version)
    print(f'신규 예측·저장 대상: {len(pending)}건',flush=True)
    saved=[]
    # Persist progress per small batch, keeping memory bounded and allowing restart.
    for offset in range(0,len(pending),64):
        batch=pending[offset:offset+64];predictions=predictor.predict(batch)
        store.acquire();store.save_verified(batch,predictions,predictor.version)
        saved.extend(dict(r,model_version=predictor.version,**p) for r,p in zip(batch,predictions))
        print(f'예측·DB 저장 확인: {len(saved)}/{len(pending)}건',flush=True)
    if saved:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        write_json(directory/'batches'/(stamp+'.json'),saved)
        write_json(directory/'latest-batch.json',saved)
    write_json(queue_path,[])
    return dict(state='partial' if errors else 'ok',checked_at_utc=datetime.now(timezone.utc).isoformat(),
                stocks=len(stocks),fetched_stocks=fetched,predicted_and_saved=len(saved),invalid=invalid,
                capped_stocks=capped,excluded_pending=len(excluded),errors=errors,model_version=predictor.version,database=os.getenv('STOCKPILOT_DB_NAME','stockpilot_db'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default='models/final-stockpilot-news-v1')
    p.add_argument('--universe',type=Path,default=DEFAULT_UNIVERSE)
    p.add_argument('--check-universe',action='store_true')
    p.add_argument('--interval-minutes',type=int,default=15);p.add_argument('--pages',type=int,default=1)
    p.add_argument('--once',action='store_true');a=p.parse_args()
    if a.check_universe:
        universe=load_universe(a.universe)
        print(json.dumps(dict(stocks=len(universe['stocks']),source_file=universe['source_file'],source_snapshot=universe['source_snapshot'],source_sha256=universe['source_sha256'],db_accessed=False,api_called=False),ensure_ascii=False))
        return
    if not 15<=a.interval_minutes<=1440 or a.pages!=1:p.error('200 stocks require interval >=15 minutes and pages=1')
    if not all(os.getenv(k) for k in ('NAVER_CLIENT_ID','NAVER_CLIENT_SECRET')):p.error('NAVER credentials required in environment')
    print('최종 모델을 불러오는 중입니다.',flush=True)
    from sentiment_runtime import Predictor
    directory=Path('data/live200');directory.mkdir(parents=True,exist_ok=True)
    predictor=Predictor(a.model);store=TargetStore();budget=Budget(directory/'request-budget.json')
    exit_code=0;owned=False
    try:
        store.acquire();owned=True
        write_json(directory/'process-state.json',dict(state='running'))
        while True:
            start=time.monotonic()
            try:
                print('주식 수집기와 공통으로 사용하는 200종목 목록 확인 중입니다.',flush=True)
                universe=load_universe(a.universe)
                write_json(directory/'universe.json',universe)
                status=run_cycle(directory,predictor,store,universe['stocks'],budget)
                status.update(universe_source=universe['source_file'],universe_sha256=universe['source_sha256'],universe_snapshot=universe['source_snapshot'])
            except Exception as exc:
                status=dict(state='error',checked_at_utc=datetime.now(timezone.utc).isoformat(),error=error_summary(exc))
            status['interval_minutes']=a.interval_minutes
            write_json(directory/'status.json',status);write_report(directory,status)
            print(json.dumps(status,ensure_ascii=False),flush=True)
            exit_code=int(status['state']!='ok')
            if a.once:break
            time.sleep(max(1,a.interval_minutes*60-(time.monotonic()-start)))
    except KeyboardInterrupt: print('수집 종료. 저장 결과와 대기 목록을 유지합니다.',flush=True)
    finally:
        store.close()
        if owned:write_json(directory/'process-state.json',dict(state='stopped'))
    raise SystemExit(exit_code if a.once else 0)

if __name__=='__main__':main()
