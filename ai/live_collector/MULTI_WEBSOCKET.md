# 200종목 모의 WebSocket 수신 (5개 독립 앱키)

## 전제
KIS에 API 사용이 허용된 독립 계좌별 모의 앱키 5쌍이 필요합니다. 개인이 모의계좌 5개를 개설하거나 서로 독립된 한도를 부여받을 수 있는지는 이 코드가 보장하지 않습니다. 동일 키를 복사하거나 세션만 여러 개 여는 방식은 지원하지 않습니다. 계좌 발급 가능 여부와 배포 화면 시세 이용 범위는 KIS에 확인해야 합니다. 팀원의 키를 허가 없이 사용하지 마세요.

공식 공지의 계좌별 실시간 등록 한도 내에서 계좌당 현재가 체결 40개만 요청합니다. 코스피 20개 + 코스닥 20개를 5개 연결에 나눕니다. 호가·체결통보·주문은 사용하지 않습니다. 기존 KIS_APP_KEY를 재사용하지 않고 KIS_PAPER_1~5 키만 사용합니다.

## 설치 및 설정
ai/README.md의 Python 설치를 완료하고 ai/live_collector에서 실행합니다. websocket-client는 ai/requirements.txt에 포함되어 있습니다.

```powershell
if (!(Test-Path .env.paper)) { Copy-Item .env.paper.example .env.paper }
notepad .env.paper
```
각 번호에 서로 다른 계좌의 모의 앱키와 시크릿을 넣습니다. 키는 채팅·GitHub에 올리지 않습니다. DB 설정은 기존 .env의 STOCKPILOT_DB_*를 사용합니다. .env.paper는 .gitignore의 .env.* 규칙으로 제외됩니다. 이번 구현은 모의 서버 전용입니다. 실전 키를 넣거나 도메인만 임의 변경하지 마세요.

## 실행 전 오프라인 확인
```powershell
..\.venv\Scripts\python.exe live_quotes_multi.py --check-plan
..\.venv\Scripts\python.exe live_quotes_multi.py --check-config
```
--check-plan은 키 없이도 코스피100/코스닥100 분할을 보여줍니다. --check-config는 키 5쌍과 중복 여부만 검사하며 실제 발급/연결 가능 여부를 검증하지 않습니다. data/top200-20261012.json이 기본 목록입니다. 다른 목록은 --universe로 지정하되 100+100 조건을 만족해야 합니다.

## DB 테이블 준비
```powershell
..\.venv\Scripts\python.exe live_quotes_multi.py --init-db
```
stock_live_quotes_paper만 생성합니다. 실전 stock_live_quotes, 분봉, 일봉, AI 의견은 건드리지 않습니다. 모의 수신 값을 실전 테이블에 섞지 않습니다.

## 실제 연결 시험 및 저장
먼저 저장 없이 수신:
```powershell
..\.venv\Scripts\python.exe live_quotes_multi.py
```
구독 승인이 확인되면 Ctrl+C로 종료한 뒤 저장 모드로 실행:
```powershell
..\.venv\Scripts\python.exe live_quotes_multi.py --write
```
한 서버에서 한 인스턴스만 운영합니다. 다른 프로그램이 같은 모의 앱키로 소켓을 열면 세션이 충돌할 수 있습니다. 기존 실전 키의 프로그램은 별도이나 같은 키로 중복 연결하지 마세요. 실행 중 종목 목록 변경은 자동 반영하지 않습니다. 목록 변경 시 중단 후 재실행하세요.

