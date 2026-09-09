"""Recompute smoke statistics from saved observations and explicit reviewed judgments."""
import json
import statistics
from collections import Counter, defaultdict
from urllib.parse import urlparse, unquote
from probe import ROOT, save


def canonical(url):
    p = urlparse(unquote(url))
    return (p.hostname, p.path.rstrip('/'), p.query)


def main():
    annotations = json.loads((ROOT / 'quality-annotations.json').read_text(encoding='utf-8'))
    labels = {(v['query_id'], v['url']): v for v in annotations['judgments']}
    corpus = {v['id']: v for v in json.loads((ROOT / 'corpus.json').read_text(encoding='utf-8'))}
    groups = defaultdict(list)
    details = []
    for path in sorted((ROOT / 'runs').glob('smoke*/*.json')):
        if path.name == 'environment.json':
            continue
        row = json.loads(path.read_text(encoding='utf-8'))
        if row['injected']:
            continue
        reviewed = [labels[(row['query_id'], v.get('href', v.get('url')))] for v in row['results'][:3]]
        refs = corpus[row['query_id']]['known_relevant_urls']
        urls = [v.get('href', v.get('url')) for v in row['results']]
        relevant = [v for v in reviewed if v['relevance'] == 'relevant']
        sources = {v['source_group'] for v in relevant if v['source_group']}
        detail = {'observation': str(path.relative_to(ROOT)).replace('\\', '/'),
                  'query_id': row['query_id'], 'route': row['route'], 'backend': row['backend'],
                  'window': path.parent.name, 'status': row['status'], 'latency_ms': row['latency_ms'],
                  'url_count': len(urls), 'exact_url_duplicates': row['exact_url_duplicates'],
                  'reviewed_top3': len(reviewed), 'relevant_top3': len(relevant),
                  'source_groups_top3_relevant': sorted(sources),
                  'hostname_count_top3': len({urlparse(v['url']).hostname for v in reviewed}),
                  'site_groups_top3': sorted({v['site_group'] for v in reviewed}),
                  'languages_top3': dict(Counter(v['language'] for v in reviewed)),
                  'known_url_hit_top10': any(canonical(u) == canonical(ref) for u in urls for ref in refs),
                  'known_site_hit_top10': any(urlparse(u).hostname == urlparse(ref).hostname for u in urls for ref in refs)}
        details.append(detail)
        groups[(row['route'], row['backend'])].append(detail)
    summary = []
    for (route, backend), rows in sorted(groups.items()):
        latencies = sorted(r['latency_ms'] for r in rows)
        reviewed = sum(r['reviewed_top3'] for r in rows)
        relevant = sum(r['relevant_top3'] for r in rows)
        summary.append({'route': route, 'backend': backend, 'requests': len(rows),
            'statuses': dict(Counter(r['status'] for r in rows)), 'returned_urls': sum(r['url_count'] for r in rows),
            'latency_ms_sorted': latencies, 'median_ms_all_outcomes': statistics.median(latencies),
            'min_ms': min(latencies), 'max_ms': max(latencies),
            'relevant_top3': relevant, 'reviewed_top3': reviewed,
            'precision_among_returned_top3': relevant / reviewed if reviewed else None,
            'relevant_over_all_requested_top3_slots': relevant / (3 * len(rows)),
            'known_url_hit_top10_requests': sum(r['known_url_hit_top10'] for r in rows),
            'known_site_hit_top10_requests': sum(r['known_site_hit_top10'] for r in rows),
            'exact_url_duplicates_top10': sum(r['exact_url_duplicates'] for r in rows)})
    save(ROOT / 'smoke-summary.json', {'scope': 'Two smoke windows only; freshness-smoke separate; top3 agent manual SERP review; no global recall or accepted thresholds',
        'unique_reviewed_query_urls': len(labels), 'summary': summary, 'per_query': details})
    for r in summary:
        print(r['route'], r['backend'], r['statuses'], f"relevant={r['relevant_top3']}/{r['reviewed_top3']}",
              f"known_url={r['known_url_hit_top10_requests']}/{r['requests']}", f"median_ms={r['median_ms_all_outcomes']}")


if __name__ == '__main__':
    main()
