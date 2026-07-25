"""
SYJ OpenTrade Logic - Auth security primitives (v0.4.0)
==========================================================
Password hashing via stdlib hashlib.pbkdf2_hmac (no bcrypt/passlib
dependency needed -- this sandbox has no network to install them, and
PBKDF2-HMAC-SHA256 with a strong iteration count is a legitimate, widely
used choice, e.g. it's what Django uses by default).

JWT access/refresh tokens via PyJWT.

SECRET KEY: reads from the SYJ_SECRET_KEY environment variable. Falls back
to a random key generated at process start ONLY for local dev convenience
-- this means tokens won't survive a server restart in that fallback case,
which is intentional (forces you to set a real secret for anything that
needs to persist across restarts).
"""

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import jwt  # PyJWT

PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16

ACCESS_TOKEN_TTL_SECONDS = 15 * 60          # 15 minutes
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
JWT_ALGORITHM = "HS256"

_SECRET_KEY = os.environ.get("SYJ_SECRET_KEY") or secrets.token_hex(32)


def hash_password(plain_password: str) -> str:
    """Returns 'pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>'."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)  # constant-time comparison


def create_access_token(user_id: int, org_id: int, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "org_id": org_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int, org_id: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "org_id": org_id,
        "type": "refresh",
        "iat": now,
        "exp": now + REFRESH_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=JWT_ALGORITHM)


class TokenError(Exception):
    pass


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"Invalid token: {e}")

    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token, got {payload.get('type')}")
    return payload
