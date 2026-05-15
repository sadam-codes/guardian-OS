import os
import subprocess
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from helpers.jarvis_web import google_search_url, looks_like_web_search, resolve_web_open, youtube_search_url
from helpers.jarvis_windows import launch_windows_app
from schemas.jarvis import JarvisIntent

ALLOW_OS_CONTROL = os.getenv("JARVIS_ALLOW_OS", "true").lower() in ("1", "true", "yes")

_FOLDER_MAP = {
    "desktop": Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "downloads": Path.home() / "Downloads",
    "home": Path.home(),
    "pictures": Path.home() / "Pictures",
}


@dataclass
class JarvisActionResult:
    success: bool
    message: str
    action: str
    target_label: str | None = None


def _powershell(script: str) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
    )


def _require_os() -> JarvisActionResult | None:
    if not ALLOW_OS_CONTROL:
        return JarvisActionResult(False, "OS control is disabled.", "blocked")
    return None


def _action_greet(_: JarvisIntent) -> JarvisActionResult:
    hour = datetime.now().hour
    period = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    return JarvisActionResult(True, f"Good {period}. How can I help you?", "greet")


def _action_time(_: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(True, f"The time is {datetime.now().strftime('%I:%M %p')}.", "time")


def _action_date(_: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(
        True, f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.", "date"
    )


def _action_help(_: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(
        True,
        "I can open apps and websites, search Google and YouTube, change volume, lock the PC, and take screenshots. "
        "I cannot click inside apps or control Netflix, games, etc. Say: open YouTube and play song NAME.",
        "help",
    )


def _action_youtube_search(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    query = (intent.slots.get("query") or "").strip().strip("'\"")
    if not query:
        return JarvisActionResult(False, "Which song should I search on YouTube?", "youtube_search")
    webbrowser.open(youtube_search_url(query))
    return JarvisActionResult(
        True,
        f"Opening YouTube search for {query}.",
        "youtube_search",
        target_label=query,
    )


def _action_acknowledge(_: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(True, "Understood.", "acknowledge")


def _action_cancel(_: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(True, "Cancelled.", "cancel")


def _action_unknown(intent: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(
        False,
        "I don't know that command. Say help for what I can do.",
        "unknown",
    )


def _action_open_app(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    raw = (intent.slots.get("app") or "").strip()
    if not raw:
        return JarvisActionResult(False, "Which app should I open?", "open_app")

    web = resolve_web_open(raw)
    if web:
        url, label = web
        webbrowser.open(url)
        return JarvisActionResult(True, f"Opening {label}.", "open_app", target_label=label)

    if looks_like_web_search(raw):
        webbrowser.open(google_search_url(raw))
        return JarvisActionResult(
            True,
            f"Searching Google for {raw}.",
            "web_search",
            target_label=raw,
        )

    ok, label = launch_windows_app(raw)
    if not ok:
        webbrowser.open(google_search_url(raw))
        return JarvisActionResult(
            True,
            f"Searching Google for {raw}.",
            "web_search",
            target_label=raw,
        )

    return JarvisActionResult(True, f"Opening {label}.", "open_app", target_label=label)


def _action_open_url(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    url = intent.slots.get("url", "").strip()
    if not url:
        return JarvisActionResult(False, "No URL provided.", "open_url")
    webbrowser.open(url)
    return JarvisActionResult(True, f"Opening {url}.", "open_url", target_label=url)


def _action_web_search(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    query = intent.slots.get("query", "").strip()
    if not query:
        return JarvisActionResult(False, "What should I search for?", "web_search")
    webbrowser.open(google_search_url(query))
    return JarvisActionResult(
        True, f"Searching Google for {query}.", "web_search", target_label=query
    )


def _action_open_url_search(intent: JarvisIntent) -> JarvisActionResult:
    return _action_web_search(
        JarvisIntent(intent="web_search", confidence=intent.confidence, slots=intent.slots)
    )


def _action_open_folder(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    folder_key = (intent.slots.get("folder") or "").lower()
    path = _FOLDER_MAP.get(folder_key)
    if not path or not path.exists():
        return JarvisActionResult(False, f"Folder '{folder_key}' not found.", "open_folder")
    os.startfile(path)  # noqa: S606
    return JarvisActionResult(
        True, f"Opening {folder_key}.", "open_folder", target_label=folder_key
    )


def _action_lock(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
    return JarvisActionResult(True, "Locking your computer.", "lock")


def _action_volume_up(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    _powershell("(New-Object -ComObject WScript.Shell).SendKeys([char]175)")
    return JarvisActionResult(True, "Turning volume up.", "volume_up")


def _action_volume_down(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    _powershell("(New-Object -ComObject WScript.Shell).SendKeys([char]174)")
    return JarvisActionResult(True, "Turning volume down.", "volume_down")


def _action_volume_mute(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    _powershell("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")
    return JarvisActionResult(True, "Toggling mute.", "volume_mute")


def _action_minimize_all(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    _powershell("(New-Object -ComObject Shell.Application).MinimizeAll()")
    return JarvisActionResult(True, "Showing the desktop.", "minimize_all")


def _action_screenshot(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    folder = Path.home() / "Pictures" / "GuardianScreenshots"
    folder.mkdir(parents=True, exist_ok=True)
    name = folder / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    _powershell(
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object {{ "
        f"$bmp = New-Object Drawing.Bitmap $_.Bounds.Width, $_.Bounds.Height; "
        f"$g = [Drawing.Graphics]::FromImage($bmp); "
        f"$g.CopyFromScreen($_.Bounds.Location, [Drawing.Point]::Empty, $_.Bounds.Size); "
        f"$bmp.Save('{name}'); $g.Dispose(); $bmp.Dispose() }}"
    )
    return JarvisActionResult(True, "Screenshot saved.", "screenshot")


def _action_shutdown(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    subprocess.run(["shutdown", "/s", "/t", "15"], check=False)
    return JarvisActionResult(True, "Shutting down in 15 seconds.", "shutdown")


def _action_restart(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    subprocess.run(["shutdown", "/r", "/t", "15"], check=False)
    return JarvisActionResult(True, "Restarting in 15 seconds.", "restart")


_HANDLERS: dict[str, Callable[[JarvisIntent], JarvisActionResult]] = {
    "greet": _action_greet,
    "acknowledge": _action_acknowledge,
    "cancel": _action_cancel,
    "help": _action_help,
    "time": _action_time,
    "date": _action_date,
    "open_app": _action_open_app,
    "open_url": _action_open_url,
    "open_url_search": _action_open_url_search,
    "web_search": _action_web_search,
    "youtube_search": _action_youtube_search,
    "open_folder": _action_open_folder,
    "lock": _action_lock,
    "volume_up": _action_volume_up,
    "volume_down": _action_volume_down,
    "volume_mute": _action_volume_mute,
    "minimize_all": _action_minimize_all,
    "screenshot": _action_screenshot,
    "shutdown": _action_shutdown,
    "restart": _action_restart,
    "unknown": _action_unknown,
}


def execute_jarvis_intent(intent: JarvisIntent) -> JarvisActionResult:
    handler = _HANDLERS.get(intent.intent, _action_unknown)
    return handler(intent)
