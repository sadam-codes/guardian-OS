from sqlalchemy.orm import Session

from models.activity_log import ActivityLog

STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"
STATUS_INFO = "info"
STATUS_WARNING = "warning"


def record_activity(
    db: Session,
    *,
    event_type: str,
    message: str,
    status: str = STATUS_INFO,
    actor_name: str | None = None,
    target_name: str | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        event_type=event_type,
        status=status,
        message=message,
        actor_name=actor_name,
        target_name=target_name,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_activity_logs(
    db: Session,
    *,
    limit: int = 100,
    after_id: int | None = None,
) -> list[ActivityLog]:
    query = db.query(ActivityLog).order_by(ActivityLog.id.desc())
    if after_id is not None:
        query = query.filter(ActivityLog.id > after_id)
    return query.limit(min(limit, 200)).all()


def activity_summary(db: Session) -> dict:
    from models.register import Register

    total_users = db.query(Register).count()
    admin_count = db.query(Register).filter(Register.role == "admin").count()
    log_count = db.query(ActivityLog).count()
    return {
        "total_users": total_users,
        "admin_count": admin_count,
        "user_count": total_users - admin_count,
        "total_events": log_count,
    }
