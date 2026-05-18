"""Follow-up actions: write files, run projects, terminal in context folder."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from helpers.jarvis_context import resolve_run_folder, resolve_workspace_path
from helpers.jarvis_local import launch_shell, resolve_existing_path
from helpers.jarvis_messaging import parse_message_slots, should_type_not_write
from helpers.jarvis_type import action_type_text
import os

from schemas.jarvis import JarvisActionResult, JarvisIntent, JarvisSessionContext

ALLOW_OS_CONTROL = os.getenv("JARVIS_ALLOW_OS", "true").lower() in ("1", "true", "yes")


def _require_os() -> JarvisActionResult | None:
    if not ALLOW_OS_CONTROL:
        return JarvisActionResult(False, "OS control is disabled.", "blocked")
    return None


def _is_editor_app(app: str | None) -> bool:
    if not app:
        return False
    low = app.lower()
    return any(x in low for x in ("code", "visual studio", "vs code", "cursor", "notepad"))


def _hello_world_body(content: str) -> tuple[str, str]:
    """Return (filename, file_body) from natural language like 'hello world'."""
    low = content.lower().strip()
    if re.search(r"\bhello\s*world\b", low):
        return "hello_world.py", 'print("Hello, world!")\n'
    if re.search(r"\b(html|web\s*page)\b", low):
        return "hello.html", "<!DOCTYPE html>\n<html><body><h1>Hello</h1></body></html>\n"
    safe = re.sub(r"[^\w\s-]", "", content)[:40].strip().replace(" ", "_") or "note"
    return f"{safe}.txt", content + ("\n" if not content.endswith("\n") else "")


def _pick_write_dir(intent: JarvisIntent) -> Path:
    raw = (intent.slots.get("path") or "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            return p.parent
        if p.is_dir():
            return p
        resolved = resolve_existing_path(raw)
        if resolved:
            return resolved if resolved.is_dir() else resolved.parent
    return Path.home() / "Desktop"


def _open_in_editor(file_path: Path, app_hint: str | None) -> None:
    code = shutil.which("code") or shutil.which("cursor")
    if code and _is_editor_app(app_hint):
        subprocess.Popen([code, str(file_path)], cwd=str(file_path.parent))  # noqa: S603
        return
    os.startfile(file_path)  # noqa: S606


def action_write_text(
    intent: JarvisIntent,
    ctx: JarvisSessionContext | None = None,
) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked

    content = (intent.slots.get("content") or intent.slots.get("text") or "").strip()
    if not content:
        return JarvisActionResult(False, "What should I write?", "write_text")

    app_hint = intent.slots.get("app") or (ctx.last_app if ctx else None)
    if should_type_not_write(app=app_hint, content=content):
        slots = dict(intent.slots)
        slots["app"] = app_hint or slots.get("app") or ""
        recipient, body, auto_send = parse_message_slots(content)
        if recipient:
            slots["recipient"] = recipient
            slots["content"] = body
        if auto_send:
            slots["send"] = "true"
        return action_type_text(
            JarvisIntent(intent="type_text", confidence=intent.confidence, slots=slots),
            ctx,
        )
    directory = _pick_write_dir(intent)
    directory.mkdir(parents=True, exist_ok=True)

    filename = (intent.slots.get("filename") or "").strip()
    if filename:
        body = content if "\n" in content or "." in filename else content + "\n"
    else:
        filename, body = _hello_world_body(content)

    file_path = (directory / filename).resolve()
    try:
        file_path.write_text(body, encoding="utf-8")
    except OSError as exc:
        return JarvisActionResult(False, f"Could not write file: {exc}", "write_text")

    try:
        _open_in_editor(file_path, app_hint)
    except OSError:
        pass

    return JarvisActionResult(
        True,
        f"Wrote {file_path.name} and opened it.",
        "write_text",
        target_label=str(file_path),
    )


def _detect_run_command(folder: Path) -> list[str] | None:
    main_py = folder / "main.py"
    pkg = folder / "package.json"

    if main_py.is_file():
        text = main_py.read_text(encoding="utf-8", errors="ignore")
        if "FastAPI" in text or "uvicorn" in text.lower():
            return ["uvicorn", "main:app", "--reload"]
        return [shutil.which("python") or "python", "main.py"]

    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        scripts = data.get("scripts") or {}
        for key in ("dev", "start", "serve"):
            if key in scripts:
                npm = shutil.which("npm") or "npm"
                return [npm, "run", key]
        return [shutil.which("npm") or "npm", "start"]

    return None


def action_run_project(intent: JarvisIntent, ctx) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked

    folder = resolve_run_folder(intent, ctx)
    if not folder:
        return JarvisActionResult(
            False,
            "Which folder should I run? Open a folder first or say run backend folder.",
            "run_project",
        )

    cmd = _detect_run_command(folder)
    if not cmd:
        return JarvisActionResult(
            False,
            f"No runnable project found in {folder.name}.",
            "run_project",
            target_label=str(folder),
        )

    creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    try:
        subprocess.Popen(  # noqa: S603
            cmd,
            cwd=str(folder),
            creationflags=creationflags,
        )
    except OSError as exc:
        return JarvisActionResult(False, f"Could not start: {exc}", "run_project", target_label=str(folder))

    label = folder.name
    return JarvisActionResult(
        True,
        f"Started {' '.join(cmd)} in {label}.",
        "run_project",
        target_label=str(folder),
    )


def action_open_terminal_here(intent: JarvisIntent) -> JarvisActionResult:
    blocked = _require_os()
    if blocked:
        return blocked

    folder = resolve_run_folder(intent, None)
    cwd = str(folder) if folder else None

    if cwd and os.name == "nt":
        wt = shutil.which("wt") or shutil.which("wt.exe")
        if wt:
            subprocess.Popen([wt, "-d", cwd])  # noqa: S603
            return JarvisActionResult(True, f"Opening terminal in {folder.name}.", "open_terminal_here", target_label=cwd)
        ps = shutil.which("powershell") or "powershell"
        subprocess.Popen([ps, "-NoExit", "-Command", f"Set-Location '{cwd}'"])  # noqa: S603
        return JarvisActionResult(True, f"Opening PowerShell in {folder.name}.", "open_terminal_here", target_label=cwd)

    ok, label = launch_shell("wt")
    if not ok:
        return JarvisActionResult(False, "Could not open a terminal.", "open_terminal_here")
    return JarvisActionResult(True, f"Opening {label}.", "open_terminal_here")


def action_clear_context(_: JarvisIntent) -> JarvisActionResult:
    return JarvisActionResult(True, "Context cleared.", "clear_context")
