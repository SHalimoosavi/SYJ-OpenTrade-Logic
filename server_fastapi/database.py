"""
SYJ OpenTrade Logic - Database setup (SQLAlchemy 2.0 style)
==============================================================
Direct port of server/db.py's schema, using a real ORM instead of raw
sqlite3. Default is still SQLite (matches your Termux-first, SQLite-default
working style) -- swap DATABASE_URL for a postgresql:// DSN when you're
ready to move to Postgres; nothing else in this file needs to change.
"""

import enum
import os
from datetime import datetime

from sqlalchemy import (
    create_engine, String, Float, Integer, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

DATABASE_URL = os.environ.get("SYJ_DATABASE_URL", "sqlite:///./syj_opentrade.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    """
    RBAC roles, ordered from least to most privileged. Kept as a simple
    flat enum per organization (not a full permissions matrix) -- matches
    the original spec's "Organizations / Users / Teams / Roles /
    Permissions" module at a scope that's actually buildable and testable
    in one release, rather than a half-built generic permissions engine.
    """
    VIEWER = "viewer"     # read-only: view products, view classifications
    MEMBER = "member"     # + create/edit products, run classifications
    ADMIN = "admin"       # + invite/manage users, delete products
    OWNER = "owner"       # + billing/org settings, cannot be removed by others


ROLE_HIERARCHY = {
    UserRole.VIEWER: 0,
    UserRole.MEMBER: 1,
    UserRole.ADMIN: 2,
    UserRole.OWNER: 3,
}


def role_at_least(user_role: str, required_role: UserRole) -> bool:
    """True if user_role has >= privilege of required_role."""
    try:
        current = ROLE_HIERARCHY[UserRole(user_role)]
    except ValueError:
        return False
    return current >= ROLE_HIERARCHY[required_role]


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_user_org_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.MEMBER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="users")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("organization_id", "sku", name="uq_product_org_sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hts_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duty_rate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="products")


class ClassificationRecord(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    final_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_classified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duty_rate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unresolved_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """
    Append-only audit trail. Never updated or deleted once written -- that's
    the whole point of an audit log. Scoped to organization_id so each org
    only ever sees its own history.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # denormalized snapshot at time of action
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "product.created", "member.role_changed"
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "product", "user", "classification"
    resource_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # arbitrary JSON blob of what changed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(100), nullable=False)  # for HMAC-SHA256 payload signing
    event_types: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array, e.g. ["product.created", "classification.created"]
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebhookDelivery(Base):
    """Log of every delivery attempt -- lets an org debug why a webhook
    didn't fire or what payload was actually sent, without needing external
    tooling."""
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
