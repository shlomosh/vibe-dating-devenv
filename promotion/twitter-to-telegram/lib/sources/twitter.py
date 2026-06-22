from __future__ import annotations

import glob
import os
import shutil
import tempfile
from pathlib import Path

from lib import proc
from lib.config import parse_tweet_id
from lib.log import log

# Hard caps so a stalled download can never hang the task.
VIDEO_TIMEOUT = 300  # seconds (yt-dlp: download + ffmpeg merge)
IMAGE_TIMEOUT = 120  # seconds (gallery-dl: single image)


class TwitterDownloadError(Exception):
    pass


def _write_cookie_file(auth_token: str, ct0: str) -> Path:
    """Write a Netscape cookie file for x.com / twitter.com (auth_token + ct0).

    Both downloaders read this file: it avoids yt-dlp's "cookies as a header"
    deprecation warning, and gallery-dl requires authenticated cookies (under a
    dotted domain) to fetch image / sensitive tweets.
    """
    fd, name = tempfile.mkstemp(prefix="x_cookies_", suffix=".txt")
    os.close(fd)
    lines = ["# Netscape HTTP Cookie File\n"]
    for domain in (".x.com", ".twitter.com"):
        lines.append(f"{domain}\tTRUE\t/\tTRUE\t2000000000\tauth_token\t{auth_token}\n")
        lines.append(f"{domain}\tTRUE\t/\tTRUE\t2000000000\tct0\t{ct0}\n")
    path = Path(name)
    path.write_text("".join(lines), encoding="utf-8")
    return path


def _find_output(base: Path, class_name: str, tweet_id: str) -> Path | None:
    # Match only this run's output template ("{class}_{tweet_id}.{ext}") and skip
    # in-progress fragments so we never return a partial/stale file.
    matches = sorted(
        p
        for p in glob.glob(str(base / f"{class_name}_{tweet_id}.*"))
        if not p.endswith((".part", ".ytdl"))
    )
    return Path(matches[0]) if matches else None


def _download_video(url: str, class_name: str, tweet_id: str, output_dir: Path, cookie_file: Path) -> Path | None:
    """Download a video tweet via yt-dlp. Returns None for image-only tweets."""
    if not shutil.which("yt-dlp"):
        raise TwitterDownloadError("yt-dlp not found on PATH")
    cmd = [
        "yt-dlp",
        "--no-progress",
        "--extractor-args", "twitter:legacy_api=true",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--cookies", str(cookie_file),
        "-o", str(output_dir / f"{class_name}_{tweet_id}.%(ext)s"),
        url,
    ]
    log.info("yt-dlp: start (timeout=%ss) %s", VIDEO_TIMEOUT, url)
    try:
        result = proc.run(cmd, timeout=VIDEO_TIMEOUT)
    except proc.ProcessTimeout as e:
        raise TwitterDownloadError(f"Twitter video download {e}") from e
    log.info("yt-dlp: finished rc=%s", result.returncode)
    if result.returncode == 0:
        return _find_output(output_dir, class_name, tweet_id)
    # Non-zero usually means "No video could be found" (image-only tweet); the
    # caller falls back to gallery-dl. yt-dlp cannot download Twitter photos.
    return None


def _download_image(url: str, class_name: str, tweet_id: str, output_dir: Path, cookie_file: Path) -> Path:
    """Download the first image of a tweet via gallery-dl (yt-dlp can't do photos)."""
    if not shutil.which("gallery-dl"):
        raise TwitterDownloadError("gallery-dl not found on PATH (needed for image tweets)")
    cmd = [
        "gallery-dl",
        "--cookies", str(cookie_file),
        "--range", "1",  # first media item only (multi-image tweets are a non-goal)
        "--directory", str(output_dir),
        "--filename", f"{class_name}_{tweet_id}.{{extension}}",
        url,
    ]
    log.info("gallery-dl: start (timeout=%ss) %s", IMAGE_TIMEOUT, url)
    try:
        result = proc.run(cmd, timeout=IMAGE_TIMEOUT)
    except proc.ProcessTimeout as e:
        raise TwitterDownloadError(f"Twitter image download {e}") from e
    log.info("gallery-dl: finished rc=%s", result.returncode)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error").strip()
        raise TwitterDownloadError(f"Twitter image download failed: {err}")
    found = _find_output(output_dir, class_name, tweet_id)
    if not found or not found.exists():
        raise TwitterDownloadError("gallery-dl reported success but no output file found")
    return found


def download_twitter(
    url: str,
    class_name: str,
    output_dir: Path,
    auth_token: str,
    ct0: str,
) -> Path:
    tweet_id = parse_tweet_id(url)
    if not tweet_id:
        raise TwitterDownloadError(f"Could not parse tweet ID from URL: {url}")

    output_dir.mkdir(parents=True, exist_ok=True)
    cookie_file = _write_cookie_file(auth_token, ct0)
    try:
        found = _download_video(url, class_name, tweet_id, output_dir, cookie_file)
        if found and found.exists():
            return found
        return _download_image(url, class_name, tweet_id, output_dir, cookie_file)
    finally:
        cookie_file.unlink(missing_ok=True)
