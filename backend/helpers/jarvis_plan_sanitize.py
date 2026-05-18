"""Fix common Groq plan mistakes before execution."""

from __future__ import annotations

from pathlib import Path

from helpers.jarvis_context import resolve_folder_path
from helpers.jarvis_messaging import is_messaging_app, looks_like_chat_message, parse_message_slots
from schemas.jarvis import JarvisIntent

_BUILTIN_FOLDERS = frozenset({"desktop", "documents", "downloads", "home", "pictures"})


def _is_bare_drive(path: str) -> bool:
    p = path.strip().rstrip("\\/").lower()
    return len(p) <= 3 and p.endswith(":")


def sanitize_plan_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    if not steps:
        return steps

    fixed: list[JarvisIntent] = []
    pending_folder: str | None = None
    pending_parent: str | None = None

    for step in steps:
        if step.intent == "create_folder":
            name = step.slots.get("name") or step.slots.get("folder") or ""
            parent = step.slots.get("parent") or step.slots.get("path") or ""
            if name:
                pending_folder = name
                pending_parent = parent or None
            fixed.append(step)
            continue

        if step.intent == "open_folder":
            name = (step.slots.get("name") or step.slots.get("folder") or "").strip()
            parent = (step.slots.get("parent") or step.slots.get("path") or "").strip() or None
            if name and name.lower() not in _BUILTIN_FOLDERS:
                resolved = resolve_folder_path(name, parent)
                if resolved:
                    fixed.append(
                        JarvisIntent(
                            intent="open_path",
                            confidence=step.confidence,
                            slots={"path": str(resolved)},
                        )
                    )
                    continue
            if name.lower() in _BUILTIN_FOLDERS:
                fixed.append(step)
                continue

        if step.intent == "open_path":
            path = (step.slots.get("path") or "").strip()
            if _is_bare_drive(path) and pending_folder:
                resolved = resolve_folder_path(pending_folder, pending_parent or path)
                if resolved:
                    fixed.append(
                        JarvisIntent(
                            intent="open_path",
                            confidence=step.confidence,
                            slots={"path": str(resolved)},
                        )
                    )
                    continue
            if _is_bare_drive(path) and any(
                s.intent == "open_app" and (s.slots.get("path") or "") for s in steps
            ):
                continue
            if path:
                full = Path(path)
                if full.is_dir():
                    fixed.append(step)
                    continue
                resolved = resolve_folder_path(path.split("\\")[-1], path)
                if resolved:
                    fixed.append(
                        JarvisIntent(
                            intent="open_path",
                            confidence=step.confidence,
                            slots={"path": str(resolved)},
                        )
                    )
                    continue

        if step.intent == "open_app" and not (step.slots.get("path") or "").strip():
            app = (step.slots.get("app") or "").lower()
            if pending_folder and any(x in app for x in ("code", "visual studio", "cursor")):
                resolved = resolve_folder_path(pending_folder, pending_parent)
                if resolved:
                    slots = dict(step.slots)
                    slots["path"] = str(resolved)
                    fixed.append(
                        JarvisIntent(
                            intent="open_app",
                            confidence=step.confidence,
                            slots=slots,
                        )
                    )
                    continue

        fixed.append(step)

    return _dedupe_steps(_rewrite_messaging_steps(fixed))


def _rewrite_messaging_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    """write_text after WhatsApp means type in chat — not create a file in VS Code."""
    out: list[JarvisIntent] = []
    last_app: str | None = None

    for step in steps:
        if step.intent == "open_app":
            last_app = step.slots.get("app") or last_app
            out.append(step)
            continue

        if step.intent == "write_text":
            app = (step.slots.get("app") or last_app or "").strip()
            content = (step.slots.get("content") or step.slots.get("text") or "").strip()
            if is_messaging_app(app) or looks_like_chat_message(content):
                slots = dict(step.slots)
                if app:
                    slots["app"] = app
                recipient, body, auto_send = parse_message_slots(content)
                if recipient:
                    slots["recipient"] = recipient
                    slots["content"] = body
                if auto_send:
                    slots["send"] = "true"
                out.append(
                    JarvisIntent(
                        intent="type_text",
                        confidence=step.confidence,
                        slots=slots,
                    )
                )
                continue

        out.append(step)

    return out


def _dedupe_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    seen: set[tuple[str, str]] = set()
    out: list[JarvisIntent] = []
    for step in steps:
        key = (step.intent, str(sorted(step.slots.items())))
        if key in seen:
            continue
        seen.add(key)
        out.append(step)
    return out
