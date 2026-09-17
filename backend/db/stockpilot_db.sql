-- 1. 스키마 생성
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
    change_rate DOUBLE,                 -- prdy_vrss 등락폭
    volume BIGINT,                      -- acml_vol 거래량
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );

-- 차트 데이터를 담는 테이블
CREATE TABLE IF NOT EXISTS chart_data(
                                         stock_code VARCHAR(15) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    close_price INT,
    trade_date DATE,
    volume BIGINT,                      -- acml_vol 거래량
    change_rate DOUBLE,                 -- prdy_vrss 등락폭
    open_price INT,                     -- stck_oprc 시가
    high_price INT,                     -- stck_hgpr 고가
    low_price INT,                      -- stck_lwpr 저가

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
    buy INT DEFAULT 0,
    neutral INT DEFAULT 0,
    sell INT DEFAULT 0
    );

-- 사용자의 의견을 담는 테이블
-- 기본적으로 '중립'값을 가지도록 설정합니다.
CREATE TABLE IF NOT EXISTS user_opinions(
    stock_code VARCHAR(15) NOT NULL,
    user_id VARCHAR(50) NOT NULL,       -- users 테이블의 크기(50)와 동일하게 설정
    opinion ENUM('buy', 'neutral', 'sell') NOT NULL DEFAULT 'neutral',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (stock_code, user_id)
    );