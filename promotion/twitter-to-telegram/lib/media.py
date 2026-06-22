"""Prepare downloaded media for Telegram inline playback."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from lib import proc
from lib.log import log

VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v")
FFMPEG_TIMEOUT = 180  # seconds (faststart re-mux, stream copy)
FFPROBE_TIMEOUT = 30  # seconds (metadata probe)
THUMBNAIL_TIMEOUT = 30  # seconds (single-frame extract)


def ensure_faststart(path: Path) -> Path:
    """Re-mux an MP4/MOV so the moov atom is at the front of the file.

    Telegram needs a streamable ("faststart") video to autoplay inline and to
    render a preview thumbnail; otherwise the client shows a blank box that the
    user must download before viewing. yt-dlp/ffmpeg writes the moov atom at the
    end by default, so we relocate it with a stream copy (no re-encode). No-op
    when ffmpeg is missing or the file is not an MP4-family container.
    """
    if path.suffix.lower() not in VIDEO_SUFFIXES or not shutil.which("ffmpeg"):
        return path
    tmp = path.with_name(path.stem + ".faststart" + path.suffix)
    log.info("faststart: start %s", path.name)
    try:
        result = proc.run(
            ["ffmpeg", "-y", "-i", str(path), "-c", "copy", "-movflags", "+faststart", str(tmp)],
            timeout=FFMPEG_TIMEOUT,
        )
    except proc.ProcessTimeout:
        log.warning("faststart: timed out, skipping for %s", path.name)
        tmp.unlink(missing_ok=True)
        return path  # best-effort: skip faststart rather than hang
    if result.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, path)
    else:
        tmp.unlink(missing_ok=True)
    log.info("faststart: done %s", path.name)
    return path


def video_metadata(path: Path) -> dict[str, int]:
    """Return {width, height, duration} for a video via ffprobe (best effort)."""
    if not shutil.which("ffprobe"):
        return {}
    log.info("ffprobe: start %s", path.name)
    try:
        result = proc.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            timeout=FFPROBE_TIMEOUT,
        )
    except proc.ProcessTimeout:
        return {}
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    meta: dict[str, int] = {}
    streams = data.get("streams") or []
    if streams:
        if streams[0].get("width"):
            meta["width"] = int(streams[0]["width"])
        if streams[0].get("height"):
            meta["height"] = int(streams[0]["height"])
    dur = (data.get("format") or {}).get("duration")
    if dur:
        try:
            meta["duration"] = int(float(dur))
        except (TypeError, ValueError):
            pass
    log.info("ffprobe: done %s", meta)
    return meta


def make_thumbnail(path: Path) -> Path | None:
    """Extract a JPEG poster frame (<=320px) for Telegram (best effort).

    Sending an explicit thumbnail makes Telegram render an inline video player
    with a preview; without one it sometimes shows the video as a download-only
    file. Telegram thumbnails must be JPEG and at most 320px on a side.
    """
    if not shutil.which("ffmpeg"):
        return None
    thumb = path.with_name(path.stem + ".thumb.jpg")
    log.info("thumbnail: start %s", path.name)
    try:
        result = proc.run(
            [
                "ffmpeg", "-y",
                "-i", str(path),
                "-frames:v", "1",
                "-an",
                "-vf", "scale=w=320:h=320:force_original_aspect_ratio=decrease",
                str(thumb),
            ],
            timeout=THUMBNAIL_TIMEOUT,
        )
    except proc.ProcessTimeout:
        log.warning("thumbnail: timed out for %s", path.name)
        thumb.unlink(missing_ok=True)
        return None
    log.info("thumbnail: done rc=%s", result.returncode)
    if result.returncode == 0 and thumb.exists() and thumb.stat().st_size > 0:
        return thumb
    thumb.unlink(missing_ok=True)
    return None
