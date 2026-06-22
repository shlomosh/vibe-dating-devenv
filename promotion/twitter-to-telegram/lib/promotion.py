from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.config import (
    CAPTION_MAX_LEN,
    AppConfig,
    env_required,
    has_resource_posts,
    render_caption,
    parse_tweet_id,
)
from lib.resource import create_backend
from lib.resource.base import ResourceRow
from lib.run_state import (
    clear_message_ids,
    get_channel_state,
    get_message_id,
    load_state,
    mark_run_complete,
    save_state,
    set_message_id,
)
from lib.sources.twitter import TwitterDownloadError, download_twitter
from lib import telegram as tg
from lib.log import log


class NoPendingRows(Exception):
    pass


class PromotionError(Exception):
    pass


def _validate_post_entry(post: dict, index: int) -> None:
    resource = post.get("resource")
    text = post.get("text")
    image = post.get("image")
    if resource:
        if not str(resource).strip():
            raise PromotionError(f"Post {index}: resource class must be non-empty")
        if image:
            raise PromotionError(f"Post {index}: resource posts cannot have image")
        if text and len(str(text)) > CAPTION_MAX_LEN:
            raise PromotionError(f"Post {index}: caption exceeds {CAPTION_MAX_LEN} chars")
    else:
        if not text and not image:
            raise PromotionError(f"Post {index}: static post needs text and/or image")
        if text and image and len(str(text)) > CAPTION_MAX_LEN:
            raise PromotionError(f"Post {index}: caption exceeds {CAPTION_MAX_LEN} chars")


