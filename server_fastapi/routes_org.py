"""
SYJ OpenTrade Logic - Organization member management routes (v0.4.0)
=======================================================================
POST /organizations/members       - invite a new user into your org (ADMIN+)
GET  /organizations/members        - list your org's members (VIEWER+)
PUT  /organizations/members/{id}/role - change a member's role (ADMIN+)

All scoped to current_user.organization_id.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, User, UserRole
from server_fastapi.dependencies import require_role
from server_fastapi.security import hash_password
from server_fastapi.schemas import InviteUserRequest, UpdateUserRoleRequest, UserOut

router = APIRouter(prefix="/organizations/members", tags=["organizations"])


@router.get("", response_model=list[UserOut])
def list_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    return db.query(User).filter(User.organization_id == current_user.organization_id).all()


@router.post("", response_model=UserOut, status_code=201)
def invite_member(
    req: InviteUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    try:
        role = UserRole(req.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role '{req.role}'. Must be one of: viewer, member, admin, owner")

    existing = (
        db.query(User)
        .filter(User.organization_id == current_user.organization_id, User.email == req.email)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists in this organization")

    new_user = User(
        organization_id=current_user.organization_id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.put("/{user_id}/role", response_model=UserOut)
def update_member_role(
    user_id: int,
    req: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    try:
        new_role = UserRole(req.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role '{req.role}'")

    member = (
        db.query(User)
        .filter(User.id == user_id, User.organization_id == current_user.organization_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail=f"No member with id {user_id} in your organization")

    if member.id == current_user.id and new_role != UserRole.OWNER and current_user.role == UserRole.OWNER:
        raise HTTPException(status_code=400, detail="An owner cannot demote themselves; transfer ownership to another user first")

    member.role = new_role
    db.commit()
    db.refresh(member)
    return member
