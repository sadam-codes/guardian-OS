from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class JarvisActionResult:
    success: bool
    message: str
    action: str
    target_label: str | None = None


class ContextTurn(BaseModel):
    """One user command and what Guardian did."""

    user: str = ""
    intent: str = ""
    success: bool = True
    summary: str = ""


class JarvisSessionContext(BaseModel):
    """Client-held session state — paths, apps, and recent prompts."""

    active: bool = False
    updated_at: float = 0
    last_intent: str | None = None
    last_app: str | None = None
    last_path: str | None = None
    last_label: str | None = None
    last_drive: str | None = None
    last_user_text: str | None = None
    last_recipient: str | None = None
    recent_turns: list[ContextTurn] = Field(default_factory=list)


class JarvisCommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    user_name: str | None = Field(default=None, max_length=120)
    speak: bool = False
    context: JarvisSessionContext | None = None
    # From POST /jarvis/plan — skips re-planning so execute is faster
    planned_steps: list["JarvisIntent"] | None = None
    understood: str | None = None
    jarvis_brief: str | None = None


class JarvisPlanResponse(BaseModel):
    """Fast plan only (for speaking before slow OS actions)."""

    understood: str = ""
    jarvis_brief: str = ""
    intent: str = "unknown"
    confidence: float = 0.0
    planned_steps: list["JarvisIntent"] = Field(default_factory=list)
    context: JarvisSessionContext = Field(default_factory=JarvisSessionContext)


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
