"""ElevenLabs text-to-speech (bypasses Vapi when their integration fails)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5").strip() or "eleven_turbo_v2_5"


def mask_api_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return "(not set)"
    if len(k) <= 12:
        return f"{k[:4]}…(len={len(k)})"
    return f"{k[:7]}…{k[-4:]} (len={len(k)})"


def elevenlabs_configured() -> bool:
    return bool(ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID)


def elevenlabs_status() -> dict[str, str | bool | int | None]:
    """Safe status for logs/API — never returns full API key."""
    return {
        "configured": elevenlabs_configured(),
        "api_key_set": bool(ELEVENLABS_API_KEY),
        "api_key_masked": mask_api_key(ELEVENLABS_API_KEY),
        "api_key_length": len(ELEVENLABS_API_KEY) if ELEVENLABS_API_KEY else 0,
        "voice_id": ELEVENLABS_VOICE_ID or None,
        "model": ELEVENLABS_MODEL,
    }


def log_elevenlabs_startup() -> None:
    st = elevenlabs_status()
    logger.info(
        "ElevenLabs env: configured=%s key=%s voice_id=%s model=%s",
        st["configured"],
        st["api_key_masked"],
        st["voice_id"],
        st["model"],
    )
    if ELEVENLABS_API_KEY:
        ok, msg = validate_elevenlabs_key()
        if ok:
            logger.info("ElevenLabs API key validation: OK")
        else:
            logger.warning("ElevenLabs API key validation FAILED: %s", msg)


def validate_elevenlabs_key() -> tuple[bool, str]:
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY missing in .env")
        return False, "ELEVENLABS_API_KEY not set in backend .env"
    logger.info("Validating ElevenLabs key %s", mask_api_key(ELEVENLABS_API_KEY))
    url = "https://api.elevenlabs.io/v1/user"
    req = urllib.request.Request(
        url,
        headers={"xi-api-key": ELEVENLABS_API_KEY, "User-Agent": "Guardian-OS/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= getattr(resp, "status", 200) < 300:
                logger.info("ElevenLabs /v1/user → OK")
                return True, "ElevenLabs API key is valid."
            return False, f"ElevenLabs returned status {getattr(resp, 'status', '?')}."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        logger.warning("ElevenLabs /v1/user → HTTP %s: %s", exc.code, detail)
        if exc.code == 401:
            return False, "ElevenLabs API key is invalid (401). Create a new key at elevenlabs.io."
        return False, f"ElevenLabs error {exc.code}: {detail}"
    except urllib.error.URLError as exc:
        logger.warning("ElevenLabs /v1/user unreachable: %s", exc.reason)
        return False, f"Could not reach ElevenLabs: {exc.reason}"


def synthesize_mp3(text: str) -> tuple[bytes | None, str]:
    """Return MP3 bytes or (None, error message)."""
    clean = (text or "").strip()
    if not clean:
        return None, "No text to speak."
    if not elevenlabs_configured():
        return None, "Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in backend .env."

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    payload = json.dumps(
        {
            "text": clean[:2500],
            "model_id": ELEVENLABS_MODEL,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "User-Agent": "Guardian-OS/1.0",
        },
    )
    try:
        logger.info(
            "ElevenLabs TTS: voice=%s model=%s chars=%d key=%s",
            ELEVENLABS_VOICE_ID,
            ELEVENLABS_MODEL,
            len(clean),
            mask_api_key(ELEVENLABS_API_KEY),
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
            logger.info("ElevenLabs TTS → OK (%d bytes mp3)", len(data))
            return data, ""
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        logger.warning("ElevenLabs TTS → HTTP %s: %s", exc.code, detail)
        if exc.code == 401:
            return None, "ElevenLabs key invalid. Fix ELEVENLABS_API_KEY in backend .env."
        return None, f"ElevenLabs TTS failed ({exc.code}): {detail}"
    except urllib.error.URLError as exc:
        logger.warning("ElevenLabs TTS unreachable: %s", exc.reason)
        return None, f"ElevenLabs unreachable: {exc.reason}"
