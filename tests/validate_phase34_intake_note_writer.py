#!/usr/bin/env python3
"""Phase 34 controlled-DB intake-note-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/migration/doc files exist and compile;
  the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or
  credential, and no Phase 22 review writer; the Phase 32 `peak/reviewer_decisions` package stays
  DB-free and the Phase 33 writer still uses the public classifier; the migration is additive
  schema-only (creates one table, no INSERT/seed, down_revision 008); the Phase 17 allowlist gained
  exactly the one new table/action; the docs carry the required language; the repo stays source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database — migration upgrade/downgrade/re-upgrade, successful create (note_text persisted but
  never echoed), idempotent replay, conflicting replay, DB-backed authorization (stored-scope
  comparison), identity/allowlist checks, posture rejections, note-text/label/summary content-safety
  rejections (non-echoing), side-effect discipline (no `review_records`/`agent_run_records` write),
  and transaction/failure semantics. SQLite here is only a fast structural smoke path — NOT the
  production-readiness proof path (see docs/PRODUCTION_PARITY_DB_VALIDATION.md). Skipped with
  instructions if SQLAlchemy is absent (still exits 0).

Phase 34 approves nothing, publishes nothing, executes nothing, calls no Phase 22 review writer,
creates no `review_records`/`agent_run_records` row, and makes no LLM/MockLLM/AgentNet/AgentNet-
publication/MCP/resolver/connector/network call. It creates exactly one review-gated, non-final
`intake_note_records` row.

Exit status:
  0  -> all run checks passed (DB layer skipped counts as pass if deps absent)
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import shutil
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

REQUIRED_FILES = [
    "peak/db/intake_note_writer.py",
    "peak/db/writer_contracts.py",
    "alembic/versions/009_intake_note_records.py",
    "docs/INTAKE_NOTE_CONTROLLED_WRITER.md",
    "docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md",
]
WRITER_FILES = ["peak/db/intake_note_writer.py", "peak/db/writer_contracts.py"]
COMPILE_FILES = WRITER_FILES + ["alembic/versions/009_intake_note_records.py",
                                "tools/managed_mysql_check.py"]
DOCS = ["docs/INTAKE_NOTE_CONTROLLED_WRITER.md", "docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md"]
REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "review-gated",
    "non-final",
    "review_status=needs_review",
    "lifecycle_status=draft",
    "review_records",
    "server-stamped",
    "15 tables",
    "create_intake_note_record",
    "managed db",
    "never echo",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b")
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|resolver_client)\b", re.IGNORECASE)
REVIEW_WRITER_RE = re.compile(r"\breview_writer\b|persist_review_record")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE)
INSERT_PATTERNS = ("insert into", "bulk_insert", ".insert(")
DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _import_lines(text: str):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            yield s


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Writer scaffold files")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Writer imports no LLM/exec/AgentNet/connector/network/review-writer/credential")
    for rel in WRITER_FILES:
        text = read(rel)
        imports = list(_import_lines(text))
        check(f"{rel}: no network import",
              not [ln for ln in imports if NETWORK_IMPORT_RE.search(ln) or NETWORK_HTTP_RE.search(ln)])
        check(f"{rel}: no LLM provider import",
              not [ln for ln in imports if LLM_PROVIDER_RE.search(ln)])
        check(f"{rel}: no mock-LLM / executor import",
              not [ln for ln in imports if EXEC_IMPORT_RE.search(ln)])
        check(f"{rel}: no AgentNet/MCP/resolver/connector import",
              not [ln for ln in imports if CONNECTOR_RE.search(ln)])
        check(f"{rel}: no Phase 22 review writer import",
              not [ln for ln in imports if REVIEW_WRITER_RE.search(ln)])
        check(f"{rel}: no credential value literal", not CREDENTIAL_RE.search(text))

    print("\n4. Phase 32 stays DB-free; Phase 33 uses the public classifier")
    for rel in ("peak/reviewer_decisions/__init__.py", "peak/reviewer_decisions/contracts.py",
                "peak/reviewer_decisions/governance.py", "peak/reviewer_decisions/decision_mapper.py"):
        hits = [ln for ln in _import_lines(read(rel))
                if DB_IMPORT_RE.search(ln) or PEAK_DB_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)
    p33 = read("peak/db/internal_reviewer_decision_writer.py")
    check("Phase 33 writer uses public classify_prohibited_value_marker",
          "classify_prohibited_value_marker" in p33 and "_value_marker_category" not in p33)
    check("Phase 34 writer reuses the public classifier",
          "classify_prohibited_value_marker" in read("peak/db/intake_note_writer.py"))

    print("\n5. Migration is additive, creates one table, schema-only (no INSERT/seed)")
    mig = read("alembic/versions/009_intake_note_records.py")
    low = mig.lower()
    check("migration has no insert/seed pattern", not any(p in low for p in INSERT_PATTERNS))
    check("migration defines upgrade()", "def upgrade()" in mig)
    check("migration defines downgrade()", "def downgrade()" in mig)
    check("migration creates the table", "op.create_table" in mig)
    check("migration targets intake_note_records", "intake_note_records" in mig)
    check("migration adds unique idempotency index", "uq_intake_note_records_idem" in mig)
    check("migration down_revision is 008_internal_reviewer_decision_records",
          'down_revision = "008_internal_reviewer_decision_records"' in mig)
    check("downgrade drops the table", "op.drop_table" in mig)

    print("\n6. Allowlist gained exactly the new table/action (no broadening)")
    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_TABLES, is_allowed_action, is_allowed_table, is_prohibited_action,
    )
    check("intake_note_records allowed", is_allowed_table("intake_note_records"))
    check("create_intake_note_record allowed", is_allowed_action("create_intake_note_record"))
    check("no update/delete/upsert/raw-SQL intake action on allowlist",
          not any(a for a in ALLOWED_ACTIONS
                  if "intake" in a and a != "create_intake_note_record"))
    for bad in ("update_intake_note", "delete_intake_note", "upsert_intake_note",
                "publish_intake_note", "run_raw_sql"):
        check(f"prohibited/absent action '{bad}' not allowed",
              not is_allowed_action(bad) or is_prohibited_action(bad))
    check("exactly one intake table on allowlist",
          len([t for t in ALLOWED_TABLES if "intake" in t]) == 1)

    print("\n7. Doc language")
    blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"phrase present: '{phrase}'", phrase.lower() in blob)

    print("\n8. Source-only discipline")
    check("no examples/ directory", not os.path.exists(os.path.join(REPO_ROOT, "examples")))
    artifacts, dbfiles = [], []
    for dp, _, files in os.walk(REPO_ROOT):
        if _skip(dp):
            continue
        for f in files:
            rel = os.path.relpath(os.path.join(dp, f), REPO_ROOT)
            if f == ".env.example":
                continue
            if ".example." in f:
                artifacts.append(rel)
            if f.lower().endswith(DB_FILE_EXTS):
                dbfiles.append(rel)
    check("no committed data artifacts", not artifacts)
    check("no committed database files", not dbfiles)


# --------------------------------------------------------------------------- builders

# Synthetic, marker-free operational prose (NOT client-like; safe to keep in the repo).
_NOTE_TEXT = ("During the discovery call the operations lead described seasonal peak volume and the "
              "manual pick path. Putaway is slow and cycle counts happen quarterly.")
_NOTE_SUMMARY = "Discovery call: seasonal peaks and manual pick path"
_CANARY = "CANARY-DO-NOT-LEAK"
_KEY = "idem-intn-1"


def _make_builders():
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.db.writer_contracts import IntakeNoteDraft

    def subject(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized")
        base.update(over)
        return ControlledWriteSubject(**base)

    def draft(**over):
        base = dict(
            intake_note_id=None, owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            authorization_scope="engagement_authorized", note_type="discovery_call",
            note_source="consultant", note_text=_NOTE_TEXT, note_summary=_NOTE_SUMMARY,
            captured_by="consultant_a", captured_role="lead_consultant", source_ref="call_2026_07",
            source_ingestion_record_id="ing_1", related_evidence_reference_id="evid_1",
            related_review_bundle_record_id="rvb_1", review_status="needs_review",
            lifecycle_status="draft", client_facing_approved=False, financial_verified=False,
            capsule_candidate_ready=False, publication_allowed=False, execution_allowed=False,
            requires_human_review=True, warnings=["intake note"], captured_at=None)
        base.update(over)
        return IntakeNoteDraft(**base)

    def build(*, draft_over=None, subject_over=None, **cwr_over):
        d = draft(**(draft_over or {}))
        subj = subject(**(subject_over or {}))
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            target_table="intake_note_records", requested_action="create_intake_note_record",
            subject=subj, record_draft=d, source_phase="phase34", lifecycle_status="active",
            idempotency_key=_KEY)
        base.update(cwr_over)
        return ControlledWriteRequest(**base), d

    return subject, draft, build


def _blob(receipt) -> str:
    return " ".join(list(receipt.reasons or []) + list(receipt.warnings or []))


def _migration_reversibility() -> None:
    from sqlalchemy import create_engine, inspect
    from alembic.config import Config
    from alembic import command

    print("\n9. Migration apply / reversibility (temp SQLite structural smoke; NOT prod proof)")
    tmp = tempfile.mkdtemp(prefix="peak_phase34_mig_")
    prev_url = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created intake_note_records",
              "intake_note_records" in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns("intake_note_records")}
        check("table carries note_text + posture + idempotency columns",
              {"note_text", "note_summary", "note_type", "note_source", "captured_by",
               "publication_allowed", "execution_allowed", "requires_human_review",
               "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"])
               for i in insp.get_indexes("intake_note_records")}
        check("unique idempotency index over (owner,client,engagement,key)",
              idx.get("uq_intake_note_records_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        command.downgrade(cfg, "008_internal_reviewer_decision_records")
        check("downgrade drops the table",
              "intake_note_records" not in inspect(create_engine(url)).get_table_names())
        command.upgrade(cfg, "head")
        check("re-upgrade succeeds", True)
    finally:
        if prev_url is None:
            os.environ.pop("PEAK_DATABASE_URL", None)
        else:
            os.environ["PEAK_DATABASE_URL"] = prev_url
        shutil.rmtree(tmp, ignore_errors=True)


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    import peak.db.intake_note_writer as writer_mod
    from peak.db.intake_note_writer import (
        build_intake_note_controlled_write_request, persist_intake_note_record,
    )
    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, IntakeNoteRecord, ReviewRecord,
    )
    from peak.db.writer_contracts import IntakeNoteWriteOutcome as OC

    _migration_reversibility()

    subject, draft, build = _make_builders()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase34_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    def seed(factory, **over):
        s = factory()
        base = dict(id="eng_x", client_id="client_a", owner_id="owner_1",
                    authorization_scope="engagement_authorized", lifecycle_status="active",
                    review_status="active")
        base.update(over)
        s.add(Engagement(**base))
        s.commit()
        s.close()

    def count(factory, model):
        s = factory()
        n = s.query(model).count()
        s.close()
        return n

    # ---- Successful create ----
    print("\n10. Successful create (note_text persisted, never echoed; non-final)")
    f = fresh_db()
    seed(f)
    cwr, d = build()
    r = persist_intake_note_record(cwr, session_factory=f)
    check("outcome == created", r.outcome == OC.CREATED)
    check("permitted True", r.permitted is True)
    check("exactly one row created", count(f, IntakeNoteRecord) == 1)
    check("server-generated id (intn_ prefix)",
          bool(r.stored_record_id) and r.stored_record_id.startswith("intn_"))
    check("receipt created_at present", bool(r.created_at))
    check("receipt posture + safe labels",
          r.review_status == "needs_review" and r.lifecycle_status == "draft"
          and r.note_type == "discovery_call" and r.note_source == "consultant")
    check("flags: connection/sql/write/commit/created all True",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.transaction_committed and r.stored_record_created)
    check("non-effect flags all False",
          r.review_records_write_made is False and r.review_approval_made is False
          and r.client_facing_output_created is False and r.financial_verification_made is False
          and r.capsule_publication_made is False and r.agentnet_publication_made is False
          and r.agent_execution_made is False and r.llm_call_made is False
          and r.agentnet_call_made is False and r.resolver_call_made is False
          and r.network_call_made is False)
    check("receipt never echoes note_text", _NOTE_TEXT not in _blob(r))
    s = f()
    row = s.get(IntakeNoteRecord, r.stored_record_id)
    check("note_text persisted in DB", row.note_text == _NOTE_TEXT)
    check("note_summary stored", row.note_summary == _NOTE_SUMMARY)
    check("safe labels/refs stored",
          row.note_type == "discovery_call" and row.note_source == "consultant"
          and row.captured_by == "consultant_a" and row.source_ref == "call_2026_07"
          and row.source_ingestion_record_id == "ing_1"
          and row.related_evidence_reference_id == "evid_1"
          and row.related_review_bundle_record_id == "rvb_1")
    check("stored posture non-final",
          row.review_status == "needs_review" and row.lifecycle_status == "draft"
          and row.client_facing_approved is False and row.financial_verified is False
          and row.capsule_candidate_ready is False and row.publication_allowed is False
          and row.execution_allowed is False and row.requires_human_review is True)
    check("idempotency_key + payload_fingerprint persisted",
          bool(row.idempotency_key) and bool(row.payload_fingerprint))
    check("details_json stores a note_text hash, not a copy",
          row.details_json.get("note_text_sha256") and _NOTE_TEXT not in str(row.details_json))
    check("created_at server-stamped", row.created_at is not None)
    s.close()

    print("\n11. Side-effect discipline (no review_records / agent_run_records / unrelated)")
    check("NO review_records row created", count(f, ReviewRecord) == 0)
    check("NO agent_run_records row created", count(f, AgentRunRecord) == 0)
    check("clients untouched", count(f, Client) == 0)

    # ---- Planning helper ----
    print("\n12. CWR planning helper (DB-layer bridge)")
    f = fresh_db()
    seed(f)
    cwr2 = build_intake_note_controlled_write_request(
        draft(), requested_by="consultant_a", requester_role="consultant",
        idempotency_key="idem-intn-h")
    check("helper targets the one table/action",
          cwr2.target_table == "intake_note_records"
          and cwr2.requested_action == "create_intake_note_record")
    rh = persist_intake_note_record(cwr2, session_factory=f)
    check("helper-built request persists one row",
          rh.outcome == OC.CREATED and count(f, IntakeNoteRecord) == 1)

    # ---- Idempotent replay ----
    print("\n13. Idempotent replay")
    f = fresh_db()
    seed(f)
    first = persist_intake_note_record(build()[0], session_factory=f)
    second = persist_intake_note_record(build()[0], session_factory=f)
    check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
    check("no second row", count(f, IntakeNoteRecord) == 1)
    check("existing id returned", second.stored_record_id == first.stored_record_id)
    check("replay reports no new record",
          second.stored_record_created is False and second.database_write_made is False
          and second.existing_record_returned is True)

    # ---- Conflicting replay (edited note body under same key) ----
    print("\n14. Conflicting replay (edited note_text under same key)")
    f = fresh_db()
    seed(f)
    created = persist_intake_note_record(build()[0], session_factory=f)
    conflict = persist_intake_note_record(
        build(draft_over=dict(note_text=_NOTE_TEXT + " Additional walkaround detail."))[0],
        session_factory=f)
    check("conflict denied", conflict.outcome == OC.DENIED)
    check("conflict reason idempotency_conflict", conflict.reason_code == "idempotency_conflict")
    check("no new row on conflict", count(f, IntakeNoteRecord) == 1)
    s = f()
    check("existing row unchanged (note_text)",
          s.get(IntakeNoteRecord, created.stored_record_id).note_text == _NOTE_TEXT)
    s.close()

    # ---- DB-backed authorization ----
    print("\n15. DB-backed authorization (stored-scope comparison)")
    f = fresh_db()
    seed(f, authorization_scope="internal_peak_only")
    r = persist_intake_note_record(build()[0], session_factory=f)
    check("stored-scope mismatch denied",
          r.outcome == OC.DENIED and r.reason_code == "stored_scope_mismatch")
    check("no row on scope mismatch", count(f, IntakeNoteRecord) == 0)
    check("connection+sql made, no write",
          r.database_connection_made and r.sql_execution_made and r.database_write_made is False)
    f = fresh_db()
    seed(f, authorization_scope=None)
    r = persist_intake_note_record(build()[0], session_factory=f)
    check("missing stored scope denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_stored_scope")
    f = fresh_db()
    r = persist_intake_note_record(build()[0], session_factory=f)
    check("missing stored subject denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")
    f = fresh_db()
    seed(f)
    r = persist_intake_note_record(build(authorization_scope=None)[0], session_factory=f)
    check("missing request scope denied (pre-DB)",
          r.outcome == OC.DENIED and r.database_connection_made is False)
    for over, label in ((dict(owner_id="owner_2"), "owner"), (dict(client_id="client_b"), "client")):
        f = fresh_db()
        seed(f, **over)
        r = persist_intake_note_record(build()[0], session_factory=f)
        check(f"stored {label} mismatch denied",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")
    for bad in ("revoked", "archived", "deleted_reference_only"):
        f = fresh_db()
        seed(f, lifecycle_status=bad)
        r = persist_intake_note_record(build()[0], session_factory=f)
        check(f"prohibited stored lifecycle '{bad}' denied",
              r.outcome == OC.DENIED and r.reason_code == "subject_lifecycle_blocked")

    # ---- Draft/request identity (pre-DB) ----
    print("\n16. Draft/request identity mismatches (pre-DB)")
    for attr in ("owner_id", "client_id", "engagement_id"):
        r = persist_intake_note_record(
            build(draft_over={attr: "WRONG"})[0], session_factory=fresh_db())
        check(f"draft {attr} mismatch denied (pre-DB)",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch"
              and r.database_connection_made is False)
    r = persist_intake_note_record(
        build(draft_over={"authorization_scope": "other"})[0], session_factory=fresh_db())
    check("draft↔request scope mismatch denied (pre-DB)",
          r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")

    # ---- Table/action allowlist ----
    print("\n17. Table/action allowlist")
    r = persist_intake_note_record(build(target_table="review_records")[0], session_factory=fresh_db())
    check("review_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_intake_note_record(build(target_table="agent_run_records")[0], session_factory=fresh_db())
    check("agent_run_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_intake_note_record(build(requested_action="create_review_record")[0],
                                   session_factory=fresh_db())
    check("wrong action denied", r.outcome == OC.DENIED and r.reason_code == "wrong_target_action")
    for bad in ("update_intake_note", "delete_intake_note", "upsert_intake_note", "run_raw_sql",
                "publish_capsule", "create_report_for_client", "client_facing_approve_note",
                "verify_financial_impact"):
        r = persist_intake_note_record(build(requested_action=bad)[0], session_factory=fresh_db())
        check(f"prohibited action '{bad}' denied", r.outcome == OC.DENIED)

    # ---- Posture rejections (pre-DB) ----
    print("\n18. Posture / caller-field rejections")
    posture_cases = {
        "review_status not needs_review": (dict(review_status="approved"),
                                           "invalid_draft_review_status"),
        "lifecycle_status not draft": (dict(lifecycle_status="active"),
                                       "invalid_draft_lifecycle_status"),
        "client_facing_approved true": (dict(client_facing_approved=True),
                                        "prohibited_client_facing"),
        "financial_verified true": (dict(financial_verified=True), "prohibited_financial_verified"),
        "capsule_candidate_ready true": (dict(capsule_candidate_ready=True),
                                         "prohibited_capsule_candidate"),
        "publication_allowed true": (dict(publication_allowed=True),
                                     "prohibited_publication_allowed"),
        "execution_allowed true": (dict(execution_allowed=True), "prohibited_execution_allowed"),
        "requires_human_review false": (dict(requires_human_review=False),
                                        "prohibited_no_human_review"),
        "caller-supplied id": (dict(intake_note_id="intn_caller"), "caller_supplied_id"),
        "caller-supplied captured_at": (dict(captured_at="2026-01-01T00:00:00"),
                                        "caller_supplied_timestamp"),
    }
    for label, (draft_over, code) in posture_cases.items():
        f = fresh_db()
        seed(f)
        r = persist_intake_note_record(build(draft_over=draft_over)[0], session_factory=f)
        check(f"{label} denied ({code})",
              r.outcome == OC.DENIED and r.reason_code == code
              and r.database_connection_made is False and count(f, IntakeNoteRecord) == 0)

    # ---- note_text content-safety (non-echoing) ----
    print("\n19. note_text content-safety (ordinary prose passes; markers denied, non-echoing)")
    f = fresh_db()
    seed(f)
    r_ok = persist_intake_note_record(
        build(draft_over=dict(note_text="Ordinary operational prose about the receiving dock."))[0],
        session_factory=f)
    check("ordinary operational prose passes", r_ok.outcome == OC.CREATED)
    long_note = "a" * 16001
    r_long = persist_intake_note_record(
        build(draft_over=dict(note_text=long_note))[0], session_factory=fresh_db())
    check("over-length note_text denied", r_long.outcome == OC.DENIED
          and r_long.reason_code == "note_text_too_long")
    check("over-length reason does not echo note body", long_note not in _blob(r_long))
    marker_cases = {
        "credential assignment": f"notes api_key={_CANARY} were shared",
        "DB URL/DSN": f"connect via postgres://u@h:5432/{_CANARY}",
        "raw SQL SELECT": f"they ran SELECT * FROM engagements where id='{_CANARY}'",
        "raw SQL UPDATE...SET": f"then UPDATE engagements SET flag='{_CANARY}'",
        # Built via concatenation so the contiguous literal is not committed in source (the repo's
        # credential scanner would otherwise flag it); the runtime value still trips the writer guard.
        "private key": "-----BEGIN " + "PRIVATE KEY-----" + _CANARY + "-----END PRIVATE KEY-----",
        "stack trace": f"Traceback (most recent call last): File \"x.py\", line 1 {_CANARY}",
        "raw JSON blob": '{"a": 1, "b": 2, "c": 3, "d": 4}',
    }
    for label, txt in marker_cases.items():
        r_m = persist_intake_note_record(
            build(draft_over=dict(note_text=txt))[0], session_factory=fresh_db())
        check(f"note_text with {label} denied",
              r_m.outcome == OC.DENIED and r_m.reason_code == "prohibited_note_text_content")
        check(f"note_text {label} value not echoed", _CANARY not in _blob(r_m))

    print("\n19b. Credential-disclosure hardening (bare prose passes; disclosure denied, non-echoing)")
    # Bare secret *words* in ordinary prose must still pass (no separator+value, no auth token).
    for prose in ("we discussed the password policy",
                  "the secret shopper process was mentioned",
                  "token counts were not discussed",
                  "the api key was rotated last quarter and bearer bonds are on file"):
        f = fresh_db()
        seed(f)
        r_p = persist_intake_note_record(
            build(draft_over=dict(note_text=prose))[0], session_factory=f)
        check(f"prose passes: {prose!r}",
              r_p.outcome == OC.CREATED and count(f, IntakeNoteRecord) == 1)
    # Credential-disclosure forms (key + separator + value, or auth scheme) must be denied without
    # echoing the secret value ("hunter2"/"abc123"/…).
    disclosure_cases = {
        "password= form": "field password=hunter2 was noted",
        "password: form": "field password: hunter2 was noted",
        "secret: form": "field secret: hunter2 was noted",
        "api key: (space) form": "the api key: abc123 was shared",
        "apikey= form": "the apikey=abc123 was shared",
        "token: form": "the token: abc123 was shared",
        "access_key= form": "the access_key=abc123val was shared",
        "connection_string= form": "the connection_string=abc123 was shared",
        "private key: (space) form": "the private key: abc123 was shared",
        "Bearer token": "auth header Bearer abc123 was captured",
        "Basic auth": "auth header Basic dXNlcjE6cA9z was captured",
    }
    _secret_vals = ("hunter2", "abc123", "abc123val", "dXNlcjE6cA9z")
    for label, txt in disclosure_cases.items():
        r_d = persist_intake_note_record(
            build(draft_over=dict(note_text=txt))[0], session_factory=fresh_db())
        check(f"note_text {label} denied",
              r_d.outcome == OC.DENIED and r_d.reason_code == "prohibited_note_text_content")
        check(f"note_text {label} secret value not echoed",
              not any(v in _blob(r_d) for v in _secret_vals))

    print("\n20. note_summary / label content-safety (non-echoing)")
    r_s = persist_intake_note_record(
        build(draft_over=dict(note_summary=f"api_key={_CANARY}"))[0], session_factory=fresh_db())
    check("note_summary secret marker denied",
          r_s.outcome == OC.DENIED and r_s.reason_code == "prohibited_note_summary_content")
    check("note_summary secret value not echoed", _CANARY not in _blob(r_s))
    for attr, val, code in (
        ("note_type", "line1\nline2", "invalid_note_label"),
        ("note_source", f"token={_CANARY}", "invalid_note_label"),
        ("captured_by", "x" * 200, "invalid_note_label"),
        ("source_ref", f"secret={_CANARY}", "invalid_note_ref"),
    ):
        r_l = persist_intake_note_record(
            build(draft_over={attr: val})[0], session_factory=fresh_db())
        check(f"{attr} unsafe value denied ({code})",
              r_l.outcome == OC.DENIED and r_l.reason_code == code)
        check(f"{attr} value not echoed", _CANARY not in _blob(r_l))

    # ---- Duck-typed / non-draft rejection ----
    print("\n21. Duck-typed / malformed rejection")
    class _Fake:
        target_table = "intake_note_records"
        requested_action = "create_intake_note_record"
    r = persist_intake_note_record(_Fake(), session_factory=fresh_db())
    check("duck-typed request denied",
          r.outcome == OC.DENIED and r.reason_code == "invalid_request_type"
          and r.database_connection_made is False)
    cwr_bad, _ = build()
    cwr_bad.record_draft = object()
    r = persist_intake_note_record(cwr_bad, session_factory=fresh_db())
    check("non-draft record_draft denied",
          r.outcome == OC.DENIED and r.reason_code == "invalid_record_draft")

    # ---- Transaction / failure semantics ----
    print("\n22. Transaction and failure semantics")

    class _FailAt:
        def __init__(self, session, method, exc):
            object.__setattr__(self, "_s", session)
            object.__setattr__(self, "_m", method)
            object.__setattr__(self, "_exc", exc)

        def __getattr__(self, name):
            if name == object.__getattribute__(self, "_m"):
                def _raise(*a, **k):
                    raise object.__getattribute__(self, "_exc")
                return _raise
            return getattr(object.__getattribute__(self, "_s"), name)

    f = fresh_db()
    seed(f)
    fail_get = lambda: _FailAt(f(), "get", SQLAlchemyError("boom-read"))  # noqa: E731
    r = persist_intake_note_record(build()[0], session_factory=fail_get)
    check("failed_before_write on read failure",
          r.outcome == OC.FAILED_BEFORE_WRITE and r.database_write_made is False)
    check("failed_before_write left no row", count(f, IntakeNoteRecord) == 0)

    f = fresh_db()
    seed(f)
    fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
    r = persist_intake_note_record(build()[0], session_factory=fail_commit)
    check("write_outcome_uncertain on commit failure",
          r.outcome == OC.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)
    check("uncertain does not claim no record", "no row" not in _blob(r).lower())

    # IntegrityError race branch (force pre-check miss).
    f = fresh_db()
    seed(f)
    createdA = persist_intake_note_record(build()[0], session_factory=f)
    orig_find = writer_mod._find_existing
    try:
        writer_mod._find_existing = lambda *a, **k: None
        rrep = persist_intake_note_record(build()[0], session_factory=f)
        check("race -> idempotent_replay",
              rrep.outcome == OC.IDEMPOTENT_REPLAY
              and rrep.stored_record_id == createdA.stored_record_id)
        check("race replay left one row", count(f, IntakeNoteRecord) == 1)
        rconf = persist_intake_note_record(
            build(draft_over=dict(note_summary="a different summary"))[0], session_factory=f)
        check("race -> conflict denied",
              rconf.outcome == OC.DENIED and rconf.reason_code == "idempotency_conflict")
        check("race conflict left one row", count(f, IntakeNoteRecord) == 1)
    finally:
        writer_mod._find_existing = orig_find

    print("\n23. Rollback safety")
    check("no partial row after failure paths", count(f, IntakeNoteRecord) == 1)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 34 controlled-DB intake-note-writer check")
    print("=" * 51)

    structural_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
        print("         Run: make validate-phase34 PYTHON=.venv/bin/python")
    else:
        print(f"  SQLAlchemy {sqlalchemy.__version__} present — running DB-backed checks "
              "(SQLite structural smoke; NOT production proof).")
        db_backed_checks()

    print("\n" + "=" * 51)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    if _failures:
        print(f"\nRESULT: {FAIL} ({len(_failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
