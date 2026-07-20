#!/usr/bin/env python3
"""Phase 30 controlled-DB review-bundle-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/migration/doc files exist and compile;
  the Phase 29 ``peak/review_orchestration`` package stays DB-free; the writer imports no
  LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential, and no Phase
  22 review writer; the migration is additive schema-only (creates one table, no INSERT/seed,
  down_revision 006); the docs carry the required language; the repo stays source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database — migration upgrade/downgrade/re-upgrade, successful create (safe references only),
  idempotent replay, conflicting replay, DB-backed authorization (stored-scope comparison),
  identity/allowlist checks, posture/content rejections, non-approval posture, side-effect
  discipline (no ``review_records``/``agent_run_records`` write), and transaction/failure
  semantics. Skipped with instructions if SQLAlchemy is absent (still exits 0).

Phase 30 approves nothing, calls no Phase 22 review writer, creates no ``review_records`` or
``agent_run_records`` row, executes no agent, makes no LLM/MockLLM/AgentNet/MCP/resolver/connector/
network call, and performs no client-facing output / financial verification / capsule publication.
It creates exactly one review-gated, not-approved ``review_bundle_records`` row.

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
    "peak/db/review_bundle_writer.py",
    "peak/db/writer_contracts.py",
    "alembic/versions/007_review_bundle_records.py",
    "docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md",
    "docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md",
]
WRITER_FILES = ["peak/db/review_bundle_writer.py", "peak/db/writer_contracts.py"]
PHASE29_FILES = [
    "peak/review_orchestration/__init__.py",
    "peak/review_orchestration/contracts.py",
    "peak/review_orchestration/governance.py",
    "peak/review_orchestration/review_planner.py",
]
COMPILE_FILES = WRITER_FILES + ["alembic/versions/007_review_bundle_records.py"]
DOCS = ["docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md", "docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md"]
REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "review-gated",
    "not-approved",
    "output_status=draft",
    "review_status=needs_review",
    "lifecycle_status=draft",
    "review_records",
    "server-stamped",
    "13 tables",
    "create_review_bundle_record",
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
CONNECTOR_RE = re.compile(
    r"\b(?:agentnet|mcp_connector|mcp|resolver_client|resolver|connector)\b", re.IGNORECASE)
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

    print("\n3. Phase 29 review_orchestration package stays DB-free")
    for rel in PHASE29_FILES:
        hits = [ln for ln in _import_lines(read(rel))
                if DB_IMPORT_RE.search(ln) or PEAK_DB_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n4. Writer imports no LLM/exec/AgentNet/connector/network/review-writer/credential")
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

    print("\n5. Migration is additive, creates one table, schema-only (no INSERT/seed)")
    mig = read("alembic/versions/007_review_bundle_records.py")
    low = mig.lower()
    check("migration has no insert/seed pattern", not any(p in low for p in INSERT_PATTERNS))
    check("migration defines upgrade()", "def upgrade()" in mig)
    check("migration defines downgrade()", "def downgrade()" in mig)
    check("migration creates the table", "op.create_table" in mig)
    check("migration targets review_bundle_records", "review_bundle_records" in mig)
    check("migration adds unique idempotency index", "uq_review_bundle_records_idem" in mig)
    check("migration down_revision is 006_agent_task_queue_records",
          'down_revision = "006_agent_task_queue_records"' in mig)
    check("downgrade drops the table", "op.drop_table" in mig)

    print("\n6. Doc language")
    blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"phrase present: '{phrase}'", phrase.lower() in blob)

    print("\n7. Source-only discipline")
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

_SENTINEL = "SENSITIVE-DO-NOT-LEAK"
_KEY = "idem-rvb-1"


def _make_builders():
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.review_orchestration.contracts import (
        PacketReviewOrchestrationRequest, ReviewBundleDraft, ReviewSubjectReference,
    )

    def subject(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized")
        base.update(over)
        return ControlledWriteSubject(**base)

    def draft(**over):
        base = dict(
            review_bundle_id=None, owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            packet_processing_receipt_ref="pkt_run_1",
            source_ingestion_record_ids=["ing_1"], evidence_reference_ids=["evid_1", "evid_2"],
            agent_task_queue_record_ids=["atq_1"],
            subject_refs=[ReviewSubjectReference(
                subject_ref_id="ing_1", subject_type="source_ingestion_record",
                owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
                authorization_scope="engagement_authorized")],
            reviewer_role="internal_reviewer", review_reason="post-packet review",
            review_scope="engagement_authorized", output_status="draft",
            review_status="needs_review", lifecycle_status="draft", authoritative=False,
            client_facing_approved=False, capsule_candidate_ready=False, financial_verified=False,
            execution_allowed=False, approval_allowed=False, publication_allowed=False,
            requires_human_review=True, reasons=[], warnings=["review plan only"], created_at=None)
        base.update(over)
        return ReviewBundleDraft(**base)

    def rreq(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized", idempotency_key=_KEY,
            requested_action="prepare_packet_review_plan", lifecycle_status="active")
        base.update(over)
        return PacketReviewOrchestrationRequest(**base)

    def build(*, draft_over=None, subject_over=None, **cwr_over):
        d = draft(**(draft_over or {}))
        subj = subject(**(subject_over or {}))
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            target_table="review_bundle_records", requested_action="create_review_bundle_record",
            subject=subj, record_draft=d, source_phase="phase29", lifecycle_status="active",
            idempotency_key=_KEY)
        base.update(cwr_over)
        return ControlledWriteRequest(**base), d, rreq()

    return subject, draft, rreq, build


def _migration_reversibility() -> None:
    from sqlalchemy import create_engine, inspect
    from alembic.config import Config
    from alembic import command

    print("\n8. Migration apply / reversibility (temp SQLite)")
    tmp = tempfile.mkdtemp(prefix="peak_phase30_mig_")
    prev_url = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created review_bundle_records",
              "review_bundle_records" in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns("review_bundle_records")}
        check("table carries posture + idempotency columns",
              {"approval_allowed", "financial_verified", "publication_allowed",
               "requires_human_review", "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"])
               for i in insp.get_indexes("review_bundle_records")}
        check("unique idempotency index over (owner,client,engagement,key)",
              idx.get("uq_review_bundle_records_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        command.downgrade(cfg, "006_agent_task_queue_records")
        check("downgrade drops the table",
              "review_bundle_records" not in inspect(create_engine(url)).get_table_names())
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

    import peak.db.review_bundle_writer as writer_mod
    from peak.db.review_bundle_writer import persist_review_bundle_record
    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, ReviewBundleRecord, ReviewRecord,
    )
    from peak.db.writer_contracts import ReviewBundleWriteOutcome as OC

    _migration_reversibility()

    subject, draft, rreq, build = _make_builders()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase30_")
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
    print("\n9. Successful create (safe references only, not-approved)")
    f = fresh_db()
    seed(f)
    cwr, d, rr = build()
    r = persist_review_bundle_record(cwr, session_factory=f, review_request=rr)
    check("outcome == created", r.outcome == OC.CREATED)
    check("permitted True", r.permitted is True)
    check("exactly one row created", count(f, ReviewBundleRecord) == 1)
    check("server-generated id (rvb_ prefix)",
          bool(r.stored_record_id) and r.stored_record_id.startswith("rvb_"))
    check("receipt created_at present", bool(r.created_at))
    check("receipt posture", r.review_status == "needs_review" and r.output_status == "draft"
          and r.lifecycle_status == "draft")
    check("flags: connection/sql/write/commit/created all True",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.transaction_committed and r.stored_record_created)
    check("flags: existing_record_returned / outcome_uncertain False",
          r.existing_record_returned is False and r.outcome_uncertain is False)
    check("non-effect flags all False",
          r.review_approval_made is False and r.client_facing_output_created is False
          and r.financial_verification_made is False and r.capsule_publication_made is False
          and r.agent_execution_made is False and r.llm_call_made is False
          and r.agentnet_call_made is False and r.resolver_call_made is False
          and r.network_call_made is False)
    s = f()
    row = s.get(ReviewBundleRecord, r.stored_record_id)
    check("stored posture columns safe",
          row.output_status == "draft" and row.review_status == "needs_review"
          and row.lifecycle_status == "draft" and row.authoritative is False
          and row.client_facing_approved is False and row.capsule_candidate_ready is False
          and row.financial_verified is False and row.execution_allowed is False
          and row.approval_allowed is False and row.publication_allowed is False
          and row.requires_human_review is True)
    check("stored reviewer_role / review_scope", row.reviewer_role == "internal_reviewer"
          and row.review_scope == "engagement_authorized")
    check("safe references stored (source/evidence/task ids)",
          row.details_json.get("source_ingestion_record_ids") == ["ing_1"]
          and row.details_json.get("evidence_reference_ids") == ["evid_1", "evid_2"]
          and row.details_json.get("agent_task_queue_record_ids") == ["atq_1"])
    check("subject_refs stored as safe id+type",
          row.details_json.get("subject_refs") == [
              {"subject_ref_id": "ing_1", "subject_type": "source_ingestion_record"}])
    check("NO raw payload/content stored",
          all(k not in row.details_json for k in
              ("packet_payload", "raw_evidence_text", "raw_interview_text", "source_bytes",
               "generated_output", "approval_decision"))
          and not hasattr(row, "packet_payload"))
    check("idempotency_key + payload_fingerprint persisted",
          bool(row.idempotency_key) and bool(row.payload_fingerprint))
    check("created_at server-stamped", row.created_at is not None)
    s.close()

    print("\n10. Side-effect discipline (no review_records / agent_run_records / unrelated)")
    check("NO review_records row created", count(f, ReviewRecord) == 0)
    check("NO agent_run_records row created", count(f, AgentRunRecord) == 0)
    check("clients untouched", count(f, Client) == 0)

    # ---- Idempotent replay ----
    print("\n11. Idempotent replay")
    f = fresh_db()
    seed(f)
    first = persist_review_bundle_record(build()[0], session_factory=f)
    second = persist_review_bundle_record(build()[0], session_factory=f)
    check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
    check("no second row", count(f, ReviewBundleRecord) == 1)
    check("existing id returned", second.stored_record_id == first.stored_record_id)
    check("replay reports no new record",
          second.stored_record_created is False and second.database_write_made is False
          and second.existing_record_returned is True)

    # ---- Conflicting replay ----
    print("\n12. Conflicting replay")
    f = fresh_db()
    seed(f)
    created = persist_review_bundle_record(build()[0], session_factory=f)
    conflict = persist_review_bundle_record(
        build(draft_over=dict(review_reason="a different reason"))[0], session_factory=f)
    check("conflict denied", conflict.outcome == OC.DENIED)
    check("conflict reason idempotency_conflict", conflict.reason_code == "idempotency_conflict")
    check("no new row on conflict", count(f, ReviewBundleRecord) == 1)
    s = f()
    check("existing row unchanged (review_reason)",
          s.get(ReviewBundleRecord, created.stored_record_id).review_reason == "post-packet review")
    s.close()

    # ---- DB-backed authorization ----
    print("\n13. DB-backed authorization (stored-scope comparison)")
    f = fresh_db()
    seed(f, authorization_scope="internal_peak_only")
    r = persist_review_bundle_record(build()[0], session_factory=f)
    check("stored-scope mismatch denied",
          r.outcome == OC.DENIED and r.reason_code == "stored_scope_mismatch")
    check("no row on scope mismatch", count(f, ReviewBundleRecord) == 0)
    check("connection+sql made, no write",
          r.database_connection_made and r.sql_execution_made and r.database_write_made is False)
    f = fresh_db()
    seed(f, authorization_scope=None)
    r = persist_review_bundle_record(build()[0], session_factory=f)
    check("missing stored scope denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_stored_scope")
    f = fresh_db()
    r = persist_review_bundle_record(build()[0], session_factory=f)
    check("missing stored subject denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")
    f = fresh_db()
    seed(f)
    r = persist_review_bundle_record(build(authorization_scope=None)[0], session_factory=f)
    check("missing request scope denied (pre-DB)",
          r.outcome == OC.DENIED and r.database_connection_made is False)
    check("missing request scope: no row", count(f, ReviewBundleRecord) == 0)

    # ---- Stored identity mismatches ----
    print("\n14. Stored identity mismatches")
    for over, label in ((dict(owner_id="owner_2"), "owner"), (dict(client_id="client_b"), "client")):
        f = fresh_db()
        seed(f, **over)
        r = persist_review_bundle_record(build()[0], session_factory=f)
        check(f"stored {label} mismatch denied",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")
    f = fresh_db()
    seed(f, id="eng_other")
    r = persist_review_bundle_record(build()[0], session_factory=f)
    check("stored engagement mismatch (subject absent) denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")

    # ---- Draft/request identity (pre-DB) ----
    print("\n15. Draft/request identity mismatches (pre-DB)")
    for attr in ("owner_id", "client_id", "engagement_id"):
        r = persist_review_bundle_record(
            build(draft_over={attr: "WRONG"})[0], session_factory=fresh_db())
        check(f"draft {attr} mismatch denied (pre-DB)",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch"
              and r.database_connection_made is False)
    r = persist_review_bundle_record(build(authorization_scope="other")[0], session_factory=fresh_db())
    check("request↔subject scope mismatch denied (pre-DB)",
          r.outcome == OC.DENIED and r.database_connection_made is False)

    # ---- Table/action allowlist ----
    print("\n16. Table/action allowlist")
    r = persist_review_bundle_record(build(target_table="review_records")[0], session_factory=fresh_db())
    check("review_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_review_bundle_record(build(target_table="agent_run_records")[0], session_factory=fresh_db())
    check("agent_run_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_review_bundle_record(build(requested_action="create_review_record")[0],
                                     session_factory=fresh_db())
    check("wrong action denied", r.outcome == OC.DENIED and r.reason_code == "wrong_target_action")
    for bad in ("approve_internal_review", "update_review_bundle", "delete_review_bundle",
                "publish_review_bundle", "execute_review", "client_facing_approve_bundle",
                "verify_financial_impact", "run_raw_sql"):
        r = persist_review_bundle_record(build(requested_action=bad)[0], session_factory=fresh_db())
        check(f"prohibited action '{bad}' denied", r.outcome == OC.DENIED)

    # ---- Posture rejections (pre-DB) ----
    print("\n17. Posture rejections")
    posture_cases = {
        "output_status not draft": (dict(output_status="reviewed"), "invalid_draft_output_status"),
        "review_status not needs_review": (dict(review_status="approved_internal"),
                                           "invalid_draft_review_status"),
        "lifecycle_status not draft": (dict(lifecycle_status="active"),
                                       "invalid_draft_lifecycle_status"),
        "authoritative true": (dict(authoritative=True), "prohibited_authoritative"),
        "client_facing_approved true": (dict(client_facing_approved=True),
                                        "prohibited_client_facing"),
        "capsule_candidate_ready true": (dict(capsule_candidate_ready=True),
                                         "prohibited_capsule_candidate"),
        "financial_verified true": (dict(financial_verified=True), "prohibited_financial_verified"),
        "execution_allowed true": (dict(execution_allowed=True), "prohibited_execution_allowed"),
        "approval_allowed true": (dict(approval_allowed=True), "prohibited_approval_allowed"),
        "publication_allowed true": (dict(publication_allowed=True),
                                     "prohibited_publication_allowed"),
        "requires_human_review false": (dict(requires_human_review=False),
                                        "prohibited_no_human_review"),
        "caller-supplied id": (dict(review_bundle_id="rvb_caller"), "caller_supplied_id"),
        "caller-supplied timestamp": (dict(created_at="2026-01-01T00:00:00"),
                                      "caller_supplied_timestamp"),
    }
    for label, (draft_over, code) in posture_cases.items():
        f = fresh_db()
        seed(f)
        r = persist_review_bundle_record(build(draft_over=draft_over)[0], session_factory=f)
        check(f"{label} denied ({code})",
              r.outcome == OC.DENIED and r.reason_code == code
              and r.database_connection_made is False and count(f, ReviewBundleRecord) == 0)

    # ---- Content / decision / secret guard ----
    print("\n18. Content / decision / secret guard (rejected without echoing values)")
    for inj_attr in ("packet_payload", "raw_evidence_text", "raw_interview_text", "source_bytes",
                     "generated_output", "approval_decision", "api_key", "connection_string",
                     "token", "credential"):
        f = fresh_db()
        seed(f)
        cwr, d, rr = build()
        setattr(d, inj_attr, {"x": "y"} if inj_attr.endswith("payload") else _SENTINEL)
        r = persist_review_bundle_record(cwr, session_factory=f, review_request=rr)
        check(f"draft with '{inj_attr}' rejected",
              r.outcome == OC.DENIED and r.reason_code == "prohibited_content"
              and count(f, ReviewBundleRecord) == 0)
        check(f"'{inj_attr}' reason does not echo value", _SENTINEL not in " ".join(r.reasons))

    # ---- Duck-typed rejection ----
    print("\n19. Duck-typed / malformed rejection")
    class _Fake:
        target_table = "review_bundle_records"
        requested_action = "create_review_bundle_record"
    r = persist_review_bundle_record(_Fake(), session_factory=fresh_db())
    check("duck-typed request denied",
          r.outcome == OC.DENIED and r.reason_code == "invalid_request_type"
          and r.database_connection_made is False)

    # ---- Transaction / failure semantics ----
    print("\n20. Transaction and failure semantics")

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
    r = persist_review_bundle_record(build()[0], session_factory=fail_get)
    check("failed_before_write on read failure",
          r.outcome == OC.FAILED_BEFORE_WRITE and r.database_write_made is False)
    check("failed_before_write left no row", count(f, ReviewBundleRecord) == 0)

    f = fresh_db()
    seed(f)
    fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
    r = persist_review_bundle_record(build()[0], session_factory=fail_commit)
    check("write_outcome_uncertain on commit failure",
          r.outcome == OC.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)
    check("uncertain does not claim no record", "no row" not in " ".join(r.reasons).lower())

    # IntegrityError race branch (force pre-check miss).
    f = fresh_db()
    seed(f)
    createdA = persist_review_bundle_record(build()[0], session_factory=f)
    orig_find = writer_mod._find_existing
    try:
        writer_mod._find_existing = lambda *a, **k: None
        rrep = persist_review_bundle_record(build()[0], session_factory=f)
        check("race -> idempotent_replay",
              rrep.outcome == OC.IDEMPOTENT_REPLAY
              and rrep.stored_record_id == createdA.stored_record_id)
        check("race replay left one row", count(f, ReviewBundleRecord) == 1)
        rconf = persist_review_bundle_record(
            build(draft_over=dict(review_reason="race conflict"))[0], session_factory=f)
        check("race -> conflict denied",
              rconf.outcome == OC.DENIED and rconf.reason_code == "idempotency_conflict")
        check("race conflict left one row", count(f, ReviewBundleRecord) == 1)
    finally:
        writer_mod._find_existing = orig_find

    print("\n21. Rollback safety")
    check("no partial row after failure paths", count(f, ReviewBundleRecord) == 1)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 30 controlled-DB review-bundle-writer check")
    print("=" * 52)

    structural_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
        print("         Run: make validate-phase30 PYTHON=.venv/bin/python")
    else:
        print(f"  SQLAlchemy {sqlalchemy.__version__} present — running DB-backed checks.")
        db_backed_checks()

    print("\n" + "=" * 52)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    if _failures:
        print(f"\nRESULT: {FAIL} ({len(_failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
