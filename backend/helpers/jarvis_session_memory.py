"""Conversation memory — recent prompts + paths so follow-ups work."""

from __future__ import annotations

import os
import re
from pathlib import Path

from helpers.jarvis_context import context_is_active, touch_context
from schemas.jarvis import ContextTurn, JarvisIntent, JarvisSessionContext

_MAX_TURNS = int(os.getenv("JARVIS_MEMORY_TURNS", "8"))

_THERE_WORDS = re.compile(
    r"\b("
    r"there|here|it|this|that|same\s+(?:place|drive|folder|location)|"
    r"inside\s+it|in\s+it|over\s+there|wahan|udhar|yahi|wahi|isi|us\s+drive"
    r")\b",
    re.I,
)


def mentions_context_place(text: str) -> bool:
    return bool(_THERE_WORDS.search(text or ""))


def append_session_turn(
    ctx: JarvisSessionContext,
    *,
    user_text: str,
    intent: str,
    success: bool,
    summary: str,
) -> JarvisSessionContext:
    out = ctx.model_copy(deep=True)
    turns = list(out.recent_turns or [])
    turns.insert(
        0,
        ContextTurn(
            user=user_text.strip()[:300],
            intent=intent,
            success=success,
            summary=summary.strip()[:220],
        ),
    )
    out.recent_turns = turns[:_MAX_TURNS]
    out.last_user_text = user_text.strip()[:300]
    return touch_context(out)


def build_session_context_block(ctx: JarvisSessionContext | None) -> str:
    if not context_is_active(ctx):
        return ""

    lines = [
        "SESSION MEMORY — the user may refer to earlier commands in this session "
        "('there', 'it', 'same drive', 'open it again'). Use these facts when planning:"
    ]
    if ctx.last_path:
        lines.append(f"- Last folder/path: {ctx.last_path}")
    if ctx.last_drive:
        lines.append(f"- Last drive root: {ctx.last_drive}")
    if ctx.last_app:
        lines.append(f"- Last app opened: {ctx.last_app}")
    if ctx.last_intent:
        lines.append(f"- Last completed action: {ctx.last_intent}")
    if ctx.last_label:
        lines.append(f"- Last target label: {ctx.last_label}")
    if getattr(ctx, "last_recipient", None):
        lines.append(f"- Last chat contact: {ctx.last_recipient}")

    turns = ctx.recent_turns or []
    if turns:
        lines.append("- Recent conversation (newest first):")
        for i, turn in enumerate(turns[:6], start=1):
            status = "ok" if turn.success else "failed"
            lines.append(
                f"  {i}. User: \"{turn.user}\" → {turn.intent} ({status}): {turn.summary}"
            )

    lines.append(
        "If the new command is vague, infer location/app from memory. "
        "create_folder without a drive → use last_path or last_drive as slots.parent. "
        "open it / open that → open_path with last_path."
    )
    return "\n".join(lines)


def _parent_from_ctx(ctx: JarvisSessionContext) -> str | None:
    if ctx.last_path:
        try:
            p = Path(ctx.last_path)
            if p.is_dir():
                return str(p.resolve())
            if p.parent.exists():
                return str(p.parent.resolve())
        except OSError:
            pass
    if ctx.last_drive:
        return ctx.last_drive
    return None


def apply_context_to_steps(
    steps: list[JarvisIntent],
    ctx: JarvisSessionContext | None,
    *,
    user_text: str = "",
) -> list[JarvisIntent]:
    if not context_is_active(ctx) or not steps:
        return steps

    blob = f"{user_text} " + " ".join(
        str(v) for s in steps for v in s.slots.values()
    )
    use_place = mentions_context_place(blob)
    parent = _parent_from_ctx(ctx) if ctx else None

    out: list[JarvisIntent] = []
    for step in steps:
        slots = dict(step.slots)
        intent = step.intent

        if intent == "create_folder" and parent:
            if not (slots.get("parent") or slots.get("path") or "").strip():
                if use_place or not re.search(r"\b(?:on|in)\s+[a-z]:\b", blob, re.I):
                    slots["parent"] = parent

        if intent == "open_path" and not (slots.get("path") or "").strip():
            if use_place and ctx and ctx.last_path:
                slots["path"] = ctx.last_path

        if intent == "open_app" and use_place and ctx and ctx.last_app:
            if not (slots.get("app") or "").strip():
                slots["app"] = ctx.last_app
            if ctx.last_path and not (slots.get("path") or "").strip():
                slots["path"] = ctx.last_path

        if intent == "run_powershell" and ctx and ctx.last_path:
            slots.setdefault("context_path", ctx.last_path)

        if intent in ("send_voice_message", "start_call", "type_text"):
            from helpers.jarvis_messaging import resolve_recipient_pronoun

            recip = resolve_recipient_pronoun(slots.get("recipient") or "", ctx)
            if recip:
                slots["recipient"] = recip
            if not (slots.get("app") or "").strip() and ctx.last_app:
                slots.setdefault("app", ctx.last_app)

        out.append(
            JarvisIntent(
                intent=intent,
                confidence=step.confidence,
                slots=slots,
            )
        )
    return out
