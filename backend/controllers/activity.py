from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config.database import get_db
from helpers.activity_log import activity_summary, list_activity_logs
from schemas.activity import ActivityLogItem, ActivityLogsResponse, ActivitySummaryResponse

router = APIRouter(prefix="/activity", tags=["activity"])


def _require_admin(actor_role: str | None) -> None:
    if actor_role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")


@router.get("/logs", response_model=ActivityLogsResponse)
def get_activity_logs(
    actor_role: str = Query(...),
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ActivityLogsResponse:
    _require_admin(actor_role)
    logs = list_activity_logs(db, limit=limit, after_id=after_id)
    items = [
        ActivityLogItem(
            id=log.id,
            event_type=log.event_type,
            status=log.status,
            message=log.message,
            actor_name=log.actor_name,
            target_name=log.target_name,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return ActivityLogsResponse(count=len(items), logs=items)


@router.get("/summary", response_model=ActivitySummaryResponse)
def get_activity_summary(
    actor_role: str = Query(...),
    db: Session = Depends(get_db),
) -> ActivitySummaryResponse:
    _require_admin(actor_role)
    data = activity_summary(db)
    return ActivitySummaryResponse(**data)
