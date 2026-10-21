"""시장별 전일 거래량 상위 종목 선정, 종목별 CSV 수집 및 manifest 기반 DB 적재."""
from __future__ import annotations
import argparse
import asyncio
import csv
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
KST = timezone(timedelta(hours=9))
# 한국투자증권 stocks_info/kis_kospi_code_mst.py / kis_kosdaq_code_mst.py 기준
MASTER = {"KOSPI": ("kospi", 227, 212, 81), "KOSDAQ": ("kosdaq", 221, 206, 76)}

def now():
    return datetime.now(KST)

def parse_master(content, market):
    _, width, cap_offset, volume_offset = MASTER[market]
    stocks = {}
    for line in content.decode("cp949").splitlines():
        if not line:
            continue
        if len(line) < width + 22:
            raise ValueError(f"{market}: 종목 마스터 형식이 변경되었습니다.")
        prefix, tail = line[:-width], line[-width:]
        code = prefix[:9].strip()
        # 주식 그룹만 선정: ETF/ETN 등은 제외. 우선주는 별도로 제외하지 않는다.
        if tail[:2] != "ST" or not re.fullmatch(r"[0-9]{6}", code):
            continue
        cap = tail[cap_offset:cap_offset + 9].strip()
        if not cap.isdigit():
            raise ValueError(f"{market}/{code}: 시가총액 형식 오류")
        volume = tail[volume_offset:volume_offset + 12].strip()
        if not volume.isdigit():
            raise ValueError(f"{market}/{code}: 전일 거래량 형식 오류")
        if int(volume) <= 0:
            continue
        stocks[code] = {"stock_code": code, "stock_name": prefix[21:].strip(),
                        "market": market, "market_cap": int(cap), "previous_volume": int(volume)}
    if not stocks:
        raise ValueError(f"{market}: 주식 데이터를 찾지 못했습니다.")
    return sorted(stocks.values(), key=lambda row: (-row["previous_volume"], row["stock_code"]))

def select_top(per_market=20):
    selected, sources = [], []
    for market, (stem, _, _, _) in MASTER.items():
        url = f"https://new.real.download.dws.co.kr/common/master/{stem}_code.mst.zip"
        with urllib.request.urlopen(url, timeout=30) as response:
            zipped = response.read()
            modified = response.headers.get("Last-Modified")
        with zipfile.ZipFile(io.BytesIO(zipped)) as archive:
            content = archive.read(f"{stem}_code.mst")
        ranked = parse_master(content, market)
        if len(ranked) < per_market:
            raise ValueError(f"{market}: 요청한 종목 수보다 적습니다.")
        selected.extend(dict(row, rank=i) for i, row in enumerate(ranked[:per_market], 1))
        sources.append({"market": market, "url": url, "last_modified": modified})
    return {"selected_at": now().isoformat(), "basis": "KIS master previous trading day volume",
            "per_market": per_market, "sources": sources, "stocks": selected}

def validate_universe(universe, per_market):
    if universe.get("basis") != "KIS master previous trading day volume":
        raise ValueError("전일 거래량 기준 선정 목록이 아닙니다. top-list로 다시 생성하세요.")
    stocks = universe["stocks"]
    seen = set()
    for market in MASTER:
        group = [row for row in stocks if row["market"] == market]
        if len(group) != per_market:
            raise ValueError(f"선정 목록의 {market} 종목 수가 {per_market}개가 아닙니다.")
    for row in stocks:
        code = row["stock_code"]
        if not re.fullmatch(r"[0-9]{6}", code) or code in seen:
            raise ValueError("종목코드가 올바르지 않거나 중복입니다.")
        if row["market"] not in MASTER or not row["stock_name"] or len(row["stock_name"]) > 100:
            raise ValueError("종목 기본정보 오류")
        seen.add(code)
    return stocks

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)

def symbol_path(code, kind, run_id, start=None, end=None):
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("종목코드 형식 오류")
    label = f"tick_{run_id}" if kind == "tick" else f"daily_{start:%Y%m%d}_{end:%Y%m%d}_{run_id}"
    filename = "ticks.csv" if kind == "tick" else "daily.csv"
    return DATA / code / label / filename

class SymbolRecorder:
    def __init__(self, core, stocks, run_id):
        self.core = core
        self.recorders = {}
        try:
            for stock in stocks:
                code = stock["stock_code"]
                self.recorders[code] = core.TickRecorder(symbol_path(code, "tick", run_id))
        except BaseException:
            self.close()
            raise

    def write(self, raw, columns):
        rows = self.core.parse_ticks(raw, columns)
        if not rows:
            return 0
        names = list(columns)
        if self.core.is_krx_base_columns(columns):
            names.append("EXTRA_FIELD_47")
        frame = self.core.pd.DataFrame(rows, columns=names, dtype=str).fillna("")
        count = 0
        for code, group in frame.groupby("MKSC_SHRN_ISCD", sort=False):
            if code not in self.recorders:
                continue
            self.recorders[code].write_frame(group)
            count += len(group)
        return count

    def close(self):
        for recorder in self.recorders.values():
            recorder.close()

