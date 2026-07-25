#!/usr/bin/env python3
"""Copy every message from one Telegram channel to another.

Messages are not forwarded (no "Forwarded from..." attribution). Instead each
message's media and/or text is downloaded from the source and re-uploaded as
fresh content on the destination.

Why a user session and not the bot token: the Telegram **Bot API cannot read or
search a channel's history** even when the bot is an admin -- it only receives
new messages via updates. Enumerating past messages requires the MTProto client
API, which needs a user account. We use Telethon for that.

Setup:
  1. pip install -r requirements.txt   (telethon)
  2. Create an app at https://my.telegram.org -> API development tools, then set
     in .env (or the environment):
        TELEGRAM_API_ID=...
        TELEGRAM_API_HASH=...
        TELEGRAM_PHONE=+49...        # optional; prompted if absent
  3. First run performs an interactive phone-code login and caches a local
     .telegram_repost.session file for subsequent runs.

Usage:
  python telegram_repost.py --source <chan> --destination <chan> [options]

  <chan> may be a numeric id (e.g. -1004364960110), a @username, or a t.me link.
  --source and --destination may be the same channel.

Options:
  --limit N        Stop after scanning N source messages (newest first).
  --min-id ID      Only consider source messages with id > ID.
  --max-id ID      Only consider source messages with id < ID.
  --keep-files     Keep downloaded media instead of deleting after repost.
  --dry-run        Report what would be reposted; download/send nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.config import load_env  # noqa: E402
from lib.log import log, setup_logging  # noqa: E402

SESSION_PATH = ROOT / ".telegram_repost.session"
CAPTION_MAX_LEN = 1024  # Telegram media caption limit
TEXT_MAX_LEN = 4096  # Telegram plain text message limit


def build_env() -> dict[str, str]:
    merged = load_env(ROOT / ".env")
    merged.update(os.environ)
    return merged


def env_required(env: dict[str, str], name: str) -> str:
    val = env.get(name)
    if not val:
        raise SystemExit(f"Missing required environment variable: {name} (set it in .env)")
    return val


def parse_chat(value: str):
    """Turn a CLI channel argument into something Telethon can resolve.

    Accepts a numeric id (-100... or bare), a @username, or a t.me link. Numeric
    ids are returned as int so Telethon resolves them as peers; everything else
    is passed through as a string.
    """
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        return value


def is_repostable(msg) -> bool:
    """True if the message carries content worth copying (media and/or text).

    Service messages (user joined, pinned, etc.) and empty placeholders are
    skipped since there is nothing to re-upload.
    """
    if getattr(msg, "action", None) is not None:
        return False
    if msg.media is not None:
        return True
    return bool((msg.message or "").strip())


def caption_for(msg) -> str | None:
    text = (msg.message or "").strip()
    if not text:
        return None
    return text[:CAPTION_MAX_LEN]


async def collect_messages(client, source, *, limit, min_id, max_id):
    """Return all repostable source messages, oldest-first.

    Albums (grouped media) are collapsed into a single batch keyed by grouped_id
    so a multi-photo post is reposted as one album rather than N separate posts.
    """
    singles: list = []
    groups: dict[int, list] = {}
    scanned = 0

    iter_kwargs: dict = {}
    if min_id:
        iter_kwargs["min_id"] = min_id
    if max_id:
        iter_kwargs["max_id"] = max_id

    async for msg in client.iter_messages(source, limit=limit, **iter_kwargs):
        scanned += 1
        if not is_repostable(msg):
            continue
        gid = msg.grouped_id
        if gid is not None:
            groups.setdefault(gid, []).append(msg)
        else:
            singles.append(msg)

    log.info("scanned %d source message(s)", scanned)

    # Build a unified, chronologically ordered (oldest-first) work list. Each
    # item is a list of messages: length 1 for a single, >1 for an album.
    batches: list[list] = [[m] for m in singles]
    for gid, msgs in groups.items():
        msgs.sort(key=lambda m: m.id)
        batches.append(msgs)
    batches.sort(key=lambda b: b[0].id)
    return batches, scanned


async def repost_batch(client, dest, batch, downloads_dir: Path, *, keep_files: bool) -> bool:
    """Download a batch's media (if any) and re-upload it to dest, or send its
    text as a plain message when the batch carries no media. Returns True on send.
    """
    has_media = any(m.media is not None for m in batch)

    if not has_media:
        msg = batch[0]
        text = (msg.message or "").strip()
        if not text:
            log.warning("msg %d has no text or media; skipping", msg.id)
            return False
        await client.send_message(dest, text[:TEXT_MAX_LEN])
        log.info("reposted text-only msg %d", msg.id)
        return True

    paths: list[Path] = []
    try:
        for msg in batch:
            if msg.media is None:
                continue
            dest_path = await client.download_media(msg, file=str(downloads_dir))
            if dest_path:
                paths.append(Path(dest_path))
                log.info("downloaded msg %d -> %s", msg.id, Path(dest_path).name)
        if not paths:
            log.warning("batch starting at msg %d had no downloadable media", batch[0].id)
            return False

        # Caption comes from whichever message in the batch carried text.
        caption = next((caption_for(m) for m in batch if caption_for(m)), None)

        send_arg = str(paths[0]) if len(paths) == 1 else [str(p) for p in paths]
        await client.send_file(dest, send_arg, caption=caption, supports_streaming=True)
        log.info("reposted %d media item(s) from msg %d", len(paths), batch[0].id)
        return True
    finally:
        if not keep_files:
            for p in paths:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass


async def run(args) -> int:
    from telethon import TelegramClient

    env = build_env()
    api_id = int(env_required(env, "TELEGRAM_API_ID"))
    api_hash = env_required(env, "TELEGRAM_API_HASH")
    phone = env.get("TELEGRAM_PHONE")

    source = parse_chat(args.source)
    dest = parse_chat(args.destination)

    downloads_dir = ROOT / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await client.start(phone=phone)
    try:
        me = await client.get_me()
        log.info("logged in as %s (id=%s)", me.username or me.first_name, me.id)

        src_entity = await client.get_entity(source)
        dst_entity = await client.get_entity(dest)
        log.info(
            "source=%s destination=%s%s",
            getattr(src_entity, "title", source),
            getattr(dst_entity, "title", dest),
            " (same channel)" if src_entity.id == dst_entity.id else "",
        )

        batches, scanned = await collect_messages(
            client, src_entity, limit=args.limit, min_id=args.min_id, max_id=args.max_id
        )
        media_batches = [b for b in batches if any(m.media is not None for m in b)]
        total_media = sum(len(b) for b in media_batches)
        text_only = len(batches) - len(media_batches)
        log.info(
            "found %d post(s) to repost (%d media post(s) / %d media item(s), %d text-only)",
            len(batches), len(media_batches), total_media, text_only,
        )

        if args.dry_run:
            for b in batches:
                ids = ", ".join(str(m.id) for m in b)
                has_media = any(m.media is not None for m in b)
                if has_media:
                    cap = next((caption_for(m) for m in b if caption_for(m)), None)
                    kind = f"{len(b)} media"
                else:
                    cap = (b[0].message or "").strip()
                    kind = "text"
                preview = f' "{cap[:60]}"' if cap else ""
                print(f"[dry-run] would repost msg(s) {ids} ({kind}){preview}")
            print(f"\n[dry-run] {len(batches)} post(s) / {total_media} media item(s) / {text_only} text-only; scanned {scanned}")
            return 0

        reposted = 0
        for b in batches:
            try:
                if await repost_batch(client, dst_entity, b, downloads_dir, keep_files=args.keep_files):
                    reposted += 1
            except Exception as e:  # noqa: BLE001 - keep going on a single failure
                log.error("failed to repost msg %d: %s", b[0].id, e)

        print(f"Done: reposted {reposted}/{len(batches)} post(s); scanned {scanned} message(s).")
        return 0 if reposted == len(batches) else 1
    finally:
        await client.disconnect()


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Source channel id, @username, or t.me link")
    parser.add_argument("--destination", required=True, help="Destination channel id, @username, or t.me link")
    parser.add_argument("--limit", type=int, default=None, help="Stop after scanning N source messages")
    parser.add_argument("--min-id", type=int, default=0, help="Only messages with id > this")
    parser.add_argument("--max-id", type=int, default=0, help="Only messages with id < this")
    parser.add_argument("--keep-files", action="store_true", help="Keep downloaded media after repost")
    parser.add_argument("--dry-run", action="store_true", help="Report only; download/send nothing")
    args = parser.parse_args(argv)

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