def run_promotion(
    cfg: AppConfig,
    env: dict[str, str],
    channel_key: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    channel = cfg.channels.get(channel_key)
    if not channel:
        raise PromotionError(f"Unknown channel: {channel_key}")
    if not channel.get("enabled", True):
        raise PromotionError(f"Channel disabled: {channel_key}")

    posts = channel.get("posts") or []
    if not posts:
        raise PromotionError(f"Channel {channel_key} has empty posts list")

    tg_cfg = channel["telegram"]
    chat_id = tg_cfg["chat_id"]
    bot_token = ""
    if not dry_run:
        bot_token = env_required(cfg, env, tg_cfg["bot_token_env"])

    log.info("run start: channel=%s posts=%d dry_run=%s", channel_key, len(posts), dry_run)

    log.info("loading state from %s", cfg.state_path)
    state = load_state(cfg.state_path)
    ch_state = get_channel_state(state, channel_key)
    log.info("state loaded")

    backend = None
    if not dry_run and has_resource_posts(cfg):
        log.info("loading resource backend (%s)", cfg.resource.get("type"))
        backend = create_backend(cfg.resource, cfg.config_dir)
        backend.reload()
        log.info("resource backend loaded")

    message_ids: list[int] = []
    resource_log: list[str] = []
    run_resources: list[dict] = []
    posts_succeeded = 0

    for i, post in enumerate(posts):
        _validate_post_entry(post, i)
        silent = bool(post.get("silent", False))
        delete_prev = bool(post.get("delete_previous", False))
        resource_class = post.get("resource")
        log.info("post %d: begin (resource=%s delete_previous=%s)", i, resource_class, delete_prev)

        if dry_run:
            if resource_class:
                print(f"[dry-run] post {i}: resource class={resource_class}")
            elif post.get("image") and post.get("text"):
                print(f"[dry-run] post {i}: photo+caption")
            elif post.get("image"):
                print(f"[dry-run] post {i}: photo")
            else:
                print(f"[dry-run] post {i}: text")
            posts_succeeded += 1
            continue

        if delete_prev:
            prev_id = get_message_id(ch_state, i)
            if prev_id is not None:
                try:
                    log.info("post %d: deleting previous message %s", i, prev_id)
                    tg.delete_message(bot_token, chat_id, prev_id)
                    log.info("post %d: deleted previous message %s", i, prev_id)
                except tg.TelegramError as e:
                    log.warning("post %d: delete_previous failed: %s", i, e)

        if resource_class:
            assert backend is not None
            log.info("post %d: selecting next row for class=%s", i, resource_class)
            row = backend.select_next(str(resource_class))
            if row is None:
                if posts_succeeded == 0:
                    raise NoPendingRows(f"No available rows for class {resource_class!r}")
                raise PromotionError(f"No available rows for class {resource_class!r} (partial run)")
            log.info("post %d: selected %s (source=%s)", i, row.url, row.source)

            caption = None
            if post.get("text"):
                ctx = _caption_context(channel_key, str(resource_class), row)
                caption = render_caption(str(post["text"]), ctx)
                if len(caption) > CAPTION_MAX_LEN:
                    raise PromotionError(f"Post {i}: rendered caption exceeds {CAPTION_MAX_LEN} chars")

            log.info("post %d: downloading %s", i, row.url)
            media_path = _download_resource(cfg, env, row, str(resource_class))
            size = media_path.stat().st_size if media_path.exists() else -1
            log.info("post %d: downloaded %s (%d bytes)", i, media_path.name, size)
            try:
                log.info("post %d: sending media to telegram", i)
                mid = tg.send_media_file(bot_token, chat_id, media_path, caption, silent)
                log.info("post %d: telegram accepted, message_id=%s", i, mid)
            finally:
                if not cfg.keep_files and media_path.exists():
                    media_path.unlink(missing_ok=True)

            log.info("post %d: marking row used", i)
            backend.mark_used(row)
            resource_log.append(f"{resource_class}:{row.url}")
            run_resources.append({"class": resource_class, "url": row.url, "post_index": i})
            log.info("post %d: resource post done (%s) message_id=%s", i, resource_class, mid)
        else:
            text = post.get("text")
            image = post.get("image")
            if image:
                img_path = cfg.resolve_path(str(image))
                if not img_path.exists():
                    raise PromotionError(f"Post {i}: image not found: {img_path}")
                log.info("post %d: sending photo %s", i, img_path.name)
                mid = tg.send_photo(bot_token, chat_id, img_path, text, silent)
                log.info("post %d: photo sent message_id=%s", i, mid)
            else:
                log.info("post %d: sending text", i)
                mid = tg.send_text(bot_token, chat_id, str(text), silent)
                log.info("post %d: text sent message_id=%s", i, mid)

        set_message_id(ch_state, i, mid)
        log.info("post %d: saving state", i)
        save_state(cfg.state_path, state)
        log.info("post %d: state saved", i)
        message_ids.append(mid)
        posts_succeeded += 1

    if not dry_run:
        mark_run_complete(ch_state, run_resources)
        save_state(cfg.state_path, state)
    log.info("run complete: channel=%s posts_sent=%d", channel_key, posts_succeeded)

    return {
        "channel": channel_key,
        "chat_id": chat_id,
        "message_ids": message_ids,
        "resources": resource_log,
        "posts_sent": posts_succeeded,
        "status": "posted" if not dry_run else "dry_run",
    }


def _caption_context(channel_key: str, class_name: str, row: ResourceRow) -> dict[str, str]:
    now = datetime.now()
    tweet_id = parse_tweet_id(row.url) or ""
    return {
        "url": row.url,
        "tweet_id": tweet_id,
        "channel": channel_key,
        "class": class_name,
        "post_date": now.strftime("%Y-%m-%d"),
        "post_datetime": now.strftime("%Y-%m-%d %H:%M"),
    }


def _download_resource(cfg: AppConfig, env: dict[str, str], row: ResourceRow, class_name: str) -> Path:
    source = row.source.lower()
    if source != "twitter":
        raise PromotionError(f"Unsupported source: {row.source!r}")

    auth_env = cfg.twitter.get("auth_token_env")
    ct0_env = cfg.twitter.get("ct0_env")
    if not auth_env or not ct0_env:
        raise PromotionError("Missing twitter.auth_token_env / twitter.ct0_env in config")
    try:
        auth = env_required(cfg, env, auth_env)
        ct0 = env_required(cfg, env, ct0_env)
    except ValueError as e:
        raise PromotionError(str(e)) from e
    try:
        path = download_twitter(row.url, class_name, cfg.downloads_dir, auth, ct0)
    except TwitterDownloadError as e:
        raise PromotionError(str(e)) from e
    return path


def delete_channel_posts(
    cfg: AppConfig,
    env: dict[str, str],
    channel_key: str,
    post_index: int | None = None,
) -> None:
    channel = cfg.channels.get(channel_key)
    if not channel:
        raise PromotionError(f"Unknown channel: {channel_key}")

    tg_cfg = channel["telegram"]
    bot_token = env_required(cfg, env, tg_cfg["bot_token_env"])
    chat_id = tg_cfg["chat_id"]

    state = load_state(cfg.state_path)
    ch_state = get_channel_state(state, channel_key)
    pids = ch_state.get("post_message_ids", {})

    if post_index is not None:
        mid = pids.get(str(post_index))
        if mid is None:
            raise PromotionError(f"No stored message for post index {post_index}")
        try:
            tg.delete_message(bot_token, chat_id, int(mid))
            print(f"✅ Deleted message {mid} (post {post_index})")
        except tg.TelegramError as e:
            print(f"⚠️  delete failed for post {post_index}: {e}", file=sys.stderr)
        clear_message_ids(ch_state, [post_index])
        save_state(cfg.state_path, state)
    else:
        if not pids:
            raise PromotionError("No stored messages to delete")
        for idx, mid in list(pids.items()):
            try:
                tg.delete_message(bot_token, chat_id, int(mid))
                print(f"✅ Deleted message {mid} (post {idx})")
            except tg.TelegramError as e:
                print(f"⚠️  delete failed for post {idx}: {e}", file=sys.stderr)
            clear_message_ids(ch_state, [int(idx)])
            save_state(cfg.state_path, state)


def print_run_summary(result: dict[str, Any]) -> None:
    print(f"channel={result['channel']}")
    print(f"chat_id={result['chat_id']}")
    if result.get("resources"):
        print(f"resources={','.join(result['resources'])}")
    if result.get("message_ids"):
        print(f"message_ids={','.join(str(m) for m in result['message_ids'])}")
    print(f"posts_sent={result['posts_sent']}")
    print(f"status={result['status']}")
