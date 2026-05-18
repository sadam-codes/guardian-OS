import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import engine, init_db, log_db_status
from config.settings import settings
from controllers import activity_router, face_router, guardian_router, health_router, jarvis_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[APP] Starting {settings.app_name}...")
    log_db_status()
    init_db()
    print("[DB] Register table ready.")
    yield
    print("[DB] Closing database connections...")
    engine.dispose()
    print("[APP] Shutdown complete.")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(face_router)
app.include_router(activity_router)
app.include_router(jarvis_router)
app.include_router(guardian_router)
