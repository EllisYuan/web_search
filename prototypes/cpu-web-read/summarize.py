"""Recompute evidence summaries and a self-contained real-trace review page."""
import json
from pathlib import Path
from probe import ROOT, dump, normalize, distance


def region_review(result,refs):
    case=result['case']; name=case['id']; lang=case['language']
    reference=refs.get(name) or (refs.get(f'public-image-{lang}') if name.startswith('public-derived') else None)
    if not reference:return []
    regions=[]
    units=[x for x in result['units'] if x.get('mode')=='ocr']
    ocr_stages=[s for s in result['stages'] if s['stage']=='ocr' and not s.get('error')]
    for unit,stage in zip(units,ocr_stages):
        for ref in reference['regions']:
            left,top,right,bottom=ref['bounds'];texts=[]
            for box in unit.get('boxes',[]):
                cx=sum(x[0] for x in box['bbox'])/(4*stage['width'])
                cy=sum(x[1] for x in box['bbox'])/(4*stage['height'])
                if left<=cx<right and top<=cy<bottom:texts.append(box['text'])
            actual='\n'.join(texts);a=normalize(ref['reference']);b=normalize(actual)
            regions.append(dict(name=ref['name'],locator=unit['locator'],reference=ref['reference'],actual=actual,
                                cer=distance(a,b)/max(1,len(a)),bounds=ref['bounds']))
    return regions


def main():
    refs=json.loads((ROOT/'references.json').read_text(encoding='utf-8'))
    results=[];admissions=[];traces=[]
    for run in sorted((ROOT/'runs').iterdir()):
        if not run.is_dir():continue
        for path in sorted(run.glob('*-gate.json')):
            data=json.loads(path.read_text(encoding='utf-8'))
            admissions.append(dict(run=run.name,id=path.name.removesuffix('-gate.json'),**data))
        for path in sorted(run.glob('*.json')):
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or 'temperature' not in data:continue
            case=data['case'];resource_path=run/f'{case["id"]}-resources.json'
            resource=json.loads(resource_path.read_text(encoding='utf-8')) if resource_path.exists() else {}
            samples=[x for x in resource.get('samples',[]) if data['start_perf']<=x.get('perf',0)<=data['end_perf']]
            row=dict(run=run.name,id=case['id'],kind=case['kind'],language=case['language'],temperature=data['temperature'],
                     status=data['status'],error=data.get('error'),wall_s=data['wall_s'],first_preview_s=data['first_preview_s'],
                     process_tree_rss_peak_mib=max((x['tree_rss_bytes'] for x in samples),default=0)/2**20,
                     process_tree_cpu_sampled_s=(samples[-1]['tree_cpu_s']-samples[0]['tree_cpu_s']) if len(samples)>1 else None,
                     stage_wall_s={name:sum(s['wall_s'] for s in data['stages'] if s['stage']==name) for name in ['download','browser_render','text_extraction','html_extraction','model_load','raster','ocr']},
                     cer=data.get('quality',{}).get('cer'),keyword_checks=data.get('quality',{}).get('keywords'),
                     line_coverage=data.get('quality',{}).get('reference_line_coverage'),
                     regions=region_review(data,refs),scope=data['scope'],
                     reconstruction=next((t['equal'] for t in data['trace'] if t['action']=='reconstruction'),None),
                     source=str(path.relative_to(ROOT)).replace('\\','/'),
                     resource_stop_reason=resource.get('stop_reason'),
                     host_cpu_percent_mean=sum(x['host_cpu_percent'] for x in samples)/len(samples) if samples else None,
                     min_available_mib=min((x['available_bytes'] for x in samples),default=0)/2**20)
            results.append(row)
            # Keep full traces of controlled fixtures only in the shareable demo.
            # Public third-party pages are inspected locally; summary links their source.
            if not case['id'].startswith('public'):
                traces.append(dict(name=run.name+'/'+case['id']+'/'+data['temperature'],trace=data['trace']))
    dump(ROOT/'summary.json',dict(results=results,admissions=admissions))
    lines=['# 实测汇总（自动重算）','','尚需用户评审。cold = 首次 process/engine；warm = 同一 process 保留 engine 后重读。',
           'stage_wall_s 的 advance 与子阶段存在包含关系，不能简单累加。RSS 是 100 ms 采样值，不是 OS 精确 peak。','',
           '| run / case | state | preview s | total s | peak MiB | CER |',
           '|---|---|---:|---:|---:|---:|']
    for row in results:
        preview=f'{row["first_preview_s"]:.3f}' if row['first_preview_s'] is not None else '—'
        cer=f'{row["cer"]:.4f}' if row['cer'] is not None else '—'
        lines.append(f'| {row["run"]} / {row["id"]} {row["temperature"]} | {row["status"]} | {preview} | {row["wall_s"]:.3f} | {row["process_tree_rss_peak_mib"]:.1f} | {cer} |')
    lines.extend(['',f'实际结果 {len(results)} 条；resource gate 拒绝 {sum(not a["allowed"] for a in admissions)} 次。拒绝不计格式成功率。'])
    (ROOT/'SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    template=(ROOT/'trace-viewer.template.html').read_text(encoding='utf-8')
    payload=json.dumps(traces,ensure_ascii=False).replace('<','\\u003c')
    (ROOT/'trace-viewer.html').write_text(template.replace('/*TRACE_DATA*/[]',payload),encoding='utf-8')
    print(f'{len(results)} measured results; {len(admissions)} admission attempts; {len(traces)} trace scenarios.')


if __name__=='__main__':main()
