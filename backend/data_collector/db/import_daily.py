"""NEW/data/daily의 CSV를 기존 daily_chart_data 테이블에 저장한다."""
from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import getpass
import os
from pathlib import Path
import sys

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "daily"
COLUMNS = ("stock_code", "trade_date", "close_price", "volume", "change_amount",
           "change_rate", "open_price", "high_price", "low_price")
SQL = """
INSERT INTO daily_chart_data
(stock_code,trade_date,close_price,volume,change_amount,change_rate,open_price,high_price,low_price)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
close_price=VALUES(close_price), volume=VALUES(volume),
change_amount=VALUES(change_amount), change_rate=VALUES(change_rate),
open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price),
updated_at=CURRENT_TIMESTAMP
"""


def numeric(value, column):
    # SQL의 시세 컬럼은 NULL을 허용한다. CSV의 빈 값은 NULL로 유지한다.
    if value is None or not value.strip():
        return None
    try:
        result = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{column}: 숫자가 아닙니다.") from exc
    if not result.is_finite():
        raise ValueError(f"{column}: 유한한 숫자여야 합니다.")
    if column in ("change_amount", "change_rate"):
        number = float(result)
        import math
        if not math.isfinite(number):
            raise ValueError(f"{column}: DOUBLE 범위를 벗어났습니다.")
        return number
    maximum = 2**63 - 1 if column == "volume" else 2**31 - 1
    if result != result.to_integral_value() or not 0 <= result <= maximum:
        raise ValueError(f"{column}: 0~{maximum} 범위의 정수여야 합니다.")
    return int(result)


def load_rows(files):
    """모든 파일을 먼저 검증. 같은 키는 뒤에 읽은 파일/행을 우선한다."""
    unique = {}
    total = 0
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            if len(header) != len(set(header)) or set(COLUMNS) - set(header):
                raise ValueError(f"{path.name}: 필수 CSV 컬럼이 없거나 헤더가 중복됩니다.")
            for line, row in enumerate(reader, 2):
                try:
                    if None in row or any(row[column] is None for column in COLUMNS):
                        raise ValueError("CSV 행의 필드 수가 올바르지 않습니다.")
                    code = row["stock_code"].strip()
                    if not code or len(code) > 15:
                        raise ValueError("stock_code는 1~15자리 문자열이어야 합니다.")
                    day = date.fromisoformat(row["trade_date"].strip())
                    values = (code, day, *(numeric(row[col], col) for col in COLUMNS[2:]))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{path.name}:{line}행: {exc}") from exc
                unique[(code, day)] = values
                total += 1
    return [unique[key] for key in sorted(unique)], total


def connect_db():
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("PyMySQL이 필요합니다. python -m pip install -r NEW/requirements.txt") from exc
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


def save_rows(connection, rows):
    try:
        with connection.cursor() as cursor:
            for offset in range(0, len(rows), 500):
                cursor.executemany(SQL, rows[offset:offset + 500])
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY,
                        help="입력 폴더. daily_*.csv를 파일명 순으로 읽습니다.")
    parser.add_argument("--file", type=Path, help="지정한 CSV 한 개만 읽습니다.")
    parser.add_argument("--dry-run", action="store_true", help="DB 접속 없이 CSV 검증 및 건수 확인")
    args = parser.parse_args()
    files = [args.file.resolve()] if args.file else sorted(args.directory.resolve().glob("daily_*.csv"))
    if not files:
        parser.error("입력 폴더에 daily_*.csv 파일이 없습니다.")
    rows, total = load_rows(files)
    print(f"CSV {len(files)}개 / 총 {total}행 / 중복 키 {total - len(rows)}행 / 저장 대상 {len(rows)}행")
    if args.dry_run:
        print("검증 완료. DB에 접속하거나 저장하지 않았습니다.")
        return
    if not rows:
        print("저장할 데이터가 없습니다.")
        return
    connection = connect_db()
    try:
        save_rows(connection, rows)
    finally:
        connection.close()
    print(f"daily_chart_data에 {len(rows)}개 종목·날짜 키 저장 완료 (삽입 또는 갱신)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("작업을 중단했습니다.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        if type(exc).__module__.startswith("pymysql"):
            print(f"MySQL 오류 ({type(exc).__name__}). 연결 설정과 테이블을 확인하세요.", file=sys.stderr)
        else:
            print(f"저장 실패: {exc}", file=sys.stderr)
        sys.exit(1)
