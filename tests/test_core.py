import base64
import queue
import struct
import sys
import types
import zlib

import pytest

from steroids_openai_image_gen.background import (
    BackgroundImageJobError,
    BackgroundImageJobRunner,
    format_completion_message,
    format_failure_message,
    make_completion_event,
    normalize_jobs,
)
from steroids_openai_image_gen.codex_auth import (
    CodexAuthClient,
    extract_image_b64,
    image_b64_dimensions,
    normalize_image_b64_to_size,
)
from steroids_openai_image_gen.config import SteroidsConfig
from steroids_openai_image_gen.provider import _save_payload_image
from steroids_openai_image_gen.openai_compatible import OpenAICompatibleAPIError, OpenAICompatibleClient
from steroids_openai_image_gen.refs import (
    collect_sources,
    load_image_as_data_uri,
    load_image_bytes,
    validate_edit_mask_bytes,
)


def png_bytes(width=2, height=1):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw_rows = []
    for _ in range(height):
        raw_rows.append(b'\x00' + bytes([255, 0, 0]) * width)
    raw = b''.join(raw_rows)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def rgba_png_bytes(width=2, height=1):
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes([0, 0, 0, 0]) * width for _ in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def test_collect_sources_caps_primary_plus_refs():
    assert collect_sources('a', ['b', 'c'], max_refs=2) == ['a', 'b']


def test_load_data_uri_roundtrip():
    data = png_bytes()
    uri = 'data:image/png;base64,' + base64.b64encode(data).decode()
    got, mime, name = load_image_bytes(uri, max_bytes=10000)
    assert got == data
    assert mime == 'image/png'
    assert name == 'image.png'
    assert load_image_as_data_uri(uri, max_bytes=10000).startswith('data:image/png;base64,')


def test_extract_image_b64_nested_prefers_nested():
    assert extract_image_b64({'foo': [{'type': 'image_generation_call', 'result': 'x' * 120}]}) == 'x' * 120


def test_normalize_image_b64_to_size_resizes_and_pads_png():
    source_b64 = base64.b64encode(png_bytes(width=3, height=5)).decode()

    normalized = normalize_image_b64_to_size(source_b64, (1024, 1536))

    assert normalized is not None
    assert image_b64_dimensions(normalized) == (1024, 1536)


def test_save_payload_image_b64(monkeypatch):
    import steroids_openai_image_gen.provider as p
    monkeypatch.setattr(p, 'save_b64_image', lambda b64, prefix: '/tmp/fake.png')
    image, revised = _save_payload_image({'data': [{'b64_json': 'abc', 'revised_prompt': 'rp'}]}, prefix='x')
    assert image == '/tmp/fake.png'
    assert revised == 'rp'


def test_config_defaults():
    cfg = SteroidsConfig()
    assert cfg.mode == 'openai-compatible'
    assert cfg.model == 'gpt-image-2'
    assert cfg.quality == 'medium'


def test_openai_compatible_error_preserves_backend_code_and_message():
    class Response:
        status_code = 400
        text = ''

        def json(self):
            return {
                'error': {
                    'message': 'backend says this size is unsupported',
                    'type': 'invalid_request_error',
                    'code': 'unsupported_image_size',
                }
            }

    with pytest.raises(OpenAICompatibleAPIError) as exc_info:
        OpenAICompatibleClient._json_or_raise(Response())

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == 'unsupported_image_size'
    assert exc_info.value.message == 'backend says this size is unsupported'


def test_openai_compatible_error_fills_empty_backend_message():
    class Response:
        status_code = 502
        text = ''

        def json(self):
            return {'error': {'message': '', 'type': 'server_error', 'code': 'codex_image_error'}}

    with pytest.raises(OpenAICompatibleAPIError) as exc_info:
        OpenAICompatibleClient._json_or_raise(Response())

    assert exc_info.value.error_code == 'codex_image_error'
    assert exc_info.value.message == 'OpenAI-compatible image backend returned codex_image_error without a message (HTTP 502)'


