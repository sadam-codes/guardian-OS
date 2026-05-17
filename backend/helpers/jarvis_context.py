"""Session context for nested / follow-up voice commands."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from schemas.jarvis import JarvisIntent, JarvisSessionContext

CONTEXT_TTL_SEC = int(os.getenv("JARVIS_CONTEXT_TTL_SEC", "600"))

_WRITE_RE = re.compile(
    r"^(?:please\s+)?(?:write|type|create|add|put)\s+(.+?)(?:\s+in\s+it)?\.?\s*$",
    re.I,
)
_RUN_RE = re.compile(
    r"^(?:please\s+)?(?:run|start|execute|launch)\s+"
    r"(?:the\s+)?(?:project|server|app|backend|folder|it|this)?\s*"
    r"(?:folder\s+)?(?P<target>[\w./\\-]+)?\.?\s*$",
    re.I,
)
_TERMINAL_HERE_RE = re.compile(
    r"^(?:open\s+)?(?:a\s+)?(?:terminal|powershell|cmd)\s+(?:here|there|in\s+it)\.?\s*$",
    re.I,
)
_CLEAR_RE = re.compile(r"^(?:clear|reset|forget)\s+(?:context|memory|session)\.?\s*$", re.I)
_OPEN_IN_EDITOR_RE = re.compile(
    r"open(?:\s+the)?\s+(?P<name>[\w-]+)\s+folder.*?(?:in|with|using)\s+"
    r"(?:the\s+)?(?P<app>visual studio code|vs\s*code|vscode)",
    re.I,
)
_DRIVE_IN_TEXT_RE = re.compile(r"\bfrom\s+(?P<letter>[a-z])\s+drive\b", re.I)


def _workspace_root() -> Path:
    raw = os.getenv("JARVIS_WORKSPACE_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    # backend/helpers/jarvis_context.py -> repo root
    return Path(__file__).resolve().parents[2]


def fresh_context() -> JarvisSessionContext:
    return JarvisSessionContext()


def context_is_active(ctx: JarvisSessionContext | None) -> bool:
    if not ctx or not ctx.active:
        return False
    if ctx.updated_at <= 0:
        return False
    return (time.time() - ctx.updated_at) < CONTEXT_TTL_SEC


def touch_context(ctx: JarvisSessionContext) -> JarvisSessionContext:
    ctx.active = True
    ctx.updated_at = time.time()
    return ctx


def clear_context() -> JarvisSessionContext:
    return fresh_context()


def resolve_folder_path(
    name: str,
    parent: str | None = None,
    ctx: JarvisSessionContext | None = None,
) -> Path | None:
    """Resolve a folder name like 'sadam' on C:\\ or from session context."""
    token = (name or "").strip().strip('"').strip("'")
    if not token:
        return None

    if ctx and ctx.last_path:
        last = Path(ctx.last_path)
        if last.is_dir() and last.name.lower() == token.lower():
            return last.resolve()
        child = last / token if last.is_dir() else last.parent / token
        if child.is_dir():
            return child.resolve()

    parent_path: Path | None = None
    if parent:
        from helpers.jarvis_local import resolve_existing_path

        resolved_parent = resolve_existing_path(parent) or parent
        try:
            parent_path = Path(resolved_parent)
        except (OSError, ValueError):
            parent_path = None
        if parent_path and parent_path.is_dir():
            child = parent_path / token
            if child.is_dir():
                return child.resolve()

    for candidate in (Path(f"C:/{token}"), Path(f"C:\\{token}")):
        if candidate.is_dir():
            return candidate.resolve()

    ws = resolve_workspace_path(token)
    if ws:
        return ws
    return None


def resolve_workspace_path(name: str) -> Path | None:
    """Resolve a folder name like 'backend' under the workspace root."""
    token = name.strip().strip('"').strip("'")
    if not token:
        return None
    root = _workspace_root()
    candidate = Path(token)
    if candidate.is_absolute() and candidate.is_dir():
        return candidate.resolve()
    joined = (root / token).resolve()
    if joined.is_dir():
        return joined
    aliases = {
        "backend": root / "backend",
        "frontend": root / "frontend",
    }
    low = token.lower().replace(" folder", "").strip()
    if low in aliases and aliases[low].is_dir():
        return aliases[low].resolve()
    return None


def resolve_run_folder(intent: JarvisIntent, ctx: JarvisSessionContext | None) -> Path | None:
    raw = (intent.slots.get("path") or intent.slots.get("folder") or "").strip()
    if raw:
        p = resolve_workspace_path(raw)
        if p:
            return p
        from helpers.jarvis_local import resolve_existing_path

        existing = resolve_existing_path(raw)
        if existing and existing.is_dir():
            return existing
    if ctx and ctx.last_path:
        p = Path(ctx.last_path)
        if p.is_dir():
            return p.resolve()
        if p.is_file():
            return p.parent.resolve()
    return None


def parse_followup_intent(text: str, ctx: JarvisSessionContext) -> JarvisIntent | None:
    """Map a short follow-up utterance to an intent using session context."""
    if not context_is_active(ctx):
        return None

    clean = " ".join(text.strip().split())
    if not clean:
        return None

    if _CLEAR_RE.match(clean):
        return JarvisIntent(intent="clear_context", confidence=0.99)

    editor = _OPEN_IN_EDITOR_RE.search(clean)
    if editor:
        m = editor
        name = m.group("name").strip()
        app = m.group("app").strip()
        parent = None
        dm = _DRIVE_IN_TEXT_RE.search(clean)
        if dm:
            parent = f"{dm.group('letter').upper()}:\\"
        elif ctx.last_path and Path(ctx.last_path).drive:
            parent = str(Path(ctx.last_path).anchor)
        folder = resolve_folder_path(name, parent, ctx)
        if folder:
            return JarvisIntent(
                intent="open_app",
                confidence=0.94,
                slots={"app": "Visual Studio Code", "path": str(folder)},
            )

    m = _WRITE_RE.match(clean)
    if m:
        content = m.group(1).strip().strip("'\"")
        slots: dict[str, str] = {"content": content}
        if ctx.last_path:
            slots["path"] = ctx.last_path
        if ctx.last_app:
            slots["app"] = ctx.last_app
        return JarvisIntent(intent="write_text", confidence=0.92, slots=slots)

    if _TERMINAL_HERE_RE.match(clean):
        slots = {}
        if ctx.last_path:
            slots["path"] = ctx.last_path
        return JarvisIntent(intent="open_terminal_here", confidence=0.93, slots=slots)

    m = _RUN_RE.match(clean)
    if m:
        target = (m.group("target") or "").strip()
        slots = {}
        if target:
            slots["folder"] = target
        elif ctx.last_path:
            slots["path"] = ctx.last_path
        elif ctx.last_label and "backend" in ctx.last_label.lower():
            slots["folder"] = "backend"
        return JarvisIntent(intent="run_project", confidence=0.9, slots=slots)

    low = clean.lower()
    if low in ("run it", "start it", "run this", "start server", "run server", "run project"):
        slots = {}
        if ctx.last_path:
            slots["path"] = ctx.last_path
        return JarvisIntent(intent="run_project", confidence=0.88, slots=slots)

    return None


def update_context_after_action(
    ctx: JarvisSessionContext,
    intent: JarvisIntent,
    *,
    success: bool,
    target_label: str | None = None,
    resolved_path: str | None = None,
) -> JarvisSessionContext:
    if intent.intent == "clear_context":
        return clear_context()

    if not success:
        return touch_context(ctx)

    out = ctx.model_copy(deep=True)
    out = touch_context(out)
    out.last_intent = intent.intent

    if intent.intent in ("open_app",):
        out.last_app = (
            intent.slots.get("app")
            or intent.slots.get("app_name")
            or target_label
            or out.last_app
        )
    if intent.intent in ("open_path", "open_folder", "run_project", "write_text", "open_terminal_here"):
        path = resolved_path or intent.slots.get("path") or out.last_path
        if path:
            out.last_path = str(Path(path).resolve()) if Path(path).exists() else path
    if target_label:
        out.last_label = target_label
    elif intent.intent == "open_app" and out.last_app:
        out.last_label = out.last_app

    return out
