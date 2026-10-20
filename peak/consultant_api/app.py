"""Thin FastAPI transport over ``peak.accounts`` (Phase 201) and ``peak.workspace`` (Phase 202).

Validates input, calls account functions, returns minimal JSON, and enforces the Admin role on
consultant administration. No business logic lives here.

The Phase 206 assessment route is **read-only and derived**: it composes the existing one-call
assessment workflow over a caller-owned connection and returns the result. There is no assessment
writer, no assessment table, and no write endpoint — an assessment is recomputed from persisted
records on every request, so it can never drift from them. The Phase 208 final-report route is the
same: it composes the same assessment into report sections, and nothing is stored. The Phase 209
DOCX route renders that same composed report as a download; it adds no write path either.

Phase 213 adds the internal release-package routes: fixing the composed report as an immutable
version (Phase 212) with its web and DOCX renditions rendered once and stored as a release package,
serving those stored renditions, and recording the Lead approval, Final Approver designation, final
approval and release of one package (``peak.workspace.approvals``). Each write is an explicit POST
that appends records; the report and DOCX routes above stay read-only and never create a version.

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
from peak.workspace import approvals, discovery

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


class ClientCreateIn(ClientIn):
    """Phase 215: ``internal_test`` creates an internal test client (any consultant)."""
    internal_test: Optional[bool] = None


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
    #: Phase 215: any consultant; the engagement must belong to an internal test client and its
    #: classification is server-forced. ``internal_test_confirmed`` must be true with it: the
    #: affirmative confirmation, checked here as well as in the form.
    internal_test: Optional[bool] = None
    internal_test_confirmed: Optional[bool] = None


class InternalTestDeleteIn(BaseModel):
    """Phase 215: the Admin repeats the engagement's name to confirm the deletion."""
    model_config = ConfigDict(extra="forbid")
    confirm_engagement_label: str = Field(max_length=255)


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
    # Phase 216: supplemental-question provenance. ``engagement_id`` only on create.
    engagement_id: Optional[str] = None
    rationale: Optional[str] = None
    domain: Optional[str] = None
    finding_classes: Optional[List[str]] = None


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
    # Phase 216: the prompting question and the observation's basis; null clears either.
    question_id: Optional[str] = None
    basis: Optional[Literal["testimony", "observed", "document", "measured", "inferred"]] = None


class ObservationCreateIn(ObservationUpdateIn):
    session_id: Optional[str] = None


class DecisionIn(BaseModel):
    """An approval decision on the release package whose package hash the approver was shown."""
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    package_hash: str = Field(max_length=64)
    #: The client-facing rendition the approver reviewed; the decision is on the whole package.
    reviewed_rendition: Literal["web", "docx"]
    note: Optional[str] = Field(default=None, max_length=approvals.MAX_NOTE_LENGTH)


class DesignationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consultant_id: str = Field(max_length=64)


class ReleaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_hash: str = Field(max_length=64)


