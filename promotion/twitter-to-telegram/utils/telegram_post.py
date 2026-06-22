#!/usr/bin/env python3
"""
Telegram Group Publisher
Usage examples at bottom of file.

Setup (.env):
  TELEGRAM_BOT_TOKEN=your_bot_token
  TELEGRAM_CHAT_ID=your_group_chat_id
"""

import argparse
import sys
import json
import urllib.request
import urllib.parse
import mimetypes
from pathlib import Path
from datetime import datetime


# ─── Config ───────────────────────────────────────────────────────────────────

def load_env() -> dict:
    env = {}
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def get_config():
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        sys.exit(1)
    return token, chat_id


# ─── Helpers ──────────────────────────────────────────────────────────────────

def api_post_json(token: str, endpoint: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        print(f"❌ API error: {result}")
        sys.exit(1)
    return result


def api_post_multipart(token: str, endpoint: str, fields: dict, file_field: str, file_path: Path) -> dict:
    url = f"https://api.telegram.org/bot{token}/{endpoint}"
    boundary = "----TGBoundary"
    body = b""

    for key, val in fields.items():
        if val is None:
            continue
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{val}\r\n"
        ).encode()

    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_data = f.read()

    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode()
    body += file_data
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        print(f"❌ API error: {result}")
        sys.exit(1)
    return result


def extra_flags(silent: bool, schedule: str) -> dict:
    flags = {}
    if silent:
        flags["disable_notification"] = True
    if schedule:
        try:
            dt = datetime.strptime(schedule, "%Y-%m-%d %H:%M")
            flags["schedule_date"] = int(dt.timestamp())
        except ValueError:
            print("❌ Schedule format must be: 'YYYY-MM-DD HH:MM'")
            sys.exit(1)
    return flags


def message_id_from_result(result: dict) -> int | None:
    return result.get("result", {}).get("message_id")


def emit_message_id(result: dict) -> int | None:
    message_id = message_id_from_result(result)
    if message_id is not None:
        print(f"message_id={message_id}")
    return message_id


# ─── Senders ──────────────────────────────────────────────────────────────────

def send_text(token, chat_id, text, silent, schedule) -> int | None:
    payload = {"chat_id": chat_id, "text": text, **extra_flags(silent, schedule)}
    result = api_post_json(token, "sendMessage", payload)
    print("✅ Text sent!")
    return emit_message_id(result)


def send_media(token, chat_id, media_path, caption, silent, schedule) -> int | None:
    path = Path(media_path)
    if not path.exists():
        print(f"❌ File not found: {media_path}")
        sys.exit(1)

    mime_type, _ = mimetypes.guess_type(str(path))
    suffix = path.suffix.lower()

    if suffix == ".gif" or (mime_type and "gif" in mime_type):
        endpoint, field = "sendAnimation", "animation"
        label = "GIF"
    elif mime_type and mime_type.startswith("video"):
        endpoint, field = "sendVideo", "video"
        label = "Video"
    elif mime_type and mime_type.startswith("image"):
        endpoint, field = "sendPhoto", "photo"
        label = "Photo"
    else:
        endpoint, field = "sendDocument", "document"
        label = "Document"

    fields = {"chat_id": chat_id, "caption": caption, **extra_flags(silent, schedule)}
    print(f"📤 Uploading {label}: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)...")
    result = api_post_multipart(token, endpoint, fields, field, path)
    print(f"✅ {label} sent!")
    return emit_message_id(result)


def send_document(token, chat_id, file_path, caption, silent, schedule) -> int | None:
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    fields = {"chat_id": chat_id, "caption": caption, **extra_flags(silent, schedule)}
    print(f"📤 Uploading document: {path.name}...")
    result = api_post_multipart(token, "sendDocument", fields, "document", path)
    print("✅ Document sent!")
    return emit_message_id(result)


def send_poll(token, chat_id, args_poll, silent, schedule) -> int | None:
    if len(args_poll) < 3:
        print("❌ Poll needs: 'Question?' 'Option 1' 'Option 2' ...")
        sys.exit(1)
    payload = {
        "chat_id": chat_id,
        "question": args_poll[0],
        "options": args_poll[1:],
        "is_anonymous": True,
        **extra_flags(silent, schedule)
    }
    result = api_post_json(token, "sendPoll", payload)
    print("✅ Poll sent!")
    return emit_message_id(result)


