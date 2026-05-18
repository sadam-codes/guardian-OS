import os

from helpers.jarvis_actions import execute_jarvis_intent
from helpers.jarvis_context import (
    clear_context,
    context_is_active,
    fresh_context,
    parse_followup_intent,
    update_context_after_action,
)
from helpers.jarvis_groq import generate_spoken_reply, groq_enabled, parse_steps_with_groq
from helpers.jarvis_intent import parse_jarvis_intent
from helpers.jarvis_plan import execute_jarvis_steps
from schemas.jarvis import JarvisActionResult, JarvisCommandResponse, JarvisIntent, JarvisSessionContext

ASSISTANT_NAME = os.getenv("JARVIS_NAME", "Guardian")
USE_GROQ_REPLIES = os.getenv("JARVIS_GROQ_REPLIES", "false").lower() in ("1", "true", "yes")
USE_LLM = os.getenv("JARVIS_USE_LLM", "true").lower() in ("1", "true", "yes")


def _first_name(user_name: str | None) -> str | None:
    if not user_name or not user_name.strip():
        return None
    return user_name.strip().split()[0]


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
        "run_project": f"Okay {name}, {base.lower()}.",
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
            f"Sure {name}. Say chained commands naturally, like: open C drive and create a folder named sadam. "
            "Or open VS Code, then write hello world."
        ),
        "acknowledge": f"Got it, {name}.",
        "cancel": f"Alright {name}, cancelled.",
        "shutdown": f"Okay {name}, shutting down in 15 seconds.",
        "restart": f"Okay {name}, restarting in 15 seconds.",
        "unknown": f"{name}, I don't know that command. Say help for examples.",
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


def _resolve_steps(text: str, ctx: JarvisSessionContext | None) -> list[JarvisIntent]:
    if context_is_active(ctx):
        follow = parse_followup_intent(text, ctx)  # type: ignore[arg-type]
        if follow:
            return [follow]

    if USE_LLM and groq_enabled():
        planned = parse_steps_with_groq(text)
        if planned:
            return planned

    return [parse_jarvis_intent(text, context=ctx if context_is_active(ctx) else None)]


def process_jarvis_command(
    text: str,
    user_name: str | None = None,
    context: JarvisSessionContext | None = None,
) -> JarvisCommandResponse:
    ctx = context if context_is_active(context) else fresh_context()
    steps = _resolve_steps(text, ctx if context_is_active(ctx) else None)

    if len(steps) > 1:
        result, ctx = execute_jarvis_steps(
            steps,
            context=ctx if context_is_active(ctx) else None,
        )
        response_intent = "compound"
        confidence = min(s.confidence for s in steps)
        slots = {"step_count": str(len(steps))}
    else:
        intent = steps[0]
        result = execute_jarvis_intent(intent, context=ctx if context_is_active(ctx) else None)
        new_ctx = update_context_after_action(
            ctx,
            intent,
            success=result.success,
            target_label=result.target_label,
            resolved_path=_resolved_path_from_result(result),
        )
        ctx = new_ctx
        response_intent = intent.intent
        confidence = intent.confidence
        slots = intent.slots

    if response_intent in ("clear_context", "cancel"):
        ctx = clear_context()

    message = _personalize_message(user_name, response_intent, result)

    if response_intent == "greet" and not _first_name(user_name):
        message = message.replace("How can I help", f"I'm {ASSISTANT_NAME}. How can I help")

    if USE_GROQ_REPLIES and groq_enabled() and result.success:
        spoken = generate_spoken_reply(
            user_text=text,
            user_name=user_name,
            intent=response_intent,
            action_success=result.success,
            action_message=result.message,
            assistant_name=ASSISTANT_NAME,
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
        "Hey , what time is it?",
        "Open YouTube and play song Atif Aslma song",
        "Open C drive and create a folder named sadam",
        "Open Visual Studio Code",
        "Open Windows settings",
        "Search weather in Lahore",
        "Open backend folder",
        "Run backend folder",
        "Open PowerShell",
        "Lock the computer",
        "Volume up",
        "Take a screenshot",
        "What can you do?",
    ]
