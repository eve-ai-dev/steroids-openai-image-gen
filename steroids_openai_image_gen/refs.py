"""Image reference loading and multipart helpers."""
from __future__ import annotations

import base64
import mimetypes
import os
import struct
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests

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
        data = base64.b64decode(b64)
        _check_size(data, max_bytes)
        mime = sniff_mime(data, mime)
        if mime not in _ALLOWED_MIME:
            raise ValueError(f"unsupported image MIME type: {mime}")
        return data, mime, "image.png"

    if lower.startswith(("http://", "https://")):
        if not allow_remote:
            raise ValueError("remote image URLs are disabled by config")
        response = requests.get(ref, timeout=60)
        response.raise_for_status()
        data = response.content
        _check_size(data, max_bytes)
        mime = sniff_mime(data, (response.headers.get("content-type") or "image/png").split(";", 1)[0])
        if mime not in _ALLOWED_MIME:
            raise ValueError(f"unsupported image MIME type: {mime}")
        name = os.path.basename(urlparse(ref).path) or "image.png"
        return data, mime, name

    path = Path(ref).expanduser()
    data = path.read_bytes()
    _check_size(data, max_bytes)
    mime = sniff_mime(data, mimetypes.guess_type(str(path))[0] or "image/png")
    if mime not in _ALLOWED_MIME:
        raise ValueError(f"unsupported image MIME type: {mime}")
    return data, mime, path.name or "image.png"


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
    return sources[:max_refs]
