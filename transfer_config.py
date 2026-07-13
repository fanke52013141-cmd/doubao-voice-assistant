"""Shared limits, storage paths, and phone-access credentials."""
from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlencode


APP_DATA_FOLDER = "VoiceInputAssistant"
PHONE_ACCESS_COOKIE = "voice_assistant_access"
PHONE_ACCESS_TOKEN_FILE = "phone-access-token.txt"
PHONE_ACCESS_COOKIE_SECONDS = 30 * 24 * 60 * 60

MAX_TRANSFER_FILE_BYTES = 200 * 1024 * 1024
MAX_TRANSFER_SELECTION_BYTES = 210 * 1024 * 1024
MAX_TRANSFER_REQUEST_BYTES = 220 * 1024 * 1024
MAX_SHARED_FILE_BYTES = 2 * 1024 * 1024 * 1024
MESSAGE_RETENTION_SECONDS = 30 * 24 * 60 * 60

ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mov", ".m4v"})
ALLOWED_IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif",
})
BLOCKED_TRANSFER_EXTENSIONS = frozenset({
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse", ".msi",
    ".scr", ".dll", ".sys", ".reg", ".lnk", ".url", ".hta",
})

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}")


def app_data_root() -> Path:
    fallback = os.path.dirname(os.path.abspath(__file__))
    root = Path(os.environ.get("APPDATA", fallback)) / APP_DATA_FOLDER
    root.mkdir(parents=True, exist_ok=True)
    return root


def phone_access_token_path() -> Path:
    return app_data_root() / PHONE_ACCESS_TOKEN_FILE


def get_phone_access_token() -> str:
    """Return a stable local secret used to pair phone browsers with the PC."""
    path = phone_access_token_path()
    try:
        current = path.read_text(encoding="ascii").strip()
        if _TOKEN_PATTERN.fullmatch(current):
            return current
    except OSError:
        pass

    token = secrets.token_urlsafe(32)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(token, encoding="ascii")
    os.replace(temporary, path)
    return token


def phone_access_url(ip_address: str, port: int = 56789) -> str:
    query = urlencode({"token": get_phone_access_token()})
    return f"http://{ip_address}:{port}/?{query}"
