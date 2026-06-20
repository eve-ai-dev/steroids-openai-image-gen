"""Hermes ImageGenProvider implementation."""
from __future__ import annotations

from typing import Any

try:
    from agent.image_gen_provider import (
        DEFAULT_ASPECT_RATIO,
        ImageGenProvider,
        error_response,
        resolve_aspect_ratio,
        save_b64_image,
        save_url_image,
        success_response,
    )
except Exception:  # pragma: no cover - allow unit tests to import helper functions only
    DEFAULT_ASPECT_RATIO = "square"

    class ImageGenProvider:  # type: ignore[no-redef]
        pass

    def error_response(**kwargs):
        return kwargs

    def resolve_aspect_ratio(value):
        return value or DEFAULT_ASPECT_RATIO

    def save_b64_image(b64, prefix):
        raise RuntimeError("save_b64_image unavailable")

    def save_url_image(url, prefix):
        raise RuntimeError("save_url_image unavailable")

    def success_response(**kwargs):
        return kwargs

from .codex_auth import CodexAuthClient
from .config import load_config
from .openai_compatible import OpenAICompatibleClient
from .refs import collect_sources

PROVIDER = "steroids-openai"


class SteroidsOpenAIImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return PROVIDER

    @property
    def display_name(self) -> str:
        return "Steroids OpenAI Image Gen"

    def is_available(self) -> bool:
        cfg = load_config()
        if cfg.mode == "openai-compatible":
            return OpenAICompatibleClient(cfg).available()
        if cfg.mode == "codex-auth":
            return CodexAuthClient(cfg).available()
        return False

    def list_models(self):
        return [
            {"id": "gpt-image-2", "display": "GPT Image 2", "speed": "~15-25s", "strengths": "Generation and edit/reference workflows"},
            {"id": "openai/gpt-image-2", "display": "OpenAI GPT Image 2", "speed": "~15-25s", "strengths": "Proxy alias"},
        ]

    def default_model(self):
        return "gpt-image-2"

    def get_setup_schema(self):
        return {
            "name": self.display_name,
            "badge": "custom",
            "tag": "OpenAI-compatible /v1/images plus direct Hermes Codex Auth mode",
            "env_vars": [],
        }

    def capabilities(self) -> dict[str, Any]:
        cfg = load_config()
        return {
            "modalities": ["text", "image"],
            "max_reference_images": cfg.max_reference_images,
            "supports_quality": True,
            "quality_values": ["low", "medium", "high", "auto"],
            "supports_input_fidelity": False,
            "mode": cfg.mode,
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: str | None = None,
        reference_image_urls=None,
        quality: str | None = None,
        input_fidelity: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        cfg = load_config()
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        selected_quality = (quality or cfg.quality or "medium").strip().lower()
        if selected_quality not in {"low", "medium", "high", "auto"}:
            selected_quality = cfg.quality
        size = cfg.sizes.get(aspect, cfg.sizes["square"])
        sources = collect_sources(image_url, reference_image_urls, max_refs=cfg.max_reference_images)

        if not prompt:
            return error_response(error="Prompt is required and must be a non-empty string", error_type="invalid_argument", provider=PROVIDER, model=cfg.model, aspect_ratio=aspect)

        try:
            if cfg.mode == "openai-compatible":
                client = OpenAICompatibleClient(cfg)
                if not client.available():
                    return error_response(error=f"OpenAI-compatible mode needs image_gen.steroids-openai.base_url and env {cfg.api_key_env}", error_type="auth_required", provider=PROVIDER, model=cfg.model, prompt=prompt, aspect_ratio=aspect)
                payload = client.edit(prompt=prompt, size=size, quality=selected_quality, sources=sources) if sources else client.generate(prompt=prompt, size=size, quality=selected_quality)
            elif cfg.mode == "codex-auth":
                client = CodexAuthClient(cfg)
                if not client.available():
                    return error_response(error="Codex Auth mode needs Hermes Codex/OpenAI auth token or configured token_env", error_type="auth_required", provider=PROVIDER, model=cfg.model, prompt=prompt, aspect_ratio=aspect)
                payload = client.generate(prompt=prompt, size=size, quality=selected_quality, sources=sources)
            else:
                return error_response(error=f"Unsupported mode: {cfg.mode}", error_type="invalid_config", provider=PROVIDER, model=cfg.model, prompt=prompt, aspect_ratio=aspect)
        except Exception as exc:
            return error_response(error=f"{cfg.mode} image generation failed: {exc}", error_type="api_error", provider=PROVIDER, model=cfg.model, prompt=prompt, aspect_ratio=aspect)

        try:
            image_ref, revised_prompt = _save_payload_image(payload, prefix=f"steroids_openai_{cfg.mode.replace('-', '_')}")
        except Exception as exc:
            return error_response(error=f"Could not read/save image response: {exc}", error_type="empty_response", provider=PROVIDER, model=cfg.model, prompt=prompt, aspect_ratio=aspect)

        extra = {
            "size": size,
            "quality": selected_quality,
            "mode": cfg.mode,
            "modality": "image" if sources else "text",
        }
        if revised_prompt:
            extra["revised_prompt"] = revised_prompt
        return success_response(image=image_ref, model=cfg.model, prompt=prompt, aspect_ratio=aspect, provider=PROVIDER, extra=extra)


def _save_payload_image(payload: dict[str, Any], *, prefix: str) -> tuple[str, str | None]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        raise ValueError("response has no data array")
    first = data[0]
    if not isinstance(first, dict):
        raise ValueError("response data[0] is not an object")
    revised_prompt = first.get("revised_prompt") if isinstance(first.get("revised_prompt"), str) else None
    b64 = first.get("b64_json")
    if isinstance(b64, str) and b64:
        return str(save_b64_image(b64, prefix=prefix)), revised_prompt
    url = first.get("url")
    if isinstance(url, str) and url:
        try:
            return str(save_url_image(url, prefix=prefix)), revised_prompt
        except Exception:
            return url, revised_prompt
    raise ValueError("response contained neither b64_json nor url")
