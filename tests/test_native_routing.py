"""Real installed gateway dispatcher with an in-memory store and adapter."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from tests.test_public_boundaries import context, OWNER
from steroids_openai_image_gen import register
from steroids_openai_image_gen.background import jobs_root
from gateway.session_context import set_session_vars, clear_session_vars


def test_native_rotation_missing_route_and_current_authorization(context):
    from gateway.run_inbound import GatewayInboundMixin
    from gateway.config import Platform
    from gateway.session import SessionSource
    source = SessionSource(platform=Platform.DISCORD, chat_id='origin-chat', thread_id='origin-thread')
    current = SimpleNamespace(origin=source, session_id='replacement-id')
    seen, looked_up = [], []
    async def lookup(key):
        looked_up.append(key)
        return current if key == OWNER.session_key else None
    async def receive(event):
        seen.append(event)
    class Policy(GatewayInboundMixin):
        _running = True
        authorized = True
        async_session_store = SimpleNamespace(lookup_by_session_key=lookup)
        def _restored_source(self, entry):
            return entry.origin
        def _is_user_authorized_for_source(self, value, **kwargs):
            return self.authorized
        def _delivery_adapter_for(self, value):
            return SimpleNamespace(handle_message=receive)
    policy = Policy()
    def dispatch(key):
        return asyncio.run(policy._dispatch_plugin_message_injection(session_key=key, content='synthetic', plugin_id='steroids-openai-image-gen'))
    assert dispatch(OWNER.session_key)
    assert looked_up == [OWNER.session_key]
    assert seen[0].metadata['gateway_session_id'] == 'replacement-id'
    assert seen[0].metadata['gateway_session_strict'] is True
    assert seen[0].source.chat_id == 'origin-chat' and seen[0].source.thread_id == 'origin-thread'
    policy.authorized = False
    assert not dispatch(OWNER.session_key)
    assert not dispatch('foreign-key')
    assert len(seen) == 1


def test_stateless_admission_creates_no_jobs(context):
    ctx, manager = context
    register(ctx)
    tokens = set_session_vars(session_key=OWNER.session_key, session_id=OWNER.session_id, async_delivery=False)
    try:
        result = json.loads(ctx.dispatch_tool('steroids_image_generate_background', {'prompt': 'x'}))
        assert not result['success'] and 'stateless' in result['error']
        assert not list(jobs_root().glob('*/status.json'))
    finally:
        clear_session_vars(tokens)
        manager.unload(ctx.manifest)


def test_image_toolset_resolution_includes_namespaced_tools(context):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    from toolsets import resolve_toolset
    ctx, manager = context
    register(ctx)
    token = set_hermes_home_override(manager.home_path)
    try:
        resolved = resolve_toolset('image_gen')
        assert {'image_generate', 'steroids_image_generate', 'steroids_image_generate_background',
                'steroids_image_generate_background_status'} <= set(resolved)
        # Registration alone does not put image tools into the configured Discord pair.
        existing = set(resolve_toolset('connections')) | set(resolve_toolset('hermes-discord'))
        assert 'steroids_image_generate' not in existing
    finally:
        reset_hermes_home_override(token)
        manager.unload(ctx.manifest)
