import os
import shutil
import subprocess
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
from helpers.jarvis_context import resolve_folder_path
from helpers.jarvis_local import launch_shell, resolve_existing_path
from helpers.jarvis_focus import bring_window_to_front, focus_app_by_name
from helpers.jarvis_playwright import jarvis_browser_goto, jarvis_youtube_play
from helpers.jarvis_web import friendly_url_label, google_search_url, looks_like_web_search, resolve_web_open
from helpers.jarvis_nested import (
    action_clear_context,
    action_open_terminal_here,
    action_run_project,
    action_write_text,
)
from helpers.jarvis_type import action_type_text
from helpers.jarvis_calls import action_start_call
from helpers.jarvis_voice_message import action_send_voice_message
from helpers.jarvis_powershell import run_voice_command
from helpers.jarvis_windows import canonical_app_name, launch_windows_app
from schemas.jarvis import JarvisActionResult, JarvisIntent, JarvisSessionContext

ALLOW_OS_CONTROL = os.getenv("JARVIS_ALLOW_OS", "true").lower() in ("1", "true", "yes")


def _is_editor_app(app: str | None) -> bool:
    if not app:
        return False
    low = app.lower()
    return any(x in low for x in ("code", "visual studio", "vs code", "cursor"))

_FOLDER_MAP = {
    "desktop": Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "downloads": Path.home() / "Downloads",
    "home": Path.home(),
    "pictures": Path.home() / "Pictures",
}


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
        "WhatsApp: text messages, voice messages, audio call, and video call. "
        "Nested: open VS Code then write hello world; open WhatsApp then message or call a contact. "
        "Groq understands your words. PowerShell runs from C Windows System32 with access to the whole PC "
        "(drives, services, registry, processes). Run backend as Administrator for full admin rights. "
        "I remember recent prompts in this session (paths, drives, apps). "
        "Say clear context to reset memory. Deep in-app UI control is still limited.",
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


def _resolve_local_path(raw: str) -> str | None:
    from helpers.jarvis_context import resolve_workspace_path

    token = raw.strip().strip('"').strip("'")
    if not token:
        return None
    ws = resolve_workspace_path(token.replace(" folder", "").strip())
    if ws:
        return str(ws)
    existing = resolve_existing_path(token)
    if existing:
        return str(existing)
    return token


