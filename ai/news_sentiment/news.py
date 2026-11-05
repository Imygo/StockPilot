"""NAVER API HUB -> cleaned, deduplicated Samsung news CSV. Secrets: env only."""
import argparse
import csv
import hashlib
import html
import json
import os
import re
import time
import unicodedata
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

FIELDS = ['article_id', 'stock_code', 'title', 'description', 'url', 'published_at', 'text_hash', 'label']

def clean(value):
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(re.sub(r'<[^>]*>', '', value or ''))).split())

def canonical_url(value):
    u = urlsplit(value)
    if u.scheme not in ('http', 'https') or not u.netloc or u.username or u.password:
        raise ValueError('Invalid article URL')
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path, urlencode(sorted(query)), ''))

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def normalize(item):
    title, description = clean(item.get('title')), clean(item.get('description'))
    if not title or '삼성전자' not in title + description:
        return None
    url = canonical_url(item.get('originallink') or item.get('link', ''))
    dt = parsedate_to_datetime(item['pubDate'])
    if dt.tzinfo is None:
        raise ValueError('Publication timezone missing')
    return dict(zip(FIELDS, [digest(url), '005930', title, description, url,
                dt.astimezone(timezone.utc).isoformat(), digest(title + '\n' + description), '']))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward API secrets to redirected hosts.

def fetch(start, display, query_text='삼성전자', before_request=None):
    keys = [os.environ.get(k) for k in ('NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET')]
    if not all(keys):
        raise ValueError('Set NAVER_CLIENT_ID and NAVER_CLIENT_SECRET in the process environment')
    query = urlencode(dict(query=query_text, display=display, start=start, sort='date', format='json'))
    request = Request('https://naverapihub.apigw.ntruss.com/search/v1/news?' + query,
                      headers={'X-NCP-APIGW-API-KEY-ID': keys[0], 'X-NCP-APIGW-API-KEY': keys[1]})
    for attempt in range(3):
        if before_request: before_request()
        try:
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                payload = json.load(response)
            if not isinstance(payload.get('items'), list):
                raise ValueError('Unexpected API response; response body suppressed')
            return payload['items']
        except HTTPError as exc:
            if (exc.code == 429 or exc.code >= 500) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f'NAVER HTTP {exc.code}; response body suppressed') from None
        except URLError:
            raise RuntimeError('NAVER connection failed; request details suppressed') from None

def merge(rows, items):
    ids, hashes = {r['article_id'] for r in rows}, {r['text_hash'] for r in rows}
    rejected = 0
    for item in items:
        try:
            row = normalize(item)
        except (ValueError, KeyError, TypeError, OverflowError):
            rejected += 1
            continue
        if row and row['article_id'] not in ids and row['text_hash'] not in hashes:
            rows.append(row)
            ids.add(row['article_id'])
            hashes.add(row['text_hash'])
    return rows, rejected

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='data/news.csv')
    p.add_argument('--pages', type=int, default=1)
    a = p.parse_args()
    if not 1 <= a.pages <= 10:
        p.error('pages must be 1..10 (100 results per page)')
    rows = read_csv(a.output) if Path(a.output).exists() else []
    before, rejected = len(rows), 0
    for page in range(a.pages):
        items = fetch(page * 100 + 1, 100)
        rows, bad = merge(rows, items)
        rejected += bad
        if len(items) < 100:
            break
    write_csv(a.output, rows)
    print(json.dumps({'added': len(rows)-before, 'total': len(rows), 'rejected': rejected}))

if __name__ == '__main__':
    main()
