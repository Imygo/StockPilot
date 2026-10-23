"""체결 CSV를 분봉으로 집계하여 기존 minute_chart_data에 저장한다."""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import csv
from datetime import datetime
from pathlib import Path
import sys
from import_daily import connect_db, numeric

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "tick"
REQUIRED = ("MKSC_SHRN_ISCD", "BSOP_DATE", "STCK_CNTG_HOUR", "STCK_PRPR",
            "ACML_VOL", "PRDY_VRSS", "PRDY_CTRT", "PRDY_VRSS_SIGN")
SQL = """
INSERT INTO minute_chart_data
(stock_code,candle_start,close_price,volume,change_amount,change_rate,open_price,high_price,low_price)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE close_price=VALUES(close_price),volume=VALUES(volume),
change_amount=VALUES(change_amount),change_rate=VALUES(change_rate),
open_price=VALUES(open_price),high_price=VALUES(high_price),low_price=VALUES(low_price),
updated_at=CURRENT_TIMESTAMP
"""

def required_number(row, source, target):
    result = numeric(row[source], target)
    if result is None:
        raise ValueError(f"{source}가 비어 있습니다.")
    return result

def load_minutes(files):
    """전체 CSV 검증 후 시간/누적량 순서로 집계한다. 원본 파일은 수정하지 않는다."""
    ticks = {}
    total = 0
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            if not header:
                continue  # 연결 실패 등으로 생성된 빈 CSV
            if len(header) != len(set(header)) or set(REQUIRED) - set(header):
                raise ValueError(f"{path.name}: 필수 체결 컬럼이 없거나 헤더가 중복됩니다.")
            for line, row in enumerate(reader, 2):
                try:
                    if None in row or any(row[key] is None for key in REQUIRED):
                        raise ValueError("CSV 필드 수가 맞지 않습니다.")
                    code = row["MKSC_SHRN_ISCD"].strip()
                    if not code or len(code) > 15:
                        raise ValueError("종목코드는 1~15자리 문자열이어야 합니다.")
                    day, clock = row["BSOP_DATE"].strip(), row["STCK_CNTG_HOUR"].strip()
                    if len(day) != 8 or len(clock) != 6 or not (day + clock).isdigit():
                        raise ValueError("날짜/시간은 YYYYMMDD/HHMMSS 형식이어야 합니다.")
                    stamp = datetime.strptime(day + clock, "%Y%m%d%H%M%S")
                    if stamp.year < 1000:
                        raise ValueError("MySQL DATETIME 범위를 벗어났습니다.")
                    price = required_number(row, "STCK_PRPR", "close_price")
                    volume = required_number(row, "ACML_VOL", "volume")
                    amount = required_number(row, "PRDY_VRSS", "change_amount")
                    rate = required_number(row, "PRDY_CTRT", "change_rate")
                    sign = row["PRDY_VRSS_SIGN"].strip()
                    if sign not in ("1", "2", "3", "4", "5"):
                        raise ValueError("전일 대비 부호 코드가 올바르지 않습니다.")
                    if sign in ("4", "5"):
                        amount, rate = -abs(amount), -abs(rate)
                    elif sign in ("1", "2"):
                        amount, rate = abs(amount), abs(rate)
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{path.name}:{line}행: {exc}") from exc
                ticks[(code, stamp, volume)] = (price, amount, rate)
                total += 1
    candles = {}
    for (code, stamp, volume), (price, amount, rate) in sorted(ticks.items()):
        minute = stamp.replace(second=0)
        key = (code, minute)
        if key not in candles:
            candles[key] = [code, minute, price, volume, amount, rate, price, price, price]
        else:
            candle = candles[key]
            candle[2:6] = [price, volume, amount, rate]
            candle[7] = max(candle[7], price)
            candle[8] = min(candle[8], price)
    return [tuple(candles[key]) for key in sorted(candles)], total, len(ticks)

def save_minutes(connection, rows):
    try:
        with connection.cursor() as cursor:
            for offset in range(0, len(rows), 500):
                cursor.executemany(SQL, rows[offset:offset + 500])
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


async def receive_for_duration(ws, columns, recorder, collector, seconds=60):
    """구독 요청 후 seconds 동안 수신. 타임아웃 때만 정상 종료한다."""
    deadline = asyncio.get_running_loop().time() + seconds
    count = 0
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return count
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return count
        if isinstance(raw, bytes):
            raw = raw.decode()
        if raw.startswith("0|"):
            # 전체 47개 필드를 CSV에 보존한다. DB는 수집 종료 후에만 접근한다.
            frame = collector.websocket_to_dataframe_csv(raw, columns, recorder)
            count += len(frame)
            if count == len(frame) and count:
                print(f"첫 체결 수신: {count}건 / {len(frame.columns)}컬럼")
        else:
            message = json.loads(raw)
            if message.get("header", {}).get("tr_id") == "PINGPONG":
                await ws.pong(raw.encode())
            elif message.get("body", {}).get("rt_cd") not in (None, "0"):
                raise RuntimeError("웹소켓 구독 실패: " + str(message["body"].get("msg_cd")))
            elif message.get("body", {}).get("rt_cd") == "0":
                print("모의투자 구독 승인")


