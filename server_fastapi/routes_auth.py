"""
SYJ OpenTrade Logic - Auth routes (v0.4.0)
=============================================
POST /auth/register  - creates a new Organization + its first User (owner)
POST /auth/login      - returns an access + refresh JWT pair
POST /auth/refresh     - exchanges a valid refresh token for a new access token
GET  /auth/me          - returns the caller's own user + org info
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, Organization, User, UserRole
from server_fastapi.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenError,
)
from server_fastapi.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenPairOut, UserOut
from server_fastapi.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "org"


@router.post("/register", response_model=TokenPairOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    base_slug = _slugify(req.organization_name)
    slug = base_slug
    suffix = 1
    while db.query(Organization).filter(Organization.slug == slug).first() is not None:
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    org = Organization(name=req.organization_name, slug=slug)
    db.add(org)
    db.flush()  # get org.id without committing yet

    # Note: no duplicate-email check needed here -- org.id above is always a
    # BRAND NEW organization (registering never joins an existing org, even
    # if organization_name matches one; that would let anyone "join" a
    # company's org just by knowing its name, which is a real security hole).
    # A freshly created org can never already contain a user with this email.
    # Duplicate-email prevention for adding MORE users to an EXISTING org is
    # correctly enforced by the ADMIN-gated /organizations/members endpoint
    # instead (see routes_org.py::invite_member).

    user = User(
        organization_id=org.id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=UserRole.OWNER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_access_token(user.id, org.id, user.role.value if hasattr(user.role, "value") else user.role)
    refresh = create_refresh_token(user.id, org.id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/login", response_model=TokenPairOut)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if user is None or not verify_password(req.password, user.password_hash):
        # Same error for "no such user" and "wrong password" -- don't leak
        # which one it was, that's a real account-enumeration protection.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    role_value = user.role.value if hasattr(user.role, "value") else user.role
    access = create_access_token(user.id, user.organization_id, role_value)
    refresh = create_refresh_token(user.id, user.organization_id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenPairOut)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token, expected_type="refresh")
    except TokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    role_value = user.role.value if hasattr(user.role, "value") else user.role
    access = create_access_token(user.id, user.organization_id, role_value)
    new_refresh = create_refresh_token(user.id, user.organization_id)
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
