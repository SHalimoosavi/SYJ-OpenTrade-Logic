"""
SYJ OpenTrade Logic - Database setup (SQLAlchemy 2.0 style)
==============================================================
Direct port of server/db.py's schema, using a real ORM instead of raw
sqlite3. Default is still SQLite (matches your Termux-first, SQLite-default
working style) -- swap DATABASE_URL for a postgresql:// DSN when you're
ready to move to Postgres; nothing else in this file needs to change.
"""

import os
from datetime import datetime

from sqlalchemy import create_engine, String, Float, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get("SYJ_DATABASE_URL", "sqlite:///./syj_opentrade.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class ClassificationRecord(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    final_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_classified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duty_rate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unresolved_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