async def collect_session(collector, auth, subscribe, recorder, code):
    import websockets
    url = auth.getTREnv().my_url_ws.rstrip("/") + "/tryitout"
    async with websockets.connect(url, open_timeout=15, ping_interval=None) as ws:
        message, columns = subscribe("1", code, env_dv="demo")
        await ws.send(json.dumps(message))
        print(f"연결 성공. {code} 체결을 지금부터 60초 동안 수집합니다.")
        return await receive_for_duration(ws, columns, recorder, collector)


def collect_one_minute(code, auth_file=None):
    # 현재 프로젝트의 기존 수집기와 인증 설정을 재사용한다.
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    import data_collector as collector
    path = auth_file or Path(os.getenv("KIS_AUTH_FILE", str(collector.DEFAULT_AUTH_FILE)))
    auth = collector.load_module("kis_auth", path)
    auth._DEBUG = False
    collector.configure_paper_auth(auth)
    auth.auth_ws(svr="vps", product="01")
    collector.verify_paper_session(auth)
    if not auth._base_headers_ws.get("approval_key"):
        raise RuntimeError("모의투자 웹소켓 인증 실패")
    subscribe = collector.load_module(
        "minute_import_ccnl", collector.ROOT / "examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py"
    ).ccnl_krx
    output = DEFAULT_DIRECTORY / f"ticks_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    recorder = collector.TickRecorder(output)
    print(f"원본 CSV: {output}")
    try:
        count = asyncio.run(collect_session(collector, auth, subscribe, recorder, code))
        print(f"60초 수집 종료: {count}건")
    finally:
        recorder.close()
    return output


def main():
    parser = argparse.ArgumentParser(description="60초 모의투자 체결 수집 후 분봉 DB 저장")
    parser.add_argument("--code", default="005930", help="수집 종목 (기본 삼성전자)")
    parser.add_argument("--auth-file", type=Path, help="kis_auth.py 경로")
    parser.add_argument("--from-csv", action="store_true", help="수집 없이 기존 CSV 전체를 가져오기")
    parser.add_argument("--directory", type=Path, help="기존 CSV 폴더 (API 수집 생략)")
    parser.add_argument("--file", type=Path, help="기존 CSV 한 개 (API 수집 생략)")
    parser.add_argument("--dry-run", action="store_true", help="기존 CSV만 검증. API/DB 접속 없음")
    args = parser.parse_args()
    if not args.code or len(args.code) > 15:
        parser.error("--code는 1~15자리 종목코드여야 합니다.")
    offline = args.from_csv or args.directory is not None or args.file is not None or args.dry_run
    if offline:
        directory = args.directory or DEFAULT_DIRECTORY
        files = [args.file.resolve()] if args.file else sorted(directory.resolve().glob("ticks_*.csv"))
        if not files:
            parser.error("ticks_*.csv 파일이 없습니다.")
    else:
        # 이전 파일을 섞지 않고 이번 60초 동안 수집한 파일만 저장한다.
        files = [collect_one_minute(args.code, args.auth_file)]
    rows, total, unique = load_minutes(files)
    print(f"CSV {len(files)}개 / 체결 {total}행 / 중복 제외 {unique}행 / 분봉 {len(rows)}행")
    for row in rows[:5]:
        print(f"{row[0]} {row[1]} O={row[6]} H={row[7]} L={row[8]} C={row[2]} 누적거래량={row[3]}")
    if args.dry_run:
        print("검증 완료. API/DB 접속 및 저장은 하지 않았습니다.")
        return
    if not rows:
        print("수신 체결이 없어 DB에 저장하지 않습니다. 거래 시간과 구독 상태를 확인하세요.")
        return
    connection = connect_db()
    try:
        save_minutes(connection, rows)
    finally:
        connection.close()
    print(f"minute_chart_data 저장 완료: {len(rows)}개 종목·분 키 (삽입 또는 갱신)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("중단했습니다.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        if type(exc).__module__.startswith("pymysql"):
            print(f"MySQL 오류 ({type(exc).__name__}). 연결/권한/테이블을 확인하세요.", file=sys.stderr)
        else:
            print(f"저장 실패: {exc}", file=sys.stderr)
        sys.exit(1)
