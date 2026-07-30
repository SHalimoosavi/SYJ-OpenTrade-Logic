"""
SYJ OpenTrade Logic - Audit logging helper (v0.8.0)
======================================================
A thin, reusable helper so every mutating route can log consistently
without repeating the same boilerplate. Append-only by design -- there
is deliberately no update/delete function for audit log entries.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from server_fastapi.database import AuditLog, User


def log_action(
    db: Session,
    organization_id: int,
    user: Optional[User],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> AuditLog:
    entry = AuditLog(
        organization_id=organization_id,
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details_json=json.dumps(details) if details is not None else None,
    )
    db.add(entry)
    # Deliberately NOT calling db.commit() here -- the caller's own
    # transaction commit (after its main write) covers this too, so an
    # audit log entry and the action it describes are always committed
    # together atomically, never one without the other.
    return entry
