"""OpenAI-compatible /v1/images client."""
from __future__ import annotations

from typing import Any

import requests

from .config import SteroidsConfig
from .refs import load_image_bytes


class OpenAICompatibleAPIError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        error_code: str | None = None,
        payload: Any = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.payload = payload
        super().__init__(f"HTTP {status_code}: {message}")


class OpenAICompatibleClient:
    def __init__(self, config: SteroidsConfig):
        self.config = config

    def available(self) -> bool:
        return bool(self.config.base_url and self.config.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}", "Accept": "application/json"}

    def generate(self, *, prompt: str, size: str, quality: str) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "response_format": "b64_json",
        }
        response = requests.post(
            f"{self.config.base_url}/images/generations",
            json=payload,
            headers=self._headers(),
            timeout=self.config.timeout_seconds,
        )
        return self._json_or_raise(response)

    def edit(self, *, prompt: str, size: str, quality: str, sources: list[str]) -> dict[str, Any]:
        files = []
        opened = []
        try:
            for idx, ref in enumerate(sources):
                data, mime, name = load_image_bytes(
                    ref,
                    max_bytes=self.config.max_image_bytes,
                    allow_remote=self.config.allow_remote_images,
                )
                field = "image" if idx == 0 else "image[]"
                files.append((field, (name, data, mime)))
            data = {
                "model": self.config.model,
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "response_format": "b64_json",
            }
            response = requests.post(
                f"{self.config.base_url}/images/edits",
                data=data,
                files=files,
                headers=self._headers(),
                timeout=self.config.timeout_seconds,
            )
            return self._json_or_raise(response)
        finally:
            for fp in opened:
                try:
                    fp.close()
                except Exception:
                    pass

    @staticmethod
    def _json_or_raise(response) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:
            payload = {"raw": response.text[:1000]}
        if response.status_code >= 400:
            err = payload.get("error") if isinstance(payload, dict) else payload
            message = None
            error_code = None
            if isinstance(err, dict):
                raw_message = err.get("message")
                raw_code = err.get("code")
                message = raw_message if isinstance(raw_message, str) and raw_message.strip() else None
                error_code = raw_code if isinstance(raw_code, str) and raw_code.strip() else None
            if not message:
                raw = payload.get("raw") if isinstance(payload, dict) else None
                if isinstance(raw, str) and raw.strip():
                    message = raw.strip()[:1000]
                elif error_code:
                    message = f"OpenAI-compatible image backend returned {error_code} without a message (HTTP {response.status_code})"
                else:
                    message = f"OpenAI-compatible image backend returned HTTP {response.status_code} without a message"
            raise OpenAICompatibleAPIError(
                status_code=response.status_code,
                message=message,
                error_code=error_code,
                payload=payload,
            )
        if not isinstance(payload, dict):
            raise RuntimeError("API returned non-object JSON")
        return payload
