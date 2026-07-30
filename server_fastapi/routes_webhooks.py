"""
SYJ OpenTrade Logic - Webhook management routes (v0.8.0)
===========================================================
POST   /webhooks              - register a new webhook (ADMIN+)
GET    /webhooks               - list your org's webhooks (ADMIN+)
DELETE /webhooks/{id}          - remove a webhook (ADMIN+)
POST   /webhooks/{id}/test     - fire a test event at a webhook (ADMIN+)
GET    /webhooks/{id}/deliveries - view delivery history (ADMIN+)

The webhook secret is returned ONLY at creation time (POST response) --
never again on subsequent GETs, same principle as an API key: if you lose
it, you register a new webhook rather than being able to retrieve the
old secret.
"""

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, Webhook, WebhookDelivery, User, UserRole
from server_fastapi.dependencies import require_role
from server_fastapi.webhooks import deliver_webhook
from server_fastapi.audit import log_action
from server_fastapi.schemas import (
    WebhookCreateRequest,
    WebhookOut,
    WebhookListOut,
    WebhookDeliveryOut,
    WebhookTestRequest,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _webhook_to_out(webhook: Webhook, include_secret: bool = False) -> dict:
    return {
        "id": webhook.id,
        "url": webhook.url,
        "event_types": json.loads(webhook.event_types),
        "is_active": webhook.is_active,
        "created_at": webhook.created_at,
        "secret": webhook.secret if include_secret else None,
    }


@router.post("", response_model=WebhookOut, status_code=201)
def create_webhook(
    req: WebhookCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    webhook_secret = secrets.token_hex(32)
    webhook = Webhook(
        organization_id=current_user.organization_id,
        url=req.url,
        secret=webhook_secret,
        event_types=json.dumps(req.event_types),
        is_active=True,
    )
    db.add(webhook)
    db.flush()

    log_action(
        db, current_user.organization_id, current_user,
        action="webhook.created", resource_type="webhook", resource_id=webhook.id,
        details={"url": req.url, "event_types": req.event_types},
    )
    db.commit()
    db.refresh(webhook)
    return _webhook_to_out(webhook, include_secret=True)


@router.get("", response_model=WebhookListOut)
def list_webhooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    webhooks = db.query(Webhook).filter(Webhook.organization_id == current_user.organization_id).all()
    return {"results": [_webhook_to_out(w) for w in webhooks]}


@router.delete("/{webhook_id}")
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    webhook = (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.organization_id == current_user.organization_id)
        .first()
    )
    if webhook is None:
        raise HTTPException(status_code=404, detail=f"No webhook with id {webhook_id}")

    log_action(
        db, current_user.organization_id, current_user,
        action="webhook.deleted", resource_type="webhook", resource_id=webhook_id,
        details={"url": webhook.url},
    )
    db.delete(webhook)
    db.commit()
    return {"deleted": True, "id": webhook_id}


@router.post("/{webhook_id}/test")
def test_webhook(
    webhook_id: int,
    req: WebhookTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    webhook = (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.organization_id == current_user.organization_id)
        .first()
    )
    if webhook is None:
        raise HTTPException(status_code=404, detail=f"No webhook with id {webhook_id}")

    result = deliver_webhook(
        url=webhook.url,
        secret=webhook.secret,
        event_type=req.event_type,
        data={"message": "This is a test event from SYJ OpenTrade Logic."},
    )

    db.add(
        WebhookDelivery(
            webhook_id=webhook.id,
            event_type=req.event_type,
            payload_json=result.payload_json,
            response_status=result.status_code,
            error=result.error,
        )
    )
    db.commit()

    return {
        "success": result.success,
        "status_code": result.status_code,
        "error": result.error,
    }


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryOut])
def list_deliveries(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    webhook = (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.organization_id == current_user.organization_id)
        .first()
    )
    if webhook is None:
        raise HTTPException(status_code=404, detail=f"No webhook with id {webhook_id}")

    deliveries = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(50)
        .all()
    )
    return deliveries
