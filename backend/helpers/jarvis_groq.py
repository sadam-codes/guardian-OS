import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
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


def parse_intent_with_groq(text: str) -> JarvisIntent | None:
    system = (
        "You classify short Windows voice commands. Reply with JSON only (no markdown): "
        '{"intent":"...","confidence":0-1,"slots":{...}}. '
        "Intents: greet, time, date, lock, volume_up, volume_down, volume_mute, open_app, open_url, "
        "web_search, open_folder, open_path, open_terminal, minimize_all, screenshot, shutdown, restart, "
        "youtube_search, help, acknowledge, cancel, unknown. "
        "Rules: Use open_path with slots.path for any local path, drive, or folder (examples: C:\\\\Users, "
        "D:\\\\, E:\\\\work\\\\notes.txt, Desktop folder as a path if user gives a path). "
        "Use open_terminal with slots.shell (wt | cmd | powershell) for terminal, CMD, command prompt, "
        "PowerShell, pwsh, or Windows Terminal. "
        "Use web_search only for real internet questions or when the user clearly wants Google/the web — "
        "never for opening shells, drives, or files. "
        "open_app: start menu apps only when it is clearly an application name, not a path. "
        "Understand Roman Urdu / mixed phrases the same way (e.g. kholo, jao, c drive, terminal chalao)."
    )
    user = f'Command: "{text}"'
    raw = _chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=180,
        temperature=0.1,
    )
    if not raw:
        return None
    try:
        data = _parse_json_content(raw)
        raw_slots = data.get("slots") or {}
        slots: dict[str, str] = {}
        if isinstance(raw_slots, dict):
            for k, v in raw_slots.items():
                if v is None:
                    continue
                slots[str(k).strip()] = str(v).strip()
        return JarvisIntent(
            intent=str(data.get("intent", "unknown")).strip() or "unknown",
            confidence=float(data.get("confidence", 0.75)),
            slots=slots,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
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
        f"You are {assistant_name}, a calm male voice assistant on a Windows PC. "
        "Write exactly one or two short sentences to be read aloud. "
        "Sound natural and direct — like a man speaking, not robotic. "
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
