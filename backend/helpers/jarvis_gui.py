"""Jarvis desktop automation via PyAutoGUI (volume, desktop, screenshots)."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore[misc, assignment]


def _gui_ok() -> bool:
    return os.getenv("JARVIS_USE_PYAUTOGUI", "true").lower() in ("1", "true", "yes")


def _configure() -> None:
    if pyautogui is None:
        return
    pyautogui.PAUSE = 0.05
    pyautogui.FAILSAFE = os.getenv("JARVIS_PYAUTOGUI_FAILSAFE", "true").lower() in ("1", "true", "yes")


_configure()


def volume_up() -> None:
    if pyautogui is None or not _gui_ok():
        raise RuntimeError("pyautogui is disabled or not installed")
    pyautogui.press("volumeup")


def volume_down() -> None:
    if pyautogui is None or not _gui_ok():
        raise RuntimeError("pyautogui is disabled or not installed")
    pyautogui.press("volumedown")


def volume_mute() -> None:
    if pyautogui is None or not _gui_ok():
        raise RuntimeError("pyautogui is disabled or not installed")
    pyautogui.press("volumemute")


def minimize_all_windows() -> None:
    if pyautogui is None or not _gui_ok():
        raise RuntimeError("pyautogui is disabled or not installed")
    pyautogui.hotkey("win", "d")


def screenshot_to_file(path: Path) -> None:
    if pyautogui is None or not _gui_ok():
        raise RuntimeError("pyautogui is disabled or not installed")
    path.parent.mkdir(parents=True, exist_ok=True)
    img = pyautogui.screenshot()
    img.save(str(path))


def powershell_volume_up() -> None:
    """Fallback when PyAutoGUI is unavailable."""
    import subprocess

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"],
        check=False,
        capture_output=True,
    )


def powershell_volume_down() -> None:
    import subprocess

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"],
        check=False,
        capture_output=True,
    )


def powershell_volume_mute() -> None:
    import subprocess

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
        check=False,
        capture_output=True,
    )


def powershell_minimize_all() -> None:
    import subprocess

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll()"],
        check=False,
        capture_output=True,
    )


def powershell_screenshot(path: Path) -> None:
    import subprocess
    from datetime import datetime

    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object { "
        f"$bmp = New-Object Drawing.Bitmap $_.Bounds.Width, $_.Bounds.Height; "
        f"$g = [Drawing.Graphics]::FromImage($bmp); "
        f"$g.CopyFromScreen($_.Bounds.Location, [Drawing.Point]::Empty, $_.Bounds.Size); "
        f"$bmp.Save('{path}'); $g.Dispose(); $bmp.Dispose() }}"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False, capture_output=True)
