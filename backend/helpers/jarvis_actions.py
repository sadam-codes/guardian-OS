import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from helpers.jarvis_gui import (
    minimize_all_windows,
    powershell_minimize_all,
    powershell_screenshot,
    powershell_volume_down,
    powershell_volume_mute,
    powershell_volume_up,
    screenshot_to_file,
    volume_down,
    volume_mute,
    volume_up,
)
from helpers.jarvis_local import launch_shell, resolve_existing_path
from helpers.jarvis_playwright import jarvis_browser_goto, jarvis_youtube_play
from helpers.jarvis_web import google_search_url, looks_like_web_search, resolve_web_open
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


def _require_os() -> JarvisActionResult | None:
    if not ALLOW_OS_CONTROL:
        return JarvisActionResult(False, "OS control is disabled.", "blocked")
    return None


def _browse(url: str) -> tuple[bool, str | None]:
    ok, note = jarvis_browser_goto(url)
    return ok, note


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
        "I can open apps, folders, and files on this PC, open Terminal or PowerShell, open websites, "
        "search Google and YouTube, change volume, lock the PC, and take screenshots. "
        "Say the full path or drive (for example open C drive) for local items. "
        "Websites and Google search use Playwright (install: pip install playwright && playwright install chromium). "
        "YouTube songs: Playwright opens results and clicks the first video to play. "
        "Volume, desktop, and screenshots use PyAutoGUI when available. "
        "I cannot control other desktop apps in depth.",
        "help",
    )


