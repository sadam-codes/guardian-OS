"""Type text into the focused app (WhatsApp, Instagram, etc.) — not file editors."""

from __future__ import annotations

import os
import subprocess
import time

from helpers.jarvis_focus import focus_app_by_name
from helpers.jarvis_messaging import (
    is_instagram_app,
    is_messaging_app,
    looks_like_call_request,
    looks_like_voice_message,
    parse_message_slots,
    resolve_recipient_pronoun,
)
from helpers.jarvis_instagram import instagram_send_message
from schemas.jarvis import JarvisActionResult, JarvisIntent, JarvisSessionContext

ALLOW_OS_CONTROL = os.getenv("JARVIS_ALLOW_OS", "true").lower() in ("1", "true", "yes")
_TYPE_DELAY_SEC = float(os.getenv("JARVIS_TYPE_DELAY_SEC", "2.0"))


def _require_os() -> JarvisActionResult | None:
    if not ALLOW_OS_CONTROL:
        return JarvisActionResult(False, "OS control is disabled.", "blocked")
    return None


def _gui_ready() -> bool:
    try:
        from helpers.jarvis_gui import _gui_ok  # noqa: PLC0415

        if not _gui_ok():
            return False
        import pyautogui  # noqa: PLC0415

        return pyautogui is not None
    except Exception:
        return False


def _paste_text(text: str) -> None:
    import base64

    import pyautogui  # noqa: PLC0415

    if not text:
        return
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"$t = [System.Text.Encoding]::UTF8.GetString("
                f"[Convert]::FromBase64String('{b64}')); "
                "Set-Clipboard -Value $t"
            ),
        ],
        check=False,
        capture_output=True,
    )
    pyautogui.hotkey("ctrl", "v")


def _type_keys(text: str) -> None:
    import pyautogui  # noqa: PLC0415

    if not text:
        return
    if text.isascii():
        pyautogui.typewrite(text, interval=0.02)
    else:
        _paste_text(text)


def _open_chat_with_recipient(recipient: str) -> None:
    import pyautogui  # noqa: PLC0415

    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.4)
    _type_keys(recipient)
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(0.8)


def action_type_text(
    intent: JarvisIntent,
    ctx: JarvisSessionContext | None = None,
) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked

    if not _gui_ready():
        return JarvisActionResult(
            False,
            "Typing in apps needs PyAutoGUI enabled on this PC.",
            "type_text",
        )

    raw = (intent.slots.get("content") or intent.slots.get("text") or "").strip()
    user_blob = (intent.slots.get("user_text") or raw or "").strip()

    if looks_like_voice_message(user_blob):
        from helpers.jarvis_voice_message import action_send_voice_message

        return action_send_voice_message(intent, ctx)

    if looks_like_call_request(user_blob):
        from helpers.jarvis_calls import action_start_call

        return action_start_call(intent, ctx)

    recipient = (intent.slots.get("recipient") or "").strip()
    app = (
        intent.slots.get("app")
        or (ctx.last_app if ctx else None)
        or "WhatsApp"
    ).strip()

    send_flag = (intent.slots.get("send") or "").strip().lower()
    should_send = send_flag in ("1", "true", "yes")
    if send_flag in ("0", "false", "no"):
        should_send = False

    if not recipient:
        parsed_recipient, parsed_body, parsed_send = parse_message_slots(raw)
        if parsed_recipient:
            recipient = parsed_recipient
            raw = parsed_body
        if parsed_send:
            should_send = True

    recipient = resolve_recipient_pronoun(recipient, ctx)
    message = raw.strip()
    if not message and not recipient:
        return JarvisActionResult(False, "What message should I type?", "type_text")

    if is_instagram_app(app):
        if message and (not recipient or " to " in message.lower()):
            parsed_recipient, parsed_body, parsed_send = parse_message_slots(message)
            if parsed_recipient:
                recipient = parsed_recipient
                message = parsed_body
            if parsed_send:
                should_send = True
        ok, err = instagram_send_message(recipient, message, send=should_send)
        label = "Instagram"
        if not ok:
            return JarvisActionResult(False, err or "Could not send on Instagram.", "type_text")
        if recipient and message:
            msg = (
                f"Sent your message to {recipient} on {label}."
                if should_send
                else f"Opened {label}, found {recipient}, and typed your message."
            )
        elif recipient:
            msg = f"Opened {label} and searched for {recipient}."
        else:
            msg = f"Typed your message in {label}."
        return JarvisActionResult(True, msg, "type_text", target_label=label)

    if is_messaging_app(app):
        focus_app_by_name(app)
        time.sleep(_TYPE_DELAY_SEC)

    if recipient and is_messaging_app(app):
        _open_chat_with_recipient(recipient)

    if message:
        _type_keys(message)
        if should_send and is_messaging_app(app):
            import pyautogui  # noqa: PLC0415

            time.sleep(0.35)
            pyautogui.press("enter")

    label = app or "the app"
    if recipient and message:
        if should_send:
            msg = f"Sent your message to {recipient} on {label}."
        else:
            msg = f"Opened {label}, found {recipient}, and typed your message."
    elif recipient:
        msg = f"Opened {label} and searched for {recipient}."
    else:
        msg = f"Typed your message in {label}."
    return JarvisActionResult(True, msg, "type_text", target_label=label)
