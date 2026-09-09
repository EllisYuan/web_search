"""THROWAWAY offline batch replay + explicit fault injection. Never upstream stats."""
import json
from pathlib import Path
from probe import ROOT, now, save


def batch(items, max_retries=1):
    if not 1 <= len(items) <= 4:
        raise ValueError('Prototype budget: 1..4 query items')
    grouped = []
    for item in items:
        attempts = []
        for index in range(max_retries + 1):
            outcome = item['outcomes'][min(index, len(item['outcomes']) - 1)]
            attempts.append({'attempt': index + 1, 'status': outcome['status'],
                             'reason': outcome.get('reason'), 'injected': True})
            if outcome['status'] != 'timeout':
                break
        grouped.append({'query_id': item['query_id'], 'status': outcome['status'],
                        'results': outcome.get('results', []), 'reason': outcome.get('reason'),
                        'retry_count': len(attempts) - 1, 'retry_exhausted': outcome['status'] == 'timeout',
                        'attempts': attempts})
    return grouped


def main():
    fixture = ROOT / 'runs/smoke-1-ddgs/zh01-ddgs-brave.json'
    actual = json.loads(fixture.read_text(encoding='utf-8'))
    success = {'status': 'success', 'results': actual['results'][:3]}
    empty = {'status': 'empty', 'results': [], 'reason': 'Injected confirmed empty; not observed upstream empty'}
    timeout = {'status': 'timeout', 'reason': 'Injected request deadline exceeded'}
    forbidden = {'status': 'http_forbidden', 'reason': 'Injected HTTP 403; no retry'}
    cases = {
        'success_and_empty': [{'query_id': 'success', 'outcomes': [success]}, {'query_id': 'empty', 'outcomes': [empty]}],
        'single_timeout_preserves_success': [{'query_id': 'success', 'outcomes': [success]}, {'query_id': 'timeout', 'outcomes': [timeout]}],
        'all_failed': [{'query_id': 'timeout', 'outcomes': [timeout]}, {'query_id': 'forbidden', 'outcomes': [forbidden]}],
        'retry_recovers': [{'query_id': 'recovers', 'outcomes': [timeout, success]}],
        'retry_exhausted': [{'query_id': 'exhausted', 'outcomes': [timeout]}],
    }
    result = {'created_at': now(), 'mode': 'offline_replay_and_fault_injection', 'injected': True,
              'fixture': str(fixture.relative_to(ROOT)).replace('\\', '/'),
              'note': 'No real timeout/empty/403 claim; sequential grouping only, no production scheduler or wall-clock deadline tested',
              'experimental_budget': {'max_batch': 4, 'max_retries': 1, 'retry_only': ['timeout']},
              'cases': {name: batch(items) for name, items in cases.items()}}
    save(ROOT / 'batch-observations.json', result)
    for name, groups in result['cases'].items():
        print(name, [(g['query_id'], g['status'], g['retry_count'], len(g['results'])) for g in groups])


if __name__ == '__main__':
    main()
