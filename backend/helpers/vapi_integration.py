"""Vapi.ai — voice in/out + webhook tools that run Guardian/Jarvis."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

VAPI_PUBLIC_KEY = os.getenv("VAPI_PUBLIC_KEY", "").strip()
VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY", "").strip()
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "").strip()
VAPI_WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()
GUARDIAN_TOOL_NAME = os.getenv("VAPI_GUARDIAN_TOOL_NAME", "run_guardian_command")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
VAPI_API_BASE = "https://api.vapi.ai"

# Paste into Vapi Dashboard → Assistant → Model → Tools
GUARDIAN_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": GUARDIAN_TOOL_NAME,
        "description": (
            "Execute a Guardian OS command on the user's Windows PC: open apps, folders, "
            "WhatsApp messages, voice messages, calls, recycle bin, PowerShell tasks, etc. "
            "Pass the user's full natural-language request in command."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Full user request, e.g. open Chrome, empty recycle bin",
                },
                "user_name": {
                    "type": "string",
                    "description": "Optional user first name for personalization",
                },
            },
            "required": ["command"],
        },
    },
}


def vapi_enabled() -> bool:
    return bool(VAPI_PRIVATE_KEY or VAPI_ASSISTANT_ID)


def vapi_web_configured() -> bool:
    return bool(VAPI_PUBLIC_KEY and VAPI_ASSISTANT_ID)


def elevenlabs_voice_configured() -> bool:
    return bool(ELEVENLABS_VOICE_ID)


def build_elevenlabs_voice_payload() -> dict[str, Any]:
    """Vapi voice block for ElevenLabs (provider id is 11labs in Vapi API)."""
    return {
        "provider": "11labs",
        "voiceId": ELEVENLABS_VOICE_ID,
        "model": os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5").strip() or "eleven_turbo_v2_5",
    }


def build_vapi_web_voice_payload() -> dict[str, Any] | None:
    """Voice for Vapi web calls. ElevenLabs: only voiceId here — API key lives in Vapi Integrations."""
    default_provider = "11labs" if ELEVENLABS_VOICE_ID else "openai"
    default_voice = ELEVENLABS_VOICE_ID if ELEVENLABS_VOICE_ID else "alloy"
    provider = os.getenv("VAPI_VOICE_PROVIDER", default_provider).strip() or default_provider
    voice_id = os.getenv("VAPI_VOICE_ID", default_voice).strip() or default_voice
    if provider == "11labs" and ELEVENLABS_VOICE_ID:
        return build_elevenlabs_voice_payload()
    if provider in ("none", "skip", "browser"):
        return None
    return {"provider": provider, "voiceId": voice_id}


def build_web_transcriber_payload() -> dict[str, Any]:
    """Browser-safe Deepgram model (flux-* can warn: unsupported input processor audio)."""
    return {
        "provider": "deepgram",
        "model": os.getenv("VAPI_WEB_TRANSCRIBER_MODEL", "nova-2").strip() or "nova-2",
        "language": "en",
    }


def _patch_assistant(payload: dict[str, Any]) -> tuple[bool, str]:
    if not VAPI_PRIVATE_KEY:
        return False, "Set VAPI_PRIVATE_KEY in backend .env."
    if not VAPI_ASSISTANT_ID:
        return False, "Set VAPI_ASSISTANT_ID in backend .env."

    url = f"{VAPI_API_BASE}/assistant/{VAPI_ASSISTANT_ID}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Guardian-OS/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if 200 <= getattr(resp, "status", 200) < 300:
                return True, "Vapi assistant updated."
            return False, f"Vapi returned status {getattr(resp, 'status', '?')}."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        return False, f"Vapi API error {exc.code}: {detail}"
    except urllib.error.URLError as exc:
        return False, f"Could not reach Vapi API: {exc.reason}"


def sync_vapi_assistant_voice() -> tuple[bool, str]:
    """PATCH Vapi assistant so spoken replies use ELEVENLABS_VOICE_ID."""
    if not VAPI_PRIVATE_KEY:
        return False, "Set VAPI_PRIVATE_KEY in backend .env (Vapi private API key)."
    if not VAPI_ASSISTANT_ID:
        return False, "Set VAPI_ASSISTANT_ID in backend .env."
    if not ELEVENLABS_VOICE_ID:
        return False, "Set ELEVENLABS_VOICE_ID in backend .env."

    ok, msg = _patch_assistant({"voice": build_elevenlabs_voice_payload()})
    if ok:
        return True, f"Vapi assistant voice set to ElevenLabs {ELEVENLABS_VOICE_ID}."
    return False, msg


def sync_vapi_assistant_web() -> tuple[bool, str]:
    """PATCH Vapi voice + nova-2 transcriber. ElevenLabs key only in Vapi Dashboard, not backend .env."""
    transcriber = build_web_transcriber_payload()
    voice = build_vapi_web_voice_payload()
    payload: dict[str, Any] = {
        "transcriber": transcriber,
        "backgroundDenoisingEnabled": False,
    }
    if voice:
        payload["voice"] = voice
    ok, msg = _patch_assistant(payload)
    if ok:
        voice_note = (
            f"voice {voice['provider']}/{voice['voiceId']}"
            if voice
            else "voice unchanged (browser fallback for speech)"
        )
        return True, f"Vapi web settings applied ({voice_note}, transcriber {transcriber['model']})."
    return False, msg


def verify_webhook_secret(headers: dict[str, str]) -> bool:
    if not VAPI_WEBHOOK_SECRET:
        return True
    for key in ("x-vapi-secret", "authorization", "Authorization"):
        val = headers.get(key, "")
        if val == VAPI_WEBHOOK_SECRET or val == f"Bearer {VAPI_WEBHOOK_SECRET}":
            return True
    return False


def _run_guardian_command(command: str, user_name: str | None) -> str:
    from helpers.jarvis import process_jarvis_command

    text = (command or "").strip()
    if not text:
        return "No command was provided."
    try:
        resp = process_jarvis_command(text, user_name=user_name or None)
        prefix = "Done. " if resp.success else "Sorry. "
        return f"{prefix}{resp.message}"
    except Exception as exc:
        logger.exception("Guardian command failed from Vapi: %s", exc)
        return f"Guardian could not run that command: {exc}"


def handle_vapi_webhook(body: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Handle Vapi server URL POST. Returns JSON body for Vapi."""
    if headers and not verify_webhook_secret(headers):
        return {"error": "Invalid webhook secret."}

    message = body.get("message") or {}
    mtype = message.get("type") or ""

    if mtype == "assistant-request":
        if VAPI_ASSISTANT_ID:
            return {"assistantId": VAPI_ASSISTANT_ID}
        return {"error": "Guardian assistant is not configured. Set VAPI_ASSISTANT_ID in .env."}

    if mtype == "tool-calls":
        results: list[dict[str, Any]] = []
        tool_list = message.get("toolCallList") or []
        for item in tool_list:
            name = item.get("name") or ""
            if name != GUARDIAN_TOOL_NAME:
                continue
            params = item.get("parameters") or {}
            if isinstance(params, str):
                cmd = params
                user = None
            else:
                cmd = str(params.get("command") or params.get("text") or "")
                user = params.get("user_name")
            out = _run_guardian_command(cmd, str(user) if user else None)
            results.append(
                {
                    "name": name,
                    "toolCallId": item.get("id") or "",
                    "result": out,
                }
            )
        return {"results": results}

    # Informational events — no response required
    logger.debug("Vapi webhook event: %s", mtype)
    return {}


