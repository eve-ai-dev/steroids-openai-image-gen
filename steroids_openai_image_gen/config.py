"""Configuration for steroids-openai-image-gen."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

VALID_MODES = {"openai-compatible", "codex-auth"}
VALID_QUALITIES = {"low", "medium", "high", "auto"}


@dataclass
class SteroidsConfig:
    mode: str = "openai-compatible"
    base_url: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    token_env: str = ""
    model: str = "gpt-image-2"
    quality: str = "medium"
    max_reference_images: int = 16
    timeout_seconds: int = 300
    max_image_bytes: int = 25 * 1024 * 1024
    allow_remote_images: bool = True
    sizes: dict[str, str] = field(default_factory=lambda: {
        "landscape": "1536x1024",
        "square": "1024x1024",
        "portrait": "1024x1536",
    })

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None

    @property
    def token(self) -> str | None:
        return os.environ.get(self.token_env) if self.token_env else None


def _load_image_gen_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception:
        return {}


def _coerce_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        out = int(_expand_env(value))
    except Exception:
        return default
    return max(minimum, out)


def _expand_env(value: Any) -> Any:
    """Expand ${VAR} config strings using the process env.

    Hermes core does not currently expand nested plugin config values before
    plugins read them, so the plugin handles the standard YAML ${ENV_VAR}
    pattern itself.
    """
    if not isinstance(value, str):
        return value
    def repl(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), match.group(0))
    return re.sub(r"\$\{([^}]+)\}", repl, value)


def _str(value: Any, default: str = "") -> str:
    value = _expand_env(value)
    if value is None:
        return default
    return str(value).strip()


def load_config() -> SteroidsConfig:
    image_cfg = _load_image_gen_config()
    sub = image_cfg.get("steroids-openai")
    if not isinstance(sub, dict):
        sub = image_cfg.get("steroids_openai")
    if not isinstance(sub, dict):
        sub = {}

    mode = _str(sub.get("mode"), "openai-compatible").lower()
    if mode not in VALID_MODES:
        mode = "openai-compatible"

    model = _str(sub.get("model") or image_cfg.get("model"), "gpt-image-2")
    # Proxy and Codex paths both expect API model + quality, not virtual tier ids.
    quality_from_model = None
    if model.endswith("-low"):
        model, quality_from_model = "gpt-image-2", "low"
    elif model.endswith("-medium"):
        model, quality_from_model = "gpt-image-2", "medium"
    elif model.endswith("-high"):
        model, quality_from_model = "gpt-image-2", "high"

    quality = _str(sub.get("quality") or quality_from_model, "medium").lower()
    if quality not in VALID_QUALITIES:
        quality = "medium"

    sizes = {
        "landscape": "1536x1024",
        "square": "1024x1024",
        "portrait": "1024x1536",
    }
    if isinstance(sub.get("sizes"), dict):
        for k in sizes:
            v = sub["sizes"].get(k)
            if isinstance(v, str) and v.strip():
                sizes[k] = _str(v)
    if isinstance(sub.get("size"), dict):
        for k in sizes:
            v = sub["size"].get(k)
            if isinstance(v, str) and v.strip():
                sizes[k] = _str(v)

    return SteroidsConfig(
        mode=mode,
        base_url=_str(sub.get("base_url")).rstrip("/"),
        api_key_env=_str(sub.get("api_key_env"), "OPENAI_API_KEY"),
        token_env=_str(sub.get("token_env")),
        model=model,
        quality=quality,
        max_reference_images=_coerce_int(sub.get("max_reference_images"), 16),
        timeout_seconds=_coerce_int(sub.get("timeout_seconds"), 300, minimum=10),
        max_image_bytes=_coerce_int(sub.get("max_image_bytes"), 25 * 1024 * 1024, minimum=1024),
        allow_remote_images=bool(sub.get("allow_remote_images", True)),
        sizes=sizes,
    )
