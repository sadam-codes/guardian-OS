from pydantic import BaseModel, Field

from schemas.jarvis import JarvisCommandResponse, JarvisSessionContext


class WorkflowStageLog(BaseModel):
    stage: str
    status: str
    detail: str
    duration_ms: float = 0


class GuardianWorkflowRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    user_id: int | None = None
    user_name: str | None = Field(default=None, max_length=120)
    identity_verified: bool = False
    gesture: str | None = Field(default=None, max_length=32)
    context: JarvisSessionContext | None = None
    skip_safety: bool = False


class GuardianWorkflowResponse(BaseModel):
    success: bool
    message: str
    intent: str
    confidence: float
    action: str | None = None
    slots: dict[str, str] = Field(default_factory=dict)
    context: JarvisSessionContext = Field(default_factory=JarvisSessionContext)
    stages: list[WorkflowStageLog] = Field(default_factory=list)
    security_blocked: bool = False
    jarvis: JarvisCommandResponse | None = None


class GuardianStatusResponse(BaseModel):
    pipeline: list[str]
    assistant_name: str
    os_control_enabled: bool
    memory_entries: int
    supported_gestures: list[str]
