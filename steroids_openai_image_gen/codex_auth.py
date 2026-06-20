"""Direct Hermes Codex Auth image-generation client."""
from __future__ import annotations

import json
from typing import Any

import httpx

from .config import SteroidsConfig
from .refs import load_image_as_data_uri

_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
_CODEX_CHAT_MODEL = "gpt-5.1-codex"
_INSTRUCTIONS = "You must fulfill image requests by using the image_generation tool."


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
                    found = extract_image_b64(event)
                    if found:
                        image_b64 = found
                    prompt_found = extract_revised_prompt(event)
                    if prompt_found:
                        revised_prompt = prompt_found
        if not image_b64:
            raise RuntimeError("Codex response contained no image_generation result")
        item = {"b64_json": image_b64}
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
        })
        return headers

    def _payload(self, *, prompt: str, size: str, quality: str, image_data_uris: list[str]) -> dict[str, Any]:
        content = [{"type": "input_text", "text": prompt}]
        for uri in image_data_uris:
            content.append({"type": "input_image", "image_url": uri})
        tool: dict[str, Any] = {
            "type": "image_generation",
            "model": "gpt-image-2",
            "size": size,
            "quality": quality,
            "output_format": "png",
            "background": "opaque",
            "partial_images": 1,
        }
        if image_data_uris:
            tool["action"] = "edit"
        return {
            "model": _CODEX_CHAT_MODEL,
            "stream": True,
            "store": False,
            "instructions": _INSTRUCTIONS,
            "input": [{"role": "user", "content": content}],
            "tools": [tool],
            "tool_choice": {
                "type": "allowed_tools",
                "mode": "required",
                "tools": [{"type": "image_generation"}],
            },
        }


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
