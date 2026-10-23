# 시장별 상위 20개 종목 수집 (최신 실행 방식)

현재 기본 명령은 **코스피 20 + 코스닥 20 = 총 40종목**을 5분간 수집하는 `top-tick`입니다.
상위 기준은 한국투자증권 종목 마스터의 **전일 거래량**입니다.
현재 당일 장중 순위가 아닌 마스터에 기재된 전일 거래량 기준입니다. 주식 그룹(ST), 숫자 6자리 종목만 사용하며 ETF/ETN 등은 제외합니다. 우선주는 별도로 제외하지 않습니다.
동률은 종목코드순으로 결정합니다. 목록을 하드코딩하지 않고 실행할 때 마스터를 내려받습니다.
모의투자 전용 설정을 유지하며 실전 서버나 키로 자동 전환하지 않습니다.

## 실행

```powershell
cd C:\Users\moonj\Desktop\CapstoneDesign_2026\backend\data_collector
python -m pip install -r requirements.txt

# 종목 선정만 확인 (KIS 인증 및 DB 접속 없이 공식 마스터 다운로드)
python data_collector.py top-list

# 40종목의 실시간 체결을 한 웹소켓에서 5분간 수집 → 종목별 CSV
python data_collector.py top-tick

# 40종목 과거 일봉 수집 → 종목별 CSV
python data_collector.py top-daily --start 2025-01-01 --end 2025-12-31
```

`python data_collector.py`만 입력해도 top-tick입니다. 기존 단일 종목 수집은
`python data_collector.py collect5 --codes 005930`처럼 명시적 모드를 사용합니다.
기존 stream/history/snapshot 등은 유지되며 기존 저장 경로를 사용합니다.
**새 종목별 디렉토리 구조는 top-tick/top-daily에 적용됩니다.**

## 저장 구조

```text
data/
  005930/
    tick_YYYYMMDD_HHMMSS_ffffff/
      ticks.csv
    daily_시작일_종료일_YYYYMMDD_HHMMSS_ffffff/
      daily.csv
  다른종목코드/
    ...
  runs/
    universe_시간.json
    tick_시간.json
    tick_시간.raw.jsonl
    daily_시간.json
```

시간은 한국 시간이며 마지막 6자리는 마이크로초로 같은 초의 실행 충돌을 줄입니다.
CSV를 덮어쓰지 않습니다. 종목별 ticks.csv에는 수신 원본 47개 필드를 모두 보존하고,
일봉 CSV에는 기존 daily_chart_data에 대응하는 필드를 기록합니다.
runs의 universe에는 종목코드/이름/시장/순위/마스터 전일 거래량/다운로드 시각/출처 URL과 Last-Modified를 남깁니다.
이 목록을 그대로 다시 쓰려면 `--universe data/runs/universe_실제시간.json`을 추가합니다.
선정 시점은 유지되며 이 옵션으로 현재 순위를 재조회하지 않습니다.
테스트용으로 `--per-market 2`를 지정하면 시장별 2개를 수집합니다.

## 실시간 동작

한 연결에 최대 40종목을 순차 구독하고 첫 구독 요청 직전부터 공통 300초를 측정합니다.
약 4초의 순차 구독 시간도 수집 구간에 포함되므로 모든 종목에 정확히 300초의 체결이 보장되지는 않습니다.
모든 정상 체결을 종목코드별로 분리해 DataFrame/CSV에 기록합니다.
모의투자 웹소켓 주소는 `ws://ops.koreainvestment.com:31000/`입니다. `/tryitout`에서 HTTP 응답 없이 연결이 종료되는 현상을 확인하여 루트 경로로 수정했습니다.
초기 웹소켓 연결은 시스템 프록시를 사용하지 않는 직접 연결이며, 실패하면 2/4/8/16초 간격으로 최대 5회 시도합니다. 연결 성공 후부터 300초를 측정합니다.
잘못된 수신 형식과 서버 구독 오류, 수집 중 연결 끊김은 원인을 표시하고 실패로 종료합니다. 이미 저장한 CSV는 남고 failed manifest는 자동 DB 적재하지 않습니다.
초기 연결의 `did not receive a valid HTTP response`는 체결 컬럼이나 명령 인수 오류가 아니라 웹소켓 HTTP 핸드셰이크 실패입니다. 서버/네트워크 문제는 재시도 후에도 남을 수 있습니다. 이때 PowerShell에서 `Test-NetConnection ops.koreainvestment.com -Port 31000`으로 TCP 접근을 확인하세요(TCP 성공만으로 웹소켓 정상 동작을 보장하지는 않음).
관련 구현은 kis_websocket.py이며 data_collector.py/market_batch.py와 함께 보관해야 합니다.
체결 원본은 runs의 .raw.jsonl에 보관합니다(인증 JSON은 기록하지 않음).
장외 또는 거래가 없으면 해당 CSV가 비어 있을 수 있고 빈 종목의 분봉은 생성하지 않습니다.
실시간 거래가 없는 저녁 시연에서는 미리 수집한 CSV를 사용해야 합니다.
기존 수집 프로세스가 별도로 구독 중이면 계정 단위 한도에 걸릴 수 있으므로 함께 실행하지 마세요.

