from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class JarvisActionResult:
    success: bool
    message: str
    action: str
    target_label: str | None = None


class JarvisSessionContext(BaseModel):
    """Client-held session state for nested follow-up commands."""

    active: bool = False
    updated_at: float = 0
    last_intent: str | None = None
    last_app: str | None = None
    last_path: str | None = None
    last_label: str | None = None


class JarvisCommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    user_name: str | None = Field(default=None, max_length=120)
    speak: bool = False
    context: JarvisSessionContext | None = None


class JarvisIntent(BaseModel):
    intent: str
    confidence: float
    slots: dict[str, str] = Field(default_factory=dict)


class JarvisCommandResponse(BaseModel):
    success: bool
    message: str
    intent: str
    confidence: float
    action: str | None = None
    slots: dict[str, str] = Field(default_factory=dict)
    context: JarvisSessionContext = Field(default_factory=JarvisSessionContext)


class JarvisTranscribeResponse(BaseModel):
    text: str


class JarvisCapabilitiesResponse(BaseModel):
    assistant_name: str
    examples: list[str]
    intents: list[str]
    voice_mode: str = "groq_whisper"
