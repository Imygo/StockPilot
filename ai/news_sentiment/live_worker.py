import json
import html
from pathlib import Path
from database import connect


def write_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)

def error_summary(exc):
    # Never serialize request headers, credentials, SQL text or server error bodies.
    code=exc.args[0] if exc.args and isinstance(exc.args[0],int) else None
    return {'type':type(exc).__name__,'code':code}

def write_report(directory,status):
    path=Path(directory)/'latest-batch.json'
    latest=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    names={'negative':'부정','neutral':'중립','positive':'긍정'}
    content='<h1>자동 수집 상태</h1><p>마지막 확인: '+html.escape(status.get('checked_at_utc',''))+' (UTC)</p>'
    content+='<pre>'+html.escape(json.dumps(status,ensure_ascii=False,indent=2))+'</pre><h2>마지막으로 새로 저장한 기사</h2>'
    content+='<p>아래 목록은 전체 DB가 아닌 마지막 신규 저장 묶음입니다. 새로고침하면 최신 저장 결과가 표시됩니다.</p><table><tr><th>제목</th><th>예측</th><th>확률</th></tr>'
    for row in latest:
        target=html.escape(row.get('stock_name','삼성전자'))+' ('+html.escape(row.get('stock_code','005930'))+')'
        content+=f'<tr><td>{target}<br>{html.escape(row["title"])}</td><td>{names[row["label"]]}</td><td>{row[row["label"]]:.1%}</td></tr>'
    content+='</table>'
    Path(directory,'live-results.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>StockPilot 자동 수집 상태</title><style>body{font:16px/1.6 sans-serif;max-width:1100px;margin:30px auto;padding:20px}td,th{border-bottom:1px solid #ddd;padding:10px;text-align:left}pre{background:#f1f4f8;padding:15px;white-space:pre-wrap}</style>'+content+'</html>',encoding='utf-8')

class Store:

    def __init__(self):
        self.lock = None

    def acquire(self):
        if self.lock is not None:
            try:
                self.lock.ping(reconnect=False)
                with self.lock.cursor() as cur:
                    cur.execute("SELECT IS_USED_LOCK('stockpilot_news_worker_v1')=CONNECTION_ID()")
                    if cur.fetchone()[0] == 1:
                        return
            except Exception:
                pass
            self.close()
        self.lock = connect()
        with self.lock.cursor() as cur:
            cur.execute("SELECT GET_LOCK('stockpilot_news_worker_v1',0)")
            if cur.fetchone()[0] != 1:
                self.close()
                raise RuntimeError('Another worker holds the development DB lock')

    def close(self):
        if self.lock:
            self.lock.close()
            self.lock = None
