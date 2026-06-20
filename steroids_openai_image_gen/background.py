"""Background image job orchestration for steroids-openai-image-gen.

Usage: queue background generations, persist job state, and notify the source chat when ready.
Example: run_image_jobs([{"prompt": "robot cat", "aspect_ratio": "square"}], origin_session_key="agent:main:discord:dm:123")
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .provider import SteroidsOpenAIImageGenProvider
except Exception:  # pragma: no cover - direct import / test fallback
    SteroidsOpenAIImageGenProvider = None  # type: ignore[assignment]

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover - fallback for direct imports
    def get_hermes_home() -> str:
        return str(Path(os.getenv("HERMES_HOME", Path.home() / ".hermes")))


TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_MAX_JOBS = 4
DEFAULT_MAX_CONCURRENT = 2


class BackgroundImageJobError(Exception):
    """Expected background-image failure with a stable human-readable message."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except Exception as exc:
        raise BackgroundImageJobError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise BackgroundImageJobError(f"{name} must be between {minimum} and {maximum}")
    return value


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _text_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_session_key(session_key: str) -> dict[str, str] | None:
    parts = (session_key or "").split(":")
    if len(parts) < 5 or parts[0] != "agent" or parts[1] != "main":
        return None
    result = {"platform": parts[2], "chat_type": parts[3], "chat_id": parts[4]}
    if len(parts) > 5 and parts[3] in {"dm", "thread"}:
        result["thread_id"] = parts[5]
    return result


@dataclass
class BackgroundJobSpec:
    prompt: str
    aspect_ratio: str = "landscape"
    quality: str = "medium"
    image_url: str | None = None
    reference_image_urls: list[str] | None = None
    input_fidelity: str | None = None


def jobs_root() -> Path:
    return Path(get_hermes_home()) / "steroids_openai_image_gen" / "jobs"


def _job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = os.urandom(3).hex()
    return f"img_{stamp}_{suffix}"


def normalize_jobs(args: dict[str, Any]) -> list[BackgroundJobSpec]:
    jobs = args.get("jobs")
    if jobs is None:
        prompt = str(args.get("prompt") or "").strip()
        if not prompt:
            raise BackgroundImageJobError("prompt is required")
        jobs = [{
            "prompt": prompt,
            "aspect_ratio": args.get("aspect_ratio", "landscape"),
            "quality": args.get("quality", "medium"),
            "image_url": args.get("image_url"),
            "reference_image_urls": args.get("reference_image_urls"),
            "input_fidelity": args.get("input_fidelity"),
        }]
    if not isinstance(jobs, list) or not jobs:
        raise BackgroundImageJobError("jobs must be a non-empty list")
    max_jobs = _env_int("STEROIDS_IMAGE_BG_MAX_JOBS", DEFAULT_MAX_JOBS, 1, 32)
    if len(jobs) > max_jobs:
        raise BackgroundImageJobError(f"too many jobs: {len(jobs)} > {max_jobs}")
    normalized: list[BackgroundJobSpec] = []
    for item in jobs:
        if not isinstance(item, dict):
            raise BackgroundImageJobError("each job must be an object")
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            raise BackgroundImageJobError("each job requires a prompt")
        refs = item.get("reference_image_urls") or []
        if refs and not isinstance(refs, list):
            raise BackgroundImageJobError("reference_image_urls must be a list")
        normalized.append(
            BackgroundJobSpec(
                prompt=prompt,
                aspect_ratio=str(item.get("aspect_ratio") or "landscape"),
                quality=str(item.get("quality") or "medium"),
                image_url=item.get("image_url") or None,
                reference_image_urls=[str(x) for x in refs] if refs else None,
                input_fidelity=item.get("input_fidelity") or None,
            )
        )
    return normalized


