import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from helpers.jarvis_intent import normalize_jarvis_slots
from helpers.jarvis_system import build_system_context_block
from helpers.jarvis_plan_sanitize import sanitize_plan_steps
from schemas.jarvis import JarvisIntent, JarvisSessionContext

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


@dataclass
class GroqPlan:
    """Groq understood the user and produced an execution plan."""

    steps: list[JarvisIntent]
    understood: str = ""
    jarvis_brief: str = ""
    confidence: float = 0.0


def _api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def groq_enabled() -> bool:
    return bool(_api_key())


def _model() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _chat(messages: list[dict[str, str]], *, max_tokens: int = 120, temperature: float = 0.65) -> str | None:
    if not groq_enabled():
        return None
    payload = json.dumps(
        {
            "model": _model(),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GROQ_CHAT_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
            "User-Agent": "guardian-os-jarvis/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("choices") or [{}])[0].get("message", {}).get("content")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        logger.warning("Groq API HTTP %s: %s", exc.code, body or exc.reason)
        return None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Groq API error: %s", exc)
        return None


def _parse_json_content(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(text)


_GROQ_BRAIN_SYSTEM = (
    "You are the BRAIN of Guardian — a Windows voice assistant. "
    "The user may speak English or Urdu — understand both, but write understood and jarvis_brief in ENGLISH only. "
    "Reply with JSON only (no markdown):\n"
    '{"confidence":0-1,"understood":"one line what user wants","jarvis_brief":"short English line for the user (what you will do)",'
    '"steps":[{"intent":"...","slots":{...}}]}\n'
    "Use multiple steps for and/then/phir/aur chains. One action per step.\n\n"
    "EXECUTOR INTENTS (pick the best — do NOT memorize static app lists):\n"
    "- open_terminal: user wants a VISIBLE terminal WINDOW on screen (open/start terminal, PowerShell, cmd). "
    "slots.shell = wt | powershell | cmd. NEVER use run_powershell for this.\n"
    "- empty_recycle_bin: delete ALL items in Recycle Bin at once (one command, no confirmations). "
    "Use when user says empty/clear/delete all in recycle bin. slots.open_after=true only if they also want the folder open after.\n"
    "- run_powershell: run a command in the BACKGROUND (no window). slots.command = full request. "
    "Returns text output only. Use for disk space, processes, services, files — NOT for emptying recycle bin "
    "(use empty_recycle_bin). NOT for 'open terminal'.\n"
    "- open_app: slots.app = what to open (browser, Chrome, WhatsApp, Notepad, Calculator, VS Code…). "
    "Use app=browser for generic browser.\n"
    "- open_path: slots.path = full Windows path or C:\\\\folder\n"
    "- open_folder: desktop|documents|downloads|pictures|home\n"
    "- web_search / youtube_search: slots.query\n"
    "- send_voice_message: WhatsApp VOICE note (recorded audio), NOT typed text. slots.content = words to speak, "
    "slots.recipient = contact. NOT for voice call / audio call.\n"
    "- start_call: WhatsApp audio or video CALL. slots.recipient = contact, "
    "slots.call_type = audio | video. Use for video call, audio call, voice call, phone call.\n"
    "- type_text: typed TEXT only — NOT voice messages or calls\n"
    "- create_folder: make a DIRECTORY only (never a .txt file). slots.name = folder name, "
    "slots.parent = drive/path like D:\\\\ or C:\\\\Users\\\\You. "
    "Use for 'create folder named asad on D drive'. NEVER use write_text for folders.\n"
    "- write_text: create/open a code or text FILE in an editor — NOT for folders\n"
    "- run_project: dev server in a project folder\n"
    "- greet, time, date, lock, volume_up/down/mute, minimize_all, screenshot, shutdown, restart, help, cancel\n\n"
    "RULES: Never web_search for local paths. YouTube song -> youtube_search. "
    "open terminal / open PowerShell -> open_terminal only. empty/delete all recycle bin -> empty_recycle_bin ONLY "
    "(never open_app + run_powershell loops). show disk/processes -> run_powershell. "
    "jarvis_brief must match the intent (do not say 'opening terminal' for run_powershell). "
    "create folder -> create_folder only (one step). Do not add write_text or open_path unless user asked to open. "
    "When SESSION MEMORY is provided, resolve 'there/it/same drive' from last_path / last_drive."
)


def _steps_from_payload(data: dict, *, user_text: str) -> list[JarvisIntent]:
    steps_raw = data.get("steps")
    conf = float(data.get("confidence", 0.85))
    brief = str(data.get("jarvis_brief", "")).strip()
    understood = str(data.get("understood", "")).strip()

    if not isinstance(steps_raw, list) or not steps_raw:
        intent_name = str(data.get("intent", "unknown")).strip() or "unknown"
        raw_slots = data.get("slots") or {}
        slots: dict[str, str] = {}
        if isinstance(raw_slots, dict):
            for k, v in raw_slots.items():
                if v is None:
                    continue
                slots[str(k).strip()] = str(v).strip()
        slots.setdefault("user_text", user_text)
        if brief:
            slots["jarvis_brief"] = brief
        if understood:
            slots["understood"] = understood
        return [
            JarvisIntent(
                intent=intent_name,
                confidence=conf,
                slots=normalize_jarvis_slots(intent_name, slots),
            )
        ]

    out: list[JarvisIntent] = []
    for item in steps_raw[:8]:
        if not isinstance(item, dict):
            continue
        intent_name = str(item.get("intent", "")).strip()
        if not intent_name:
            continue
        raw_slots = item.get("slots") or {}
        slots: dict[str, str] = {}
        if isinstance(raw_slots, dict):
            for k, v in raw_slots.items():
                if v is None:
                    continue
                slots[str(k).strip()] = str(v).strip()
        slots.setdefault("user_text", user_text)
        if brief:
            slots["jarvis_brief"] = brief
        if understood:
            slots["understood"] = understood
        out.append(
            JarvisIntent(
                intent=intent_name,
                confidence=conf,
                slots=normalize_jarvis_slots(intent_name, slots),
            )
        )
    return out


def plan_with_groq(
    text: str,
    *,
    session: JarvisSessionContext | None = None,
) -> GroqPlan | None:
    """Single Groq call: understand user + brief for Jarvis + execution steps."""
    clean = " ".join(text.strip().split())
    if not clean:
        return None

    from helpers.jarvis_context import context_is_active
    from helpers.jarvis_session_memory import apply_context_to_steps, build_session_context_block

    sys_ctx = build_system_context_block()
    mem_ctx = build_session_context_block(session)
    user_block = f"{sys_ctx}\n\n"
    if mem_ctx:
        user_block += f"{mem_ctx}\n\n"
    user_block += f'User said now: "{clean}"'

    raw = _chat(
        [
            {"role": "system", "content": _GROQ_BRAIN_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        max_tokens=600,
        temperature=0.15,
    )
    if not raw:
        return None
    try:
        data = _parse_json_content(raw)
        steps = _steps_from_payload(data, user_text=clean)
        if not steps:
            return None
        steps = sanitize_plan_steps(steps)
        if not steps:
            return None
        if context_is_active(session):
            steps = apply_context_to_steps(steps, session, user_text=clean)
        return GroqPlan(
            steps=steps,
            understood=str(data.get("understood", "")).strip(),
            jarvis_brief=str(data.get("jarvis_brief", "")).strip(),
            confidence=float(data.get("confidence", 0.85)),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Groq plan JSON error: %s | %s", exc, raw[:250])
        return None


def parse_steps_with_groq(text: str) -> list[JarvisIntent] | None:
    plan = plan_with_groq(text)
    return plan.steps if plan else None


def parse_intent_with_groq(text: str) -> JarvisIntent | None:
    plan = plan_with_groq(text)
    return plan.steps[0] if plan and plan.steps else None


def generate_spoken_reply(
    *,
    user_text: str,
    user_name: str | None,
    intent: str,
    action_success: bool,
    action_message: str,
    assistant_name: str = "Guardian",
    jarvis_brief: str | None = None,
) -> str | None:
    name_line = f"The user's first name is {user_name.split()[0]}." if user_name and user_name.strip() else ""
    brief_line = f"Plan (internal): {jarvis_brief}" if jarvis_brief else ""
    system = (
        f"You are {assistant_name}, a calm female voice assistant on a Windows PC. "
        "Write exactly one or two short sentences to be read aloud. "
        "Sound natural and warm. Reply in ENGLISH only. "
        "No markdown, emoji, or quotes around the whole reply. "
        "Confirm what you did using the action result. "
        "If intent is run_powershell, summarize command output — do NOT say you opened a terminal window. "
        "If intent is open_terminal, say the terminal window was opened."
    )
    user_msg = (
        f"{name_line}\n{brief_line}\n"
        f'User said: "{user_text}"\n'
        f"Intent: {intent}\n"
        f"Action OK: {action_success}\n"
        f"System result: {action_message}"
    )
    raw = _chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=120,
        temperature=0.65,
    )
    if not raw:
        return None
    return raw.strip().strip('"')