def send_quiz(token, chat_id, args_quiz, explanation, silent, schedule) -> int | None:
    # Format: "Question?" "Option1" "Option2" "correct_index"
    if len(args_quiz) < 4:
        print("❌ Quiz needs: 'Question?' 'Option 1' 'Option 2' correct_index(0-based)")
        sys.exit(1)
    try:
        correct = int(args_quiz[-1])
    except ValueError:
        print("❌ Last argument must be the correct answer index (0, 1, 2...)")
        sys.exit(1)
    payload = {
        "chat_id": chat_id,
        "question": args_quiz[0],
        "options": args_quiz[1:-1],
        "type": "quiz",
        "correct_option_id": correct,
        "is_anonymous": True,
        **extra_flags(silent, schedule)
    }
    if explanation:
        payload["explanation"] = explanation
    result = api_post_json(token, "sendPoll", payload)
    print("✅ Quiz sent!")
    return emit_message_id(result)


def send_dice(token, chat_id, emoji, silent, schedule) -> int | None:
    valid = ["🎲", "🎯", "🏀", "⚽", "🎳", "🎰"]
    if emoji not in valid:
        print(f"❌ Valid emojis: {' '.join(valid)}")
        sys.exit(1)
    payload = {"chat_id": chat_id, "emoji": emoji, **extra_flags(silent, schedule)}
    result = api_post_json(token, "sendDice", payload)
    print(f"✅ Dice {emoji} sent!")
    return emit_message_id(result)


def delete_message(token, chat_id, message_id):
    payload = {"chat_id": chat_id, "message_id": int(message_id)}
    api_post_json(token, "deleteMessage", payload)
    print(f"✅ Message {message_id} deleted!")


def pin_message(token, chat_id, message_id, silent):
    payload = {"chat_id": chat_id, "message_id": int(message_id), "disable_notification": silent}
    api_post_json(token, "pinChatMessage", payload)
    print(f"✅ Message {message_id} pinned!")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Publish to Telegram group",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Text
  python telegram_post.py --text "Hello! 👋"

  # Video / Photo / GIF (auto-detected)
  python telegram_post.py --media ./video.mp4 --text "Caption here"

  # Document (PDF, ZIP, etc.)
  python telegram_post.py --document ./report.pdf --text "Read this"

  # Poll
  python telegram_post.py --poll "Favorite country?" "Italy" "Japan" "Brazil"

  # Quiz
  python telegram_post.py --quiz "Capital of France?" "London" "Paris" "Berlin" 1 --explanation "Paris is the capital!"

  # Dice / Game
  python telegram_post.py --dice 🎲
  python telegram_post.py --dice 🏀

  # Pin a message
  python telegram_post.py --pin 42

  # Delete a message (use message_id printed after posting)
  python telegram_post.py --delete 42

  # Capture message_id in a shell script
  MSG_ID=$(python telegram_post.py --text "Hello!" | sed -n 's/^message_id=//p')

  # Silent (no notification)
  python telegram_post.py --text "Quiet post" --silent

  # Scheduled
  python telegram_post.py --text "Good morning!" --schedule "2025-06-15 09:00"
        """
    )

    parser.add_argument("--text", "-t", help="Text message")
    parser.add_argument("--media", "-m", help="Image / Video / GIF path (auto-detected)")
    parser.add_argument("--document", "-d", help="Any file as document (PDF, ZIP, etc.)")
    parser.add_argument("--poll", nargs="+", metavar="ARG", help='"Question?" "Opt1" "Opt2" ...')
    parser.add_argument("--quiz", nargs="+", metavar="ARG", help='"Question?" "Opt1" "Opt2" correct_index')
    parser.add_argument("--explanation", help="Explanation for quiz answer")
    parser.add_argument("--dice", metavar="EMOJI", help="🎲 🎯 🏀 ⚽ 🎳 🎰")
    parser.add_argument("--pin", metavar="MESSAGE_ID", help="Pin a message by ID")
    parser.add_argument("--delete", metavar="MESSAGE_ID", help="Delete a message by ID")
    parser.add_argument("--silent", action="store_true", help="Send without notification")
    parser.add_argument("--schedule", metavar="DATETIME", help="Schedule: 'YYYY-MM-DD HH:MM'")

    args = parser.parse_args()

    if not any([args.text, args.media, args.document, args.poll, args.quiz, args.dice, args.pin, args.delete]):
        parser.print_help()
        sys.exit(1)

    token, chat_id = get_config()

    if args.delete:
        delete_message(token, chat_id, args.delete)
    elif args.pin:
        pin_message(token, chat_id, args.pin, args.silent)
    elif args.dice:
        send_dice(token, chat_id, args.dice, args.silent, args.schedule)
    elif args.quiz:
        send_quiz(token, chat_id, args.quiz, args.explanation, args.silent, args.schedule)
    elif args.poll:
        send_poll(token, chat_id, args.poll, args.silent, args.schedule)
    elif args.document:
        send_document(token, chat_id, args.document, args.text, args.silent, args.schedule)
    elif args.media:
        send_media(token, chat_id, args.media, args.text, args.silent, args.schedule)
    elif args.text:
        send_text(token, chat_id, args.text, args.silent, args.schedule)


if __name__ == "__main__":
    main()