# StockPilot 수집기 실행 안내

전체 설치와 데이터 흐름은 [AI README](../README.md)를 먼저 확인하세요.

- [200종목 모의 WebSocket](MULTI_WEBSOCKET.md): 5개 독립 모의 앱키, 순차 연결, 부분 실패·재시도, 현재가 DB 저장
- [REST 분봉과 예측 스냅샷](SNAPSHOT_RUN.md): 수집 완료 데이터를 고정해 AI 입력으로 사용
- [AI 예측기](LIVE_PREDICTION.md): 5분 후 상승·하락 예측 및 저장
- [REST 일봉](DAILY_COLLECTION.md): 과거 1년 일봉 수집
- [실시간 예측 평가](LIVE_EVALUATION.md): 저장된 예측과 실제 결과 비교
- [기존 실전 선택 종목 수신](REALTIME_RUN.md): live_quotes.py 사용 시 참고

실행 위치는 이 폴더입니다. 가상환경은 ai/.venv에 생성합니다. `.env.example`, `.env.paper.example`만 공유하고 실제 `.env`, `.env.paper`는 서버에서 작성하세요. 분봉·일봉·모의 현재가는 서로 다른 테이블에 저장됩니다. 현재 AI 입력은 REST 분봉이며 웹소켓 최신값을 입력하지 않습니다.

## 홈 화면의 200종목 등록·시세 갱신

뉴스와 동일한 `ai/data/top200-20261012.json`을 사용합니다. 현재 시점의 순위를 자동 재선정하지 않습니다. 종목 목록을 변경할 경우 뉴스·차트·모델 대상도 함께 검토해야 합니다.

`ai/live_collector`에서 실행합니다. 기존 `ai/.venv`와 `.env`의 `STOCKPILOT_DB_*`, `KIS_APP_KEY`, `KIS_APP_SECRET`을 사용합니다. 키와 비밀번호는 공유하지 않습니다.

```powershell
# 목록 확인: API·DB 접근 없음
..\.venv\Scripts\python.exe register_stocks.py
..\.venv\Scripts\python.exe stock_quotes.py

# 없는 종목의 기본정보만 등록. 기존 종목·시세 유지
..\.venv\Scripts\python.exe register_stocks.py --write

# 모의투자용 키: 200종목 시세 한 번 갱신
..\.venv\Scripts\python.exe stock_quotes.py --environment paper --write

# 같은 수집기를 5분마다 반복 실행 (위 일회 실행이 끝난 뒤 선택)
..\.venv\Scripts\python.exe stock_quotes.py --environment paper --write --loop --interval 300
```

`stock_quotes.py` 기본 서버는 모의투자입니다. 실전용 키를 사용하는 담당자만 `--environment live`를 명시합니다. 서버를 자동 전환하지 않으며 주문 기능은 없습니다. 다른 분봉·일봉 수집기의 서버 설정은 변경하지 않습니다.

현재가·시가총액·등락금액·등락률·거래량을 `stock`에 갱신하고 DB 값을 대조한 후 확정합니다. `marketCap` 단위는 기존 화면과 동일한 억원입니다. 종목명·시장·차트·뉴스 테이블 및 스키마는 변경하지 않습니다. 기본정보 누락 시 먼저 등록해야 합니다.

인증 토큰은 실행 중 메모리에서 재사용합니다. 인증 실패 시 즉시 종료하고, 시세 요청이 3종목 연속 실패해도 중단합니다. 실패한 회차는 자동 반복하지 않습니다. 재시작 시 토큰 발급 제한을 피하도록 60초 이상 기다리고 동일 키로 다른 프로그램을 동시에 재시작하지 마세요. `.env`의 키 종류와 선택한 서버가 일치해야 합니다.

장외에는 최근 조회 가능한 값이 저장될 수 있습니다. `stock.updated_at`은 DB 갱신 시각이며 거래소 체결 시각이 아닙니다. 별도의 실시간 체결 수집기를 대체하지 않습니다. 종료는 Ctrl+C입니다.

```powershell
..\.venv\Scripts\python.exe -m unittest test_register_stocks test_stock_quotes
```
