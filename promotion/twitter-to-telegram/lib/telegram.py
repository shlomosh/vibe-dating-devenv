from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path

from lib import media
from lib.log import log

API_TIMEOUT = 30  # seconds (sendMessage / deleteMessage JSON calls)
UPLOAD_TIMEOUT = 180  # seconds (photo / video / document multipart uploads)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # Telegram Bot API upload limit (sendVideo/Document)


class TelegramError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def _api_post_json(token: str, endpoint: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise TelegramError(f"Telegram API HTTP {e.code}: {body}", code=e.code) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise TelegramError(f"Telegram API request failed ({endpoint}): {e}") from e
    if not result.get("ok"):
        raise TelegramError(f"Telegram API error: {result}")
    return result


def _api_post_multipart(token: str, endpoint: str, fields: dict, files: dict[str, Path]) -> dict:
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

    for field, file_path in files.items():
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{file_path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
        body += file_path.read_bytes()
        body += b"\r\n"

    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    log.info("telegram %s: uploading %d bytes (timeout=%ss)", endpoint, len(body), UPLOAD_TIMEOUT)
    try:
        with urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        raise TelegramError(f"Telegram API HTTP {e.code}: {body_err}", code=e.code) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise TelegramError(f"Telegram upload failed ({endpoint}): {e}") from e
    if not result.get("ok"):
        raise TelegramError(f"Telegram API error: {result}")
    log.info("telegram %s: ok", endpoint)
    return result


def message_id_from_result(result: dict) -> int:
    mid = result.get("result", {}).get("message_id")
    if mid is None:
        raise TelegramError(f"No message_id in response: {result}")
    return int(mid)


def send_text(token: str, chat_id, text: str, silent: bool = False) -> int:
    payload = {"chat_id": chat_id, "text": text}
    if silent:
        payload["disable_notification"] = True
    return message_id_from_result(_api_post_json(token, "sendMessage", payload))


def send_photo(
    token: str,
    chat_id,
    file_path: Path,
    caption: str | None = None,
    silent: bool = False,
    parse_mode: str | None = None,
) -> int:
    fields = {"chat_id": str(chat_id)}
    if caption:
        fields["caption"] = caption
    if parse_mode:
        fields["parse_mode"] = parse_mode
    if silent:
        fields["disable_notification"] = "true"
    return message_id_from_result(_api_post_multipart(token, "sendPhoto", fields, {"photo": file_path}))


def send_video(
    token: str,
    chat_id,
    file_path: Path,
    caption: str | None = None,
    silent: bool = False,
    width: int | None = None,
    height: int | None = None,
    duration: int | None = None,
    thumbnail: Path | None = None,
    parse_mode: str | None = None,
) -> int:
    # supports_streaming + dimensions + an explicit thumbnail make Telegram play
    # the video inline with a preview instead of a download-only file.
    fields = {"chat_id": str(chat_id), "supports_streaming": "true"}
    if caption:
        fields["caption"] = caption
    if parse_mode:
        fields["parse_mode"] = parse_mode
    if silent:
        fields["disable_notification"] = "true"
    if width:
        fields["width"] = str(width)
    if height:
        fields["height"] = str(height)
    if duration:
        fields["duration"] = str(duration)
    files = {"video": file_path}
    if thumbnail:
        files["thumb"] = thumbnail
        fields["thumbnail"] = "attach://thumb"
    return message_id_from_result(_api_post_multipart(token, "sendVideo", fields, files))


def send_media_file(
    token: str,
    chat_id,
    file_path: Path,
    caption: str | None = None,
    silent: bool = False,
    parse_mode: str | None = None,
) -> int:
    mime_type, _ = mimetypes.guess_type(str(file_path))
    suffix = file_path.suffix.lower()

    if suffix == ".gif" or (mime_type and "gif" in mime_type):
        fields = {"chat_id": str(chat_id)}
        if caption:
            fields["caption"] = caption
        if parse_mode:
            fields["parse_mode"] = parse_mode
        if silent:
            fields["disable_notification"] = "true"
        return message_id_from_result(_api_post_multipart(token, "sendAnimation", fields, {"animation": file_path}))
    if mime_type and mime_type.startswith("video"):
        file_path = media.ensure_faststart(file_path)
        meta = media.video_metadata(file_path)
        thumb = media.make_thumbnail(file_path)
        try:
            return send_video(
                token,
                chat_id,
                file_path,
                caption,
                silent,
                width=meta.get("width"),
                height=meta.get("height"),
                duration=meta.get("duration"),
                thumbnail=thumb,
                parse_mode=parse_mode,
            )
        finally:
            if thumb:
                thumb.unlink(missing_ok=True)
    if mime_type and mime_type.startswith("image"):
        return send_photo(token, chat_id, file_path, caption, silent, parse_mode=parse_mode)
    fields = {"chat_id": str(chat_id)}
    if caption:
        fields["caption"] = caption
    if parse_mode:
        fields["parse_mode"] = parse_mode
    if silent:
        fields["disable_notification"] = "true"
    return message_id_from_result(_api_post_multipart(token, "sendDocument", fields, {"document": file_path}))


def delete_message(token: str, chat_id, message_id: int) -> None:
    _api_post_json(token, "deleteMessage", {"chat_id": chat_id, "message_id": int(message_id)})
