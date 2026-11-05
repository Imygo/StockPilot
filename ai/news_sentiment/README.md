# StockPilot 통합 뉴스 감성평가

기존 ai의 주가 방향 예측과 별개로, 코스피·코스닥 시가총액 상위 100개씩의 뉴스를 15분마다 수집하고 기업별 긍정/중립/부정 예측을 **기존 stockpilot_db.news_target_predictions**에 저장합니다. 기존 주가·ai_opinions 테이블은 변경하지 않습니다.

## 설치

Python 3.11 / MySQL 8. 경로가 너무 길면 PyTorch 설치가 실패할 수 있으므로 짧은 저장소 경로를 권장합니다. 이 폴더에서 실행합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

별도로 제공된 final-stockpilot-news-v1 폴더 전체를 `models/final-stockpilot-news-v1`에 놓고 검증합니다.

```powershell
.\.venv\Scripts\python.exe verify_model.py
```

모델은 Git 커밋에서 제외됩니다. `model-info`에 모델 설명·데이터 출처·평가·파일 SHA256을 포함했습니다. 재배포 시 출처 문서를 유지하고 기본 KLUE 모델 및 KorFin-ASC의 이용조건을 확인하세요. GPU는 호환되는 PyTorch와 드라이버가 필요하며 CPU도 실행 가능합니다.

## DB 설정

기존 StockPilot과 동일한 DB 환경변수를 사용합니다. Python은 아래 HOST/PORT/NAME을, Spring은 기존 STOCKPILOT_DB_URL을 사용하므로 같은 서버·DB를 가리키게 설정하세요. .env.example은 문서용이며 자동 로드하지 않습니다.

```powershell
$env:STOCKPILOT_DB_HOST='127.0.0.1'
$env:STOCKPILOT_DB_PORT='3306'
$env:STOCKPILOT_DB_NAME='stockpilot_db'
$env:STOCKPILOT_DB_USER='실제_DB_사용자'
# 비밀번호는 비밀 환경변수로 주입하거나 실행 스크립트에서 숨김 입력합니다.
```

MySQL Workbench에서 서버에 연결한 뒤 저장소의 **`backend/db/stockpilot_db.sql`을 실행**하세요. 뉴스 예측 결과는 `stockpilot_db.news_target_predictions`에 저장됩니다.

- 새 DB: MySQL Workbench에서 서버에 연결한 뒤 위 SQL 파일 전체를 실행합니다.
- 기존 DB: 같은 파일을 실행하면 없는 테이블만 생성합니다. `CREATE TABLE IF NOT EXISTS`는 이미 있는 테이블의 구조나 데이터를 변경하지 않습니다. 기존 테이블 구조가 정의와 다르면 별도 확인이 필요합니다.
- SQL 파일을 편집·저장하는 것만으로 실제 DB가 변경되지는 않습니다.
- GitHub에는 수집 데이터가 포함되지 않습니다. 서버에 데이터를 채우려면 아래 수집기를 실행하세요.

실행에는 테이블 생성 권한이 필요합니다. 정기 수집 계정에는 `news_target_predictions`의 SELECT, INSERT, UPDATE 권한이 필요합니다. 기존 주가·AI 의견 테이블은 뉴스 수집기가 변경하지 않습니다. `stock`에 일부 종목만 등록되어 있어도 결과를 저장할 수 있도록 외래키는 걸지 않았으며, 종목코드로 연결합니다.

설치 후 DB 연결과 뉴스 테이블을 확인합니다. 아래 명령에는 `STOCKPILOT_DB_PASSWORD` 환경변수가 필요합니다. 비밀번호를 직접 명령에 쓰지 않으려면 다음 실행 절차의 `run.ps1 -Once`에서 숨김 입력하고 연결·수집을 함께 확인할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe check_db.py
```

## 실행

```powershell
# NAVER 키와 DB 비밀번호는 숨김 입력
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Once
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

