"""Fix common Groq plan mistakes before execution."""

from __future__ import annotations

from pathlib import Path

from helpers.jarvis_context import resolve_folder_path
from helpers.jarvis_messaging import (
    is_instagram_app,
    is_messaging_app,
    looks_like_chat_message,
    parse_message_slots,
)
from schemas.jarvis import JarvisIntent

_BUILTIN_FOLDERS = frozenset({"desktop", "documents", "downloads", "home", "pictures"})


def _is_bare_drive(path: str) -> bool:
    p = path.strip().rstrip("\\/").lower()
    return len(p) <= 3 and p.endswith(":")


def sanitize_plan_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    if not steps:
        return steps

    user_text = ""
    for step in steps:
        user_text = (step.slots.get("user_text") or user_text or "").strip()
    if user_text:
        from helpers.jarvis_folder import parse_create_folder_intent, looks_like_create_folder_request

        if looks_like_create_folder_request(user_text):
            folder_step = parse_create_folder_intent(user_text)
            if folder_step:
                return [folder_step]

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

    merged = _merge_recycle_bin_steps(
        _merge_instagram_dm_steps(_rewrite_messaging_steps(fixed))
    )
    merged = _rewrite_voice_message_steps(merged, user_text)
    merged = _rewrite_call_steps(merged, user_text)
    return _dedupe_steps(merged)


def _rewrite_call_steps(
    steps: list[JarvisIntent],
    user_text: str,
) -> list[JarvisIntent]:
    from helpers.jarvis_calls import parse_call_slots, wants_call

    blob = user_text or " ".join(str(v) for s in steps for v in s.slots.values())
    if not wants_call(blob):
        return steps

    recipient, call_kind = parse_call_slots(blob)
    if not recipient:
        for s in steps:
            if s.slots.get("recipient"):
                recipient = s.slots["recipient"]
                break

    if not recipient:
        return steps

    slots: dict[str, str] = {
        "recipient": recipient,
        "call_type": call_kind,
        "user_text": user_text or blob,
    }
    app = next((s.slots.get("app") for s in steps if s.slots.get("app")), None)
    if app:
        slots["app"] = app

    return [
        JarvisIntent(
            intent="start_call",
            confidence=max((s.confidence for s in steps), default=0.92),
            slots=slots,
        )
    ]


def _rewrite_voice_message_steps(
    steps: list[JarvisIntent],
    user_text: str,
) -> list[JarvisIntent]:
    from helpers.jarvis_messaging import looks_like_voice_message
    from helpers.jarvis_voice_message import parse_voice_message_slots

    blob = user_text or " ".join(
        str(v) for s in steps for v in s.slots.values()
    )
    if not looks_like_voice_message(blob):
        return steps

    recipient, spoken, send = parse_voice_message_slots(blob)
    if not spoken and steps:
        for s in steps:
            if s.intent == "type_text":
                spoken = (s.slots.get("content") or s.slots.get("text") or "").strip()
                recipient = recipient or (s.slots.get("recipient") or "").strip()
                break

    if not spoken:
        return steps

    slots: dict[str, str] = {
        "content": spoken,
        "user_text": user_text or blob,
        "send": "true" if send else "false",
    }
    if recipient:
        slots["recipient"] = recipient
    app = next((s.slots.get("app") for s in steps if s.slots.get("app")), None)
    if app:
        slots["app"] = app
    elif any(s.intent == "open_app" for s in steps):
        for s in steps:
            if s.intent == "open_app" and s.slots.get("app"):
                slots["app"] = s.slots["app"]
                break

    return [
        JarvisIntent(
            intent="send_voice_message",
            confidence=max((s.confidence for s in steps), default=0.92),
            slots=slots,
        )
    ]


def _merge_recycle_bin_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    """Open recycle bin + delete all -> one empty_recycle_bin (no per-file deletes)."""
    from helpers.jarvis_recycle import user_wants_empty_recycle_bin

    blob_parts: list[str] = []
    for step in steps:
        blob_parts.append(step.intent)
        blob_parts.extend(str(v) for v in step.slots.values())
    blob = " ".join(blob_parts)

    if not user_wants_empty_recycle_bin(blob):
        return steps

    open_after = any(
        s.intent in ("open_app", "open_path") and "recycle" in str(s.slots).lower() for s in steps
    )
    return [
        JarvisIntent(
            intent="empty_recycle_bin",
            confidence=max((s.confidence for s in steps), default=0.9),
            slots={"open_after": "true" if open_after else "false"},
        )
    ]


def _merge_instagram_dm_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    """open_app(Instagram) + type_text -> single type_text (one tab, one navigation)."""
    out: list[JarvisIntent] = []
    i = 0
    while i < len(steps):
        step = steps[i]
        if (
            step.intent == "open_app"
            and is_instagram_app(step.slots.get("app"))
            and i + 1 < len(steps)
            and steps[i + 1].intent == "type_text"
        ):
            nxt = steps[i + 1]
            slots = dict(nxt.slots)
            slots["app"] = step.slots.get("app") or "Instagram"
            if not (slots.get("send") or "").strip():
                slots["send"] = "true"
            out.append(
                JarvisIntent(
                    intent="type_text",
                    confidence=nxt.confidence,
                    slots=slots,
                )
            )
            i += 2
            continue
        out.append(step)
        i += 1
    return out


def _rewrite_messaging_steps(steps: list[JarvisIntent]) -> list[JarvisIntent]:
    """write_text after WhatsApp/Instagram means type in chat — not create a file in VS Code."""
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
            from helpers.jarvis_folder import (
                content_looks_like_folder_not_file,
                parse_create_folder_intent,
            )

            if content_looks_like_folder_not_file(content):
                folder_step = parse_create_folder_intent(user_text or content) or parse_create_folder_intent(
                    content
                )
                if folder_step:
                    out.append(folder_step)
                    continue
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
