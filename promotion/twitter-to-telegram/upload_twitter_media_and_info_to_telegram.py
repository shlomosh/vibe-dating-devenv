#!/usr/bin/env python3
"""Upload media described by a download_twitter_media_and_info.py JSON file to a
Telegram channel, captioned with the poster's profile.

Takes the JSON produced by download_twitter_media_and_info.py plus a channel id,
and sends the media (video/image) to the channel via the Telegram Bot API with a
caption formatted as:

    <b>{name}</b>
    {profile_link}
    {bio_link_1}
    {bio_link_2}
    ...

The name is rendered bold (Telegram HTML parse mode) and the bare URLs are
auto-linked by Telegram. The bot must be an admin of the target channel.

Credentials: reads TELEGRAM_BOT_TOKEN from .env (or the environment).

Usage:
  python upload_twitter_media_and_info_to_telegram.py <info.json> --channel <chat_id> [--silent]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import telegram  # noqa: E402
from lib.config import load_env  # noqa: E402
from lib.log import log, setup_logging  # noqa: E402

CAPTION_MAX_LEN = 1024  # Telegram media caption limit


def build_env() -> dict[str, str]:
    merged = load_env(ROOT / ".env")
    merged.update(os.environ)
    return merged


def env_required(env: dict[str, str], name: str) -> str:
    val = env.get(name)
    if not val:
        raise SystemExit(f"Missing required environment variable: {name} (set it in .env)")
    return val


def build_caption(profile: dict) -> str:
    """Format the profile as an HTML caption: bold name, profile link, bio links."""
    name = (profile.get("name") or "").strip()
    profile_link = (profile.get("profile_link") or "").strip()
    bio_links = profile.get("bio_links") or []

    lines: list[str] = []
    if name:
        lines.append(f"<b>{html.escape(name)}</b>")
    if profile_link:
        lines.append(html.escape(profile_link))
    for link in bio_links:
        link = (link or "").strip()
        if link:
            lines.append(html.escape(link))

    caption = "\n".join(lines)
    if len(caption) > CAPTION_MAX_LEN:
        caption = caption[:CAPTION_MAX_LEN]
    return caption


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("info_json", help="Path to the JSON from download_twitter_media_and_info.py")
    parser.add_argument("--channel", default="-1004454678300", help="Destination channel id (e.g. -1004454678300)")
    parser.add_argument("--silent", action="store_true", help="Send without a notification")
    args = parser.parse_args(argv)

    info_path = Path(args.info_json).resolve()
    if not info_path.exists():
        print(f"❌ Info JSON not found: {info_path}", file=sys.stderr)
        return 1
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ Could not parse info JSON: {e}", file=sys.stderr)
        return 1

    media_path = Path(info.get("media_path", ""))
    if not media_path.is_absolute():
        # Resolve relative media paths against the JSON file's directory.
        media_path = (info_path.parent / media_path).resolve()
    if not media_path.exists():
        print(f"❌ Media file not found: {media_path}", file=sys.stderr)
        return 1

    caption = build_caption(info.get("profile") or {})
    env = build_env()
    token = env_required(env, "TELEGRAM_BOT_TOKEN")

    try:
        chat_id = int(args.channel)
    except ValueError:
        chat_id = args.channel  # allow @username

    try:
        message_id = telegram.send_media_file(
            token,
            chat_id,
            media_path,
            caption=caption,
            silent=args.silent,
            parse_mode="HTML",
        )
    except telegram.TelegramError as e:
        print(f"❌ Telegram upload failed: {e}", file=sys.stderr)
        return 1

    log.info("uploaded %s to %s as message %s", media_path.name, chat_id, message_id)
    print(f"✅ Uploaded {media_path.name} to {chat_id} (message_id={message_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