첫 명령은 1회, 둘째는 15분마다 반복합니다. PC와 창을 켜두어야 하며 Ctrl+C로 종료합니다. 서버 운영 시 환경변수를 주입하고 `python multi_worker.py --model models/final-stockpilot-news-v1 --interval-minutes 15 --pages 1`로 실행할 수 있습니다. 부팅 자동실행은 별도입니다.

## 백엔드 API

`StockNewsController.java`가 기존 Spring 프로젝트에 추가되어 있습니다. 백엔드를 빌드·재시작하면 기존 Spring 데이터소스로 뉴스 테이블을 조회합니다. 해당 데이터소스도 수집기와 같은 `stockpilot_db`를 가리켜야 합니다.

`GET /api/stocks/005930/news?limit=30`

- limit: 1~100, 기본 30
- modelVersion: 선택. 미지정 시 해당 종목의 최근 저장 모델 버전을 선택
- 결과: 기사 ID, 종목, 제목, 요약, URL, UTC 시각, 라벨, 세 확률, 모델 버전, 검토 사유 JSON 문자열
- 기사 없는 종목은 빈 배열. 잘못된 종목코드·limit·모델 버전은 400
- 사용자 화면에 표시하는 프론트 변경은 포함하지 않음

## 상태와 제한

`data/live200/status.json`은 회차 결과, live-results.html은 마지막 신규 저장 기사, pending.json은 실패 재처리 대기열입니다. 동일 URL의 수정 기사는 같은 모델에서 다시 예측하지 않습니다. 한 기사가 여러 기업을 다루면 기업별 결과가 있습니다. 기사 시각은 UTC입니다.

하루 기준 종목 목록을 갱신하고 우선주를 포함한 주식만 선정합니다. 종목당 최신 검색 결과 100개만 확인하며, 최대 건수 도달 종목은 capped_stocks에 표시합니다. 최근 24시간 호출을 재시도 포함 22,000회로 제한합니다. 같은 키를 사용하는 다른 프로그램의 횟수는 포함하지 않습니다. 과거 전체 뉴스 복원 기능은 없습니다.

모델의 테스트 정확도 약 84.98%, macro F1 약 0.8467은 공개 평가셋 기준이며 200종목 각각의 실뉴스 성능 보장이 아닙니다. 짧은 기업명·간접 언급·우선주 고유 영향은 검토가 필요합니다. 제목·요약만 사용합니다.

## 검증 범위

뉴스 수집·모델 예측·DB 저장 및 저장값 읽기 비교를 검증했습니다. 배포 환경에서는 1회 실행으로 DB 저장을 확인하고, 백엔드 빌드·API 응답·프론트 연결 및 정기 수집의 연속 운영을 별도로 확인하세요.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Git에는 코드·SQL·설명·모델 메타데이터만 추가합니다. 모델 가중치, 수집 기사, 실제 설정·키·비밀번호, 가상환경, 로그는 제외합니다.





---------프론트전달내용--------

요청
GET /api/stocks/{stockCode}/news?limit=30

예: /api/stocks/005930/news?limit=30

limit: 기본 30, 최대 100

결과 없는 종목은 빈 배열 []

화면에 사용할 응답 필드

title: 기사 제목

description: 기사 요약

url: 기사 원문 링크

publishedAt: 기사 시각(UTC → 한국 시간으로 표시)

label: positive 긍정 / neutral 중립 / negative 부정

positive, neutral, negative: 각 분류 확률(0~1, 화면에서는 ×100%)

stockCode, stockName: 종목코드·종목명

articleId: 기사 ID

기사 목록에 제목·날짜·감성 배지를 표시하고, 제목을 누르면 원문 링크로 이동하면 됩니다. 감성 결과는 매수·매도 추천과 구분해서 표시해주세요.

수집기가 실행 중이면 15분마다 새 뉴스가 추가됩니다. 프론트에서 NAVER API나 AI 모델을 직접 호출할 필요는 없습니다.

백엔드 빌드·재시작 후 실제 API 응답 확인이 필요합니다. 서버 주소와 인증 방식은 백엔드 담당자와 맞춰주세요.