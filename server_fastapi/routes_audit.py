"""
SYJ OpenTrade Logic - Audit log routes (v0.8.0)
==================================================
GET /audit-log - view your organization's audit trail (ADMIN+ only --
this is sensitive operational history, not general member data).
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, AuditLog, User, UserRole
from server_fastapi.dependencies import require_role

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("")
def list_audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    q = db.query(AuditLog).filter(AuditLog.organization_id == current_user.organization_id)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()

    results = []
    for row in rows:
        results.append({
            "id": row.id,
            "user_email": row.user_email,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "details": json.loads(row.details_json) if row.details_json else None,
            "created_at": row.created_at,
        })

    return {"count": total, "limit": limit, "offset": offset, "results": results}
