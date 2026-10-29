"""Current-Hermes recovery regressions; synthetic bytes and no external I/O."""
import base64
from pathlib import Path

import pytest

from steroids_openai_image_gen.refs import collect_sources, load_image_bytes
from steroids_openai_image_gen.config import SteroidsConfig
from steroids_openai_image_gen.openai_compatible import OpenAICompatibleClient
from tests.test_core import png_bytes, rgba_png_bytes


def test_reference_overflow_is_explicit_in_provider(monkeypatch):
    from steroids_openai_image_gen import provider as p
    monkeypatch.setattr(p, 'load_config', lambda: SteroidsConfig(max_reference_images=2))
    assert collect_sources('a', ['b'], max_refs=2) == ['a', 'b']
    result = p.SteroidsOpenAIImageGenProvider().generate('edit', image_url='a', reference_image_urls=['b', 'c'])
    assert result['error_type'] == 'invalid_argument'
    assert '3' in result['error'] and '2' in result['error']


def test_credential_file_rejected_before_read(tmp_path, monkeypatch):
    image = tmp_path / 'ordinary.png'
    image.write_bytes(png_bytes())
    assert load_image_bytes(str(image), max_bytes=1024)[0] == png_bytes()
    secret = tmp_path / '.env'
    secret.write_bytes(png_bytes())  # synthetic, never a credential
    open_file = Path.open
    def guarded_open(path, *args, **kwargs):
        assert path != secret, 'credential bytes were opened'
        return open_file(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded_open)
    with pytest.raises(ValueError, match='Access denied'):
        load_image_bytes(str(secret), max_bytes=1024)


def test_metadata_remote_reference_denied_before_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('unsafe URL reached network'))
    with pytest.raises(ValueError, match='SSRF'):
        load_image_bytes('http://169.254.169.254/latest/meta-data/', max_bytes=1024)


def test_base64_and_local_size_limits(tmp_path):
    data = png_bytes()
    uri = 'data:image/png;base64,' + base64.b64encode(data).decode()
    assert load_image_bytes(uri, max_bytes=len(data))[0] == data
    with pytest.raises(ValueError, match='max_image_bytes'):
        load_image_bytes(uri, max_bytes=len(data)-1)
    image = tmp_path / 'large.png'
    image.write_bytes(data)
    with pytest.raises(ValueError, match='max_image_bytes'):
        load_image_bytes(str(image), max_bytes=len(data)-1)


def test_safe_remote_redirect_and_stream_limit(monkeypatch):
    import httpx
    from tools import url_safety
    calls = []
    scenario = {'mode': 'ok'}
    def transport(request):
        calls.append(str(request.url))
        if scenario['mode'] == 'redirect':
            return httpx.Response(302, headers={'location': 'http://169.254.169.254/secret'})
        return httpx.Response(200, content=png_bytes(), headers={'content-type': 'image/png'})
    monkeypatch.setattr(url_safety, 'create_ssrf_safe_client',
                        lambda **kw: httpx.Client(transport=httpx.MockTransport(transport), **kw))
    # Mock only HTTP transport; native URL policy and plugin redirect hook stay real.
    url = 'https://93.184.216.34/image.png'
    assert load_image_bytes(url, max_bytes=1024)[0] == png_bytes()
    with pytest.raises(ValueError, match='max_image_bytes'):
        load_image_bytes(url, max_bytes=10)
    scenario['mode'] = 'redirect'
    with pytest.raises(ValueError, match='SSRF'):
        load_image_bytes(url, max_bytes=1024)
    assert calls == [url, url, url]  # unsafe redirect never requested


def test_generation_and_edit_payloads_no_response_format_no_retry(tmp_path, monkeypatch):
    calls = []
    class Response:
        status_code = 200
        def json(self):
            return {'data': [{'b64_json': 'synthetic'}]}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr('steroids_openai_image_gen.openai_compatible.requests.post', post)
    source, ref, mask = [tmp_path / name for name in ['source.png', 'ref.png', 'mask.png']]
    source.write_bytes(png_bytes()); ref.write_bytes(png_bytes()); mask.write_bytes(rgba_png_bytes())
    # This spelling is a fixture identifier, NOT a claimed live Codex model alias.
    cfg = SteroidsConfig(base_url='https://managed.invalid/v1', model='fixture-image-model')
    client = OpenAICompatibleClient(cfg)
    client.generate(prompt='draw', size='1536x1024', quality='high')
    client.edit(prompt='edit', size='1024x1536', quality='low', sources=[str(source), str(ref)], mask_url=str(mask), input_fidelity='high')
    assert len(calls) == 2
    for _, kw in calls:
        payload = kw.get('json', kw.get('data'))
        assert 'response_format' not in payload
        assert payload['model'] == 'fixture-image-model'
        assert kw['allow_redirects'] is False
    assert [k for k, _ in calls[1][1]['files']] == ['image', 'image[]', 'mask']
    assert calls[1][1]['data']['input_fidelity'] == 'high'
