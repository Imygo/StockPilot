"""KIS 국내주식 -> 기존 StockPilot MySQL 테이블. 사용법: README.md.

인증 파일은 실행 시에만 로드한다. import 또는 --help는 인증/DB 접속을 하지 않는다.
삼성전자 기본정보는 없으면 등록하며, 테이블을 생성하거나 변경하지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import getpass
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTH_FILE = ROOT / "Test_Project" / "kis_auth.py"
LOG = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent / "data"
TICK_DIR = DATA_DIR / "tick"
DAILY_DIR = DATA_DIR / "daily"
TICK_FIELDS = ["MKSC_SHRN_ISCD", "BSOP_DATE", "STCK_CNTG_HOUR", "STCK_PRPR",
               "ACML_VOL", "PRDY_VRSS", "PRDY_VRSS_SIGN", "PRDY_CTRT"]
DAILY_FIELDS = ["stock_code", "trade_date", "close_price", "volume", "change_amount",
                "change_rate", "open_price", "high_price", "low_price"]
PAPER_REST = "https://openapivts.koreainvestment.com:29443"
PAPER_WS = "ws://ops.koreainvestment.com:31000"


def configure_paper_auth(auth):
    """인증 요청 전에 모의 서버/키 설정을 확인하고 공용 토큰 캐시를 분리한다."""
    cfg = auth.getEnv()
    if cfg.get("vps", "").rstrip("/") != PAPER_REST or cfg.get("vops", "").rstrip("/") != PAPER_WS:
        raise ValueError("auth.yaml의 vps/vops가 모의투자 서버가 아닙니다. 접속을 중단합니다.")
    for key in ("paper_app", "paper_sec", "my_paper_stock"):
        if not cfg.get(key):
            raise ValueError(f"auth.yaml에 모의투자 설정 {key}가 필요합니다.")
    auth._autoReAuth = False
    auth.token_tmp = str(Path(auth.config_root) / f"KIS_demo_{date.today():%Y%m%d}")
    LOG.warning("모의투자 전용 | REST=%s | WebSocket=%s | 주문 기능 없음", PAPER_REST, PAPER_WS)


def verify_paper_session(auth):
    env = auth.getTREnv()
    if (not auth.isPaperTrading() or env.my_url.rstrip("/") != PAPER_REST
            or env.my_url_ws.rstrip("/") != PAPER_WS):
        raise RuntimeError("모의투자 인증 환경 검증 실패. 수집을 중단합니다.")


def number(value):
    if value is None or str(value).strip() == "":
        raise ValueError("필수 숫자 필드가 비어 있습니다.")
    result = Decimal(str(value).replace(",", ""))
    if not result.is_finite():
        raise ValueError("유효하지 않은 숫자입니다.")
    return result


def integer(value):
    result = number(value)
    if result != result.to_integral_value():
        raise ValueError("정수 필드에 소수가 들어 있습니다.")
    return int(result)


def changes(row, close=None):
    amount = number(row["prdy_vrss"])
    sign = str(row.get("prdy_vrss_sign", ""))
    if sign in ("4", "5"):
        amount = -abs(amount)
    elif sign in ("1", "2"):
        amount = abs(amount)
    if row.get("prdy_ctrt") not in (None, ""):
        rate = number(row["prdy_ctrt"])
        if sign in ("4", "5"):
            rate = -abs(rate)
        elif sign in ("1", "2"):
            rate = abs(rate)
    else:
        # 기간별시세 output2에는 prdy_ctrt가 없으므로 전일 종가로 계산한다.
        previous = number(close) - amount
        rate = amount / previous * 100 if previous else None
    return amount, rate


def daily_values(code, row):
    close = integer(row["stck_clpr"])
    amount, rate = changes(row, close)
    return (code, datetime.strptime(row["stck_bsop_date"], "%Y%m%d").date(),
            close, integer(row["acml_vol"]), amount, rate,
            integer(row["stck_oprc"]), integer(row["stck_hgpr"]),
            integer(row["stck_lwpr"]))


def tick_values(row):
    stamp = datetime.strptime(row["BSOP_DATE"] + row["STCK_CNTG_HOUR"], "%Y%m%d%H%M%S")
    amount, rate = changes({k.lower(): v for k, v in row.items()})
    return (row["MKSC_SHRN_ISCD"], stamp.replace(second=0),
            integer(row["STCK_PRPR"]), integer(row["ACML_VOL"]), amount, rate)


class TickRecorder:
    """전체 DataFrame 컬럼을 보존한다. 기존 파일에는 덮어쓰지 않는다."""
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("x", encoding="utf-8-sig", newline="")
        self.columns = None

    def write(self, row):
        self.write_frame(pd.DataFrame([row], dtype=str))

    def write_frame(self, frame):
        if frame.empty:
            return
        columns = list(frame.columns)
        if self.columns is not None and columns != self.columns:
            raise ValueError("CSV 기록 중 전체 수신 컬럼 구성이 변경되었습니다.")
        try:
            frame.to_csv(self.file, index=False, header=self.columns is None)
            self.file.flush()
            self.columns = columns
        except OSError as exc:
            raise RuntimeError("체결 CSV 저장 실패. 디스크 공간과 파일 접근 권한을 확인하세요.") from exc

    def close(self):
        self.file.close()

    def record_raw(self, raw):
        # 체결 프레임만 기록한다. 승인키가 포함된 JSON 제어 메시지는 저장하지 않는다.
        path = self.path.with_suffix(".raw.jsonl")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"received_at": datetime.now().isoformat(), "raw": raw},
                                    ensure_ascii=False) + "\n")


def websocket_to_dataframe_csv(raw, columns, recorder):
    """1. 전체 수신 컬럼을 문자열 DataFrame으로 구성하고 CSV에 기록한다."""
    recorder.record_raw(raw)
    rows = parse_ticks(raw, columns)
    output_columns = list(columns)
    if is_krx_base_columns(columns):
        output_columns.append("EXTRA_FIELD_47")
    frame = pd.DataFrame(rows, columns=output_columns, dtype=str).fillna("")
    recorder.write_frame(frame)
    return frame


def save_dataframe_to_tables(frame, store, codes=None):
    """2. DB 변환에 필요한 컬럼만 선택하여 stock/분봉 테이블에 저장한다.

    Store.tick에서 현재가/등락/누적량을 매핑하고, 분별 OHLC를 집계한다.
    원본 46개 컬럼은 DB에 임의로 추가하지 않는다.
    """
    missing = set(TICK_FIELDS) - set(frame.columns)
    if missing:
        raise ValueError(f"DB 변환 필수 컬럼 누락: {', '.join(sorted(missing))}")
    selected = frame.loc[:, TICK_FIELDS]
    if codes is not None:
        selected = selected[selected["MKSC_SHRN_ISCD"].isin(codes)]
    rows = selected.to_dict(orient="records")
    for row in rows:
        tick_values(row)  # 배치 전체를 검증한 뒤 DB 저장 시작
    for row in rows:
        store.tick(row)
    return len(rows)


def replay_csv(source, output, codes):
    """인증/DB 없이 CSV 체결을 수신 순서대로 집계하여 별도 분봉 CSV를 만든다."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise ValueError("입력 CSV와 출력 CSV는 달라야 합니다.")
    candles, latest = {}, {}
    count = 0
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(TICK_FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("체결 CSV에 필요한 컬럼이 없습니다. stream으로 저장한 파일을 사용하세요.")
        for line, row in enumerate(reader, 2):
            if row["MKSC_SHRN_ISCD"] not in codes:
                continue
            try:
                code, minute, price, volume, amount, rate = tick_values(row)
            except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                raise ValueError(f"CSV {line}행의 체결 데이터가 잘못되었습니다.") from exc
            previous = latest.get(code)
            if previous and (minute < previous[0] or (minute == previous[0] and volume <= previous[1])):
                continue
            latest[code] = (minute, volume)
            key = (code, minute)
            if key not in candles:
                candles[key] = dict(stock_code=code, candle_start=minute,
                                    open_price=price, high_price=price, low_price=price)
            candle = candles[key]
            candle.update(close_price=price, volume=volume, change_amount=amount, change_rate=rate,
                          high_price=max(candle["high_price"], price), low_price=min(candle["low_price"], price))
            count += 1
    if not candles:
        raise ValueError("선택 종목의 체결 데이터가 없습니다.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_code", "candle_start", "open_price",
            "high_price", "low_price", "close_price", "volume", "change_amount", "change_rate"])
        writer.writeheader()
        writer.writerows(candles[key] for key in sorted(candles))
    LOG.warning("CSV 재생 완료: %s개 체결 → %s개 분봉 | %s", count, len(candles), output)
    return len(candles)


