import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

APP_NAME = os.getenv("APP_NAME", "guardian-OS")
DEBUG = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip().strip('"')


class Settings:
    app_name: str = APP_NAME
    debug: bool = DEBUG
    database_url: str = DATABASE_URL


settings = Settings()
