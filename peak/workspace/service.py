"""Client and engagement workspace functions (Phase 202).

Every write names its (table, action) pair and the exact columns it sets, and is refused unless
``is_allowed_workspace_write`` accepts that combination. A caller can never write a governance,
classification, review/audit or publication column. Engagement creation then applies the fixed
``WORKSPACE_ENGAGEMENT_CREATION_STAMP`` (owner ``peak_consultants``, scope
``engagement_authorized``) so downstream controlled writers can match the engagement. Those two
values come only from that constant; the other governance columns keep the model defaults. There
is no delete.

Updates are two explicit functions, one per table, each passing its own column dict to a single
``UPDATE ... WHERE id = ?``. (The model's ``updated_at`` ``onupdate`` still fires; that is the
audit mechanism, not a value this service chooses.)

Inputs are plain dicts already shaped by the API; this module validates values and returns plain
dicts. Consultant assignment is workflow metadata, never authorization.

**Internal test engagements (Phase 215).** Any consultant (Admin or Consultant) may create an
internal-test client (its id is in the reserved ``internal_test_`` namespace) and, under it, an
internal_test engagement, which carries the same workspace stamp plus the fixed, server-forced
``WORKSPACE_INTERNAL_TEST_CLASSIFICATION``. Only an Admin may delete an internal_test engagement,
and only **logically**: ``deleted_at`` is set, the engagement leaves the
active lists and accepts no further work, and every record under it is kept. A real_client
engagement cannot be deleted at all.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Optional

from peak.persistence.allowlist import (
    CLIENT_PROFILE_COLUMNS,
    ENGAGEMENT_WORKSPACE_COLUMNS,
    WORKSPACE_ENGAGEMENT_CREATION_STAMP,
    WORKSPACE_ENGAGEMENT_STATUSES,
    WORKSPACE_INTERNAL_TEST_CLASSIFICATION,
    WORKSPACE_INTERNAL_TEST_CLIENT_PREFIX,
    is_allowed_workspace_write,
)
from peak.persistence.governance import (
    ENGAGEMENT_CATEGORY_INTERNAL_TEST,
    RESERVED_INTERNAL_TEST_CLIENT_PREFIXES,
    is_reserved_internal_test_client_id,
    validate_engagement_classification,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_KEY_PERSONNEL = 25
MAX_LONG_TEXT = 4000
#: The account role that may set or change an engagement's assigned consultant (Phase 213).
ASSIGNMENT_ROLE = "admin"
#: The account role that may delete (retire) an internal_test engagement. Creating one is open to
#: every consultant; its classification is always server-forced.
INTERNAL_TEST_DELETE_ROLE = "admin"
assert WORKSPACE_INTERNAL_TEST_CLIENT_PREFIX in RESERVED_INTERNAL_TEST_CLIENT_PREFIXES

# Column -> max length for single-line client profile text.
_CLIENT_TEXT_LIMITS = {
    "organization_label": 255, "address_line1": 255, "address_line2": 255, "city": 128,
    "region": 128, "postal_code": 32, "country": 128, "contact_name": 255,
    "contact_title": 255, "contact_email": 254, "contact_phone": 64,
}


class WorkspaceError(ValueError):
    """A workspace request was refused. ``code`` is a short machine-readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _clean(value, limit: int, label: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkspaceError("invalid_field", f"{label} must be text.")
    value = value.strip()
    if len(value) > limit:
        raise WorkspaceError("invalid_field", f"{label} must be at most {limit} characters.")
    return value or None


def _email(value, label: str) -> Optional[str]:
    value = _clean(value, 254, label)
    if value is not None and not _EMAIL_RE.match(value):
        raise WorkspaceError("invalid_field", f"{label} is not a valid email address.")
    return value


def _key_personnel(value) -> Optional[list]:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > MAX_KEY_PERSONNEL:
        raise WorkspaceError("invalid_field",
                             f"Key personnel must be a list of at most {MAX_KEY_PERSONNEL} people.")
    people = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"name", "role", "email", "phone"}:
            raise WorkspaceError("invalid_field", "Each key person has name, role, email, phone.")
        person = {
            "name": _clean(item.get("name"), 255, "Key person name"),
            "role": _clean(item.get("role"), 255, "Key person role"),
            "email": _email(item.get("email"), "Key person email"),
            "phone": _clean(item.get("phone"), 64, "Key person phone"),
        }
        if person["name"] is None:
            if any(person.values()):
                raise WorkspaceError("invalid_field", "Each key person needs a name.")
            continue  # an entirely blank row is dropped
        people.append(person)
    return people or None


