"""
SYJ OpenTrade Logic - Auth/RBAC FastAPI dependencies (v0.4.0)
================================================================
get_current_user(): decodes the Bearer JWT, loads the User row, checks
it's active. require_role(min_role): a dependency FACTORY that returns a
dependency enforcing the caller's role is >= min_role within their own
organization. Every catalog/org endpoint is scoped to request.user's
organization_id -- there is no cross-tenant data access path.
"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, User, UserRole, role_at_least
from server_fastapi.security import decode_token, TokenError


def get_current_user(
    authorization: str = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization[len("Bearer "):]
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def require_role(min_role: UserRole):
    """Dependency factory: require_role(UserRole.ADMIN) -> a dependency that
    401s if not authenticated, 403s if authenticated but under-privileged."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if not role_at_least(current_user.role, min_role):
            raise HTTPException(
                status_code=403,
                detail=f"Requires role '{min_role.value}' or higher; you have '{current_user.role}'",
            )
        return current_user

    return _dependency
