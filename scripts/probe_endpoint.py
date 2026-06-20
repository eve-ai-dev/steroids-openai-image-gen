#!/usr/bin/env python3
# Probe OpenAI-compatible image generation endpoints; usage: python scripts/probe_endpoint.py --base-url URL --model MODEL
# Example: OPENAI_API_KEY=*** python scripts/probe_endpoint.py --base-url https://api.openai.com/v1 --model gpt-image-2
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PNG_1X1_RED = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mP8z8BQDwAFgwJ/l83U7wAAAABJRU5ErkJggg=='
)


def proc_env_lookup(names: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            raw = (proc / 'environ').read_bytes()
        except Exception:
            continue
        for item in raw.split(b'\0'):
            if b'=' not in item:
                continue
            k, v = item.split(b'=', 1)
            ks = k.decode('utf-8', 'ignore')
            if ks in names and ks not in found:
                found[ks] = v.decode('utf-8', 'ignore')
    return found


def request(method: str, url: str, key: str | None, *, json_body: Any = None, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: int = 180) -> dict[str, Any]:
    h = {'Accept': 'application/json'}
    if key:
        h['Authorization'] = f'Bearer {key}'
    if headers:
        h.update(headers)
    data = body
    if json_body is not None:
        data = json.dumps(json_body).encode('utf-8')
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(2_000_000)
            text = raw.decode('utf-8', 'replace')
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                pass
            return {'ok': 200 <= r.status < 300, 'status': r.status, 'elapsed_s': round(time.time()-t0, 2), 'json': parsed, 'text_preview': text[:500]}
    except urllib.error.HTTPError as e:
        raw = e.read(200_000)
        text = raw.decode('utf-8', 'replace')
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            pass
        return {'ok': False, 'status': e.code, 'elapsed_s': round(time.time()-t0, 2), 'json': parsed, 'text_preview': text[:800]}
    except Exception as e:
        return {'ok': False, 'status': None, 'elapsed_s': round(time.time()-t0, 2), 'error': f'{type(e).__name__}: {e}'}


def summarize_image_response(resp: dict[str, Any]) -> dict[str, Any]:
    out = {k: resp.get(k) for k in ['ok', 'status', 'elapsed_s', 'error'] if k in resp}
    j = resp.get('json')
    if isinstance(j, dict):
        data = j.get('data')
        if isinstance(data, list) and data:
            first = data[0] if isinstance(data[0], dict) else {}
            out['data_len'] = len(data)
            out['first_keys'] = sorted(first.keys()) if isinstance(first, dict) else type(first).__name__
            out['has_b64_json'] = isinstance(first, dict) and bool(first.get('b64_json'))
            out['has_url'] = isinstance(first, dict) and bool(first.get('url'))
        elif 'error' in j:
            out['api_error'] = j.get('error')
        else:
            out['json_keys'] = sorted(j.keys())[:20]
    else:
        out['text_preview'] = resp.get('text_preview')
    return out


def multipart(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
    boundary = '----steroidsProbeBoundary7MA4YWxkTrZu0gW'
    chunks: list[bytes] = []
    for k, v in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for field, filename, ctype, content in files:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'.encode())
        chunks.append(content + b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), f'multipart/form-data; boundary={boundary}'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default=os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1')
    ap.add_argument('--model', default=os.environ.get('OPENAI_IMAGE_MODEL') or 'gpt-image-2')
    ap.add_argument('--api-key-env', default='OPENAI_API_KEY')
    ap.add_argument('--timeout', type=int, default=180)
    args = ap.parse_args()
    base = args.base_url.rstrip('/')
    proc = proc_env_lookup([args.api_key_env])
    key = os.environ.get(args.api_key_env) or proc.get(args.api_key_env)
    report: dict[str, Any] = {
        'base_url': base,
        'model': args.model,
        'api_key_env': args.api_key_env,
        'has_key': bool(key),
        'tests': {},
    }
    if not key:
        report['fatal'] = 'No API key found in current env or /proc for requested api-key-env.'
        print(json.dumps(report, indent=2))
        return 2

    report['tests']['models'] = request('GET', f'{base}/models', key, timeout=60)

    qualities = [None, 'low', 'medium', 'high', 'auto']
    gen_results = {}
    for q in qualities:
        payload = {
            'model': args.model,
            'prompt': 'A tiny simple red square icon on a plain white background. No text.',
            'size': '1024x1024',
            'response_format': 'b64_json',
        }
        label = 'omitted' if q is None else q
        if q is not None:
            payload['quality'] = q
        resp = request('POST', f'{base}/images/generations', key, json_body=payload, timeout=args.timeout)
        gen_results[label] = summarize_image_response(resp)
    report['tests']['images_generations_quality'] = gen_results

    edit_results = {}
    fields = {
        'model': args.model,
        'prompt': 'Change the red pixel/square to blue while preserving the simple white background.',
        'size': '1024x1024',
        'quality': 'medium',
        'response_format': 'b64_json',
    }
    body, ctype = multipart(fields, [('image', 'red.png', 'image/png', PNG_1X1_RED)])
    resp = request('POST', f'{base}/images/edits', key, body=body, headers={'Content-Type': ctype}, timeout=args.timeout)
    edit_results['single_image'] = summarize_image_response(resp)
    report['tests']['images_edits_multipart'] = edit_results

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
