# StockPilot 실시간 수집 · AI 예측

200종목의 KRX 1분봉과 시장 정보를 읽어 **5분 뒤 상승(UP) / 하락(DOWN)** 을 예측합니다. 모델 대상은 199종목이며 041960은 학습 표본 부족으로 제외됐습니다. 시장 정보에는 전체 200종목이 필요합니다. 종목 목록을 임의로 바꾸면 모델 입력과 맞지 않습니다.

## 데이터 흐름과 팀원 역할

| 수집 데이터 | 방식 | 저장 테이블 | 용도 |
|---|---|---|---|
| 완성된 분봉 | REST / collector.py | minute_chart_data | 차트와 AI 입력 |
| 일봉 | REST / daily_collector.py | daily_chart_data | 과거 일별 차트 |
| 200종목 모의 현재가 | WebSocket / live_quotes_multi.py | stock_live_quotes_paper | 실시간 화면 표시 |

AI는 REST 분봉으로 만든 5분봉·시장 정보를 사용합니다. 현재 모델에 일봉이나 모의 현재가는 입력하지 않습니다. WebSocket 테이블은 최신값만 보관하며 전체 체결 이력이 아닙니다.

배포 담당은 서버의 DB 및 환경변수를 설정하고 아래 수집기와 예측기를 운영합니다. DB 데이터는 GitHub에 포함되지 않으므로 서버에서 일봉·분봉을 별도로 수집해야 합니다. Spring 담당은 같은 DB를 조회해 프론트 API에 연결하고, 모의 시세 표시와 데이터 지연·예측 만료 처리를 구현해야 합니다. Python 실행만으로 화면이 자동 연결되지는 않습니다.

## 포함 기능
- `live_collector/collector.py`: REST → 완성된 분봉 → MySQL `minute_chart_data`
- `live_collector/predictor.py`: 저장된 분봉 → 고정 XGBoost 모델 → `ai_prediction_history`, `ai_opinions`
- `live_collector/live_quotes.py`: 선택 종목 WebSocket 체결 → `stock_live_quotes` 최신값
- 학습된 모델과 종목 목록을 포함합니다. 재학습 및 과거 학습 원본 데이터는 포함하지 않습니다.