def test_openai_compatible_edit_sends_mask_and_input_fidelity(tmp_path, monkeypatch):
    source = tmp_path / 'source.png'
    mask = tmp_path / 'mask.png'
    source.write_bytes(png_bytes(2, 1))
    mask.write_bytes(rgba_png_bytes(2, 1))
    captured = {}

    class Response:
        status_code = 200
        text = ''

        def json(self):
            return {'data': [{'b64_json': 'abc'}]}

    def fake_post(url, **kwargs):
        captured.update({'url': url, **kwargs})
        return Response()

    monkeypatch.setattr('steroids_openai_image_gen.openai_compatible.requests.post', fake_post)
    client = OpenAICompatibleClient(SteroidsConfig(base_url='http://route.test/v1'))

    client.edit(
        prompt='repair only the transparent region',
        size='1024x1536',
        quality='high',
        sources=[str(source)],
        mask_url=str(mask),
        input_fidelity='high',
    )

    assert captured['url'].endswith('/images/edits')
    assert captured['data']['input_fidelity'] == 'high'
    assert [field for field, _value in captured['files']] == ['image', 'mask']
    assert captured['files'][1][1][1] == rgba_png_bytes(2, 1)


def test_edit_mask_validation_requires_matching_alpha_png():
    with pytest.raises(ValueError, match='dimensions must match'):
        validate_edit_mask_bytes(png_bytes(2, 1), rgba_png_bytes(1, 1))
    with pytest.raises(ValueError, match='alpha channel'):
        validate_edit_mask_bytes(png_bytes(2, 1), png_bytes(2, 1))


def test_codex_auth_payload_uses_minimal_builtin_tool_shape():
    body = CodexAuthClient(SteroidsConfig(mode='codex-auth'))._payload(
        prompt='draw a gate',
        size='1536x1024',
        quality='high',
        image_data_uris=[],
    )

    assert body['model'] == 'gpt-5.5'
    assert body['tool_choice'] == 'auto'
    assert body['tools'][0] == {'type': 'image_generation', 'output_format': 'png', 'size': '1536x1024'}
    prompt_text = body['input'][0]['content'][-1]['text']
    assert 'Size: 1536x1024' in prompt_text
    assert 'Quality: high' in prompt_text


def test_codex_auth_edit_payload_sets_action_and_fidelity():
    source = 'data:image/png;base64,c291cmNl'
    body = CodexAuthClient(SteroidsConfig(mode='codex-auth'))._payload(
        prompt='repair the grip',
        size='1024x1536',
        quality='high',
        image_data_uris=[source],
        input_fidelity='high',
    )

    assert body['input'][0]['content'][0] == {'type': 'input_image', 'image_url': source}
    assert body['tool_choice'] == 'required'
    assert body['tools'][0]['action'] == 'edit'
    assert body['tools'][0]['input_fidelity'] == 'high'


def test_provider_returns_structured_openai_compatible_errors(monkeypatch):
    import steroids_openai_image_gen.provider as p

    class Client:
        def __init__(self, cfg):
            pass

        def available(self):
            return True

        def generate(self, **kwargs):
            raise OpenAICompatibleAPIError(
                status_code=400,
                message='non-square size unsupported by backend',
                error_code='unsupported_image_size',
                payload={},
            )

    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(base_url='http://route.test/v1'))
    monkeypatch.setattr(p, 'OpenAICompatibleClient', Client)

    result = p.SteroidsOpenAIImageGenProvider().generate('draw a gate', aspect_ratio='landscape')

    assert result['error_type'] == 'unsupported_image_size'
    assert result['error'] == 'non-square size unsupported by backend'


def test_provider_forwards_mask_and_reports_image_modality(monkeypatch):
    import steroids_openai_image_gen.provider as p

    class Client:
        calls = []

        def __init__(self, cfg):
            pass

        def available(self):
            return True

        def edit(self, **kwargs):
            self.calls.append(kwargs)
            return {'data': [{'b64_json': 'abc'}]}

    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(base_url='http://route.test/v1'))
    monkeypatch.setattr(p, 'OpenAICompatibleClient', Client)
    monkeypatch.setattr(p, 'save_b64_image', lambda b64, prefix: '/tmp/fake.png')

    result = p.SteroidsOpenAIImageGenProvider().generate(
        'repair the grip',
        image_url='/tmp/source.png',
        mask_url='/tmp/mask.png',
        input_fidelity='high',
    )

    assert Client.calls[0]['mask_url'] == '/tmp/mask.png'
    assert Client.calls[0]['input_fidelity'] == 'high'
    assert result['modality'] == 'image'