def _action_create_folder(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    from helpers.jarvis_folder import run_create_folder

    return run_create_folder(intent)


def _action_open_path(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    raw = (intent.slots.get("path") or "").strip().strip('"').strip("'")
    if not raw:
        return JarvisActionResult(False, "Which file or folder path should I open?", "open_path")
    resolved = _resolve_local_path(raw)
    path = resolve_existing_path(resolved or raw)
    if not path:
        return JarvisActionResult(False, f"I cannot find that path: {raw}", "open_path")
    try:
        os.startfile(path)  # noqa: S606
        bring_window_to_front(["File Explorer", path.name])
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
    return JarvisActionResult(
        True,
        f"Opened {label} in a new window. You can type commands there.",
        "open_terminal",
        target_label=label,
    )


def _action_open_app(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    raw = (
        intent.slots.get("app")
        or intent.slots.get("app_name")
        or intent.slots.get("application")
        or ""
    ).strip()
    if not raw:
        return JarvisActionResult(False, "Which app should I open?", "open_app")

    raw = canonical_app_name(raw)
    folder_path = (intent.slots.get("path") or intent.slots.get("folder_path") or "").strip()
    if not folder_path and intent.slots.get("folder"):
        resolved = resolve_folder_path(
            intent.slots.get("folder", ""),
            intent.slots.get("parent"),
        )
        if resolved:
            folder_path = str(resolved)

    if folder_path:
        resolved = _resolve_local_path(folder_path) or folder_path
        try:
            p = Path(resolved)
        except (OSError, ValueError):
            p = None
        if p and p.exists() and _is_editor_app(raw):
            code = shutil.which("code") or shutil.which("cursor")
            if code:
                target = str(p if p.is_dir() else p.parent)
                subprocess.Popen([code, target])  # noqa: S603
                focus_app_by_name(raw)
                label = raw if not str(raw).lower().startswith("http") else "Visual Studio Code"
                return JarvisActionResult(
                    True,
                    f"Opening {p.name} in {label}.",
                    "open_app",
                    target_label=target,
                )
            try:
                os.startfile(p)  # noqa: S606
            except OSError:
                return JarvisActionResult(False, f"Could not open {p}.", "open_app")
            return JarvisActionResult(True, f"Opening {p}.", "open_path", target_label=str(p))

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
        display = label if not str(label).lower().startswith("http") else friendly_url_label(url)
        msg = f"Opening {display}."
        if not ok:
            return JarvisActionResult(False, note or f"Could not open {display}.", "open_app", target_label=display)
        return JarvisActionResult(True, msg, "open_app", target_label=display)

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
        user_text = (intent.slots.get("user_text") or intent.slots.get("command") or raw).strip()
        ps_ok, ps_msg, _ = run_voice_command(user_text)
        if ps_ok:
            return JarvisActionResult(True, ps_msg, "run_powershell", target_label=user_text[:80])
        return JarvisActionResult(
            False,
            ps_msg if ps_msg and "GROQ" in ps_msg else f"I could not open {raw}. {ps_msg or ''}".strip(),
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
    label = friendly_url_label(url)
    if not ok:
        return JarvisActionResult(False, note or f"Could not open {label}.", "open_url", target_label=label)
    msg = f"Opening {label}."
    return JarvisActionResult(True, msg, "open_url", target_label=label)


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
    name = (intent.slots.get("name") or intent.slots.get("folder") or "").strip()
    parent = (intent.slots.get("parent") or "").strip() or None
    if name and name.lower() not in {k.lower() for k in _FOLDER_MAP}:
        resolved = resolve_folder_path(name, parent)
        if resolved:
            return _action_open_path(
                JarvisIntent(
                    intent="open_path",
                    confidence=intent.confidence,
                    slots={"path": str(resolved)},
                )
            )
        return JarvisActionResult(
            False,
            f"I cannot find folder '{name}' on {parent or 'C:'}.",
            "open_folder",
            target_label=name,
        )
    folder_key = name.lower() if name else ""
    path = _FOLDER_MAP.get(folder_key)
    if not path or not path.exists():
        return JarvisActionResult(False, f"Folder '{folder_key}' not found.", "open_folder")
    os.startfile(path)  # noqa: S606
    bring_window_to_front(["File Explorer", folder_key.title()])
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


def _action_empty_recycle_bin(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    from helpers.jarvis_recycle import empty_recycle_bin

    open_after = (intent.slots.get("open_after") or "").lower() in ("1", "true", "yes")
    ok, msg = empty_recycle_bin(open_folder_after=open_after)
    return JarvisActionResult(ok, msg, "empty_recycle_bin", target_label="Recycle Bin")


def _action_run_powershell(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked
    speech = (
        intent.slots.get("command")
        or intent.slots.get("query")
        or intent.slots.get("user_text")
        or intent.slots.get("text")
        or ""
    ).strip()
    from helpers.jarvis_recycle import user_wants_empty_recycle_bin
    from helpers.jarvis_terminal_detect import user_wants_visible_terminal

    if user_wants_empty_recycle_bin(speech):
        return _action_empty_recycle_bin(intent)

    if user_wants_visible_terminal(speech):
        shell = "powershell" if "powershell" in speech.lower() or "pwsh" in speech.lower() else "wt"
        if "cmd" in speech.lower() and "powershell" not in speech.lower():
            shell = "cmd"
        return _action_open_terminal(
            JarvisIntent(intent="open_terminal", confidence=0.95, slots={"shell": shell, **intent.slots})
        )
    script_hint = (intent.slots.get("script") or "").strip()
    if not speech and not script_hint:
        return JarvisActionResult(
            False,
            "Say what you want done — I will run it with PowerShell.",
            "run_powershell",
        )
    ok, msg, executed = run_voice_command(speech or script_hint, script_hint=script_hint or None)
    label = (executed or speech or "PowerShell")[:80]
    return JarvisActionResult(ok, msg, "run_powershell", target_label=label)


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
    "create_folder": _action_create_folder,
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
    "run_powershell": _action_run_powershell,
    "empty_recycle_bin": _action_empty_recycle_bin,
    "unknown": _action_unknown,
    "open_terminal_here": action_open_terminal_here,
    "clear_context": action_clear_context,
}


def execute_jarvis_intent(
    intent: JarvisIntent,
    *,
    context: JarvisSessionContext | None = None,
) -> JarvisActionResult:
    if intent.intent == "run_project":
        return action_run_project(intent, context)
    if intent.intent == "start_call":
        return action_start_call(intent, context)
    if intent.intent == "send_voice_message":
        return action_send_voice_message(intent, context)
    if intent.intent == "type_text":
        return action_type_text(intent, context)
    if intent.intent == "write_text":
        return action_write_text(intent, context)
    handler = _HANDLERS.get(intent.intent, _action_unknown)
    return handler(intent)
