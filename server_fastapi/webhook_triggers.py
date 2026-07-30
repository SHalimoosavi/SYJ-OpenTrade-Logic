"""
SYJ OpenTrade Logic - Webhook triggering (v0.8.0)
====================================================
Looks up active webhooks subscribed to a given event type within an
organization, delivers to each (using the already-tested signing/delivery
primitives in webhooks.py), and logs every attempt as a WebhookDelivery
row so an org can see exactly what was sent and how the receiver responded
without needing external tooling.

Kept as a separate module from webhooks.py so the pure signing/delivery
logic (fully unit-tested against a real local HTTP server, see
test_webhooks.py) stays untangled from the database-integration layer.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from server_fastapi.database import Webhook, WebhookDelivery
from server_fastapi.webhooks import deliver_webhook


def trigger_webhooks(db: Session, organization_id: int, event_type: str, data: dict) -> None:
    webhooks = (
        db.query(Webhook)
        .filter(Webhook.organization_id == organization_id, Webhook.is_active.is_(True))
        .all()
    )

    for webhook in webhooks:
        subscribed_events = json.loads(webhook.event_types)
        if event_type not in subscribed_events:
            continue

        result = deliver_webhook(url=webhook.url, secret=webhook.secret, event_type=event_type, data=data)

        db.add(
            WebhookDelivery(
                webhook_id=webhook.id,
                event_type=event_type,
                payload_json=result.payload_json,
                response_status=result.status_code,
                error=result.error,
            )
        )
    # Same pattern as audit.log_action: no commit here, caller's own
    # transaction covers it.
