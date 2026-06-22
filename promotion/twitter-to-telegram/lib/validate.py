from __future__ import annotations

import importlib
import shutil

from lib.config import (
    AppConfig,
    SUPPORTED_SOURCES,
    all_referenced_classes,
    env_required,
    has_resource_posts,
)
from lib.resource import create_backend
from lib.resource.seed import load_csv_rows, validate_csv_sources


def _check_config_structure(cfg: AppConfig) -> list[str]:
    errors: list[str] = []
    raw = cfg.raw
    for key in ("downloads", "run_state", "resource", "channels"):
        if key not in raw:
            errors.append(f"Missing top-level config key: {key}")
    if "downloads" in raw and "dir" not in raw["downloads"]:
        errors.append("Missing downloads.dir")
    if "run_state" in raw and "path" not in raw["run_state"]:
        errors.append("Missing run_state.path")
    resource = raw.get("resource", {})
    if "type" not in resource:
        errors.append("Missing resource.type")
    rtype = resource.get("type")
    if rtype == "csvfile" and "url" not in resource:
        errors.append("Missing resource.url")
    return errors


def validate_all(cfg: AppConfig, env: dict[str, str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_check_config_structure(cfg))

    disabled = [k for k, ch in cfg.channels.items() if not ch.get("enabled", True)]
    for key in disabled:
        warnings.append(f"Channel {key} is disabled (skipped)")

    enabled = [k for k, ch in cfg.channels.items() if ch.get("enabled", True)]
    if not enabled:
        errors.append("No enabled channels in config")

    rtype = cfg.resource.get("type")
    if rtype != "csvfile":
        errors.append(f"Unsupported resource.type: {rtype!r}")
        return errors, warnings

    backend = None
    counts: dict[str, dict[str, int]] = {}
    try:
        backend = create_backend(cfg.resource, cfg.config_dir)
        if not hasattr(backend, "path") or not backend.path.exists():
            errors.append(f"Resource CSV not found: {backend.path}")
        else:
            backend.reload()

        schema_errors = backend.validate_schema()
        errors.extend(schema_errors)
        if not schema_errors:
            counts = backend.counts()

        if hasattr(backend, "path") and backend.path.exists():
            rows = load_csv_rows(backend.path)
            errors.extend(validate_csv_sources(rows))
    except Exception as e:
        errors.append(f"Resource backend: {e}")

    if backend and counts:
        refs = all_referenced_classes(cfg)
        store_classes = backend.classes_in_store()
        for cls in refs:
            if cls not in store_classes:
                warnings.append(f"Class {cls!r} referenced in posts but has no rows in resource store")

    if has_resource_posts(cfg):
        for field in ("auth_token_env", "ct0_env"):
            if field not in cfg.twitter:
                errors.append(f"Missing twitter.{field} in config")
            else:
                try:
                    env_required(cfg, env, cfg.twitter[field])
                except ValueError as e:
                    errors.append(str(e))

    from lib.promotion import _validate_post_entry

    for key in enabled:
        ch = cfg.channels[key]
        posts = ch.get("posts") or []
        if not posts:
            errors.append(f"Channel {key}: posts list is empty")

        tg = ch.get("telegram", {})
        for field in ("bot_token_env", "chat_id"):
            if field not in tg:
                errors.append(f"Channel {key}: missing telegram.{field}")

        bot_env = tg.get("bot_token_env")
        if bot_env:
            try:
                env_required(cfg, env, bot_env)
            except ValueError as e:
                errors.append(f"Channel {key}: {e}")

        for i, post in enumerate(posts):
            try:
                _validate_post_entry(post, i)
            except Exception as e:
                errors.append(f"Channel {key}: {e}")

            img = post.get("image")
            if img:
                p = cfg.resolve_path(str(img))
                if not p.exists():
                    errors.append(f"Channel {key} post {i}: image not found: {p}")

        need: dict[str, int] = {}
        for post in posts:
            rc = post.get("resource")
            if rc:
                need[str(rc)] = need.get(str(rc), 0) + 1
        for cls, n in need.items():
            pending = counts.get(cls, {}).get("pending", 0)
            if pending < n:
                warnings.append(
                    f"Channel {key}: class {cls!r} has {pending} available rows but {n} resource posts"
                )

    if not shutil.which("yt-dlp"):
        errors.append("yt-dlp not found on PATH")
    if not shutil.which("gallery-dl"):
        errors.append("gallery-dl not found on PATH (required for image tweets)")
    if not shutil.which("ffmpeg"):
        warnings.append("ffmpeg not found on PATH (required for video tweets)")

    try:
        importlib.import_module("pandas")
    except ImportError:
        errors.append("Python package not installed: pandas")

    return errors, warnings
