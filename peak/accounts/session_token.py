"""Signed, time-limited session tokens for the web application (``itsdangerous``).

The token carries only a consultant id, signed with ``PEAK_WEB_SECRET_KEY`` and valid for eight
hours. It is stateless: logout clears the cookie, and a copied token stays valid until it expires.
Role and existence are re-read from the database on every request, so the token never grants a role
by itself. The secret is read from the environment only and is never printed.
"""

from __future__ import annotations

import os
from typing import Optional

from itsdangerous import BadSignature, URLSafeTimedSerializer

SECRET_KEY_ENV = "PEAK_WEB_SECRET_KEY"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
MIN_SECRET_LENGTH = 32
_SALT = "peak-web-session"


def get_secret_key() -> str:
    """Return the signing secret from the environment, or raise (naming the variable only)."""
    secret = os.environ.get(SECRET_KEY_ENV, "")
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"{SECRET_KEY_ENV} must be set to at least {MIN_SECRET_LENGTH} characters "
            f"(e.g. python3 -c 'import secrets; print(secrets.token_urlsafe(48))')."
        )
    return secret


def issue_session_token(consultant_id: str, secret_key: str) -> str:
    return URLSafeTimedSerializer(secret_key, salt=_SALT).dumps({"cid": consultant_id})


def read_session_token(
    token: str, secret_key: str, max_age: int = SESSION_MAX_AGE_SECONDS
) -> Optional[str]:
    """Return the consultant id in a valid, unexpired token, else ``None``."""
    if not token:
        return None
    try:
        data = URLSafeTimedSerializer(secret_key, salt=_SALT).loads(token, max_age=max_age)
    except BadSignature:  # includes SignatureExpired
        return None
    cid = data.get("cid") if isinstance(data, dict) else None
    return cid if isinstance(cid, str) else None