## 일봉 동작

40종목을 순서대로 조회하며 기간을 90일씩 나눕니다.
기존 Collector의 요청 간격(응답 후 1.1초)과 EGW00201 재시도를 사용합니다.
오래된 기간에도 **현재 선정 목록의 종목**을 조회합니다. 과거 당시의 상위 20개를 재구성하는 것은 아닙니다.
모든 종목을 완료하면 manifest 상태가 complete가 됩니다.
실패 시 이미 받은 CSV는 남지만 manifest는 failed이므로 자동 DB 적재하지 않습니다.

## MySQL 저장

기본은 CSV만 저장합니다. DB 연결정보 없이도 수집할 수 있습니다.

### 수집 직후 자동 저장

```powershell
python data_collector.py top-tick --save-db
python data_collector.py top-daily --start 2025-01-01 --end 2025-12-31 --save-db
```

### 이미 수집한 결과 저장

수집 종료 로그에 표시된 **tick_시간.json 또는 daily_시간.json manifest**를 지정합니다.
universe_시간.json은 수집 파일 목록이 아니므로 load-db에 사용하지 않습니다.

```powershell
# 검증만: DB 접속 없음
python data_collector.py load-db --manifest data/runs/tick_실제시간.json --dry-run
# 실제 저장
python data_collector.py load-db --manifest data/runs/tick_실제시간.json
python data_collector.py load-db --manifest data/runs/daily_실제시간.json
```

기존 stock/minute_chart_data/daily_chart_data 테이블이 필요합니다. 테이블 생성·변경은 하지 않습니다.
MYSQL_HOST=127.0.0.1, MYSQL_PORT=3306, MYSQL_USER=root, MYSQL_DATABASE=stockpilot_db가 기본값입니다.
MYSQL_PASSWORD가 없으면 저장 단계에서 비밀번호를 숨김 입력합니다. README에 비밀번호를 적지 마세요.

| 수집 결과 | DB 저장 |
|---|---|
| 선정 목록 | stock의 stock_code, stock_name, market 등록/갱신 |
| top-tick | 5분 수집 구간을 종목당 1행으로 집계 → minute_chart_data |
| top-daily | 거래일별 일봉 → daily_chart_data |

stock의 current_price/marketCap 등 시세는 이 배치에서 갱신하지 않습니다.
필요하면 기본정보 적재 후 기존 snapshot 모드로 조회하세요.
전체 CSV 검증 후 하나의 트랜잭션으로 적재합니다. 기본키가 같으면 갱신하므로 재실행에 따른 중복 삽입은 없습니다.
CSV 파일은 수정하지 않습니다. DB 저장 실패 시 CSV와 complete manifest로 재시도할 수 있습니다.

5분 집계의 candle_start는 공통 수집 시작 시각이며 정규 5분 경계에 맞춘 봉은 아닙니다.
시가는 처음, 고가는 최대, 저가는 최소, 종가는 마지막 체결 가격입니다.
volume은 마지막 ACML_VOL(당일 누적량), 등락금액/률도 마지막 체결 값입니다.
체결이 없는 종목을 제외하면 최대 40행입니다.
기존 테이블에는 주기 구분이 없으므로 기존 1분봉과 섞어 조회하지 마세요.

