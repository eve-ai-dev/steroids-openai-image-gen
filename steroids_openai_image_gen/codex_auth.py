"""Direct Hermes Codex Auth image-generation client."""
from __future__ import annotations

import base64
import io
import json
import struct
from typing import Any

import httpx

from .config import SteroidsConfig
from .refs import load_image_as_data_uri

_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
_CODEX_CHAT_MODEL = "gpt-5.5"
_INSTRUCTIONS = "You are an image generation assistant."


def read_codex_access_token(config: SteroidsConfig) -> str | None:
    if config.token:
        return config.token.strip()
    try:
        from agent.auxiliary_client import _read_codex_access_token
        token = _read_codex_access_token()
        if isinstance(token, str) and token.strip():
            return token.strip()
    except Exception:
        return None
    return None


class CodexAuthClient:
    def __init__(self, config: SteroidsConfig):
        self.config = config

    def available(self) -> bool:
        return bool(read_codex_access_token(self.config))

    def generate(self, *, prompt: str, size: str, quality: str, sources: list[str] | None = None) -> dict[str, Any]:
        token = read_codex_access_token(self.config)
        if not token:
            raise RuntimeError("No Codex Auth token available. Run Hermes Codex/OpenAI auth setup first.")
        image_data_uris = [
            load_image_as_data_uri(
                ref,
                max_bytes=self.config.max_image_bytes,
                allow_remote=self.config.allow_remote_images,
            )
            for ref in (sources or [])
        ]
        payload = self._payload(prompt=prompt, size=size, quality=quality, image_data_uris=image_data_uris)
        headers = self._headers(token)
        timeout = httpx.Timeout(float(self.config.timeout_seconds), connect=30.0, read=float(self.config.timeout_seconds), write=30.0, pool=30.0)
        image_b64 = None
        revised_prompt = None
        with httpx.Client(timeout=timeout, headers=headers) as client:
            with client.stream("POST", f"{_CODEX_BASE_URL}/responses", json=payload) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    exc.response.read()
                    raise RuntimeError(f"Codex Responses API HTTP {exc.response.status_code}: {exc.response.text[:800]}") from exc
                for event in iter_sse_json(response):
                    error = extract_error(event)
                    if error:
                        raise RuntimeError(error)
                    found = extract_image_b64(event)
                    if found:
                        image_b64 = found
                    prompt_found = extract_revised_prompt(event)
                    if prompt_found:
                        revised_prompt = prompt_found
        if not image_b64:
            raise RuntimeError("Codex response contained no image_generation result")
        requested = requested_image_size(size)
        actual = image_b64_dimensions(image_b64)
        normalized_from = None
        if requested and actual and requested != actual:
            normalized_b64 = normalize_image_b64_to_size(image_b64, requested)
            if normalized_b64:
                image_b64 = normalized_b64
                normalized_from = f"{actual[0]}x{actual[1]}"
            elif not same_image_aspect_ratio(requested, actual):
                raise RuntimeError(f"Codex image output size mismatch: requested {requested[0]}x{requested[1]}, got {actual[0]}x{actual[1]}")
        item = {"b64_json": image_b64}
        if normalized_from:
            assert requested is not None
            item["actual_size"] = normalized_from
            item["normalized_size"] = f"{requested[0]}x{requested[1]}"
        elif requested and actual and requested != actual:
            item["actual_size"] = f"{actual[0]}x{actual[1]}"
        if revised_prompt:
            item["revised_prompt"] = revised_prompt
        return {"data": [item]}

    def _headers(self, token: str) -> dict[str, str]:
        try:
            from agent.auxiliary_client import _codex_cloudflare_headers
            headers = _codex_cloudflare_headers(token)
        except Exception:
            headers = {}
        headers.update({
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "responses=experimental",
            "User-Agent": "codex_cli_rs/0.130.0 (steroids-openai-image-gen)",
        })
        return headers

    def _payload(self, *, prompt: str, size: str, quality: str, image_data_uris: list[str]) -> dict[str, Any]:
        user_text = self._user_text(prompt=prompt, size=size, quality=quality, image_count=len(image_data_uris))
        content = []
        for uri in image_data_uris:
            content.append({"type": "input_image", "image_url": uri})
        content.append({"type": "input_text", "text": user_text})
        tool: dict[str, Any] = {"type": "image_generation", "output_format": "png"}
        if size and size != "auto":
            tool["size"] = size
        return {
            "model": _CODEX_CHAT_MODEL,
            "stream": True,
            "store": False,
            "instructions": _INSTRUCTIONS,
            "input": [{"type": "message", "role": "user", "content": content}],
            "tools": [tool],
            "tool_choice": "required" if image_data_uris else "auto",
            "parallel_tool_calls": False,
            "reasoning": {"effort": "low", "summary": "auto"},
            "include": ["reasoning.encrypted_content"],
            "text": {"verbosity": "low"},
        }

    def _user_text(self, *, prompt: str, size: str, quality: str, image_count: int) -> str:
        if image_count:
            text = (
                "Use the image_generation tool to edit the attached reference image(s). "
                f"Request: {prompt}. Output format: png."
            )
        else:
            text = (
                "Use the image_generation tool to render the following. "
                f"Request: {prompt}. Output format: png."
            )
        if size and size != "auto":
            text += f" Size: {size}."
        if quality:
            text += f" Quality: {quality}."
        text += " Do not include explanatory text; produce only the image."
        return text


