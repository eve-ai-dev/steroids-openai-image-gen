"""Image reference loading and multipart helpers."""
from __future__ import annotations

import base64
import mimetypes
import os
import struct
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


_ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


def normalize_reference_images(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable):
        out = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out
    return []


def sniff_mime(data: bytes, fallback: str = "image/png") -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    return fallback


def _check_size(data: bytes, max_bytes: int) -> None:
    if len(data) > max_bytes:
        raise ValueError(f"image exceeds max_image_bytes ({max_bytes})")
    if not data:
        raise ValueError("image is empty")


def load_image_bytes(ref: str, *, max_bytes: int, allow_remote: bool = True) -> tuple[bytes, str, str]:
    ref = ref.strip()
    lower = ref.lower()
    if lower.startswith("data:"):
        header, _, b64 = ref.partition(",")
        if ";base64" not in header or not b64:
            raise ValueError("only base64 data: image URLs are supported")
        mime = header[5:].split(";", 1)[0] or "image/png"
        if len(b64) > 4 * ((max_bytes + 2) // 3):
            raise ValueError(f'image exceeds max_image_bytes ({max_bytes})')
        data = base64.b64decode(b64, validate=True)
        _check_size(data, max_bytes)
        mime = sniff_mime(data, mime)
        if mime not in _ALLOWED_MIME:
            raise ValueError(f"unsupported image MIME type: {mime}")
        return data, mime, "image.png"

    if lower.startswith(("http://", "https://")):
        if not allow_remote:
            raise ValueError("remote image URLs are disabled by config")
        data, content_type = _download_reference(ref, max_bytes)
        mime = sniff_mime(data, content_type)
        if mime not in _ALLOWED_MIME:
            raise ValueError(f"unsupported image MIME type: {mime}")
        name = os.path.basename(urlparse(ref).path) or "image.png"
        return data, mime, name

    from agent.file_safety import raise_if_read_blocked
    path = Path(ref).expanduser()
    raise_if_read_blocked(str(path))
    with path.open('rb') as source:
        data = source.read(max_bytes + 1)
    _check_size(data, max_bytes)
    mime = sniff_mime(data, mimetypes.guess_type(str(path))[0] or "image/png")
    if mime not in _ALLOWED_MIME:
        raise ValueError(f"unsupported image MIME type: {mime}")
    return data, mime, path.name or "image.png"


def _check_remote_url(url):
    from tools.url_safety import is_safe_url
    from tools.website_policy import check_website_access
    if not is_safe_url(url):
        raise ValueError('Image reference URL failed the SSRF safety check')
    if check_website_access(url):
        raise ValueError('Image reference URL blocked by website policy')


def _download_reference(url, max_bytes):
    from tools.url_safety import create_ssrf_safe_client, redirect_target_from_response
    _check_remote_url(url)
    def check_redirect(response):
        target = redirect_target_from_response(response)
        if target:
            _check_remote_url(target)
    with create_ssrf_safe_client(timeout=60, follow_redirects=True,
                                 event_hooks={'response': [check_redirect]}) as client:
        with client.stream('GET', url) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                if len(data) + len(chunk) > max_bytes:
                    raise ValueError(f'image exceeds max_image_bytes ({max_bytes})')
                data.extend(chunk)
            _check_size(data, max_bytes)
            content_type = (response.headers.get('content-type') or 'image/png').split(';', 1)[0]
            return bytes(data), content_type


def load_image_as_data_uri(ref: str, *, max_bytes: int, allow_remote: bool = True) -> str:
    data, mime, _ = load_image_bytes(ref, max_bytes=max_bytes, allow_remote=allow_remote)
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def png_edit_metadata(data: bytes) -> tuple[int, int, bool]:
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise ValueError("masked edits require PNG source and mask files")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    has_alpha = color_type in {4, 6}
    offset = 8
    while offset + 12 <= len(data):
        chunk_length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_end = offset + 12 + chunk_length
        if chunk_end > len(data):
            raise ValueError("masked edits require valid PNG source and mask files")
        chunk_type = data[offset + 4:offset + 8]
        if chunk_type == b"tRNS":
            has_alpha = True
        offset = chunk_end
        if chunk_type == b"IEND":
            break
    return width, height, has_alpha


def validate_edit_mask_bytes(source: bytes, mask: bytes) -> None:
    source_width, source_height, _ = png_edit_metadata(source)
    mask_width, mask_height, mask_has_alpha = png_edit_metadata(mask)
    if (source_width, source_height) != (mask_width, mask_height):
        raise ValueError(
            "mask dimensions must match the primary image "
            f"({mask_width}x{mask_height} != {source_width}x{source_height})"
        )
    if not mask_has_alpha:
        raise ValueError("mask PNG must include an alpha channel")


def collect_sources(image_url: str | None, reference_image_urls, *, max_refs: int) -> list[str]:
    sources = []
    if isinstance(image_url, str) and image_url.strip():
        sources.append(image_url.strip())
    sources.extend(normalize_reference_images(reference_image_urls))
    if len(sources) > max_refs:
        raise ValueError(f'{len(sources)} images exceed max_reference_images ({max_refs}); reduce references')
    return sources