def _client_values(data: dict, creating: bool) -> dict:
    """Validated client profile columns present in ``data`` (all required columns on create)."""
    unknown = set(data) - CLIENT_PROFILE_COLUMNS
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an editable client field: {sorted(unknown)[0]}")
    values = {}
    for column, limit in _CLIENT_TEXT_LIMITS.items():
        if column in data:
            values[column] = (_email(data[column], "Contact email") if column == "contact_email"
                              else _clean(data[column], limit, column.replace("_", " ")))
    if "description" in data:
        values["description"] = _clean(data["description"], MAX_LONG_TEXT, "Description")
    if "key_personnel" in data:
        values["key_personnel"] = _key_personnel(data["key_personnel"])
    if (creating or "organization_label" in values) and not values.get("organization_label"):
        raise WorkspaceError("invalid_field", "Company name is required.")
    return values


def _client_dict(row, engagements=None) -> dict:
    out = {"id": row.id, "internal_test": is_reserved_internal_test_client_id(row.id)}
    for column in sorted(CLIENT_PROFILE_COLUMNS):
        out[column] = getattr(row, column)
    out["key_personnel"] = out["key_personnel"] or []
    if engagements is not None:
        out["engagements"] = engagements
    return out


def is_internal_test(engagement) -> bool:
    return engagement.engagement_category == ENGAGEMENT_CATEGORY_INTERNAL_TEST


def source_marker(engagement) -> dict:
    """The engagement's machine-readable source state (Phase 215).

    This is the propagation point for future capsule projection: a capsule derived from this
    engagement's records must carry ``engagement_classification`` (``internal_test`` marks test
    material, never real-client operational data) and ``source_status`` (``deleted`` once an Admin
    has retired it). Nothing here publishes anything.
    """
    return {"engagement_classification": engagement.engagement_category,
            "source_status": "deleted" if engagement.deleted_at is not None else "active"}


def assessment_read_options(session_factory, engagement_id: str) -> dict:
    """Phase 57 read options for the consultant assessment and report routes (Phase 215).

    A stamped internal_test workspace engagement is read in the existing ``INTERNAL_ADMIN`` mode
    with ``include_internal_test`` explicitly true, so the consultant workflow can be exercised on
    it. Every other engagement keeps the default read: real_client is unchanged, and an internal
    record without the workspace stamp (the Phase 59 anchor) stays invisible.
    """
    from peak.db.engagement_read_isolation import ReadMode
    from peak.db.models import Engagement

    with session_factory() as session:
        row = session.get(Engagement, engagement_id)
        stamped = row is not None and all(
            getattr(row, k) == v for k, v in WORKSPACE_ENGAGEMENT_CREATION_STAMP.items())
        if stamped and is_internal_test(row):
            return {"mode": ReadMode.INTERNAL_ADMIN, "include_internal_test": True}
    return {}


def require_active(engagement) -> None:
    """Refuse new work on a deleted (retired) internal_test engagement. Its history stays readable."""
    if engagement.deleted_at is not None:
        raise WorkspaceError("engagement_deleted",
                             "This internal test engagement was deleted; it accepts no new work.")


