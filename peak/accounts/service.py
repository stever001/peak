"""Consultant account functions: create, authenticate, look up, list.

Passwords are hashed with Argon2id via ``argon2-cffi`` (library defaults); nothing here implements
cryptography. Plaintext passwords and hashes are never returned, logged, or included in an error.
Functions return plain dicts carrying only ``id``, ``name``, ``email`` and ``role``.
"""

from __future__ import annotations

import re
import secrets
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ROLES = ("admin", "consultant")
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
MAX_NAME_LENGTH = 255
MAX_EMAIL_LENGTH = 254

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_hasher = PasswordHasher()
# Verified against when an email is unknown, so a miss costs the same as a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


class AccountError(ValueError):
    """An account request was refused. ``code`` is a short machine-readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def normalize_email(email: str) -> str:
    """Trim and lower-case an email, or raise ``AccountError('invalid_email')``."""
    value = (email or "").strip().lower()
    if len(value) > MAX_EMAIL_LENGTH or not _EMAIL_RE.match(value):
        raise AccountError("invalid_email", "Enter a valid email address.")
    return value


def _validate_name(name: str) -> str:
    value = (name or "").strip()
    if not value or len(value) > MAX_NAME_LENGTH:
        raise AccountError("invalid_name", "Enter a name (up to 255 characters).")
    return value


def _validate_password(password: str) -> str:
    if not isinstance(password, str) or not (
        MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
    ):
        raise AccountError(
            "invalid_password",
            f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters.",
        )
    return password


def _public(row) -> dict:
    return {"id": row.id, "name": row.name, "email": row.email, "role": row.role}


def create_consultant(session_factory, *, name: str, email: str, role: str, password: str) -> dict:
    """Create one consultant account (a single ``INSERT``) and return its public fields.

    Raises ``AccountError`` for invalid input or an email that is already registered.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from peak.db.models import Consultant

    name = _validate_name(name)
    email = normalize_email(email)
    if role not in ROLES:
        raise AccountError("invalid_role", "Role must be admin or consultant.")
    password_hash = _hasher.hash(_validate_password(password))

    with session_factory() as session:
        if session.scalar(select(Consultant.id).where(Consultant.email == email)) is not None:
            raise AccountError("email_taken", "A consultant with that email already exists.")
        row = Consultant(
            id=f"cons_{secrets.token_hex(12)}",
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise AccountError("email_taken", "A consultant with that email already exists.") from None
        return _public(row)


def authenticate(session_factory, email: str, password: str) -> Optional[dict]:
    """Return the consultant for a correct email/password pair, else ``None``."""
    from sqlalchemy import select

    from peak.db.models import Consultant

    try:
        email = normalize_email(email)
    except AccountError:
        return None
    if not isinstance(password, str) or len(password) > MAX_PASSWORD_LENGTH:
        return None

    with session_factory() as session:
        row = session.scalar(select(Consultant).where(Consultant.email == email))
        try:
            _hasher.verify(row.password_hash if row is not None else _DUMMY_HASH, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None
        return _public(row) if row is not None else None


def get_consultant(session_factory, consultant_id: str) -> Optional[dict]:
    from peak.db.models import Consultant

    with session_factory() as session:
        row = session.get(Consultant, consultant_id)
        return _public(row) if row is not None else None


def list_consultants(session_factory) -> list:
    from sqlalchemy import select

    from peak.db.models import Consultant

    with session_factory() as session:
        rows = session.scalars(select(Consultant).order_by(Consultant.name, Consultant.email))
        return [_public(r) for r in rows]


def admin_exists(session_factory) -> bool:
    from sqlalchemy import select

    from peak.db.models import Consultant

    with session_factory() as session:
        return session.scalar(
            select(Consultant.id).where(Consultant.role == "admin").limit(1)
        ) is not None