def _action_youtube_search(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    query = (intent.slots.get("query") or "").strip().strip("'\"")
    if not query:
        return JarvisActionResult(False, "Which song should I search on YouTube?", "youtube_search")
    ok, note = jarvis_youtube_play(query)
    msg = f"Playing {query} on YouTube."
    if note:
        msg = f"{msg} {note}"
    if not ok:
        return JarvisActionResult(False, note or "Could not open YouTube.", "youtube_search", target_label=query)
    return JarvisActionResult(True, msg, "youtube_search", target_label=query)


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


def _action_open_path(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    raw = (intent.slots.get("path") or "").strip().strip('"').strip("'")
    if not raw:
        return JarvisActionResult(False, "Which file or folder path should I open?", "open_path")
    path = resolve_existing_path(raw)
    if not path:
        return JarvisActionResult(False, f"I cannot find that path: {raw}", "open_path")
    try:
        os.startfile(path)  # noqa: S606
    except OSError:
        return JarvisActionResult(False, f"I could not open: {path}", "open_path")
    return JarvisActionResult(True, f"Opening {path}.", "open_path", target_label=str(path))


def _action_open_terminal(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    shell_raw = (intent.slots.get("shell") or "").strip().lower()
    if "cmd" in shell_raw or "command" in shell_raw:
        pick = "cmd"
    elif "pwsh" in shell_raw or "powershell" in shell_raw:
        pick = "powershell"
    else:
        pick = "wt"
    ok, label = launch_shell(pick)
    if not ok:
        return JarvisActionResult(
            False,
            "Could not start a terminal. Install Windows Terminal or ensure PowerShell is on PATH.",
            "open_terminal",
        )
    return JarvisActionResult(True, f"Opening {label}.", "open_terminal", target_label=label)


def _action_open_app(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    raw = (intent.slots.get("app") or "").strip()
    if not raw:
        return JarvisActionResult(False, "Which app should I open?", "open_app")

    existing = resolve_existing_path(raw)
    if existing:
        try:
            os.startfile(existing)  # noqa: S606
        except OSError:
            return JarvisActionResult(False, f"I could not open: {existing}", "open_path")
        return JarvisActionResult(True, f"Opening {existing}.", "open_path", target_label=str(existing))

    web = resolve_web_open(raw)
    if web:
        url, label = web
        ok, note = _browse(url)
        msg = f"Opening {label}."
        if note:
            msg = f"{msg} {note}"
        if not ok:
            return JarvisActionResult(False, note or f"Could not open {label}.", "open_app", target_label=label)
        return JarvisActionResult(True, msg, "open_app", target_label=label)

    if looks_like_web_search(raw):
        ok, note = _browse(google_search_url(raw))
        if not ok:
            return JarvisActionResult(False, note or "Search failed.", "web_search", target_label=raw)
        m = f"Searching Google for {raw}."
        if note:
            m = f"{m} {note}"
        return JarvisActionResult(True, m, "web_search", target_label=raw)

    ok, label = launch_windows_app(raw)
    if not ok:
        if looks_like_web_search(raw):
            ok2, note = _browse(google_search_url(raw))
            if not ok2:
                return JarvisActionResult(False, note or "Search failed.", "web_search", target_label=raw)
            m = f"Searching Google for {raw}."
            if note:
                m = f"{m} {note}"
            return JarvisActionResult(True, m, "web_search", target_label=raw)
        return JarvisActionResult(
            False,
            f"I could not find an app named {raw}. Say the exact Start menu name or a full path.",
            "open_app",
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
    ok, note = _browse(url)
    if not ok:
        return JarvisActionResult(False, note or "Could not open URL.", "open_url", target_label=url)
    msg = f"Opening {url}."
    if note:
        msg = f"{msg} {note}"
    return JarvisActionResult(True, msg, "open_url", target_label=url)


def _action_web_search(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    query = intent.slots.get("query", "").strip()
    if not query:
        return JarvisActionResult(False, "What should I search for?", "web_search")
    ok, note = _browse(google_search_url(query))
    if not ok:
        return JarvisActionResult(False, note or "Search failed.", "web_search", target_label=query)
    msg = f"Searching Google for {query}."
    if note:
        msg = f"{msg} {note}"
    return JarvisActionResult(True, msg, "web_search", target_label=query)


def _action_open_url_search(intent: JarvisIntent) -> JarvisActionResult:
    return _action_web_search(
        JarvisIntent(intent="web_search", confidence=intent.confidence, slots=intent.slots)
    )


def _action_open_folder(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    path_slot = (intent.slots.get("path") or "").strip()
    if path_slot:
        return _action_open_path(
            JarvisIntent(intent="open_path", confidence=intent.confidence, slots={"path": path_slot})
        )
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
    try:
        volume_up()
        return JarvisActionResult(True, "Turning volume up.", "volume_up")
    except Exception:
        powershell_volume_up()
        return JarvisActionResult(True, "Turning volume up (fallback).", "volume_up")


def _action_volume_down(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    try:
        volume_down()
        return JarvisActionResult(True, "Turning volume down.", "volume_down")
    except Exception:
        powershell_volume_down()
        return JarvisActionResult(True, "Turning volume down (fallback).", "volume_down")


def _action_volume_mute(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    try:
        volume_mute()
        return JarvisActionResult(True, "Toggling mute.", "volume_mute")
    except Exception:
        powershell_volume_mute()
        return JarvisActionResult(True, "Toggling mute (fallback).", "volume_mute")


def _action_minimize_all(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    try:
        minimize_all_windows()
        return JarvisActionResult(True, "Showing the desktop.", "minimize_all")
    except Exception:
        powershell_minimize_all()
        return JarvisActionResult(True, "Showing the desktop (fallback).", "minimize_all")


def _action_screenshot(_: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    folder = Path.home() / "Pictures" / "GuardianScreenshots"
    folder.mkdir(parents=True, exist_ok=True)
    name = folder / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    try:
        screenshot_to_file(name)
        return JarvisActionResult(True, "Screenshot saved.", "screenshot")
    except Exception:
        powershell_screenshot(name)
        return JarvisActionResult(True, "Screenshot saved (fallback).", "screenshot")


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
    "open_path": _action_open_path,
    "open_terminal": _action_open_terminal,
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
