from datetime import datetime

from pydantic import BaseModel


class ActivityLogItem(BaseModel):
    id: int
    event_type: str
    status: str
    message: str
    actor_name: str | None
    target_name: str | None
    created_at: datetime


class ActivityLogsResponse(BaseModel):
    count: int
    logs: list[ActivityLogItem]


class ActivitySummaryResponse(BaseModel):
    total_users: int
    admin_count: int
    user_count: int
    total_events: int