def _engagement_dicts(session, rows) -> list:
    from sqlalchemy import select

    from peak.db.models import Client, Consultant

    client_ids = {r.client_id for r in rows}
    consultant_ids = {r.assigned_consultant_id for r in rows if r.assigned_consultant_id}
    clients = dict(session.execute(
        select(Client.id, Client.organization_label).where(Client.id.in_(client_ids))).all()) \
        if client_ids else {}
    consultants = dict(session.execute(
        select(Consultant.id, Consultant.name).where(Consultant.id.in_(consultant_ids))).all()) \
        if consultant_ids else {}
    return [{
        "id": r.id,
        "engagement_label": r.engagement_label,
        "objective": r.objective,
        "status": r.status,
        "current_phase": r.current_phase,
        "client": {"id": r.client_id, "name": clients.get(r.client_id)},
        "assigned_consultant": (
            {"id": r.assigned_consultant_id, "name": consultants.get(r.assigned_consultant_id)}
            if r.assigned_consultant_id else None),
        **source_marker(r),
        "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
    } for r in rows]


def _require_allowed(table: str, action: str, values: dict) -> None:
    if not is_allowed_workspace_write(table, action, values.keys()):
        raise WorkspaceError("write_not_permitted", f"{table}/{action} may not write these fields.")


# --------------------------------------------------------------------------- clients


def list_clients(session_factory, query: Optional[str] = None,
                 internal_test: Optional[bool] = None) -> list:
    """Clients by name. ``internal_test`` true lists only reserved internal-test clients (the
    engagement form's Internal Test chooser); false lists only real clients; None lists both (the
    normal Clients workspace). Both the chooser and the workspace leave out retired internal-test
    clients, those whose engagements have all been retired; their records stay readable at
    ``/clients/{id}``. ``engagement_count`` counts active engagements only."""
    from sqlalchemy import func, or_, select

    from peak.db.models import Client, Engagement

    with session_factory() as session:
        stmt = select(Client).order_by(Client.organization_label, Client.id)
        if internal_test is not None:
            reserved = Client.id.startswith(WORKSPACE_INTERNAL_TEST_CLIENT_PREFIX, autoescape=True)
            stmt = stmt.where(reserved if internal_test else ~reserved)
        if query and query.strip():
            like = f"%{query.strip().lower()}%"
            stmt = stmt.where(or_(func.lower(Client.organization_label).like(like),
                                  func.lower(Client.city).like(like),
                                  func.lower(Client.contact_name).like(like)))
        rows = session.scalars(stmt).all()
        counts = dict(session.execute(
            select(Engagement.client_id, func.count()).where(Engagement.deleted_at.is_(None))
            .group_by(Engagement.client_id)).all())
        if internal_test is not False:
            retired = set(session.scalars(
                select(Engagement.client_id).where(Engagement.deleted_at.is_not(None)).distinct()))
            rows = [r for r in rows if not (is_reserved_internal_test_client_id(r.id)
                                            and r.id in retired and not counts.get(r.id))]
        return [{"id": r.id, "organization_label": r.organization_label, "city": r.city,
                 "country": r.country, "contact_name": r.contact_name,
                 "internal_test": is_reserved_internal_test_client_id(r.id),
                 "engagement_count": counts.get(r.id, 0)} for r in rows]


def get_client(session_factory, client_id: str) -> Optional[dict]:
    from sqlalchemy import select

    from peak.db.models import Client, Engagement

    with session_factory() as session:
        row = session.get(Client, client_id)
        if row is None:
            return None
        engagements = session.scalars(select(Engagement).where(Engagement.client_id == client_id,
                                                               Engagement.deleted_at.is_(None))
                                      .order_by(Engagement.engagement_label, Engagement.id)).all()
        return _client_dict(row, _engagement_dicts(session, engagements))


def create_client(session_factory, data: dict) -> dict:
    """Create a client. ``internal_test: true`` puts it in the reserved internal-test namespace."""
    from peak.db.models import Client

    data = dict(data)
    internal_test = data.pop("internal_test", False) is True
    prefix = WORKSPACE_INTERNAL_TEST_CLIENT_PREFIX if internal_test else "client_"
    values = {"id": f"{prefix}{secrets.token_hex(8)}", **_client_values(data, creating=True)}
    _require_allowed("clients", "create_client_profile", values)
    with session_factory() as session:
        session.add(Client(**values))
        session.commit()
    return get_client(session_factory, values["id"])


