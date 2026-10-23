# 5분 수집 → 집계 1행

기본 실행이 5분 수집으로 변경되었습니다.

```powershell
cd C:\Users\moonj\Desktop\CapstoneDesign_2026\backend\data_collector
python data_collector.py --codes 005930
# 명시적으로 모드 지정
python data_collector.py collect5 --codes 005930
```

한 종목을 모의투자 웹소켓으로 수집합니다. 인증/연결 후 구독 요청부터 300초간 수신합니다.
모든 수신 필드는 data/tick/ticks_시간.csv에 저장하고, 종료 후 이번 CSV만 집계하여
minute_chart_data에 한 행을 삽입/갱신하고 종료합니다.
DB 비밀번호가 환경변수 MYSQL_PASSWORD에 없으면 수집 종료 후 숨김 입력합니다.
실시간 체결이 없으면 행을 생성하지 않습니다. 연결/파싱 오류 또는 Ctrl+C에는 CSV를 남기고 DB 저장을 하지 않습니다.

이는 **실행 시점부터 5분의 집계봉**입니다. 09:02:30에 시작하면 약 09:07:30까지의 체결이 하나로 집계됩니다.
09:00~09:05 같은 거래소 기준 정규 5분봉이 아닙니다.
candle_start에는 한국 시간의 수집 시작 시각(초까지)을 기록합니다.
open_price는 첫 체결, high/low_price는 전체 기간의 최대/최소, close_price는 마지막 체결 가격입니다.
volume은 기존 정의대로 마지막 ACML_VOL(당일 누적량)이며 5분간 거래량이 아닙니다.
change_amount/change_rate도 마지막 체결의 전일 대비 값입니다. updated_at은 DB에서 생성합니다.

테이블 구조는 변경하지 않습니다. 이 모드의 결과는 기존 1분봉과 의미가 다르며,
현재 테이블에 봉 주기 컬럼이 없으므로 섞어서 조회하면 안 됩니다.
같은 기본키가 이미 있으면 이번 집계값으로 갱신됩니다.
stock/daily_chart_data는 이 모드에서 변경하지 않습니다.

기존 stream(연속 1분봉), history, snapshot 등 명시적 모드는 유지됩니다.
db/import_ticks.py의 기본 60초 수집 기능도 그대로이며, 이번 변경은 data_collector.py의 기본 모드에 적용됩니다.
