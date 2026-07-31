#!/usr/bin/env python3
"""Phase 35 governed managed-record workflow integration check.

Three layers:

* **Structural (always, stdlib-only):** the workflow package/contracts/docs exist and compile; the
  package imports no SQLAlchemy/Alembic/DB-model/migration at module scope (proved at runtime in a
  subprocess), no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential,
  no Phase 22 review writer, and no publication code; the Phase 17 allowlist gained **no** new
  table/action pair; no migration `010` was added; the docs carry the required language; the repo
  stays source-only.

* **Plan-only / DB-free (always, stdlib-only):** gate behavior (planned / skipped / denied), stage
  idempotency-key derivation and stage prefixing, identity + authorization-scope pre-flight denial,
  prohibited key/value denial, strict-mode halting vs non-strict warning collection, and result
  leak-safety with canary values. None of this opens a database connection.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database — a fully gated six-stage workflow persisting through the six existing narrow writers,
  per-stage gating, sanitized receipts and record refs, `table_write_counts`, replay, writer-denial
  and idempotency-conflict halting, and side-effect discipline (no `review_records` /
  `agent_run_records` row). SQLite here is only a fast local structural smoke path — **NOT** the
  production-readiness proof path (see docs/PRODUCTION_PARITY_DB_VALIDATION.md). Skipped with
  instructions if SQLAlchemy is absent (still exits 0).

Phase 35 adds no table/model/migration, no allowlist pair, no generic CRUD, no arbitrary SQL, no
client-facing output, no financial verification, no capsule publication, and makes no agent /
mock-agent / LLM / AgentNet / MCP / resolver / network call.

Exit status:
  0  -> all run checks passed (DB layer skipped counts as pass if deps absent)
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PY = sys.executable or "python3"

WORKFLOW_FILES = [
    "peak/workflows/__init__.py",
    "peak/workflows/contracts.py",
    "peak/workflows/governance.py",
    "peak/workflows/managed_record_workflow.py",
]
DOCS = [
    "docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md",
    "docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md",
]
REQUIRED_FILES = WORKFLOW_FILES + DOCS
COMPILE_FILES = WORKFLOW_FILES + [
    "tests/validate_phase35_managed_record_workflow.py",
]

REQUIRED_DOC_PHRASES = [
    "workflow integration phase, not a new persistence primitive",
    "no db table",
    "009_intake_note_records",
    "15 tables",
    "plan-only",
    "no silent escalation",
    "halted_after_stage",
    "stored engagement remains the authorization anchor",
    "identity matching is necessary but not sufficient",
    "cross-tenant",
    "idempotent_replay",
    "idempotency_conflict",
    "wf35::",
    "never echo",
    "review_records",
    "agent_run_records",
    "managed remote mysql",
    "client isolation option a",
    "sqlite is not the production-readiness proof path",
    "no live database credentials and no network",
]

# The Phase 17 allowlist as it stood at the Phase 34 baseline. Phase 35 adds nothing.
BASELINE_ALLOWED_TABLES = {
    "evidence_references", "engagement_records", "review_records", "agent_run_records",
    "source_ingestion_records", "agent_task_queue_records", "review_bundle_records",
    "internal_reviewer_decision_records", "intake_note_records", "capsule_publication_candidates",
}
BASELINE_ALLOWED_ACTIONS = {
    "create_draft", "create_review_record", "create_agent_run_record",
    "create_source_ingestion_record", "create_agent_task_queue_record",
    "create_review_bundle_record", "create_internal_reviewer_decision_record",
    "create_intake_note_record", "create_capsule_candidate_draft", "update_review_status",
    "update_lifecycle_status", "mark_superseded",
}

EXISTING_WRITERS = [
    ("peak/db/agent_run_writer.py", "persist_agent_run_record"),
    ("peak/db/evidence_writer.py", "persist_evidence_reference"),
    ("peak/db/review_writer.py", "persist_review_record"),
    ("peak/db/source_ingestion_writer.py", "persist_source_ingestion_record"),
    ("peak/db/agent_task_queue_writer.py", "persist_agent_task_queue_record"),
    ("peak/db/review_bundle_writer.py", "persist_review_bundle_record"),
    ("peak/db/internal_reviewer_decision_writer.py", "persist_internal_reviewer_decision_record"),
    ("peak/db/intake_note_writer.py", "persist_intake_note_record"),
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
MODEL_IMPORT_RE = re.compile(r"peak\.db\.(?:models|session|base)\b")
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp|mcp_connector|resolver_client)\b", re.IGNORECASE)
REVIEW_WRITER_RE = re.compile(r"\breview_writer\b|persist_review_record")
AGENT_RUN_WRITER_RE = re.compile(r"\bagent_run_writer\b|persist_agent_run_record")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE)
RAW_SQL_RE = re.compile(r"\b(?:text\(|execute\(|session\.execute|engine\.execute)\b")
PUBLISH_IMPL_RE = re.compile(
    r"\b(?:publish_capsule|publish_node|agentnet_publish|resolver_publish)\s*\(")

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []

# A canary that must never appear in any workflow result, reason, or warning.
_CANARY = "ZZCANARY35ZZ"


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


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


def _blob(result) -> str:
    """Flatten everything a caller could read off a workflow result into one string."""
    parts = list(result.reasons or []) + list(result.warnings or [])
    parts += [str(result.reason_code), str(result.outcome)]
    for sr in (result.stage_results or {}).values():
        parts += list(sr.reasons or []) + list(sr.warnings or [])
        parts += [str(sr.reason_code), str(sr.idempotency_key), str(sr.created_record_ref)]
        if sr.receipt is not None:
            parts += list(sr.receipt.reasons or []) + list(sr.receipt.warnings or [])
            parts += [str(sr.receipt.reason_code), str(sr.receipt.stored_record_id)]
    parts += [str(v) for v in (result.created_record_refs or {}).values()]
    parts += [str(v) for v in (result.stage_idempotency_keys or {}).values()]
    return " ".join(parts)


def _no_effects(result) -> bool:
    """True when every prohibited side-effect flag on a workflow result is False."""
    return (result.review_records_write_made is False
            and result.agent_run_records_write_made is False
            and result.review_approval_made is False
            and result.client_facing_output_created is False
            and result.financial_verification_made is False
            and result.capsule_publication_made is False
            and result.agent_execution_made is False
            and result.mock_agent_execution_made is False
            and result.llm_call_made is False
            and result.agentnet_call_made is False
            and result.resolver_call_made is False
            and result.network_call_made is False)


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Workflow package / doc files present")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Workflow package imports: no DB layer / LLM / connector / network / credential")
    for rel in WORKFLOW_FILES:
        text = read(rel)
        imports = list(_import_lines(text))
        joined = " ".join(imports)
        check(f"{rel}: no SQLAlchemy/Alembic/pymysql import",
              not DB_IMPORT_RE.search(joined))
        check(f"{rel}: no DB model/session/base import at module scope",
              not any(MODEL_IMPORT_RE.search(ln) for ln in imports if not _is_lazy(text, ln)))
        check(f"{rel}: no network client import", not NETWORK_IMPORT_RE.search(joined))
        check(f"{rel}: no LLM provider import", not LLM_PROVIDER_RE.search(joined))
        check(f"{rel}: no executor/MockLLM import", not EXEC_IMPORT_RE.search(joined))
        check(f"{rel}: no AgentNet/MCP/resolver connector import",
              not CONNECTOR_RE.search(joined))
        check(f"{rel}: no Phase 22 review-writer import", not REVIEW_WRITER_RE.search(joined))
        check(f"{rel}: no agent-run-writer import", not AGENT_RUN_WRITER_RE.search(joined))
        check(f"{rel}: no committed credential literal", not CREDENTIAL_RE.search(text))
        check(f"{rel}: no raw SQL execution", not RAW_SQL_RE.search(text))
        check(f"{rel}: no publication implementation", not PUBLISH_IMPL_RE.search(text))

    print("\n4. Package imports lazily: peak.workflows pulls in no SQLAlchemy/Alembic")
    probe = (
        "import sys; import peak.workflows as w; "
        "bad=[m for m in sys.modules if m.split('.')[0] in ('sqlalchemy','alembic','pymysql')]; "
        "print('LAZY_OK' if not bad else 'LEAKED:'+','.join(sorted(bad)))"
    )
    proc = subprocess.run([PY, "-c", probe], capture_output=True, text=True,
                          cwd=REPO_ROOT, timeout=90)
    check("importing peak.workflows loads no DB driver",
          "LAZY_OK" in proc.stdout)
    plan_probe = (
        "import sys; from peak.workflows import ManagedRecordWorkflowRequest, "
        "run_managed_record_workflow as run; "
        "r = run(ManagedRecordWorkflowRequest(owner_id='o', client_id='c', engagement_id='e', "
        "authorization_scope='engagement_authorized', requested_by='u', requester_role='consultant',"
        " workflow_id='wf_1')); "
        "bad=[m for m in sys.modules if m.split('.')[0] in ('sqlalchemy','alembic','pymysql')]; "
        "print('PLAN_OK' if (r.outcome=='planned' and not bad) else 'BAD:'+r.outcome+str(bad))"
    )
    proc2 = subprocess.run([PY, "-c", plan_probe], capture_output=True, text=True,
                           cwd=REPO_ROOT, timeout=90)
    check("a plan-only run needs no DB driver", "PLAN_OK" in proc2.stdout)

    print("\n5. Public entry point and result contracts exist")
    from peak.workflows import (
        WORKFLOW_STAGES, ManagedRecordWorkflowRequest, ManagedRecordWorkflowResult,
        WorkflowOutcome, WorkflowStageOutcome, WorkflowStageReceipt, WorkflowStageResult,
        run_managed_record_workflow,
    )
    from peak.workflows.contracts import STAGE_TARGETS, WORKFLOW_TABLES

    check("run_managed_record_workflow is callable", callable(run_managed_record_workflow))
    import inspect
    sig = inspect.signature(run_managed_record_workflow)
    check("entry point signature (request, *, session_factory=None)",
          list(sig.parameters) == ["request", "session_factory"]
          and sig.parameters["session_factory"].default is None)
    check("six workflow stages in controlled order",
          WORKFLOW_STAGES == ("intake_note", "source_ingestion", "evidence_reference",
                              "agent_task_queue", "review_bundle", "reviewer_decision"))
    check("result contract carries stage bookkeeping",
          all(hasattr(ManagedRecordWorkflowResult(), f) for f in (
              "outcome", "permitted", "reason_code", "workflow_id", "owner_id", "client_id",
              "engagement_id", "authorization_scope", "stages_requested", "stages_planned",
              "stages_skipped", "stages_persisted", "stages_replayed", "stages_denied",
              "stages_conflicted", "halted_after_stage", "receipts", "stage_results",
              "warnings", "reasons", "table_write_counts", "created_record_refs")))
    check("result contract carries the side-effect flags",
          all(hasattr(ManagedRecordWorkflowResult(), f) for f in (
              "database_connection_made", "sql_execution_made", "database_write_made",
              "stored_record_created", "review_records_write_made", "review_approval_made",
              "client_facing_output_created", "financial_verification_made",
              "capsule_publication_made", "agent_execution_made", "mock_agent_execution_made",
              "llm_call_made", "agentnet_call_made", "resolver_call_made", "network_call_made")))
    check("request contract carries identity/gates/strict_mode",
          all(hasattr(ManagedRecordWorkflowRequest(), f) for f in (
              "owner_id", "client_id", "engagement_id", "authorization_scope", "requested_by",
              "requester_role", "workflow_id", "intake_note_payload", "source_ingestion_payload",
              "evidence_payload", "agent_task_payload", "review_bundle_payload",
              "reviewer_decision_payload", "persistence_gates", "strict_mode")))
    check("stage/receipt result contracts exist",
          WorkflowStageResult().stage == "" and WorkflowStageReceipt().stage == ""
          and WorkflowOutcome.PERSISTED == "persisted"
          and WorkflowStageOutcome.HALTED == "halted")
    check("workflow targets only the six existing tables (no review_records/agent_run_records)",
          set(WORKFLOW_TABLES) == {
              "intake_note_records", "source_ingestion_records", "evidence_references",
              "agent_task_queue_records", "review_bundle_records",
              "internal_reviewer_decision_records"}
          and len(STAGE_TARGETS) == 6)

    print("\n6. Phase 35 itself adds no table / model / migration / allowlist pair")
    # Scoped to what PHASE 35 contributed. Later phases add their own schema additively (Phase 37
    # adds internal_assessment_report_drafts + migration 010), so a frozen global count or an exact
    # allowlist set would fail for reasons unrelated to Phase 35.
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    # "Authored by" = the migration's own docstring header declares it. A later migration may
    # legitimately *reference* Phase 35 as context without being a Phase 35 migration.
    check("no migration was authored by Phase 35",
          not any(re.match(r'\s*"""Phase 35\b',
                           read(os.path.join("alembic", "versions", f)))
                  for f in versions))
    check("the workflow package defines no DB model / table",
          not any(re.search(r"__tablename__|\(\s*Base\b", read(rel)) for rel in WORKFLOW_FILES))
    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("Phase 17 allowlist still contains the Phase 35 baseline (nothing removed)",
          BASELINE_ALLOWED_TABLES <= set(ALLOWED_TABLES)
          and BASELINE_ALLOWED_ACTIONS <= set(ALLOWED_ACTIONS))
    check("the workflow package targets only pre-existing allowlist pairs",
          all(table in ALLOWED_TABLES and action in ALLOWED_ACTIONS
              for table, action in STAGE_TARGETS.values())
          and {t for t, _ in STAGE_TARGETS.values()} <= BASELINE_ALLOWED_TABLES)
    check("the workflow package never mutates the allowlist",
          not any("ALLOWED_TABLES" in read(rel) or "ALLOWED_ACTIONS" in read(rel)
                  for rel in WORKFLOW_FILES))
    import importlib
    p11mod = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11mod, "EXPECTED_TABLES", []))
    check("db-check expects at least the 15 tables present at the Phase 35 baseline",
          len(expected) >= 15)

    print("\n7. Regression: the eight existing writers remain; earlier phases intact")
    for rel, fn in EXISTING_WRITERS:
        body = read(rel)
        check(f"{rel}: {fn} present", f"def {fn}(" in body)
    rd_imports = " ".join(_import_lines(read("peak/reviewer_decisions/governance.py"))
                          ) + " " + " ".join(_import_lines(read(
                              "peak/reviewer_decisions/contracts.py")))
    check("Phase 32 reviewer_decisions package remains DB-free",
          not DB_IMPORT_RE.search(rd_imports) and "peak.db" not in rd_imports)
    check("Phase 33 writer still uses the public classify_prohibited_value_marker",
          "classify_prohibited_value_marker" in read(
              "peak/db/internal_reviewer_decision_writer.py"))
    intake = read("peak/db/intake_note_writer.py")
    check("Phase 34 intake writer still uses the hardened credential-disclosure scanner",
          "_CRED_ASSIGN_RE" in intake and "_note_text_category" in intake)

    print("\n8. Docs carry the required Phase 35 language")
    doc_blob = re.sub(r"\s+", " ", " ".join(read(d) for d in DOCS)).lower()
    for phrase in REQUIRED_DOC_PHRASES:
        check(f"docs state: {phrase}", phrase in doc_blob)
    check("docs record the DB-free boundary handoff", "handoff" in doc_blob)
    check("docs state AgentNet publication is unchanged/deferred",
          "agentnet publication remains deferred" in doc_blob
          or "does not alter the peak-operated agentnet publication policy" in doc_blob)

    print("\n9. Managed MySQL policy regression (unchanged by Phase 35)")
    rub = re.sub(r"\s+", " ", read("docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md") + " "
                 + read("docs/PRODUCTION_PARITY_DB_VALIDATION.md") + " "
                 + read("docs/CLIENT_ISOLATION_MODEL.md")).lower()
    check("managed remote MySQL is still the operational data store",
          "managed remote mysql" in rub and "operational data store" in rub)
    check("Client Isolation Option A is still the default",
          "client isolation option a" in rub and "default" in rub)
    check("SQLite is still not the production-readiness proof path",
          "sqlite is not the production-readiness proof path" in rub)
    check("managed MySQL test/staging validation still required",
          "managed mysql test/staging validation is required" in rub)
    mk = read("Makefile")
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("validate-phase35 is part of `make validate`", "validate-phase35" in validate_line)
    for target in ("db-check-managed-test", "managed-mysql-smoke",
                   "managed-mysql-migration-check"):
        check(f"managed target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("no DSN / database URL added by Phase 35",
          not any(re.search(r"mysql\+pymysql://|postgres://|PEAK_DATABASE_URL\s*=", read(rel))
                  for rel in WORKFLOW_FILES + DOCS))

    print("\n10. AgentNet publication policy regression (unchanged by Phase 35)")
    pub = re.sub(r"\s+", " ", read("docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md")).lower()
    check("client authorizes Peak as publisher in the consulting agreement",
          "consulting agreement" in pub and "authorized capsule/node publisher" in pub)
    check("clients do not operate any AgentNet publishing tools",
          "clients do not operate any agentnet publishing tools" in pub)
    check("no client-facing AgentNet publisher UI",
          "no client-facing agentnet publisher ui" in pub)
    check("no client-held publishing credentials", "no client-held publishing credentials" in pub)
    check("no client-operated resolver publication tools",
          "no client-operated resolver publication tools" in pub)
    check("no direct client publication path", "no direct client publication path" in pub)
    offenders = []
    for dp, dns, fns in os.walk(REPO_ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if _skip(os.path.relpath(dp, REPO_ROOT)):
            continue
        for f in fns:
            if f.endswith(".py") and PUBLISH_IMPL_RE.search(
                read(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
            ):
                offenders.append(f)
    check("no AgentNet/resolver publish implementation added", not offenders)

    print("\n11. Repo hygiene: source-only, no data / credentials / examples")
    check("no examples/ directory", not os.path.isdir(os.path.join(REPO_ROOT, "examples")))
    artifacts, dbfiles = [], []
    for dp, dns, fns in os.walk(REPO_ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if _skip(os.path.relpath(dp, REPO_ROOT)):
            continue
        for f in fns:
            if f.lower().endswith(DATA_EXTS):
                (dbfiles if f.lower().endswith((".db", ".sqlite", ".sqlite3", ".sql"))
                 else artifacts).append(os.path.join(dp, f))
    check("no committed data artifacts", not artifacts)
    check("no committed database files / dumps", not dbfiles)
    check("docs/Peak_Investor_Overview_AI.docx untouched",
          os.path.isfile(os.path.join(REPO_ROOT, "docs", "Peak_Investor_Overview_AI.docx")))
    try:
        tracked = subprocess.run(["git", "-C", REPO_ROOT, "ls-files"],
                                 capture_output=True, text=True, timeout=20).stdout
        check(".claude/settings.local.json is not tracked",
              ".claude/settings.local.json" not in tracked)
        check(".env is not tracked", "\n.env\n" not in "\n" + tracked)
        docx_diff = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--",
             "docs/Peak_Investor_Overview_AI.docx"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff", not docx_diff)
        # Verify the pinned baseline commit by ancestry over the FULL history. A fixed
        # `git log --oneline -N` window silently falls out of range as later phases land,
        # which made this check fail (or pass by accident) for reasons unrelated to the
        # baseline actually being present.
        present = subprocess.run(
            ["git", "-C", REPO_ROOT, "merge-base", "--is-ancestor", "a2bd5be", "HEAD"],
            capture_output=True, timeout=20).returncode == 0
        check("Phase 34 baseline commit a2bd5be present in history", present)
    except Exception:
        check("git-backed hygiene checks (git unavailable — skipped)", True)


def _is_lazy(text: str, import_line: str) -> bool:
    """True when an import line sits inside a function body (indented) — i.e. a lazy import."""
    for line in text.splitlines():
        if line.strip() == import_line:
            return line.startswith((" ", "\t"))
    return False


# --------------------------------------------------------------------------- builders


_ID = dict(owner_id="owner_1", client_id="client_a", engagement_id="eng_x")
_SCOPE = "engagement_authorized"
# Synthetic, marker-free operational prose (NOT client-like; safe to keep in the repo).
_NOTE_TEXT = ("Walkaround with the operations lead: pallets were staged in the receiving aisle and "
              "putaway was running about a shift behind the receiving schedule.")


def _make_drafts():
    """Build one safe, review-gated draft per stage (synthetic; no client data)."""
    from peak.db.writer_contracts import IntakeNoteDraft
    from peak.evidence.persistence_contracts import EvidencePersistenceDraft
    from peak.ingestion.contracts import SourceIngestionDraft
    from peak.review_orchestration.contracts import ReviewBundleDraft, ReviewSubjectReference
    from peak.reviewer_decisions.contracts import InternalReviewerDecisionDraft
    from peak.task_queue.contracts import AgentTaskQueueDraft

    def intake(**over):
        base = dict(**_ID, authorization_scope=_SCOPE, note_type="discovery_call",
                    note_source="consultant", note_text=_NOTE_TEXT,
                    note_summary="receiving aisle congestion", captured_by="consultant_a",
                    captured_role="lead_consultant", source_ref="call_2026_07",
                    source_ingestion_record_id="ing_1")
        base.update(over)
        return IntakeNoteDraft(**base)

    def source(**over):
        base = dict(**_ID, packet_reference_id="pkt_1", packet_schema_name="engagement-packet",
                    packet_schema_version="1.0", packet_source_type="consultant_upload",
                    packet_location_reference="controlled://engagement/eng_x/packet_1",
                    packet_hash="sha256:deadbeef", output_status="draft",
                    review_status="needs_review", lifecycle_status="active")
        base.update(over)
        return SourceIngestionDraft(**base)

    def evidence(**over):
        base = dict(**_ID, source_reference_id="src_1", evidence_type="visual_observation",
                    normalized_title="[draft] visual_observation - receiving_dock",
                    normalized_summary="Worker-normalized, review-gated evidence.",
                    observed_condition="Pallets staged in the receiving aisle",
                    operational_area="receiving_dock", inventory_process_area="receiving",
                    source_type="site_walk", source_location="receiving dock",
                    confidence_level="medium", output_status="draft",
                    review_status="needs_review", lifecycle_status="active")
        base.update(over)
        return EvidencePersistenceDraft(**base)

    def task(**over):
        base = dict(**_ID, agent_name="new_client_intake_agent", workflow="intake",
                    task_type="intake", requested_action="normalize", task_input_ref=["rec_1"],
                    task_input_summary="1 input record id(s)", source_ingestion_record_id="ing_1",
                    evidence_reference_ids=["evid_1"], packet_processing_run_ref="pkt_run_1",
                    orchestration_ref="orch_1",
                    prompt_contract_path="prompts/intake/normalize-client-intake.prompt.md",
                    authorization_scope=_SCOPE, readiness_state="queued_for_review",
                    output_status="draft", review_status="needs_review",
                    lifecycle_status="draft")
        base.update(over)
        return AgentTaskQueueDraft(**base)

    def bundle(**over):
        base = dict(**_ID, packet_processing_receipt_ref="pkt_run_1",
                    source_ingestion_record_ids=["ing_1"], evidence_reference_ids=["evid_1"],
                    agent_task_queue_record_ids=["atq_1"],
                    subject_refs=[ReviewSubjectReference(
                        subject_ref_id="ing_1", subject_type="source_ingestion_record",
                        **_ID, authorization_scope=_SCOPE)],
                    reviewer_role="internal_reviewer", review_reason="post-packet review",
                    review_scope=_SCOPE, output_status="draft", review_status="needs_review",
                    lifecycle_status="draft")
        base.update(over)
        return ReviewBundleDraft(**base)

    def decision(**over):
        base = dict(**_ID, review_bundle_ref="rvb_ref_1", review_bundle_record_id="rvb_1",
                    review_bundle_draft_ref="rvb_draft_1", review_plan_item_refs=["rpi_1"],
                    evidence_reference_ids=["evid_1"], source_ingestion_record_ids=["ing_1"],
                    agent_task_queue_record_ids=["atq_1"], reviewer_role="internal_reviewer",
                    decision_intent="ready_for_internal_use",
                    decision_reason_code="meets_internal_bar",
                    safe_decision_summary="internally reliable for planning",
                    requested_followup_actions=["schedule_internal_followup"],
                    authorization_scope=_SCOPE, output_status="draft",
                    review_status="needs_review", lifecycle_status="draft")
        base.update(over)
        return InternalReviewerDecisionDraft(**base)

    return intake, source, evidence, task, bundle, decision


def _make_request(**over):
    from peak.workflows import ManagedRecordWorkflowRequest

    base = dict(**_ID, authorization_scope=_SCOPE, requested_by="consultant_a",
                requester_role="consultant", workflow_id="wf_1")
    base.update(over)
    return ManagedRecordWorkflowRequest(**base)


def _all_payloads():
    intake, source, evidence, task, bundle, decision = _make_drafts()
    return dict(intake_note_payload=intake(), source_ingestion_payload=source(),
                evidence_payload=evidence(), agent_task_payload=task(),
                review_bundle_payload=bundle(), reviewer_decision_payload=decision())


# --------------------------------------------------------------------------- plan-only / DB-free


def plan_only_checks() -> None:
    from peak.workflows import (
        WORKFLOW_STAGES, WorkflowOutcome as WO, WorkflowStageOutcome as SO,
        run_managed_record_workflow as run,
    )

    intake, source, evidence, task, bundle, decision = _make_drafts()

    print("\n12. Plan-only default: nothing requested, nothing persisted")
    r = run(_make_request())
    check("outcome planned", r.outcome == WO.PLANNED and r.permitted is True)
    check("every stage skipped", set(r.stages_skipped) == set(WORKFLOW_STAGES))
    check("no stage requested", r.stages_requested == [])
    check("no DB flags set",
          r.database_connection_made is False and r.sql_execution_made is False
          and r.database_write_made is False and r.stored_record_created is False)
    check("no prohibited side effects", _no_effects(r))

    print("\n13. Payload present + gate false -> planned, no writer called")
    r = run(_make_request(**_all_payloads()))
    check("outcome planned", r.outcome == WO.PLANNED)
    check("all six stages planned", set(r.stages_planned) == set(WORKFLOW_STAGES))
    check("all six stages requested", set(r.stages_requested) == set(WORKFLOW_STAGES))
    check("no writer called", all(sr.writer_called is False
                                  for sr in r.stage_results.values()))
    check("no receipts produced", r.receipts == {})
    check("no DB write flags", r.database_write_made is False
          and r.database_connection_made is False)
    check("stage keys still derived for the plan", len(r.stage_idempotency_keys) == 6)

    print("\n14. No payload + gate false -> skipped cleanly; gate true + no payload -> denied")
    r = run(_make_request(intake_note_payload=intake(),
                          persistence_gates={"source_ingestion": True}))
    check("intake_note planned", r.stage_results["intake_note"].outcome == SO.PLANNED)
    check("source_ingestion denied (missing payload)",
          r.stage_results["source_ingestion"].outcome == SO.DENIED
          and r.stage_results["source_ingestion"].reason_code == "missing_stage_payload")
    check("no writer called for the denied stage",
          r.stage_results["source_ingestion"].writer_called is False)
    check("dependent stages halted after the denial",
          r.halted_after_stage == "source_ingestion"
          and all(r.stage_results[s].outcome == SO.HALTED
                  for s in ("evidence_reference", "agent_task_queue", "review_bundle",
                            "reviewer_decision")))
    check("aggregate outcome halted", r.outcome == WO.HALTED)
    check("no DB connection made on denial", r.database_connection_made is False)

    print("\n15. Gate true with no session_factory fails closed (no ambient DSN)")
    r = run(_make_request(intake_note_payload=intake(),
                          persistence_gates={"intake_note": True}))
    check("denied with missing_session_factory",
          r.stage_results["intake_note"].reason_code == "missing_session_factory")
    check("no writer called", r.stage_results["intake_note"].writer_called is False)
    check("no DB connection made", r.database_connection_made is False)

    print("\n16. Pre-flight request denials (no stage runs)")
    for field, reason in (("owner_id", "missing_identity_field"),
                          ("client_id", "missing_identity_field"),
                          ("authorization_scope", "missing_identity_field"),
                          ("requester_role", "missing_identity_field")):
        r = run(_make_request(**{field: None}))
        check(f"missing {field} -> {reason}",
              r.outcome == WO.DENIED and r.reason_code == reason)
    r = run(_make_request(authorization_scope="revoked"))
    check("revoked scope denied", r.reason_code == "blocked_authorization_scope")
    r = run(_make_request(persistence_gates={"not_a_stage": True}))
    check("unknown gate stage denied", r.reason_code == "unknown_stage_gate")
    r = run(_make_request(persistence_gates={"intake_note": "yes"}))
    check("non-bool gate denied", r.reason_code == "invalid_persistence_gates")
    r = run(_make_request(workflow_id="wf 1/../bad"))
    check("unsafe workflow_id denied", r.reason_code == "invalid_workflow_id")
    r = run(object())
    check("duck-typed request denied", r.reason_code == "invalid_request_type")
    check("denied result runs no stage", r.stage_results == {} and r.permitted is False)

    print("\n17. Identity / authorization-scope pre-flight denial (before any writer)")
    r = run(_make_request(source_ingestion_payload=source(client_id="other_client"),
                          persistence_gates={"source_ingestion": True}))
    check("cross-tenant source payload denied",
          r.stage_results["source_ingestion"].reason_code == "identity_mismatch")
    check("no writer called", r.stage_results["source_ingestion"].writer_called is False)
    r = run(_make_request(source_ingestion_payload=source(engagement_id="eng_other"),
                          persistence_gates={"source_ingestion": True}))
    check("cross-engagement source payload denied",
          r.stage_results["source_ingestion"].reason_code == "identity_mismatch")
    r = run(_make_request(agent_task_payload=task(authorization_scope="other_scope")))
    check("authorization_scope mismatch denied",
          r.stage_results["agent_task_queue"].reason_code == "authorization_scope_mismatch")
    r = run(_make_request(intake_note_payload=object()))
    check("wrong payload type denied",
          r.stage_results["intake_note"].reason_code == "invalid_stage_payload")

    print("\n18. Idempotency key derivation")
    r1 = run(_make_request(**_all_payloads()))
    r2 = run(_make_request(**_all_payloads()))
    check("derived keys are deterministic",
          r1.stage_idempotency_keys == r2.stage_idempotency_keys)
    check("every key is stage-prefixed",
          all(key.startswith(f"wf35::{stage}::")
              for stage, key in r1.stage_idempotency_keys.items()))
    check("keys differ across stages", len(set(r1.stage_idempotency_keys.values())) == 6)
    check("keys carry the workflow_id",
          all("wf_1" in key for key in r1.stage_idempotency_keys.values()))
    check("keys respect the writers' 128-char bound",
          all(len(key) <= 128 for key in r1.stage_idempotency_keys.values()))
    check("derived keys are marked derived",
          all(sr.idempotency_key_source == "derived" for sr in r1.stage_results.values()))
    r3 = run(_make_request(**_all_payloads(),
                           stage_idempotency_keys={"intake_note": "my-own-key"}))
    check("explicit stage key is respected (and stage-namespaced)",
          r3.stage_idempotency_keys["intake_note"] == "wf35::intake_note::my-own-key")
    check("explicit key is marked explicit",
          r3.stage_results["intake_note"].idempotency_key_source == "explicit")
    check("other stages still derive",
          r3.stage_idempotency_keys["review_bundle"]
          == r1.stage_idempotency_keys["review_bundle"])
    # Same literal, two stages -> two distinct namespaced keys (no cross-table confusion).
    r4 = run(_make_request(**_all_payloads(),
                           stage_idempotency_keys={"intake_note": "shared", "review_bundle": "shared"}))
    check("the same literal key cannot collide across tables",
          r4.stage_idempotency_keys["intake_note"] != r4.stage_idempotency_keys["review_bundle"])
    # Payload change -> derived key changes; explicit key is stable across payload changes.
    r5 = run(_make_request(**{**_all_payloads(), "source_ingestion_payload": source(
        packet_reference_id="pkt_2")}))
    check("a changed payload changes its derived key",
          r5.stage_idempotency_keys["source_ingestion"]
          != r1.stage_idempotency_keys["source_ingestion"])
    r6 = run(_make_request(intake_note_payload=intake(note_summary="different summary"),
                           stage_idempotency_keys={"intake_note": "my-own-key"}))
    check("an explicit key is stable when the payload changes",
          r6.stage_idempotency_keys["intake_note"] == "wf35::intake_note::my-own-key")
    r7 = run(_make_request(workflow_id=None, intake_note_payload=intake()))
    check("no workflow_id and no explicit key -> denied, never a random key",
          r7.stage_results["intake_note"].reason_code == "missing_stage_idempotency_key")
    r8 = run(_make_request(workflow_id=None, intake_note_payload=intake(),
                           stage_idempotency_keys={"intake_note": "k1"}))
    check("no workflow_id but an explicit key -> planned",
          r8.stage_results["intake_note"].outcome == SO.PLANNED)

    print("\n19. Prohibited keys / values denied before any writer")
    prohibited_keys = ("database_url", "raw_sql", "source_bytes", "generated_output",
                       "raw_evidence_text", "raw_interview_text", "packet_payload",
                       "final_client_report", "client_facing_output", "approve_internal",
                       "approve_client_facing", "publish_capsule", "agentnet_publish",
                       "resolver_credentials", "llm_prompt")
    for key in prohibited_keys:
        d = intake()
        setattr(d, key, _CANARY)
        r = run(_make_request(intake_note_payload=d, persistence_gates={"intake_note": True}))
        sr = r.stage_results["intake_note"]
        ok = (sr.outcome == SO.DENIED and sr.reason_code == "prohibited_payload_key"
              and sr.writer_called is False and _CANARY not in _blob(r))
        check(f"prohibited key '{key}' denied without echoing its value", ok)

    marker_values = {
        "credential/secret": f"api_key={_CANARY}",
        "DB-URL/DSN": f"mysql://user:{_CANARY}@host/db",
        "raw-SQL": f"select * from clients where name='{_CANARY}'",
        "raw-content": f"source_bytes {_CANARY}",
        "JSON dump": '{"a": "' + _CANARY + '"}',
    }
    for label, value in marker_values.items():
        r = run(_make_request(intake_note_payload=intake(note_summary=value),
                              persistence_gates={"intake_note": True}))
        sr = r.stage_results["intake_note"]
        ok = (sr.outcome == SO.DENIED and sr.reason_code == "prohibited_payload_value"
              and sr.writer_called is False and _CANARY not in _blob(r))
        check(f"{label} value denied without echoing the value", ok)

    r = run(_make_request(intake_note_payload=intake(source_ref="a ref with spaces"),
                          persistence_gates={"intake_note": True}))
    check("unsafe stage ref denied",
          r.stage_results["intake_note"].reason_code == "unsafe_stage_ref")
    r = run(_make_request(source_ingestion_payload=source(created_at="2026-07-30T00:00:00Z")))
    check("caller-supplied server timestamp denied",
          r.stage_results["source_ingestion"].reason_code == "caller_supplied_timestamp")
    r = run(_make_request(intake_note_payload=intake(captured_at="2026-07-30T00:00:00Z")))
    check("caller-supplied capture timestamp denied",
          r.stage_results["intake_note"].reason_code == "caller_supplied_timestamp")

    print("\n20. Result never echoes note_text or raw content")
    r = run(_make_request(**_all_payloads()))
    check("result never echoes note_text", _NOTE_TEXT not in _blob(r))
    check("result never echoes a note_text fragment",
          "pallets were staged" not in _blob(r).lower())
    long_note = "operational prose. " * 400
    r = run(_make_request(intake_note_payload=intake(note_text=long_note)))
    check("long note body never echoed", "operational prose." not in _blob(r))

    print("\n21. strict_mode halts on a warning; non-strict collects it")
    d = intake()
    setattr(d, "unmapped_local_marker", "safe-value")
    r = run(_make_request(intake_note_payload=d, source_ingestion_payload=source(),
                          strict_mode=False))
    check("non-strict: warning collected", any("unexpected attribute" in w for w in r.warnings))
    check("non-strict: workflow continues", r.halted_after_stage is None
          and r.stage_results["source_ingestion"].outcome == SO.PLANNED)
    check("non-strict: no side effects from the warning", _no_effects(r)
          and r.database_write_made is False)
    d2 = intake()
    setattr(d2, "unmapped_local_marker", "safe-value")
    r = run(_make_request(intake_note_payload=d2, source_ingestion_payload=source(),
                          strict_mode=True))
    check("strict: workflow halts after the warning stage",
          r.halted_after_stage == "intake_note" and r.outcome == WO.HALTED)
    check("strict: later stages halted",
          r.stage_results["source_ingestion"].outcome == SO.HALTED)
    check("strict: still no side effects", _no_effects(r) and r.database_write_made is False)


# --------------------------------------------------------------------------- DB-backed


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, AgentTaskQueueRecord, Client, Engagement, EvidenceReference,
        IntakeNoteRecord, InternalReviewerDecisionRecord, ReviewBundleRecord, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.workflows import (
        WORKFLOW_STAGES, WorkflowOutcome as WO, WorkflowStageOutcome as SO,
        run_managed_record_workflow as run,
    )

    intake, source, evidence, task, bundle, decision = _make_drafts()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase35_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        s = factory()
        s.add(Engagement(id="eng_x", client_id="client_a", owner_id="owner_1",
                         authorization_scope=_SCOPE, lifecycle_status="active",
                         review_status="active"))
        s.commit()
        s.close()
        return factory

    def count(factory, model):
        s = factory()
        n = s.query(model).count()
        s.close()
        return n

    all_gates = {stage: True for stage in WORKFLOW_STAGES}

    try:
        print("\n22. Fully gated six-stage workflow persists through the six narrow writers")
        f = fresh_db()
        r = run(_make_request(**_all_payloads(), persistence_gates=all_gates), session_factory=f)
        check("outcome persisted", r.outcome == WO.PERSISTED and r.permitted is True)
        check("all six stages persisted", set(r.stages_persisted) == set(WORKFLOW_STAGES))
        check("nothing denied / conflicted / halted",
              not r.stages_denied and not r.stages_conflicted
              and r.halted_after_stage is None)
        check("exactly one row per controlled table",
              count(f, IntakeNoteRecord) == 1 and count(f, SourceIngestionRecord) == 1
              and count(f, EvidenceReference) == 1 and count(f, AgentTaskQueueRecord) == 1
              and count(f, ReviewBundleRecord) == 1
              and count(f, InternalReviewerDecisionRecord) == 1)
        check("table_write_counts reports one write per table",
              r.table_write_counts == {
                  "intake_note_records": 1, "source_ingestion_records": 1,
                  "evidence_references": 1, "agent_task_queue_records": 1,
                  "review_bundle_records": 1, "internal_reviewer_decision_records": 1})
        check("created_record_refs reported for every stage",
              set(r.created_record_refs) == set(WORKFLOW_STAGES)
              and all(isinstance(v, str) and v for v in r.created_record_refs.values()))
        check("record refs are server-assigned ids, not content",
              r.created_record_refs["intake_note"].startswith("intn_")
              and r.created_record_refs["review_bundle"].startswith("rvb_"))
        check("DB flags true after a real write",
              r.database_connection_made and r.sql_execution_made and r.database_write_made
              and r.stored_record_created)
        check("no prohibited side effects", _no_effects(r))
        check("receipts sanitized (no raw content, no note body)",
              _NOTE_TEXT not in _blob(r) and len(r.receipts) == 6)
        check("each receipt names only its own controlled table",
              all(r.receipts[s].target_table == tbl for s, tbl in (
                  ("intake_note", "intake_note_records"),
                  ("source_ingestion", "source_ingestion_records"),
                  ("evidence_reference", "evidence_references"),
                  ("agent_task_queue", "agent_task_queue_records"),
                  ("review_bundle", "review_bundle_records"),
                  ("reviewer_decision", "internal_reviewer_decision_records"))))
        check("stored note_text is in the DB, never in the result",
              _stored_note_text(f, IntakeNoteRecord) == _NOTE_TEXT and _NOTE_TEXT not in _blob(r))

        print("\n23. Side-effect discipline: no review_records / agent_run_records / clients")
        check("NO review_records row created", count(f, ReviewRecord) == 0)
        check("NO agent_run_records row created", count(f, AgentRunRecord) == 0)
        check("clients table untouched", count(f, Client) == 0)

        print("\n24. Each writer runs only when its own gate is true")
        f = fresh_db()
        r = run(_make_request(**_all_payloads(),
                              persistence_gates={"intake_note": True, "review_bundle": True}),
                session_factory=f)
        check("only the two gated stages persisted",
              set(r.stages_persisted) == {"intake_note", "review_bundle"})
        check("the ungated stages planned only",
              set(r.stages_planned) == {"source_ingestion", "evidence_reference",
                                        "agent_task_queue", "reviewer_decision"})
        check("only the two gated tables were written",
              count(f, IntakeNoteRecord) == 1 and count(f, ReviewBundleRecord) == 1
              and count(f, SourceIngestionRecord) == 0 and count(f, EvidenceReference) == 0
              and count(f, AgentTaskQueueRecord) == 0
              and count(f, InternalReviewerDecisionRecord) == 0)
        check("outcome persisted", r.outcome == WO.PERSISTED)
        check("no prohibited side effects", _no_effects(r))

        print("\n25. Identity / scope mismatch is denied before any row is written")
        f = fresh_db()
        r = run(_make_request(**{**_all_payloads(),
                                 "source_ingestion_payload": source(client_id="other_client")},
                              persistence_gates=all_gates), session_factory=f)
        check("source stage denied on identity mismatch",
              r.stage_results["source_ingestion"].reason_code == "identity_mismatch")
        check("no source_ingestion row written", count(f, SourceIngestionRecord) == 0)
        check("dependent stages halted", r.halted_after_stage == "source_ingestion"
              and r.stage_results["evidence_reference"].outcome == SO.HALTED)
        check("outcome partial (intake wrote, then halted)",
              r.outcome == WO.PARTIAL and r.stages_persisted == ["intake_note"])
        f = fresh_db()
        r = run(_make_request(**{**_all_payloads(),
                                 "agent_task_payload": task(authorization_scope="other_scope")},
                              persistence_gates=all_gates), session_factory=f)
        check("authorization_scope mismatch denied before write",
              r.stage_results["agent_task_queue"].reason_code == "authorization_scope_mismatch"
              and count(f, AgentTaskQueueRecord) == 0)

        print("\n26. Writer denial halts the dependent stages")
        f = fresh_db()
        r = run(_make_request(**{**_all_payloads(),
                                 "review_bundle_payload": bundle(requires_human_review=False)},
                              persistence_gates=all_gates), session_factory=f)
        rb = r.stage_results["review_bundle"]
        check("review_bundle stage denied by its writer",
              rb.outcome == SO.DENIED and rb.writer_called is True)
        check("denial came from the writer, not pre-flight", rb.receipt is not None
              and rb.receipt.writer_outcome == "denied")
        check("no review_bundle row written", count(f, ReviewBundleRecord) == 0)
        check("reviewer_decision halted",
              r.stage_results["reviewer_decision"].outcome == SO.HALTED
              and r.halted_after_stage == "review_bundle")
        check("no internal_reviewer_decision row written",
              count(f, InternalReviewerDecisionRecord) == 0)
        check("earlier stages still persisted", len(r.stages_persisted) == 4)

        print("\n27. Stored-scope authorization is still enforced by the writers")
        tmp = tempfile.mkdtemp(prefix="peak_phase35_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "scope.db"))
        Base.metadata.create_all(engine)
        f2 = sessionmaker(bind=engine, expire_on_commit=False)
        s = f2()
        s.add(Engagement(id="eng_x", client_id="client_a", owner_id="owner_1",
                         authorization_scope="a_different_stored_scope",
                         lifecycle_status="active", review_status="active"))
        s.commit()
        s.close()
        r = run(_make_request(**_all_payloads(), persistence_gates=all_gates), session_factory=f2)
        check("stored-scope mismatch denied at the writer",
              r.stage_results["intake_note"].reason_code == "stored_scope_mismatch")
        check("no row written", count(f2, IntakeNoteRecord) == 0)
        check("workflow halted with nothing written",
              r.outcome == WO.HALTED and r.halted_after_stage == "intake_note")

        print("\n28. Idempotent replay: same workflow + same payloads, no duplicate rows")
        f = fresh_db()
        first = run(_make_request(**_all_payloads(), persistence_gates=all_gates),
                    session_factory=f)
        second = run(_make_request(**_all_payloads(), persistence_gates=all_gates),
                     session_factory=f)
        check("first run persisted all six", len(first.stages_persisted) == 6)
        check("second run replayed all six",
              set(second.stages_replayed) == set(WORKFLOW_STAGES)
              and second.stages_persisted == [])
        check("no duplicate rows",
              count(f, IntakeNoteRecord) == 1 and count(f, SourceIngestionRecord) == 1
              and count(f, EvidenceReference) == 1 and count(f, AgentTaskQueueRecord) == 1
              and count(f, ReviewBundleRecord) == 1
              and count(f, InternalReviewerDecisionRecord) == 1)
        check("replay returns the same record refs",
              second.created_record_refs == first.created_record_refs)
        check("replay reports no new writes", second.table_write_counts == {}
              and second.stored_record_created is False)
        check("replay still reports the read", second.database_connection_made is True)
        check("replay outcome persisted", second.outcome == WO.PERSISTED)

        print("\n29. Idempotency conflict halts the dependent stages")
        f = fresh_db()
        keys = {"review_bundle": "fixed-bundle-key"}
        run(_make_request(**_all_payloads(), persistence_gates=all_gates,
                          stage_idempotency_keys=keys), session_factory=f)
        r = run(_make_request(**{**_all_payloads(),
                                 "review_bundle_payload": bundle(
                                     review_reason="a materially different review reason")},
                              persistence_gates=all_gates, stage_idempotency_keys=keys),
                session_factory=f)
        rb = r.stage_results["review_bundle"]
        check("changed payload on the same explicit key conflicts",
              rb.outcome == SO.CONFLICTED and rb.reason_code == "idempotency_conflict")
        check("conflict recorded in stages_conflicted",
              r.stages_conflicted == ["review_bundle"])
        check("no duplicate review_bundle row", count(f, ReviewBundleRecord) == 1)
        check("dependent stage halted after the conflict",
              r.halted_after_stage == "review_bundle"
              and r.stage_results["reviewer_decision"].outcome == SO.HALTED)
        check("no prohibited side effects", _no_effects(r))

        print("\n30. Canary values never reach the result on a real DB path")
        f = fresh_db()
        d = intake()
        setattr(d, "database_url", f"mysql://u:{_CANARY}@h/db")
        r = run(_make_request(**{**_all_payloads(), "intake_note_payload": d},
                              persistence_gates=all_gates), session_factory=f)
        check("prohibited key denied before any writer ran",
              r.stage_results["intake_note"].reason_code == "prohibited_payload_key"
              and r.stage_results["intake_note"].writer_called is False)
        check("canary never echoed", _CANARY not in _blob(r))
        check("no rows written at all",
              count(f, IntakeNoteRecord) == 0 and count(f, SourceIngestionRecord) == 0
              and count(f, ReviewRecord) == 0 and count(f, AgentRunRecord) == 0)
        check("no DB connection opened", r.database_connection_made is False)
    finally:
        for tmp in tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)


def _stored_note_text(factory, model):
    s = factory()
    row = s.query(model).first()
    text = row.note_text if row is not None else None
    s.close()
    return text


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 35 governed managed-record workflow integration check")
    print("=" * 70)

    structural_checks()
    plan_only_checks()

    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("\n22+. DB-backed checks")
        print("  [skip] SQLAlchemy not installed — structural + plan-only checks only "
              "(pip install -r requirements.txt to enable)")
    else:
        db_backed_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
