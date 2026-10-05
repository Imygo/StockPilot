-- SQL파일을 수정한 후에는 이미 생성된 DB테이블을 변경해야 한다.

--1. 스키마 생성
CREATE SCHEMA IF NOT EXISTS stockpilot_db
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

-- 2. 생성된 스키마를 사용하도록 설정
USE stockpilot_db;

-- 3. 테이블 정의
-- 사용자 정보를 담는 테이블
CREATE TABLE IF NOT EXISTS users(
    user_id VARCHAR(50) NOT NULL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

-- 주식 정보를 담는 테이블
CREATE TABLE IF NOT EXISTS stock(
    stock_code VARCHAR(15) NOT NULL PRIMARY KEY,
    stock_name VARCHAR(100) NOT NULL,
    market VARCHAR(10),
    current_price INT,
    marketCap BIGINT,                   -- hts_avls 시가총액
    change_amount DOUBLE,               -- prdy_ctrt 전일 대비 등락폭
    change_rate DOUBLE,                 -- prdy_vrss 전일 대비율
    volume BIGINT,                      -- acml_vol 거래량
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );

-- 차트 데이터를 담는 테이블
-- 웹소켓을 통해 실시간 데이터를 받으며, 분봉 캔들차트를 그리기 위해 사용합니다.
CREATE TABLE IF NOT EXISTS minute_chart_data(
    stock_code VARCHAR(15) NOT NULL,
    candle_start DATETIME,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    close_price INT,
    volume BIGINT,                      -- acml_vol 거래량
    change_amount DOUBLE,               -- prdy_ctrt 전일 대비 등락폭
    change_rate DOUBLE,                 -- prdy_vrss 전일 대비율
    open_price INT,                     -- stck_oprc 시가
    high_price INT,                     -- stck_hgpr 고가
    low_price INT,                      -- stck_lwpr 저가

    PRIMARY KEY (stock_code, candle_start)
);

-- 차트 데이터를 담는 테이블
-- API를 이용하여 정해진 기간만큼의 데이터를 받으며, 일봉, 주봉, 월봉 캔들차트를 그리기 위해 사용합니다.
CREATE TABLE IF NOT EXISTS daily_chart_data(
    stock_code VARCHAR(15) NOT NULL,
    trade_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    close_price INT,
    volume BIGINT,                      -- acml_vol 거래량
    change_amount DOUBLE,               -- prdy_ctrt 전일 대비 등락폭
    change_rate DOUBLE,                 -- prdy_vrss 전일 대비율
    open_price INT,                     -- stck_oprc 시가
    high_price INT,                     -- stck_hgpr 고가
    low_price INT,                      -- sck_lwpr 저가

    PRIMARY KEY (stock_code, trade_date)
);

-- AI 의견을 담는 테이블
CREATE TABLE IF NOT EXISTS ai_opinions(
    stock_code VARCHAR(15) NOT NULL PRIMARY KEY,
    invest_opinion VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );

-- 커뮤니티 의견을 담는 테이블
CREATE TABLE IF NOT EXISTS community_opinions(
    stock_code VARCHAR(15) NOT NULL PRIMARY KEY,
    buy INT NOT NULL DEFAULT 0,
    neutral INT NOT NULL DEFAULT 0,
    sell INT NOT NULL DEFAULT 0
    );

-- 사용자의 의견을 담는 테이블
CREATE TABLE IF NOT EXISTS user_opinions(
    stock_code VARCHAR(15) NOT NULL,
    vote_yn ENUM('Y','N') NOT NULL DEFAULT 'N',
    user_id VARCHAR(50) NOT NULL,       -- users 테이블의 크기(50)와 동일하게 설정
    opinion ENUM('buy', 'neutral', 'sell'),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (stock_code, user_id)
);