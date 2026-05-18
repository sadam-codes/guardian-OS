import os

from helpers.jarvis_actions import execute_jarvis_intent
from helpers.jarvis_context import (
    clear_context,
    context_is_active,
    fresh_context,
    parse_followup_intent,
    touch_context,
    update_context_after_action,
)
from helpers.jarvis_session_memory import append_session_turn, apply_context_to_steps
from helpers.jarvis_groq import (
    generate_spoken_reply,
    groq_enabled,
    plan_with_groq,
)
from helpers.jarvis_intent import parse_jarvis_intent
from helpers.jarvis_plan import execute_jarvis_steps
from schemas.jarvis import (
    JarvisActionResult,
    JarvisCommandResponse,
    JarvisIntent,
    JarvisPlanResponse,
    JarvisSessionContext,
)

ASSISTANT_NAME = os.getenv("JARVIS_NAME", "Guardian")
USE_GROQ_REPLIES = os.getenv("JARVIS_GROQ_REPLIES", "true").lower() in ("1", "true", "yes")
USE_LLM = os.getenv("JARVIS_USE_LLM", "true").lower() in ("1", "true", "yes")
EARLY_VOICE_ACK = os.getenv("JARVIS_EARLY_VOICE_ACK", "true").lower() in ("1", "true", "yes")


def _first_name(user_name: str | None) -> str | None:
    if not user_name or not user_name.strip():
        return None
    return user_name.strip().split()[0]


def _plan_meta_from_steps(steps: list[JarvisIntent]) -> tuple[str, str]:
    if not steps:
        return "", ""
    slots = steps[0].slots or {}
    return (
        str(slots.get("understood", "")).strip(),
        str(slots.get("jarvis_brief", "")).strip(),
    )


def _message_from_groq_plan(
    user_name: str | None,
    intent: str,
    result: JarvisActionResult,
    *,
    jarvis_brief: str,
    understood: str,
) -> str:
    if jarvis_brief and result.success:
        base = jarvis_brief.rstrip(".")
        if result.message and result.message.strip() not in base:
            detail = result.message.strip()
            if len(detail) < 200 and "error" not in detail.lower():
                return f"{base}. {detail}"
        name = _first_name(user_name)
        if name and name.lower() not in base.lower():
            return f"Okay {name}, {base.lower()}."
        return f"{base}."

    return _personalize_message(user_name, intent, result)


def _personalize_message(
    user_name: str | None,
    intent: str,
    result: JarvisActionResult,
) -> str:
    name = _first_name(user_name)
    base = result.message.rstrip(".")
    label = result.target_label

    if not name:
        return result.message

    if not result.success:
        if intent == "open_app" and label:
            return f"Sorry {name}, I couldn't open {label}."
        return f"Sorry {name}, {base.lower()}."

    if intent == "compound":
        return f"Okay {name}, {base.lower()}."

    templates: dict[str, str] = {
        "open_app": f"Okay {name}, opening {label or 'that'}." if label else f"Okay {name}, {base.lower()}.",
        "open_url": f"Okay {name}, opening that link.",
        "web_search": f"Okay {name}, searching Google for {label}." if label else f"Okay {name}, opening Google search.",
        "youtube_search": f"Okay {name}, {base.lower()}." if base else f"Okay {name}, opening YouTube.",
        "open_folder": f"Okay {name}, opening your {label} folder." if label else f"Okay {name}, opening that folder.",
        "open_path": f"Okay {name}, opening {label}." if label else f"Okay {name}, opening that path.",
        "create_folder": f"Okay {name}, {base.lower()}.",
        "open_terminal": f"Okay {name}, opening the terminal.",
        "write_text": f"Okay {name}, {base.lower()}.",
        "type_text": f"Okay {name}, {base.lower()}.",
        "send_voice_message": f"Okay {name}, {base.lower()}.",
        "start_call": f"Okay {name}, {base.lower()}.",
        "run_project": f"Okay {name}, {base.lower()}.",
        "run_powershell": f"Okay {name}, {base.lower()}.",
        "open_terminal_here": f"Okay {name}, {base.lower()}.",
        "clear_context": f"Okay {name}, starting fresh.",
        "lock": f"Okay {name}, locking your computer.",
        "volume_up": f"Okay {name}, turning the volume up.",
        "volume_down": f"Okay {name}, turning the volume down.",
        "volume_mute": f"Okay {name}, toggling mute.",
        "minimize_all": f"Okay {name}, showing the desktop.",
        "screenshot": f"Okay {name}, taking a screenshot.",
        "time": f"{name}, {base.lower()}.",
        "date": f"{name}, {base.lower()}.",
        "greet": f"Hello {name}. Good to see you. How can I help?",
        "help": (
            f"Sure {name}. I remember your last commands in this session — say things like "
            "'open D drive', then 'create folder asad there'. Say 'clear context' to forget."
        ),
        "acknowledge": f"Got it, {name}.",
        "cancel": f"Alright {name}, cancelled.",
        "shutdown": f"Okay {name}, shutting down in 15 seconds.",
        "restart": f"Okay {name}, restarting in 15 seconds.",
        "unknown": f"Sorry {name}, I did not understand. Please say it again or say help.",
    }

    if intent in templates:
        return templates[intent]

    return f"Okay {name}, {base.lower()}."


