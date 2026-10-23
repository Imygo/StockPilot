# 60초 수집 후 분봉 저장

프로젝트 폴더에서 실행:

```powershell
cd C:\Users\moonj\Desktop\CapstoneDesign_2026\backend\data_collector
python db/import_ticks.py
```

기본 삼성전자(005930)를 모의투자 웹소켓으로 수집합니다.
인증/연결 후 구독 요청을 보낸 시점부터 60초간 받습니다. 인증과 연결에 걸리는 시간은 60초에 포함되지 않습니다.
전체 필드는 data/tick/ticks_시간.csv에 기록하고 종료 후 이번 파일만 분봉으로 집계해 minute_chart_data에 저장합니다.
MySQL 비밀번호를 환경변수로 설정하지 않았다면 60초 수집 후 숨김 입력을 받습니다.
입력이 끝나고 저장 완료가 출력되면 프로그램이 종료됩니다.
stock/daily_chart_data는 수정하지 않습니다.

다른 종목:
```powershell
python db/import_ticks.py --code 000660
```

기존 CSV 기능:
```powershell
python db/import_ticks.py --from-csv
python db/import_ticks.py --file data/tick/파일명.csv
python db/import_ticks.py --dry-run
```
--dry-run은 기존 CSV 검증만 수행하며 API/DB 접속이 없습니다.
--directory 지정도 기존 CSV 모드입니다.

**60초 수집은 완성된 분봉 한 개와 다릅니다.** 예를 들어 15:18:30~15:19:30이면 분봉 두 개가 생기며 각각 부분 데이터입니다.
수신한 체결만으로 분별 첫 가격/최대/최소/마지막 가격을 저장합니다.
volume은 ACML_VOL 당일 누적량, change_amount는 PRDY_VRSS, change_rate는 PRDY_CTRT입니다.
SQL 주석의 PRDY_CTRT/PRDY_VRSS 설명은 뒤바뀌어 있습니다.
종목코드는 문자열, candle_start는 거래소 날짜/시간을 분 단위로 절삭, updated_at은 DB 현재 시각입니다.

기본키가 같은 기존 DB 행은 이번 집계값으로 갱신하므로 더 완전한 기존 분봉을 부분 데이터로 덮어쓸 수 있습니다.
수집 완료 파일들로 전체 기간을 다시 집계하려면 --from-csv를 사용하세요.
중간 연결/파싱 오류나 Ctrl+C에는 DB에 자동 저장하지 않고 이미 기록한 CSV를 남깁니다.
남은 CSV를 --file로 수동 저장할 수 있습니다. 장외 등 체결이 없으면 DB에 쓰지 않습니다.
자동 재연결은 하지 않으며 연결 오류를 표시하고 종료합니다.

기존 data_collector.py 및 db/import_daily.py를 재사용합니다.
인증 파일은 기존 기본 경로/환경변수 KIS_AUTH_FILE 또는 --auth-file을 사용합니다.
DB 기본값은 127.0.0.1:3306 / root / stockpilot_db이며 MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
MYSQL_DATABASE, MYSQL_PASSWORD로 변경할 수 있습니다.
의존성 설치: python -m pip install -r requirements.txt

테스트: python -B -m unittest discover -s db -p "test_import_ticks.py" -v
