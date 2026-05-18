"""Bring launched Windows apps to the foreground after Jarvis opens them."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

_FOCUS_SCRIPT = r"""
param([string]$HintsJson, [int]$TimeoutSec = 8)

$Hints = @($HintsJson | ConvertFrom-Json) | Where-Object { $_ -and $_.ToString().Trim() }
if (-not $Hints -or $Hints.Count -eq 0) { exit 1 }

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class JarvisWin32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    public const int SW_RESTORE = 9;
}
"@

$deadline = (Get-Date).AddSeconds([Math]::Max(2, $TimeoutSec))
$shell = New-Object -ComObject WScript.Shell

function Focus-ProcessWindow($proc) {
    if (-not $proc -or $proc.MainWindowHandle -eq [IntPtr]::Zero) { return $false }
    $hwnd = $proc.MainWindowHandle
    if ([JarvisWin32]::IsIconic($hwnd)) {
        [void][JarvisWin32]::ShowWindow($hwnd, [JarvisWin32]::SW_RESTORE)
    }
    [void][JarvisWin32]::SetForegroundWindow($hwnd)
    try { return $shell.AppActivate($proc.Id) } catch { return $true }
}

while ((Get-Date) -lt $deadline) {
    foreach ($hint in $Hints) {
        $h = $hint.ToString().Trim()
        if (-not $h) { continue }

        try {
            if ($shell.AppActivate($h)) { exit 0 }
        } catch {}

        $proc = Get-Process | Where-Object {
            $_.MainWindowHandle -ne [IntPtr]::Zero -and
            $_.MainWindowTitle -like "*$h*"
        } | Sort-Object StartTime -Descending | Select-Object -First 1

        if ($proc -and (Focus-ProcessWindow $proc)) { exit 0 }
    }
    Start-Sleep -Milliseconds 250
}
exit 1
"""

_APP_FOCUS_HINTS: dict[str, list[str]] = {
    "visual studio code": ["Visual Studio Code", "Code"],
    "cursor": ["Cursor"],
    "google chrome": ["Google Chrome", "Chrome"],
    "microsoft edge": ["Microsoft Edge", "Edge"],
    "firefox": ["Mozilla Firefox", "Firefox"],
    "notepad": ["Notepad"],
    "word": ["Word"],
    "excel": ["Excel"],
    "spotify": ["Spotify"],
    "discord": ["Discord"],
    "whatsapp": ["WhatsApp"],
    "zoom": ["Zoom"],
    "microsoft teams": ["Microsoft Teams", "Teams"],
    "windows terminal": ["Windows Terminal"],
    "windows powershell": ["Windows PowerShell", "PowerShell"],
    "powershell": ["PowerShell"],
    "calculator": ["Calculator"],
    "task manager": ["Task Manager"],
    "settings": ["Settings"],
}


def _focus_enabled() -> bool:
    return os.getenv("JARVIS_FOCUS_WINDOWS", "true").lower() in ("1", "true", "yes")


def focus_hints_for_app(name: str) -> list[str]:
    key = " ".join((name or "").strip().split()).lower()
    if key in _APP_FOCUS_HINTS:
        return _APP_FOCUS_HINTS[key]
    clean = (name or "").strip()
    if not clean:
        return []
    parts = clean.split()
    hints = [clean]
    if len(parts) > 1:
        hints.append(parts[-1])
    return hints


def focus_browser_window() -> None:
    channel = os.getenv("JARVIS_PLAYWRIGHT_CHANNEL", "").strip().lower()
    if channel in ("chrome", "msedge", "edge"):
        hints = ["Google Chrome"] if channel == "chrome" else ["Microsoft Edge", "Edge"]
    else:
        hints = ["Chromium", "Google Chrome", "Microsoft Edge", "Chrome"]
    bring_window_to_front(hints, wait_sec=6.0)


def bring_window_to_front(hints: list[str], *, wait_sec: float = 8.0) -> bool:
    if not _focus_enabled() or sys.platform != "win32":
        return False

    cleaned = []
    seen: set[str] = set()
    for hint in hints:
        h = (hint or "").strip()
        if not h or h.lower() in seen:
            continue
        seen.add(h.lower())
        cleaned.append(h)
    if not cleaned:
        return False

    _alt_tab_unlock()
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Sta",
                "-Command",
                _FOCUS_SCRIPT,
                "-HintsJson",
                json.dumps(cleaned),
                "-TimeoutSec",
                str(int(wait_sec)),
            ],
            capture_output=True,
            text=True,
            timeout=wait_sec + 5,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Window focus failed: %s", exc)
        return False


def focus_app_by_name(name: str, *, wait_sec: float = 8.0) -> bool:
    return bring_window_to_front(focus_hints_for_app(name), wait_sec=wait_sec)


def _alt_tab_unlock() -> None:
    """Brief Alt tap so SetForegroundWindow works when the backend is in the background."""
    try:
        from helpers.jarvis_gui import _gui_ok  # noqa: PLC0415

        if not _gui_ok():
            return
        import pyautogui  # noqa: PLC0415

        pyautogui.press("alt")
    except Exception:
        pass
