# 수집 완료 스냅샷 기반 예측

## 변경 내용
기존 방식은 시장 데이터가 80% 이상 준비되면 수집 도중에도 예측했습니다. 새 방식은 `--publish-snapshot` 수집기가 같은 5분 경계의 모든 종목 요청·저장을 마친 뒤 분봉을 고정하고, `--require-snapshot` 예측기가 그 고정본만 읽습니다. 모델과 80% 시장 충족 기준은 변경하지 않습니다. 모든 종목에 거래가 있다는 의미는 아닙니다. 요청 실패가 1개라도 있으면 해당 회차 스냅샷을 발행하지 않습니다.

고정 시점의 분봉을 압축하여 ai_market_snapshots에 저장합니다. 이후 원본 분봉이 바뀌어도 해당 고정본은 바뀌지 않습니다. 예측에 사용한 78개 입력, 입력 해시, 시장 충족률, 제외 사유, 수집 완료 시각은 ai_prediction_runs에 기록됩니다. 같은 모델·기준 시각의 예측은 한 번만 저장하고 이후 종목을 추가하지 않습니다. 기존 예측이 이미 존재하는 회차는 다시 작성하지 않습니다.

## 시작 전
기존 분봉 수집기와 예측기는 Ctrl+C로 중단합니다. 새것과 동시에 실행하지 마세요. 현재가 WebSocket과 일봉 수집은 이 기능과 별개입니다. 같은 모델 파일과 종목 목록, 같은 DB를 사용합니다.

ai/live_collector에서 실행:
```powershell
..\.venv\Scripts\python.exe predictor.py --init-db
```
기존 예측 이력 테이블을 유지하고 새 ai_market_snapshots, ai_prediction_runs를 생성합니다. 기존 테이블을 변경하거나 삭제하지 않습니다.

창 1 — 분봉 수집 및 스냅샷 생성:
```powershell
..\.venv\Scripts\python.exe collector.py --universe ..\data\top200-20261012.json --write --loop --ai-cycle --publish-snapshot
```

창 2 — 고정된 스냅샷으로 예측:
```powershell
..\.venv\Scripts\python.exe predictor.py --write --loop --require-snapshot
```

창 3 — 기존 적중률 평가:
```powershell
..\.venv\Scripts\python.exe evaluate_live.py --loop --out ..\evaluations\live-today.json
```

## 로그
- snapshot_ready: 수집 완료 후 스냅샷 보관. new_snapshot=false이면 동일 경계·종목 목록의 최초 고정본이 이미 있습니다.
- snapshot_skipped / collection_failed: 수집 요청 실패. 다음 경계에서 재시도합니다.
- snapshot_skipped / outside_prediction_interval 또는 expired_during_freeze: 이미 목표 시각 만료. 이 회차는 예측하지 않습니다.
- WAIT: completed market snapshot absent: 수집 완료를 기다리는 중입니다.
- prediction_already_saved: 같은 모델·회차는 이미 저장돼 재예측하지 않습니다.
- 저장 로그 snapshot.collection_delay_seconds: 기준 시각부터 스냅샷 고정까지 걸린 시간입니다.

## DB 확인
```sql
SELECT candle_end, completed_at, symbol_count, row_count,
       OCTET_LENGTH(payload) AS compressed_bytes
FROM ai_market_snapshots ORDER BY candle_end DESC LIMIT 10;

SELECT candle_end, collection_completed_at, created_at, prediction_count,
       TIMESTAMPDIFF(SECOND,candle_end,created_at) AS creation_delay_seconds,
       TIMESTAMPDIFF(SECOND,created_at,candle_end + INTERVAL 5 MINUTE) AS remaining_seconds
FROM ai_prediction_runs ORDER BY candle_end DESC LIMIT 10;
```

ai_prediction_runs.audit_json에는 inputs(종목코드·입력 해시·78개 입력), market_coverage, skipped, snapshot_sha256, collection_completed_at가 있습니다. 숫자 배열을 float32로 복원하면 당시 input_sha256을 재검증할 수 있습니다. 예측 결과와 실행 감사 기록은 같은 트랜잭션으로 저장하며 중간 오류 또는 만료 시 함께 롤백합니다. 예측이 목표 전에 생성돼도 DB 커밋까지 완전히 완료되기 전에는 조회할 수 없으므로 created_at만으로 전송 지연 전체를 측정하지는 못합니다.

## 운영 범위와 한계
- 수집 완료를 기다린다고 정확도가 높아진다고 보장하지 않습니다. 입력을 재현하고 검증할 수 있게 만드는 변경입니다.
- 완성 확인 여유 1분과 기본 API 호출 간격을 그대로 사용합니다. 현재 약3분의 지연을 자동으로 해소하지 않습니다. 계정 한도를 확인한 뒤 수집 속도를 별도로 개선해야 합니다.
- 80% 데이터 충족 기준과 11:00~14:50 예측 기준 시각을 유지합니다. 완성되지 않은 종목은 제외되며 이후 같은 회차에 추가하지 않습니다.
- 최초 당일 보충이 목표 시각보다 늦으면 정상적으로 예측을 건너뜁니다. 수집기는 계속 운영하여 이후 회차 및 목표 분봉을 확보하세요.
- 스냅샷 생성 당시 진행 중인 다른 DB 쓰기가 있으면 SELECT 시점에 보이는 확정 데이터를 보관합니다. 단일 분봉 수집기를 운영하세요. 동일 경계는 INSERT IGNORE로 최초 스냅샷만 보존합니다.
- 같은 DB에 과거 방식 예측기를 함께 실행하지 마세요. 이전 방식으로 이미 저장된 회차는 새 방식이 덮어쓰지 않습니다.
- --publish-snapshot/--require-snapshot을 생략하면 기존 방식으로 동작합니다. 두 플래그를 함께 사용해야 합니다.
- 압축 분봉과 감사 입력이 계속 쌓입니다. 자동 삭제는 구현하지 않았습니다. 배포 담당이 보관 기간과 백업을 정해야 합니다. 압축 스냅샷은 3MiB 상한이며 MySQL max_allowed_packet도 이를 수용해야 합니다. 초과 시 자르지 않고 오류 처리합니다.
- 예측 당시의 기준 분봉은 스냅샷에 있지만 미래 목표 분봉은 아직 없습니다. 적중률 평가는 이후 minute_chart_data의 목표 구간을 계속 사용합니다.

## 테스트
```powershell
..\.venv\Scripts\python.exe -m unittest test_snapshots test_predictor test_collector -v
```
