#!/usr/bin/env python3
"""Phase 202 client and engagement workspace check (offline; temporary SQLite only).

Proves, through the consultant API over ``peak.workspace``:

1. an authenticated consultant can create a client (full profile, key personnel);
2. an authenticated consultant can edit a client, and cannot write a governance column;
3. one client can have several engagements;
4. an authenticated consultant can create and edit an engagement;
5. assignment, status, and current phase persist;
6. every workspace engagement is born with owner ``peak_consultants`` and scope
   ``engagement_authorized``, which no caller can set or change, and which an unchanged
   controlled writer (Phase 34 intake note) accepts only when owner and scope match.

Plus migration 016 structure and the narrow workspace allowlist. No network, no credential.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_failures = []
SECRET = "phase202-test-secret-" + "x" * 32
PASSWORD = "consultant-pw-202"


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def migration_checks(tmp):
    print("\n[migration 016]")
    db = os.path.join(tmp, "migrate.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"

    def alembic(*args):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                              capture_output=True, text=True).returncode

    up = alembic("upgrade", "016_client_engagement_workspace_fields")
    con = sqlite3.connect(db)
    client_cols = {r[1] for r in con.execute("PRAGMA table_info(clients)")}
    eng_cols = {r[1] for r in con.execute("PRAGMA table_info(engagements)")}
    con.close()
    check("upgrade to 016 adds the client profile and engagement workflow columns",
          up == 0 and {"description", "address_line1", "city", "contact_email", "key_personnel"}
          <= client_cols and {"objective", "assigned_consultant_id", "current_phase"} <= eng_cols)
    down = alembic("downgrade", "015_consultants")
    con = sqlite3.connect(db)
    eng_cols = {r[1] for r in con.execute("PRAGMA table_info(engagements)")}
    con.close()
    check("downgrade to 015 removes them", down == 0 and "current_phase" not in eng_cols)
    src = open(os.path.join(REPO_ROOT, "alembic/versions/016_client_engagement_workspace_fields.py"))\
        .read().lower()
    check("migration 016 carries no data (no INSERT)",
          "insert into" not in src and "bulk_insert" not in src and "op.execute(" not in src)


def allowlist_checks():
    print("\n[workspace allowlist]")
    from peak.persistence import allowlist as a

    phase202_pairs = {("clients", "create_client_profile"), ("clients", "update_client_profile"),
                      ("engagements", "create_workspace_engagement"),
                      ("engagements", "update_engagement_workspace_fields")}
    check("the four Phase 202 workspace pairs keep their exact columns; no pair is a delete",
          phase202_pairs <= set(a.WORKSPACE_WRITE_COLUMNS)
          and a.WORKSPACE_WRITE_COLUMNS[("clients", "update_client_profile")]
          == a.CLIENT_PROFILE_COLUMNS
          and a.WORKSPACE_WRITE_COLUMNS[("engagements", "update_engagement_workspace_fields")]
          == a.ENGAGEMENT_WORKSPACE_COLUMNS
          and not any("delete" in action for _, action in a.WORKSPACE_WRITE_COLUMNS))
    check("no workspace column set touches a governance/classification/audit column",
          not any(c & a.WORKSPACE_FORBIDDEN_COLUMNS for c in a.WORKSPACE_WRITE_COLUMNS.values()))
    check("engagement update may not change client_id or any governance column",
          not a.is_allowed_workspace_write("engagements", "update_engagement_workspace_fields",
                                           {"client_id"})
          and not a.is_allowed_workspace_write("engagements", "update_engagement_workspace_fields",
                                               {"status", "client_accessible"}))
    check("engagements stay prohibited on the generic path; clients reach no controlled writer",
          a.is_prohibited_table("engagements") and not a.is_allowed_table("engagements")
          and a.is_workspace_only_table("clients")
          and not a.is_allowed_anchor_creation_pair("clients", a.ANCHOR_CREATION_ACTION))


def api_checks(session_factory):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.models import Engagement

    casey = accounts.create_consultant(session_factory, name="Casey Consultant",
                                       email="casey@example.com", role="consultant",
                                       password=PASSWORD)
    morgan = accounts.create_consultant(session_factory, name="Morgan Lee",
                                        email="morgan@example.com", role="consultant",
                                        password=PASSWORD)
    app = create_app(session_factory=session_factory, secret_key=SECRET, secure_cookie=True)
    anon = TestClient(app, base_url="https://testserver")
    c = TestClient(app, base_url="https://testserver")
    c.post("/auth/login", json={"email": "casey@example.com", "password": PASSWORD})

    print("\n[auth]")
    check("unauthenticated client and engagement access -> 401",
          anon.get("/clients").status_code == 401 and anon.post("/engagements", json={}).status_code
          == 401)

    print("\n[1-2] clients")
    profile = {
        "organization_label": "Acme Logistics", "description": "Regional 3PL.",
        "address_line1": "1 Dock St", "city": "Denver", "region": "CO", "postal_code": "80202",
        "country": "USA", "contact_name": "Pat Doe", "contact_title": "COO",
        "contact_email": "pat@acme.example", "contact_phone": "555-0100",
        "key_personnel": [{"name": "Lee Ray", "role": "Warehouse lead", "email": None,
                           "phone": "555-0101"}],
    }
    r = c.post("/clients", json=profile)
    client = r.json().get("client", {})
    check("a consultant (non-Admin) creates a client with the full profile",
          r.status_code == 201 and client.get("city") == "Denver"
          and client.get("key_personnel", [{}])[0].get("name") == "Lee Ray")
    cid = client.get("id", "")
    check("company name is required", c.post("/clients", json={"city": "X"}).status_code == 422)
    r = c.patch(f"/clients/{cid}", json={"city": "Boulder", "contact_title": "CEO",
                                         "key_personnel": []})
    check("editing a client persists the changed fields only",
          r.status_code == 200 and r.json()["client"]["city"] == "Boulder"
          and r.json()["client"]["contact_title"] == "CEO"
          and r.json()["client"]["organization_label"] == "Acme Logistics"
          and r.json()["client"]["key_personnel"] == [])
    check("a governance field in a client edit is refused (422)",
          c.patch(f"/clients/{cid}", json={"owner_id": "x"}).status_code == 422)
    check("search finds the client by name",
          [x["id"] for x in c.get("/clients", params={"q": "acme"}).json()["clients"]] == [cid])

    print("\n[3-5] engagements")
    e1 = c.post("/engagements", json={"client_id": cid, "engagement_label": "Inventory review",
                                      "assigned_consultant_id": morgan["id"],
                                      "current_phase": "Discovery", "objective": "Baseline."})
    e2 = c.post("/engagements", json={"client_id": cid, "engagement_label": "WMS selection"})
    eid = e1.json().get("engagement", {}).get("id", "")
    check("two engagements are created for one client",
          e1.status_code == 201 and e2.status_code == 201
          and len(c.get(f"/clients/{cid}").json()["client"]["engagements"]) == 2)
    got = c.get(f"/engagements/{eid}").json()["engagement"]
    check("assignment, default status, phase and client persist on create",
          got["assigned_consultant"] == {"id": morgan["id"], "name": "Morgan Lee"}
          and got["status"] == "active" and got["current_phase"] == "Discovery"
          and got["client"] == {"id": cid, "name": "Acme Logistics"})
    r = c.patch(f"/engagements/{eid}", json={"status": "on_hold", "current_phase": "Analysis",
                                             "assigned_consultant_id": casey["id"]})
    got = r.json().get("engagement", {})
    check("editing an engagement persists status, phase and reassignment",
          r.status_code == 200 and got["status"] == "on_hold" and got["current_phase"] == "Analysis"
          and got["assigned_consultant"]["id"] == casey["id"])
    check("an unknown status, unknown consultant, or client change is refused (422)",
          c.patch(f"/engagements/{eid}", json={"status": "paused"}).status_code == 422
          and c.patch(f"/engagements/{eid}",
                      json={"assigned_consultant_id": "cons_nobody"}).status_code == 422
          and c.patch(f"/engagements/{eid}", json={"client_id": cid}).status_code == 422)
    check("a governance field in an engagement edit is refused (422)",
          c.patch(f"/engagements/{eid}", json={"client_accessible": False}).status_code == 422)
    with session_factory() as s:
        row = s.get(Engagement, eid)
    check("the engagement is born with owner peak_consultants and scope engagement_authorized",
          row.owner_id == "peak_consultants" and row.authorization_scope == "engagement_authorized")
    check("other governance columns keep their defaults (draft review, no publication)",
          row.review_status == "draft" and row.engagement_category == "real_client"
          and row.capsule_publication_authorized is False)
    before = len(c.get("/engagements").json()["engagements"])
    check("a caller cannot supply owner_id or authorization_scope on create (422, nothing created)",
          c.post("/engagements", json={"client_id": cid, "engagement_label": "X",
                                       "authorization_scope": "client_facing_approved"})
          .status_code == 422
          and c.post("/engagements", json={"client_id": cid, "engagement_label": "X",
                                           "owner_id": "someone"}).status_code == 422
          and len(c.get("/engagements").json()["engagements"]) == before)
    check("an edit cannot supply owner_id or authorization_scope (422)",
          c.patch(f"/engagements/{eid}", json={"authorization_scope": "revoked"}).status_code == 422
          and c.patch(f"/engagements/{eid}", json={"owner_id": "someone"}).status_code == 422)
    c.patch(f"/engagements/{eid}", json={"engagement_label": "Inventory review (renamed)"})
    with session_factory() as s:
        row = s.get(Engagement, eid)
    check("a normal edit leaves owner and scope unchanged",
          row.engagement_label == "Inventory review (renamed)"
          and row.owner_id == "peak_consultants" and row.authorization_scope == "engagement_authorized")
    writer_checks(session_factory, cid, eid)
    listed = c.get("/engagements").json()["engagements"]
    check("the engagement list shows client, consultant, status and phase",
          len(listed) == 2 and any(e["id"] == eid and e["client"]["name"] == "Acme Logistics"
                                   and e["status"] == "on_hold" for e in listed))
    check("missing records return 404",
          c.get("/clients/client_missing").status_code == 404
          and c.patch("/engagements/eng_missing", json={"status": "closed"}).status_code == 404)


def writer_checks(session_factory, cid, eid):
    """An unchanged controlled writer accepts the workspace engagement only on an exact match."""
    print("\n[6] controlled-writer compatibility (Phase 34 intake note writer, unchanged)")
    from peak.db.intake_note_writer import persist_intake_note_record
    from peak.db.writer_contracts import IntakeNoteDraft
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

    def attempt(owner, scope, key):
        ident = dict(owner_id=owner, client_id=cid, engagement_id=eid)
        draft = IntakeNoteDraft(
            **ident, authorization_scope=scope, note_type="discovery_call",
            note_source="consultant",
            note_text="The operations lead described seasonal peaks and a manual pick path.",
            note_summary="Discovery call: seasonal peaks", captured_by="consultant_a",
            captured_role="lead_consultant", source_ref="call_1", review_status="needs_review",
            lifecycle_status="draft", client_facing_approved=False, financial_verified=False,
            capsule_candidate_ready=False, publication_allowed=False, execution_allowed=False,
            requires_human_review=True, warnings=["intake note"])
        subject = ControlledWriteSubject(subject_record_id=eid, subject_record_type="engagement",
                                         stored_authorization_scope=scope, **ident)
        request = ControlledWriteRequest(
            **ident, requested_by="consultant_a", requester_role="consultant",
            authorization_scope=scope, target_table="intake_note_records",
            requested_action="create_intake_note_record", subject=subject, record_draft=draft,
            source_phase="phase202", lifecycle_status="active", idempotency_key=key)
        return persist_intake_note_record(request, session_factory=session_factory)

    ok = attempt("peak_consultants", "engagement_authorized", "p202-intake-1")
    check(f"matching owner and scope: the writer creates the record ({ok.outcome})",
          ok.permitted and ok.stored_record_id is not None)
    bad_owner = attempt("someone_else", "engagement_authorized", "p202-intake-2")
    check(f"mismatched owner is still rejected ({bad_owner.reason_code})",
          not bad_owner.permitted and bad_owner.stored_record_id is None)
    bad_scope = attempt("peak_consultants", "internal_peak_only", "p202-intake-3")
    check(f"mismatched scope is still rejected ({bad_scope.reason_code})",
          not bad_scope.permitted and bad_scope.reason_code == "stored_scope_mismatch")


def main() -> int:
    print("Peak Phase 202 client and engagement workspace check")
    print("=" * 53)
    try:
        import argon2, fastapi, httpx, itsdangerous, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python after "
              "pip install -r requirements-web.txt for the full check")
        return 0
    import peak.db.models  # noqa: F401  (registers models on Base.metadata)
    from peak.db.base import Base
    from peak.db.session import create_session_factory

    tmp = tempfile.mkdtemp(prefix="peak_phase202_")
    try:
        migration_checks(tmp)
        allowlist_checks()
        factory = create_session_factory(url=f"sqlite:///{os.path.join(tmp, 'api.sqlite3')}")
        Base.metadata.create_all(factory.kw["bind"])
        api_checks(factory)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
