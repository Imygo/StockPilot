USE stockpilot_db;

INSERT INTO community_opinions (
    stock_code, buy, neutral, sell
)
SELECT
    s.stock_code,
    0,
    0,
    0
FROM stock s
WHERE s.market IN ('KOSPI', 'KOSDAQ')
  AND NOT EXISTS (
    SELECT 1
    FROM community_opinions c
    WHERE c.stock_code = s.stock_code
);