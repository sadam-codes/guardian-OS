"""WhatsApp voice messages — TTS audio + send (not typed text)."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from helpers.jarvis_whatsapp_ui import focus_whatsapp, open_chat
from helpers.jarvis_messaging import (
    is_instagram_app,
    is_messaging_app,
    parse_message_slots,
    resolve_recipient_pronoun,
)
from schemas.jarvis import JarvisActionResult, JarvisIntent, JarvisSessionContext

logger = logging.getLogger(__name__)

_TYPE_DELAY_SEC = float(os.getenv("JARVIS_TYPE_DELAY_SEC", "2.0"))

_VOICE_HINT = re.compile(
    r"\b("
    r"voice\s*message|voice\s*note|voice\s*msg|audio\s*message|audio\s*note|"
    r"record(?:ed)?\s*message|awaaz|awaz|bol\s*kar|voice\s*pe|mic\s*message"
    r")\b",
    re.I,
)

_SEND_VOICE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"send\s+(?P<recipient>him|her|them)\s+(?:a\s+)?(?P<body>.+?)\s+voice\s+message",
        re.I,
    ),
    re.compile(
        r"send\s+(?:a\s+)?(?P<body>.+?)\s+voice\s+(?:message|note)\s+to\s+(?P<recipient>.+)$",
        re.I,
    ),
    re.compile(
        r"send\s+(?P<recipient>[^.]+?)\s+(?:a\s+)?(?P<body>.+?)\s+voice\s+message",
        re.I,
    ),
]


def wants_voice_message(text: str) -> bool:
    return bool(_VOICE_HINT.search(text or ""))


def parse_voice_message_slots(text: str) -> tuple[str | None, str, bool]:
    """Return (recipient, spoken_text, should_send)."""
    raw = " ".join((text or "").strip().split())
    raw = re.sub(r"^(?:now|please|ok|okay)\s+", "", raw, flags=re.I)
    if not raw:
        return None, "", True

    for pat in _SEND_VOICE_PATTERNS:
        m = pat.search(raw)
        if m:
            recipient = (m.group("recipient") or "").strip()
            body = (m.group("body") or "").strip()
            body = re.sub(r"^(?:a|an|the)\s+", "", body, flags=re.I).strip()
            return recipient or None, body, True

    if wants_voice_message(raw):
        body = re.sub(r"\bvoice\s*(?:message|note|msg)\b", "", raw, flags=re.I)
        body = re.sub(r"^send\s+", "", body, flags=re.I).strip()
        recipient, msg_body, send = parse_message_slots(body)
        if recipient and msg_body:
            return recipient, msg_body, send
        if recipient:
            return recipient, "", send
        return None, body.strip(), True

    return None, "", False


def synthesize_speech_wav(text: str, out_path: Path) -> tuple[bool, str]:
    """Windows built-in TTS → .wav (no extra pip packages)."""
    phrase = text.strip()
    if not phrase:
        return False, "Nothing to speak."

    out_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path = str(out_path.resolve()).replace("'", "''")
    safe_text = phrase.replace("'", "''")

    script = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile('{safe_path}')
$s.Speak('{safe_text}')
$s.Dispose()
Write-Output 'ok'
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return False, "Voice synthesis timed out."
    except OSError as exc:
        return False, f"Could not run speech synthesis: {exc}"

    if proc.returncode != 0 or not out_path.is_file():
        err = (proc.stderr or proc.stdout or "TTS failed").strip()[:200]
        return False, err or "Could not create voice audio."

    return True, str(out_path)


def _paste_path(path: str) -> None:
    import base64

    import pyautogui  # noqa: PLC0415

    b64 = base64.b64encode(path.encode("utf-8")).decode("ascii")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"$t = [System.Text.Encoding]::UTF8.GetString("
                f"[Convert]::FromBase64String('{b64}')); Set-Clipboard -Value $t"
            ),
        ],
        check=False,
        capture_output=True,
    )
    pyautogui.hotkey("ctrl", "v")


def _send_audio_via_attach(file_path: str) -> bool:
    """Attach audio file in WhatsApp Desktop and press send."""
    import pyautogui  # noqa: PLC0415

    from helpers.jarvis_whatsapp_ui import whatsapp_window_rect

    rect = whatsapp_window_rect()
    if not rect:
        return False

    left, top, width, height = rect
    clip_x = left + max(40, int(width * 0.11))
    clip_y = top + max(40, int(height * 0.86))

    pyautogui.click(clip_x, clip_y)
    time.sleep(0.7)

    # Attach menu: navigate to document / file picker (layout varies by version)
    for _ in range(2):
        pyautogui.press("down")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(1.0)

    # File dialog — file name field
    pyautogui.hotkey("alt", "n")
    time.sleep(0.25)
    _paste_path(str(Path(file_path).resolve()))
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.8)
    pyautogui.press("enter")
    return True


def _send_audio_via_mic_and_playback(file_path: str) -> bool:
    """Click mic, play TTS during recording (needs Stereo Mix / virtual cable)."""
    import pyautogui  # noqa: PLC0415

    from helpers.jarvis_whatsapp_ui import whatsapp_window_rect

    rect = whatsapp_window_rect()
    if not rect:
        return False

    left, top, width, height = rect
    mic_x = left + int(width * 0.90)
    mic_y = top + int(height * 0.88)

    pyautogui.click(mic_x, mic_y)
    time.sleep(0.4)

    safe = str(Path(file_path).resolve()).replace("'", "''")
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(New-Object System.Media.SoundPlayer '{safe}').PlaySync()",
        ],
        shell=False,
    )
    time.sleep(0.3)
    pyautogui.click(mic_x, mic_y)
    time.sleep(0.2)
    pyautogui.press("enter")
    return True


def whatsapp_send_voice_message(
    recipient: str,
    spoken_text: str,
    *,
    prefer_mic: bool = False,
) -> tuple[bool, str]:
    if not spoken_text.strip():
        return False, "What should the voice message say?"

    with tempfile.TemporaryDirectory(prefix="guardian-voice-") as tmp:
        wav = Path(tmp) / "voice_message.wav"
        ok, err = synthesize_speech_wav(spoken_text, wav)
        if not ok:
            return False, err

        focus_whatsapp()
        open_chat(recipient)
        time.sleep(0.6)

        sent = False
        if prefer_mic:
            try:
                sent = _send_audio_via_mic_and_playback(str(wav))
            except Exception as exc:
                logger.warning("Mic voice send failed: %s", exc)

        if not sent:
            try:
                sent = _send_audio_via_attach(str(wav))
            except Exception as exc:
                logger.warning("Attach voice send failed: %s", exc)
                return False, f"Could not send voice on WhatsApp: {exc}"

        if not sent:
            return (
                False,
                "Could not send voice on WhatsApp. Open the chat manually and try again.",
            )

    return True, spoken_text


def action_send_voice_message(
    intent: JarvisIntent,
    ctx: JarvisSessionContext | None = None,
) -> JarvisActionResult:
    from helpers.jarvis_type import _gui_ready, _require_os

    blocked = _require_os()
    if blocked:
        return blocked

    if not _gui_ready():
        return JarvisActionResult(
            False,
            "Voice messages need PyAutoGUI on this PC.",
            "send_voice_message",
        )

    blob = (
        intent.slots.get("user_text")
        or intent.slots.get("content")
        or intent.slots.get("text")
        or ""
    ).strip()
    recipient = (intent.slots.get("recipient") or "").strip()
    spoken = (intent.slots.get("content") or intent.slots.get("text") or "").strip()
    app = (intent.slots.get("app") or (ctx.last_app if ctx else None) or "WhatsApp").strip()

    if not recipient or not spoken:
        pr, pb, _ = parse_voice_message_slots(blob)
        recipient = recipient or (pr or "")
        spoken = spoken or pb

    recipient = resolve_recipient_pronoun(recipient, ctx)
    if not recipient:
        return JarvisActionResult(
            False,
            "Who should I send the voice message to? Say their name or chat with them first.",
            "send_voice_message",
        )

    if not spoken:
        return JarvisActionResult(
            False,
            "What should the voice message say?",
            "send_voice_message",
        )

    if is_instagram_app(app):
        return JarvisActionResult(
            False,
            "Instagram voice messages are not supported yet. Use WhatsApp.",
            "send_voice_message",
        )

    if not is_messaging_app(app):
        app = "WhatsApp"

    prefer_mic = os.getenv("JARVIS_WHATSAPP_VOICE_MIC", "false").lower() in ("1", "true", "yes")
    ok, detail = whatsapp_send_voice_message(recipient, spoken, prefer_mic=prefer_mic)
    if not ok:
        return JarvisActionResult(False, detail, "send_voice_message", target_label=recipient)

    return JarvisActionResult(
        True,
        f"Sent a voice message to {recipient} on WhatsApp saying: {spoken}.",
        "send_voice_message",
        target_label=recipient,
    )
