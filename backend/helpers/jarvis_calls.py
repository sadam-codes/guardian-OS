"""Start audio / video calls in WhatsApp (and similar apps)."""

from __future__ import annotations

import re
import time

from helpers.jarvis_messaging import (
    is_instagram_app,
    is_messaging_app,
    looks_like_voice_message,
    resolve_recipient_pronoun,
)
from helpers.jarvis_whatsapp_ui import (
    click_audio_call_button,
    click_video_call_button,
    focus_whatsapp,
    open_chat,
)
from schemas.jarvis import JarvisActionResult, JarvisIntent, JarvisSessionContext

_VIDEO_CALL = re.compile(r"\bvideo\s*call\b", re.I)
_AUDIO_CALL = re.compile(
    r"\b(audio\s*call|voice\s*call|phone\s*call)\b",
    re.I,
)
_GENERIC_CALL = re.compile(
    r"\b(?:start\s+)?(?:a\s+)?call\b",
    re.I,
)

_CALL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?:start\s+)?(?:a\s+)?(?P<kind>video|audio|voice|phone)\s+call\s+"
            r"(?:with\s+)?(?P<recipient>.+?)(?:\s+on\s+whatsapp)?\s*$",
            re.I,
        ),
        "kind",
    ),
    (
        re.compile(
            r"(?:start\s+)?(?:a\s+)?(?P<kind>video|audio|voice|phone)\s+call\s+"
            r"(?:to\s+)?(?P<recipient>him|her|them)\b",
            re.I,
        ),
        "kind",
    ),
    (
        re.compile(
            r"call\s+(?P<recipient>him|her|them)\s+"
            r"(?:on\s+)?(?:whatsapp\s+)?(?:with\s+)?(?P<kind>video|audio)?",
            re.I,
        ),
        "kind",
    ),
    (
        re.compile(
            r"call\s+(?P<recipient>.+?)\s+on\s+whatsapp",
            re.I,
        ),
        "",
    ),
    (
        re.compile(
            r"(?:whatsapp\s+)?(?P<kind>video|audio|voice)\s+call\s+"
            r"(?P<recipient>him|her|them|\w+(?:\s+\w+)*)",
            re.I,
        ),
        "kind",
    ),
]


def wants_call(text: str) -> bool:
    t = text or ""
    if looks_like_voice_message(t):
        return False
    if _VIDEO_CALL.search(t) or _AUDIO_CALL.search(t):
        return True
    if _GENERIC_CALL.search(t) and is_messaging_context(t):
        return True
    return False


def is_messaging_context(text: str) -> bool:
    low = text.lower()
    return any(
        k in low
        for k in ("whatsapp", "him", "her", "them", "call ", "video call", "audio call")
    )


def _normalize_call_kind(kind: str | None, text: str) -> str:
    if kind:
        k = kind.lower().strip()
        if k in ("video",):
            return "video"
        if k in ("audio", "voice", "phone"):
            return "audio"
    if _VIDEO_CALL.search(text):
        return "video"
    return "audio"


def parse_call_slots(text: str) -> tuple[str | None, str]:
    """Return (recipient, call_kind) where call_kind is audio or video."""
    raw = " ".join((text or "").strip().split())
    raw = re.sub(r"^(?:now|please|ok|okay)\s+", "", raw, flags=re.I)
    if not raw:
        return None, "audio"

    for pat, _ in _CALL_PATTERNS:
        m = pat.search(raw)
        if not m:
            continue
        gd = m.groupdict()
        recipient = (gd.get("recipient") or "").strip()
        kind = _normalize_call_kind(gd.get("kind"), raw)
        if recipient:
            return recipient, kind

    if _VIDEO_CALL.search(raw):
        kind = "video"
    else:
        kind = "audio"

    m = re.search(r"call\s+(?:with\s+)?(.+?)(?:\s+on\s+whatsapp)?\s*$", raw, re.I)
    if m:
        return m.group(1).strip(), kind

    return None, kind


def whatsapp_start_call(recipient: str, *, video: bool) -> tuple[bool, str]:
    focus_whatsapp()
    open_chat(recipient)
    time.sleep(0.7)

    ok = click_video_call_button() if video else click_audio_call_button()
    if not ok:
        return (
            False,
            "Could not find WhatsApp call buttons. Open the chat manually, or adjust "
            "JARVIS_WHATSAPP_AUDIO_CALL_X/Y in .env.",
        )

    kind = "video" if video else "audio"
    return True, kind


def action_start_call(
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
            "Calls need PyAutoGUI and WhatsApp Desktop on this PC.",
            "start_call",
        )

    blob = (
        intent.slots.get("user_text")
        or intent.slots.get("content")
        or ""
    ).strip()
    recipient = (intent.slots.get("recipient") or "").strip()
    call_kind = (intent.slots.get("call_type") or intent.slots.get("kind") or "").strip().lower()

    if not recipient or not call_kind:
        pr, pk = parse_call_slots(blob)
        recipient = recipient or (pr or "")
        call_kind = call_kind or pk

    recipient = resolve_recipient_pronoun(recipient, ctx)
    if not recipient:
        return JarvisActionResult(
            False,
            "Who should I call? Say the contact name or message them first so I remember.",
            "start_call",
        )

    app = (intent.slots.get("app") or (ctx.last_app if ctx else None) or "WhatsApp").strip()
    if is_instagram_app(app):
        return JarvisActionResult(
            False,
            "Instagram calls are not supported yet. Use WhatsApp.",
            "start_call",
        )

    if not is_messaging_app(app):
        app = "WhatsApp"

    video = call_kind == "video" or _VIDEO_CALL.search(blob)
    ok, detail = whatsapp_start_call(recipient, video=video)
    if not ok:
        return JarvisActionResult(False, detail, "start_call", target_label=recipient)

    label = "Video" if video else "Audio"
    return JarvisActionResult(
        True,
        f"Starting {label.lower()} call with {recipient} on WhatsApp.",
        "start_call",
        target_label=recipient,
    )
