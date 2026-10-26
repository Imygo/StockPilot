# 실시간 예측 적중률 확인

ai/live_collector 폴더에서 실행합니다. 기존 .env와 라이브러리를 사용합니다. DB 테이블 추가와 쓰기 권한은 필요 없습니다. ai_prediction_history와 minute_chart_data를 SELECT합니다.

## 오늘 결과 한 번 확인
```powershell
..\.venv\Scripts\python.exe evaluate_live.py --out ..\evaluations\live-today.json
```

## 60초마다 자동 재계산
```powershell
..\.venv\Scripts\python.exe evaluate_live.py --loop --out ..\evaluations\live-today.json
```
날짜를 생략하면 매 회차 KST 오늘을 평가하므로 자정을 지나면 새 날짜로 전환됩니다. JSON은 최신 결과로 교체합니다. 전날 결과는 아래 기간 지정으로 다시 계산할 수 있습니다. 자동 시작/서버 스케줄 등록은 포함하지 않습니다.

## 날짜 범위 지정
```powershell
..\.venv\Scripts\python.exe evaluate_live.py --start 2026-10-23 --end 2026-10-23 --out ..\evaluations\live-20261023.json
```

## 계산 기준
- 기준: 예측 기록에 저장된 reference_close. 나중에 수정된 기준 분봉으로 바꾸지 않습니다.
- 목표: candle_end부터 target_end 직전까지 1분봉 5개가 모두 존재하고 유효한 경우, 마지막 1분봉 종가. 예: 11:15→11:20 예측은 11:15,16,17,18,19 분봉을 확인하며 11:19 분봉 종가와 비교합니다. 11:20 분봉은 사용하지 않습니다.
- DB 서버의 KST 시각 기준 목표 시각 + 60초 이후 평가합니다. 수집기 저장이 늦으면 이후 회차에 재시도합니다.
- 실제 가격이 기준보다 높으면 UP, 낮으면 DOWN, 정확히 같으면 FLAT입니다. ±0.1% 같은 중립 구간을 적용하지 않습니다.
- all_outcomes_accuracy: 보합 포함 정답 수 / 평가 가능 전체 건수. UP/DOWN 모델에서 실제 FLAT은 오답으로 계산합니다.
- nonzero_accuracy: 실제 FLAT을 제외한 정답률. 개발 검증 57.24%와 같은 비보합 분모지만 기간·지연·샘플 선택이 달라 직접 같은 성능으로 단정할 수 없습니다.
- 정확도는 0~1입니다. 0.57은 57%입니다. 평가 표본이 없으면 null로 표시합니다.
- majority_nonzero_baseline은 평가 표본에서 더 많은 방향만 고른 사후 기준선입니다. 사전 예측 모델 성능은 아닙니다.

## 결과 구분
JSON models 아래 모델 해시별 overall/by_stock/by_day/by_creation_delay가 있습니다. details에는 예측별 실제 방향, 종가, 기준가, 지연, 가격 원본 해시가 포함됩니다. 행렬은 실제 DOWN/FLAT/UP 행과 예측 DOWN/UP 열 순서입니다.

status_counts:
- evaluated: 평가 완료
- pending_target: 목표 시각 및 확정 여유시간 전
- missing_target_minutes: 목표 구간 분봉 부족
- invalid_target_minutes: OHLCV 이상
- invalid_prediction_timing: 기준 시각 이전 또는 목표 시각 이후 저장된 예측
- invalid_prediction: 지원하지 않는 구간/방향/기준가

평가 불가 건은 정확도 분모에 넣지 않고 별도 집계합니다. 누락이 많으면 정확도만 보지 마세요. recorded=0은 해당 날짜에 예측 이력이 없다는 뜻입니다.

## 해석 시 주의
이 도구는 저장된 예측의 결과를 평가하며 모든 종목/예정 시점의 서비스 가용률을 계산하지 않습니다. 늦게 저장된 예측은 실제 제공 후 5분 예측이 아닙니다. JSON의 creation_delay_seconds와 remaining_seconds_at_creation, 지연별 집계를 함께 보세요. 수익률은 기준 캔들 종가 대비이며 체결 가능 가격, 수수료, 실제 투자 수익을 반영하지 않습니다.

DB 원본 분봉 수정 시 재평가 결과가 바뀔 수 있습니다. target_source_sha256으로 원본 변경을 추적할 수 있으며 독립 감사 기록이 필요하면 보고서를 별도 보관하세요. 예측 이력은 변경하지 않습니다. 기존 분봉 수집은 당일만 보충하므로 과거 날짜 누락은 이 도구가 복구하지 않습니다.

루프는 같은 데이터를 다시 계산하므로 실행 횟수만큼 표본 수가 늘어나지 않습니다. 모델을 바꾸면 해시별로 결과를 분리합니다. 며칠의 결과만으로 성능을 확정하지 말고 충분한 새 기간을 관찰하세요.

## 테스트
```powershell
..\.venv\Scripts\python.exe -m unittest test_evaluate_live -v
```
