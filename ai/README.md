# StockPilot 실시간 수집 · AI 예측

200종목의 KRX 1분봉과 시장 정보를 읽어 **5분 뒤 상승(UP) / 하락(DOWN)** 을 예측합니다. 모델 대상은 199종목이며 041960은 학습 표본 부족으로 제외됐습니다. 시장 정보에는 전체 200종목이 필요합니다. 종목 목록을 임의로 바꾸면 모델 입력과 맞지 않습니다.

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
..\.venv\Scripts\python.exe live_quotes.py --init-db
```

## 실행: PowerShell 창 3개
각 창은 `ai/live_collector` 폴더에서 실행합니다. 같은 프로그램을 중복 실행하지 마세요.

1. 200종목 분봉 수집
```powershell
..\.venv\Scripts\python.exe collector.py --universe ..\data\top200-20261012.json --write --loop --ai-cycle
```
2. AI 예측 및 저장
```powershell
..\.venv\Scripts\python.exe predictor.py --write --loop
```
3. 선택 종목 현재가
```powershell
..\.venv\Scripts\python.exe live_quotes.py --write
```

`watchlist.json`에서 현재가 수신 종목을 지정합니다(기본 삼성전자, 최대 40개). 200종목 전체 WebSocket 수집 기능은 아닙니다. 같은 KIS 앱키를 여러 팀원이 동시에 사용하지 않도록 운영 담당을 정하세요.

최초 당일 분봉 보충에는 시간이 걸립니다. 현재 모델의 예측 기준 시각은 평일 11:00~14:50 KST입니다. 데이터가 부족하거나 대상 시각이 만료되면 저장하지 않습니다. 휴장일 거래가 생기는 것은 아니며, 프로그램·PC·DB가 계속 실행 중이어야 합니다. 자동 부팅 등록은 포함하지 않습니다.

## 정상 동작 확인
- `quotes_saved`: 현재가 DB 저장 처리
- `ai_cycle_finished`: 분봉 수집 회차 완료; 지연과 실패 수 확인
- `mode: saved`, `new_rows_saved: 199`: 해당 회차 신규 예측 199건 저장
- 동일 기준 시각의 `new_rows_saved: 0`: 중복 저장 방지
- `WAIT`: 지원 시간 또는 데이터 충족을 기다리는 상태; 계속되면 분봉 수집기와 DB 확인

```sql
SELECT stock_code, price, trade_time, received_at FROM stock_live_quotes;
SELECT stock_code, candle_end, target_end, direction, score_up, created_at
FROM ai_prediction_history ORDER BY created_at DESC LIMIT 200;
```

## Spring 담당 연동
현재가는 `stock_live_quotes`, 확정 캔들은 `minute_chart_data`에서 읽습니다. 예측은 `ai_prediction_history`의 기준·대상 시각을 함께 제공하고 만료 여부를 표시하세요. `ai_opinions`만 읽으면 오래된 결과를 최신 예측으로 표시할 수 있습니다. 프론트 API·SSE·WebSocket 전달은 Spring에서 별도로 연결해야 합니다. DB 저장만으로 화면이 자동 갱신되지는 않습니다.

시간은 KST입니다. 최신 체결이 없으면 이전 가격이 남으므로 `trade_time`/`received_at`을 표시해야 합니다. `score_up`은 보정되지 않은 모델 점수이며 적중 확률로 단정하지 않습니다.

## 성능과 범위
개발 검증 3구간 평균 정확도는 **57.24%**였습니다. 실제 미래 가격이 그대로였던 표본을 제외한 조건부 상승/하락 평가이며, 반복 사용한 검증 기간의 결과입니다. 실시간 전체 시점 정확도 57.24%를 입증한 결과가 아닙니다. 실시간에는 미래 보합 여부를 알 수 없어 UP/DOWN을 출력합니다. 실시간 적중률 정산 기능은 아직 포함하지 않습니다.

## 테스트
`ai/live_collector`에서:
```powershell
..\.venv\Scripts\python.exe -m unittest test_collector test_predictor test_realtime -v
```
테스트는 외부 API 및 실제 DB 없이 실행합니다. 실제 계정 접속과 장중 데이터 수신은 팀원 환경에서 별도로 확인하세요. 모델 파일 무결성은 `MODEL_SHA256.json`에 기록했습니다.

상세 운영 안내: [실시간 수집](live_collector/REALTIME_RUN.md), [예측기](live_collector/LIVE_PREDICTION.md).