모듈 의존성: data_collector.py + market_batch.py + db/import_ticks.py + db/import_daily.py,
기존 ../Test_Project/kis_auth.py 및 ../examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py를 사용합니다.
auth.yaml과 토큰은 기존 개인 설정 경로를 사용합니다.

검증: `python -B -m unittest discover -s . -p "test_market_batch.py" -v`

---
아래는 기존 단일 종목 모드 설명입니다. 기본 실행과 상위 종목 수집은 위 안내를 따르세요.

# StockPilot 데이터 수집기

기존 MySQL 테이블에 현재가, 실시간 분봉, 과거 일봉을 저장합니다. 테이블 생성/변경이나 주문 기능은 없습니다.

## 설정

```powershell
python -m pip install -r NEW/requirements.txt
$env:MYSQL_HOST = '127.0.0.1'
$env:MYSQL_PORT = '3306'
$env:MYSQL_USER = 'root'
$env:MYSQL_DATABASE = 'stockpilot_db'
```

위 연결값은 기본값이므로 같으면 환경변수를 생략합니다. Workbench의 `StockPilot`은 연결 표시 이름이며 DB 이름은 `stockpilot_db`입니다. Workbench에 저장된 비밀번호를 자동으로 읽지 않습니다. `MYSQL_PASSWORD` 환경변수가 없으면 실행할 때 비밀번호를 숨김 입력합니다. 비밀번호를 코드나 명령줄 인수에 적지 마세요.

기본 인증 파일은 저장소의 `Test_Project/kis_auth.py`입니다. 실행하는 폴더에 관계없이 스크립트 위치를 기준으로 찾으므로 별도 경로 설정이 필요하지 않습니다. 다른 인증 파일을 사용할 때만 다음 설정을 사용하세요.

```powershell
$env:KIS_AUTH_FILE = 'C:\실제경로\kis_auth.py'
# 또는 실행 명령에 --auth-file C:\실제경로\kis_auth.py 추가
```

`Test_Project/kis_auth.py`를 확인하여 `auth`, `auth_ws`, `_url_fetch`, `data_fetch`, `smart_sleep`, `getTREnv` 인터페이스를 사용하도록 연결했습니다. 이 파일은 사용자 홈의 `KIS/config/auth.yaml`을 읽고 같은 폴더에 토큰을 저장합니다. 해당 폴더와 YAML 설정이 준비되어 있어야 합니다. 인증 모듈의 설정 파일 참조를 `auth.yaml`로 변경했으며, YAML 내용은 수정하거나 복사하지 않았습니다. `auth.yaml`은 Git 추적에서 제외됩니다. 기존에 `KIS_AUTH_FILE`을 설정했다면 그 값이 기본 경로보다 우선하므로 불필요한 설정은 제거하세요.

이 수집기는 **모의투자 전용**입니다. REST와 웹소켓 인증 모두 `svr="vps", product="01"`로 호출하고, 실전 옵션은 거부합니다. 인증 전 `vps=https://openapivts.koreainvestment.com:29443`, `vops=ws://ops.koreainvestment.com:31000`인지 검사하며 인증 후에도 세션을 검사합니다. `paper_app`, `paper_sec`, `my_paper_stock`을 사용합니다. 토큰은 공용 캐시 대신 `KIS/config/KIS_demo_YYYYMMDD`에 저장합니다. 웹소켓은 공식 KRX 예제와 같은 `/tryitout` 경로를 사용합니다. HTTP 핸드셰이크 실패도 최대 5회 연결을 시도하며 오류 종류와 접속 URL을 로그에 남깁니다. 시세 수집만 수행하며 주문 API를 호출하지 않습니다. 모의투자 접속은 가상 가격을 생성한다는 의미가 아닙니다.

## 삼성전자 예제와 PyCharm 설정

인수 없이 `data_collector.py`를 실행하면 **삼성전자 / 005930 / KOSPI** 기본정보를 `stock`에 upsert하고 현재가를 수집합니다. 기존 행의 시세는 초기화하지 않습니다. 실시간 분봉까지 받으려면 Parameters에 `stream`을 입력하세요. 과거 일봉은 `history --start 2025-01-01 --end 2025-12-31`로 실행합니다.

