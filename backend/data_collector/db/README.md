# 일봉 CSV → MySQL

저장소 루트에서 실행합니다.

```powershell
# 기본: NEW/data/daily/daily_*.csv 전체 저장
python NEW/db/import_daily.py

# DB 접속 없이 데이터 검증
python NEW/db/import_daily.py --dry-run

# 파일 하나만 저장
python NEW/db/import_daily.py --file NEW/data/daily/daily_20261015_112930_470117.csv
```

기본 폴더는 스크립트 위치를 기준으로 찾으므로 실행 위치에 의존하지 않습니다. `--directory`로 다른 입력 폴더를 지정할 수도 있습니다. 파일명 마지막 6자리(예: `470117`)는 생성 시각의 마이크로초입니다.

DB 연결은 기존 수집기와 동일합니다. `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=3306`, `MYSQL_USER=root`, `MYSQL_DATABASE=stockpilot_db`가 기본값입니다. `MYSQL_PASSWORD` 환경변수가 없으면 비밀번호를 숨김 입력합니다. 의존성은 `python -m pip install -r NEW/requirements.txt`로 설치합니다. KIS 인증이나 네트워크 시세 조회는 하지 않습니다.

CSV의 `stock_code, trade_date, close_price, volume, change_amount, change_rate, open_price, high_price, low_price`를 같은 이름의 테이블 컬럼에 저장합니다. `stock_code`는 문자열로 읽어 `005930`을 보존합니다. `updated_at`은 새 행에서 DB 기본값, 기존 행 갱신 시 `CURRENT_TIMESTAMP`를 사용합니다. 빈 시세 값은 NULL로 저장합니다.

SQL 주석과 달리 CSV의 `change_amount`는 등락금액(prdy_vrss), `change_rate`는 등락률(prdy_ctrt)입니다. 값을 서로 바꾸지 않습니다. `low_price`는 이미 수집기에서 stck_lwpr로 매핑된 값입니다.

모든 파일을 검증한 후 하나의 트랜잭션으로 저장합니다(InnoDB 기준). 잘못된 행이 있으면 파일명과 행 번호를 출력하고 저장을 시작하지 않습니다. DB 처리 중 실패하면 전체 트랜잭션을 롤백합니다. 기본키 `(stock_code, trade_date)`가 같으면 값을 갱신합니다. 여러 CSV가 겹치면 파일명 정렬상 나중 파일의 값이 우선하며 같은 파일 안에서는 마지막 행이 우선합니다. 같은 파일을 다시 실행해도 중복 행이 생기지 않습니다. 출력 건수는 삽입/갱신을 합친 고유 키 개수입니다.

기존 `daily_chart_data` 테이블이 필요합니다. 테이블 생성/변경, 다른 테이블 변경, 원본 CSV 수정은 하지 않습니다. 대량 파일은 검증·중복 제거를 위해 메모리에 올립니다.

오프라인 테스트: `python -m unittest discover -s NEW/db -p "test_*.py" -v`