def update_client(session_factory, client_id: str, data: dict) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import Client

    values = _client_values(data, creating=False)
    if not values:
        raise WorkspaceError("invalid_field", "Nothing to update.")
    _require_allowed("clients", "update_client_profile", values)
    with session_factory() as session:
        result = session.execute(update(Client).where(Client.id == client_id).values(**values))
        session.commit()
        if result.rowcount == 0:
            return None
    return get_client(session_factory, client_id)


# --------------------------------------------------------------------------- engagements


def _engagement_values(session, data: dict, creating: bool) -> dict:
    from peak.db.models import Client, Consultant

    allowed = ENGAGEMENT_WORKSPACE_COLUMNS | ({"client_id"} if creating else set())
    unknown = set(data) - allowed
    if unknown:
        raise WorkspaceError("invalid_field",
                             f"Not an editable engagement field: {sorted(unknown)[0]}")
    values = {}
    if "engagement_label" in data:
        values["engagement_label"] = _clean(data["engagement_label"], 255, "Engagement name")
    if "objective" in data:
        values["objective"] = _clean(data["objective"], MAX_LONG_TEXT, "Objective")
    if "current_phase" in data:
        values["current_phase"] = _clean(data["current_phase"], 128, "Current phase")
    if "status" in data:
        if data["status"] not in WORKSPACE_ENGAGEMENT_STATUSES:
            raise WorkspaceError("invalid_field", "Status must be active, on_hold, or closed.")
        values["status"] = data["status"]
    if "assigned_consultant_id" in data:
        cid = data["assigned_consultant_id"] or None
        if cid is not None and session.get(Consultant, cid) is None:
            raise WorkspaceError("invalid_field", "Assigned consultant does not exist.")
        values["assigned_consultant_id"] = cid
    if creating:
        client_id = data.get("client_id")
        if not isinstance(client_id, str) or session.get(Client, client_id) is None:
            raise WorkspaceError("invalid_field", "Client does not exist.")
        values["client_id"] = client_id
        values.setdefault("status", "active")
    if (creating or "engagement_label" in values) and not values.get("engagement_label"):
        raise WorkspaceError("invalid_field", "Engagement name is required.")
    return values


def list_engagements(session_factory) -> list:
    from sqlalchemy import select

    from peak.db.models import Engagement

    with session_factory() as session:
        rows = session.scalars(select(Engagement).where(Engagement.deleted_at.is_(None))
                               .order_by(Engagement.engagement_label, Engagement.id)).all()
        return _engagement_dicts(session, rows)


def get_engagement(session_factory, engagement_id: str) -> Optional[dict]:
    from peak.db.models import Engagement

    with session_factory() as session:
        row = session.get(Engagement, engagement_id)
        return _engagement_dicts(session, [row])[0] if row is not None else None


def _refuse_assignment_change(actor_role: Optional[str]) -> None:
    """Phase 213: the assigned consultant names the Lead Consultant, whose approval is the first
    release gate, so only an Admin may set or change it. Every consultant still reaches every
    engagement; this restricts one field, it is not an access boundary."""
    if actor_role != ASSIGNMENT_ROLE:
        raise WorkspaceError("admin_required", "Only an Admin can change the assigned consultant.")


def _classification(internal_test: bool, client_id: str) -> dict:
    """The server-forced classification for a new engagement, checked against the Phase 55 policy."""
    classification = WORKSPACE_INTERNAL_TEST_CLASSIFICATION if internal_test else {}
    reasons = validate_engagement_classification(
        classification.get("engagement_category", "real_client"),
        classification.get("real_client_data", True), classification.get("client_accessible", True),
        False, client_id)
    if reasons:
        raise WorkspaceError(
            "classification_mismatch",
            "An internal test engagement needs an internal test client, and an internal test "
            "client takes only internal test engagements.")
    return classification


