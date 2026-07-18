#!/usr/bin/env python3
"""Phase 27 controlled-DB agent-task-queue-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/migration/doc files exist and
  compile; the Phase 26 ``peak/task_queue`` package stays DB-free (no SQLAlchemy/Alembic/peak.db
  import); the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network
  client or credential; the migration is additive schema-only (creates one table, no INSERT/
  seed, down_revision 005); the docs carry the required language; the repo stays source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database built from the models — migration upgrade/downgrade/re-upgrade, successful create
  (safe references only), idempotent replay, conflicting replay, DB-backed authorization
  (stored-scope comparison), identity/registry checks, table/action allowlist, posture/content
  rejections, non-execution posture, side-effect discipline (no agent_run_records write), and
  transaction/failure semantics. Skipped with instructions if SQLAlchemy is absent (still
  exits 0).

Phase 27 executes no agent (live or mock), makes no LLM/MockLLM/AgentNet/MCP/resolver/connector/
network call, creates no ``agent_run_records`` row, performs no client-facing approval / financial
verification / capsule publication, and never updates or deletes. It creates exactly one
review-gated, not-executed ``agent_task_queue_records`` row.

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
    "peak/db/agent_task_queue_writer.py",
    "peak/db/writer_contracts.py",
    "alembic/versions/006_agent_task_queue_records.py",
    "docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md",
    "docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md",
]
WRITER_FILES = ["peak/db/agent_task_queue_writer.py", "peak/db/writer_contracts.py"]
# Phase 26 task_queue package must stay DB-free (regression guard).
PHASE26_FILES = [
    "peak/task_queue/__init__.py",
    "peak/task_queue/contracts.py",
    "peak/task_queue/governance.py",
    "peak/task_queue/task_queue_mapper.py",
]
COMPILE_FILES = WRITER_FILES + ["alembic/versions/006_agent_task_queue_records.py"]
DOCS = [
    "docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md",
    "docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md",
]
REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "review-gated",
    "not-executed",
    "execution_status=not_executed",
    "review_status=needs_review",
    "output_status=draft",
    "agent_run_records",
    "create_agent_task_queue_record",
    "server-stamped",
    "12 tables",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b|import\s+\.\.db\b")
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(
    r"\b(?:agentnet|mcp_connector|mcp|resolver_client|resolver|connector)\b", re.IGNORECASE
)
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE,
)
INSERT_PATTERNS = ("insert into", "bulk_insert", ".insert(")
DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def _skip(dirpath: str) -> bool:
    return bool(SKIP_DIRS.intersection(dirpath.split(os.sep)))


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

    print("\n3. Phase 26 task_queue package stays DB-free")
    for rel in PHASE26_FILES:
        hits = [ln for ln in _import_lines(read(rel))
                if DB_IMPORT_RE.search(ln) or PEAK_DB_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n4. Writer imports no LLM/MockLLM/executor/AgentNet/connector/network/credential")
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
        check(f"{rel}: no credential value literal", not CREDENTIAL_RE.search(text))

    print("\n5. Migration is additive, creates one table, schema-only (no INSERT/seed)")
    mig = read("alembic/versions/006_agent_task_queue_records.py")
    low = mig.lower()
    check("migration has no insert/seed pattern", not any(p in low for p in INSERT_PATTERNS))
    check("migration defines upgrade()", "def upgrade()" in mig)
    check("migration defines downgrade()", "def downgrade()" in mig)
    check("migration creates the table", "op.create_table" in mig)
    check("migration targets agent_task_queue_records", "agent_task_queue_records" in mig)
    check("migration adds unique idempotency index", "uq_agent_task_queue_records_idem" in mig)
    check("migration down_revision is 005_source_ingestion_idem",
          'down_revision = "005_source_ingestion_idem"' in mig)
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


def _make_builders():
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.task_queue.contracts import AgentTaskQueueRequest, AgentTaskQueueDraft

    _KEY = "idem-q-1::taskq::0::new_client_intake_agent"

    def subject(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
        )
        base.update(over)
        return ControlledWriteSubject(**base)

    def draft(**over):
        base = dict(
            agent_task_queue_record_id=None, owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", agent_name="new_client_intake_agent", workflow="intake",
            task_type="intake", requested_action="normalize", task_input_ref=["rec_1"],
            task_input_summary="1 input record id(s)", source_ingestion_record_id="ing_1",
            evidence_reference_ids=["evid_1", "evid_2"], packet_processing_run_ref="pkt_run_1",
            orchestration_ref="orch_1", prompt_contract_path="prompts/intake/x.prompt.md",
            authorization_scope="engagement_authorized", idempotency_key=_KEY,
            readiness_state="queued_for_review", output_status="draft",
            review_status="needs_review", lifecycle_status="draft", authoritative=False,
            client_facing_approved=False, capsule_candidate_ready=False,
            execution_status="not_executed", execution_allowed=False,
            llm_execution_allowed=False, agentnet_context_allowed=False,
            resolver_context_allowed=False, network_allowed=False, requires_human_review=True,
            reasons=[], warnings=["queue plan only"], created_at=None,
        )
        base.update(over)
        return AgentTaskQueueDraft(**base)

    def qreq(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized", idempotency_key="idem-q-1",
            agent_task_requests=[], requested_action="prepare_agent_task_queue_plan",
            lifecycle_status="active",
        )
        base.update(over)
        return AgentTaskQueueRequest(**base)

    def build(*, draft_over=None, subject_over=None, **cwr_over):
        d = draft(**(draft_over or {}))
        subj = subject(**(subject_over or {}))
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            target_table="agent_task_queue_records",
            requested_action="create_agent_task_queue_record",
            subject=subj, record_draft=d, source_phase="phase26", lifecycle_status="active",
            idempotency_key=_KEY,
        )
        base.update(cwr_over)
        cwr = ControlledWriteRequest(**base)
        return cwr, d, qreq()

    return subject, draft, qreq, build


def _migration_reversibility() -> None:
    """Apply upgrade -> downgrade -> re-upgrade against a temp SQLite DB (no production DB)."""
    from sqlalchemy import create_engine, inspect
    from alembic.config import Config
    from alembic import command

    print("\n8. Migration apply / reversibility (temp SQLite)")
    tmp = tempfile.mkdtemp(prefix="peak_phase27_mig_")
    prev_url = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created agent_task_queue_records",
              "agent_task_queue_records" in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns("agent_task_queue_records")}
        check("table carries posture + idempotency columns",
              {"readiness_state", "execution_status", "execution_allowed", "requires_human_review",
               "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"])
               for i in insp.get_indexes("agent_task_queue_records")}
        check("unique idempotency index over (owner,client,engagement,key)",
              idx.get("uq_agent_task_queue_records_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        command.downgrade(cfg, "005_source_ingestion_idem")
        check("downgrade drops the table",
              "agent_task_queue_records" not in inspect(create_engine(url)).get_table_names())
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

    import peak.db.agent_task_queue_writer as writer_mod
    from peak.db.agent_task_queue_writer import persist_agent_task_queue_record
    from peak.db.base import Base
    from peak.db.models import AgentRunRecord, AgentTaskQueueRecord, Client, Engagement
    from peak.db.writer_contracts import AgentTaskQueueWriteOutcome as OC

    _migration_reversibility()

    subject, draft, qreq, build = _make_builders()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase27_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    def seed_engagement(factory, **over):
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
    print("\n9. Successful create (safe references only, not-executed)")
    f = fresh_db()
    seed_engagement(f)
    cwr, d, q = build()
    r = persist_agent_task_queue_record(cwr, session_factory=f, readiness_request=q)
    check("outcome == created", r.outcome == OC.CREATED)
    check("permitted True", r.permitted is True)
    check("exactly one row created", count(f, AgentTaskQueueRecord) == 1)
    check("server-generated id (atq_ prefix)",
          bool(r.stored_record_id) and r.stored_record_id.startswith("atq_"))
    check("receipt created_at present", bool(r.created_at))
    check("receipt review/output/execution posture",
          r.review_status == "needs_review" and r.output_status == "draft"
          and r.execution_status == "not_executed")
    check("receipt readiness_state carried", r.readiness_state == "queued_for_review")
    check("flags: connection/sql/write/commit/created all True",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.transaction_committed and r.stored_record_created)
    check("flags: existing_record_returned / outcome_uncertain False",
          r.existing_record_returned is False and r.outcome_uncertain is False)
    s = f()
    row = s.get(AgentTaskQueueRecord, r.stored_record_id)
    check("stored review_status needs_review", row.review_status == "needs_review")
    check("stored output_status draft", row.output_status == "draft")
    check("stored lifecycle_status draft (mirrors Phase 26)", row.lifecycle_status == "draft")
    check("stored execution_status not_executed", row.execution_status == "not_executed")
    check("stored readiness_state queued_for_review", row.readiness_state == "queued_for_review")
    check("stored agent_name", row.agent_name == "new_client_intake_agent")
    check("stored task_type/requested_action", row.task_type == "intake"
          and row.requested_action == "normalize")
    check("stored source_ingestion_record_id", row.source_ingestion_record_id == "ing_1")
    check("stored authorization_scope == request scope",
          row.authorization_scope == "engagement_authorized")
    check("stored all posture booleans safe",
          row.authoritative is False and row.client_facing_approved is False
          and row.capsule_candidate_ready is False and row.execution_allowed is False
          and row.llm_execution_allowed is False and row.agentnet_context_allowed is False
          and row.resolver_context_allowed is False and row.network_allowed is False
          and row.requires_human_review is True)
    check("evidence_reference_ids stored as safe id list",
          row.details_json.get("evidence_reference_ids") == ["evid_1", "evid_2"])
    check("safe_input_summary + refs stored",
          row.details_json.get("safe_input_summary") == "1 input record id(s)"
          and row.details_json.get("packet_processing_run_ref") == "pkt_run_1"
          and row.details_json.get("orchestration_ref") == "orch_1")
    check("NO raw payload/content stored",
          all(k not in row.details_json for k in
              ("packet_payload", "raw_packet_content", "raw_evidence_text", "raw_interview_text",
               "source_bytes"))
          and not hasattr(row, "packet_payload"))
    check("idempotency_key + payload_fingerprint persisted",
          bool(row.idempotency_key) and bool(row.payload_fingerprint))
    check("created_at server-stamped", row.created_at is not None)
    s.close()

    print("\n10. Side-effect discipline (no agent_run_records / unrelated writes)")
    check("agent_run_records untouched (no run created)", count(f, AgentRunRecord) == 0)
    check("clients untouched", count(f, Client) == 0)

    # ---- Idempotent replay ----
    print("\n11. Idempotent replay")
    f = fresh_db()
    seed_engagement(f)
    cwr1, _, q1 = build()
    first = persist_agent_task_queue_record(cwr1, session_factory=f, readiness_request=q1)
    cwr2, _, q2 = build()
    second = persist_agent_task_queue_record(cwr2, session_factory=f, readiness_request=q2)
    check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
    check("no second row", count(f, AgentTaskQueueRecord) == 1)
    check("existing id returned", second.stored_record_id == first.stored_record_id)
    check("replay reports no new record",
          second.stored_record_created is False and second.database_write_made is False
          and second.existing_record_returned is True)

    # ---- Conflicting replay ----
    print("\n12. Conflicting replay")
    f = fresh_db()
    seed_engagement(f)
    cwrA, _, qA = build()
    created = persist_agent_task_queue_record(cwrA, session_factory=f, readiness_request=qA)
    cwrB, _, qB = build(draft_over=dict(requested_action="different_action"))
    conflict = persist_agent_task_queue_record(cwrB, session_factory=f, readiness_request=qB)
    check("conflict denied", conflict.outcome == OC.DENIED)
    check("conflict reason idempotency_conflict", conflict.reason_code == "idempotency_conflict")
    check("no new row on conflict", count(f, AgentTaskQueueRecord) == 1)
    s = f()
    row = s.get(AgentTaskQueueRecord, created.stored_record_id)
    check("existing row unchanged (requested_action)", row.requested_action == "normalize")
    s.close()

    # ---- DB-backed authorization ----
    print("\n13. DB-backed authorization (stored-scope comparison)")
    f = fresh_db()
    seed_engagement(f, authorization_scope="internal_peak_only")
    cwr, _, q = build()
    r = persist_agent_task_queue_record(cwr, session_factory=f, readiness_request=q)
    check("stored-scope mismatch denied",
          r.outcome == OC.DENIED and r.reason_code == "stored_scope_mismatch")
    check("no row on scope mismatch", count(f, AgentTaskQueueRecord) == 0)
    check("connection+sql made, no write",
          r.database_connection_made and r.sql_execution_made and r.database_write_made is False)
    f = fresh_db()
    seed_engagement(f, authorization_scope=None)
    r = persist_agent_task_queue_record(build()[0], session_factory=f)
    check("missing stored scope denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_stored_scope")
    f = fresh_db()
    r = persist_agent_task_queue_record(build()[0], session_factory=f)
    check("missing stored subject denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")
    f = fresh_db()
    seed_engagement(f)
    r = persist_agent_task_queue_record(build(authorization_scope=None)[0], session_factory=f)
    check("missing request scope denied (pre-DB)",
          r.outcome == OC.DENIED and r.database_connection_made is False)
    check("missing request scope: no row", count(f, AgentTaskQueueRecord) == 0)

    # ---- Stored identity mismatches ----
    print("\n14. Stored identity mismatches")
    for over, label in ((dict(owner_id="owner_2"), "owner"), (dict(client_id="client_b"), "client")):
        f = fresh_db()
        seed_engagement(f, **over)
        r = persist_agent_task_queue_record(build()[0], session_factory=f)
        check(f"stored {label} mismatch denied",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")
    f = fresh_db()
    seed_engagement(f, id="eng_other")  # eng_x subject absent
    r = persist_agent_task_queue_record(build()[0], session_factory=f)
    check("stored engagement mismatch (subject absent) denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")

    # ---- Draft/request identity + registry (pre-DB) ----
    print("\n15. Draft/request identity + registry gate (pre-DB)")
    for attr in ("owner_id", "client_id", "engagement_id"):
        r = persist_agent_task_queue_record(
            build(draft_over={attr: "WRONG"})[0], session_factory=fresh_db())
        check(f"draft {attr} mismatch denied (pre-DB)",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch"
              and r.database_connection_made is False)
    r = persist_agent_task_queue_record(
        build(draft_over=dict(authorization_scope="internal_peak_only"))[0],
        session_factory=fresh_db())
    check("draft scope mismatch denied (pre-DB)",
          r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")
    r = persist_agent_task_queue_record(
        build(draft_over=dict(agent_name=None))[0], session_factory=fresh_db())
    check("missing agent_name denied", r.outcome == OC.DENIED
          and r.reason_code == "missing_agent_name")
    r = persist_agent_task_queue_record(
        build(draft_over=dict(agent_name="nonexistent_agent"))[0], session_factory=fresh_db())
    check("unknown agent denied", r.outcome == OC.DENIED and r.reason_code == "unknown_agent")
    r = persist_agent_task_queue_record(
        build(draft_over=dict(task_type=None, requested_action=None))[0],
        session_factory=fresh_db())
    check("missing task_type + requested_action denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_task_type")

    # ---- Table/action allowlist ----
    print("\n16. Table/action allowlist")
    r = persist_agent_task_queue_record(
        build(target_table="agent_run_records")[0], session_factory=fresh_db())
    check("agent_run_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_agent_task_queue_record(
        build(requested_action="create_agent_run_record")[0], session_factory=fresh_db())
    check("wrong action denied", r.outcome == OC.DENIED and r.reason_code == "wrong_target_action")
    for bad in ("delete_agent_task_queue_record", "update_agent_task_queue_record",
                "publish_capsule", "execute_agent_task", "client_facing_approve_record",
                "verify_financial_impact", "run_raw_sql"):
        r = persist_agent_task_queue_record(
            build(requested_action=bad)[0], session_factory=fresh_db())
        check(f"prohibited action '{bad}' denied", r.outcome == OC.DENIED)

    # ---- Posture rejections (pre-DB) ----
    print("\n17. Posture rejections")
    posture_cases = {
        "output_status not draft": (dict(output_status="reviewed"), "invalid_draft_output_status"),
        "review_status not needs_review": (dict(review_status="approved_internal"),
                                           "invalid_draft_review_status"),
        "lifecycle_status not draft": (dict(lifecycle_status="active"),
                                       "invalid_draft_lifecycle_status"),
        "execution_status not not_executed": (dict(execution_status="executed"),
                                              "invalid_execution_status"),
        "authoritative true": (dict(authoritative=True), "prohibited_authoritative"),
        "client_facing_approved true": (dict(client_facing_approved=True),
                                        "prohibited_client_facing"),
        "capsule_candidate_ready true": (dict(capsule_candidate_ready=True),
                                         "prohibited_capsule_candidate"),
        "execution_allowed true": (dict(execution_allowed=True), "prohibited_execution_allowed"),
        "llm_execution_allowed true": (dict(llm_execution_allowed=True),
                                       "prohibited_llm_execution"),
        "agentnet_context_allowed true": (dict(agentnet_context_allowed=True),
                                          "prohibited_agentnet_context"),
        "resolver_context_allowed true": (dict(resolver_context_allowed=True),
                                          "prohibited_resolver_context"),
        "network_allowed true": (dict(network_allowed=True), "prohibited_network"),
        "requires_human_review false": (dict(requires_human_review=False),
                                        "prohibited_no_human_review"),
        "caller-supplied id": (dict(agent_task_queue_record_id="atq_caller"),
                               "caller_supplied_id"),
        "caller-supplied timestamp": (dict(created_at="2026-01-01T00:00:00"),
                                      "caller_supplied_timestamp"),
        "missing readiness_state": (dict(readiness_state=None), "missing_readiness_state"),
        "blocked readiness_state": (dict(readiness_state="blocked_invalid_scope"),
                                    "non_persistable_readiness_state"),
    }
    for label, (draft_over, code) in posture_cases.items():
        f = fresh_db()
        seed_engagement(f)
        r = persist_agent_task_queue_record(
            build(draft_over=draft_over)[0], session_factory=f)
        check(f"{label} denied ({code})",
              r.outcome == OC.DENIED and r.reason_code == code
              and r.database_connection_made is False and count(f, AgentTaskQueueRecord) == 0)

    # ---- Content / secret guard ----
    print("\n18. Content / secret guard (rejected without echoing values)")
    for inj_attr in ("packet_payload", "raw_packet_content", "raw_evidence_text",
                     "raw_interview_text", "source_bytes", "api_key", "connection_string",
                     "token"):
        f = fresh_db()
        seed_engagement(f)
        cwr, d, q = build()
        setattr(d, inj_attr, {"x": "y"} if inj_attr.endswith("payload") else _SENTINEL)
        r = persist_agent_task_queue_record(cwr, session_factory=f, readiness_request=q)
        check(f"draft with '{inj_attr}' rejected",
              r.outcome == OC.DENIED and r.reason_code == "prohibited_content"
              and count(f, AgentTaskQueueRecord) == 0)
        check(f"'{inj_attr}' reason does not echo value", _SENTINEL not in " ".join(r.reasons))

    # ---- Duck-typed rejection ----
    print("\n19. Duck-typed / malformed rejection")
    class _Fake:
        target_table = "agent_task_queue_records"
        requested_action = "create_agent_task_queue_record"
    r = persist_agent_task_queue_record(_Fake(), session_factory=fresh_db())
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
    seed_engagement(f)
    fail_get = lambda: _FailAt(f(), "get", SQLAlchemyError("boom-read"))  # noqa: E731
    r = persist_agent_task_queue_record(build()[0], session_factory=fail_get)
    check("failed_before_write on read failure",
          r.outcome == OC.FAILED_BEFORE_WRITE and r.database_write_made is False)
    check("failed_before_write left no row", count(f, AgentTaskQueueRecord) == 0)

    f = fresh_db()
    seed_engagement(f)
    fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
    r = persist_agent_task_queue_record(build()[0], session_factory=fail_commit)
    check("write_outcome_uncertain on commit failure",
          r.outcome == OC.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)
    check("uncertain does not claim no record", "no row" not in " ".join(r.reasons).lower())

    # IntegrityError race branch (force pre-check miss).
    f = fresh_db()
    seed_engagement(f)
    createdA = persist_agent_task_queue_record(build()[0], session_factory=f)
    orig_find = writer_mod._find_existing
    try:
        writer_mod._find_existing = lambda *a, **k: None
        rrep = persist_agent_task_queue_record(build()[0], session_factory=f)
        check("race -> idempotent_replay",
              rrep.outcome == OC.IDEMPOTENT_REPLAY
              and rrep.stored_record_id == createdA.stored_record_id)
        check("race replay left one row", count(f, AgentTaskQueueRecord) == 1)
        rconf = persist_agent_task_queue_record(
            build(draft_over=dict(requested_action="race_conflict"))[0], session_factory=f)
        check("race -> conflict denied",
              rconf.outcome == OC.DENIED and rconf.reason_code == "idempotency_conflict")
        check("race conflict left one row", count(f, AgentTaskQueueRecord) == 1)
    finally:
        writer_mod._find_existing = orig_find

    print("\n21. Rollback safety")
    check("no partial row after failure paths", count(f, AgentTaskQueueRecord) == 1)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 27 controlled-DB agent-task-queue-writer check")
    print("=" * 52)

    structural_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
        print("         Run: make validate-phase27 PYTHON=.venv/bin/python")
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
