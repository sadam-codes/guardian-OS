"""Vapi webhook payloads (subset used by Guardian)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VapiWebhookResponse(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    assistantId: str | None = None
    error: str | None = None


class VapiStatusResponse(BaseModel):
    enabled: bool
    has_public_key: bool
    has_private_key: bool
    has_assistant_id: bool
    has_elevenlabs_voice_id: bool = False
    elevenlabs_voice_id: str | None = None
    webhook_path: str
    assistant_tool_name: str
    setup_notes: list[str] = Field(default_factory=list)


class VapiSyncVoiceResponse(BaseModel):
    ok: bool
    message: str


class VapiSpeakRequest(BaseModel):
    text: str


class VapiDiagnoseResponse(BaseModel):
    vapi_configured: bool
    elevenlabs_in_backend: bool
    elevenlabs_key_valid: bool | None = None
    elevenlabs_message: str = ""
    assistant_voice_provider: str | None = None
    assistant_transcriber_model: str | None = None
    fixes: list[str] = Field(default_factory=list)