def load_module(name, path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"파일이 없습니다: {path}. --auth-file로 실제 경로를 지정하세요.")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def connect_db():
    import pymysql
    password = os.environ.get("MYSQL_PASSWORD")
    if password is None:
        password = getpass.getpass("StockPilot MySQL 비밀번호: ")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"), password=password,
        database=os.getenv("MYSQL_DATABASE", "stockpilot_db"),
        charset="utf8mb4", autocommit=False, connect_timeout=10,
        read_timeout=30, write_timeout=30,
    )


DAILY_SQL = """
INSERT INTO daily_chart_data
(stock_code, trade_date, close_price, volume, change_amount, change_rate,
 open_price, high_price, low_price) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE close_price=VALUES(close_price), volume=VALUES(volume),
change_amount=VALUES(change_amount), change_rate=VALUES(change_rate),
open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price),
updated_at=CURRENT_TIMESTAMP
"""


class Store:
    def __init__(self, connection):
        self.db = connection

    def codes(self, requested=None):
        with self.db.cursor() as cur:
            cur.execute("SELECT stock_code FROM stock ORDER BY stock_code")
            existing = [str(row[0]) for row in cur.fetchall()]
        self.db.commit()
        selected = list(dict.fromkeys(requested or existing))
        missing = set(selected) - set(existing)
        if missing:
            raise ValueError(f"stock에 기본정보를 먼저 등록하세요: {', '.join(sorted(missing))}")
        if not selected:
            raise ValueError("stock 테이블에 수집할 종목이 없습니다.")
        return selected

    def ensure_samsung(self):
        with self.db.cursor() as cur:
            cur.execute("""INSERT INTO stock (stock_code,stock_name,market)
                VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE
                stock_name=VALUES(stock_name), market=VALUES(market)""",
                ("005930", "삼성전자", "KOSPI"))
        self.db.commit()

    def snapshot(self, code, row):
        amount, rate = changes(row)
        with self.db.cursor() as cur:
            cur.execute("""UPDATE stock SET current_price=%s, marketCap=%s,
                change_amount=%s, change_rate=%s, volume=%s,
                updated_at=CURRENT_TIMESTAMP WHERE stock_code=%s""",
                (integer(row["stck_prpr"]), integer(row["hts_avls"]),
                 amount, rate, integer(row["acml_vol"]), code))
        self.db.commit()

    def daily(self, rows):
        if rows:
            with self.db.cursor() as cur:
                cur.executemany(DAILY_SQL, rows)
            self.db.commit()

    def tick(self, row):
        code, minute, price, volume, amount, rate = tick_values(row)
        with self.db.cursor() as cur:
            # 재시작/중복 수신 시 이미 저장한 누적 거래량을 기준으로 중복을 제거한다.
            cur.execute("""SELECT candle_start, volume FROM minute_chart_data
                WHERE stock_code=%s ORDER BY candle_start DESC LIMIT 1 FOR UPDATE""", (code,))
            latest = cur.fetchone()
            if latest and (minute < latest[0] or
                           (minute == latest[0] and volume <= latest[1])):
                self.db.commit()
                return
            cur.execute("""INSERT INTO minute_chart_data
                (stock_code,candle_start,close_price,volume,change_amount,change_rate,
                 open_price,high_price,low_price) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE close_price=VALUES(close_price),
                volume=VALUES(volume), change_amount=VALUES(change_amount),
                change_rate=VALUES(change_rate),
                high_price=GREATEST(high_price,VALUES(high_price)),
                low_price=LEAST(low_price,VALUES(low_price)), updated_at=CURRENT_TIMESTAMP""",
                (code, minute, price, volume, amount, rate, price, price, price))
            cur.execute("""UPDATE stock SET current_price=%s, volume=%s,
                change_amount=%s, change_rate=%s, updated_at=CURRENT_TIMESTAMP
                WHERE stock_code=%s""", (price, volume, amount, rate, code))
        self.db.commit()

    def chart(self, code, start, end, period="D"):
        """저장된 일봉을 조회/집계한다. 기간 양 끝의 주/월봉은 부분 봉일 수 있다."""
        with self.db.cursor() as cur:
            cur.execute("""SELECT trade_date,close_price,volume,change_amount,change_rate,
                open_price,high_price,low_price FROM daily_chart_data
                WHERE stock_code=%s AND trade_date BETWEEN %s AND %s ORDER BY trade_date""",
                (code, start, end))
            names = [col[0] for col in cur.description]
            rows = [dict(zip(names, values)) for values in cur.fetchall()]
        self.db.commit()
        return aggregate_chart(rows, period)


