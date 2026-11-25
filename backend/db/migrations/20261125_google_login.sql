-- 기존 users 테이블에 Google 컬럼이 없는 경우에만 1회 실행합니다.
-- 이미 컬럼/인덱스를 추가했다면 다시 실행하지 마세요.
-- 먼저 SHOW CREATE TABLE users; 로 확인하고 올바른 DB를 선택하세요.
ALTER TABLE users
    ADD COLUMN auth_provider VARCHAR(10) NOT NULL DEFAULT 'LOCAL',
    ADD COLUMN google_sub VARCHAR(255)
        CHARACTER SET ascii COLLATE ascii_bin NULL,
    ADD COLUMN display_name VARCHAR(255) NULL,
    ADD UNIQUE KEY uq_users_google_sub (google_sub);
