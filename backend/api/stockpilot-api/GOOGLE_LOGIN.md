# Google 로그인 실행 안내

현재 구조는 Spring Security OIDC 로그인과 기존 HttpSession(userId) 기반 API를 연결합니다.
Google 계정은 google_sub로 식별하며, 화면 이름(displayName)과 내부 userId를 분리합니다.
Google 이름/이메일이 기존 LOCAL 사용자와 같아도 계정을 자동으로 합치지 않습니다.

## 외부 설정

1. Google Cloud/Google Auth Platform에서 프로젝트와 동의 화면을 구성합니다.
2. OAuth 클라이언트를 웹 애플리케이션 유형으로 생성합니다.
3. 승인된 리디렉션 URI에 아래 주소를 정확히 등록합니다.

   http://localhost:8080/login/oauth2/code/google

4. 동의 화면이 테스트 상태라면 사용할 계정을 테스트 사용자로 등록합니다.
   조직 내부 전용 앱은 허용된 조직 계정만 사용할 수 있습니다.
5. IntelliJ의 Spring 실행 구성에 GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET 환경변수를 설정합니다.
   비밀키를 소스나 VITE_ 변수에 넣지 마세요. 여기에는 실제 인증정보를 기록하지 않습니다.
6. 기존 STOCKPILOT_DB_URL, STOCKPILOT_DB_USER, STOCKPILOT_DB_PASSWORD도 유지합니다.

Google 설정 참고: https://developers.google.com/identity/protocols/oauth2/web-server
계정 식별자 참고: https://developers.google.com/identity/openid-connect/reference

## DB 준비

이번 코드 작업은 실제 DB를 변경하지 않았습니다. Spring의 ddl-auto=none 설정도 유지합니다.
대상 DB를 선택하고 다음을 먼저 확인합니다.

```sql
SHOW CREATE TABLE users;
```

필요한 컬럼은 auth_provider, google_sub, display_name이며 google_sub에는 고유 인덱스가 필요합니다.
google_sub는 ascii_bin으로 대소문자를 구분합니다.

- 기존 테이블에 세 컬럼이 모두 없다면 backend/db/migrations/20261125_google_login.sql을 1회 실행합니다.
- 이미 컬럼과 인덱스를 추가했다면 마이그레이션을 다시 실행하지 않습니다.
- 일부만 추가했다면 SHOW CREATE TABLE 결과에 맞춰 빠진 부분만 적용해야 합니다.
- 새 DB는 backend/db/stockpilot_db.sql의 CREATE TABLE 정의에 컬럼이 포함돼 있습니다.
- CREATE TABLE IF NOT EXISTS는 기존 테이블을 갱신하지 않습니다.

## 로컬 실행

- 백엔드: localhost:8080, 프론트: localhost:5173
- Vite 설정 변경을 반영하려면 프론트 개발 서버도 재시작합니다.
- 기본 구성에서는 VITE_API_BASE_URL과 VITE_AUTH_BASE_URL을 설정하지 않습니다.
  Vite가 /api, /oauth2, /login/oauth2를 백엔드로 프록시합니다.
- localhost와 127.0.0.1을 섞어 사용하지 않습니다.
- 로컬 HTTP는 SESSION_COOKIE_SECURE=false(기본값)입니다.
- 새 OAuth2 의존성을 받도록 IntelliJ에서 Gradle 프로젝트를 다시 불러옵니다.

브라우저에서 /register의 Google로 로그인 버튼을 누르면 Google로 이동합니다.
인증 성공 후 백엔드가 사용자를 저장하고 프론트 /로 이동합니다.
RequireSession이 /api/users/me를 호출해 서버 세션과 표시 이름을 동기화합니다.
실패 시 /register?error=google로 이동합니다. 인증 이후 DB 오류라면 서버 로그와 스키마를 확인하세요.

## 세션과 CSRF

- userId: 기존 의견/투표 데이터와 연결되는 내부 ID
- displayName: Google에서 받은 화면 표시 이름
- authProvider: GOOGLE 또는 LOCAL
- 인증의 근거는 서버 세션이며 sessionStorage는 표시용 캐시입니다.
- 새로고침/새 탭에서도 쿠키가 유효하면 /api/users/me로 복원합니다.
- 요청 없이 30분이 지나면 세션이 만료됩니다. 서버 재시작 후 영속성은 보장하지 않습니다.
- Axios가 등록/투표/로그아웃 전에 /api/users/csrf를 조회해 토큰을 헤더에 보냅니다.
- userAPI.logout()은 POST /api/users/logout 후 프론트 캐시를 지웁니다.
  로그아웃 버튼을 연결할 경우 성공 후 /register로 이동하면 됩니다.
- LOCAL 방식은 이름만으로 입장하는 기존 데모 방식입니다. Google 계정에는 LOCAL 입장을 차단합니다.

## HTTPS 배포

환경변수 FRONTEND_URL, GOOGLE_REDIRECT_URI를 실제 HTTPS 주소로 설정하고 Google 콘솔에도 등록합니다.
SESSION_COOKIE_SECURE=true를 설정합니다.
운영 프록시도 /api, /oauth2, /login/oauth2를 백엔드에 전달해야 합니다.
기본 구성은 같은 사이트/프록시를 전제로 하며 별도 도메인의 프론트/API용 CORS 설정은 포함하지 않습니다.

## 검증

실제 Google 토큰이나 MySQL 연결 없이 수행하는 테스트:

```powershell
.\gradlew.bat test --tests '*Google*Test' --console=plain
```

테스트 범위: 로그인 시작 리디렉션, 잘못된 callback 거부, 익명 API 401,
CSRF 없는 POST 거부, CSRF 포함 LOCAL 로그인/세션 교체, Google 세션 조회/로그아웃,
로그인 성공 시 내부 ID와 표시 이름 분리, DB 저장 실패 시 세션 제거,
Google 계정의 LOCAL 우회 차단, 동일 sub의 사용자 ID 유지.

실제 계정으로 별도 확인할 항목:
1. 첫 Google 로그인 후 users에 GOOGLE 사용자 1개 생성
2. /api/users/me에서 내부 ID, 표시 이름, GOOGLE 확인
3. 새로고침 후 이름 유지, 투표 요청 성공
4. 로그아웃 후 /api/users/me가 401
5. 같은 Google 계정으로 재로그인 시 기존 user_id 유지

실제 Google 인증/DB 마이그레이션은 자동 테스트로 검증한 것이 아닙니다.
