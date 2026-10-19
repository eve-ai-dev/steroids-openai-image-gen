"""Persist image jobs; supervise work and notify via public plugin APIs.

Own a continuously running loop: sync tool dispatch does not promise one.
Notification acceptance is never proof of media delivery.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from hermes_constants import get_hermes_home
from .provider import SteroidsOpenAIImageGenProvider

_INSTANCE = os.urandom(16).hex()

class BackgroundImageJobError(Exception):
    """Expected job failure."""


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _env_int(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise BackgroundImageJobError(f'{name} must be an integer') from exc
    if not minimum <= value <= maximum:
        raise BackgroundImageJobError(f'{name} must be between {minimum} and {maximum}')
    return value


def _json_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def _read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


@dataclass
class BackgroundJobSpec:
    prompt: str
    aspect_ratio: str = 'landscape'
    quality: str = 'medium'
    image_url: str | None = None
    reference_image_urls: list[str] | None = None
    mask_url: str | None = None
    input_fidelity: str | None = None


def jobs_root():
    return Path(get_hermes_home()) / 'steroids_openai_image_gen' / 'jobs'


def normalize_jobs(args):
    jobs = args.get('jobs')
    if jobs is None or jobs == []:
        if not str(args.get('prompt') or '').strip():
            raise BackgroundImageJobError('prompt is required when jobs is omitted or empty')
        jobs = [{k: v for k, v in args.items() if k in BackgroundJobSpec.__dataclass_fields__}]
    if not isinstance(jobs, list) or not jobs:
        raise BackgroundImageJobError('jobs must be a non-empty list')
    if len(jobs) > _env_int('STEROIDS_IMAGE_BG_MAX_JOBS', 4, 1, 32):
        raise BackgroundImageJobError('too many jobs')
    return [_normalize_job(item) for item in jobs]


def _normalize_job(item):
    if not isinstance(item, dict) or not isinstance(item.get('prompt'), str) or not item['prompt'].strip():
        raise BackgroundImageJobError('each job requires a prompt')
    if set(item) - BackgroundJobSpec.__dataclass_fields__.keys():
        raise BackgroundImageJobError('unknown job argument')
    refs = item.get('reference_image_urls')
    if refs is not None and (not isinstance(refs, list) or not all(isinstance(x, str) for x in refs)):
        raise BackgroundImageJobError('reference_image_urls must be a list of strings')
    for field, allowed in [('aspect_ratio', {'landscape', 'square', 'portrait'}),
                           ('quality', {'low', 'medium', 'high', 'auto'}),
                           ('input_fidelity', {'low', 'high'})]:
        if item.get(field) is not None and item[field] not in allowed:
            raise BackgroundImageJobError(f'invalid {field}')
    if item.get('mask_url') and not item.get('image_url'):
        raise BackgroundImageJobError('mask_url requires image_url')
    return BackgroundJobSpec(**item)


def format_completion_message(job_id, result):
    return f"Image job {job_id} completed\nMEDIA:{result['image']}"


def format_failure_message(job_id, error, error_type=None):
    detail = f' [{error_type}]' if error_type else ''
    return f'Image job {job_id} failed{detail}: {error}'


class BackgroundImageJobRunner:
    def __init__(self, ctx):
        self.ctx = ctx
        self._lock = threading.Lock()
        self._loop = None
        self._thread = None
        self._closed = False
        self._limit = _env_int('STEROIDS_IMAGE_BG_MAX_CONCURRENT', 2, 1, 16)
        ctx.on_unload(self.close)

    def _ensure_loop(self):
        with self._lock:
            if self._closed:
                raise BackgroundImageJobError('runner unloaded')
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                self._semaphore = asyncio.Semaphore(self._limit)
                self._thread = threading.Thread(target=self._loop.run_forever, daemon=True,
                                                name='steroids-image-jobs')
                self._thread.start()
            return self._loop

    def create_jobs(self, args, origin_session_key):
        if origin_session_key == '':
            raise BackgroundImageJobError('background delivery requires an originating session key')
        specs = normalize_jobs(args)
        mode = args.get('delivery_mode', 'each')
        if mode not in {'each', 'batch'}:
            raise BackgroundImageJobError('delivery_mode must be each or batch')
        loop = self._ensure_loop()
        paths = []
        for spec in specs:
            job_id = 'img_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_') + os.urandom(6).hex()
            path = jobs_root() / job_id
            _json_write(path / 'status.json', {'job_id': job_id, 'spec': asdict(spec),
                        'origin_session_key': origin_session_key, 'created_at': _now_iso(),
                        'status': 'queued', 'instance': _INSTANCE, 'delivery': {'status': 'pending'}})
            paths.append(path)
        # Scheduling and to_thread preserve the caller's profile/secret contextvars.
        future = asyncio.run_coroutine_threadsafe(self._schedule(paths, origin_session_key, mode), loop)
        future.result(timeout=10)
        return {'success': True, 'mode': 'async', 'count': len(paths),
                'jobs': [{'job_id': p.name, 'status': 'queued'} for p in paths]}

    async def _schedule(self, paths, key, mode):
        self.ctx.spawn_task(self._batch(paths, key, mode), name='steroids-image-batch')
        # Close our loop before the host disposes its task lease across threads.
        self.ctx.on_unload(self.close)

    async def _batch(self, paths, key, mode):
        try:
            results = await asyncio.gather(*(self._worker(p, key, mode) for p in paths))
            if mode == 'batch':
                self._notify(paths, key, '\n\n'.join(results))
        finally:
            for path in paths:
                state = _read_json(path / 'status.json')
                if state['status'] in {'queued', 'running'}:
                    state.update(status='cancelled', ended_at=_now_iso())
                    _json_write(path / 'status.json', state)

    async def _worker(self, path, key, mode):
        state = _read_json(path / 'status.json')
        try:
            async with self._semaphore:
                state.update(status='running', started_at=_now_iso())
                _json_write(path / 'status.json', state)
                result = await asyncio.to_thread(SteroidsOpenAIImageGenProvider().generate, **state['spec'])
            _json_write(path / 'result.json', result)
            state.update(status='completed' if result.get('success') else 'failed',
                         ended_at=_now_iso(), error=result.get('error'))
            message = (format_completion_message(path.name, result) if result.get('success')
                       else format_failure_message(path.name, result.get('error'), result.get('error_type')))
        except asyncio.CancelledError:
            state.update(status='cancelled', ended_at=_now_iso(),
                         error='Plugin unloaded; in-flight HTTP may finish but will not notify.')
            _json_write(path / 'status.json', state)
            raise
        except Exception as exc:
            state.update(status='failed', ended_at=_now_iso(), error=str(exc))
            message = format_failure_message(path.name, str(exc))
        _json_write(path / 'status.json', state)
        if mode == 'each':
            self._notify([path], key, message)
        return message

    def _notify(self, paths, key, message):
        error = None
        try:
            accepted = (self.ctx.inject_message(message, session_key=key) if key
                        else self.ctx.inject_message(message))
        except Exception as exc:
            accepted, error = False, str(exc)
        for path in paths:
            state = _read_json(path / 'status.json')
            state['delivery'] = {'status': 'accepted' if accepted else 'failed',
                                 'confirmed': False, 'error': error or (None if accepted else 'Host refused injection'),
                                 'updated_at': _now_iso()}
            _json_write(path / 'status.json', state)

    def close(self):
        with self._lock:
            self._closed = True
            loop, thread = self._loop, self._thread
        if loop is not None and loop.is_running():
            async def cancel():
                tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            asyncio.run_coroutine_threadsafe(cancel(), loop).result(timeout=10)
            loop.call_soon_threadsafe(loop.stop)
            if thread is not None:
                thread.join(timeout=10)
            loop.close()


def get_job_status(job_id):
    if not re.fullmatch(r'img_[0-9]{8}_[0-9]{6}_[0-9a-f]{6,12}', job_id):
        raise BackgroundImageJobError('invalid job_id')
    path = jobs_root() / job_id
    if not (path / 'status.json').is_file():
        raise BackgroundImageJobError(f'job not found: {job_id}')
    state = _read_json(path / 'status.json')
    if state.get('instance') != _INSTANCE and state['status'] in {'queued', 'running'}:
        state.update(status='interrupted', error='Runtime restarted; job is not automatically retried.')
    return {'success': True, 'job_id': job_id, 'status': state,
            'result': _read_json(path / 'result.json') if (path / 'result.json').exists() else None}
