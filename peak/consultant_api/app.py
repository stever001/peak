"""Thin FastAPI transport over ``peak.accounts`` (Phase 201).

Validates input, calls account functions, returns minimal JSON, and enforces the Admin role on
consultant administration. No business logic lives here.

Run locally (see docs/PHASE201_CONSULTANT_WEB_SHELL_AUTH.md)::

    # with PEAK_RUNTIME_DATABASE_URL and PEAK_WEB_SECRET_KEY set in the environment
    uvicorn --factory peak.consultant_api.app:create_app --port 8000

Configuration (environment, read once in :func:`create_app`):

- ``PEAK_RUNTIME_DATABASE_URL`` — runtime DB (via ``peak.db.session``; no fallback);
- ``PEAK_WEB_SECRET_KEY`` — session signing secret (never printed);
- ``PEAK_WEB_INSECURE_COOKIE=1`` — local HTTP development only: drop the ``Secure`` cookie flag.
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from peak import accounts

SESSION_COOKIE = "peak_session"
INSECURE_COOKIE_ENV = "PEAK_WEB_INSECURE_COOKIE"


class LoginIn(BaseModel):
    email: str = Field(max_length=accounts.service.MAX_EMAIL_LENGTH)
    password: str = Field(max_length=accounts.service.MAX_PASSWORD_LENGTH)


class ConsultantIn(BaseModel):
    name: str = Field(max_length=accounts.service.MAX_NAME_LENGTH)
    email: str = Field(max_length=accounts.service.MAX_EMAIL_LENGTH)
    role: Literal["admin", "consultant"]
    password: str = Field(max_length=accounts.service.MAX_PASSWORD_LENGTH)


def create_app(
    session_factory=None, secret_key: Optional[str] = None, secure_cookie: Optional[bool] = None
) -> FastAPI:
    """Build the app. Arguments override environment configuration (used by tests)."""
    if session_factory is None:
        from peak.db.session import create_session_factory

        session_factory = create_session_factory()
    if secret_key is None:
        secret_key = accounts.get_secret_key()
    if secure_cookie is None:
        secure_cookie = os.environ.get(INSECURE_COOKIE_ENV) != "1"

    app = FastAPI(title="Peak web API", docs_url=None, redoc_url=None, openapi_url=None)

    def current_consultant(request: Request) -> dict:
        cid = accounts.read_session_token(request.cookies.get(SESSION_COOKIE, ""), secret_key)
        consultant = accounts.get_consultant(session_factory, cid) if cid else None
        if consultant is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
        return consultant

    def require_admin(consultant: dict = Depends(current_consultant)) -> dict:
        if consultant["role"] != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_required")
        return consultant

    @app.post("/auth/login")
    def login(body: LoginIn, response: Response):
        consultant = accounts.authenticate(session_factory, body.email, body.password)
        if consultant is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
        token = accounts.issue_session_token(consultant["id"], secret_key)
        response.set_cookie(
            SESSION_COOKIE, token, max_age=accounts.SESSION_MAX_AGE_SECONDS,
            httponly=True, samesite="lax", secure=secure_cookie, path="/",
        )
        # The token is also returned so the Next.js server can set it as its own HttpOnly cookie;
        # it never reaches browser JavaScript.
        return {"consultant": consultant, "token": token,
                "max_age": accounts.SESSION_MAX_AGE_SECONDS}

    @app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(response: Response):
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax",
                               secure=secure_cookie)

    @app.get("/auth/me")
    def me(consultant: dict = Depends(current_consultant)):
        return {"consultant": consultant}

    @app.get("/consultants")
    def consultants_list(_: dict = Depends(require_admin)):
        return {"consultants": accounts.list_consultants(session_factory)}

    @app.post("/consultants", status_code=status.HTTP_201_CREATED)
    def consultants_create(body: ConsultantIn, _: dict = Depends(require_admin)):
        try:
            consultant = accounts.create_consultant(
                session_factory, name=body.name, email=body.email, role=body.role,
                password=body.password,
            )
        except accounts.AccountError as exc:
            code = (status.HTTP_409_CONFLICT if exc.code == "email_taken"
                    else status.HTTP_422_UNPROCESSABLE_ENTITY)
            raise HTTPException(code, {"code": exc.code, "message": str(exc)}) from None
        return {"consultant": consultant}

    return app