def _resolved_path_from_result(result: JarvisActionResult) -> str | None:
    label = result.target_label
    if not label:
        return None
    from pathlib import Path

    p = Path(label)
    if p.exists():
        return str(p.resolve())
    return label


def _resolve_steps(text: str, ctx: JarvisSessionContext | None) -> tuple[list[JarvisIntent], str, str]:
    """Groq-first: understand + plan. Regex only if Groq unavailable."""
    if context_is_active(ctx):
        follow = parse_followup_intent(text, ctx)  # type: ignore[arg-type]
        if follow:
            return [follow], "", ""

    active_ctx = ctx if context_is_active(ctx) else None

    if USE_LLM and groq_enabled():
        plan = plan_with_groq(text, session=active_ctx)
        if plan and plan.steps:
            return plan.steps, plan.understood, plan.jarvis_brief

    steps = [parse_jarvis_intent(text, context=active_ctx)]
    if active_ctx:
        steps = apply_context_to_steps(steps, active_ctx, user_text=text)
    return steps, "", ""


def plan_jarvis_command(
    text: str,
    *,
    context: JarvisSessionContext | None = None,
) -> JarvisPlanResponse:
    """Groq plan only — fast enough to speak before heavy OS work."""
    ctx = context if context_is_active(context) else fresh_context()
    active = ctx if context_is_active(ctx) else None
    steps, understood, jarvis_brief = _resolve_steps(text, active)
    if active:
        steps = apply_context_to_steps(steps, active, user_text=text)
    if not understood or not jarvis_brief:
        u2, b2 = _plan_meta_from_steps(steps)
        understood = understood or u2
        jarvis_brief = jarvis_brief or b2
    intent = steps[0].intent if steps else "unknown"
    confidence = min((s.confidence for s in steps), default=0.0) if steps else 0.0
    return JarvisPlanResponse(
        understood=understood,
        jarvis_brief=jarvis_brief,
        intent=intent,
        confidence=confidence,
        planned_steps=steps,
        context=touch_context(ctx) if active else ctx,
    )


def process_jarvis_command(
    text: str,
    user_name: str | None = None,
    context: JarvisSessionContext | None = None,
    *,
    planned_steps: list[JarvisIntent] | None = None,
    understood: str | None = None,
    jarvis_brief: str | None = None,
) -> JarvisCommandResponse:
    ctx = context if context_is_active(context) else fresh_context()
    active = ctx if context_is_active(ctx) else None

    if planned_steps:
        steps = planned_steps
        understood = understood or ""
        jarvis_brief = jarvis_brief or ""
    else:
        steps, understood, jarvis_brief = _resolve_steps(text, active)
        if active:
            steps = apply_context_to_steps(steps, active, user_text=text)

    if not understood or not jarvis_brief:
        u2, b2 = _plan_meta_from_steps(steps)
        understood = understood or u2
        jarvis_brief = jarvis_brief or b2

    if len(steps) > 1:
        result, ctx = execute_jarvis_steps(
            steps,
            context=active or touch_context(ctx),
        )
        response_intent = "compound"
        confidence = min(s.confidence for s in steps)
        slots = {"step_count": str(len(steps))}
    else:
        intent = steps[0]
        result = execute_jarvis_intent(intent, context=active or touch_context(ctx))
        ctx = update_context_after_action(
            ctx,
            intent,
            success=result.success,
            target_label=result.target_label,
            resolved_path=_resolved_path_from_result(result),
        )
        response_intent = intent.intent
        confidence = intent.confidence
        slots = dict(intent.slots)

    if understood:
        slots["understood"] = understood
    if jarvis_brief:
        slots["jarvis_brief"] = jarvis_brief

    if response_intent in ("clear_context", "cancel"):
        ctx = clear_context()
    elif response_intent != "greet":
        ctx = append_session_turn(
            ctx,
            user_text=text,
            intent=response_intent,
            success=result.success,
            summary=result.message,
        )

    message = _message_from_groq_plan(
        user_name,
        response_intent,
        result,
        jarvis_brief=jarvis_brief,
        understood=understood,
    )

    if response_intent == "greet" and not _first_name(user_name):
        message = message.replace("How can I help", f"I'm {ASSISTANT_NAME}. How can I help")

    # Second Groq call for phrasing — skip if we already spoke jarvis_brief early (saves ~1–2s).
    if (
        USE_GROQ_REPLIES
        and groq_enabled()
        and not (EARLY_VOICE_ACK and jarvis_brief)
    ):
        spoken = generate_spoken_reply(
            user_text=text,
            user_name=user_name,
            intent=response_intent,
            action_success=result.success,
            action_message=result.message,
            assistant_name=ASSISTANT_NAME,
            jarvis_brief=jarvis_brief or None,
        )
        if spoken:
            message = spoken

    return JarvisCommandResponse(
        success=result.success,
        message=message,
        intent=response_intent,
        confidence=confidence,
        action=result.action,
        slots=slots,
        context=ctx,
    )


def jarvis_example_commands() -> list[str]:
    return [
        "Open recycle bin",
        "Show disk space on C drive",
        "Open Chrome",
        "Hey, what time is it?",
        "Open Instagram and send hello to a friend",
        "Open C drive and create folder sadam",
        "List running processes",
        "Volume up",
        "What can you do?",
    ]