def test_provider_returns_invalid_argument_for_bad_mask(monkeypatch):
    import steroids_openai_image_gen.provider as p

    class Client:
        def __init__(self, cfg):
            pass

        def available(self):
            return True

        def edit(self, **kwargs):
            raise ValueError("mask PNG must include an alpha channel")

    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(base_url='http://route.test/v1'))
    monkeypatch.setattr(p, 'OpenAICompatibleClient', Client)
    result = p.SteroidsOpenAIImageGenProvider().generate(
        'repair',
        image_url='/tmp/source.png',
        mask_url='/tmp/mask.png',
    )

    assert result['error_type'] == 'invalid_argument'
    assert result['error'] == 'mask PNG must include an alpha channel'


def test_provider_rejects_mask_without_primary_image(monkeypatch):
    import steroids_openai_image_gen.provider as p

    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(base_url='http://route.test/v1'))
    result = p.SteroidsOpenAIImageGenProvider().generate('repair', mask_url='/tmp/mask.png')

    assert result['error_type'] == 'invalid_argument'
    assert result['error'] == 'mask_url requires image_url'


def test_codex_auth_mode_allows_non_square_client_call(monkeypatch):
    import steroids_openai_image_gen.provider as p

    class Client:
        calls = []

        def __init__(self, cfg):
            pass

        def available(self):
            return True

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return {'data': [{'b64_json': 'abc', 'actual_size': '1254x1254'}]}

    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(mode='codex-auth'))
    monkeypatch.setattr(p, 'CodexAuthClient', Client)
    monkeypatch.setattr(p, 'save_b64_image', lambda b64, prefix: '/tmp/fake.png')

    result = p.SteroidsOpenAIImageGenProvider().generate('draw a gate', aspect_ratio='landscape')

    assert result['image'] == '/tmp/fake.png'
    assert result['actual_size'] == '1254x1254'
    assert Client.calls[0]['size'] == '1536x1024'


def test_format_failure_message_includes_error_type():
    assert format_failure_message('job1', 'failed upstream', 'codex_image_error') == 'Image job job1 failed [codex_image_error]: failed upstream'


def test_normalize_jobs_caps_and_single_prompt():
    jobs = normalize_jobs({
        'prompt': 'hello',
        'aspect_ratio': 'square',
        'image_url': '/tmp/source.png',
        'mask_url': '/tmp/mask.png',
        'input_fidelity': 'high',
    })
    assert len(jobs) == 1
    assert jobs[0].prompt == 'hello'
    assert jobs[0].aspect_ratio == 'square'
    assert jobs[0].image_url == '/tmp/source.png'
    assert jobs[0].mask_url == '/tmp/mask.png'
    assert jobs[0].input_fidelity == 'high'


def test_normalize_jobs_empty_list_uses_prompt_shortcut():
    jobs = normalize_jobs({'prompt': 'hello', 'jobs': [], 'aspect_ratio': 'square'})
    assert len(jobs) == 1
    assert jobs[0].prompt == 'hello'
    assert jobs[0].aspect_ratio == 'square'


def test_normalize_jobs_empty_list_requires_prompt():
    with pytest.raises(BackgroundImageJobError, match='prompt is required when jobs is omitted or empty'):
        normalize_jobs({'jobs': []})


def test_normalize_jobs_rejects_over_cap(monkeypatch):
    monkeypatch.setenv('STEROIDS_IMAGE_BG_MAX_JOBS', '1')
    with pytest.raises(BackgroundImageJobError):
        normalize_jobs({'jobs': [{'prompt': 'a'}, {'prompt': 'b'}]})


def test_background_runner_requires_session_key():
    runner = BackgroundImageJobRunner()
    with pytest.raises(BackgroundImageJobError):
        runner.create_jobs({'prompt': 'x'}, origin_session_key='')


