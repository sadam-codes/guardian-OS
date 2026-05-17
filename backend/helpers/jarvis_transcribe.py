"""Transcribe mic audio with Groq Whisper (works when browser SpeechRecognition fails)."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"

# Whisper often hallucinates these on silence / noise — never treat as user commands.
# Only block phrases Whisper invents on silence/noise — not real short commands.
_HALLUCINATION_EXACT = frozenset(
    {
        "thank you",
        "thanks",
        "thank you.",
        "thanks.",
        "subtitle",
        "subtitles",
        "thanks for watching",
        "thank you for watching",
        "please subscribe",
        "subscribe",
        "music",
        "applause",
        "silence",
        "blank audio",
        ".",
        "..",
        "...",
    }
)

_WHISPER_PROMPT = (
    "Short spoken commands to a Windows PC assistant named Guardian. "
    "Examples: open chrome, open visual studio code, open C drive and create folder sadam, "
    "run backend, what time is it, lock the computer. "
    "Roman Urdu mixed with English is OK. Transcribe only what the user actually said."
)


def _api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def transcribe_enabled() -> bool:
    return bool(_api_key())


def is_likely_hallucination(text: str, *, audio_bytes: int = 0) -> bool:
    """True if transcript is a known Whisper false positive on quiet audio."""
    if not text or not text.strip():
        return True
    t = re.sub(r"\s+", " ", text.lower().strip())
    t = t.strip(".,!?;:\"'")
    if t in _HALLUCINATION_EXACT:
        return True
    # Real speech with enough audio — keep short commands like "ok", "hi", "lock".
    if audio_bytes >= 3000 and len(t) >= 2:
        return False
    if len(t) <= 1:
        return True
    for phrase in (
        "thanks for watching",
        "thank you for watching",
        "please subscribe",
        "subtitles by",
        "subtitle by",
        "www.",
        "http",
    ):
        if phrase in t:
            return True
    return False


def sanitize_transcript(text: str, *, audio_bytes: int = 0) -> str | None:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return None
    if is_likely_hallucination(cleaned, audio_bytes=audio_bytes):
        return None
    return cleaned


def transcribe_audio_bytes(data: bytes, *, content_type: str = "audio/webm") -> str | None:
    if not data:
        return None
    if not transcribe_enabled():
        return None

    ext = "webm"
    if "wav" in content_type:
        ext = "wav"
    elif "mp4" in content_type or "m4a" in content_type:
        ext = "m4a"
    elif "ogg" in content_type:
        ext = "ogg"

    boundary = f"----Guardian{uuid.uuid4().hex}"
    model = os.getenv("GROQ_WHISPER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    lang = os.getenv("GROQ_WHISPER_LANGUAGE", "en").strip()

    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    add_field("model", model)
    if lang:
        add_field("language", lang)
    add_field("response_format", "json")
    add_field("temperature", "0")
    add_field("prompt", os.getenv("GROQ_WHISPER_PROMPT", _WHISPER_PROMPT))

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="voice.{ext}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)
    req = urllib.request.Request(
        GROQ_TRANSCRIBE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "guardian-os-jarvis/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        raw = (payload.get("text") or "").strip()
        logger.info("Whisper raw (%d bytes): %r", len(data), raw[:120])
        return sanitize_transcript(raw, audio_bytes=len(data))
    except urllib.error.HTTPError as exc:
        body_err = exc.read().decode("utf-8", errors="replace")[:400]
        logger.warning("Groq transcribe HTTP %s: %s", exc.code, body_err or exc.reason)
        return None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Groq transcribe error: %s", exc)
        return None
