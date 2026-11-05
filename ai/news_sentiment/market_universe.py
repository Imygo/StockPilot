"""KIS full market master -> market-cap top 100 each. No production DB access."""
import io
import json
import re
import zipfile
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import urlopen
from news import digest
from live_worker import write_json

MASTER={'KOSPI':('kospi',227,212), 'KOSDAQ':('kosdaq',221,206)}
KST=timezone(timedelta(hours=9))

def parse_master(content, market):
    _,width,offset=MASTER[market]
    rows=[]
    for line in content.decode('cp949').splitlines():
        if not line: continue
        if len(line)<width+22: raise ValueError('Master layout mismatch')
        prefix,tail=line[:-width],line[-width:]
        code=prefix[:9].strip()
        if tail[:2]!='ST': continue
        if not re.fullmatch('[0-9A-Z]{6}',code): raise ValueError('Invalid stock code')
        cap=tail[offset:offset+9].strip()
        if not cap.isdigit(): raise ValueError('Invalid market cap')
        name=prefix[21:].strip()
        if not name: raise ValueError('Missing stock name')
        rows.append(dict(stock_code=code,stock_name=name,market=market,market_cap=int(cap)))
    if len({r['stock_code'] for r in rows})!=len(rows): raise ValueError('Duplicate stock codes')
    return sorted(rows,key=lambda r:(-r['market_cap'],r['stock_code']))

def refresh(path, opener=urlopen):
    all_rows=[]; sources=[]
    for market,(stem,_,_) in MASTER.items():
        url=f'https://new.real.download.dws.co.kr/common/master/{stem}_code.mst.zip'
        with opener(url,timeout=30) as response:
            content=response.read(10_000_001)
            modified=response.headers.get('Last-Modified')
        if len(content)>10_000_000 or not modified: raise ValueError('Invalid master response')
        age=datetime.now(timezone.utc)-parsedate_to_datetime(modified)
        if not timedelta(days=-1)<age<timedelta(days=7): raise ValueError('Master source is stale')
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            info=z.getinfo(stem+'_code.mst')
            if info.file_size>20_000_000: raise ValueError('Master size exceeded')
            rows=parse_master(z.read(info),market)
        if len(rows)<100 or rows[99]['market_cap']<=0: raise ValueError('Incomplete market ranking')
        names={r['stock_name'] for r in rows}
        for rank,row in enumerate(rows[:100],1):
            name=row['stock_name']
            # Only map preferred shares when a matching ordinary-share name exists in the same master.
            base=re.sub(r'(?:[0-9]+)?우(?:B)?$','',name)
            aspect=base if base!=name and base in names else name
            all_rows.append(dict(row,rank=rank,aspect=aspect,query=aspect))
        sources.append(dict(market=market,url=url,last_modified=modified,eligible=len(rows)))
    if len({r['stock_code'] for r in all_rows})!=200: raise ValueError('Expected 200 unique stocks')
    result=dict(basis='KIS master market cap descending; ST incl preferred; no volume filter',
                refreshed_date=datetime.now(KST).date().isoformat(),sources=sources,stocks=all_rows)
    write_json(path,result)
    return result

def daily_universe(path):
    path=Path(path)
    if path.exists():
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('refreshed_date')==datetime.now(KST).date().isoformat():
            rows=data.get('stocks',[])
            if len({r['stock_code'] for r in rows})==200 and all(sum(r['market']==m for r in rows)==100 for m in MASTER):
                return data
    return refresh(path)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='data/live200/universe.json');a=p.parse_args()
    result=refresh(a.output)
    print(json.dumps(dict(count=len(result['stocks']),date=result['refreshed_date'],sources=result['sources']),ensure_ascii=False))