def aggregate_chart(rows, period):
    if period not in ("D", "W", "M"):
        raise ValueError("period는 D/W/M이어야 합니다.")
    if period == "D":
        return rows
    groups = {}
    for row in rows:
        day = row["trade_date"]
        key = day.isocalendar()[:2] if period == "W" else (day.year, day.month)
        if key not in groups:
            groups[key] = dict(row)
            groups[key]["_previous_close"] = number(row["close_price"]) - number(row["change_amount"])
        else:
            candle = groups[key]
            candle["close_price"] = row["close_price"]
            candle["volume"] += row["volume"]
            candle["high_price"] = max(candle["high_price"], row["high_price"])
            candle["low_price"] = min(candle["low_price"], row["low_price"])
    for candle in groups.values():
        previous = candle.pop("_previous_close")
        candle["change_amount"] = number(candle["close_price"]) - previous
        candle["change_rate"] = candle["change_amount"] / previous * 100 if previous else None
    return list(groups.values())


class Collector:
    def __init__(self, auth, store, env, request_interval=1.1, max_retries=5):
        if env != "demo":
            raise ValueError("이 수집기는 모의투자(demo) 전용입니다.")
        if not math.isfinite(request_interval) or request_interval < 1:
            raise ValueError("request_interval은 1초 이상의 유한한 값이어야 합니다.")
        if not isinstance(max_retries, int) or not 0 <= max_retries <= 10:
            raise ValueError("max_retries는 0~10이어야 합니다.")
        self.auth, self.store, self.env = auth, store, env
        self.request_interval, self.max_retries = request_interval, max_retries
        self.next_request_at = time.monotonic() + request_interval

    def fetch(self, endpoint, tr_id, params):
        for attempt in range(self.max_retries + 1):
            verify_paper_session(self.auth)
            delay = self.next_request_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            try:
                response = self.auth._url_fetch("/uapi/domestic-stock/v1/quotations/" + endpoint,
                                                tr_id, "", params)
            finally:
                # 응답 완료 후 간격을 보장한다. 다른 종목/페이지도 이 제한을 공유한다.
                self.next_request_at = time.monotonic() + self.request_interval
            if response is not None and response.isOK():
                return response.getBody()
            code = response.getErrorCode() if response is not None else "NO_RESPONSE"
            # HTTP 500에서는 APIRespError가 msg_cd 대신 HTTP 상태를 반환한다.
            if response is not None and code != "EGW00201":
                try:
                    payload = json.loads(response.getErrorMessage())
                    if isinstance(payload, dict):
                        code = payload.get("msg_cd", code)
                except (ValueError, TypeError):
                    pass
            if code != "EGW00201" or attempt == self.max_retries:
                raise RuntimeError(f"KIS {endpoint} 요청 실패 ({code}). 저장을 중단합니다.")
            backoff = max(self.request_interval, min(2 ** (attempt + 1), 32))
            LOG.warning("호출 제한 EGW00201: %.1f초 후 동일 요청 재시도 (%s/%s)",
                        backoff, attempt + 1, self.max_retries)
            self.next_request_at = time.monotonic() + backoff

    def snapshot(self, codes):
        for code in codes:
            body = self.fetch("inquire-price", "FHKST01010100",
                              {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
            self.store.snapshot(code, body.output)
            LOG.warning("현재가 저장 완료: %s", code)

    def history(self, codes, start, end, csv_writer=None, csv_file=None):
        # 최대 100건 제한을 넘지 않도록 달력 기준 90일 단위로 전체 기간을 조회한다.
        for code in codes:
            cursor = start
            while cursor <= end:
                stop = min(cursor + timedelta(days=89), end)
                body = self.fetch("inquire-daily-itemchartprice", "FHKST03010100", {
                    "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                    "FID_INPUT_DATE_1": cursor.strftime("%Y%m%d"),
                    "FID_INPUT_DATE_2": stop.strftime("%Y%m%d"),
                    "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1",
                })
                rows = [daily_values(code, row) for row in body.output2
                        if row.get("stck_bsop_date")]
                rows = [row for row in rows if cursor <= row[1] <= stop]
                self.store.daily(rows)
                if csv_writer is not None:
                    csv_writer.writerows(rows)
                    csv_file.flush()
                LOG.warning("일봉 저장: %s %s~%s (%s건)", code, cursor, stop, len(rows))
                cursor = stop + timedelta(days=1)

    async def stream(self, codes, recorder):
        import websockets
        from websockets.exceptions import ConnectionClosed, InvalidHandshake
        if len(codes) > 40:
            raise ValueError("실시간 구독은 최대 40종목입니다.")
        ccnl = load_module("collector_ccnl_krx", ROOT / "examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py").ccnl_krx
        failures = 0
        while True:
            self.auth.auth_ws(svr="vps", product="01")
            verify_paper_session(self.auth)
            if not self.auth._base_headers_ws.get("approval_key"):
                raise RuntimeError("모의투자 웹소켓 인증에 실패했습니다.")
            # 모의투자 서버 루트 경로 사용: /tryitout은 HTTP 응답 없이 종료될 수 있다.
            url = self.auth.getTREnv().my_url_ws.rstrip("/") + "/"
            try:
                LOG.warning("웹소켓 연결 시도: %s (%s/5)", url, failures + 1)
                async with websockets.connect(url, proxy=None, open_timeout=15, ping_interval=None) as ws:
                    LOG.warning("웹소켓 연결 성공")
                    for code in codes:
                        message, columns = ccnl("1", code, env_dv=self.env)
                        await ws.send(json.dumps(message))
                        await asyncio.sleep(0.1)
                    LOG.warning("실시간 구독 요청 완료. Ctrl+C로 종료합니다.")
                    saved = 0
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            raw = raw.decode()
                        if raw.startswith("0|"):
                            try:
                                frame = websocket_to_dataframe_csv(raw, columns, recorder)
                            except (ValueError, KeyError, ArithmeticError) as exc:
                                LOG.error("체결 저장 제외: %s | 원본: %s", exc,
                                          recorder.path.with_suffix(".raw.jsonl"))
                                continue
                            try:
                                processed = save_dataframe_to_tables(frame, self.store, codes)
                            except (ValueError, KeyError, ArithmeticError) as exc:
                                LOG.error("전체 컬럼 CSV 저장 완료, DB 변환 제외: %s", exc)
                                continue
                            saved += processed
                            if processed:
                                LOG.info("체결 CSV 및 DB 처리 완료: 누적 %s건", saved)
                                if saved == processed:
                                    LOG.warning("첫 체결 저장 완료: 전체 %s컬럼, %s건", len(frame.columns), processed)
                            failures = 0
                        else:
                            message = json.loads(raw)
                            if message.get("header", {}).get("tr_id") == "PINGPONG":
                                await ws.pong(raw.encode())
                            elif message.get("body", {}).get("rt_cd") not in (None, "0"):
                                raise RuntimeError("KIS 웹소켓 구독 오류: " + str(message["body"].get("msg_cd")))
                            elif message.get("body", {}).get("rt_cd") == "0":
                                LOG.warning("구독 응답 성공: %s", message.get("header", {}).get("tr_id"))
                    raise ConnectionError("웹소켓 연결이 종료되었습니다.")
            except (OSError, TimeoutError, ConnectionClosed, InvalidHandshake) as exc:
                failures += 1
                LOG.warning("웹소켓 연결 오류: %s (%s)", type(exc).__name__, str(exc))
                if failures >= 5:
                    raise RuntimeError(
                        f"모의투자 웹소켓 연결 5회 실패: {url}. "
                        "REST 현재가 저장과는 별개입니다. 서버 상태 및 네트워크의 31000 포트 접근을 확인하세요."
                    ) from exc
                LOG.warning("웹소켓 재연결 예정. 연결 공백의 분봉은 불완전할 수 있습니다.")
                await asyncio.sleep(min(2 ** failures, 30))


def is_krx_base_columns(columns):
    return (len(columns) == 46 and columns[0] == "MKSC_SHRN_ISCD"
            and columns[-1] == "VI_STND_PRC")


def parse_ticks(raw, columns):
    parts = raw.strip("\r\n").split("|", 3)
    if len(parts) != 4:
        raise ValueError("실시간 프레임 헤더가 올바르지 않습니다.")
    _, tr_id, count, data = parts
    if tr_id != "H0STCNT0":
        return []
    count = int(count)
    if count < 1 or not columns:
        raise ValueError("실시간 체결 건수/컬럼 목록이 비어 있습니다.")
    # 확인된 KRX 46/47필드만 지원한다. 실제 수신한 추가 필드는 절대 자르지 않는다.
    widths = [47, 46] if is_krx_base_columns(columns) else [len(columns)]
    def split_record(payload, records):
        fields = payload.split("^")
        for width in widths:
            if len(fields) == records * width:
                return fields, width
        if fields[-1] == "":
            for width in widths:
                if len(fields) - 1 == records * width:
                    return fields[:-1], width
        raise ValueError(f"실시간 필드 수 불일치: 건수={records}, 건당 지원={widths}, 실제={len(fields)}")

    lines = data.splitlines()
    if len(lines) > 1:
        if len(lines) != count:
            raise ValueError(f"실시간 행 수 불일치: 헤더={count}, 실제={len(lines)}")
        records = []
        for line in lines:
            fields, width = split_record(line, 1)
            records.append((fields, width))
    else:
        values, width = split_record(data, count)
        records = [(values[i * width:(i + 1) * width], width) for i in range(count)]
    result = []
    for fields, width in records:
        names = list(columns)
        if width == 47 and is_krx_base_columns(columns):
            names.append("EXTRA_FIELD_47")
        result.append(dict(zip(names, fields)))
    return result



def aggregate_five_minute_rows(minute_rows, code, window_start):
    """이번 300초 수집 구간의 분별 집계를 한 행으로 합친다."""
    rows = sorted((row for row in minute_rows if row[0] == code), key=lambda row: row[1])
    if not rows:
        return None
    first, last = rows[0], rows[-1]
    return (code, window_start, last[2], last[3], last[4], last[5],
            first[6], max(row[7] for row in rows), min(row[8] for row in rows))


async def receive_five_minutes(auth, subscribe, recorder, code, receiver):
    import websockets
    url = auth.getTREnv().my_url_ws.rstrip("/") + "/"
    async with websockets.connect(url, proxy=None, open_timeout=15, ping_interval=None) as ws:
        message, columns = subscribe("1", code, env_dv="demo")
        await ws.send(json.dumps(message))
        # DB에는 한국 시각의 실제 수집 시작 시각을 저장한다(정규 5분 경계 아님).
        window_start = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None, microsecond=0)
        print(f"{code}: {window_start}부터 300초 수집을 시작합니다.")
        count = await receiver(ws, columns, recorder, sys.modules[__name__], seconds=300)
        print(f"5분 수집 종료: 체결 {count}건")
        return window_start


def collect_five_minute_candle(code, auth_path, csv_path=None):
    # 기존 CSV 검증/집계/트랜잭션 및 시간 제한 수신 함수를 재사용한다.
    db_dir = Path(__file__).resolve().parent / "db"
    sys.path.insert(0, str(db_dir))
    try:
        import import_ticks as tick_import
    finally:
        sys.path.pop(0)
    auth = load_module("kis_auth", auth_path)
    auth._DEBUG = False
    configure_paper_auth(auth)
    auth.auth_ws(svr="vps", product="01")
    verify_paper_session(auth)
    if not auth._base_headers_ws.get("approval_key"):
        raise RuntimeError("모의투자 웹소켓 인증 실패")
    subscribe = load_module(
        "five_minute_ccnl", ROOT / "examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py"
    ).ccnl_krx
    path = csv_path or TICK_DIR / f"ticks_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    recorder = TickRecorder(path)
    print(f"전체 체결 CSV: {recorder.path}")
    try:
        start = asyncio.run(receive_five_minutes(
            auth, subscribe, recorder, code, tick_import.receive_for_duration))
    finally:
        recorder.close()
    minute_rows, total, unique = tick_import.load_minutes([recorder.path])
    row = aggregate_five_minute_rows(minute_rows, code, start)
    if row is None:
        print("수신된 체결이 없어 DB에 저장하지 않습니다.")
        return
    connection = connect_db()
    try:
        tick_import.save_minutes(connection, [row])
    finally:
        connection.close()
    print(f"minute_chart_data에 5분 집계 1행 저장 완료: {code}, 시작={start}, 체결={unique}건")


def main():
    if len(sys.argv) == 1 or sys.argv[1] in ("top-list", "top-tick", "top-daily", "load-db"):
        import market_batch
        market_batch.main(sys.modules[__name__])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="collect5",
                        choices=["collect5", "check-db", "snapshot", "history", "stream", "all", "chart", "replay"])
    parser.add_argument("--auth-file", type=Path,
                        default=Path(os.getenv("KIS_AUTH_FILE", str(DEFAULT_AUTH_FILE))),
                        help="기본값: Test_Project/kis_auth.py (KIS_AUTH_FILE로 재정의 가능)")
    parser.add_argument("--env", choices=["demo"], default="demo", help="모의투자 전용")
    parser.add_argument("--codes", nargs="+", default=["005930"], help="기본값: 삼성전자 005930")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--period", choices=["D", "W", "M"], default="D", help="chart 조회 시 집계 주기")
    parser.add_argument("--csv", type=Path, help="stream/all: 체결 저장 경로, replay: 입력 체결 CSV")
    parser.add_argument("--output", type=Path, help="replay 분봉 CSV 출력 경로 (기존 파일 덮어쓰기 금지)")
    parser.add_argument("--history-csv", type=Path, help="history/all의 일봉 CSV 경로 (기본: NEW/data/daily_시간.csv)")
    parser.add_argument("--request-interval", type=float, default=1.1,
                        help="REST 응답 후 다음 요청까지 대기 초 (최소 1, 기본 1.1)")
    parser.add_argument("--max-retries", type=int, default=5,
                        help="EGW00201 재시도 횟수 (0~10, 기본 5)")
    args = parser.parse_args()
    if args.history_csv and args.mode not in ("history", "all"):
        parser.error("--history-csv는 history/all에만 사용할 수 있습니다.")
    if not math.isfinite(args.request_interval) or args.request_interval < 1:
        parser.error("--request-interval은 1초 이상이어야 합니다.")
    if not 0 <= args.max_retries <= 10:
        parser.error("--max-retries는 0~10이어야 합니다.")
    if args.mode in ("history", "all", "chart"):
        if not args.start or not args.end or args.start > args.end:
            parser.error("올바른 --start YYYY-MM-DD --end YYYY-MM-DD 기간이 필요합니다.")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    if args.mode == "collect5":
        if len(args.codes) != 1:
            parser.error("collect5는 집계 1행을 위해 종목 한 개만 받습니다.")
        if args.start or args.end or args.output:
            parser.error("collect5에는 날짜 범위나 --output을 지정하지 않습니다.")
        collect_five_minute_candle(args.codes[0], args.auth_file, args.csv)
        return
    if args.mode == "replay":
        if not args.csv:
            parser.error("replay에는 --csv 입력파일이 필요합니다.")
        output = args.output or TICK_DIR / f"replay_minutes_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
        replay_csv(args.csv, output, args.codes)
        return
    if args.output or (args.csv and args.mode not in ("stream", "all")):
        parser.error("--output은 replay에만, --csv는 stream/all/replay에만 사용할 수 있습니다.")
    ka = None
    if args.mode not in ("check-db", "chart"):
        ka = load_module("kis_auth", args.auth_file)
        ka._DEBUG = False
        configure_paper_auth(ka)
    db = connect_db()
    try:
        store = Store(db)
        if args.mode == "check-db":
            with db.cursor() as cur:
                for table, columns in {
                    "stock": "stock_code,stock_name,market,current_price,marketCap,change_amount,change_rate,volume,updated_at",
                    "minute_chart_data": "stock_code,candle_start,close_price,volume,change_amount,change_rate,open_price,high_price,low_price,updated_at",
                    "daily_chart_data": "stock_code,trade_date,close_price,volume,change_amount,change_rate,open_price,high_price,low_price,updated_at",
                }.items():
                    cur.execute(f"SELECT {columns} FROM {table} LIMIT 0")
            print("MySQL 접속 및 세 테이블 컬럼 확인 완료")
            return
        if args.mode != "chart" and "005930" in args.codes:
            store.ensure_samsung()
        codes = store.codes(args.codes)
        if args.mode == "chart":
            print(json.dumps({code: store.chart(code, args.start, args.end, args.period)
                              for code in codes}, ensure_ascii=False, default=str, indent=2))
            return
        if args.mode in ("stream", "all") and len(codes) > 40:
            parser.error("실시간 수집은 --codes로 최대 40종목을 선택하세요.")
        ka.auth(svr="vps", product="01")
        verify_paper_session(ka)
        if not ka._base_headers.get("authorization"):
            raise RuntimeError("모의투자 REST 인증에 실패했습니다.")
        collector = Collector(ka, store, args.env, args.request_interval, args.max_retries)
        if args.mode in ("snapshot", "stream", "all"):
            collector.snapshot(codes)
        if args.mode in ("history", "all"):
            history_path = (args.history_csv or DAILY_DIR / f"daily_{datetime.now():%Y%m%d_%H%M%S_%f}.csv").resolve()
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with history_path.open("x", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(DAILY_FIELDS)
                handle.flush()
                LOG.warning("일봉 CSV 저장 경로: %s", history_path)
                collector.history(codes, args.start, args.end, writer, handle)
        if args.mode in ("stream", "all"):
            path = args.csv or TICK_DIR / f"ticks_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
            recorder = TickRecorder(path)
            LOG.warning("체결 CSV 저장 경로: %s", recorder.path)
            try:
                asyncio.run(collector.stream(codes, recorder))
            finally:
                recorder.close()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("수집을 종료했습니다.")
    except Exception as exc:
        # DB 드라이버 예외에 접속정보가 포함될 수 있어 종류만 출력한다.
        if type(exc).__module__.startswith("pymysql"):
            print(f"MySQL 오류 ({type(exc).__name__}). 연결 설정과 테이블 권한을 확인하세요.", file=sys.stderr)
        else:
            print(f"수집 실패: {exc}", file=sys.stderr)
        sys.exit(1)
