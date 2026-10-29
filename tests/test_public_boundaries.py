"""Public Hermes boundary tests: synthetic bytes, no paid requests or live messages."""
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest
from agent.secret_scope import set_secret_scope, reset_secret_scope, set_multiplex_context, reset_multiplex_context
from steroids_openai_image_gen import register
from steroids_openai_image_gen.background import BackgroundImageJobRunner, BackgroundImageJobError, get_job_status
from steroids_openai_image_gen.config import SteroidsConfig
from steroids_openai_image_gen.background import SessionOwner

OWNER = SessionOwner('synthetic-session', 'synthetic-id')


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    manager = PluginManager(scope_key=str(tmp_path))
    manifest = PluginManifest(name='steroids-openai-image-gen', version='0.2.0',
                              description='boundary probe', author='test', path=Path(__file__).parents[1])
    return PluginContext(manifest, manager), manager


def test_registration_preserves_builtin_and_provider(context):
    import tools.image_generation_tool  # real builtin registration, no generation
    from tools.registry import registry
    from agent.image_gen_registry import get_provider
    ctx, manager = context
    before = registry.get_entry('image_generate', scope=manager.scope_key)
    assert before is not None
    register(ctx)
    assert registry.get_entry('image_generate', scope=manager.scope_key) is before
    assert registry.get_entry('steroids_image_generate', scope=manager.scope_key).schema['parameters']['properties']['mask_url']
    assert get_provider('steroids-openai', scope=manager.scope_key) is not None
    manager.unload(ctx.manifest)
    assert registry.get_entry('steroids_image_generate', scope=manager.scope_key) is None
    assert registry.get_entry('image_generate', scope=manager.scope_key) is before


