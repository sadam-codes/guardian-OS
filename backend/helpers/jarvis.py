import os

from helpers.jarvis_actions import JarvisActionResult, execute_jarvis_intent
from helpers.jarvis_groq import generate_spoken_reply, groq_enabled
from helpers.jarvis_intent import parse_jarvis_intent
from schemas.jarvis import JarvisCommandResponse

ASSISTANT_NAME = os.getenv("JARVIS_NAME", "Guardian")
USE_GROQ_REPLIES = os.getenv("JARVIS_GROQ_REPLIES", "false").lower() in ("1", "true", "yes")


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

    templates: dict[str, str] = {
        "open_app": f"Okay {name}, opening {label or 'that'}." if label else f"Okay {name}, {base.lower()}.",
        "open_url": f"Okay {name}, opening that link.",
        "web_search": f"Okay {name}, searching Google for {label}." if label else f"Okay {name}, opening Google search.",
        "youtube_search": f"Okay {name}, {base.lower()}." if base else f"Okay {name}, opening YouTube.",
        "open_folder": f"Okay {name}, opening your {label} folder." if label else f"Okay {name}, opening that folder.",
        "open_path": f"Okay {name}, opening {label}." if label else f"Okay {name}, opening that path.",
        "open_terminal": f"Okay {name}, opening the terminal.",
        "lock": f"Okay {name}, locking your computer.",
        "volume_up": f"Okay {name}, turning the volume up.",
        "volume_down": f"Okay {name}, turning the volume down.",
        "volume_mute": f"Okay {name}, toggling mute.",
        "minimize_all": f"Okay {name}, showing the desktop.",
        "screenshot": f"Okay {name}, taking a screenshot.",
        "time": f"{name}, {base.lower()}.",
        "date": f"{name}, {base.lower()}.",
        "greet": f"Hello {name}. Good to see you. How can I help?",
        "help": f"Sure {name}. Try: open Chrome, open C drive, open PowerShell, open Windows settings, or search weather in Lahore.",
        "acknowledge": f"Got it, {name}.",
        "cancel": f"Alright {name}, cancelled.",
        "shutdown": f"Okay {name}, shutting down in 15 seconds.",
        "restart": f"Okay {name}, restarting in 15 seconds.",
        "unknown": f"{name}, I don't know that command. Say help for examples.",
    }

    if intent in templates:
        return templates[intent]

    return f"Okay {name}, {base.lower()}."


def process_jarvis_command(text: str, user_name: str | None = None) -> JarvisCommandResponse:
    intent = parse_jarvis_intent(text)
    result = execute_jarvis_intent(intent)
    message = _personalize_message(user_name, intent.intent, result)

    if intent.intent == "greet" and not _first_name(user_name):
        message = message.replace("How can I help", f"I'm {ASSISTANT_NAME}. How can I help")

    if USE_GROQ_REPLIES and groq_enabled() and result.success:
        spoken = generate_spoken_reply(
            user_text=text,
            user_name=user_name,
            intent=intent.intent,
            action_success=result.success,
            action_message=result.message,
            assistant_name=ASSISTANT_NAME,
        )
        if spoken:
            message = spoken

    return JarvisCommandResponse(
        success=result.success,
        message=message,
        intent=intent.intent,
        confidence=intent.confidence,
        action=result.action,
        slots=intent.slots,
    )


def jarvis_example_commands() -> list[str]:
    return [
        "Hey Guardian, what time is it?",
        "Open YouTube and play song Believer",
        "Open any app on my PC",
        "Open Windows settings",
        "Search weather in Lahore",
        "Open C drive",
        "Open PowerShell",
        "Lock the computer",
        "Volume up",
        "Take a screenshot",
        "What can you do?",
    ]
