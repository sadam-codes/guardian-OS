import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import check_db_connection, get_db

logger = logging.getLogger("guardian.db")
from config.settings import settings
from schemas.health import HealthResponse

router = APIRouter(tags=["health"])


def _health_payload(db: Session | None = None) -> HealthResponse:
    database = "disconnected"
    if db is not None:
        try:
            check_db_connection(db)
            database = "connected"
            logger.info("Health check: database connected")
        except Exception as exc:
            database = "disconnected"
            logger.warning("Health check: database disconnected — %s", exc)

    status = "ok" if database == "connected" else "degraded"
    return HealthResponse(status=status, app=settings.app_name, database=database)


@router.get("/", response_model=HealthResponse)
def root(db: Session = Depends(get_db)) -> HealthResponse:
    return _health_payload(db)


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    return _health_payload(db)
