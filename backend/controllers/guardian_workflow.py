from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.database import get_db
from helpers.activity_log import STATUS_FAILURE, STATUS_SUCCESS, STATUS_WARNING, record_activity
from helpers.guardian_events import list_recent_events
from helpers.guardian_memory import get_frequent_commands
from helpers.guardian_workflow import execute_guardian_workflow, guardian_status
from schemas.guardian_workflow import (
    GuardianStatusResponse,
    GuardianWorkflowRequest,
    GuardianWorkflowResponse,
)

router = APIRouter(prefix="/guardian", tags=["guardian-workflow"])


@router.get("/status", response_model=GuardianStatusResponse)
def get_guardian_status() -> GuardianStatusResponse:
    data = guardian_status()
    return GuardianStatusResponse(**data)


@router.get("/events")
def get_recent_events(limit: int = Query(default=30, ge=1, le=50)):
    return {"events": list_recent_events(limit)}


@router.get("/memory/frequent")
def get_user_frequent_commands(
    user_id: int | None = Query(default=None),
    user_name: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=10),
):
    return {"commands": get_frequent_commands(user_id, user_name, limit)}


@router.post("/workflow/execute", response_model=GuardianWorkflowResponse)
def run_workflow(
    body: GuardianWorkflowRequest,
    db: Session = Depends(get_db),
) -> GuardianWorkflowResponse:
    response = execute_guardian_workflow(body)
    actor = (body.user_name or "user").strip() or "user"
    status = STATUS_SUCCESS if response.success else STATUS_FAILURE
    if response.security_blocked:
        status = STATUS_WARNING
    record_activity(
        db,
        event_type="guardian_workflow",
        status=status,
        message=f"Guardian ({actor}): {response.message}",
        target_name=body.text[:100] if body.text else (body.gesture or ""),
    )
    return response
