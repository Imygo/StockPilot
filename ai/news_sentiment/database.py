"""Use StockPilot's shared MySQL settings; only news_target_predictions is written."""
import os
import re

def config():
    name=os.getenv('STOCKPILOT_DB_NAME','stockpilot_db')
    user=os.getenv('STOCKPILOT_DB_USER')
    password=os.getenv('STOCKPILOT_DB_PASSWORD')
    if not user or not password:raise ValueError('Set STOCKPILOT_DB_USER/PASSWORD')
    if not re.fullmatch('[A-Za-z0-9_]+',name) or name.lower() in ('mysql','sys','information_schema','performance_schema'):
        raise ValueError('Invalid application database')
    port=int(os.getenv('STOCKPILOT_DB_PORT','3306'))
    if not 1<=port<=65535:raise ValueError('Invalid DB port')
    return dict(host=os.getenv('STOCKPILOT_DB_HOST','127.0.0.1'),port=port,database=name,
                user=user,password=password,charset='utf8mb4',
                connect_timeout=5,read_timeout=30,write_timeout=30)

def connect():
    import pymysql
    conn=pymysql.connect(**config())
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT article_id,stock_code,model_version,quality_json FROM news_target_predictions LIMIT 0')
        return conn
    except BaseException:
        conn.close();raise
