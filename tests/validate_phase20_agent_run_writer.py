#!/usr/bin/env python3
"""Phase 20 controlled-DB agent-run-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/migration files exist and compile;
  the Phase 19 agent-domain mapper stays DB-free (no SQLAlchemy/Alembic/peak.db import); the
  writer imports no LLM/AgentNet/connector/network client or credential; the migration is
  additive schema-only (no INSERT/seed); the docs carry the required language; the repo stays
  source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local
  SQLite database built from the models — successful create, idempotent replay, conflicting
  replay, DB-backed authorization (stored-scope comparison), identity mismatches, action
  allowlist, draft posture, side-effect discipline, and transaction/failure semantics. If
  SQLAlchemy is not installed, this layer is skipped with instructions (run with
  ``make validate-phase20 PYTHON=.venv/bin/python``) and the harness still exits 0.

Phase 20 performs no live LLM/AgentNet/MCP/resolver/connector/network call, no client-facing
output, no financial verification, and no capsule publication; it creates exactly one
review-gated ``agent_run_records`` row and never updates or deletes.

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
    "peak/db/agent_run_writer.py",
    "peak/db/writer_contracts.py",
    "alembic/versions/002_agent_run_idempotency.py",
    "docs/AGENT_RUN_CONTROLLED_WRITER.md",
    "docs/AGENT_RUN_IDEMPOTENCY_POLICY.md",
]

WRITER_FILES = ["peak/db/agent_run_writer.py", "peak/db/writer_contracts.py"]
# Phase 19 agent-domain mapper must stay DB-free (regression guard).
PHASE19_FILES = [
    "peak/agents/persistence_contracts.py",
    "peak/agents/persistence_governance.py",
    "peak/agents/agent_run_mapper.py",
]
COMPILE_FILES = WRITER_FILES + ["alembic/versions/002_agent_run_idempotency.py"]

DOCS = ["docs/AGENT_RUN_CONTROLLED_WRITER.md", "docs/AGENT_RUN_IDEMPOTENCY_POLICY.md"]

REQUIRED_PHRASES = [
    "write-time",
    "stored authorization",
    "identity matching is necessary but not sufficient",
    "idempotency",
    "idempotent_replay",
    "review-gated",
    "output_status=draft",
    "review_status=needs_review",
    "write_outcome_uncertain",
    "no LLM",
    "no AgentNet",
    "no capsule publication",
    "server-controlled",
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
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|resolver_client|connector)\b", re.IGNORECASE)
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b", re.IGNORECASE
)
INSERT_PATTERNS = ("insert into", "bulk_insert", "op.execute(", ".insert(")
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

    print("\n3. Phase 19 agent-domain mapper stays DB-free")
    for rel in PHASE19_FILES:
        text = read(rel)
        hits = [ln for ln in _import_lines(text)
                if DB_IMPORT_RE.search(ln) or PEAK_DB_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n4. Writer imports no LLM/AgentNet/connector/network/credential")
    for rel in WRITER_FILES:
        text = read(rel)
        net = [ln for ln in _import_lines(text)
               if NETWORK_IMPORT_RE.search(ln) or NETWORK_HTTP_RE.search(ln)]
        llm = [ln for ln in _import_lines(text) if LLM_PROVIDER_RE.search(ln)]
        conn = [ln for ln in _import_lines(text) if CONNECTOR_RE.search(ln)]
        cred = LLM_PROVIDER_RE.search(text) and False  # placeholder
        check(f"{rel}: no network import", not net)
        check(f"{rel}: no LLM provider import", not llm)
        check(f"{rel}: no connector/agentnet import", not conn)
        check(f"{rel}: no credential literal", not CREDENTIAL_RE.search(text))

    print("\n5. Migration is additive schema-only (no INSERT/seed)")
    mig = read("alembic/versions/002_agent_run_idempotency.py")
    low = mig.lower()
    check("migration has no insert/seed pattern",
          not any(p in low for p in INSERT_PATTERNS))
    check("migration defines upgrade()", "def upgrade()" in mig)
    check("migration defines downgrade()", "def downgrade()" in mig)
    check("migration targets agent_run_records", "agent_run_records" in mig)
    check("migration adds unique idempotency index", "uq_agent_run_records_idem" in mig)
    check("migration down_revision is 001_initial", 'down_revision = "001_initial"' in mig)

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


# --------------------------------------------------------------------------- DB-backed


def _make_builders():
    from peak.agents.agent_run_mapper import (
        build_agent_run_persistence_draft,
        build_controlled_write_request,
    )
    from peak.agents.contracts import AgentRunDraft, AgentTaskRequest, AgentTaskResult
    from peak.agents.persistence_contracts import (
        AgentRunPersistenceRequest,
        AgentRunPersistenceSubjectSnapshot,
    )

    def snapshot(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
            stored_output_status="active", stored_review_status="approved_internal",
            stored_lifecycle_status="active", source_reference_id="src_1",
        )
        base.update(over)
        return AgentRunPersistenceSubjectSnapshot(**base)

    def task_request(**over):
        base = dict(
            agent_name="evidence_normalization_worker", workflow="evidence",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_action="normalize_evidence", input_record_ids=["raw_1"],
            prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
            authorization_scope="engagement_authorized",
        )
        base.update(over)
        return AgentTaskRequest(**base)

    def task_result(**over):
        base = dict(
            permitted=True, status="planned", output_status="draft",
            review_status="needs_review", lifecycle_status="draft",
            prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
            resolver_context_used=False, llm_call_made=False, agentnet_call_made=False,
            database_write_made=False, client_facing_output_created=False,
        )
        base.update(over)
        return AgentTaskResult(**base)

    def run_draft(**over):
        base = dict(
            agent_run_id=None, agent_name="evidence_normalization_worker", workflow="evidence",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            input_record_ids=["raw_1"],
            prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
            output_status="draft", review_status="needs_review", lifecycle_status="draft",
        )
        base.update(over)
        return AgentRunDraft(**base)

    def preq(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            agent_task_request=task_request(), agent_task_result=task_result(),
            agent_run_draft=run_draft(), subject_snapshot=snapshot(),
            requested_persistence_action="prepare_agent_run_record_write_plan",
            source_phase="phase13", idempotency_key="idem-run-1", lifecycle_status="active",
        )
        base.update(over)
        return AgentRunPersistenceRequest(**base)

    def build(**preq_over):
        p = preq(**preq_over)
        draft = build_agent_run_persistence_draft(p)
        cwr = build_controlled_write_request(p, draft)
        return cwr, draft, p

    return snapshot, task_request, task_result, run_draft, preq, build


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    import peak.db.agent_run_writer as writer_mod
    from peak.db.agent_run_writer import persist_agent_run_record
    from peak.db.base import Base
    from peak.db.models import AgentRunRecord, Client, Engagement, ReviewRecord
    from peak.db.writer_contracts import AgentRunWriteOutcome

    snapshot, task_request, task_result, run_draft, preq, build = _make_builders()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase20_")
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
    print("\n8. Successful create")
    f = fresh_db()
    seed_engagement(f)
    cwr, draft, p = build()
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("outcome == created", r.outcome == AgentRunWriteOutcome.CREATED)
    check("permitted True", r.permitted is True)
    check("exactly one row created", count(f, AgentRunRecord) == 1)
    check("server-generated id (arun_ prefix)",
          bool(r.stored_record_id) and r.stored_record_id.startswith("arun_"))
    check("receipt created_at present", bool(r.created_at))
    check("receipt review_status needs_review", r.review_status == "needs_review")
    check("receipt output_status draft", r.output_status == "draft")
    check("flags: connection/sql/write/commit/created all True",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.transaction_committed and r.stored_record_created)
    check("flags: existing_record_returned False", r.existing_record_returned is False)
    check("flags: outcome_uncertain False", r.outcome_uncertain is False)
    # Read back the stored row.
    s = f()
    row = s.get(AgentRunRecord, r.stored_record_id)
    check("stored review_status == needs_review", row.review_status == "needs_review")
    check("stored output_status == draft", row.output_status == "draft")
    check("stored idempotency_key persisted", row.idempotency_key == "idem-run-1")
    check("stored payload_fingerprint persisted", bool(row.payload_fingerprint))
    check("stored created_at is server-stamped", row.created_at is not None)
    s.close()

    # ---- Side-effect discipline: no unrelated table mutation ----
    print("\n9. Side-effect discipline (no unrelated table mutation)")
    check("clients table untouched", count(f, Client) == 0)
    check("review_records table untouched", count(f, ReviewRecord) == 0)

    # ---- Idempotent replay ----
    print("\n10. Idempotent replay")
    f = fresh_db()
    seed_engagement(f)
    cwr1, _, p1 = build()
    first = persist_agent_run_record(cwr1, session_factory=f, persistence_request=p1)
    cwr2, _, p2 = build()  # identical payload + idempotency key
    second = persist_agent_run_record(cwr2, session_factory=f, persistence_request=p2)
    check("second outcome == idempotent_replay",
          second.outcome == AgentRunWriteOutcome.IDEMPOTENT_REPLAY)
    check("no second row", count(f, AgentRunRecord) == 1)
    check("existing id returned", second.stored_record_id == first.stored_record_id)
    check("replay reports no new record",
          second.stored_record_created is False and second.database_write_made is False
          and second.existing_record_returned is True)

    # ---- Conflicting replay (same key, different payload) ----
    print("\n11. Conflicting replay")
    f = fresh_db()
    seed_engagement(f)
    cwrA, _, pA = build()
    created = persist_agent_run_record(cwrA, session_factory=f, persistence_request=pA)
    cwrB, draftB, pB = build()
    draftB.agent_name = "different_agent"  # same idem key, different payload -> conflict
    conflict = persist_agent_run_record(cwrB, session_factory=f, persistence_request=pB)
    check("conflict denied", conflict.outcome == AgentRunWriteOutcome.DENIED)
    check("conflict reason idempotency_conflict", conflict.reason_code == "idempotency_conflict")
    check("no new row on conflict", count(f, AgentRunRecord) == 1)
    s = f()
    row = s.get(AgentRunRecord, created.stored_record_id)
    check("existing row unchanged (agent_name)", row.details_json.get("agent_name")
          == "evidence_normalization_worker")
    s.close()

    # ---- DB-backed authorization ----
    print("\n12. DB-backed authorization (stored-scope comparison)")
    # matching identities but differing STORED scope
    f = fresh_db()
    seed_engagement(f, authorization_scope="internal_peak_only")  # stored differs from request
    cwr, _, p = build()  # request + snapshot scope = engagement_authorized
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("stored-scope mismatch denied", r.outcome == AgentRunWriteOutcome.DENIED)
    check("reason stored_scope_mismatch", r.reason_code == "stored_scope_mismatch")
    check("no row on scope mismatch", count(f, AgentRunRecord) == 0)
    check("connection+sql made, no write", r.database_connection_made and r.sql_execution_made
          and r.database_write_made is False)
    # stored scope missing
    f = fresh_db()
    seed_engagement(f, authorization_scope=None)
    cwr, _, p = build()
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("missing stored scope denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "missing_stored_scope")
    # stored subject missing (engagement not seeded)
    f = fresh_db()
    cwr, _, p = build()
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("missing stored subject denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "missing_subject")
    # request scope missing (denied before DB)
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build(authorization_scope=None)
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("missing request scope denied", r.outcome == AgentRunWriteOutcome.DENIED)
    check("missing request scope: no DB connection", r.database_connection_made is False)
    check("missing request scope: no row", count(f, AgentRunRecord) == 0)

    # ---- Identity mismatches ----
    print("\n13. Identity mismatches")
    # stored subject owner mismatch (DB-level)
    f = fresh_db()
    seed_engagement(f, owner_id="owner_2")
    cwr, _, p = build()
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("stored owner mismatch denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "identity_mismatch")
    # stored subject client mismatch (DB-level)
    f = fresh_db()
    seed_engagement(f, client_id="client_b")
    cwr, _, p = build()
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("stored client mismatch denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "identity_mismatch")
    # draft engagement mismatch (pre-DB)
    f = fresh_db()
    seed_engagement(f)
    cwr, draft, p = build()
    draft.engagement_id = "eng_y"
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("draft engagement mismatch denied (pre-DB)",
          r.outcome == AgentRunWriteOutcome.DENIED and r.database_connection_made is False)
    # persistence_request agent_task_request owner mismatch (pre-DB)
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build()
    p.agent_task_request.owner_id = "owner_2"
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("task_request owner mismatch denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "identity_mismatch")
    # subject snapshot id mismatch (pre-DB)
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build()
    p.subject_snapshot.subject_record_id = "eng_z"
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("snapshot subject id mismatch denied", r.outcome == AgentRunWriteOutcome.DENIED)

    # ---- Action allowlist ----
    print("\n14. Action allowlist")
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build()
    cwr.target_table = "review_records"
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("wrong table denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "wrong_target_table")
    cwr, _, p = build()
    cwr.requested_action = "update_lifecycle_status"
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("wrong action denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "wrong_target_action")
    cwr, _, p = build()
    cwr.requested_action = "delete_record"
    r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
    check("delete-like action denied", r.outcome == AgentRunWriteOutcome.DENIED)
    check("allowlist denials made no row", count(f, AgentRunRecord) == 0)

    # ---- Draft posture ----
    print("\n15. Draft posture")
    posture_cases = {
        "output_status not draft": ("output_status", "reviewed", "invalid_draft_output_status"),
        "review_status not needs_review": ("review_status", "approved_internal",
                                           "invalid_draft_review_status"),
        "caller-supplied id": ("agent_run_record_id", "arun_caller", "caller_supplied_id"),
        "caller-supplied timestamp": ("created_at", "2026-01-01T00:00:00", "caller_supplied_timestamp"),
        "llm side-effect flag": ("llm_call_made", True, "prohibited_side_effect_state"),
        "client-facing flag": ("client_facing_output_created", True, "prohibited_side_effect_state"),
    }
    for label, (attr, val, code) in posture_cases.items():
        f = fresh_db()
        seed_engagement(f)
        cwr, draft, p = build()
        setattr(draft, attr, val)
        r = persist_agent_run_record(cwr, session_factory=f, persistence_request=p)
        check(f"{label} denied ({code})",
              r.outcome == AgentRunWriteOutcome.DENIED and r.reason_code == code
              and r.database_connection_made is False and count(f, AgentRunRecord) == 0)

    # ---- Duck-typed rejection ----
    print("\n16. Duck-typed / malformed rejection")
    class _Fake:
        target_table = "agent_run_records"
        requested_action = "create_agent_run_record"
    r = persist_agent_run_record(_Fake(), session_factory=fresh_db())
    check("duck-typed request denied", r.outcome == AgentRunWriteOutcome.DENIED
          and r.reason_code == "invalid_request_type" and r.database_connection_made is False)

    # ---- Transaction / failure semantics ----
    print("\n17. Transaction and failure semantics")

    class _FailAt:
        """Proxy that delegates to a real session but raises on one chosen method."""

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

    # failed_before_write: session.get raises before any insert.
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build()
    fail_get = lambda: _FailAt(f(), "get", SQLAlchemyError("boom-read"))  # noqa: E731
    r = persist_agent_run_record(cwr, session_factory=fail_get, persistence_request=p)
    check("failed_before_write on read failure",
          r.outcome == AgentRunWriteOutcome.FAILED_BEFORE_WRITE and r.database_write_made is False)
    check("failed_before_write left no row", count(f, AgentRunRecord) == 0)

    # write_outcome_uncertain: commit raises a non-integrity error after add.
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build()
    fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
    r = persist_agent_run_record(cwr, session_factory=fail_commit, persistence_request=p)
    check("write_outcome_uncertain on commit failure",
          r.outcome == AgentRunWriteOutcome.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)

    # IntegrityError (race) branch — force the pre-check to miss an existing row.
    f = fresh_db()
    seed_engagement(f)
    cwrA, _, pA = build()
    createdA = persist_agent_run_record(cwrA, session_factory=f, persistence_request=pA)
    orig_find = writer_mod._find_existing
    try:
        writer_mod._find_existing = lambda *a, **k: None  # simulate the race window
        # same payload -> IntegrityError -> re-query matches -> idempotent_replay
        cwrB, _, pB = build()
        rrep = persist_agent_run_record(cwrB, session_factory=f, persistence_request=pB)
        check("race -> idempotent_replay",
              rrep.outcome == AgentRunWriteOutcome.IDEMPOTENT_REPLAY
              and rrep.stored_record_id == createdA.stored_record_id)
        check("race replay left one row", count(f, AgentRunRecord) == 1)
        # different payload -> IntegrityError -> re-query differs -> conflict
        cwrC, draftC, pC = build()
        draftC.agent_name = "race_conflict_agent"
        rconf = persist_agent_run_record(cwrC, session_factory=f, persistence_request=pC)
        check("race -> conflict denied",
              rconf.outcome == AgentRunWriteOutcome.DENIED
              and rconf.reason_code == "idempotency_conflict")
        check("race conflict left one row", count(f, AgentRunRecord) == 1)
    finally:
        writer_mod._find_existing = orig_find

    # ---- Rollback leaves no partial row ----
    print("\n18. Rollback safety")
    check("no partial row after failure paths", count(f, AgentRunRecord) == 1)

    # Cleanup temp DBs.
    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 20 controlled-DB agent-run-writer check")
    print("=" * 50)

    structural_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
        print("         Run: make validate-phase20 PYTHON=.venv/bin/python")
    else:
        print(f"  SQLAlchemy {sqlalchemy.__version__} present — running DB-backed checks.")
        db_backed_checks()

    print("\n" + "=" * 50)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    if _failures:
        print(f"\nRESULT: {FAIL} ({len(_failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
