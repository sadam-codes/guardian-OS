"""Shared WhatsApp Desktop UI automation (chat, window focus, header buttons)."""

from __future__ import annotations

import os
import subprocess
import time

from helpers.jarvis_focus import focus_app_by_name

_TYPE_DELAY_SEC = float(os.getenv("JARVIS_TYPE_DELAY_SEC", "2.0"))


def focus_whatsapp() -> None:
    focus_app_by_name("WhatsApp")
    time.sleep(_TYPE_DELAY_SEC)


def whatsapp_window_rect() -> tuple[int, int, int, int] | None:
    try:
        import pygetwindow as gw  # noqa: PLC0415
    except ImportError:
        return None

    for win in gw.getAllWindows():
        title = (win.title or "").lower()
        if "whatsapp" in title and win.width > 200 and win.height > 200:
            try:
                win.activate()
            except Exception:
                pass
            time.sleep(0.35)
            return win.left, win.top, win.width, win.height
    return None


def open_chat(recipient: str) -> None:
    import pyautogui  # noqa: PLC0415

    from helpers.jarvis_type import _open_chat_with_recipient

    _open_chat_with_recipient(recipient)


def click_header_button(
    *,
    x_ratio: float,
    y_ratio: float,
) -> bool:
    """Click a point in the WhatsApp window (ratios 0–1 from top-left)."""
    import pyautogui  # noqa: PLC0415

    rect = whatsapp_window_rect()
    if not rect:
        return False

    left, top, width, height = rect
    x = left + int(width * x_ratio)
    y = top + int(height * y_ratio)
    pyautogui.click(x, y)
    return True


def click_audio_call_button() -> bool:
    x = float(os.getenv("JARVIS_WHATSAPP_AUDIO_CALL_X", "0.84"))
    y = float(os.getenv("JARVIS_WHATSAPP_AUDIO_CALL_Y", "0.10"))
    return click_header_button(x_ratio=x, y_ratio=y)


def click_video_call_button() -> bool:
    x = float(os.getenv("JARVIS_WHATSAPP_VIDEO_CALL_X", "0.90"))
    y = float(os.getenv("JARVIS_WHATSAPP_VIDEO_CALL_Y", "0.10"))
    return click_header_button(x_ratio=x, y_ratio=y)
