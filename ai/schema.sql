-- Run in your selected database. Existing tables are not altered.
-- All candle times are KST; volume is per-minute cntg_vol, not cumulative.

CREATE TABLE IF NOT EXISTS minute_chart_data(
    stock_code VARCHAR(15) NOT NULL,
    candle_start DATETIME,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    close_price INT,
    volume BIGINT,                      -- Per-minute cntg_vol
    change_amount DOUBLE,               -- prdy_ctrt 전일 대비 등락폭
    change_rate DOUBLE,                 -- prdy_vrss 전일 대비율
    open_price INT,                     -- stck_oprc 시가
    high_price INT,                     -- stck_hgpr 고가
    low_price INT,                      -- stck_lwpr 저가

    PRIMARY KEY (stock_code, candle_start)
);

CREATE TABLE IF NOT EXISTS ai_opinions(
    stock_code VARCHAR(15) NOT NULL PRIMARY KEY,
    invest_opinion VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
