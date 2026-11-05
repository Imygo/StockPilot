"""Read-only connectivity check; schema creation is a separate DBA step."""
from database import connect
from live_worker import error_summary
import json
if __name__=='__main__':
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM news_target_predictions')
                print(json.dumps(dict(state='ok',stored_predictions=cur.fetchone()[0])))
    except Exception as exc:
        print(json.dumps(dict(state='error',error=error_summary(exc))))
        raise SystemExit(1)
