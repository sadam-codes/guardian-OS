from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from helpers.roles import ROLE_USER
from models.base import Base


class Register(Base):
    __tablename__ = "register"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    face_encoding: Mapped[str] = mapped_column(Text, nullable=False)
    eye_encoding: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_USER, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
