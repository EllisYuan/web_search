"""THROWAWAY real sequential batch: each item is independently persisted.

Runs one SearXNG Google and one DDGS Brave request per item. The third item uses
an explicitly invalid backend to prove one failure does not erase earlier success.
No retry is performed; this is an observation of partial failure behavior.
"""
import argparse
import json
import time
from pathlib import Path
from probe import ROOT, ddgs_search, searxng_search, save, now


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--window', required=True)
    p.add_argument('--searxng', default='http://127.0.0.1:18888')
    p.add_argument('--pause', type=float, default=8)
    args = p.parse_args()
    out = ROOT / 'runs' / args.window
    out.mkdir(parents=True, exist_ok=False)
    corpus = {x['id']: x for x in json.loads((ROOT / 'corpus.json').read_text(encoding='utf-8'))}
    jobs = [('en01', 'ddgs', 'brave'), ('zh01', 'searxng', 'google'), ('mix01', 'ddgs', 'missing-backend')]
    class A: timeout=12; region='us-en'; timelimit=None; searxng_language=None; searxng=args.searxng
    rows = []
    for index, (qid, route, backend) in enumerate(jobs):
        key = f'{args.window}/{index}-{qid}-{route}-{backend}'
        started = time.perf_counter()
        try:
            result = searxng_search(corpus[qid]['query'], backend, A, key) if route == 'searxng' else ddgs_search(corpus[qid]['query'], backend, A, key)
        except Exception as exc:
            result = {'status': 'probe_exception', 'error_type': type(exc).__name__, 'error': str(exc), 'results': [], 'http': [], 'upstream_request_count': 0}
        row = {'batch_index': index, 'query_id': qid, 'query': corpus[qid]['query'], 'route': route, 'backend': backend,
               'started_at': now(), 'injected': False, 'retry_count': 0, **result,
               'batch_latency_ms': round((time.perf_counter() - started) * 1000, 2)}
        save(out / f'{index:02d}-{qid}-{route}-{backend}.json', row)
        rows.append({'batch_index': index, 'query_id': qid, 'route': route, 'backend': backend,
                      'status': row['status'], 'url_count': len(row.get('results', [])),
                      'upstream_request_count': row.get('upstream_request_count', 0),
                      'retry_count': row.get('retry_count', 0), 'batch_latency_ms': row['batch_latency_ms']})
        print(rows[-1], flush=True)
        if index != len(jobs) - 1:
            time.sleep(args.pause)
    prior_success = any(r['status'] in ('success', 'partial_success') for r in rows[:-1])
    final_failed = rows[-1]['status'] not in ('success', 'partial_success')
    save(out / 'batch-index.json', {'created_at': now(), 'injected': False, 'retry_policy': 'none',
         'jobs': rows, 'partial_failure_preserved': prior_success and final_failed and len(rows) == 3,
         'note': 'Third item intentionally uses an unsupported backend. This is a real batch orchestration run, but not a production concurrency/deadline benchmark.'})


if __name__ == '__main__':
    main()
