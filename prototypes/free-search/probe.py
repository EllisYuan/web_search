"""THROWAWAY Search probe. Real observations, no MCP or target-page fetching.

python prototypes/free-search/probe.py --window smoke-1
Requires the adjacent pinned requirements. Raw HTTP bodies stay gitignored.
"""
import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse
from urllib.request import ProxyHandler, build_opener
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def evidence(body, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    lower = body.decode('utf-8', errors='replace').lower()
    # Markers are hints, not proof; normal SERPs may contain these words.
    markers = [s for s in ('anomaly.js', 'challenge-form', 'unusual traffic',
                          'verify you are human', 'captcha', 'too many requests') if s in lower]
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'marker_hints': markers, 'local_body': str(path.relative_to(ROOT)).replace('\\', '/')}


def ddgs_search(query, backend, args, key):
    from ddgs.ddgs import DDGS
    from ddgs.engines import ENGINES
    if backend not in ENGINES['text']:
        return {'status': 'unsupported_backend', 'error': 'Disabled/unknown backend; auto fallback prevented',
                'http': [], 'results': [], 'available_backends': sorted(ENGINES['text'])}
    client = DDGS(timeout=args.timeout)
    engines = client._get_engines('text', backend)
    if len(engines) != 1 or engines[0].name != backend:
        raise RuntimeError('Explicit backend invariant failed')
    engine = engines[0]
    http, upstream = [], []
    original_request = engine.http_client.request
    original_search = engine.search

    def observed_request(*pos, **kw):
        tick = time.perf_counter()
        item = {'method': pos[0], 'endpoint': pos[1], 'started_at': now()}
        try:
            response = original_request(*pos, **kw)
            item.update({'status_code': response.status_code,
                         **evidence(response.content, ROOT / 'raw-private' / key / f'http-{len(http)}.html')})
            return response
        except Exception as exc:
            item.update(error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            item['latency_ms'] = round((time.perf_counter() - tick) * 1000, 2)
            http.append(item)

    def observed_search(*pos, **kw):
        rows = original_search(*pos, **kw)
        upstream.extend(dataclasses.asdict(r) for r in (rows or []))
        return rows

    engine.http_client.request = observed_request
    engine.search = observed_search
    result = {'actual_engine': engine.name, 'provider_label_from_ddgs': engine.provider,
              'http': http, 'upstream_parsed_results': upstream, 'results': []}
    try:
        result['results'] = client.text(query, backend=backend, max_results=10,
                                        region=args.region, timelimit=args.timelimit)
        result['status'] = 'success' if result['results'] else 'empty_unverified'
    except Exception as exc:
        result.update(status='error', error_type=type(exc).__name__, error=str(exc))
        codes = [x.get('status_code') for x in http]
        markers = [m for x in http for m in x.get('marker_hints', [])]
        if 429 in codes:
            result['status'] = 'rate_limited'
        elif 403 in codes:
            result['status'] = 'http_forbidden'
        elif any(m in markers for m in ('anomaly.js', 'challenge-form', 'unusual traffic', 'verify you are human')):
            result['status'] = 'challenge'
        elif any(c and c != 200 for c in codes):
            result['status'] = 'http_error'
        elif 'timeout' in (type(exc).__name__ + str(exc)).lower() or 'timed out' in str(exc).lower():
            result['status'] = 'timeout'
        elif codes and all(c == 200 for c in codes):
            result['status'] = 'empty_or_parse_failure'
    return result


def searxng_search(query, backend, args, key):
    params = {'q': query, 'engines': backend, 'format': 'json'}
    if args.searxng_language:
        params['language'] = args.searxng_language
    if args.timelimit:
        params['time_range'] = {'d': 'day', 'm': 'month', 'y': 'year'}[args.timelimit]
    url = args.searxng.rstrip('/') + '/search?' + urlencode(params)
    # Localhost must not travel through any inherited proxy.
    opener = build_opener(ProxyHandler({}))
    tick = time.perf_counter()
    item = {'endpoint': args.searxng + '/search', 'params': params, 'started_at': now()}
    result = {'http': [item], 'results': []}
    try:
        with opener.open(url, timeout=args.timeout + 5) as response:
            body = response.read()
            item.update(status_code=response.status, **evidence(body, ROOT / 'raw-private' / key / 'response.json'))
        payload = json.loads(body)
        result['raw_response'] = payload
        result['results'] = payload.get('results', [])[:10]
        result['unresponsive_engines'] = payload.get('unresponsive_engines', [])
        result['actual_engines'] = sorted({e for r in result['results'] for e in r.get('engines', [])})
        result['status'] = ('partial_success' if result['unresponsive_engines'] else 'success') if result['results'] else (
            'upstream_failure' if result['unresponsive_engines'] else 'empty_unverified')
    except HTTPError as exc:
        body = exc.read()
        item.update(status_code=exc.code, **evidence(body, ROOT / 'raw-private' / key / 'error.html'))
        result.update(status='http_error', error=str(exc))
    except Exception as exc:
        result.update(status='timeout' if 'timed out' in str(exc).lower() else 'transport_error',
                      error_type=type(exc).__name__, error=str(exc))
    item['latency_ms'] = round((time.perf_counter() - tick) * 1000, 2)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window', required=True)
    parser.add_argument('--routes', default='ddgs:duckduckgo,ddgs:brave,ddgs:google,searxng:duckduckgo,searxng:brave,searxng:google')
    parser.add_argument('--ids', default='zh01,zh02,en01,en02,mix01,mix02')
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--timeout', type=int, default=12)
    parser.add_argument('--pause', type=float, default=2)
    parser.add_argument('--region', default='us-en')
    parser.add_argument('--searxng-language')
    parser.add_argument('--timelimit', choices=['d', 'm', 'y'])
    parser.add_argument('--searxng', default='http://127.0.0.1:18888')
    args = parser.parse_args()
    if not args.window or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.window):
        parser.error('window must be a safe filename')
    routes = [tuple(r.split(':')) for r in args.routes.split(',')]
    if any(len(r) != 2 or r[0] not in ('ddgs', 'searxng') for r in routes):
        parser.error('routes must be explicit ddgs:engine or searxng:engine')
    # This probe does not provision or use paid proxies or inherited DDGS_PROXY.
    if any(os.environ.get(k) for k in ('DDGS_PROXY', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY')):
        parser.error('Proxy configured; use an explicitly documented clean environment')
    corpus_path = ROOT / 'corpus.json'
    corpus = json.loads(corpus_path.read_text(encoding='utf-8'))
    ids = args.ids.split(',')
    queries = corpus if args.ids == 'all' else [q for q in corpus if q['id'] in ids]
    if not queries or (args.ids != 'all' and len(queries) != len(set(ids))):
        parser.error('unknown or empty query IDs')
    out = ROOT / 'runs' / args.window
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'environment.json', {'started_at': now(), 'platform': platform.platform(),
         'python': platform.python_version(), 'packages': {p: importlib.metadata.version(p) for p in ('ddgs', 'primp', 'lxml', 'click')},
         'config': vars(args), 'corpus_sha256': hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
         'egress': 'Windows host for DDGS; Docker Desktop WSL2 NAT for SearXNG; public IP/geolocation not measured',
         'proxy': 'none configured in probe environment', 'verify_tls': True,
         'cache': 'fresh DDGS client per query; no probe result cache; SearXNG engine suspension possible',
         'retry_count': 0, 'concurrency': 1, 'injected': False})
    for i, query in enumerate(queries):
        ordered = routes[i % len(routes):] + routes[:i % len(routes)]
        if args.reverse:
            ordered.reverse()
        for route, backend in ordered:
            key = f'{args.window}/{query["id"]}-{route}-{backend}'
            row = {'query_id': query['id'], 'query': query['query'], 'route': route,
                   'backend': backend, 'started_at': now(), 'injected': False, 'retry_count': 0}
            tick = time.perf_counter()
            row.update((ddgs_search if route == 'ddgs' else searxng_search)(query['query'], backend, args, key))
            row['latency_ms'] = round((time.perf_counter() - tick) * 1000, 2)
            row['finished_at'] = now()
            urls = [r.get('href', r.get('url', '')) for r in row['results']]
            row['url_count'] = len(urls)
            row['hostname_count'] = len({urlparse(u).hostname for u in urls if u})
            row['exact_url_duplicates'] = len(urls) - len(set(urls))
            save(out / f'{query["id"]}-{route}-{backend}.json', row)
            print(f'{query["id"]} {route}:{backend} {row["status"]} urls={len(urls)} ms={row["latency_ms"]}', flush=True)
            time.sleep(args.pause)


if __name__ == '__main__':
    main()