def fetch_vapi_assistant() -> dict[str, Any] | None:
    if not VAPI_PRIVATE_KEY or not VAPI_ASSISTANT_ID:
        return None
    url = f"{VAPI_API_BASE}/assistant/{VAPI_ASSISTANT_ID}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {VAPI_PRIVATE_KEY}", "User-Agent": "Guardian-OS/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Could not fetch Vapi assistant: %s", exc)
        return None


def vapi_diagnose() -> dict[str, Any]:
    fixes: list[str] = []
    if not vapi_web_configured():
        fixes.append("Set VITE_VAPI_PUBLIC_KEY and VITE_VAPI_ASSISTANT_ID in frontend .env.")
    fixes.append(
        "ElevenLabs: voice ID in assistant + API key in Vapi Dashboard → Integrations only. "
        "Backend ELEVENLABS_API_KEY is NOT required."
    )
    fixes.append("If Vapi audio is silent, browser voice speaks as fallback.")
    fixes.append("Unmute browser tab + Windows output volume.")
    fixes.append("POST /api/vapi/sync-web after changing VAPI_VOICE_PROVIDER in .env.")

    asst = fetch_vapi_assistant() or {}
    voice = asst.get("voice") or {}
    transcriber = asst.get("transcriber") or {}

    return {
        "vapi_configured": vapi_web_configured(),
        "elevenlabs_in_backend": False,
        "elevenlabs_key_valid": None,
        "elevenlabs_message": (
            "Use ElevenLabs API key in Vapi Integrations (not backend .env). "
            f"Voice ID in assistant: {ELEVENLABS_VOICE_ID or '(set ELEVENLABS_VOICE_ID)'}"
        ),
        "assistant_voice_provider": voice.get("provider"),
        "assistant_voice_id": voice.get("voiceId"),
        "assistant_transcriber_model": transcriber.get("model"),
        "fixes": fixes,
    }


def setup_notes() -> list[str]:
    notes = [
        "Create a Vapi account at https://dashboard.vapi.ai",
        "POST /api/vapi/sync-web — sets ElevenLabs voice ID + nova-2 (key only in Vapi Integrations)",
        "Optional: ELEVENLABS_VOICE_ID in backend .env to sync voice ID to assistant",
        "Create an Assistant with a model (OpenAI, Groq via custom LLM, etc.)",
        f"Add tool: {GUARDIAN_TOOL_NAME} (see GET /api/vapi/tool-schema)",
        "Set Assistant Server URL to: https://YOUR_PUBLIC_HOST/api/vapi/webhook",
        "For local dev use ngrok: ngrok http 8000 → paste https URL + /api/vapi/webhook",
        "Set VAPI_ASSISTANT_ID, VAPI_PUBLIC_KEY (browser), VAPI_PRIVATE_KEY in backend .env",
        "Set VITE_VAPI_PUBLIC_KEY and VITE_VAPI_ASSISTANT_ID in frontend .env",
    ]
    return notes