def create_engagement(session_factory, data: dict, actor_role: Optional[str] = None,
                      actor_id: Optional[str] = None) -> dict:
    """Create an engagement. ``internal_test: true`` classifies it internal_test (server-forced).

    Lead assignment stays Admin-only, with one exception: a non-Admin who creates an internal_test
    engagement becomes its Lead automatically (server-set), so training needs no Admin. They cannot
    name anyone else, and reassignment afterwards is Admin-only as for every engagement.
    """
    from peak.db.models import Engagement

    data = dict(data)
    internal_test = data.pop("internal_test", False) is True
    confirmed = data.pop("internal_test_confirmed", False) is True
    if internal_test and not confirmed:
        raise WorkspaceError(
            "internal_test_confirmation_required",
            "Confirm that this engagement is for internal testing, training or practice only.")
    with session_factory() as session:
        values = {"id": f"eng_{secrets.token_hex(8)}",
                  **_engagement_values(session, data, creating=True)}
        if internal_test and actor_role != ASSIGNMENT_ROLE:
            if values.get("assigned_consultant_id") not in (None, actor_id) or not actor_id:
                _refuse_assignment_change(actor_role)
            values["assigned_consultant_id"] = actor_id
        elif values.get("assigned_consultant_id"):
            _refuse_assignment_change(actor_role)
        classification = _classification(internal_test, values["client_id"])
        _require_allowed("engagements", "create_workspace_engagement", values)
        # Caller-derived columns are checked above; the stamp and classification are added only here.
        session.add(Engagement(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP, **classification))
        session.commit()
    return get_engagement(session_factory, values["id"])


def update_engagement(session_factory, engagement_id: str, data: dict,
                      actor_role: Optional[str] = None) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import Engagement

    with session_factory() as session:
        values = _engagement_values(session, data, creating=False)
        if not values:
            raise WorkspaceError("invalid_field", "Nothing to update.")
        row = session.get(Engagement, engagement_id)
        if row is not None:
            require_active(row)
        if "assigned_consultant_id" in values:
            if row is not None and row.assigned_consultant_id != values["assigned_consultant_id"]:
                _refuse_assignment_change(actor_role)
        _require_allowed("engagements", "update_engagement_workspace_fields", values)
        result = session.execute(
            update(Engagement).where(Engagement.id == engagement_id).values(**values))
        session.commit()
        if result.rowcount == 0:
            return None
    return get_engagement(session_factory, engagement_id)


def delete_internal_test_engagement(session_factory, engagement_id: str, confirm_label,
                                    actor_id: str, actor_role: Optional[str]) -> Optional[dict]:
    """An Admin's **logical** deletion of an internal_test engagement (Phase 215).

    Sets ``deleted_at`` / ``deleted_by_consultant_id`` and nothing else: the engagement row, its
    discovery records and its artifact history (versions, packages, renditions, approvals,
    designations, releases) are all kept, immutable and auditable. ``confirm_label`` must repeat the
    engagement's name. A real_client engagement is refused; there is no other delete path.
    """
    from sqlalchemy import update

    from peak.db.models import Engagement

    if actor_role != INTERNAL_TEST_DELETE_ROLE:
        raise WorkspaceError("admin_required", "Only an Admin can delete an internal test engagement.")
    values = {"deleted_at": datetime.now(timezone.utc).replace(tzinfo=None),
              "deleted_by_consultant_id": actor_id}
    _require_allowed("engagements", "retire_internal_test_engagement", values)
    with session_factory() as session:
        row = session.get(Engagement, engagement_id)
        if row is None:
            return None
        if not is_internal_test(row):
            raise WorkspaceError("not_internal_test",
                                 "Only an internal test engagement can be deleted.")
        require_active(row)
        if confirm_label != row.engagement_label:
            raise WorkspaceError("confirmation_required",
                                 "Type the engagement name exactly to confirm the deletion.")
        session.execute(update(Engagement).where(Engagement.id == engagement_id,
                                                 Engagement.deleted_at.is_(None)).values(**values))
        session.commit()
    return get_engagement(session_factory, engagement_id)


def list_consultant_options(session_factory) -> list:
    """Every consultant's id and name, for the assignment picker (no email, no role)."""
    from sqlalchemy import select

    from peak.db.models import Consultant

    with session_factory() as session:
        return [{"id": i, "name": n} for i, n in session.execute(
            select(Consultant.id, Consultant.name).order_by(Consultant.name))]
