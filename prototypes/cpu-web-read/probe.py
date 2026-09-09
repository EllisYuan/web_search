"""PROTOTYPE only. Real HTTP/browser/PDF/OCR pipeline and progressive trace.

Run with: .venv/Scripts/python.exe prototypes/cpu-web-read/probe.py run --group ocr
No model summaries, hosted OCR, GPU, production MCP or persistent reader service.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import importlib.metadata as md
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import unicodedata
from urllib.parse import urljoin, urlparse

import psutil
import requests

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT.parents[1]/'.cache'/'ms-playwright'))
LIMITS = dict(http_timeout_s=30, browser_timeout_ms=30000, case_timeout_s=180,
              max_bytes=20*1024**2, max_pages=12, max_pixels=12000000, dpi=150,
              intra_threads=2, inter_threads=1, concurrency=1,
              max_tree_rss_bytes=3*1024**3, min_available_bytes=2*1024**3,
              gate_cpu_percent=25, monitor_interval_s=0.1, retries=1)


def now(): return datetime.now(timezone.utc).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()
def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class FixtureHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/denied': self.send_error(403, 'injected denial'); return
        if self.path == '/interrupted':
            self.send_response(200)
            self.send_header('Content-Length', '100000')
            self.end_headers()
            self.wfile.write(b'<html>incomplete')
            self.close_connection = True
            return
        super().do_GET()


def serve():
    server=ThreadingHTTPServer(('127.0.0.1',8767),partial(FixtureHandler,directory=str(ROOT/'fixtures')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server


def gate():
    other=[]
    for proc in psutil.process_iter(['name','cmdline']):
        try:
            cmd=' '.join(proc.info['cmdline'] or [])
            if 'free-search' in cmd and any(x in cmd for x in ['probe.py','batch_demo.py','readability.py']):
                other.append({'pid':proc.pid,'name':proc.info['name'],'scope':'free-search workload'})
        except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    cpu=psutil.cpu_percent(interval=3)
    ram=psutil.virtual_memory().available
    return dict(at=now(),cpu_percent=cpu,available_bytes=ram,other_workloads=other,
                allowed=cpu<=LIMITS['gate_cpu_percent'] and ram>=LIMITS['min_available_bytes'] and not other)


class Reader:
    def __init__(self, case, out, engine=None):
        self.case=case; self.out=out; self.engine=engine
        self.units=[]; self.toc=[]; self.events=[]; self.failures=[]
        self.metadata={}; self.version=None; self.expired=False
        self.generator=None; self.done=False; self.cap_reached=False
        self.stages=[]; self.start=time.perf_counter(); self.started_at=now()
        self.first_preview_s=None; self.providers=[]

    @contextmanager
    def stage(self,name,**details):
        start=time.perf_counter(); cpu=time.process_time()
        record=dict(stage=name,**details)
        try: yield record
        except Exception as exc:
            record['error']=f'{type(exc).__name__}: {exc}'
            raise
        finally:
            record.update(wall_s=time.perf_counter()-start,cpu_self_s=time.process_time()-cpu)
            self.stages.append(record)

    def fetch(self,url,tag):
        last=None
        for attempt in range(2):
            try:
                with self.stage('download',url=url,attempt=attempt+1) as measure:
                    with requests.get(url,timeout=LIMITS['http_timeout_s'],stream=True,
                                      headers={'User-Agent':'cpu-web-read-prototype/0.1'}) as response:
                        measure['http_status']=response.status_code
                        response.raise_for_status()
                        data=bytearray()
                        for chunk in response.iter_content(65536):
                            data.extend(chunk)
                            if len(data)>LIMITS['max_bytes']: raise ValueError('file_byte_limit')
                        data=bytes(data)
                        measure.update(bytes=len(data),sha256=sha(data),final_url=response.url,
                                       content_type=response.headers.get('Content-Type',''))
                        path=self.out/'raw'/f'{self.case["id"]}-{tag}'
                        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                        return data,measure.copy()
            except requests.HTTPError as exc:
                # No retries for deterministic denial/not found.
                if exc.response.status_code < 500: raise
                last=exc
            except (requests.Timeout,requests.ConnectionError,requests.exceptions.ChunkedEncodingError) as exc: last=exc
        raise RuntimeError(f'fetch_retry_exhausted: {last}')

    def load_engine(self):
        if self.engine is None:
            with self.stage('model_load'):
                import cv2
                from rapidocr import RapidOCR
                cv2.setNumThreads(2)
                package=Path(md.distribution('rapidocr').locate_file('rapidocr'))
                params={'Global.log_level':'error','EngineConfig.onnxruntime.intra_op_num_threads':2,
                        'EngineConfig.onnxruntime.inter_op_num_threads':1,
                        'EngineConfig.onnxruntime.use_cuda':False,'EngineConfig.onnxruntime.use_dml':False,
                        'EngineConfig.onnxruntime.use_cann':False,'EngineConfig.onnxruntime.use_coreml':False,
                        'Det.model_path':str(package/'models/PP-OCRv6_det_small.onnx'),
                        'Rec.model_path':str(package/'models/PP-OCRv6_rec_small.onnx'),
                        'Cls.model_path':str(package/'models/ch_ppocr_mobile_v2.0_cls_mobile.onnx')}
                self.engine=RapidOCR(params=params)
        for part in ['text_det','text_cls','text_rec']:
            session=getattr(self.engine,part).session.session
            providers=session.get_providers()
            options=session.get_session_options()
            assert providers==['CPUExecutionProvider'],providers
            self.providers.append(dict(component=part,providers=providers,
                intra_threads=options.intra_op_num_threads,inter_threads=options.inter_op_num_threads))

    def ocr(self,image,locator):
        import numpy as np
        from PIL import Image
        if isinstance(image,bytes): image=Image.open(io.BytesIO(image))
        image.load()
        if image.width*image.height>LIMITS['max_pixels']: raise ValueError('image_pixel_limit')
        self.load_engine()
        with self.stage('ocr',locator=locator,width=image.width,height=image.height) as measure:
            result=self.engine(np.asarray(image.convert('RGB'))[:,:,::-1])
            records=[]
            if result.txts is not None:
                for box,text,score in zip(result.boxes,result.txts,result.scores):
                    records.append(dict(text=text,confidence=float(score),bbox=box.tolist(),locator=locator))
            measure.update(lines=len(records),internal_stage_seconds=result.elapse_list)
            if not records: raise ValueError('no_text_detected')
            return '\n'.join(x['text'] for x in records),records

    def add_unit(self,locator,text='',mode=None,**extra):
        unit=dict(locator=locator,text=text,mode=mode,status='ok',**extra)
        self.units.append(unit)
        return unit

    def fail_unit(self,locator,exc,**extra):
        failure=dict(locator=locator,error=f'{type(exc).__name__}: {exc}',**extra)
        self.failures.append(failure)
        self.units.append(dict(locator=locator,status='failed',text='',failure=failure))

    def open(self):
        data,download=self.fetch(self.case['url'],'source')
        self.version=sha(data)
        self.metadata=dict(url=self.case['url'],source_sha256=self.version,fetched_at=now(),download=download)
        kind=self.case['kind']
        if kind=='pdf': self.generator=self.pdf(data)
        elif kind=='image': self.generator=self.image(data)
        else: self.generator=self.html(data)
        self.advance()

    def advance(self):
        if self.done: return
        with self.stage('advance'):
            try: next(self.generator)
            except StopIteration: self.done=True
            if self.done: self.generator.close()

    def image(self,data):
        self.metadata['total_units']=1
        try:
            text,boxes=self.ocr(data,dict(image_url=self.case['url']))
            self.add_unit(dict(image_url=self.case['url']),text,'ocr',boxes=boxes)
        except Exception as exc: self.fail_unit(dict(image_url=self.case['url']),exc)
        self.done=True
        yield

    def pdf(self,data):
        import pypdfium2 as pdfium
        import pypdfium2.raw as raw
        with self.stage('pdf_open'):
            pdf=pdfium.PdfDocument(data)
            self.metadata.update(pdf_metadata=pdf.get_metadata_dict(),total_units=len(pdf))
            self.toc=[dict(title=x.title,page=x.page_index+1 if x.page_index is not None else None,level=x.level) for x in pdf.get_toc()]
        try:
            for index in range(min(len(pdf),LIMITS['max_pages'])):
                locator=dict(page=index+1)
                for attempt in range(2):
                    try:
                        if self.case.get('inject_fail_page')==index+1: raise RuntimeError('injected_page_ocr_failure')
                        with pdf[index] as page:
                            with self.stage('text_extraction',page=index+1):
                                with page.get_textpage() as textpage:
                                    text=textpage.get_text_range().replace('\r\n','\n').strip()
                                    # Capture only image regions with no covering native text. A text
                                    # layer elsewhere on the page must not suppress these regions.
                                    images=[]
                                    if text:
                                        for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
                                            bounds=obj.get_bounds()
                                            covered=textpage.get_text_bounded(*bounds).strip()
                                            images.append((obj,bounds,bool(covered)))
                            boxes=[]; mode='text_layer'
                            if not text:
                                with self.stage('raster',page=index+1,dpi=LIMITS['dpi']):
                                    width,height=page.get_size()
                                    if width*height*(LIMITS['dpi']/72)**2>LIMITS['max_pixels']:
                                        raise ValueError('raster_pixel_limit')
                                    bitmap=page.render(scale=LIMITS['dpi']/72)
                                    image=bitmap.to_pil().copy(); bitmap.close()
                                text,boxes=self.ocr(image,locator)
                                mode='ocr'
                            else:
                                for image_index,(obj,bounds,covered) in enumerate(images):
                                    if covered:
                                        self.events.append(dict(event='skip_image_with_text_overlay',page=index+1,bounds=bounds))
                                        continue
                                    image_locator=dict(page=index+1,image_index=image_index,bounds_pdf_points=list(bounds))
                                    try:
                                        with self.stage('raster_image',**image_locator):
                                            bitmap=obj.get_bitmap(render=True)
                                            image=bitmap.to_pil().copy();bitmap.close()
                                        image_text,image_boxes=self.ocr(image,image_locator)
                                        text+='\n'+image_text; boxes.extend(image_boxes); mode='text_layer+ocr'
                                    except Exception as exc:
                                        self.failures.append(dict(locator=image_locator,error=str(exc)))
                            self.add_unit(locator,text,mode,boxes=boxes,attempts=attempt+1)
                        break
                    except Exception as exc:
                        self.events.append(dict(event='page_attempt_failed',page=index+1,attempt=attempt+1,error=str(exc)))
                        if attempt==1: self.fail_unit(locator,exc,attempts=2,injected=bool(self.case.get('inject_fail_page')))
                if index==len(pdf)-1: self.done=True
                yield
            if len(pdf)>LIMITS['max_pages']:
                self.cap_reached=True
                self.failures.append(dict(locator=dict(pages=[LIMITS['max_pages']+1,len(pdf)]),error='page_limit_unprocessed'))
        finally: pdf.close()

    def html(self,data):
        from lxml import etree, html
        import trafilatura
        markup=data.decode('utf-8',errors='replace')
        rendered=False
        if self.case['kind']=='js':
            self.metadata['raw_dom_text_chars']=len(html.fromstring(markup).text_content())
            with self.stage('browser_render') as measure:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as play:
                    browser=play.chromium.launch(headless=True,args=['--disable-gpu'])
                    try:
                        page=browser.new_page()
                        response=page.goto(self.case['url'],wait_until='domcontentloaded',timeout=30000)
                        if response and response.status>=400: raise ValueError(f'browser_http_{response.status}')
                        page.locator(self.case.get('ready_selector','main')).first.wait_for(timeout=30000)
                        markup=page.content();rendered=True
                        measure.update(browser_version=browser.version,rendered_sha256=sha(markup.encode()))
                        path=self.out/'rendered'/f'{self.case["id"]}.html';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(markup,encoding='utf-8')
                    finally: browser.close()
            self.version=sha(markup.encode())
            self.metadata['rendered_sha256']=self.version
        with self.stage('html_extraction'):
            tree=html.fromstring(markup)
            xml=trafilatura.extract(markup,output_format='xml',include_comments=False,include_tables=True,
                                    include_images=False,favor_recall=True)
            if not xml: raise ValueError('empty_extraction')
            extracted=etree.fromstring(xml.encode())
            pieces=[]; length=0
            for elem in extracted.xpath('.//main//*[self::head or self::p or self::item or self::cell or self::quote or self::code]'):
                if any(parent.tag in ('p','item','cell','quote','code') for parent in elem.iterancestors()): continue
                value=''.join(elem.itertext()).strip()
                if not value: continue
                if elem.tag=='head':
                    self.toc.append(dict(section=f'section-{len(self.toc)+1}',title=value,position=length))
                pieces.append(value); length+=len(value)+1
            text='\n'.join(pieces)
            if not text: text='\n'.join(extracted.itertext()).strip()
            self.metadata.update(title=tree.findtext('.//title'),rendered=rendered)
            image_urls=[]
            for img in tree.xpath('//article//img | //main//img'):
                # Preserve common lazy-loading discovery; this is not an exhaustive web image resolver.
                src=img.get('data-src') or img.get('src')
                if src:
                    url=urljoin(self.case['url'],src)
                    if urlparse(url).scheme in ('http','https') and url not in image_urls: image_urls.append(url)
            self.metadata.update(image_urls=image_urls,total_units=1+len(image_urls))
            self.add_unit(dict(dom='extracted-main',url=self.case['url']),text,'rendered_dom' if rendered else 'html')
        if not image_urls: self.done=True
        yield
        for index,url in enumerate(image_urls):
            loc=dict(image_url=url,image_index=index)
            try:
                image_data,_=self.fetch(url,f'image-{index}')
                image_text,boxes=self.ocr(image_data,loc)
                self.add_unit(loc,image_text,'ocr',boxes=boxes)
            except Exception as exc: self.fail_unit(loc,exc)
            if index==len(image_urls)-1: self.done=True
            yield

    def text(self): return ''.join(unit['text']+'\n' for unit in self.units)

    def scope(self):
        return dict(processed_units=len(self.units),total_units=self.metadata.get('total_units'),
                    failed_units=sum(x['status']=='failed' for x in self.units),failures=self.failures,
                    extraction_done=self.done,complete=self.done and not self.failures and not self.cap_reached,
                    searchable_chars=len(self.text()),pending_units=max(0,self.metadata.get('total_units',len(self.units))-len(self.units)))

    def read(self,position=0,limit=320,version=None,section=None):
        if self.expired: return dict(error='state_expired')
        if version is not None and version!=self.version: return dict(error='content_version_mismatch')
        if section is not None:
            matches=[x for x in self.toc if x.get('section')==section]
            if not matches: return dict(error='unknown_section')
            position=matches[0]['position']
        text=self.text()
        if not isinstance(position,int) or position<0 or position>len(text): return dict(error='position_out_of_range')
        end=min(position+limit,len(text))
        spans=[];offset=0
        for unit in self.units:
            unit_end=offset+len(unit['text'])+1
            if end>offset and position<unit_end:
                spans.append(dict(start=max(position,offset),end=min(end,unit_end),locator=unit['locator'],mode=unit.get('mode'),status=unit['status']))
            offset=unit_end
        return dict(text=text[position:end],position=position,next_position=end,version=self.version,spans=spans,
                    truncated=end<len(text) or not self.done,
                    end_of_document=end==len(text) and self.done and not self.failures and not self.cap_reached,
                    end_of_available=end==len(text),needs_processing=end==len(text) and not self.done,scope=self.scope())

    def find(self,word):
        text=self.text(); hits=[];pos=0
        while word and (pos:=text.find(word,pos))!=-1:
            hits.append(dict(position=pos,context=self.read(max(0,pos-40),len(word)+80)))
            pos+=len(word)
        return dict(keyword=word,hits=hits,scope=self.scope(),whole_document_no_match=not hits and self.scope()['complete'])


def normalize(text): return ''.join(unicodedata.normalize('NFKC',text).split())


def distance(a,b):
    row=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        nxt=[i]
        for j,cb in enumerate(b,1): nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(ca!=cb)))
        row=nxt
    return row[-1]


def quality(reader):
    case=reader.case;ref=case.get('reference'); units=reader.units
    scope=case.get('reference_scope')
    if scope=='image_unit': units=[x for x in units if x.get('mode')=='ocr']
    actual=units[0]['text'] if units else ''
    all_text=reader.text()
    result=dict(reference_scope=scope,reference=ref,actual_first_unit=actual,
                keywords={k:normalize(k) in normalize(all_text) for k in case.get('keywords',[])},
                noise_tokens=[x for x in ['NOISE_NAV','NOISE_FOOTER'] if x in all_text])
    if ref and scope in ('whole_unit','first_unit','image_unit'):
        a,b=normalize(ref),normalize(actual)
        result.update(cer=distance(a,b)/max(1,len(a)),reference_chars=len(a),normalization='NFKC then remove all Unicode whitespace; retain case/punctuation')
    if ref:
        result['reference_line_coverage']=sum(normalize(x) in normalize(all_text) for x in ref.splitlines())/len(ref.splitlines())
    return result


def execute(case,out,engine=None):
    reader=Reader(case,out,engine);trace=[]
    try:
        reader.open()
        if case.get('eager_preview'):
            while not reader.done: reader.advance()
        preview=reader.read()
        reader.first_preview_s=time.perf_counter()-reader.start
        trace.append(dict(action='open',elapsed_s=reader.first_preview_s,metadata=reader.metadata,toc=reader.toc,preview=preview))
        keyword=(case.get('keywords') or ['ORCHID'])[0]
        trace.append(dict(action='find_before_full_processing',result=reader.find(keyword)))
        while not reader.done:
            before=time.perf_counter(); reader.advance()
            trace.append(dict(action='process_next',wall_s=time.perf_counter()-before,scope=reader.scope()))
        full_ready_s=time.perf_counter()-reader.start
        trace.append(dict(action='full_document_ready',elapsed_s=full_ready_s,
                          explanation='eager preview lower bound in this progressive run; separate eager run required for comparison'))
        final=reader.text();pos=0;chunks=[]
        while pos<len(final):
            before=time.perf_counter();piece=reader.read(pos,320)
            chunks.append(piece['text']);trace.append(dict(action='read_position',wall_s=time.perf_counter()-before,result=piece))
            pos=piece['next_position']
        reconstructed=''.join(chunks)
        trace.append(dict(action='reconstruction',equal=reconstructed==final,chars=len(final),sha256=sha(final.encode()),chunks=len(chunks)))
        trace.append(dict(action='end',result=reader.read(pos)))
        trace.append(dict(action='find_after_full_processing',result=reader.find(keyword)))
        trace.append(dict(action='no_match',result=reader.find('__absent_9f128e__')))
        trace.append(dict(action='invalid_position',result=reader.read(len(final)+1)))
        trace.append(dict(action='unknown_section',result=reader.read(section='missing')))
        if reader.toc and 'section' in reader.toc[0]: trace.append(dict(action='read_section',result=reader.read(section=reader.toc[0]['section'])))
        trace.append(dict(action='changed_content_token',injected=True,result=reader.read(version='different-content-version')))
        reader.expired=True
        trace.append(dict(action='expired_state',injected=True,result=reader.read()))
        status=('partial' if any(x['status']=='ok' for x in reader.units) else 'failed') if reader.failures else 'ok'
        result=dict(status=status,quality=quality(reader),scope=reader.scope())
    except Exception as exc:
        result=dict(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc(),scope=reader.scope())
    result.update(case=case,started_at=reader.started_at,wall_s=time.perf_counter()-reader.start,first_preview_s=reader.first_preview_s,
                  start_perf=reader.start,end_perf=time.perf_counter(),
                  stages=reader.stages,metadata=reader.metadata,toc=reader.toc,units=reader.units,
                  events=reader.events,failures=reader.failures,execution_sessions=reader.providers,trace=trace)
    return result,reader.engine


def worker(case,out,repeats):
    engine=None
    for index in range(repeats):
        # Warm means a retained OCR engine, not a new process. HTTP is fetched again.
        result,engine=execute(case,out,engine)
        result['temperature']='process_cold' if index==0 else 'engine_warm'
        dump(out/f'{case["id"]}-{index}.json',result)


def monitor(process):
    root=psutil.Process(process.pid);peak=0;cpus={};samples=[];reason=None
    start=time.perf_counter()
    while process.poll() is None:
        rss=0
        try: members=[root]+root.children(recursive=True)
        except psutil.NoSuchProcess: break
        for child in members:
            try:
                rss+=child.memory_info().rss
                cpu=child.cpu_times();cpus[child.pid]=cpu.user+cpu.system
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        peak=max(peak,rss)
        available=psutil.virtual_memory().available
        samples.append(dict(elapsed_s=round(time.perf_counter()-start,3),perf=time.perf_counter(),tree_rss_bytes=rss,tree_cpu_s=sum(cpus.values()),
                            host_cpu_percent=psutil.cpu_percent(),available_bytes=available))
        if rss>LIMITS['max_tree_rss_bytes']: reason='tree_rss_limit'
        elif available<LIMITS['min_available_bytes']: reason='available_ram_guard'
        elif time.perf_counter()-start>LIMITS['case_timeout_s']: reason='case_timeout'
        if reason:
            for child in reversed(members):
                try: child.kill()
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            break
        time.sleep(LIMITS['monitor_interval_s'])
    process.wait()
    return dict(returncode=process.returncode,stop_reason=reason,sampled_peak_tree_rss_bytes=peak,
                sampled_tree_cpu_s=sum(cpus.values()),wall_s=time.perf_counter()-start,
                samples=samples,measurement='100 ms sampling; RSS sum incl browser children, excludes controller/fixture server; CPU last observed per PID, short-lived children may be missed')


def run(args):
    cases=json.loads((ROOT/'corpus.json').read_text(encoding='utf-8'))
    if args.ids: cases=[x for x in cases if x['id'] in args.ids.split(',')]
    elif args.group=='ocr': cases=[x for x in cases if x['kind'] in ('image','inline') or x.get('expected_mode')=='ocr']
    elif args.group=='read': cases=[x for x in cases if x['kind'] in ('html','js','pdf') and x.get('expected_mode')!='ocr']
    out=ROOT/'runs'/args.name;out.mkdir(parents=True,exist_ok=True)
    dump(out/'limits.json',LIMITS)
    server=serve()
    try:
        for case in cases:
            if args.inject_page: case['inject_fail_page']=args.inject_page
            if args.eager: case['eager_preview']=True
            check=gate();dump(out/f'{case["id"]}-gate.json',check)
            if not check['allowed']:
                print(json.dumps(dict(id=case['id'],status='deferred_resource_gate',gate=check)),flush=True)
                continue
            casepath=out/f'{case["id"]}-input.json';dump(casepath,case)
            with (out/f'{case["id"]}-worker.log').open('w',encoding='utf-8') as log:
                proc=subprocess.Popen([sys.executable,__file__,'worker','--case',str(casepath),'--out',str(out),'--repeats',str(args.repeats)],
                                      stdout=log,stderr=subprocess.STDOUT,
                                      creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                metrics=monitor(proc)
            dump(out/f'{case["id"]}-resources.json',metrics)
            print(json.dumps(dict(id=case['id'],stop=metrics['stop_reason'],returncode=metrics['returncode'],wall_s=round(metrics['wall_s'],3),peak_mib=round(metrics['sampled_peak_tree_rss_bytes']/2**20,1))),flush=True)
    finally: server.shutdown();server.server_close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    batch=sub.add_parser('run')
    batch.add_argument('--group',choices=['ocr','read','all'],default='all')
    batch.add_argument('--ids');batch.add_argument('--name',default='baseline')
    batch.add_argument('--repeats',type=int,default=1);batch.add_argument('--inject-page',type=int)
    batch.add_argument('--eager',action='store_true')
    child=sub.add_parser('worker');child.add_argument('--case',type=Path);child.add_argument('--out',type=Path);child.add_argument('--repeats',type=int,default=1)
    sub.add_parser('gate')
    args=parser.parse_args()
    if args.command=='run':run(args)
    elif args.command=='gate': print(json.dumps(gate()))
    else:worker(json.loads(args.case.read_text(encoding='utf-8')),args.out,args.repeats)


if __name__=='__main__': main()
