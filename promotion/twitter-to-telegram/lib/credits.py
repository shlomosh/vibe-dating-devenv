"""Fetch a tweet poster's profile and format it as a Telegram credits caption.

Shared by download_twitter_media_and_info.py (standalone single-tweet lookup),
upload_twitter_media_and_info_to_telegram.py (standalone caption formatting),
and lib/promotion.py (the `include_credits` resource-post flow).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from lib import proc
from lib.log import log
from lib.sources.twitter import TwitterDownloadError

METADATA_TIMEOUT = 120  # seconds (gallery-dl -j metadata fetch)
URL_RE = re.compile(r"https?://[^\s]+")
CAPTION_MAX_LEN = 1024  # Telegram media caption limit


def _find_author(data) -> dict | None:
    """Pull the author/user object out of gallery-dl's -j output.

    -j prints a list of [code, ...] records; the tweet metadata record carries an
    "author" (and "user") dict. Walk the structure and return the first one.
    """
    if isinstance(data, dict):
        for key in ("author", "user"):
            if isinstance(data.get(key), dict) and data[key].get("name"):
                return data[key]
        for val in data.values():
            found = _find_author(val)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_author(item)
            if found:
                return found
    return None


def fetch_profile(url: str, cookie_file: Path) -> dict:
    """Return the poster's author metadata dict via gallery-dl -j."""
    import shutil

    if not shutil.which("gallery-dl"):
        raise TwitterDownloadError("gallery-dl not found on PATH (needed for profile info)")
    cmd = ["gallery-dl", "--cookies", str(cookie_file), "--range", "1", "-j", url]
    log.info("gallery-dl -j: start (timeout=%ss) %s", METADATA_TIMEOUT, url)
    try:
        result = proc.run(cmd, timeout=METADATA_TIMEOUT)
    except proc.ProcessTimeout as e:
        raise TwitterDownloadError(f"Profile metadata fetch {e}") from e
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error").strip()
        raise TwitterDownloadError(f"Profile metadata fetch failed: {err}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise TwitterDownloadError(f"Could not parse gallery-dl JSON: {e}") from e
    author = _find_author(data)
    if not author:
        raise TwitterDownloadError("No author metadata found in gallery-dl output")
    return author


def bio_links(author: dict) -> list[str]:
    """Every link in the bio: the profile website plus URLs in the bio text.

    gallery-dl already expands t.co links to their real targets, so both the
    `url` website field and URLs embedded in `description` are usable as-is.
    Order-preserving dedupe.
    """
    links: list[str] = []
    website = (author.get("url") or "").strip()
    if website:
        links.append(website)
    for match in URL_RE.findall(author.get("description") or ""):
        links.append(match.rstrip(".,);"))
    seen: set[str] = set()
    return [x for x in links if not (x in seen or seen.add(x))]


def build_profile(author: dict) -> dict:
    """Shape a gallery-dl author dict into the {name, handle, profile_link,
    bio, bio_links} profile record used by info JSON files and captions."""
    handle = author.get("name", "")
    display_name = author.get("nick") or handle
    profile_link = f"https://x.com/{handle}" if handle else None
    return {
        "name": display_name,
        "handle": handle,
        "profile_link": profile_link,
        "bio": author.get("description"),
        "bio_links": bio_links(author),
    }


def build_caption(profile: dict) -> str:
    """Format the profile as an HTML caption: bold name, profile link, bio links."""
    name = (profile.get("name") or "").strip()
    profile_link = (profile.get("profile_link") or "").strip()
    bio_links_ = profile.get("bio_links") or []

    lines: list[str] = []
    if name:
        lines.append(f"<b>{html.escape(name)}</b>")
    if profile_link:
        lines.append(html.escape(profile_link))
    for link in bio_links_:
        link = (link or "").strip()
        if link:
            lines.append(html.escape(link))

    caption = "\n".join(lines)
    if len(caption) > CAPTION_MAX_LEN:
        caption = caption[:CAPTION_MAX_LEN]
    return caption
