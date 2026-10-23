# 화면 실시간 가격 + 200종목 AI 분봉

## 구분

1. live_quotes.py: 선택 종목의 KRX 실시간 체결을 WebSocket으로 수신합니다.
   stock_live_quotes에 종목별 최신 가격을 저장합니다. 전체 틱 기록이나 분봉 생성은 하지 않습니다.
   수신과 DB 저장을 별도 스레드로 분리해 최대 0.5초 간격으로 최신값을 모아 저장합니다.
   모든 틱을 DB에 보존하는 구조가 아니므로 이 테이블로 분봉 OHLCV를 만들지 마세요.
2. collector.py --ai-cycle: 200종목의 완성된 분봉을 같은 5분 경계로 맞춰 조회합니다.
   predictor.py는 기존대로 해당 경계의 충분한 시장 데이터가 준비되면 예측합니다.

기존 .env를 재사용합니다. 덮어쓰지 마세요. 기존 수집기는 Ctrl+C로 중단하고 새 명령으로 실행합니다.
AI 추론기 자체는 변경하지 않았습니다.

## 최초 설치 및 테이블 생성

```powershell
cd <프로젝트 경로>\ai\live_collector
..\.venv\Scripts\python.exe -m pip install -r requirements-realtime.txt
..\.venv\Scripts\python.exe live_quotes.py --init-db
```

stock_live_quotes만 새로 생성합니다. minute_chart_data/ai_opinions 구조는 변경하지 않습니다.

## 창 1: 화면용 현재가

```powershell
cd <프로젝트 경로>\ai\live_collector
..\.venv\Scripts\python.exe live_quotes.py --write
```

watchlist.json 기본값은 삼성전자입니다. 실행 중 파일을 수정하면 구독도 교체합니다.
예: {"symbols": ["005930", "000660"]}
구독 변경은 파일 확인 및 소켓 수신 대기 때문에 약 2~12초 걸릴 수 있습니다.
동시에 최대 40종목을 사용하도록 제한했습니다. 다른 WS 프로그램을 같은 앱키로 실행하지 마세요.
거절 응답이나 데이터 형식 변경 시 중단합니다. 연결 단절은 제한된 횟수로 재접속합니다.
--write를 빼면 수신 확인만 하고 DB에는 쓰지 않습니다.

## 창 2: AI용 200종목 분봉

```powershell
cd <프로젝트 경로>\ai\live_collector
..\.venv\Scripts\python.exe collector.py --universe ..\data\top200-20261012.json --write --loop --ai-cycle
```

완성 확인용 1분 여유는 유지합니다. 예: 11:01부터 11:00 경계 분봉을 모읍니다.
모든 종목의 cutoff가 같아 서로 다른 시각의 스냅샷을 섞는 문제를 줄입니다.
--ai-cycle에서는 기존 60초 추가 대기가 없어지고 다음 경계가 준비될 때까지 확인합니다.
DB가 빈 종목의 당일 데이터 보충은 처음에 여전히 오래 걸립니다.
ai_cycle_finished 로그의 seconds와 target_expired로 실제 처리 속도/유효시간 초과를 확인하세요.
특정 종목 호출이 실패하면 다음 경계에서 DB 마지막 시각부터 재수집합니다.
기존 중간 구멍은 --backfill-today로 별도 복구할 수 있습니다.

기본 호출 간격 0.6초(200종목 약 120초+응답시간)는 계정 한도 미확인 상태에서 유지합니다.
실전 REST 일반 공지는 초당18건이지만 신규고객 등 별도 제한과 다른 프로그램 사용량이
있을 수 있습니다. 본인 계정에서 초당10건 사용 가능함을 확인한 경우에만 다음처럼 설정하세요.

```powershell
..\.venv\Scripts\python.exe collector.py --universe ..\data\top200-20261012.json --write --loop --ai-cycle --request-delay 0.1 --confirmed-fast-rest
```