## 성공 확인
- paper_subscription_plan: 요청할 종목 배정. 아직 연결 성공이 아닙니다.
- paper_ws_connected: 소켓 연결 및 요청 전송. 아직 전체 구독 승인이 아닙니다.
- paper_ws_status.acknowledged: 현재 연결에서 서버가 승인한 종목 합계. 200이어야 전체 구독 승인입니다.
- accounts: 각 slot의 acknowledged=40, symbols_seen_since_connect, symbols_received_last_60s 확인.
- paper_quotes_preview: 받은 체결을 DB 저장 없이 처리 중.
- paper_quotes_saved: 최신값 묶음 DB 저장 처리 완료. 중복/과거 체결은 DB에서 건너뜁니다.
- paper_ws_ready: 해당 계좌의 40종목 구독 승인이 완료되어 다음 연결을 진행합니다.
- subscription_complete: 선택한 모든 계좌의 구독 승인이 완료됐는지 표시합니다. 실제 수신 여부는 accounts의 수신 수를 함께 확인하세요.
- missing_slots / missing_subscription_symbols: 구독이 완료되지 않은 계좌 번호와 미승인 종목 수입니다. 부분 수신 중이면 전체 성공으로 취급하지 않습니다.
- paper_ws_disconnected: 연결 오류는 해당 계좌만 재시도합니다. 10회 이상 실패해도 전체 종료하지 않고 60초 간격으로 재시도합니다.
- paper_ws_failed: 구독 거절·형식 오류는 해당 계좌를 중단합니다. 다른 계좌는 계속 수신합니다. 설정/원인을 확인한 뒤 재실행하세요.
- DB 연속 실패 10회도 종료 코드 1입니다. 재시작 전 원인을 확인하세요.

구독 승인이 200이어도 모든 종목이 매초 거래되는 것은 아닙니다. 휴장·거래정지·무체결·모의 서비스 상태에 따라 데이터가 없을 수 있습니다. 모의 서비스의 실제 시세 제공 특성과 지연은 장중 연결로 확인해야 합니다. 서버 거절 메시지 원문은 비밀정보 노출 방지를 위해 출력하지 않습니다.

```sql
SELECT COUNT(*) AS stored_symbols, MIN(received_at), MAX(received_at)
FROM stock_live_quotes_paper;
SELECT stock_code,price,trade_time,received_at
FROM stock_live_quotes_paper ORDER BY received_at DESC LIMIT 20;
```
누적 테이블 행 수 200은 현재 연결 성공을 의미하지 않습니다. 최신 수신 시각과 구독 승인 로그를 함께 확인하세요.

## Spring 전달
모의 테스트 화면은 stock_live_quotes_paper에서 읽고 모의 연결임을 표시하세요. 기존 stock_live_quotes를 읽는 API는 자동 전환되지 않습니다. stock.market 종목 마스터도 이 프로그램에서 갱신하지 않습니다. 운영용 전환은 모의 연결 검증 및 제공사의 허용 범위 확인 후 별도로 정하세요.

## 구조 및 종료
5개 수신 스레드 + 하나의 DB 저장 스레드가 동작합니다. 최신값만 합쳐 약0.5초마다 저장하므로 전체 체결 이력이 아니며 분봉 생성에 사용하면 안 됩니다. 접속키 발급은 전체 연결에서 1.1초 이상 간격으로 직렬화합니다. 초기 연결은 계좌 순서대로 진행하고, 40종목 승인 또는 실패 후 다음 계좌로 넘어갑니다. 재접속도 인증부터 구독 승인까지 한 번에 한 계좌만 진행하며, 이미 연결된 계좌의 수신은 계속됩니다. 구독 승인 대기 한도는 요청 전송 후 60초입니다. 연결 오류는 2~30초 간격으로 재시도하고 10회부터 60초 간격을 사용합니다. 이 변경은 연결 안정성을 보장하지 않습니다. Ctrl+C 종료 시 미저장 버퍼는 로그로 알리며 유실될 수 있습니다. AI 분봉/스냅샷 수집기는 별도로 운영합니다.

단독/부분 검사에는 `--slots 3` 또는 `--slots 3 4`를 사용하세요. 기본은 5개 계좌 전체입니다. `--write`를 생략하면 DB에 저장하지 않는 preview입니다. 계좌 오류로 일부 수신만 유지되는 동안 기존 DB 행은 오래될 수 있으므로 Spring에서는 반드시 received_at을 확인해 최신/지연 상태를 구분해야 합니다. DB 연속 실패 10회는 여전히 전체 종료합니다.

## 테스트
```powershell
..\.venv\Scripts\python.exe -m unittest test_live_quotes_multi test_realtime -v
```
공식 참고:
- 계좌별 한도: https://apiportal.koreainvestment.com/community/10000000-0000-0011-0000-000000000001/post/d0d1a83f-6f8d-4437-9700-6d26702fd989
- 실전/모의 인증 분리: https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/kis_auth.py
- 모의 WebSocket 31000: https://github.com/koreainvestment/open-trading-api/blob/main/legacy/websocket/python/ops_ws_sample.py