def authenticate(core, path, rest):
    auth = core.load_module("kis_auth", path)
    auth._DEBUG = False
    core.configure_paper_auth(auth)
    if rest:
        auth.auth(svr="vps", product="01")
        core.verify_paper_session(auth)
        if not auth._base_headers.get("authorization"):
            raise RuntimeError("모의투자 REST 인증 실패")
    else:
        auth.auth_ws(svr="vps", product="01")
        core.verify_paper_session(auth)
        if not auth._base_headers_ws.get("approval_key"):
            raise RuntimeError("모의투자 웹소켓 인증 실패")
    return auth

async def receive_market(core, auth, stocks, recorder, manifest, manifest_path):
    from kis_websocket import paper_connection
    subscribe = core.load_module("batch_ccnl",
        core.ROOT / "examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py").ccnl_krx
    raw_path = manifest_path.with_suffix(".raw.jsonl")
    async with paper_connection(auth.getTREnv().my_url_ws.rstrip("/") + "/") as ws:
        # 공통 수집 구간은 첫 구독 요청 직전부터 300초. 순차 구독 시간도 포함한다.
        manifest["window_start"] = now().replace(tzinfo=None, microsecond=0).isoformat()
        deadline = asyncio.get_running_loop().time() + 300
        write_json(manifest_path, manifest)
        for stock in stocks:
            message, columns = subscribe("1", stock["stock_code"], env_dv="demo")
            await ws.send(json.dumps(message))
            await asyncio.sleep(0.1)
        print(f"{len(stocks)}종목 구독 요청 완료. 공통 수집 구간 300초.")
        received = 0
        manifest["received_ticks"] = 0
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), remaining)
            except asyncio.TimeoutError:
                break
            if isinstance(raw, bytes):
                raw = raw.decode()
            if raw.startswith("0|"):
                # 파싱 실패도 원인 추적 가능하도록 체결 프레임만 기록한다.
                with raw_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"raw": raw}, ensure_ascii=False) + "\n")
                count = recorder.write(raw, columns)
                received += count
                manifest["received_ticks"] = received
                if received == count and count:
                    print(f"첫 체결 CSV 저장: {count}건")
            else:
                message = json.loads(raw)
                body = message.get("body", {})
                if message.get("header", {}).get("tr_id") == "PINGPONG":
                    await ws.pong(raw.encode())
                elif body.get("rt_cd") not in (None, "0"):
                    raise RuntimeError("구독 오류: " + str(body.get("msg_cd")))
        manifest["received_ticks"] = received
        print(f"수신 종료: 총 {received}건")

class CsvOnlyStore:
    def daily(self, rows):
        pass

def load_db_helpers():
    sys.path.insert(0, str(BASE / "db"))
    try:
        import import_ticks
        import import_daily
        return import_ticks, import_daily
    finally:
        sys.path.pop(0)

def manifest_rows(core, manifest):
    if manifest.get("status") != "complete":
        raise ValueError("완료된 수집 manifest만 DB에 적재할 수 있습니다.")
    stocks = validate_universe(manifest["universe"], manifest["universe"]["per_market"])
    allowed = {stock["stock_code"] for stock in stocks}
    file_codes = [item["stock_code"] for item in manifest["files"]]
    if len(file_codes) != len(set(file_codes)) or set(file_codes) != allowed:
        raise ValueError("manifest의 종목별 CSV 목록이 선정 목록과 일치하지 않습니다.")
    tick_import, daily_import = load_db_helpers()
    rows = []
    for item in manifest["files"]:
        if item["stock_code"] not in allowed:
            raise ValueError("선정 목록에 없는 CSV")
        path = (BASE / item["path"]).resolve()
        if not path.is_relative_to(DATA.resolve()):
            raise ValueError("CSV는 data 디렉토리 안에 있어야 합니다.")
        if manifest["kind"] == "tick":
            minutes, _, _ = tick_import.load_minutes([path])
            if any(row[0] != item["stock_code"] for row in minutes):
                raise ValueError("종목별 CSV에 다른 종목이 포함되어 있습니다.")
            row = core.aggregate_five_minute_rows(minutes, item["stock_code"],
                    datetime.fromisoformat(manifest["window_start"]))
            if row:
                rows.append(row)
        elif manifest["kind"] == "daily":
            values, _ = daily_import.load_rows([path])
            if any(row[0] != item["stock_code"] for row in values):
                raise ValueError("종목별 CSV에 다른 종목이 포함되어 있습니다.")
            rows.extend(values)
        else:
            raise ValueError("알 수 없는 manifest 종류")
    if len({(row[0], row[1]) for row in rows}) != len(rows):
        raise ValueError("manifest에 중복된 저장 키가 있습니다.")
    return stocks, rows

