"""Consultant accounts for the Peak web application (Phase 201).

Small account functions (create, authenticate, look up, list) plus signed session tokens. The
FastAPI adapter in ``peak.consultant_api`` is a thin transport over these; no business logic lives there.

Account writes are create-only (``INSERT``) and reads are ``SELECT`` only, so the runtime database
credential needs no new privilege. Every function takes an explicit ``session_factory`` so tests
can point it at temporary SQLite.
"""

from .service import (  # noqa: F401
    MIN_PASSWORD_LENGTH,
    ROLES,
    AccountError,
    admin_exists,
    authenticate,
    create_consultant,
    get_consultant,
    list_consultants,
    normalize_email,
)
from .session_token import (  # noqa: F401
    SECRET_KEY_ENV,
    SESSION_MAX_AGE_SECONDS,
    get_secret_key,
    issue_session_token,
    read_session_token,
)