class BackgroundImageJobRunner:
    def __init__(self) -> None:
        self._semaphore = threading.BoundedSemaphore(_env_int("STEROIDS_IMAGE_BG_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT, 1, 16))

    def create_jobs(self, args: dict[str, Any], origin_session_key: str) -> dict[str, Any]:
        if not origin_session_key:
            raise BackgroundImageJobError("background image delivery requires an originating session key")
        specs = normalize_jobs(args)
        created: list[dict[str, Any]] = []
        for spec in specs:
            job_id = _job_id()
            job_dir = jobs_root() / job_id
            request = {
                "job_id": job_id,
                "created_at": _now_iso(),
                "origin_session_key": origin_session_key,
                "spec": spec.__dict__,
            }
            status = {**request, "status": "queued", "started_at": None, "ended_at": None, "error": None}
            _json_write(job_dir / "request.json", request)
            _json_write(job_dir / "status.json", status)
            _text_write(job_dir / "stdout.txt", "")
            _text_write(job_dir / "stderr.txt", "")
            self._start_worker(job_dir)
            created.append({"job_id": job_id, "status": "queued"})
        return {"success": True, "mode": "async", "jobs": created, "count": len(created)}

    def _start_worker(self, job_dir: Path) -> None:
        t = threading.Thread(target=self._worker, args=(job_dir,), daemon=True)
        t.start()

    def _worker(self, job_dir: Path) -> None:
        with self._semaphore:
            request = _read_json(job_dir / "request.json")
            status = _read_json(job_dir / "status.json")
            spec = request["spec"]
            origin_session_key = request.get("origin_session_key", "")
            status.update({"status": "running", "started_at": _now_iso()})
            _json_write(job_dir / "status.json", status)
            try:
                if SteroidsOpenAIImageGenProvider is None:
                    raise BackgroundImageJobError("provider unavailable")
                provider = SteroidsOpenAIImageGenProvider()
                result = provider.generate(**spec)
                _json_write(job_dir / "result.json", result)
                status.update({"status": "completed" if result.get("success") else "failed", "ended_at": _now_iso(), "error": result.get("error")})
                _json_write(job_dir / "status.json", status)
                self._deliver_result(origin_session_key, request["job_id"], result)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                _text_write(job_dir / "stderr.txt", error)
                status.update({"status": "failed", "ended_at": _now_iso(), "error": error})
                _json_write(job_dir / "status.json", status)
                self._deliver_failure(origin_session_key, request["job_id"], error)

    def _deliver_result(self, origin_session_key: str, job_id: str, result: dict[str, Any]) -> None:
        text = f"Image job {job_id} completed"
        image_path = result.get("image") if isinstance(result, dict) else None
        if image_path:
            text += f"\nMEDIA:{image_path}"
        self._send_to_origin(origin_session_key, text)

    def _deliver_failure(self, origin_session_key: str, job_id: str, error: str) -> None:
        self._send_to_origin(origin_session_key, f"Image job {job_id} failed: {error}")

    def _send_to_origin(self, origin_session_key: str, text: str) -> None:
        parsed = _parse_session_key(origin_session_key)
        if not parsed:
            return
        try:
            from tools.send_message_tool import send_message
        except Exception:
            return
        platform = parsed["platform"]
        if platform == "telegram" and parsed.get("thread_id"):
            target = f"telegram:{parsed['chat_id']}:{parsed['thread_id']}"
        elif platform == "telegram":
            target = f"telegram:{parsed['chat_id']}"
        elif platform == "discord":
            target = f"discord:{parsed['chat_id']}"
        else:
            target = platform
        try:
            send_message(target, text)
        except Exception:
            pass


def get_job_status(job_id: str) -> dict[str, Any]:
    job_dir = jobs_root() / job_id
    status_path = job_dir / "status.json"
    result_path = job_dir / "result.json"
    if not status_path.exists():
        raise BackgroundImageJobError(f"job not found: {job_id}")
    status = _read_json(status_path)
    result = _read_json(result_path) if result_path.exists() else None
    return {"success": True, "job_id": job_id, "status": status, "result": result, "paths": {"job_dir": str(job_dir), "status": str(status_path), "result": str(result_path)}}
