from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from helpers.activity_log import STATUS_FAILURE, STATUS_INFO, STATUS_SUCCESS, record_activity
from helpers.jarvis import ASSISTANT_NAME, jarvis_example_commands, process_jarvis_command
from schemas.jarvis import JarvisCapabilitiesResponse, JarvisCommandRequest, JarvisCommandResponse

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
                "web_search",
                "open_folder",
                "lock",
                "volume_up",
                "volume_down",
                "volume_mute",
                "screenshot",
                "help",
            }
        ),
    )


@router.post("/command", response_model=JarvisCommandResponse)
def run_command(body: JarvisCommandRequest, db: Session = Depends(get_db)) -> JarvisCommandResponse:
    response = process_jarvis_command(body.text, user_name=body.user_name)
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