PyCharm의 **Run → Edit Configurations → + → Python**에서 설정합니다.

첨부하신 화면은 항목명이 다음처럼 표시됩니다.

1. **Python interpreter**: `Run` 제목 바로 아래의 첫 번째 긴 드롭다운입니다. 화면에는 `…\NEW\.venv 3.14.3`이 선택되어 있습니다. 이 가상환경에 의존성을 설치하면 그대로 사용하면 됩니다.
2. **Script path**: 다음 줄에서 왼쪽 `script` 드롭다운 **오른쪽의 빈 입력칸**입니다. 아래 표의 전체 `.py` 파일 경로를 입력하거나 오른쪽 폴더 버튼으로 선택하세요. 왼쪽의 `script` 선택은 유지합니다.
3. **Parameters**: 그 바로 아래 `Script parameters`라고 표시된 입력칸입니다. `snapshot` 또는 `stream`을 입력합니다. `python`이나 스크립트 경로를 이 칸에 다시 적지 않습니다.
4. `Name`은 `Samsung demo collector`처럼 정하고, **Apply → Run**을 누릅니다. 아래의 `Please specify a script name` 오류는 Script path가 비어서 표시되는 것입니다.

현재 선택된 가상환경에 패키지를 설치하려면 PowerShell 터미널에서 다음 명령을 실행합니다.

```powershell
& 'C:\Users\moonj\.codex\worktrees\f764\open-trading-api\NEW\.venv\Scripts\python.exe' -m pip install -r 'C:\Users\moonj\.codex\worktrees\f764\open-trading-api\NEW\requirements.txt'
```

| 항목 | 값 |
|---|---|
| Script path | `C:\Users\moonj\.codex\worktrees\f764\open-trading-api\NEW\data_collector.py` |
| Working directory | `C:\Users\moonj\.codex\worktrees\f764\open-trading-api` |
| Parameters | `snapshot` (기본값, 생략 가능) 또는 `stream` |
| Python interpreter | `NEW/requirements.txt` 의존성을 설치한 인터프리터 |

현재 수정본은 위 worktree에 있습니다. Desktop 원본 프로젝트를 열어 두었더라도 Script path를 위 경로로 설정해야 수정본이 실행됩니다.

**Environment variables** 편집 창에서 아래 값을 각각 입력합니다. 값에 따옴표를 붙이지 않습니다.

| 변수 | 값 |
|---|---|
| MYSQL_HOST | `127.0.0.1` |
| MYSQL_PORT | `3306` |
| MYSQL_USER | `root` |
| MYSQL_DATABASE | `stockpilot_db` |
| MYSQL_PASSWORD | 본인의 MySQL 비밀번호 |
| PYTHONUNBUFFERED | `1` |
| PYTHONUTF8 | `1` |

`KIS_AUTH_FILE`은 기본 경로를 사용하므로 생략하고, 예전 값이 있다면 제거하세요. KIS 앱키/시크릿은 환경변수에 중복 입력하지 않고 `C:\Users\moonj\KIS\config\auth.yaml`에서 읽습니다. 비밀번호를 포함한 실행 설정은 공유하거나 Git에 저장하지 마세요. Run 설정의 환경변수는 별도로 실행한 Terminal에 자동 적용되는 설정이 아닙니다.

선택한 Python 인터프리터로 `python -m pip install -r NEW/requirements.txt`를 실행한 후, Parameters를 `check-db`로 설정해 DB 접속부터 확인할 수 있습니다. 실행 시 `모의투자 전용 | REST=... | WebSocket=...` 로그가 출력됩니다. 장외 시간에는 실시간 체결이 오지 않을 수 있습니다.

