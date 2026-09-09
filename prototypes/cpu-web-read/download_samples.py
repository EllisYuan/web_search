"""Download fixed public samples only; no OCR or benchmark in this preparation step."""
from pathlib import Path
import json
import requests
from prepare import ROOT, FIX, BASE, sha, save


def main():
    from reportlab.pdfgen import canvas
    from PIL import Image
    cases=json.loads((ROOT/'corpus.json').read_text(encoding='utf-8'))
    records=[]
    for case in [x for x in cases if x['id'].startswith('public-image')]:
        response=requests.get(case['url'],timeout=30)
        response.raise_for_status()
        path=ROOT/'downloads'/f'{case["id"]}.jpg';path.parent.mkdir(exist_ok=True)
        path.write_bytes(response.content)
        image=Image.open(path)
        records.append(dict(id=case['id'],url=case['url'],sha256=sha(response.content),bytes=len(response.content),resolution=list(image.size)))
        lang=case['language']
        # Controlled wrappers around genuine public images are explicitly derived,
        # not counted as independent public webpage/PDF samples.
        inline=f'public-derived-inline-{lang}'
        (FIX/f'{inline}.html').write_text(f'<meta charset="utf-8"><article><h1>Public OCR sample</h1><p>Original image follows.</p><img src="{case["url"]}"></article>',encoding='utf-8')
        cases.append(dict(id=inline,kind='inline',language=lang,url=f'{BASE}/{inline}.html',source='derived wrapper; public image source '+case['url'],reference_scope='manual_snippets',keywords=[]))
        scan=f'public-derived-scan-{lang}'
        width,height=image.size
        c=canvas.Canvas(str(FIX/f'{scan}.pdf'),pagesize=(width/2,height/2),invariant=1)
        c.drawImage(str(path),0,0,width=width/2,height=height/2);c.save()
        cases.append(dict(id=scan,kind='pdf',language=lang,url=f'{BASE}/{scan}.pdf',source='derived scan; public image source '+case['url'],reference_scope='manual_snippets',keywords=[],expected_mode='ocr'))
    commit='ffee83231532f4f67b8c0e756cddec67446570c9'
    cases.append(dict(id='public-scan-en',kind='pdf',language='en',url=f'https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/{commit}/tests/resources/linn.pdf',source='OCRmyPDF official scan fixture',reference_scope='manual_snippets',keywords=[],expected_mode='ocr'))
    for name,url in [
        ('model-card','https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/README.md'),
        ('scan-fixture-readme',f'https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/{commit}/tests/resources/README.rst'),
    ]:
        response=requests.get(url,timeout=30)
        record=dict(id=name,url=url,status=response.status_code,sha256=sha(response.content))
        if response.ok:
            (ROOT/'downloads'/f'{name}.txt').write_bytes(response.content)
        records.append(record)
    for case in cases:
        if case['url'].startswith(BASE):
            path=FIX/case['url'].rsplit('/',1)[-1]
            if path.exists():case['fixture_sha256']=sha(path.read_bytes())
    save(ROOT/'corpus.json',cases)
    save(ROOT/'public-sources.json',records)
    print(json.dumps(records,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
