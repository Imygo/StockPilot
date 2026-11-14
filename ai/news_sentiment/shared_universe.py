"""Read the same fixed universe used by stock registration and chart collectors."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

DEFAULT_UNIVERSE=Path(__file__).resolve().parents[1]/'data/top200-20261012.json'

def load_universe(path=DEFAULT_UNIVERSE):
    path=Path(path)
    raw=path.read_bytes()
    data=json.loads(raw.decode('utf-8-sig'))
    symbols=data.get('symbols')
    if not isinstance(symbols,list) or len(symbols)!=200:
        raise ValueError('Expected the shared universe with 200 symbols')
    seen=set();rows=[]
    for row in symbols:
        if not isinstance(row,dict):raise ValueError('Invalid universe row')
        code,name,market=row.get('stock_code'),row.get('name'),row.get('exchange')
        if not isinstance(code,str) or not re.fullmatch('[0-9A-Z]{6}',code) or code in seen:
            raise ValueError('Invalid or duplicate stock code')
        if not isinstance(name,str) or not name.strip() or len(name)>100:
            raise ValueError('Invalid stock name')
        if market not in ('KOSPI','KOSDAQ'):raise ValueError('Invalid market')
        rows.append(dict(stock_code=code,stock_name=name.strip(),market=market))
        seen.add(code)
    if Counter(r['market'] for r in rows)!={'KOSPI':100,'KOSDAQ':100}:
        raise ValueError('Expected KOSPI 100 and KOSDAQ 100')
    names={(r['market'],r['stock_name']) for r in rows}
    for row in rows:
        name=row['stock_name'];base=re.sub(r'(?:[0-9]+)?우(?:B)?$','',name)
        aspect=base if base!=name and (row['market'],base) in names else name
        row.update(aspect=aspect,query=aspect)
    return dict(basis='shared_stock_universe',source_file=path.name,
                source_sha256=hashlib.sha256(raw).hexdigest(),source_snapshot=data.get('snapshot_time'),stocks=rows)
