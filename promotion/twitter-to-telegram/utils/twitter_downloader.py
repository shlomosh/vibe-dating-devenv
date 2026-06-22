#!/usr/bin/env python3
"""
Twitter/X Media Downloader
Usage:
  python twitter_downloader.py <tweet_url> [--output-dir ./downloads]
  python twitter_downloader.py <tweet_url> --mp3

Setup: create a .env file with:
  X_AUTH_TOKEN=your_auth_token
  X_CT0=your_ct0_value
"""

import argparse
import sys
import shutil
import subprocess
from pathlib import Path


def check_dependencies(mp3: bool = False):
    if not shutil.which("yt-dlp"):
        print("❌ yt-dlp not found. Install: pip install yt-dlp")
        sys.exit(1)
    if mp3 and not shutil.which("ffmpeg"):
        print("❌ ffmpeg not found. Required for MP3 conversion.")
        sys.exit(1)


def load_env() -> dict:
    env = {}
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def download(url: str, output_dir: str, mp3: bool = False):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    env = load_env()
    auth_token = env.get("X_AUTH_TOKEN")
    ct0 = env.get("X_CT0")

    cmd = [
        "yt-dlp",
        "--progress",
        "--extractor-args", "twitter:legacy_api=true",
        "-o", f"{output_dir}/%(id)s.%(ext)s",
    ]

    if mp3:
        cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3"]
    else:
        cmd += [
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
        ]

    if auth_token and ct0:
        cmd += ["--add-header", f"Cookie: auth_token={auth_token}; ct0={ct0}"]
        cmd += ["--add-header", f"X-Csrf-Token: {ct0}"]
    else:
        print("⚠️  Missing X_AUTH_TOKEN or X_CT0 in .env file")

    cmd.append(url)

    print(f"🔍 Downloading: {url}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("❌ Download failed.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Download media from Twitter/X")
    parser.add_argument("url", help="Tweet URL")
    parser.add_argument("--output-dir", "-o", default="./downloads", help="Output directory")
    parser.add_argument(
        "--mp3",
        action="store_true",
        help="Extract audio and save as MP3 (single download, no video merge)",
    )

    args = parser.parse_args()

    check_dependencies(args.mp3)
    download(args.url, args.output_dir, args.mp3)


if __name__ == "__main__":
    main()
