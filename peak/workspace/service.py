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
"""

from __future__ import annotations

import re
import secrets
from typing import Optional

from peak.persistence.allowlist import (
    CLIENT_PROFILE_COLUMNS,
    ENGAGEMENT_WORKSPACE_COLUMNS,
    WORKSPACE_ENGAGEMENT_CREATION_STAMP,
    WORKSPACE_ENGAGEMENT_STATUSES,
    is_allowed_workspace_write,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_KEY_PERSONNEL = 25
MAX_LONG_TEXT = 4000

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
    out = {"id": row.id}
    for column in sorted(CLIENT_PROFILE_COLUMNS):
        out[column] = getattr(row, column)
    out["key_personnel"] = out["key_personnel"] or []
    if engagements is not None:
        out["engagements"] = engagements
    return out


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
    } for r in rows]


def _require_allowed(table: str, action: str, values: dict) -> None:
    if not is_allowed_workspace_write(table, action, values.keys()):
        raise WorkspaceError("write_not_permitted", f"{table}/{action} may not write these fields.")


# --------------------------------------------------------------------------- clients


def list_clients(session_factory, query: Optional[str] = None) -> list:
    from sqlalchemy import func, or_, select

    from peak.db.models import Client, Engagement

    with session_factory() as session:
        stmt = select(Client).order_by(Client.organization_label, Client.id)
        if query and query.strip():
            like = f"%{query.strip().lower()}%"
            stmt = stmt.where(or_(func.lower(Client.organization_label).like(like),
                                  func.lower(Client.city).like(like),
                                  func.lower(Client.contact_name).like(like)))
        rows = session.scalars(stmt).all()
        counts = dict(session.execute(
            select(Engagement.client_id, func.count()).group_by(Engagement.client_id)).all())
        return [{"id": r.id, "organization_label": r.organization_label, "city": r.city,
                 "country": r.country, "contact_name": r.contact_name,
                 "engagement_count": counts.get(r.id, 0)} for r in rows]


def get_client(session_factory, client_id: str) -> Optional[dict]:
    from sqlalchemy import select

    from peak.db.models import Client, Engagement

    with session_factory() as session:
        row = session.get(Client, client_id)
        if row is None:
            return None
        engagements = session.scalars(select(Engagement).where(Engagement.client_id == client_id)
                                      .order_by(Engagement.engagement_label, Engagement.id)).all()
        return _client_dict(row, _engagement_dicts(session, engagements))


def create_client(session_factory, data: dict) -> dict:
    from peak.db.models import Client

    values = {"id": f"client_{secrets.token_hex(8)}", **_client_values(data, creating=True)}
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
        rows = session.scalars(select(Engagement)
                               .order_by(Engagement.engagement_label, Engagement.id)).all()
        return _engagement_dicts(session, rows)


def get_engagement(session_factory, engagement_id: str) -> Optional[dict]:
    from peak.db.models import Engagement

    with session_factory() as session:
        row = session.get(Engagement, engagement_id)
        return _engagement_dicts(session, [row])[0] if row is not None else None


def create_engagement(session_factory, data: dict) -> dict:
    from peak.db.models import Engagement

    with session_factory() as session:
        values = {"id": f"eng_{secrets.token_hex(8)}",
                  **_engagement_values(session, data, creating=True)}
        _require_allowed("engagements", "create_workspace_engagement", values)
        # Caller-derived columns are checked above; the governance stamp is added only here.
        session.add(Engagement(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        session.commit()
    return get_engagement(session_factory, values["id"])


def update_engagement(session_factory, engagement_id: str, data: dict) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import Engagement

    with session_factory() as session:
        values = _engagement_values(session, data, creating=False)
        if not values:
            raise WorkspaceError("invalid_field", "Nothing to update.")
        _require_allowed("engagements", "update_engagement_workspace_fields", values)
        result = session.execute(
            update(Engagement).where(Engagement.id == engagement_id).values(**values))
        session.commit()
        if result.rowcount == 0:
            return None
    return get_engagement(session_factory, engagement_id)


def list_consultant_options(session_factory) -> list:
    """Every consultant's id and name, for the assignment picker (no email, no role)."""
    from sqlalchemy import select

    from peak.db.models import Consultant

    with session_factory() as session:
        return [{"id": i, "name": n} for i, n in session.execute(
            select(Consultant.id, Consultant.name).order_by(Consultant.name))]