def import_manifest(core, manifest_path, dry_run=False):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stocks, rows = manifest_rows(core, manifest)
    print(f"DB 적재 대상: 기본정보 {len(stocks)}종목 / {manifest['kind']} {len(rows)}행")
    if dry_run:
        print("검증 완료. DB 접속 없음.")
        return
    tick_import, daily_import = load_db_helpers()
    connection = core.connect_db()
    try:
        with connection.cursor() as cursor:
            cursor.executemany("""INSERT INTO stock(stock_code,stock_name,market)
                VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE
                stock_name=VALUES(stock_name),market=VALUES(market)""",
                [(s["stock_code"], s["stock_name"], s["market"]) for s in stocks])
            sql = tick_import.SQL if manifest["kind"] == "tick" else daily_import.SQL
            for offset in range(0, len(rows), 500):
                cursor.executemany(sql, rows[offset:offset + 500])
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    print("MySQL 저장 완료. stock 시세/시가총액은 이 배치에서 갱신하지 않습니다.")

def main(core):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="top-tick",
                        choices=["top-list", "top-tick", "top-daily", "load-db"])
    parser.add_argument("--per-market", type=int, default=20)
    parser.add_argument("--universe", type=Path, help="top-list로 저장한 선정 목록 JSON 재사용")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--auth-file", type=Path, default=Path(
        core.os.getenv("KIS_AUTH_FILE", str(core.DEFAULT_AUTH_FILE))))
    parser.add_argument("--save-db", action="store_true")
    parser.add_argument("--manifest", type=Path, help="load-db에 필요한 수집 manifest")
    parser.add_argument("--dry-run", action="store_true", help="load-db 검증만 실행")
    args = parser.parse_args()
    if args.mode == "load-db":
        if not args.manifest:
            parser.error("--manifest가 필요합니다.")
        import_manifest(core, args.manifest, args.dry_run)
        return
    if args.dry_run or args.manifest:
        parser.error("--dry-run/--manifest는 load-db에서만 사용합니다.")
    if not 1 <= args.per_market <= 20:
        parser.error("--per-market은 1~20입니다. 웹소켓 총 구독 한도는 40종목입니다.")
    if args.mode == "top-daily" and (not args.start or not args.end or args.start > args.end):
        parser.error("top-daily에는 --start YYYY-MM-DD --end YYYY-MM-DD가 필요합니다.")
    universe = json.loads(args.universe.read_text(encoding="utf-8")) if args.universe else select_top(args.per_market)
    stocks = validate_universe(universe, args.per_market)
    run_id = now().strftime("%Y%m%d_%H%M%S_%f")
    universe_path = DATA / "runs" / f"universe_{run_id}.json"
    write_json(universe_path, universe)
    print(f"전일 거래량 기준 시장별 {args.per_market}개, 총 {len(stocks)}종목 (마스터 기준)")
    for stock in stocks:
        print(stock["market"], stock.get("rank"), stock["stock_code"], stock["stock_name"], stock["previous_volume"])
    print(f"선정 목록: {universe_path}")
    if args.mode == "top-list":
        return
    kind = "tick" if args.mode == "top-tick" else "daily"
    manifest_path = DATA / "runs" / f"{kind}_{run_id}.json"
    manifest = {"status": "collecting", "kind": kind, "run_id": run_id,
                "universe": universe, "files": []}
    write_json(manifest_path, manifest)
    try:
        auth = authenticate(core, args.auth_file, rest=kind == "daily")
        if kind == "tick":
            recorder = SymbolRecorder(core, stocks, run_id)
            try:
                manifest["files"] = [{"stock_code": code, "path": str(r.path.relative_to(BASE))}
                                     for code, r in recorder.recorders.items()]
                write_json(manifest_path, manifest)
                asyncio.run(receive_market(core, auth, stocks, recorder, manifest, manifest_path))
            finally:
                recorder.close()
        else:
            collector = core.Collector(auth, CsvOnlyStore(), "demo")
            for stock in stocks:
                code = stock["stock_code"]
                path = symbol_path(code, kind, run_id, args.start, args.end)
                path.parent.mkdir(parents=True, exist_ok=True)
                manifest["files"].append({"stock_code": code, "path": str(path.relative_to(BASE))})
                write_json(manifest_path, manifest)
                with path.open("x", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(core.DAILY_FIELDS)
                    handle.flush()
                    collector.history([code], args.start, args.end, writer, handle)
        manifest["status"] = "complete"
        manifest["completed_at"] = now().isoformat()
        write_json(manifest_path, manifest)
    except BaseException as exc:
        manifest["error_type"] = type(exc).__name__
        manifest["status"] = "failed"
        write_json(manifest_path, manifest)
        raise
    print(f"수집 manifest: {manifest_path}")
    if args.save_db:
        import_manifest(core, manifest_path)
    else:
        print("CSV 저장 완료. DB 저장은 --save-db 또는 load-db로 실행하세요.")
