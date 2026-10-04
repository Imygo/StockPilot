# 삼성전자 AI 의견 DB 데모 (2분류)

`minute_chart_data`에서 삼성전자 1분봉을 읽고 5분봉으로 변환한 뒤, 포함된 CNN-LSTM 모델의 결과를 `ai_opinions`에 저장합니다. 출력은 `UP`(상승), `DOWN_OR_FLAT`(하락 또는 보합)입니다. 기존 backend/frontend 코드는 변경하지 않습니다. 각 팀원은 자신의 로컬 MySQL을 사용합니다.

## 모델

모델은 기존 `short-fixed`와 동일합니다. 데이터 전체 기간은 2026-07-01~09-30이며, 실제 가중치 학습은 7/1~9/1, 검증은 9/2~9/14, 테스트는 9/15~9/30입니다. 3개월 전부를 가중치 학습에 사용한 것은 아닙니다. 다음 5분 종가가 현재 종가보다 높으면 상승, 같거나 낮으면 하락·보합입니다. 저장된 학습 전용 스케일러와 입력 특징 12개를 그대로 사용하며 판정 기준은 0.4입니다. 모델 점수는 보정된 확률이 아닙니다. 이 데모는 연결 검증용이며 예측 정확도를 보장하지 않습니다.

## 실행 준비 (Windows PowerShell)

```powershell
cd C:\Users\user\Desktop\StockPilot\ai-demo
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

팀원은 첫 줄을 자신의 저장소 경로로 바꿉니다. 기존 .env가 있으면 복사하지 않습니다. MySQL 접속 비밀번호는 .env에 직접 입력하며 Git에 넣지 않습니다. KIS 키/토큰은 이 데모에 필요하지 않습니다. 학습 환경 버전은 artifacts/short-fixed/metadata.json에 기록돼 있습니다.

DB와 테이블은 저장소의 `backend/db/stockpilot_db.sql`로 준비합니다. 테이블 생성만으로 입력 데이터가 생기지 않습니다. 스프링 수집 코드 또는 각자의 로컬 테스트 과정에서 삼성전자 분봉을 먼저 저장해야 합니다. 시세 CSV와 계정정보는 이 데모에 포함하지 않습니다.

입력 계약:

- stock_code: 문자열 `005930`, 시장: KRX J. 테이블에 시장 컬럼이 없으므로 수집 측에서 보장해야 합니다.
- candle_start: 한국 시간 1분 시작 시각(DATETIME)
- open_price/high_price/low_price/close_price: **그 1분의** OHLC
- volume: **그 1분의** 거래량. 누적 거래량/당일 OHLC는 사용할 수 없습니다.
- 완성된 분봉만 제공해야 합니다. `--minute-ohlcv`는 이 계약을 수집 담당과 확인했다는 옵션이며 코드가 의미를 자동 판별하지 않습니다.

## 과거 데이터로 테스트

아래 날짜의 DB 분봉이 있을 때 실행합니다. 다른 날짜면 --as-of를 변경하세요.

```powershell
.\.venv\Scripts\python.exe app.py db-inspect --as-of "2026-10-02 15:15"
.\.venv\Scripts\python.exe app.py db-preview --as-of "2026-10-02 15:15" --minute-ohlcv
.\.venv\Scripts\python.exe app.py db-save --as-of "2026-10-02 15:15" --minute-ohlcv
.\.venv\Scripts\python.exe app.py show
```

15:15는 기준 5분봉 종료 시각입니다. 15:14까지의 1분봉을 입력으로 15:20까지의 방향을 예측합니다. 주말에도 과거 데이터로 실행할 수 있습니다. --as-of를 생략하면 현재의 최근 완성 5분봉을 요구하며 과거 날짜로 대체하지 않습니다. 기본 전처리상 09:05부터 연속 115분이 필요하므로 첫 예측은 11:00, 마지막은 15:15입니다. 누락·잘못된 OHLCV·입력 부족은 저장 전에 오류로 중단합니다. 저장 없이 확인하려면 db-preview를 사용합니다.

## 스프링 조회 계약

```sql
SELECT stock_code, invest_opinion, updated_at
FROM stockpilot_db.ai_opinions
WHERE stock_code = '005930';
```

`UP`은 상승, `DOWN_OR_FLAT`은 하락·보합으로 표시합니다. 행이 없으면 아직 의견이 없는 상태입니다. DB 저장은 삼성전자 한 행을 추가하거나 갱신하고 커밋합니다. updated_at은 **저장 시각**이며 기준 봉 시각은 출력 JSON에서 확인합니다. 과거 재생을 저장하면 이전 최신 의견도 덮어씁니다. 자동 5분 스케줄러·시세 수집·재학습·동시 실행 제어는 포함하지 않습니다.

## 커밋 범위

이 `ai-demo` 폴더만 커밋합니다. 기존 `ai`는 수집 데이터와 실험 코드가 있으므로 `git add .`를 사용하지 마세요. 아래는 저장소 루트에서 실행합니다.

```powershell
git add -- ai-demo
git diff --cached --stat
git diff --cached --name-only
git commit -m "Add Samsung binary AI database demo"
```

이미 다른 파일이 스테이징돼 있다면 커밋 전에 목록을 확인하고 분리하세요. 모델 3개 파일(model.pt/scaler.json/metadata.json)은 실행에 필요하여 포함합니다. .env와 가상환경은 제외됩니다. 푸시는 사용자가 별도로 진행합니다.

검증:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```
모의 DB 경로 테스트이며 실제 MySQL/모델 통합 실행은 위 데모 명령으로 확인합니다.
