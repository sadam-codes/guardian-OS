from pydantic import BaseModel, Field


class JarvisCommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    user_name: str | None = Field(default=None, max_length=120)
    speak: bool = False


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


class JarvisCapabilitiesResponse(BaseModel):
    assistant_name: str
    examples: list[str]
    intents: list[str]