def test_background_runner_create_jobs_writes_state(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    monkeypatch.setenv('STEROIDS_IMAGE_BG_MAX_JOBS', '2')
    monkeypatch.setenv('STEROIDS_IMAGE_BG_MAX_CONCURRENT', '1')
    runner = BackgroundImageJobRunner()
    result = runner.create_jobs({'prompt': 'x'}, origin_session_key='agent:main:discord:dm:1')
    assert result['success'] is True
    jobs_dir = tmp_path / 'steroids_openai_image_gen' / 'jobs'
    assert jobs_dir.exists()
    assert len(list(jobs_dir.iterdir())) == 1


def test_current_session_key_parser():
    from steroids_openai_image_gen.background import _parse_session_key
    assert _parse_session_key('agent:main:discord:dm:123') == {'platform': 'discord', 'chat_type': 'dm', 'chat_id': '123'}
    parsed = _parse_session_key('agent:main:telegram:thread:456:789')
    assert parsed is not None and parsed['thread_id'] == '789'


def test_completion_message_includes_media_tag():
    message = format_completion_message('img_1', {'success': True, 'image': '/tmp/out.png'})
    assert message == 'Image job img_1 completed\nMEDIA:/tmp/out.png'


def test_completion_event_uses_async_delegation_session_route():
    event = make_completion_event(
        'agent:main:telegram:thread:456:789',
        'img_1',
        'Image job img_1 completed\nMEDIA:/tmp/out.png',
    )
    assert event['type'] == 'async_delegation'
    assert event['delegation_id'] == 'image_gen_img_1'
    assert event['session_key'] == 'agent:main:telegram:thread:456:789'
    assert event['summary'].endswith('MEDIA:/tmp/out.png')
    assert event['status'] == 'completed'


def test_enqueue_delivery_records_queue_failure(tmp_path, monkeypatch):
    import steroids_openai_image_gen.background as bg

    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    monkeypatch.setattr(bg, 'enqueue_completion_event', lambda event: (False, 'no queue'))
    runner = BackgroundImageJobRunner()
    job_dir = tmp_path / 'steroids_openai_image_gen' / 'jobs' / 'img_1'
    status = {'job_id': 'img_1', 'status': 'completed', 'delivery': {'status': 'pending', 'error': None}}
    job_dir.mkdir(parents=True)
    (job_dir / 'status.json').write_text(__import__('json').dumps(status), encoding='utf-8')

    runner._deliver_result(job_dir, 'agent:main:discord:dm:123', 'img_1', {'success': True, 'image': '/tmp/out.png'})

    saved = __import__('json').loads((job_dir / 'status.json').read_text(encoding='utf-8'))
    event = __import__('json').loads((job_dir / 'delivery_event.json').read_text(encoding='utf-8'))
    assert saved['delivery']['status'] == 'failed'
    assert saved['delivery']['error'] == 'no queue'
    assert event['session_key'] == 'agent:main:discord:dm:123'


def test_enqueue_completion_uses_process_registry(monkeypatch):
    from steroids_openai_image_gen.background import enqueue_completion_event, make_completion_event

    q = queue.Queue()
    fake_registry = types.SimpleNamespace(completion_queue=q)
    monkeypatch.setitem(sys.modules, 'tools.process_registry', types.SimpleNamespace(process_registry=fake_registry))
    event = make_completion_event(
        'agent:main:discord:dm:123',
        'img_test',
        'Image job img_test completed\nMEDIA:/tmp/image.png',
    )

    ok, error = enqueue_completion_event(event)

    assert ok is True
    assert error is None
    evt = q.get_nowait()
    assert evt['type'] == 'async_delegation'
    assert evt['delegation_id'] == 'image_gen_img_test'
    assert evt['session_key'] == 'agent:main:discord:dm:123'
    assert 'MEDIA:/tmp/image.png' in evt['summary']


def test_make_completion_event_contains_failure_error():
    evt = make_completion_event(
        'agent:main:discord:dm:123',
        'img_bad',
        'Image job img_bad failed: nope',
        status='failed',
        error='nope',
    )

    assert evt['type'] == 'async_delegation'
    assert evt['status'] == 'failed'
    assert evt['error'] == 'nope'
    assert evt['exit_reason'] == 'failed'


def test_enqueue_completion_event_reports_missing_process_registry(monkeypatch):
    from steroids_openai_image_gen.background import enqueue_completion_event

    monkeypatch.delitem(sys.modules, 'tools.process_registry', raising=False)
    monkeypatch.setitem(sys.modules, 'tools', types.SimpleNamespace())

    ok, error = enqueue_completion_event(make_completion_event('', 'img_bad', 'x'))

    assert ok is False
    assert error and 'tools.process_registry unavailable' in error
