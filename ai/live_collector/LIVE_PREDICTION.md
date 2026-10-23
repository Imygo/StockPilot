# 200종목 수집 → 통합 XGBoost → DB 의견

작업 위치: <프로젝트 경로>\ai\live_collector
기존 .env를 그대로 사용합니다. 키를 복사하거나 새 .env로 덮어쓰지 마세요.

## 1. 삼성전자 수집을 Ctrl+C로 중단하고 200종목 수집 시작

첫 번째 PowerShell:

```powershell
cd <프로젝트 경로>\ai\live_collector
..\.venv\Scripts\python.exe collector.py --universe ..\data\top200-20261012.json --write --loop
```

최초에는 각 종목의 당일 09:00부터 채우므로 시간이 걸립니다. 프로그램은 순차 호출하며
200종목 한 바퀴에 최소 약 120초+대기60초가 필요합니다. 같은 수집기를 여러 개 실행하지 마세요.
삼성전자만 있으면 시장 정보가 부족하므로 예측은 저장되지 않습니다.

## 2. 예측 이력 테이블 최초 생성

두 번째 PowerShell:

```powershell
cd <프로젝트 경로>\ai\live_collector
..\.venv\Scripts\python.exe predictor.py --init-db
```

ai_prediction_history를 CREATE TABLE IF NOT EXISTS로 생성합니다.
기존 minute_chart_data와 ai_opinions의 구조/데이터를 삭제하거나 변경하지 않습니다.
DB 계정에 새 테이블 생성 권한이 필요합니다. 이미 있는 이름의 다른 구조는 별도 확인하세요.

## 3. DB 읽기 및 예측 확인 (쓰기 없음)

```powershell
..\.venv\Scripts\python.exe predictor.py
```

기본 모델은 artifacts/top200-binary-v1/xgboost입니다. 별도 학습하지 않고 고정 모델을 로드합니다.
schema·78개 입력·학습 universe를 검증합니다. UP 점수는 보정된 확률이 아니며
57.24%는 개별 예측 신뢰도나 전체 실시간 정확도가 아닙니다.

## 4. 자동 예측 및 의견 저장

```powershell
..\.venv\Scripts\python.exe predictor.py --write --loop
```

20초마다 최신 5분 경계를 확인합니다. 동일 종목·경계·모델은 처음 기록한 예측을 보존하고
재실행해도 중복 저장하거나 의견 시간을 갱신하지 않습니다. 성공하면 new_rows_saved가 나옵니다.
늦게 준비된 종목은 같은 예측 구간 안에서 추가 저장될 수 있습니다.
Ctrl+C로 두 프로세스를 각각 종료합니다. PC/터미널을 닫으면 실행이 멈춥니다.

## 신선도 및 학습 조건

- 학습과 동일한 5분봉·11개 특징·12개 봉 요약·32개 시장 특징을 사용합니다.
- 시장 바스켓은 학습 당시 200종목 그대로입니다. 예측 대상은 prior가 있는 199종목입니다.
- 해당 시각에 두 시장 각각 모든 시장 수익률 구간의 데이터 보유율이 80% 이상이어야 합니다.
- 종목별 최신 5분봉이 정확히 기준 시각에 있어야 하며 결측을 보간하지 않습니다.
- 최소 지표 계산 구간이 필요합니다. 학습의 공통 30분 연속 표본 조건과 맞춰
  예측 기준 시각은 평일 11:00~14:50입니다. 30분 뒤 가격을 입력으로 쓰지는 않습니다.
- 오전 수집이 충분해도 11:00 전에는 WAIT가 정상입니다. 장 시작 시간을 변경한 날 등
  기존 학습 시간표와 다른 세션은 지원하지 않습니다.
- 대상 시각은 기준+5분입니다. 그 시간이 지났으면 저장하지 않습니다.
- 수집기의 1분 여유와 순차 호출 때문에 예측이 기준 시각보다 늦게 생성됩니다.
  created_at을 반드시 함께 보세요. 데이터가 늦으면 그 구간은 건너뜁니다.
- 스냅샷에 이후 분봉은 넣지 않습니다. 실제 보합 발생 여부는 미래 정보이므로
  라이브에서는 필터링하지 않고 항상 UP/DOWN 중 하나를 예측합니다.
- 보합 제외 검증 57.24%와 실시간 전체 결과는 평가 대상이 다릅니다.

## DB 읽기 (Spring 담당에게 전달)

ai_opinions에는 호환용 최신 UP/DOWN 의견을 저장합니다. 이 테이블 자체에는 만료 시각이
없으므로 이것만 읽어서 계속 최신처럼 표시하면 안 됩니다. 화면에서는 아래처럼
이력의 target_end가 현재보다 미래인 행만 보여주고 없으면 '예측 대기/만료'로 표시하세요.
UP/DOWN은 buy/sell 주문 권고와 다릅니다.

```sql
SELECT stock_code, direction, score_up, candle_end, target_end, created_at, model_version
FROM ai_prediction_history
WHERE stock_code = '005930'
  AND created_at <= UTC_TIMESTAMP() + INTERVAL 9 HOUR
  AND target_end > UTC_TIMESTAMP() + INTERVAL 9 HOUR
ORDER BY candle_end DESC, created_at DESC LIMIT 1;
```

시간 컬럼은 한국 현지시각 DATETIME입니다. score_up은 보정되지 않은 모델 점수입니다.
model_sha256는 모델 파일+메타데이터+prior+universe의 합성 해시입니다.
reference_close와 input_sha256를 저장해 예측 기준과 입력을 추적할 수 있습니다.
예측 후 정답/전체 성능을 자동 집계하는 기능은 아직 포함하지 않았습니다.
오래된 의견을 덮어쓰는 별도의 삼성전자 데모와 동시에 실행하지 마세요.

## 검증

```powershell
..\.venv\Scripts\python.exe -m unittest test_predictor -v
```

미래 입력 차단, 결측·시장 정보 부족, 장외 시각, 만료·중복 저장 방지를 검증합니다.
원본 모델은 수정하지 않습니다. 새 수집으로 얻는 이후 기간의 결과를 별도로 평가해야 합니다.
