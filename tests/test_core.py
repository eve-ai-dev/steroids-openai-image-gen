import base64
import struct
import zlib

from steroids_openai_image_gen.codex_auth import extract_image_b64
from steroids_openai_image_gen.config import SteroidsConfig
from steroids_openai_image_gen.provider import _save_payload_image
from steroids_openai_image_gen.refs import collect_sources, load_image_as_data_uri, load_image_bytes


def png_bytes():
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b'\x00' + bytes([255, 0, 0]) * 2
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


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
