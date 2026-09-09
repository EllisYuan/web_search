"""Separate target-page check; never called by Search. Six explicit public URLs."""
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from lxml import html
from probe import ROOT, now, save, evidence


PAGES = [
    ('zh01', 'https://docs.python.org/zh-cn/3/library/asyncio-task.html', ['TaskGroup', 'ExceptionGroup']),
    ('zh02', 'https://www.ysnp.gov.tw/StaticPage/Terrain', ['3,952', '玉山主峰']),
    ('en01', 'https://www.postgresql.org/docs/current/indexes-multicolumn.html', ['multicolumn', 'B-tree']),
    ('en02', 'https://motherduck.com/learn/duckdb-vs-sqlite-databases/', ['DuckDB', 'SQLite', 'analytical']),
    ('mix01', 'https://docs.searxng.org/dev/search_api.html', ['formats', 'json']),
    ('mix02', 'https://docs.docker.com/desktop/features/wsl/', ['WSL', 'backend']),
]


def main():
    out = ROOT / 'readability-observations.json'
    if out.exists():
        raise SystemExit('Refusing to overwrite real observations')
    rows = []
    for query_id, url, terms in PAGES:
        row = {'query_id': query_id, 'url': url, 'started_at': now(), 'injected': False,
               'selection': 'One URL among observed top-3 results for this query; not a random sample'}
        tick = time.perf_counter()
        try:
            with urlopen(Request(url, headers={'User-Agent': 'FreeSearchPrototype/0.1 (readability check)'}), timeout=15) as response:
                body = response.read(2_000_001)
                row.update(status_code=response.status, final_url=response.url,
                           **evidence(body, ROOT / 'raw-private' / 'readability' / f'{query_id}.html'))
            tree = html.fromstring(body)
            for node in tree.xpath('//script|//style|//nav|//footer|//header'):
                node.drop_tree()
            nodes = tree.xpath('//main|//article|//*[@role="main"]') or [tree]
            text = ' '.join(nodes[0].text_content().split())
            row.update(extracted_chars=len(text), matched_terms=[s for s in terms if s.lower() in text.lower()],
                       expected_terms=terms, excerpt=text[:200], status='fetched')
            (ROOT / 'raw-private' / 'readability' / f'{query_id}.txt').write_text(text, encoding='utf-8')
        except HTTPError as exc:
            row.update(status='http_error', status_code=exc.code, error=str(exc))
        except Exception as exc:
            row.update(status='fetch_error', error_type=type(exc).__name__, error=str(exc))
        row['latency_ms'] = round((time.perf_counter() - tick) * 1000, 2)
        rows.append(row)
        save(out, {'note': 'Separate HTTP/body extraction check, not full Web Read implementation or whole-site readability', 'observations': rows})
        print(query_id, row['status'], row.get('matched_terms'), flush=True)
        time.sleep(1)


if __name__ == '__main__':
    main()
