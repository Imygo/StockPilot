# 최근 1년 일봉 → MySQL

저장소의 ai/README.md에 따라 설치한 뒤 ai/live_collector에서 실행합니다. 기존 .env를 재사용합니다. 테이블이 없다면 다음 명령으로 생성합니다. 기존 테이블 구조는 변경하지 않습니다.

```powershell
..\.venv\Scripts\python.exe daily_collector.py --init-db
..\.venv\Scripts\python.exe daily_collector.py --check-db
```

## 200종목 최근 1년 저장
```powershell
..\.venv\Scripts\python.exe daily_collector.py --universe ..\data\top200-20261012.json --write
```

기본 범위는 KST 어제까지 365일(거래일 365개가 아님)입니다. 오늘 미완성 일봉은 포함하지 않습니다. 기본 0.6초 간격이며 약 1,000회 요청이므로 최소 약 10분과 응답·DB 처리 시간이 필요합니다. 기존 장중 수집기와 API 한도를 공유하므로 장외에 실행하는 것을 권장합니다.

먼저 삼성전자만 DB 저장 없이 수신 확인:
```powershell
..\.venv\Scripts\python.exe daily_collector.py --symbols 005930
```

기간을 고정하려면:
```powershell
..\.venv\Scripts\python.exe daily_collector.py --universe ..\data\top200-20261012.json --start 2025-10-23 --end 2026-10-22 --write
```

## 재실행 및 갱신
- 90일 단위로 저장합니다. Ctrl+C로 중단해도 이전에 커밋된 구간은 보존됩니다.
- 동일한 기간으로 재실행하면 전체 구간을 다시 조회하고 (stock_code, trade_date) 기준 UPSERT합니다. 중간 누락도 다시 시도하며 중복 행을 만들지 않습니다. 체크포인트에서 건너뛰는 방식은 아닙니다.
- daily_saved의 rows는 처리한 일봉 수이며 신규 삽입 수가 아닙니다.
- 실패 구간은 로그에 표시하고 나머지를 계속 처리합니다. daily_finished.failed_chunks가 0인지 확인하세요. 실패가 있으면 종료 코드 1입니다.
- rows=0은 휴일·상장 전 등에도 발생합니다. 0건 응답만으로 요청한 모든 거래일의 완전성을 보장하지 않습니다. 거래정지의 0 OHLC/0 거래량 행은 만들지 않습니다.
- 다음 날 실행할 때 --start/--end로 최근 며칠을 지정해 갱신할 수 있습니다. 오늘 데이터는 다음 날부터 허용합니다. 자동 스케줄 등록은 포함하지 않습니다.

## 저장 규칙
KRX(J) 원주가(FID_ORG_ADJ_PRC=1) OHLC와 하루 누적 거래량(acml_vol)을 daily_chart_data에 저장합니다. 기존 수정주가와 혼용하지 마세요. 학습용 daily.py의 수정주가 CSV를 가져오는 기능은 아닙니다. 액면분할 등 원주가의 불연속은 그대로 남습니다.

change_amount/change_rate는 이번 수집에서 계산하거나 갱신하지 않습니다. 조회 구간 첫날의 전일 종가가 없어 잘못된 등락률을 만들지 않도록 OHLCV만 저장합니다. stock 종목 마스터와 5분 AI 모델은 변경하지 않습니다. Spring 조회를 위해 stock에 종목 등록이 필요합니다.

```sql
SELECT stock_code, COUNT(*) AS rows_count, MIN(trade_date), MAX(trade_date)
FROM daily_chart_data GROUP BY stock_code;
SELECT * FROM daily_chart_data WHERE stock_code='005930' ORDER BY trade_date DESC LIMIT 10;
```

## 테스트
```powershell
..\.venv\Scripts\python.exe -m unittest test_daily_collector test_collector -v
```

공식 API: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py
