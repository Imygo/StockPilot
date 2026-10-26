# StockPilot 수집기 실행 안내

전체 설치와 데이터 흐름은 [AI README](../README.md)를 먼저 확인하세요.

- [200종목 모의 WebSocket](MULTI_WEBSOCKET.md): 5개 독립 모의 앱키, 순차 연결, 부분 실패·재시도, 현재가 DB 저장
- [REST 분봉과 예측 스냅샷](SNAPSHOT_RUN.md): 수집 완료 데이터를 고정해 AI 입력으로 사용
- [AI 예측기](LIVE_PREDICTION.md): 5분 후 상승·하락 예측 및 저장
- [REST 일봉](DAILY_COLLECTION.md): 과거 1년 일봉 수집
- [실시간 예측 평가](LIVE_EVALUATION.md): 저장된 예측과 실제 결과 비교
- [기존 실전 선택 종목 수신](REALTIME_RUN.md): live_quotes.py 사용 시 참고

실행 위치는 이 폴더입니다. 가상환경은 ai/.venv에 생성합니다. `.env.example`, `.env.paper.example`만 공유하고 실제 `.env`, `.env.paper`는 서버에서 작성하세요. 분봉·일봉·모의 현재가는 서로 다른 테이블에 저장됩니다. 현재 AI 입력은 REST 분봉이며 웹소켓 최신값을 입력하지 않습니다.
