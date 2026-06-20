"""Image reference loading and multipart helpers."""
from __future__ import annotations

import base64
import mimetypes
import os
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


def collect_sources(image_url: str | None, reference_image_urls, *, max_refs: int) -> list[str]:
    sources = []
    if isinstance(image_url, str) and image_url.strip():
        sources.append(image_url.strip())
    sources.extend(normalize_reference_images(reference_image_urls))
    return sources[:max_refs]
