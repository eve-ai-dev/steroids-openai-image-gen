#!/usr/bin/env python3
# Probe only /v1/images/edits variants; usage: python scripts/probe_edits_only.py --base-url URL --model MODEL
# Example: OPENAI_API_KEY=*** python scripts/probe_edits_only.py --base-url https://api.openai.com/v1 --model gpt-image-2
from __future__ import annotations
import argparse, base64, json, os, time, urllib.request, urllib.error
from pathlib import Path


def proc_env_lookup(names: list[str]) -> dict[str, str]:
    found = {}
    for p in Path('/proc').glob('[0-9]*/environ'):
        try:
            for item in p.read_bytes().split(b'\0'):
                if b'=' not in item: continue
                k, v = item.split(b'=', 1)
                ks = k.decode('utf-8', 'ignore')
                if ks in names and ks not in found:
                    found[ks] = v.decode('utf-8', 'ignore')
        except Exception:
            pass
    return found


def make_png(width=64, height=64):
    import struct, zlib
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes([255, 0, 0]) * width for _ in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def mp(fields, files):
    b='----steroidsEditProbeBoundary'
    chunks=[]
    for k,v in fields.items(): chunks.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for field,fn,ct,content in files:
        chunks.append(f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode()+content+b'\r\n')
    chunks.append(f'--{b}--\r\n'.encode())
    return b''.join(chunks), f'multipart/form-data; boundary={b}'


def post(base, key, label, fields, files):
    body,ct=mp(fields,files)
    req=urllib.request.Request(f'{base}/images/edits', data=body, method='POST', headers={'Authorization':f'Bearer {key}','Content-Type':ct,'Accept':'application/json'})
    t=time.time()
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            txt=r.read(2_000_000).decode('utf-8','replace')
            j=json.loads(txt)
            first=(j.get('data') or [{}])[0]
            return {'label':label,'ok':True,'status':r.status,'elapsed_s':round(time.time()-t,2),'keys':sorted(first.keys()),'has_b64_json':bool(first.get('b64_json')),'has_revised_prompt':'revised_prompt' in first}
    except urllib.error.HTTPError as e:
        txt=e.read(200_000).decode('utf-8','replace')
        try: err=json.loads(txt)
        except Exception: err=txt[:800]
        return {'label':label,'ok':False,'status':e.code,'elapsed_s':round(time.time()-t,2),'error':err}
    except Exception as e:
        return {'label':label,'ok':False,'status':None,'elapsed_s':round(time.time()-t,2),'error':f'{type(e).__name__}: {e}'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url', default=os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1')
    ap.add_argument('--model', default=os.environ.get('OPENAI_IMAGE_MODEL') or 'gpt-image-2')
    ap.add_argument('--api-key-env', default='OPENAI_API_KEY')
    args=ap.parse_args()
    base=args.base_url.rstrip('/')
    proc=proc_env_lookup([args.api_key_env])
    key=os.environ.get(args.api_key_env) or proc.get(args.api_key_env)
    if not key:
        print(json.dumps({'base_url':base,'model':args.model,'api_key_env':args.api_key_env,'fatal':'No API key found'}, indent=2)); return 2
    png=make_png()
    base_fields={'model':args.model,'prompt':'Change the red square to blue; preserve plain white background.','size':'1024x1024','quality':'medium','response_format':'b64_json'}
    results=[]
    results.append(post(base, key, 'single_image', base_fields, [('image','source.png','image/png',png)]))
    results.append(post(base, key, 'image_plus_image_array_ref', base_fields, [('image','source.png','image/png',png),('image[]','ref.png','image/png',png)]))
    print(json.dumps({'base_url':base,'model':args.model,'endpoint':'POST /v1/images/edits','results':results}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