## 최초 설치 (Windows / Python 3.11 / MySQL 8)
PowerShell에서 저장소의 `ai` 폴더로 이동한 뒤 실행합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path live_collector\.env)) { Copy-Item live_collector\.env.example live_collector\.env }
notepad live_collector\.env
```

각자 발급받은 KIS 실전 앱키·앱시크릿과 DB 접속 정보를 입력합니다. `KIS_ACCESS_TOKEN`은 비워두면 실행 중 자동 발급합니다. `.env`는 공유하거나 커밋하지 않습니다. MySQL 서버와 데이터베이스는 별도로 준비해야 합니다. `127.0.0.1`은 실행하는 컴퓨터 자신의 DB입니다.

MySQL Workbench에서 `.env`에 지정한 데이터베이스를 선택하고 `schema.sql`을 실행합니다. 기존 테이블은 변경하지 않습니다. 기존 구조가 다르면 팀의 스키마와 먼저 맞춰야 합니다. 분봉 `volume`에는 누적 거래량이 아닌 해당 1분 거래량을 넣습니다.

```powershell
cd live_collector
..\.venv\Scripts\python.exe collector.py --check-db
..\.venv\Scripts\python.exe predictor.py --init-db
..\.venv\Scripts\python.exe live_quotes_multi.py --init-db
```

## 실행: PowerShell 창 3개
각 창은 `ai/live_collector` 폴더에서 실행합니다. 같은 프로그램을 중복 실행하지 마세요.

1. 200종목 분봉 수집
```powershell
..\.venv\Scripts\python.exe collector.py --universe ..\data\top200-20261012.json --write --loop --ai-cycle --publish-snapshot
```
2. AI 예측 및 저장
```powershell
..\.venv\Scripts\python.exe predictor.py --write --loop --require-snapshot
```
3. 200종목 모의 현재가
```powershell
..\.venv\Scripts\python.exe live_quotes_multi.py --write
```

200종목 모의 수신은 [MULTI_WEBSOCKET.md](live_collector/MULTI_WEBSOCKET.md)를 따라 `.env.paper.example`을 `.env.paper`로 복사해 독립 모의 키 5쌍을 설정한 뒤 실행합니다. `.env`에는 공통 DB와 REST 실전 키 설정이 들어갑니다. 두 실제 설정 파일은 커밋하지 않습니다. 같은 앱키로 여러 프로그램을 중복 실행하지 마세요.

기존 `live_quotes.py`는 실전 선택 종목 수신용이며 `watchlist.json` 기본 삼성전자, 코드상 최대 40개입니다. 위의 200종목 모의 수신기와 테이블이 다릅니다.

최초 당일 분봉 보충에는 시간이 걸립니다. 현재 모델의 예측 기준 시각은 평일 11:00~14:50 KST입니다. 데이터가 부족하거나 대상 시각이 만료되면 저장하지 않습니다. 휴장일 거래가 생기는 것은 아니며, 프로그램·PC·DB가 계속 실행 중이어야 합니다. 자동 부팅 등록은 포함하지 않습니다.

## 정상 동작 확인
- `paper_ws_status`: `subscription_complete=true`, `acknowledged=200`, `missing_slots=[]`이면 전체 구독 승인. 실제 수신은 계좌별 `symbols_seen_since_connect=40` 확인.
- `paper_quotes_saved`, `db_last_write_ok=true`: 모의 현재가 저장 처리. DB `received_at` 갱신도 확인하세요.
- `missing_slots`, `missing_subscription_symbols`: 미승인 계좌 및 종목 수. 일부 연결이 실패해도 정상 계좌는 유지되므로 부분 수신 상태를 반드시 확인하세요.
- `quotes_saved`: 기존 실전 선택 종목 수신기의 저장 처리
- `ai_cycle_finished`: 분봉 수집 회차 완료; 지연과 실패 수 확인
- `mode: saved`, `new_rows_saved: 199`: 해당 회차 신규 예측 199건 저장
- 동일 기준 시각의 `new_rows_saved: 0`: 중복 저장 방지
- `WAIT`: 지원 시간 또는 데이터 충족을 기다리는 상태; 계속되면 분봉 수집기와 DB 확인

```sql
SELECT stock_code, price, trade_time, received_at FROM stock_live_quotes_paper;
SELECT stock_code, candle_end, target_end, direction, score_up, created_at
FROM ai_prediction_history ORDER BY created_at DESC LIMIT 200;
```

## Spring 담당 연동
200종목 모의 현재가는 `stock_live_quotes_paper`에서 읽고 화면에 모의임을 표시합니다. 기존 실전 선택 종목 현재가는 `stock_live_quotes`입니다. 확정 캔들은 `minute_chart_data`에서 읽습니다. 예측은 `ai_prediction_history`의 기준·대상 시각을 함께 제공하고 만료 여부를 표시하세요. `ai_opinions`만 읽으면 오래된 결과를 최신 예측으로 표시할 수 있습니다. 프론트 API·SSE·WebSocket 전달은 Spring에서 별도로 연결해야 합니다. DB 저장만으로 화면이 자동 갱신되지는 않습니다.

시간은 KST입니다. 최신 체결이 없으면 이전 가격이 남으므로 `trade_time`/`received_at`을 표시해야 합니다. `score_up`은 보정되지 않은 모델 점수이며 적중 확률로 단정하지 않습니다.

## 성능과 범위
개발 검증 3구간 평균 정확도는 **57.24%**였습니다. 실제 미래 가격이 그대로였던 표본을 제외한 조건부 상승/하락 평가이며, 반복 사용한 검증 기간의 결과입니다. 실시간 전체 시점 정확도 57.24%를 입증한 결과가 아닙니다. 실시간에는 미래 보합 여부를 알 수 없어 UP/DOWN을 출력합니다. 실시간 적중률은 별도 evaluate_live.py로 확인할 수 있습니다. 아래 실시간 예측 평가 안내를 참고하세요.

## 테스트
`ai/live_collector`에서:
```powershell
..\.venv\Scripts\python.exe -m unittest discover -p 'test_*.py' -v
```
테스트는 외부 API 및 실제 DB 없이 실행합니다. 실제 계정 접속과 장중 데이터 수신은 팀원 환경에서 별도로 확인하세요. 모델 파일 무결성은 `MODEL_SHA256.json`에 기록했습니다.

상세 운영 안내: [실시간 수집](live_collector/REALTIME_RUN.md), [예측기](live_collector/LIVE_PREDICTION.md).

## 과거 일봉 DB 수집

200종목의 최근 1년 일봉을 저장하는 기능은 [일봉 수집 안내](live_collector/DAILY_COLLECTION.md)를 참고하세요. `daily_collector.py`는 기본적으로 어제까지의 완성된 일봉을 조회하며 `--write`로 DB에 저장합니다.

## 실시간 예측 평가

[evaluate_live.py 실행 안내](live_collector/LIVE_EVALUATION.md): 저장된 예측과 5분 뒤 확정 분봉을 비교합니다. 보합 포함/제외 정확도, 누락 상태, 모델·종목·날짜·지연별 결과를 제공합니다. DB 읽기 전용이며 `--loop`로 자동 재계산합니다.

## 수집 완료 후 예측 모드

[스냅샷 실행 안내](live_collector/SNAPSHOT_RUN.md)를 먼저 확인하세요. 기존 수집기·예측기를 중단하고 `predictor.py --init-db`로 새 테이블을 준비한 뒤 위의 `--publish-snapshot` / `--require-snapshot` 명령을 함께 사용합니다. 모델은 그대로이며 데이터 고정과 입력 감사 기록이 추가됐습니다.

## 200종목 모의 WebSocket 수신

[5개 독립 모의 앱키 설정 안내](live_collector/MULTI_WEBSOCKET.md)를 참고하세요. `live_quotes_multi.py`가 코스피100·코스닥100을 계좌별40종목으로 분할합니다. 모의 수신 값은 별도 `stock_live_quotes_paper`에 저장하며 실제 계좌 발급 가능 여부와 전체 구독 성공은 별도 확인이 필요합니다.
