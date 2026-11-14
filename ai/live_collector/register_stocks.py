"""Register the existing 200-stock universe. Default preview; --write inserts missing rows only."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
INSERT_MISSING = '''INSERT INTO stock (stock_code,stock_name,market)
SELECT %s,%s,%s WHERE NOT EXISTS (SELECT 1 FROM stock WHERE stock_code=%s)'''

def load_symbols(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    raw = data.get('symbols')
    if not isinstance(raw, list) or len(raw) != 200:
        raise ValueError('Expected exactly 200 symbols in the existing universe file')
    result=[]; seen=set()
    for row in raw:
        if not isinstance(row,dict): raise ValueError('Invalid universe row')
        code,name,market=row.get('stock_code'),row.get('name'),row.get('exchange')
        if not isinstance(code,str) or not re.fullmatch(r'[0-9A-Z]{6}',code) or code in seen:
            raise ValueError('Invalid or duplicate stock code')
        if not isinstance(name,str) or not name.strip() or len(name)>100:
            raise ValueError('Invalid stock name')
        if market not in ('KOSPI','KOSDAQ'): raise ValueError('Invalid market')
        result.append((code,name.strip(),market));seen.add(code)
    if Counter(r[2] for r in result) != {'KOSPI':100,'KOSDAQ':100}:
        raise ValueError('Expected KOSPI 100 and KOSDAQ 100')
    return result,data.get('snapshot_time')

def register(connection, rows):
    added=0; differences=[]
    try:
        with connection.cursor() as cur:
            for code,name,market in rows:
                cur.execute(INSERT_MISSING,(code,name,market,code))
                added+=cur.rowcount
            for code,name,market in rows:
                cur.execute('SELECT stock_name,market FROM stock WHERE stock_code=%s',(code,))
                found=cur.fetchone()
                if found is None: raise RuntimeError('Stock registration read-back failed')
                if tuple(found)!=(name,market):differences.append(code)
        connection.commit()
    except BaseException:
        connection.rollback();raise
    return dict(requested=len(rows),inserted=added,already_present=len(rows)-added,
                verified=len(rows),existing_metadata_differences=differences,
                quote_fields_changed=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--universe',type=Path,default=BASE.parent/'data/top200-20261012.json')
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    try:
        rows,snapshot=load_symbols(args.universe)
        if not args.write:
            print(json.dumps(dict(mode='preview',stocks=len(rows),markets=dict(Counter(r[2] for r in rows)),
                source_snapshot=snapshot,db_accessed=False),ensure_ascii=False))
            print('기본정보 등록: 같은 명령에 --write를 추가하세요. 기존 종목과 시세는 변경하지 않습니다.')
            return 0
        from dotenv import load_dotenv
        from collector import connect
        load_dotenv(BASE/'.env',override=False)
        connection=connect()
        try:result=register(connection,rows)
        finally:connection.close()
        print(json.dumps(dict(state='ok',source_snapshot=snapshot,**result),ensure_ascii=False))
        print('등록 완료. 홈 화면을 새로고침하세요. 현재가·시가총액은 별도 수집이 필요합니다.')
        return 0
    except Exception as exc:
        code=exc.args[0] if exc.args and isinstance(exc.args[0],int) else None
        print(json.dumps(dict(state='error',error_type=type(exc).__name__,mysql_code=code)))
        return 1

if __name__=='__main__':raise SystemExit(main())
