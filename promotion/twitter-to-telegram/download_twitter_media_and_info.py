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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.config import load_env, parse_tweet_id  # noqa: E402
from lib.credits import build_profile, fetch_profile  # noqa: E402
from lib.log import setup_logging  # noqa: E402
from lib.sources.twitter import (  # noqa: E402
    TwitterDownloadError,
    _write_cookie_file,
    download_twitter,
)


def build_env() -> dict[str, str]:
    merged = load_env(ROOT / ".env")
    merged.update(os.environ)
    return merged


def env_required(env: dict[str, str], name: str) -> str:
    val = env.get(name)
    if not val:
        raise SystemExit(f"Missing required environment variable: {name} (set it in .env)")
    return val


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

    profile = build_profile(author)

    result = {
        "url": args.url,
        "tweet_id": parse_tweet_id(args.url),
        "media_path": str(media_path),
        "profile": profile,
    }

    json_path = Path(args.json).resolve() if args.json else media_path.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== Downloaded media ===")
    print(f"  {media_path}")
    print("\n=== Poster profile ===")
    print(f"  Name:    {profile['name']}")
    print(f"  Profile: {profile['profile_link'] or '(unknown)'}")
    if profile["bio_links"]:
        print("  Bio links:")
        for link in profile["bio_links"]:
            print(f"    - {link}")
    else:
        print("  Bio links: (none)")
    print(f"\n=== JSON written ===\n  {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
