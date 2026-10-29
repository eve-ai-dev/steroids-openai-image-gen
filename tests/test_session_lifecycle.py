"""Review regressions: real routing policy, private status and deterministic shutdown."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

from tests.test_public_boundaries import context, wait_for_status, OWNER
from steroids_openai_image_gen import register
from steroids_openai_image_gen import background as bg
from gateway.session_context import set_session_vars, clear_session_vars


@pytest.mark.parametrize('platform', ['discord', 'local'])
@pytest.mark.parametrize('mode', ['each', 'batch'])
def test_registered_tool_uses_real_keyed_policy(context, monkeypatch, platform, mode):
    from gateway.config import Platform
    from gateway.run_inbound import GatewayInboundMixin
    from gateway.session import SessionSource
    ctx, manager = context
    source = SessionSource(platform=Platform(platform), chat_id='synthetic-chat')
    entry = SimpleNamespace(origin=source, session_id=OWNER.session_id)
    seen = []
    delivered = threading.Event()
    async def lookup(key):
        return entry if key == OWNER.session_key else None
    async def receive(event):
        seen.append(event)
        delivered.set()
    class RoutingPolicy(GatewayInboundMixin):
        _running = True
        async_session_store = SimpleNamespace(lookup_by_session_key=lookup)
        def _restored_source(self, value):
            return value.origin
        def _is_user_authorized_for_source(self, value, **kwargs):
            return value.chat_id == 'synthetic-chat'
        def _delivery_adapter_for(self, value):
            return SimpleNamespace(handle_message=receive)
    policy = RoutingPolicy()
    policy._background_tasks = set()
    def inject(**kw):
        policy._gateway_loop = asyncio.get_running_loop()
        return policy._schedule_plugin_message_injection(**kw)
    manager.set_gateway_message_injector(object(), inject)
    monkeypatch.setattr(ctx, '_gateway_injection_allowed', lambda: True)
    monkeypatch.setattr(bg, 'SteroidsOpenAIImageGenProvider', lambda: SimpleNamespace(
        generate=lambda **kw: {'success': True, 'image': '/synthetic.png'}))
    register(ctx)
    tokens = set_session_vars(platform=platform, session_key=OWNER.session_key, session_id=OWNER.session_id)
    try:
        result = json.loads(ctx.dispatch_tool('steroids_image_generate_background', {'prompt': 'private synthetic prompt', 'delivery_mode': mode}))
        assert result['success']
        jid = result['jobs'][0]['job_id']
        state = wait_for_status(jid, lambda s: s['status']['delivery']['status'] != 'pending')
        assert state['status']['delivery']['status'] == 'accepted'
        assert state['status']['owner'] == {'session_key': OWNER.session_key, 'session_id': OWNER.session_id}
        assert delivered.wait(3)
        assert seen[0].source.chat_id == 'synthetic-chat'
        assert seen[0].metadata['gateway_session_key'] == OWNER.session_key
        assert seen[0].metadata['gateway_session_id'] == OWNER.session_id
        assert seen[0].metadata['gateway_session_strict'] is True
        allowed = json.loads(ctx.dispatch_tool('steroids_image_generate_background_status', {'job_id': jid}))
        assert allowed['status']['spec']['prompt'] == 'private synthetic prompt'
        clear_session_vars(tokens)
        tokens = set_session_vars(platform=platform, session_key='other-session', session_id='other-id')
        denied = json.loads(ctx.dispatch_tool('steroids_image_generate_background_status', {'job_id': jid}))
        assert not denied['success'] and 'private synthetic prompt' not in json.dumps(denied)
        clear_session_vars(tokens)
        tokens = set_session_vars(platform=platform, session_key=OWNER.session_key, session_id='replacement-id')
        assert not json.loads(ctx.dispatch_tool('steroids_image_generate_background_status', {'job_id': jid}))['success']
    finally:
        clear_session_vars(tokens)
        manager.unload(ctx.manifest)


def test_ownerless_legacy_and_missing_context_fail_closed(context):
    ctx, manager = context
    path = bg.jobs_root() / 'img_20260101_010101_abcdef'
    path.mkdir(parents=True)
    (path / 'status.json').write_text(json.dumps({'status': 'completed', 'spec': {'prompt': 'legacy secret'}}))
    with pytest.raises(bg.BackgroundImageJobError, match='not owned'):
        bg.get_job_status(path.name, OWNER)
    register(ctx)
    tokens = set_session_vars(platform='discord', session_key='', session_id='')
    try:
        result = json.loads(ctx.dispatch_tool('steroids_image_generate_background', {'prompt': 'x'}))
        assert not result['success']
        assert len(list(bg.jobs_root().glob('*/status.json'))) == 1
    finally:
        clear_session_vars(tokens)
        manager.unload(ctx.manifest)


def test_demonstrated_close_after_loop_acquisition(context, monkeypatch):
    ctx, manager = context
    runner = bg.BackgroundImageJobRunner(ctx)
    original = runner._ensure_loop
    def stopped_loop():
        loop = original()
        runner.close()
        return loop
    monkeypatch.setattr(runner, '_ensure_loop', stopped_loop)
    with pytest.raises(bg.BackgroundImageJobError, match='unloaded'):
        runner.create_jobs({'prompt': 'race'}, OWNER)
    assert not list(bg.jobs_root().glob('*/status.json'))
    runner.close()


@pytest.mark.parametrize('boundary', ['enqueue', 'spawn'])
def test_schedule_failure_returns_terminal_ids_without_coroutine_leak(context, monkeypatch, boundary):
    ctx, manager = context
    runner = bg.BackgroundImageJobRunner(ctx)
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic scheduling rejection')
    target = bg.asyncio if boundary == 'enqueue' else ctx
    monkeypatch.setattr(target, 'run_coroutine_threadsafe' if boundary == 'enqueue' else 'spawn_task', fail)
    result = runner.create_jobs({'jobs': [{'prompt': 'a'}, {'prompt': 'b'}]}, OWNER)
    assert not result['success'] and len(result['jobs']) == 2
    for job in result['jobs']:
        assert bg.get_job_status(job['job_id'], OWNER)['status']['status'] == 'failed'
    monkeypatch.undo()
    runner.close()


def test_concurrent_close_waits_for_admission_then_cancels_all(context, monkeypatch):
    ctx, manager = context
    monkeypatch.setenv('STEROIDS_IMAGE_BG_MAX_CONCURRENT', '1')
    runner = bg.BackgroundImageJobRunner(ctx)
    acquired, release, closing = threading.Event(), threading.Event(), threading.Event()
    original = runner._ensure_loop
    def paused_loop():
        loop = original()
        acquired.set()
        assert release.wait(3)
        return loop
    monkeypatch.setattr(runner, '_ensure_loop', paused_loop)
    backend_release = threading.Event()
    monkeypatch.setattr(bg, 'SteroidsOpenAIImageGenProvider', lambda: SimpleNamespace(
        generate=lambda **kw: backend_release.wait(3) or {'success': False, 'error': 'x'}))
    results = []
    submit = threading.Thread(target=lambda: results.append(runner.create_jobs({'jobs': [{'prompt': 'a'}, {'prompt': 'b'}]}, OWNER)))
    def close():
        closing.set()
        runner.close()
    submit.start()
    assert acquired.wait(3)
    closers = [threading.Thread(target=close), threading.Thread(target=lambda: manager.unload(ctx.manifest))]
    for thread in closers:
        thread.start()
    assert closing.wait(3)
    release.set()
    submit.join(4)
    for thread in closers:
        thread.join(4)
    backend_release.set()
    assert not submit.is_alive() and all(not t.is_alive() for t in closers)
    assert results[0]['success']
    assert all(bg.get_job_status(j['job_id'], OWNER)['status']['status'] == 'cancelled' for j in results[0]['jobs'])
    with pytest.raises(bg.BackgroundImageJobError, match='unloaded'):
        runner.create_jobs({'prompt': 'too late'}, OWNER)
    manager.unload(ctx.manifest)
