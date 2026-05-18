from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config.database import get_db
from helpers.activity_log import STATUS_FAILURE, STATUS_INFO, STATUS_SUCCESS, record_activity
from helpers.jarvis import (
    ASSISTANT_NAME,
    jarvis_example_commands,
    plan_jarvis_command,
    process_jarvis_command,
)
from helpers.jarvis_transcribe import transcribe_audio_bytes, transcribe_enabled
from schemas.jarvis import (
    JarvisCapabilitiesResponse,
    JarvisCommandRequest,
    JarvisCommandResponse,
    JarvisPlanResponse,
    JarvisTranscribeResponse,
)

router = APIRouter(prefix="/jarvis", tags=["jarvis"])


@router.get("/capabilities", response_model=JarvisCapabilitiesResponse)
def get_capabilities() -> JarvisCapabilitiesResponse:
    return JarvisCapabilitiesResponse(
        assistant_name=ASSISTANT_NAME,
        examples=jarvis_example_commands(),
        intents=sorted(
            {
                "greet",
                "time",
                "date",
                "open_app",
                "open_path",
                "open_terminal",
                "web_search",
                "open_folder",
                "lock",
                "volume_up",
                "volume_down",
                "volume_mute",
                "screenshot",
                "create_folder",
                "write_text",
                "type_text",
                "send_voice_message",
                "start_call",
                "run_project",
                "run_powershell",
                "empty_recycle_bin",
                "compound",
                "open_terminal_here",
                "clear_context",
                "help",
            }
        ),
    )


@router.post("/plan", response_model=JarvisPlanResponse)
def plan_command(body: JarvisCommandRequest) -> JarvisPlanResponse:
    """Understand command quickly — client speaks jarvis_brief before slow execution."""
    return plan_jarvis_command(body.text, context=body.context)


@router.post("/command", response_model=JarvisCommandResponse)
def run_command(body: JarvisCommandRequest, db: Session = Depends(get_db)) -> JarvisCommandResponse:
    response = process_jarvis_command(
        body.text,
        user_name=body.user_name,
        context=body.context,
        planned_steps=body.planned_steps,
        understood=body.understood,
        jarvis_brief=body.jarvis_brief,
    )
    actor = (body.user_name or "user").strip() or "user"
    record_activity(
        db,
        event_type="jarvis_command",
        status=STATUS_SUCCESS if response.success else STATUS_FAILURE,
        message=f"Jarvis ({actor}): {response.message}",
        target_name=body.text[:100],
    )
    if response.intent == "help":
        record_activity(db, event_type="jarvis_help", status=STATUS_INFO, message="Jarvis help requested")
    return response


@router.post("/transcribe", response_model=JarvisTranscribeResponse)
async def transcribe_voice(file: UploadFile = File(...)) -> JarvisTranscribeResponse:
    if not transcribe_enabled():
        raise HTTPException(
            status_code=503,
            detail="Voice transcription needs GROQ_API_KEY in backend .env",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio too large (max 25 MB)")

    text = transcribe_audio_bytes(data, content_type=file.content_type or "audio/webm")
    if not text:
        raise HTTPException(
            status_code=422,
            detail=(
                "No clear command heard (background noise or too quiet). "
                "Tap mic, speak your command loudly, then pause for one second."
            ),
        )
    return JarvisTranscribeResponse(text=text)
