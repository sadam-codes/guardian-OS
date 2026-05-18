import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from helpers.jarvis_intent import normalize_jarvis_slots
from helpers.jarvis_plan_sanitize import sanitize_plan_steps
from schemas.jarvis import JarvisIntent

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


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
        with urllib.request.urlopen(req, timeout=30) as resp:
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


_GROQ_INTENTS_DOC = (
    "Intents: greet, time, date, lock, volume_up, volume_down, volume_mute, open_app, open_url, "
    "web_search, open_folder, open_path, open_terminal, open_terminal_here, create_folder, write_text, type_text, "
    "run_project, minimize_all, screenshot, shutdown, restart, youtube_search, help, acknowledge, cancel, unknown. "
    "open_path: slots.path = Windows path or drive (C:\\\\, D:\\\\work, C:\\\\Users\\\\name). "
    "create_folder: slots.parent = existing folder path; slots.name = new folder name "
    "(example: parent C:\\\\, name sadam -> C:\\\\sadam). "
    "open_app: slots.app = Windows Start menu app name; optional slots.path = folder to open in that app "
    "(example: Visual Studio Code + path C:\\\\sadam). "
    "To open an existing folder on C: use open_path with C:\\\\foldername — NOT open_folder with name sadam. "
    "open_terminal: slots.shell = wt | cmd | powershell. "
    "write_text: ONLY for creating a text/code file in VS Code, Notepad, or Cursor (slots.content, optional slots.path). "
    "type_text: type into a chat app already open or opened in a prior step — WhatsApp, Telegram, Discord, Teams, Slack. "
    "type_text slots: content = message body; recipient = contact name; send = true to press Enter and send. "
    "For 'open WhatsApp and send hello to Manzar bhai' use open_app(WhatsApp) then type_text(recipient=Manzar bhai, content=hello, send=true). "
    "For 'write message to X' without send, omit send or set send=false. NEVER write_text or Visual Studio Code for chat apps. "
    "run_project: slots.path or slots.folder = project directory. "
    "web_search/youtube_search: slots.query. Never use web_search for drives, folders, or shells. "
    "For YouTube with a song use youtube_search (not open_url). For open youtube only use open_app with slots.app=YouTube. "
    "Roman Urdu OK (kholo, banao, folder banao)."
)


def _steps_from_groq_payload(data: dict) -> list[JarvisIntent]:
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        intent_name = str(data.get("intent", "unknown")).strip() or "unknown"
        raw_slots = data.get("slots") or {}
        slots: dict[str, str] = {}
        if isinstance(raw_slots, dict):
            for k, v in raw_slots.items():
                if v is None:
                    continue
                slots[str(k).strip()] = str(v).strip()
        conf = float(data.get("confidence", 0.75))
        return [
            JarvisIntent(
                intent=intent_name,
                confidence=conf,
                slots=normalize_jarvis_slots(intent_name, slots),
            )
        ]

    out: list[JarvisIntent] = []
    conf = float(data.get("confidence", 0.85))
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
        out.append(
            JarvisIntent(
                intent=intent_name,
                confidence=conf,
                slots=normalize_jarvis_slots(intent_name, slots),
            )
        )
    return out


def parse_steps_with_groq(text: str) -> list[JarvisIntent] | None:
    """Ask Groq for an ordered plan (one or more steps). Fully dynamic — no hardcoded phrases."""
    system = (
        "You convert Windows voice commands into an execution plan. Reply with JSON only (no markdown). "
        'Format: {"confidence":0-1,"steps":[{"intent":"...","slots":{...}}, ...]}. '
        "Use multiple steps when the user chains actions with and/then/phir/aur (e.g. open C drive AND create folder sadam). "
        "Order steps logically. One action per step. "
        + _GROQ_INTENTS_DOC
    )
    user = f'Command: "{text}"'
    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=500,
        temperature=0.05,
    )
    if not raw:
        return None
    try:
        data = _parse_json_content(raw)
        steps = _steps_from_groq_payload(data)
        if steps:
            steps = sanitize_plan_steps(steps)
        return steps or None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def parse_intent_with_groq(text: str) -> JarvisIntent | None:
    steps = parse_steps_with_groq(text)
    if steps:
        return steps[0]
    return None


def generate_spoken_reply(
    *,
    user_text: str,
    user_name: str | None,
    intent: str,
    action_success: bool,
    action_message: str,
    assistant_name: str = "Guardian",
) -> str | None:
    name_line = f"The user's first name is {user_name.split()[0]}." if user_name and user_name.strip() else ""
    system = (
        f"You are {assistant_name}, a calm female voice assistant on a Windows PC. "
        "Write exactly one or two short sentences to be read aloud. "
        "Sound natural and warm — like a woman speaking, not robotic. "
        "No markdown, bullet points, emoji, or quotes around the whole reply. "
        "Confirm what you did using the action result; if it failed, say so briefly."
    )
    user_msg = (
        f"{name_line}\n"
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
        max_tokens=100,
        temperature=0.65,
    )
    if not raw:
        return None
    return raw.strip().strip('"')
