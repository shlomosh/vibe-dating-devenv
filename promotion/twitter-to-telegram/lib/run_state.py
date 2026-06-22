from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.durable_write import write_text_durable
from lib.log import log


STATE_VERSION = 5


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": STATE_VERSION, "channels": {}}
    log.info("state: reading %s", path)
    data = json.loads(path.read_text(encoding="utf-8"))
    log.info("state: read %s", path)
    return data


def save_state(path: Path, state: dict) -> None:
    log.info("state: writing %s", path)
    write_text_durable(path, json.dumps(state, indent=2))
    log.info("state: wrote %s", path)


def get_channel_state(state: dict, channel_key: str) -> dict:
    channels = state.setdefault("channels", {})
    return channels.setdefault(
        channel_key,
        {"post_message_ids": {}, "last_posted_at": None, "last_resources": []},
    )


def get_message_id(channel_state: dict, post_index: int) -> int | None:
    mid = channel_state.get("post_message_ids", {}).get(str(post_index))
    return int(mid) if mid is not None else None


def set_message_id(channel_state: dict, post_index: int, message_id: int) -> None:
    channel_state.setdefault("post_message_ids", {})[str(post_index)] = message_id


def clear_message_ids(channel_state: dict, indices: list[int] | None = None) -> None:
    pids = channel_state.setdefault("post_message_ids", {})
    if indices is None:
        channel_state["post_message_ids"] = {}
        return
    for i in indices:
        pids.pop(str(i), None)


def mark_run_complete(channel_state: dict, resources: list[dict[str, Any]]) -> None:
    channel_state["last_posted_at"] = datetime.now().isoformat(timespec="seconds")
    channel_state["last_resources"] = resources
