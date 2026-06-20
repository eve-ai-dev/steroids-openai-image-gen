"""Enhanced image_generate tool schemas for refs, quality, and background jobs."""
from __future__ import annotations

import json
from typing import Any

from .background import BackgroundImageJobError, BackgroundImageJobRunner, get_job_status


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


def _background_schema() -> dict[str, Any]:
    return {
        "name": "image_generate_background",
        "description": (
            "Queue one or more image jobs and deliver the images back to the originating chat when ready. "
            "Use for batches or slow images. Prefer delivery_mode=each. Max batch size is 4 unless configured otherwise."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Single-image shortcut. Used when jobs is omitted."},
                "jobs": {
                    "type": "array",
                    "description": "Optional batch of image jobs. If provided, prompt/top-level params are ignored.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "aspect_ratio": {"type": "string", "enum": ["landscape", "square", "portrait"]},
                            "quality": {"type": "string", "enum": ["low", "medium", "high", "auto"]},
                            "image_url": {"type": "string"},
                            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
                            "input_fidelity": {"type": "string", "enum": ["low", "high", "auto"]},
                        },
                        "required": ["prompt"],
                        "additionalProperties": False,
                    },
                },
                "aspect_ratio": {"type": "string", "enum": ["landscape", "square", "portrait"], "default": "landscape"},
                "quality": {"type": "string", "enum": ["low", "medium", "high", "auto"], "default": "medium"},
                "image_url": {"type": "string"},
                "reference_image_urls": {"type": "array", "items": {"type": "string"}},
                "input_fidelity": {"type": "string", "enum": ["low", "high", "auto"]},
                "delivery_mode": {"type": "string", "enum": ["each", "batch"], "default": "each"},
            },
            "required": [],
            "additionalProperties": False,
        },
    }


def _status_schema() -> dict[str, Any]:
    return {
        "name": "image_generate_background_status",
        "description": "Read the current status of a background image job by job_id.",
        "parameters": {
            "type": "object",
            "properties": {"job_id": {"type": "string", "description": "Background job id, e.g. img_20260620_155555_ab12cd."}},
            "required": ["job_id"],
            "additionalProperties": False,
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


def _current_session_key() -> str:
    try:
        from tools.approval import get_current_session_key
        key = get_current_session_key(default="")
        return key if key != "default" else ""
    except Exception:
        return ""


def _background_handler(args=None, **kwargs) -> str:
    payload = args if isinstance(args, dict) else {}
    payload = {**kwargs, **payload}
    try:
        runner = BackgroundImageJobRunner()
        result = runner.create_jobs(payload, origin_session_key=_current_session_key())
    except BackgroundImageJobError as exc:
        result = {"success": False, "status": "failed", "error": str(exc)}
    except Exception as exc:
        result = {"success": False, "status": "failed", "error": f"image_generate_background internal error: {type(exc).__name__}: {exc}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


def _status_handler(args=None, **kwargs) -> str:
    payload = args if isinstance(args, dict) else {}
    payload = {**payload, **kwargs}
    try:
        result = get_job_status(str(payload.get("job_id") or ""))
    except BackgroundImageJobError as exc:
        result = {"success": False, "status": "failed", "error": str(exc)}
    except Exception as exc:
        result = {"success": False, "status": "failed", "error": f"image_generate_background_status internal error: {type(exc).__name__}: {exc}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    ctx.register_tool(
        name="image_generate_background",
        toolset="image_gen",
        schema=_background_schema(),
        handler=_background_handler,
        check_fn=lambda: True,
        requires_env=[],
        description="Queue image jobs and deliver them back to chat when ready",
        emoji="🕒",
    )
    ctx.register_tool(
        name="image_generate_background_status",
        toolset="image_gen",
        schema=_status_schema(),
        handler=_status_handler,
        check_fn=lambda: True,
        requires_env=[],
        description="Read background image job status",
        emoji="📎",
    )