def test_scoped_secret_does_not_inherit_other_profile(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-wrong-profile')
    mode = set_multiplex_context(True)
    token = set_secret_scope({'OPENAI_API_KEY': 'synthetic-own-profile'})
    try:
        assert SteroidsConfig().api_key == 'synthetic-own-profile'
        reset_secret_scope(token)
        token = set_secret_scope({})
        assert SteroidsConfig().api_key is None
    finally:
        reset_secret_scope(token)
        reset_multiplex_context(mode)


def wait_for_status(job_id, predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = get_job_status(job_id, owner=OWNER)
        if predicate(state):
            return state
        time.sleep(.01)
    pytest.fail('job did not reach expected state')


@pytest.mark.parametrize('delivery_mode,accepted,expected_notifications', [('each', True, 2), ('batch', True, 1), ('each', False, 2)])
def test_public_spawn_and_injection_receipt(context, monkeypatch, delivery_mode, accepted, expected_notifications):
    ctx, manager = context
    notifications = []
    manager.set_gateway_message_injector(object(), lambda **kw: notifications.append(kw) or accepted)
    monkeypatch.setattr(ctx, '_gateway_injection_allowed', lambda: True)
    image = manager.home_path / 'synthetic.png'
    image.write_bytes(b'synthetic artifact, not generated media')
    monkeypatch.setattr('steroids_openai_image_gen.background.SteroidsOpenAIImageGenProvider',
                        lambda: SimpleNamespace(generate=lambda **kw: {'success': True, 'image': str(image)}))
    runner = BackgroundImageJobRunner(ctx)
    try:
        result = runner.create_jobs({'jobs': [{'prompt': 'a'}, {'prompt': 'b'}], 'delivery_mode': delivery_mode}, OWNER)
        states = [wait_for_status(j['job_id'], lambda s: s['status']['delivery']['status'] != 'pending') for j in result['jobs']]
        assert len(notifications) == expected_notifications
        assert all(n['session_key'] == 'synthetic-session' for n in notifications)
        assert all('MEDIA:' + str(image) in n['content'] for n in notifications)
        assert all(s['status']['delivery']['status'] == ('accepted' if accepted else 'failed') for s in states)
        assert all(s['status']['delivery']['confirmed'] is False for s in states)
    finally:
        runner.close()


def test_unload_cancels_without_notification(context, monkeypatch):
    ctx, manager = context
    started, release = threading.Event(), threading.Event()
    def generate(**kwargs):
        started.set()
        release.wait(5)
        return {'success': True, 'image': '/synthetic.png'}
    monkeypatch.setattr('steroids_openai_image_gen.background.SteroidsOpenAIImageGenProvider',
                        lambda: SimpleNamespace(generate=generate))
    runner = BackgroundImageJobRunner(ctx)
    try:
        with pytest.raises(BackgroundImageJobError):
            runner.create_jobs({'prompt': 'x'}, '')
        result = runner.create_jobs({'prompt': 'x'}, OWNER)
        assert started.wait(3)
        manager.unload(ctx.manifest)
        assert get_job_status(result['jobs'][0]['job_id'], OWNER)['status']['status'] == 'cancelled'
    finally:
        release.set()
        runner.close()


def test_legacy_codex_mode_unavailable_without_public_host_seam(monkeypatch):
    from steroids_openai_image_gen.codex_auth import CodexAuthClient
    from steroids_openai_image_gen import provider as p
    assert not CodexAuthClient(SteroidsConfig(mode='codex-auth')).available()
    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(mode='codex-auth'))
    result = p.SteroidsOpenAIImageGenProvider().generate('synthetic')
    assert result['error_type'] == 'auth_required'
    assert 'signed-in provider request support' in result['error']


def test_explicit_injection_carries_captured_session_after_return(context, monkeypatch):
    from gateway.session_context import set_session_vars, clear_session_vars
    ctx, manager = context
    received = []
    manager.set_gateway_message_injector(object(), lambda **kw: received.append(kw) or True)
    monkeypatch.setattr(ctx, '_gateway_injection_allowed', lambda: True)
    release = threading.Event()
    def generate(**kwargs):
        release.wait(3)
        return {'success': True, 'image': '/synthetic.png'}
    monkeypatch.setattr('steroids_openai_image_gen.background.SteroidsOpenAIImageGenProvider',
                        lambda: SimpleNamespace(generate=generate))
    runner = BackgroundImageJobRunner(ctx)
    try:
        tokens = set_session_vars(session_key=OWNER.session_key, session_id=OWNER.session_id)
        result = runner.create_jobs({'prompt': 'x'}, OWNER)
        clear_session_vars(tokens)
        tokens = set_session_vars(session_key='synthetic-other-B', session_id='id-B')
        release.set()
        state = wait_for_status(result['jobs'][0]['job_id'], lambda s: s['status']['delivery']['status'] == 'accepted')
        clear_session_vars(tokens)
        assert not received[0].get('keyless')
        assert received[0]['session_key'] == OWNER.session_key
        assert state['status']['delivery']['confirmed'] is False
    finally:
        release.set()
        runner.close()


def test_worker_preserves_profile_home_and_scoped_secret(context, monkeypatch):
    from hermes_constants import get_hermes_home, set_hermes_home_override, reset_hermes_home_override
    from agent.secret_scope import get_secret
    ctx, manager = context
    observed = []
    def generate(**kwargs):
        observed.append((get_hermes_home(), get_secret('OPENAI_API_KEY')))
        return {'success': True, 'image': '/synthetic.png'}
    monkeypatch.setattr('steroids_openai_image_gen.background.SteroidsOpenAIImageGenProvider',
                        lambda: SimpleNamespace(generate=generate))
    runner = BackgroundImageJobRunner(ctx)
    home = set_hermes_home_override(manager.home_path)
    mode = set_multiplex_context(True)
    secret = set_secret_scope({'OPENAI_API_KEY': 'synthetic-origin-key'}, profile_home=str(manager.home_path))
    try:
        result = runner.create_jobs({'prompt': 'x'}, OWNER)
        reset_secret_scope(secret)
        secret = set_secret_scope({'OPENAI_API_KEY': 'synthetic-other-key'})
        wait_for_status(result['jobs'][0]['job_id'], lambda s: s['status']['delivery']['status'] != 'pending')
        assert observed == [(manager.home_path, 'synthetic-origin-key')]
    finally:
        reset_secret_scope(secret)
        reset_multiplex_context(mode)
        reset_hermes_home_override(home)
        runner.close()


def test_restart_marks_unfinished_job_interrupted(context):
    ctx, manager = context
    path = manager.home_path / 'steroids_openai_image_gen/jobs/img_20260101_010101_abcdef'
    path.mkdir(parents=True)
    (path / 'status.json').write_text(json.dumps({'status': 'running', 'instance': 'old-process', 'owner': {'session_key': OWNER.session_key, 'session_id': OWNER.session_id}}))
    assert get_job_status(path.name, OWNER)['status']['status'] == 'interrupted'
    with pytest.raises(BackgroundImageJobError, match='invalid job_id'):
        get_job_status('../../config.yaml', OWNER)


def test_public_injection_without_host_is_not_delivery(context):
    ctx, manager = context
    assert ctx.inject_message('synthetic notification') is False


@pytest.mark.parametrize('change', [{'quality': 'wrong'}, {'aspect_ratio': 'wide'}, {'input_fidelity': 'wrong'}, {'mask_url': 'x'}, {'reference_image_urls': 'x'}])
def test_invalid_controls_rejected_before_backend(change):
    from steroids_openai_image_gen.provider import SteroidsOpenAIImageGenProvider
    result = SteroidsOpenAIImageGenProvider().generate('valid prompt', **change)
    assert result['error_type'] == 'invalid_argument'