def _workspace_call(fn, *args):
    """Run a workspace function, mapping its refusals to 422 and a missing record to 404."""
    try:
        result = fn(*args)
    except workspace.WorkspaceError as exc:
        code = (status.HTTP_403_FORBIDDEN if exc.code == "admin_required"
                else status.HTTP_422_UNPROCESSABLE_ENTITY)
        raise HTTPException(code, {"code": exc.code, "message": str(exc)}) from None
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
        from urllib.parse import urlsplit

        from peak.db.session import create_session_factory, get_runtime_database_url

        # TEMPORARY (Phase 216 runtime-credential diagnosis): username and schema only — never the
        # URL, password, host, port or query. Remove once the Render runtime identity is confirmed.
        _parts = urlsplit(get_runtime_database_url())
        try:
            _user = _parts.username or ""
        except ValueError:
            _user = "<unparseable>"
        print(f"runtime_db_identity username={_user} "
              f"database={_parts.path.lstrip('/').split('/', 1)[0]}", flush=True)
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
    def clients_list(q: Optional[str] = None, internal_test: Optional[bool] = None,
                     _: dict = Depends(current_consultant)):
        return {"clients": workspace.list_clients(session_factory, q, internal_test)}

    @app.post("/clients", status_code=status.HTTP_201_CREATED)
    def clients_create(body: ClientCreateIn, _: dict = Depends(current_consultant)):
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
    def engagements_create(body: EngagementCreateIn, me: dict = Depends(current_consultant)):
        return {"engagement": _workspace_call(workspace.create_engagement, session_factory,
                                              _body(body), me["role"], me["id"])}

    @app.get("/engagements/{engagement_id}")
    def engagements_get(engagement_id: str, _: dict = Depends(current_consultant)):
        return {"engagement": _workspace_call(workspace.get_engagement, session_factory,
                                              engagement_id)}

    @app.patch("/engagements/{engagement_id}")
    def engagements_update(engagement_id: str, body: EngagementUpdateIn,
                           me: dict = Depends(current_consultant)):
        """Any consultant may edit; only an Admin may change the assigned consultant (Phase 213)."""
        return {"engagement": _workspace_call(workspace.update_engagement, session_factory,
                                              engagement_id, _body(body), me["role"])}

    @app.post("/engagements/{engagement_id}/internal-test-deletion")
    def engagements_delete_internal_test(engagement_id: str, body: InternalTestDeleteIn,
                                         me: dict = Depends(require_admin)):
        """Phase 215: an Admin's logical deletion of an internal_test engagement. Nothing is
        physically deleted; real_client engagements are refused."""
        return {"engagement": _workspace_call(
            workspace.delete_internal_test_engagement, session_factory, engagement_id,
            body.confirm_engagement_label, me["id"], me["role"])}

    # --- Phase 204: discovery / interview workflow (any authenticated consultant) ---------------

    @app.get("/questions")
    def questions_list(engagement_id: Optional[str] = None,
                       _: dict = Depends(current_consultant)):
        return {"questions": discovery.list_questions(session_factory, engagement_id)}

    @app.post("/questions", status_code=status.HTTP_201_CREATED)
    def questions_create(body: QuestionIn, me: dict = Depends(current_consultant)):
        # Never canonical: the API never sets seed_key. A global question needs an Admin; a
        # Consultant adds supplemental questions only within an engagement (Phase 216).
        return {"question": _workspace_call(discovery.create_question, session_factory,
                                            body.model_dump(exclude_unset=True), None, me["id"],
                                            me["role"])}

    @app.get("/questions/{question_id}")
    def questions_get(question_id: str, _: dict = Depends(current_consultant)):
        return {"question": _workspace_call(discovery.get_question, session_factory, question_id)}

    @app.patch("/questions/{question_id}")
    def questions_update(question_id: str, body: QuestionIn,
                         me: dict = Depends(current_consultant)):
        # A canonical (seeded) question needs an Admin; the service enforces it (Phase 216).
        return {"question": _workspace_call(discovery.update_question, session_factory,
                                            question_id, body.model_dump(exclude_unset=True),
                                            me["role"])}

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

    # --- Phase 206: internal assessment (read-only, derived; any authenticated consultant) ------

    @app.get("/engagements/{engagement_id}/assessment")
    def engagement_assessment(engagement_id: str, _: dict = Depends(current_consultant)):
        """The engagement's internal assessment: evidence-backed material plus discovery context.

        Derived on every request from persisted records. Nothing is written, cached, or persisted,
        and there is deliberately no companion write endpoint: the assessment is a view of stored
        state, so the only way to change it is to change that state through the existing paths.

        The engagement is read through the Phase 57 visibility primitive inside the workflow. A
        missing engagement and one that is not visible to this route both return 404, so the route
        never reports the existence of an engagement it may not show.
        """
        import dataclasses

        from peak.db.engagement_packet_reader import EngagementNotVisible
        from peak.workflows.consultant_assessment_workflow import (
            build_consultant_internal_assessment,
        )

        engagement = _workspace_call(workspace.get_engagement, session_factory, engagement_id)
        with session_factory() as session:
            try:
                result = build_consultant_internal_assessment(
                    session.connection(), engagement_id,
                    **workspace.service.assessment_read_options(session_factory, engagement_id))
            except (LookupError, EngagementNotVisible):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found") from None
        return {
            "engagement": engagement,
            "assessment": dataclasses.asdict(result.assessment),
            "markdown": result.markdown,
        }

    # --- Phase 208: final report foundation (read-only, derived; any authenticated consultant) --

    def _final_report(engagement_id: str):
        """(engagement, FinalReport): same read path and visibility rules as the assessment
        route above, then the Phase 208 pure composer. Shared by the JSON and DOCX routes."""
        from peak.db.engagement_packet_reader import EngagementNotVisible
        from peak.reports.final_report import compose_final_report
        from peak.workflows.consultant_assessment_workflow import (
            build_consultant_internal_assessment,
        )

        engagement = _workspace_call(workspace.get_engagement, session_factory, engagement_id)
        with session_factory() as session:
            try:
                result = build_consultant_internal_assessment(
                    session.connection(), engagement_id,
                    **workspace.service.assessment_read_options(session_factory, engagement_id))
            except (LookupError, EngagementNotVisible):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found") from None
        return engagement, compose_final_report(result.assessment, engagement)

    @app.get("/engagements/{engagement_id}/final-report")
    def engagement_final_report(engagement_id: str, _: dict = Depends(current_consultant)):
        """The engagement's internal Final Report foundation, composed from its assessment.

        Nothing is written, cached, or stored, and there is no companion write endpoint.
        """
        import dataclasses

        from peak.reports.final_report import render_final_report_markdown

        engagement, report = _final_report(engagement_id)
        return {
            "engagement": engagement,
            "report": dataclasses.asdict(report),
            "markdown": render_final_report_markdown(report),
        }

    # --- Phase 209: final report DOCX export (read-only, derived; any authenticated consultant) -

    @app.get("/engagements/{engagement_id}/final-report.docx")
    def engagement_final_report_docx(engagement_id: str, _: dict = Depends(current_consultant)):
        """The same composed FinalReport, rendered as an editable DOCX attachment.

        Rendered on every request from the report the JSON route composes; nothing is stored.
        """
        from peak.reports.final_report_docx import (
            DOCX_MEDIA_TYPE, final_report_docx_filename, render_final_report_docx,
        )

        _, report = _final_report(engagement_id)
        return Response(
            content=render_final_report_docx(report),
            media_type=DOCX_MEDIA_TYPE,
            headers={
                "Content-Disposition":
                    f'attachment; filename="{final_report_docx_filename(report)}"',
                "Cache-Control": "no-store",
            },
        )

    # --- Phase 213: release packages, two-stage approval and release (internal) ----------------

    @app.get("/engagements/{engagement_id}/final-report/packages")
    def final_report_packages(engagement_id: str, _: dict = Depends(current_consultant)):
        """Release packages and their approval chains, and whether the live draft matches."""
        _, report = _final_report(engagement_id)
        return {"review": approvals.get_final_report_review(session_factory, engagement_id,
                                                            report)}

    @app.post("/engagements/{engagement_id}/final-report/packages",
              status_code=status.HTTP_201_CREATED)
    def final_report_package_create(engagement_id: str, me: dict = Depends(current_consultant)):
        """Fix the report as composed now as a version and prepare its release package (explicit,
        never on read). Its web and DOCX renditions are rendered once and stored."""
        _, report = _final_report(engagement_id)
        return {"package": _workspace_call(approvals.prepare_final_report_package,
                                           session_factory, engagement_id, report, me["id"])}

    @app.get("/engagements/{engagement_id}/final-report/released")
    def final_report_released(engagement_id: str, _: dict = Depends(current_consultant)):
        """The released package current for client delivery (AL30); 404 if none is released."""
        _workspace_call(workspace.get_engagement, session_factory, engagement_id)
        return {"package": _workspace_call(approvals.get_released_package, session_factory,
                                           engagement_id)}

    @app.get("/release-packages/{package_id}")
    def release_package_get(package_id: str, _: dict = Depends(current_consultant)):
        return {"package": _workspace_call(approvals.get_package, session_factory, package_id)}

    def _rendition(package_id: str, kind: str, disposition: str) -> Response:
        """A rendition's stored bytes, exactly as approved. Never re-rendered."""
        r = _workspace_call(approvals.get_rendition, session_factory, package_id, kind)
        headers = {"Cache-Control": "no-store", "X-Peak-Rendition-Hash": r["rendition_hash"]}
        if disposition == "attachment":
            headers["Content-Disposition"] = f'attachment; filename="{r["file_name"]}"'
        else:
            # Static document: no script, no external fetch, framed only by this application.
            headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; " \
                                                 "frame-ancestors 'self'"
        return Response(content=r["bytes"], media_type=r["media_type"], headers=headers)

    @app.get("/release-packages/{package_id}/web")
    def release_package_web(package_id: str, _: dict = Depends(current_consultant)):
        return _rendition(package_id, approvals.WEB, "inline")

    @app.get("/release-packages/{package_id}/docx")
    def release_package_docx(package_id: str, _: dict = Depends(current_consultant)):
        return _rendition(package_id, approvals.DOCX, "attachment")

    @app.post("/release-packages/{package_id}/lead-approval")
    def release_package_lead(package_id: str, body: DecisionIn,
                             me: dict = Depends(current_consultant)):
        return {"package": _workspace_call(approvals.record_lead_decision, session_factory,
                                           package_id, body.decision, body.package_hash,
                                           body.reviewed_rendition, body.note, me["id"])}

    @app.post("/release-packages/{package_id}/final-approver")
    def release_package_designate(package_id: str, body: DesignationIn,
                                  me: dict = Depends(current_consultant)):
        return {"package": _workspace_call(approvals.designate_final_approver, session_factory,
                                           package_id, body.consultant_id, me["id"])}

    @app.post("/release-packages/{package_id}/final-approval")
    def release_package_final(package_id: str, body: DecisionIn,
                              me: dict = Depends(current_consultant)):
        return {"package": _workspace_call(approvals.record_final_decision, session_factory,
                                           package_id, body.decision, body.package_hash,
                                           body.reviewed_rendition, body.note, me["id"])}

    @app.post("/release-packages/{package_id}/release")
    def release_package_release(package_id: str, body: ReleaseIn,
                                me: dict = Depends(current_consultant)):
        return {"package": _workspace_call(approvals.release_package, session_factory,
                                           package_id, body.package_hash, me["id"])}

    return app