[PyCharm 공식 Python 실행 설정 안내](https://www.jetbrains.com/help/pycharm/run-debug-configuration-python.html)

## 장중 체결 CSV 저장과 장외 재생 테스트

현재 파서는 실제 수신에서 확인한 **47필드 형식**과 기존 46필드 형식을 모두 지원합니다. 47번째 필드는 의미를 추측하지 않고 `EXTRA_FIELD_47`로 DataFrame/CSV에 보존합니다. 기존 46필드 메시지는 이 컬럼을 빈 값으로 기록하여 한 CSV의 헤더를 유지합니다. DB에는 기존 매핑 필드만 전달하므로 테이블에 추가 컬럼을 만들 필요가 없습니다. 아래의 공식 예제 46개 컬럼 설명에 이 추가 컬럼이 붙는 구조입니다.

`stream` 및 `all` 모드는 전체 수신 컬럼을 DataFrame으로 만든 후 DB 처리 전에 CSV에 저장합니다. 기본 저장 폴더는 **수집기 파일 옆의 `NEW/data/tick`**이며 파일명은 `ticks_YYYYMMDD_HHMMSS_ffffff.csv`입니다. 메시지마다 flush하고 Ctrl+C 종료 시 파일을 닫습니다. 헤더는 첫 DataFrame 수신 시 생성하므로 수신 전 파일은 비어 있습니다. 기존 파일은 이동하지 않습니다.

`websocket_to_dataframe_csv(raw, columns, recorder)`는 공식 예제에 정의된 **전체 46개 컬럼**을 문자열 DataFrame으로 구성해 CSV에 기록하고 DataFrame을 반환합니다. 호가·체결량 등 DB에 사용하지 않는 컬럼도 보존합니다. `save_dataframe_to_tables(frame, store, codes)`는 그 DataFrame에서 DB 변환에 필요한 필드만 선택하여 기존 `stock`, `minute_chart_data`에 저장합니다. `Store.tick()`에서 DB 컬럼명으로 매핑하고 분봉 OHLC를 집계합니다. DB 변환이 실패해도 앞서 기록한 전체 컬럼 CSV는 남습니다. 컬럼 수를 해석할 수 없는 프레임은 임의로 자르지 않고 `.raw.jsonl`에 보존합니다.

CSV는 UTF-8 BOM 형식이며 `005930`의 앞자리 0을 유지합니다. Excel로 열어 다시 저장하면 종목코드가 바뀔 수 있으므로 원본을 보관하세요. 앱키와 인증 토큰은 기록하지 않습니다. 신규 전체 컬럼 CSV와 기존 8개 필드 CSV 모두 `replay`로 읽을 수 있습니다.

PyCharm **Script parameters**에 입력하는 예:

```text
# 장중: DB 저장 + 지정 경로에 원본 체결 CSV 저장
stream --csv NEW/data/tick/samsung_ticks.csv

# 장외: 저장된 체결 CSV로 분봉 집계 테스트 (KIS/DB 접속 없음)
replay --csv NEW/data/tick/samsung_ticks.csv --output NEW/data/tick/samsung_minutes.csv
```

위에서 `#`로 시작하는 설명 줄은 입력하지 않습니다. 상대 경로는 Working directory를 기준으로 합니다. 파일명에 공백이 있으면 큰따옴표로 감싸세요. **기존 파일을 덮어쓰거나 이어 쓰지 않습니다.** 같은 파일명으로 다시 실행하면 오류가 나므로 새 이름을 지정하거나 `stream`만 입력하여 자동 파일명을 사용하세요. replay의 `--output`을 생략하면 `NEW/data/tick/replay_minutes_시간.csv`를 새로 생성합니다.

`replay`는 원래 체결 시각을 유지하고 수신 순서대로 즉시 처리합니다. 실시간 대기 시간을 흉내 내지는 않습니다. 당일 누적 거래량 기준으로 중복/이전 체결을 제외하고 분별 시가·고가·저가·종가를 계산하여 CSV로 출력합니다. `volume`은 실시간 DB와 동일하게 당일 누적 거래량입니다. DB의 최신 시세를 과거 값으로 바꾸지 않도록 **재생 결과는 CSV에만 출력**합니다. 모의 인증 파일이나 MySQL 비밀번호도 필요 없습니다.

장외 시간에는 과거 실시간 체결을 새로 생성할 수 없으므로 먼저 장중에 기록한 CSV가 필요합니다. `snapshot`은 DB에 저장하고, `history`는 DB 및 별도 일봉 CSV에 저장합니다. 연결 공백 동안의 체결은 CSV에도 없으므로 완전한 분봉으로 복구되지는 않습니다. 재생은 파일 크기에 비례한 메모리를 사용하므로 거래일별 파일로 나누어 보관하세요.

### 헤더만 있는 CSV와 수신 진단

2026-10-14의 `ticks_20261014_172619_848988.csv`는 98바이트의 헤더만 남아 있었습니다. 파일 생성 후 `parse_ticks()`가 메시지 필드 수 불일치로 중단되어 실제 체결 저장이 실행되지 않았습니다. 당시 원본 프레임이 없어 불일치의 구체적인 원인(필드 추가/누락/구분자 등)은 확정할 수 없습니다.

수정본은 공식 예제의 H0STCNT0 **46개 필드** 순서를 사용합니다. 한 메시지의 다건 체결, 행 구분 개행, 마지막 `^` 구분자를 처리합니다. 정의와 다른 필드는 임의로 잘라 DB에 넣지 않습니다. 불일치 프레임은 제외하고 계속 수신하며 예상/실제 필드 수를 로그에 남깁니다. 체결 원본은 파싱 전에 같은 이름의 `.raw.jsonl` 파일에 기록합니다. 이 파일에는 체결 프레임만 담고 승인키가 포함될 수 있는 JSON 제어 메시지는 기록하지 않습니다. 반복 오류가 나면 이 파일로 실제 형식을 확인해야 합니다.

`구독 요청 완료`는 서버 승인이나 데이터 저장 완료를 의미하지 않습니다. 서버 승인 후 `구독 응답 성공`, 첫 체결 처리 후 `첫 체결 저장 완료` 로그를 구분해서 확인하세요. 모든 프레임이 거부되거나 시장에서 체결이 오지 않으면 전체 컬럼 CSV는 비어 있을 수 있습니다.

### 과거 일봉 CSV

```powershell
python NEW/data_collector.py history --codes 005930 --start 2025-01-01 --end 2025-12-31
```

기본 출력은 `NEW/data/daily/daily_시간.csv`입니다. `--history-csv NEW/data/daily/samsung_daily.csv`로 지정할 수 있으며 기존 파일은 덮어쓰지 않습니다. 각 페이지의 DB 저장 성공 후 동일한 값을 CSV에 기록합니다. 중단되면 이미 저장된 페이지까지 남습니다. DB와 파일은 하나의 원자적 트랜잭션이 아니므로 파일 쓰기 오류가 나면 해당 페이지는 DB에만 남을 수 있습니다.

일봉 CSV 컬럼은 `stock_code, trade_date, close_price, volume, change_amount, change_rate, open_price, high_price, low_price`입니다. `updated_at`은 DB에서 생성합니다. 실시간 `ticks_*.csv`는 재생용 원본 필드이며 DB 테이블에 그대로 INSERT하지 않습니다. 실시간 DB는 아래 매핑대로 변환하고, `replay` 결과는 `minute_chart_data`의 컬럼명(`updated_at` 제외)을 사용합니다.

## 실행

저장소 루트에서 실행합니다. 다른 폴더에서는 스크립트의 절대 경로를 사용합니다.

```powershell
# KIS 인증 없이 DB 접속과 세 테이블 컬럼 확인
python NEW/data_collector.py check-db

# 현재가/시가총액 저장
python NEW/data_collector.py snapshot --codes 005930 000660

# 전체 기간을 90일 단위로 나누어 원주가 일봉 저장
python NEW/data_collector.py history --codes 005930 --start 2025-01-01 --end 2025-12-31

# 현재가 조회 후 실시간 체결 수집. Ctrl+C로 종료
python NEW/data_collector.py stream --codes 005930 000660

# 현재가 + 과거 일봉 + 실시간 체결
python NEW/data_collector.py all --codes 005930 --start 2025-01-01 --end 2025-12-31

# 저장된 일봉으로 주봉/월봉을 조회하여 JSON 출력 (KIS 인증 불필요)
python NEW/data_collector.py chart --codes 005930 --start 2025-01-01 --end 2025-12-31 --period W
python NEW/data_collector.py chart --codes 005930 --start 2025-01-01 --end 2025-12-31 --period M
```

`--codes` 생략 시 삼성전자 `005930`만 사용하며, 수집 모드에서는 삼성전자 이름과 KOSPI 시장 정보를 자동 등록/갱신합니다. 다른 종목의 기본정보는 미리 등록해야 합니다. 실시간 모드는 최대 40종목이며, `--env demo`만 허용됩니다. KRX 국내주식 기준입니다. `check-db`와 `chart`는 종목정보를 변경하지 않습니다.

## 필드 매핑

| DB 컬럼 | KIS 필드/처리 |
|---|---|
| current_price | stck_prpr |
| marketCap | hts_avls 원본 값(억원 단위), 원화로 환산하지 않음 |
| change_amount | prdy_vrss: 전일 대비 금액, 부호 코드 반영 |
| change_rate | prdy_ctrt: 전일 대비율(%) |
| stock.volume | acml_vol: 당일 누적 거래량 |
| daily.close_price | stck_clpr |
| daily.volume | acml_vol: 해당 거래일 거래량 |
| daily.open/high/low_price | stck_oprc / stck_hgpr / stck_lwpr |
| trade_date | stck_bsop_date |
| minute.close_price | 해당 분 마지막 수신 체결가 STCK_PRPR |
| minute.open/high/low_price | 해당 분 수신 체결가의 첫 값/최대/최소 |
| minute.volume | ACML_VOL: 해당 분 마지막 수신 시점의 **당일 누적 거래량** |
| candle_start | BSOP_DATE + STCK_CNTG_HOUR를 분 단위로 절삭한 한국 거래소 시간 |
| updated_at | DB의 CURRENT_TIMESTAMP |

제공된 SQL 주석의 `prdy_ctrt`/`prdy_vrss` 설명은 뒤바뀌어 있어 컬럼의 의미에 맞춰 수정 매핑했습니다. `sck_lwpr`는 `stck_lwpr`의 오타입니다. 일봉 응답 output2에는 등락률이 없어 `등락금액 / (종가 - 등락금액) * 100`으로 계산합니다. 전일 종가가 0이면 NULL을 저장합니다.

웹소켓의 STCK_OPRC/HGPR/LWPR는 **당일** 시고저가이므로 분봉에 그대로 넣지 않습니다. 분봉 거래량도 당일 누적량이므로 차트에서 분당 거래량으로 표시하려면 연속된 분봉 사이의 차이를 사용해야 합니다. 수집 시작 분, 연결 공백 또는 거래일 경계에서는 단순 차분으로 완전한 분당 거래량을 복구할 수 없습니다.

`daily_chart_data`의 기본키에는 봉 주기 구분이 없어 일/주/월봉을 같이 저장하면 덮어쓰게 됩니다. 따라서 일봉만 저장하고 `chart --period W/M` 또는 `Store.chart()`로 집계합니다. 주봉은 ISO 주(월요일 시작), 월봉은 달력 월 기준입니다. 첫 거래일을 trade_date로 사용하며, 등락금액/률은 기간 첫 거래일의 전일 종가 대비 마지막 종가로 계산합니다. 조회 범위 양 끝은 부분 주/월봉일 수 있고, 휴일과 실제 누락은 자동으로 구별하지 않습니다.

## 동작과 한계

### REST 호출 속도와 EGW00201

REST는 기본적으로 **응답 완료 후 1.1초 이상** 기다린 뒤 다음 요청을 보냅니다. 인증 직후 첫 시세 요청도 기다리며 종목과 일봉 페이지가 같은 제한을 공유합니다. 기존 인증 모듈의 짧은 `smart_sleep()` 대신 수집기에서 간격을 직접 관리합니다. 이는 이 프로세스에만 적용되므로 같은 앱키를 사용하는 다른 프로그램은 별도로 중지하거나 호출량을 조정해야 합니다.

`EGW00201`이면 동일 페이지를 2·4·8·16·32초 간격으로 최대 5회 재시도합니다. 지정한 요청 간격이 더 길면 그 값을 적용합니다. HTTP 500 본문에 들어 있는 `msg_cd`도 확인합니다. 다른 오류는 즉시 중단하고, 이미 저장한 페이지는 유지합니다. 재실행 시 일봉 upsert로 기존 데이터가 중복되지 않습니다.

```powershell
python NEW/data_collector.py history --codes 005930 --start 2025-01-01 --end 2025-12-31 --request-interval 1.1 --max-retries 5
```

여전히 제한에 걸리면 `--request-interval 2`처럼 더 늘릴 수 있습니다. 이것은 **API 요청 속도**이며, 웹소켓으로 들어오는 시장 체결 수나 CSV 기록 수를 줄이지 않습니다.

### 세 테이블의 저장 범위

| 실행 모드 | stock | daily_chart_data | minute_chart_data |
|---|---|---|---|
| snapshot (기본) | 현재가·시가총액·등락·누적거래량 | 저장 안 함 | 저장 안 함 |
| history | 삼성전자 기본정보만 등록/갱신 | 지정 기간의 일봉 | 저장 안 함 |
| stream | 최초 현재가/시가총액 + 체결마다 시세 갱신 | 저장 안 함 | 체결을 받은 분의 분봉 |
| all | 현재가 + 실시간 시세 | 지정 기간의 일봉 | 체결을 받은 분의 분봉 |
| replay / chart / check-db | DB 쓰기 없음 | DB 쓰기 없음 | DB 쓰기 없음 |

세 테이블을 모두 수집하는 명령:

```powershell
python NEW/data_collector.py all --codes 005930 --start 2025-01-01 --end 2025-12-31 --request-interval 1.1
```

현재가 → 일봉 → 실시간 체결 순서입니다. 장외에는 실시간 체결이 없으므로 `all`도 새 분봉을 만들지 않습니다. 실시간 체결의 당일 시고저가 대신 수신 체결을 분별로 집계하고, 분봉 거래량은 요청하신 당일 누적 거래량을 저장합니다. 모드별 저장 완료는 실제 DB에서 확인해야 하며 오프라인 테스트만으로 실제 행 존재를 보장하지 않습니다.

- 현재가 조회 실패 시 저장을 중단하며, 없는 숫자를 0으로 대체하지 않습니다.
- 과거 일봉은 기본키 기준 upsert하므로 재실행해도 중복 행이 생기지 않습니다. 원주가(`FID_ORG_ADJ_PRC=1`)를 저장합니다.
- 실시간 메시지 한 개에 여러 체결이 들어와도 모두 처리합니다. 누적 거래량과 분 시각으로 중복/이전 체결을 건너뜁니다. 분봉의 첫 가격은 재시작해도 보존합니다.
- 실시간 체결마다 분봉과 stock 시세를 같은 트랜잭션에 저장합니다. 시가총액은 최초 REST 조회 시점 값입니다. 필요할 때 `snapshot`으로 갱신하세요.
- 이 수집기는 한 프로세스로 실행하세요. DB 오류 시 롤백하고 종료합니다. 앞서 커밋된 일봉 페이지와 체결은 유지됩니다.
- 네트워크 단절은 최대 5회 연속 재연결합니다. 연결 중단 중 체결이나 수집 시작 전 체결을 소급 복원하지 않습니다. 누락된 분봉이 자동으로 완성된다고 가정하면 안 됩니다.
- 실시간 수집은 체결당 DB 쓰기를 수행합니다. 구독 종목이 많으면 처리 지연이 생길 수 있습니다.

## 참고한 예제

- `examples_llm/domestic_stock/inquire_price/inquire_price.py`: FHKST01010100 현재가
- `examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py`: FHKST03010100 기간별 시세
- `examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py`: H0STCNT0 구독 메시지와 컬럼 목록을 직접 재사용

REST는 예제와 같은 엔드포인트/인자를 `kis_auth._url_fetch`에 전달합니다. 예제가 실패 응답을 빈 DataFrame으로 반환하는 대신 수집기는 실패를 명시적으로 처리합니다. 웹소켓은 예제 KISWebSocket의 단일행 파싱 대신 건수에 맞춰 여러 체결을 분리합니다.

오프라인 테스트: `python -m unittest discover -s NEW -p "test_*.py" -v`
