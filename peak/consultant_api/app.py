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
import threading
import time
from typing import Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from peak import accounts, workspace
from peak.workspace import discovery

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


class BranchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    operator: Literal["equals", "not_equals"]
    value: str


class QuestionIn(BaseModel):
    """Question-pool fields only. ``branch: null`` removes a branch."""
    model_config = ConfigDict(extra="forbid")
    prompt: Optional[str] = None
    category: Optional[str] = None
    answer_type: Optional[Literal["short_text", "long_text", "yes_no", "single_choice"]] = None
    choices: Optional[List[str]] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None
    branch: Optional[BranchIn] = None


class NorthStarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    north_star: Optional[str] = None
    north_star_context: Optional[str] = None


class SessionIn(BaseModel):
    """Interview details only; the conducting consultant is the signed-in consultant."""
    model_config = ConfigDict(extra="forbid")
    interviewee_name: Optional[str] = None
    interviewee_title: Optional[str] = None
    notes: Optional[str] = None


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Optional[str] = None


class ObservationUpdateIn(BaseModel):
    """Observation fields only; the recording consultant is the signed-in consultant."""
    model_config = ConfigDict(extra="forbid")
    category: Optional[str] = None
    observation_text: Optional[str] = None
    low_hanging_fruit: Optional[bool] = None
    estimated_effort: Optional[Literal["low", "medium", "high"]] = None
    estimated_value: Optional[Literal["low", "medium", "high"]] = None


class ObservationCreateIn(ObservationUpdateIn):
    session_id: Optional[str] = None


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


class LoginThrottle:
    """Failed sign-in limiter (Phase 203): per email, in memory, per process.

    After ``max_failures`` failed attempts for one email within ``window_seconds``, further attempts
    for that email are refused (HTTP 429) until the window passes, even with the right password. A
    successful sign-in clears the count. It is keyed on the submitted email rather than the client
    address: behind the Next.js server every browser shares one upstream address, and a
    client-supplied forwarding header can be forged. State resets when the process restarts.
    """

    MAX_TRACKED = 10_000

    def __init__(self, max_failures: int = 5, window_seconds: int = 900, clock=time.monotonic):
        self.max_failures = max_failures
        self.window = window_seconds
        self.clock = clock
        self._failures: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str) -> List[float]:
        cutoff = self.clock() - self.window
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key)) >= self.max_failures

    def failure(self, key: str) -> None:
        with self._lock:
            if len(self._failures) >= self.MAX_TRACKED and key not in self._failures:
                self._failures.pop(next(iter(self._failures)))  # bounded memory: drop the oldest
            self._failures[key] = self._recent(key) + [self.clock()]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def create_app(
    session_factory=None, secret_key: Optional[str] = None, secure_cookie: Optional[bool] = None,
    login_throttle: Optional[LoginThrottle] = None,
) -> FastAPI:
    """Build the app. Arguments override environment configuration (used by tests)."""
    if session_factory is None:
        from peak.db.session import create_session_factory

        session_factory = create_session_factory()
    if secret_key is None:
        secret_key = accounts.get_secret_key()
    if secure_cookie is None:
        secure_cookie = os.environ.get(INSECURE_COOKIE_ENV) != "1"
    throttle = login_throttle or LoginThrottle()

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

    @app.get("/healthz")
    def healthz():
        """Liveness only (Phase 203): no database access, no configuration, no secrets."""
        return {"status": "ok"}

    @app.post("/auth/login")
    def login(body: LoginIn, response: Response):
        key = body.email.strip().lower()
        if throttle.blocked(key):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
        consultant = accounts.authenticate(session_factory, body.email, body.password)
        if consultant is None:
            throttle.failure(key)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
        throttle.reset(key)
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

    # --- Phase 204: discovery / interview workflow (any authenticated consultant) ---------------

    @app.get("/questions")
    def questions_list(_: dict = Depends(current_consultant)):
        return {"questions": discovery.list_questions(session_factory)}

    @app.post("/questions", status_code=status.HTTP_201_CREATED)
    def questions_create(body: QuestionIn, _: dict = Depends(current_consultant)):
        return {"question": _workspace_call(discovery.create_question, session_factory,
                                            body.model_dump(exclude_unset=True))}

    @app.get("/questions/{question_id}")
    def questions_get(question_id: str, _: dict = Depends(current_consultant)):
        return {"question": _workspace_call(discovery.get_question, session_factory, question_id)}

    @app.patch("/questions/{question_id}")
    def questions_update(question_id: str, body: QuestionIn, _: dict = Depends(current_consultant)):
        return {"question": _workspace_call(discovery.update_question, session_factory,
                                            question_id, body.model_dump(exclude_unset=True))}

    @app.get("/engagements/{engagement_id}/discovery")
    def discovery_get(engagement_id: str, _: dict = Depends(current_consultant)):
        return {"discovery": _workspace_call(discovery.get_discovery, session_factory,
                                             engagement_id)}

    @app.patch("/engagements/{engagement_id}/north-star")
    def north_star_set(engagement_id: str, body: NorthStarIn,
                       _: dict = Depends(current_consultant)):
        return {"discovery": _workspace_call(discovery.set_north_star, session_factory,
                                             engagement_id, body.model_dump(exclude_unset=True))}

    @app.post("/engagements/{engagement_id}/sessions", status_code=status.HTTP_201_CREATED)
    def sessions_start(engagement_id: str, body: SessionIn,
                       me: dict = Depends(current_consultant)):
        return {"session": _workspace_call(discovery.start_session, session_factory,
                                           engagement_id, body.model_dump(exclude_unset=True),
                                           me["id"])}

    @app.get("/sessions/{session_id}")
    def sessions_get(session_id: str, _: dict = Depends(current_consultant)):
        return {"session": _workspace_call(discovery.get_session, session_factory, session_id)}

    @app.patch("/sessions/{session_id}")
    def sessions_update(session_id: str, body: SessionIn, _: dict = Depends(current_consultant)):
        return {"session": _workspace_call(discovery.update_session, session_factory, session_id,
                                           body.model_dump(exclude_unset=True))}

    @app.post("/sessions/{session_id}/complete")
    def sessions_complete(session_id: str, _: dict = Depends(current_consultant)):
        return {"session": _workspace_call(discovery.complete_session, session_factory,
                                           session_id)}

    @app.put("/sessions/{session_id}/answers/{question_id}")
    def answers_save(session_id: str, question_id: str, body: AnswerIn,
                     _: dict = Depends(current_consultant)):
        return {"session": _workspace_call(discovery.save_answer, session_factory, session_id,
                                           question_id, body.answer)}

    @app.post("/engagements/{engagement_id}/observations", status_code=status.HTTP_201_CREATED)
    def observations_create(engagement_id: str, body: ObservationCreateIn,
                            me: dict = Depends(current_consultant)):
        return {"observation": _workspace_call(discovery.create_observation, session_factory,
                                               engagement_id, body.model_dump(exclude_unset=True),
                                               me["id"])}

    @app.get("/observations/{observation_id}")
    def observations_get(observation_id: str, _: dict = Depends(current_consultant)):
        return {"observation": _workspace_call(discovery.get_observation, session_factory,
                                               observation_id)}

    @app.patch("/observations/{observation_id}")
    def observations_update(observation_id: str, body: ObservationUpdateIn,
                            _: dict = Depends(current_consultant)):
        return {"observation": _workspace_call(discovery.update_observation, session_factory,
                                               observation_id, body.model_dump(exclude_unset=True))}

    return app