이를 실행하면 앞 명령은 반드시 중단합니다. 권장 간격 안내와 계정 실제 한도를 먼저 확인하세요.
200종목 한 페이지씩이면 간격만 약20초이지만 순차 HTTP 응답·DB 처리·재시도로 더 걸립니다.
시간 보장이 아닙니다. 429/유량 제한 응답 시 속도를 자동으로 낮춥니다.
다른 REST 수집/학습 데이터 다운로드와 같은 계정 한도를 공유합니다.

## 창 3: 기존 AI 추론

```powershell
cd <프로젝트 경로>\ai\live_collector
..\.venv\Scripts\python.exe predictor.py --write --loop
```

처음 사용한다면 먼저 predictor.py --init-db를 실행합니다.
시장 정보가 부족하면 WAIT가 정상입니다. 만료된 대상에는 예측을 쓰지 않습니다.
5분마다 항상 199종목을 예측한다는 보장은 없습니다. 지연/휴장/누락은 로그로 확인합니다.

## Spring/프론트 전달 계약

Python 수신 → DB 최신 가격까지 구현한 단계입니다. 이 코드를 실행한다고 기존 프론트가
자동으로 변경되지는 않습니다. Spring 담당이 선택 종목 목록 갱신과 가격 조회/푸시를 연결해야 합니다.

- watchlist.json은 한 계정의 전역 선택 종목 목록입니다. 서버는 활성 화면의 종목을 합쳐
  최대40개로 제한하고, 임시 파일 생성 후 원자적으로 교체하세요. 사용자별 세션을 만들지 마세요.
- 현재가/그래프의 마지막 가격 점: stock_live_quotes.price.
- trade_time: 거래소 체결 시각(KST DATETIME), received_at: 수신 시각(KST DATETIME(6)).
- tick_volume은 마지막 체결량, cumulative_volume은 당일 누적량입니다. 1분 거래량이 아닙니다.
- 과거 확정 캔들: minute_chart_data. 실시간 가격 점은 확정 분봉과 구분해서 표시하세요.
- 가격 등락폭: change_amount, 등락률(%): change_rate.
- 최신 체결이 없으면 이전 값이 남습니다. trade_time/received_at을 함께 내려 보내고
  장외·거래정지·무체결·연결 끊김을 '지금 발생한 체결'로 표시하지 마세요.
- 이 테이블만으로 연결 상태를 확정할 수 없습니다. 수신 시각과 Python ws_disconnected 로그를
  확인하세요. 오래된 값은 마지막 가격으로 표시하고 실시간 표시를 제거하세요.
- 같은시각 중복/과거 체결은 누적거래량과 거래소 시각으로 순서를 비교해 역행을 방지합니다.

```sql
SELECT stock_code,price,trade_time,received_at,change_amount,change_rate,cumulative_volume,
       TIMESTAMPDIFF(SECOND,received_at,UTC_TIMESTAMP()+INTERVAL 9 HOUR) AS received_age_seconds
FROM stock_live_quotes WHERE stock_code='005930';
```

세션/구독 제한은 계정 전체에 적용됩니다. 신규 소켓 여러 개로 200종목 제한을 우회하지 않습니다.
KIS 공식 공지: https://apiportal.koreainvestment.com/community/10000000-0000-0011-0000-000000000001/post/d0d1a83f-6f8d-4437-9700-6d26702fd989
체결 형식: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py
공식 샘플의 ws://ops.koreainvestment.com:21000, H0STCNT0을 사용합니다. 주문 없음.

## 검증

```powershell
..\.venv\Scripts\python.exe -m unittest test_collector test_realtime -v
```

실제 장중 수신·DB 기록·Spring 화면 반영은 별도 실행 확인이 필요합니다.
종료 직전 버퍼에 남은 최신값은 보존되지 않을 수 있으나 재연결 후 새 체결로 갱신됩니다.
