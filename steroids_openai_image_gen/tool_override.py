"""Enhanced image_generate tool schema for refs and quality."""
from __future__ import annotations

import json
from typing import Any


def _schema() -> dict[str, Any]:
    return {
        "name": "image_generate",
        "description": (
            "Generate or edit images using the configured image backend. Supports text-to-image, "
            "image_url edits, reference_image_urls, and quality when the active provider supports them. "
            "Use image_url for the primary source image and reference_image_urls for extra visual refs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Detailed text prompt describing the desired image or edit."},
                "aspect_ratio": {"type": "string", "enum": ["landscape", "square", "portrait"], "default": "landscape"},
                "quality": {"type": "string", "enum": ["low", "medium", "high", "auto"], "description": "Optional quality/speed tier. Use medium by default, low for drafts, high for final assets."},
                "image_url": {"type": "string", "description": "Optional primary image to edit/use as source. Accepts local path, HTTPS URL, or data:image URL."},
                "reference_image_urls": {"type": "array", "items": {"type": "string"}, "description": "Optional extra reference images as local paths, HTTPS URLs, or data:image URLs."},
                "input_fidelity": {"type": "string", "enum": ["low", "high", "auto"], "description": "Optional; currently omitted/ignored for gpt-image-2 unless backend supports it."},
            },
            "required": ["prompt"],
        },
    }


def _handler(args=None, **kwargs) -> str:
    args = args if isinstance(args, dict) else {"prompt": str(args or "")}
    try:
        from .provider import SteroidsOpenAIImageGenProvider
        result = SteroidsOpenAIImageGenProvider().generate(**args)
    except Exception as exc:
        result = {"success": False, "image": None, "error": f"steroids image_generate error: {type(exc).__name__}: {exc}", "error_type": "provider_exception"}
    return json.dumps(result, ensure_ascii=False)


def register_image_generate_override(ctx) -> None:
    ctx.register_tool(
        name="image_generate",
        toolset="image_gen",
        schema=_schema(),
        handler=_handler,
        check_fn=lambda: True,
        requires_env=[],
        description="Generate/edit images with quality and references",
        emoji="🎨",
        override=True,
    )
