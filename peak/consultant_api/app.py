"""Thin FastAPI transport over ``peak.accounts`` (Phase 201) and ``peak.workspace`` (Phase 202).

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
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from peak import accounts, workspace

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


class KeyPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ClientIn(BaseModel):
    """Client profile fields only. Anything else — including every governance column — is a 422."""
    model_config = ConfigDict(extra="forbid")
    organization_label: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    key_personnel: Optional[List[KeyPerson]] = None


class EngagementUpdateIn(BaseModel):
    """Engagement workflow fields only; the client cannot be changed after creation."""
    model_config = ConfigDict(extra="forbid")
    engagement_label: Optional[str] = None
    objective: Optional[str] = None
    assigned_consultant_id: Optional[str] = None
    status: Optional[Literal["active", "on_hold", "closed"]] = None
    current_phase: Optional[str] = None


class EngagementCreateIn(EngagementUpdateIn):
    client_id: str


def _workspace_call(fn, *args):
    """Run a workspace function, mapping its refusals to 422 and a missing record to 404."""
    try:
        result = fn(*args)
    except workspace.WorkspaceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            {"code": exc.code, "message": str(exc)}) from None
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return result


def _body(model: BaseModel) -> dict:
    data = model.model_dump(exclude_unset=True)
    if data.get("key_personnel") is not None:
        data["key_personnel"] = [dict(p) for p in data["key_personnel"]]
    return data


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

    # --- Phase 202: client and engagement workspace (any authenticated consultant) -----------

    @app.get("/consultant-options")
    def consultant_options(_: dict = Depends(current_consultant)):
        return {"consultants": workspace.list_consultant_options(session_factory)}

    @app.get("/clients")
    def clients_list(q: Optional[str] = None, _: dict = Depends(current_consultant)):
        return {"clients": workspace.list_clients(session_factory, q)}

    @app.post("/clients", status_code=status.HTTP_201_CREATED)
    def clients_create(body: ClientIn, _: dict = Depends(current_consultant)):
        return {"client": _workspace_call(workspace.create_client, session_factory, _body(body))}

    @app.get("/clients/{client_id}")
    def clients_get(client_id: str, _: dict = Depends(current_consultant)):
        return {"client": _workspace_call(workspace.get_client, session_factory, client_id)}

    @app.patch("/clients/{client_id}")
    def clients_update(client_id: str, body: ClientIn, _: dict = Depends(current_consultant)):
        return {"client": _workspace_call(workspace.update_client, session_factory, client_id,
                                          _body(body))}

    @app.get("/engagements")
    def engagements_list(_: dict = Depends(current_consultant)):
        return {"engagements": workspace.list_engagements(session_factory)}

    @app.post("/engagements", status_code=status.HTTP_201_CREATED)
    def engagements_create(body: EngagementCreateIn, _: dict = Depends(current_consultant)):
        return {"engagement": _workspace_call(workspace.create_engagement, session_factory,
                                              _body(body))}

    @app.get("/engagements/{engagement_id}")
    def engagements_get(engagement_id: str, _: dict = Depends(current_consultant)):
        return {"engagement": _workspace_call(workspace.get_engagement, session_factory,
                                              engagement_id)}

    @app.patch("/engagements/{engagement_id}")
    def engagements_update(engagement_id: str, body: EngagementUpdateIn,
                           _: dict = Depends(current_consultant)):
        return {"engagement": _workspace_call(workspace.update_engagement, session_factory,
                                              engagement_id, _body(body))}

    return app
