"""Load config.json, .env, and resolve paths."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_CSV_COLUMNS = ("url", "date", "source", "class")
SUPPORTED_SOURCES = {"twitter"}
CAPTION_MAX_LEN = 1024


@dataclass
class AppConfig:
    raw: dict
    path: Path
    config_dir: Path

    @property
    def downloads_dir(self) -> Path:
        return self.resolve_path(self.raw["downloads"]["dir"])

    @property
    def keep_files(self) -> bool:
        return self.raw.get("downloads", {}).get("keep_files", True)

    @property
    def state_path(self) -> Path:
        return self.resolve_path(self.raw["run_state"]["path"])

    @property
    def resource(self) -> dict:
        return self.raw["resource"]

    @property
    def twitter(self) -> dict:
        return self.raw.get("twitter", {})

    @property
    def channels(self) -> dict:
        return self.raw.get("channels", {})

    def resolve_path(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        return (self.config_dir / p).resolve()

    def resolve_file_url(self, file_url: str) -> Path:
        if not file_url.startswith("file://"):
            p = Path(file_url)
            if not p.is_absolute():
                p = self.config_dir / p
            return p.resolve()

        rest = file_url[len("file://") :]
        if rest.startswith("/"):
            # file:///absolute/path (three slashes)
            if os.name == "nt" and len(rest) > 3 and rest[1].isalpha() and rest[2] == ":":
                p = Path(rest[1:])  # /C:/Users/...
            else:
                p = Path(rest)
        else:
            # file://relative/path — no leading slash after scheme
            p = Path(rest)

        if not p.is_absolute():
            p = self.config_dir / p
        return p.resolve()


def load_env(env_path: Path | None = None) -> dict[str, str]:
    if env_path is None:
        env_path = Path(".env")
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
    return env


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(raw=raw, path=path, config_dir=path.parent)


def env_required(cfg: AppConfig, env: dict[str, str], name: str) -> str:
    val = env.get(name) or os.environ.get(name)
    if not val:
        raise ValueError(f"Missing environment variable: {name}")
    return val


def channel_resource_classes(channel: dict) -> list[str]:
    classes = []
    for post in channel.get("posts", []):
        rc = post.get("resource")
        if rc:
            classes.append(str(rc))
    return classes


def has_resource_posts(cfg: AppConfig) -> bool:
    for ch in cfg.channels.values():
        if not ch.get("enabled", True):
            continue
        for post in ch.get("posts", []):
            if post.get("resource"):
                return True
    return False


def all_referenced_classes(cfg: AppConfig) -> set[str]:
    classes: set[str] = set()
    for key, ch in cfg.channels.items():
        if not ch.get("enabled", True):
            continue
        for post in ch.get("posts", []):
            rc = post.get("resource")
            if rc:
                classes.add(str(rc))
    return classes


def parse_tweet_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def render_caption(template: str, ctx: dict[str, str]) -> str:
    out = template
    for key, val in ctx.items():
        out = out.replace("{" + key + "}", val)
    return out