def iter_sse_json(response: Any):
    event_name = None
    data_lines: list[str] = []

    def flush():
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = None
            return None
        raw = "\n".join(data_lines).strip()
        event = event_name
        event_name = None
        data_lines = []
        if not raw or raw == "[DONE]":
            return None
        payload = json.loads(raw)
        if isinstance(payload, dict) and event and "type" not in payload:
            payload["type"] = event
        return payload

    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        line = str(line)
        if line == "":
            payload = flush()
            if payload is not None:
                yield payload
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip())
    payload = flush()
    if payload is not None:
        yield payload


def extract_image_b64(value: Any) -> str | None:
    found = None
    if isinstance(value, dict):
        if value.get("type") == "image_generation_call" and isinstance(value.get("result"), str):
            found = value["result"]
        for key in ("partial_image_b64", "partial_image", "result"):
            val = value.get(key)
            if isinstance(val, str) and len(val) > 100:
                found = val
        for child in value.values():
            nested = extract_image_b64(child)
            if nested:
                found = nested
    elif isinstance(value, list):
        for child in value:
            nested = extract_image_b64(child)
            if nested:
                found = nested
    return found


def extract_error(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    raw_error = value.get("error")
    error = raw_error if isinstance(raw_error, dict) else value if value.get("type") == "error" else None
    if not isinstance(error, dict):
        return None
    message = error.get("message")
    code = error.get("code")
    if isinstance(message, str) and message.strip():
        return message.strip()
    if isinstance(code, str) and code.strip():
        return f"Codex image generation failed: {code.strip()}"
    return "Codex image generation failed"


def requested_image_size(size: str) -> tuple[int, int] | None:
    if not size or size == "auto" or "x" not in size:
        return None
    width, height = size.split("x", 1)
    try:
        return int(width), int(height)
    except Exception:
        return None


def image_b64_dimensions(value: str) -> tuple[int, int] | None:
    try:
        raw = base64.b64decode(value, validate=False)
    except Exception:
        return None
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        return struct.unpack(">II", raw[16:24])
    if raw.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(raw):
            while index < len(raw) and raw[index] == 0xFF:
                index += 1
            if index >= len(raw):
                return None
            marker = raw[index]
            index += 1
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(raw):
                return None
            segment_length = struct.unpack(">H", raw[index:index + 2])[0]
            if marker in {*range(0xC0, 0xC4), *range(0xC5, 0xC8), *range(0xC9, 0xCC), *range(0xCD, 0xD0)}:
                if index + 7 <= len(raw):
                    height, width = struct.unpack(">HH", raw[index + 3:index + 7])
                    return width, height
                return None
            index += segment_length
    return None


def normalize_image_b64_to_size(value: str, size: tuple[int, int]) -> str | None:
    """Resize/pad a backend image to the exact requested PNG size.

    Codex image generation often treats size as an orientation hint, not a hard
    pixel contract. Keep the full image visible and letterbox/pillarbox it so
    downstream Hermes tooling receives deterministic dimensions.
    """
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        raw = base64.b64decode(value, validate=False)
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            source = image.convert("RGBA")
    except Exception:
        return None
    target_w, target_h = size
    if target_w <= 0 or target_h <= 0 or source.width <= 0 or source.height <= 0:
        return None
    scale = min(target_w / source.width, target_h / source.height)
    resized_w = max(1, round(source.width * scale))
    resized_h = max(1, round(source.height * scale))
    resized = source.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    background.paste(resized, ((target_w - resized_w) // 2, (target_h - resized_h) // 2), resized)
    output = io.BytesIO()
    background.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def same_image_aspect_ratio(requested: tuple[int, int], actual: tuple[int, int]) -> bool:
    return requested[0] * actual[1] == requested[1] * actual[0]


def extract_revised_prompt(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("revised_prompt", "revisedPrompt"):
            val = value.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for child in value.values():
            found = extract_revised_prompt(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = extract_revised_prompt(child)
            if found:
                return found
    return None
