"""Vapi.ai webhooks and setup helpers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from helpers.elevenlabs_tts import (
    elevenlabs_configured,
    elevenlabs_status,
    synthesize_mp3,
    validate_elevenlabs_key,
)
from helpers.vapi_integration import (
    ELEVENLABS_VOICE_ID,
    GUARDIAN_TOOL_NAME,
    GUARDIAN_TOOL_SCHEMA,
    elevenlabs_voice_configured,
    handle_vapi_webhook,
    setup_notes,
    fetch_vapi_assistant,
    sync_vapi_assistant_web,
    vapi_diagnose,
    vapi_enabled,
    vapi_web_configured,
)
from schemas.vapi import (
    VapiDiagnoseResponse,
    VapiSpeakRequest,
    VapiStatusResponse,
    VapiSyncVoiceResponse,
    VapiWebhookResponse,
)

router = APIRouter(prefix="/vapi", tags=["vapi"])


@router.get("/status", response_model=VapiStatusResponse)
def vapi_status() -> VapiStatusResponse:
    return VapiStatusResponse(
        enabled=vapi_enabled(),
        has_public_key=bool(__import__("os").getenv("VAPI_PUBLIC_KEY", "").strip()),
        has_private_key=bool(__import__("os").getenv("VAPI_PRIVATE_KEY", "").strip()),
        has_assistant_id=bool(__import__("os").getenv("VAPI_ASSISTANT_ID", "").strip()),
        has_elevenlabs_voice_id=elevenlabs_voice_configured(),
        elevenlabs_voice_id=ELEVENLABS_VOICE_ID or None,
        webhook_path="/api/vapi/webhook",
        assistant_tool_name=GUARDIAN_TOOL_NAME,
        setup_notes=setup_notes(),
    )


@router.post("/sync-voice", response_model=VapiSyncVoiceResponse)
def vapi_sync_voice() -> VapiSyncVoiceResponse:
    """Apply ElevenLabs voice + browser-safe transcriber to your Vapi assistant."""
    ok, message = sync_vapi_assistant_web()
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return VapiSyncVoiceResponse(ok=True, message=message)


@router.post("/sync-web", response_model=VapiSyncVoiceResponse)
def vapi_sync_web() -> VapiSyncVoiceResponse:
    """Same as sync-voice — voice + nova-2 transcriber for Chrome/Edge web calls."""
    ok, message = sync_vapi_assistant_web()
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return VapiSyncVoiceResponse(ok=True, message=message)


@router.get("/diagnose", response_model=VapiDiagnoseResponse)
def vapi_diagnose_route() -> VapiDiagnoseResponse:
    """Why Vapi voice may be silent + how to fix."""
    return VapiDiagnoseResponse(**vapi_diagnose())


@router.post("/speak")
def vapi_speak(body: VapiSpeakRequest) -> Response:
    """Play Guardian reply via ElevenLabs (works even when Vapi integration 401)."""
    audio, err = synthesize_mp3(body.text)
    if not audio:
        raise HTTPException(status_code=400, detail=err or "Could not synthesize speech.")
    return Response(content=audio, media_type="audio/mpeg")


@router.get("/elevenlabs-check")
def elevenlabs_check() -> dict[str, Any]:
    ok, msg = validate_elevenlabs_key()
    return {
        "ok": ok,
        "configured": elevenlabs_configured(),
        "message": msg,
        **elevenlabs_status(),
    }

@router.get("/tool-schema")
def vapi_tool_schema() -> dict[str, Any]:
    """Copy this JSON into your Vapi Assistant → Tools."""
    return GUARDIAN_TOOL_SCHEMA


@router.post("/webhook")
async def vapi_webhook(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    headers = {k: v for k, v in request.headers.items()}
    out = handle_vapi_webhook(body, headers=headers)
    if out.get("error") and "secret" in str(out.get("error", "")).lower():
        raise HTTPException(status_code=401, detail=out["error"])
    return out
