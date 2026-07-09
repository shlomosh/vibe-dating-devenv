#!/usr/bin/env python3
"""Download a tweet's media and print its poster's profile info.

Given a Twitter/X status URL this script:
  1. Downloads the tweet's media (video or image) into ./downloads, reusing the
     project's yt-dlp/gallery-dl pipeline (lib/sources/twitter.py).
  2. Fetches the poster's profile metadata via gallery-dl and prints their
     display name, a link to their profile, and every link found in their bio
     (the bio website plus any URLs in the bio text).
  3. Writes a JSON file next to the media (<media>.json) recording the media
     location and the profile output.

Credentials: reads X_AUTH_TOKEN and X_CT0 from .env (or the environment) -- the
same authenticated cookies the rest of the project uses.

Usage:
  python download_twitter_media_and_info.py <tweet-url> [--output-dir DIR] [--json PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import proc  # noqa: E402
from lib.config import load_env, parse_tweet_id  # noqa: E402
from lib.log import log, setup_logging  # noqa: E402
from lib.sources.twitter import (  # noqa: E402
    TwitterDownloadError,
    _write_cookie_file,
    download_twitter,
)

METADATA_TIMEOUT = 120  # seconds (gallery-dl -j metadata fetch)
URL_RE = re.compile(r"https?://[^\s]+")


def build_env() -> dict[str, str]:
    merged = load_env(ROOT / ".env")
    merged.update(os.environ)
    return merged


def env_required(env: dict[str, str], name: str) -> str:
    val = env.get(name)
    if not val:
        raise SystemExit(f"Missing required environment variable: {name} (set it in .env)")
    return val


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


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="Twitter/X status URL")
    parser.add_argument("--output-dir", default=None, help="Where to save media (default: ./downloads)")
    parser.add_argument("--json", default=None, help="Path to write result JSON (default: <output-dir>/<media>.json)")
    args = parser.parse_args(argv)

    if not parse_tweet_id(args.url):
        print(f"❌ Not a tweet status URL: {args.url}", file=sys.stderr)
        return 1

    env = build_env()
    auth_token = env_required(env, "X_AUTH_TOKEN")
    ct0 = env_required(env, "X_CT0")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (ROOT / "downloads")

    # 1. Download the media.
    try:
        media_path = download_twitter(args.url, "twitter", output_dir, auth_token, ct0)
    except TwitterDownloadError as e:
        print(f"❌ Media download failed: {e}", file=sys.stderr)
        return 1

    # 2. Fetch and print the poster's profile.
    cookie_file = _write_cookie_file(auth_token, ct0)
    try:
        author = fetch_profile(args.url, cookie_file)
    except TwitterDownloadError as e:
        print(f"❌ Profile lookup failed: {e}", file=sys.stderr)
        return 1
    finally:
        cookie_file.unlink(missing_ok=True)

    handle = author.get("name", "")
    display_name = author.get("nick") or handle
    profile_link = f"https://x.com/{handle}" if handle else None
    links = bio_links(author)

    result = {
        "url": args.url,
        "tweet_id": parse_tweet_id(args.url),
        "media_path": str(media_path),
        "profile": {
            "name": display_name,
            "handle": handle,
            "profile_link": profile_link,
            "bio": author.get("description"),
            "bio_links": links,
        },
    }

    json_path = Path(args.json).resolve() if args.json else media_path.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== Downloaded media ===")
    print(f"  {media_path}")
    print("\n=== Poster profile ===")
    print(f"  Name:    {display_name}")
    print(f"  Profile: {profile_link or '(unknown)'}")
    if links:
        print("  Bio links:")
        for link in links:
            print(f"    - {link}")
    else:
        print("  Bio links: (none)")
    print(f"\n=== JSON written ===\n  {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
