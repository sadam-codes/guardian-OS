"""Execute multi-step command plans from Groq."""

from __future__ import annotations

from helpers.jarvis_actions import execute_jarvis_intent
from helpers.jarvis_context import fresh_context, touch_context, update_context_after_action
from schemas.jarvis import JarvisActionResult, JarvisIntent, JarvisSessionContext


def _path_from_result(result: JarvisActionResult) -> str | None:
    label = result.target_label
    if not label:
        return None
    from pathlib import Path

    p = Path(label)
    if p.exists():
        return str(p.resolve())
    return label


def execute_jarvis_steps(
    steps: list[JarvisIntent],
    *,
    context: JarvisSessionContext | None = None,
) -> tuple[JarvisActionResult, JarvisSessionContext | None]:
    if not steps:
        return (
            JarvisActionResult(False, "No steps to run.", "compound"),
            context,
        )

    ctx = context if context is not None else fresh_context()
    parts: list[str] = []
    overall_ok = True
    last_label: str | None = None
    last_action = "compound"

    for step in steps:
        result = execute_jarvis_intent(step, context=ctx if ctx and ctx.active else None)
        last_action = result.action
        last_label = result.target_label or last_label
        parts.append(result.message.rstrip("."))
        ctx = update_context_after_action(
            ctx,
            step,
            success=result.success,
            target_label=result.target_label,
            resolved_path=_path_from_result(result),
        )
        if not result.success:
            overall_ok = False
            break

    summary = ". ".join(parts)
    if summary and not summary.endswith("."):
        summary += "."
    ctx = touch_context(ctx)
    return (
        JarvisActionResult(overall_ok, summary or "Done.", last_action, target_label=last_label),
        ctx,
    )
