"""
SYJ OpenTrade Logic - Webhook signing and delivery (v0.8.0)
==============================================================
Every webhook payload is signed with HMAC-SHA256 over the raw request
body, using the webhook's own secret. The signature is sent in the
'X-SYJ-Signature' header as 'sha256=<hex digest>' -- the same pattern
GitHub, Stripe, and most webhook providers use, specifically so a
receiver can verify the payload wasn't tampered with or spoofed by
someone who doesn't know the secret.

Delivery is a best-effort HTTP POST with a short timeout. This is
synchronous (no task queue) to keep the stack simple, matching this
project's SQLite-first, minimal-infrastructure philosophy -- a slow or
dead webhook receiver will delay the request that triggered it by at
most a couple of seconds (bounded by the timeout), never hang forever.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

import requests

DELIVERY_TIMEOUT_SECONDS = 5


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Returns 'sha256=<hex>' -- verify with hmac.compare_digest, never == """
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(payload_bytes: bytes, secret: str, signature_header: str) -> bool:
    """What a webhook RECEIVER would call to verify an incoming payload
    really came from us and wasn't tampered with. Included here so this
    module is a complete reference implementation, not just a sender."""
    expected = sign_payload(payload_bytes, secret)
    return hmac.compare_digest(expected, signature_header)


def build_payload(event_type: str, data: dict) -> dict:
    return {
        "event": event_type,
        "timestamp": int(time.time()),
        "data": data,
    }


@dataclass
class DeliveryResult:
    success: bool
    status_code: Optional[int]
    error: Optional[str]
    payload_json: str


def deliver_webhook(url: str, secret: str, event_type: str, data: dict) -> DeliveryResult:
    """
    Sends a signed webhook POST. Never raises -- network failures, timeouts,
    and non-2xx responses are all captured in the returned DeliveryResult
    rather than propagating an exception into the caller's request handling,
    since a webhook receiver being down should never break the action that
    triggered the webhook (e.g. creating a product shouldn't fail just
    because someone's webhook endpoint is offline).
    """
    payload = build_payload(event_type, data)
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = sign_payload(payload_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "X-SYJ-Signature": signature,
        "X-SYJ-Event": event_type,
    }

    try:
        resp = requests.post(url, data=payload_bytes, headers=headers, timeout=DELIVERY_TIMEOUT_SECONDS)
        return DeliveryResult(
            success=200 <= resp.status_code < 300,
            status_code=resp.status_code,
            error=None if resp.ok else f"Non-2xx response: {resp.status_code}",
            payload_json=payload_bytes.decode("utf-8"),
        )
    except requests.exceptions.RequestException as e:
        return DeliveryResult(
            success=False,
            status_code=None,
            error=str(e),
            payload_json=payload_bytes.decode("utf-8"),
        )
