import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from config.settings import settings

logger = logging.getLogger("guardian.db")


def _db_label(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    port = parsed.port or 5432
    name = (parsed.path or "/postgres").lstrip("/") or "postgres"
    return f"{host}:{port}/{name}"


def _normalize_database_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        return url

    query = parse_qs(parsed.query)
    query.pop("pgbouncer", None)
    new_query = urlencode({k: v[0] for k, v in query.items()})
    return urlunparse(parsed._replace(query=new_query))


def _create_engine() -> Engine:
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not set in .env")

    url = _normalize_database_url(settings.database_url)
    connect_args: dict = {}
    if "sslmode" not in url:
        connect_args["sslmode"] = "require"

    return create_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection(db: Session) -> bool:
    db.execute(text("SELECT 1"))
    return True


def init_db() -> None:
    from models import ActivityLog, Base, Register  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE register ADD COLUMN IF NOT EXISTS role VARCHAR(20) "
                "NOT NULL DEFAULT 'user'"
            )
        )
    logger.info("Database tables ensured")


def log_db_status() -> bool:
    label = _db_label(settings.database_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connected: %s", label)
        print(f"[DB] Connected to {label}")
        return True
    except Exception as exc:
        logger.error("Database connection failed (%s): %s", label, exc)
        print(f"[DB] Connection failed ({label}): {exc}")
        return False
