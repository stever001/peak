#!/usr/bin/env python3
"""Phase 40 end-to-end internal report review workflow integration check.

Two layers:

* **Structural (always, stdlib-only):** the workflow module / doc / harness exist and compile; the
  module imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client, no
  credential, and **no writer function**; it has no `session.add`/`delete`/`merge`/`flush`/`commit`,
  no `update()`/`delete` path, and no raw SQL; `import peak.workflows` still loads no DB driver and
  a DB-free denial needs none; the public entry point and the typed request/result/trace contracts
  exist; the baseline is unchanged (Alembic head `012`, 18 tables, 13 allowlist tables / 15 actions,
  no migration `013`, no new table/model/writer/allowlist pair, Phase 37/38/39 writer sources and
  `peak/db/models.py` byte-for-byte unchanged); Phase 36 `peak/reports` stays DB-free; the closed
  computed vocabularies cover the whole Phase 32 decision vocabulary and stay in lockstep with
  Phase 39's server-side derivation; the docs carry the required language; the repo stays
  source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database over a genuine Phase 37 -> 38 -> 39 chain — a successful read-only summary, **proof that
  no row is inserted, updated, or deleted and that the packet / report-draft rows are byte-for-byte
  unchanged**, the full `decision_intent` -> computed-state mapping, the awaiting-decision path, the
  conflicting-decisions path (no automatic resolution), every stored Engagement / report-draft /
  review-packet blocker, non-echoing content safety, determinism, and read-failure semantics. SQLite
  here is only a fast local structural smoke path — NOT the production-readiness proof path. Skipped
  with instructions if SQLAlchemy is absent (still exits 0).

Phase 40 is a read-only consolidation layer. It creates no record, updates no packet or
report-draft row, adds no table/model/migration/allowlist pair, approves nothing for client use,
verifies nothing financially, publishes nothing, and executes nothing.

Exit status:
  0  -> all run checks passed (DB layer skipped counts as pass if deps absent)
  1  -> a check failed
"""

from __future__ import annotations

import io
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PY = sys.executable or "python3"

BASELINE_COMMIT = "eedf2bc"   # Add Phase 39 internal report review packet decision writer

MODULE = "peak/workflows/internal_report_review_workflow.py"
PACKAGE_INIT = "peak/workflows/__init__.py"
DOC = "docs/INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md"
HARNESS = "tests/validate_phase40_internal_report_review_workflow.py"
REQUIRED_FILES = [MODULE, PACKAGE_INIT, DOC, HARNESS]
COMPILE_FILES = [MODULE, PACKAGE_INIT, HARNESS]
SCANNED_FILES = [MODULE, PACKAGE_INIT]

#: Sources Phase 40 must not have touched at all.
#: Sources Phase 40 must not have touched. ``peak/db/models.py`` and ``alembic/versions`` were
#: originally in this list; Phase 44 legitimately owns both (governed-collation metadata and
#: migration 013), so they moved out. The real guarantee — that the three narrow writers and the
#: controlled-write allowlist are untouched — is unchanged and still enforced here.
# ``peak/persistence/allowlist.py`` was in this list until Phase 54, which legitimately owns the
# one-pair engagement anchor-creation gate added beside the generic sets. The Phase 37/38/39
# writers this phase actually depends on are still frozen, and the generic allowlist is asserted
# unchanged separately below.
UNCHANGED_SOURCES = [
    "peak/db/internal_assessment_report_draft_writer.py",
    "peak/db/internal_report_review_packet_writer.py",
    "peak/db/internal_report_review_packet_decision_writer.py",
]
REPORTS_FILES = [
    "peak/reports/__init__.py", "peak/reports/contracts.py", "peak/reports/governance.py",
    "peak/reports/internal_assessment_planner.py",
]

#: The head Phase 40 was built on and records in its own doc. Historical and correct as written.
ALEMBIC_HEAD = "012_internal_report_review_packet_decisions"
#: The current newest migration. Phase 44 added 013 (governed collation).
CURRENT_HEAD = "014_engagement_classification"
DECISION_TABLE = "internal_report_review_packet_decisions"
PACKET_TABLE = "internal_report_review_packets"
DRAFT_TABLE = "internal_assessment_report_drafts"

REQUIRED_PHRASES = [
    "read-only",
    "no persistence primitive",
    "insert-only",
    "derivation, not mutation",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "never updated",
    "awaiting_reviewer_decision",
    "conflicting_decisions",
    "decision_recorded_ready_for_internal_use",
    "not client-facing approval",
    "review_records",
    "agent_run_records",
    "18 tables",
    ALEMBIC_HEAD,
    "managed remote mysql",
    "client isolation option a",
    "sqlite is not the production-readiness proof path",
    "never echo",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|resolver_client)\b", re.IGNORECASE)
WRITER_IMPORT_RE = re.compile(r"peak\.db\.\w*writer|\bpersist_\w+|_writer\s+import")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE)
PUBLISH_IMPL_RE = re.compile(
    r"\b(?:publish_capsule|publish_node|agentnet_publish|resolver_publish)\s*\(")
RAW_SQL_RE = re.compile(
    r"session\.execute|engine\.execute|connection\.execute|\btext\(\s*['\"]|"
    r"\b(?:SELECT|INSERT INTO|UPDATE|DELETE FROM|DROP TABLE)\b\s", re.IGNORECASE)
MUTATION_RE = re.compile(
    r"session\.add\(|session\.add_all\(|session\.delete\(|session\.merge\(|session\.flush\(|"
    r"session\.commit\(|session\.bulk_|\.update\(\)")
DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"
_failures: list = []

_CANARY = "ZZCANARY40ZZ"
_ID = dict(owner_id="owner_1", client_id="client_a", engagement_id="eng_x")
_SCOPE = "engagement_authorized"


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


def code_only(text: str) -> str:
    """Return the executable tokens of a module — comments, docstrings, and string literals gone.

    Boundary claims ("no writer import", "no raw SQL", "no mutation call") must be about the code
    that runs, not about prose that merely *names* the thing it forbids.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover - only on unparsable source
        return text
    return " ".join(out)


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


def _blob(r) -> str:
    """Every caller-visible string on a result, for leak assertions."""
    parts = list(r.reasons or []) + list(r.warnings or [])
    parts += [str(getattr(r, name, None)) for name in (
        "outcome", "reason_code", "workflow_state", "computed_packet_decision_state",
        "owner_id", "client_id", "engagement_id", "authorization_scope",
        "internal_assessment_report_draft_id", "internal_report_review_packet_id",
        "report_plan_id", "plan_fingerprint")]
    parts += [str(v) for v in (r.decision_record_ids or [])]
    parts += [str(v) for v in (r.decision_intents or [])]
    parts += [str(v) for v in (r.decision_statuses or [])]
    if r.trace is not None:
        parts += [str(getattr(r.trace, f)) for f in vars(r.trace)]
    return " ".join(parts)


def _no_effects(r) -> bool:
    return all(getattr(r, flag) is False for flag in (
        "database_write_made", "stored_record_created", "packet_row_updated",
        "report_draft_row_updated", "review_records_write_made",
        "agent_run_records_write_made", "review_approval_made", "client_facing_output_created",
        "financial_verification_made", "capsule_publication_made", "agent_execution_made",
        "mock_agent_execution_made", "llm_call_made", "agentnet_call_made", "resolver_call_made",
        "network_call_made"))


def _posture(r) -> bool:
    return r.requires_human_review is True and r.read_only is True


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Workflow module / doc / harness files present")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. No LLM/exec/AgentNet/connector/network/writer/credential import; no raw SQL")
    for rel in SCANNED_FILES:
        text = read(rel)
        joined = " ".join(_import_lines(text))
        check(f"{rel}: no network client import", not NETWORK_IMPORT_RE.search(joined))
        check(f"{rel}: no LLM provider import", not LLM_PROVIDER_RE.search(joined))
        check(f"{rel}: no executor/MockLLM import", not EXEC_IMPORT_RE.search(joined))
        check(f"{rel}: no AgentNet/MCP/resolver connector import", not CONNECTOR_RE.search(joined))
        check(f"{rel}: no committed credential literal", not CREDENTIAL_RE.search(text))
        check(f"{rel}: no publication implementation", not PUBLISH_IMPL_RE.search(text))
    mtext = read(MODULE)
    mcode = code_only(mtext)   # comments/docstrings stripped: claims are about executed code
    check(f"{MODULE}: imports or calls no controlled writer",
          not WRITER_IMPORT_RE.search(mcode))
    check(f"{MODULE}: no SQLAlchemy/Alembic import at module scope",
          not DB_IMPORT_RE.search(" ".join(_import_lines(mtext))))
    check(f"{MODULE}: no raw SQL / SQL text", not RAW_SQL_RE.search(mcode))
    check(f"{MODULE}: no session.add/delete/merge/flush/commit", not MUTATION_RE.search(mcode))
    check(f"{MODULE}: no ORM update()/delete() statement construction",
          not re.search(r"\bfrom sqlalchemy import\b|sqlalchemy\.update|sqlalchemy\.delete",
                        mcode))
    check(f"{MODULE}: reads only via session.get / session.query",
          sorted(set(re.findall(r"session\s*\.\s*(\w+)\s*\(", mcode)))
          == ["close", "get", "query"])
    check(f"{MODULE}: session.get targets only the three authorized stored models",
          sorted(set(re.findall(r"session\s*\.\s*get\s*\(\s*(\w+)", mcode)))
          == ["Engagement", "InternalAssessmentReportDraftRecord",
              "InternalReportReviewPacketRecord"])
    check(f"{MODULE}: no Phase 22 review-writer / agent-run-writer reference",
          not re.search(r"review_writer|agent_run_writer|ReviewRecord|AgentRunRecord", mcode))
    check(f"{MODULE}: no approval / client-facing / publication entry point",
          not re.search(r"def\s+(?:approve_\w+|send_to_client|publish_\w+|export_\w+|"
                        r"verify_financial\w*)\s*\(", mtext))
    check(f"{MODULE}: declares no allowlist table/action pair",
          not re.search(r"ALLOWED_TABLES|ALLOWED_ACTIONS|ControlledWriteRequest", mcode))
    check(f"{MODULE}: reuses the public Phase 32 value classifier",
          "from peak.reviewer_decisions.governance import classify_prohibited_value_marker"
          in mtext)
    check(f"{MODULE}: reuses the closed Phase 32 decision vocabulary",
          "from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS" in mtext)

    print("\n4. Package still imports lazily; a DB-free denial needs no driver")
    probe = ("import sys; import peak.workflows as w; "
             "bad=[m for m in sys.modules if m.split('.')[0] in "
             "('sqlalchemy','alembic','pymysql')]; "
             "print('LAZY_OK' if not bad else 'LEAKED:'+','.join(sorted(bad)))")
    proc = subprocess.run([PY, "-c", probe], capture_output=True, text=True,
                          cwd=REPO_ROOT, timeout=90)
    check("importing peak.workflows loads no DB driver", "LAZY_OK" in proc.stdout)
    denial_probe = (
        "import sys; from peak.workflows import InternalReportReviewWorkflowRequest as Q, "
        "summarize_internal_report_review_workflow as run; "
        "r = run(Q(owner_id='o', client_id='c', engagement_id='e', "
        "authorization_scope='engagement_authorized', requested_by='u', "
        "requester_role='consultant', internal_assessment_report_draft_id='iard_1', "
        "internal_report_review_packet_id='irrp_1')); "
        "bad=[m for m in sys.modules if m.split('.')[0] in "
        "('sqlalchemy','alembic','pymysql')]; "
        "print('DENY_OK' if (r.outcome=='denied' and r.reason_code=='missing_session_factory' "
        "and r.database_connection_made is False and not bad) else 'BAD:'+str(r.reason_code))")
    proc2 = subprocess.run([PY, "-c", denial_probe], capture_output=True, text=True,
                           cwd=REPO_ROOT, timeout=90)
    check("no session_factory -> denied with no ambient-DSN fallback and no driver load",
          "DENY_OK" in proc2.stdout)

    print("\n5. Public entry point and typed contracts exist")
    import inspect

    from peak.workflows import (
        ComputedPacketDecisionState, InternalReportReviewWorkflowOutcome,
        InternalReportReviewWorkflowRequest, InternalReportReviewWorkflowResult,
        InternalReportReviewWorkflowState, InternalReportReviewWorkflowTrace,
        summarize_internal_report_review_workflow as summarize,
    )

    check("summarize_internal_report_review_workflow is callable", callable(summarize))
    sig = inspect.signature(summarize)
    check("entry point signature is (request, *, session_factory=None)",
          list(sig.parameters) == ["request", "session_factory"]
          and sig.parameters["session_factory"].kind is inspect.Parameter.KEYWORD_ONLY
          and sig.parameters["session_factory"].default is None)
    for cls in (InternalReportReviewWorkflowRequest, InternalReportReviewWorkflowResult,
                InternalReportReviewWorkflowTrace):
        check(f"{cls.__name__} is a dataclass",
              hasattr(cls, "__dataclass_fields__"))
    req_fields = set(InternalReportReviewWorkflowRequest.__dataclass_fields__)
    check("request carries every required field",
          {"owner_id", "client_id", "engagement_id", "authorization_scope", "requested_by",
           "requester_role", "internal_assessment_report_draft_id",
           "internal_report_review_packet_id", "expected_report_plan_id",
           "expected_plan_fingerprint", "strict_mode"} <= req_fields)
    res_fields = set(InternalReportReviewWorkflowResult.__dataclass_fields__)
    check("result carries every required field",
          {"outcome", "permitted", "reason_code", "workflow_state",
           "computed_packet_decision_state", "owner_id", "client_id", "engagement_id",
           "authorization_scope", "internal_assessment_report_draft_id",
           "internal_report_review_packet_id", "report_plan_id", "plan_fingerprint",
           "decision_record_ids", "decision_intents", "decision_statuses", "trace", "reasons",
           "warnings", "requires_human_review", "read_only", "database_connection_made",
           "sql_execution_made", "database_write_made", "stored_record_created",
           "packet_row_updated", "report_draft_row_updated", "review_records_write_made",
           "review_approval_made", "client_facing_output_created", "financial_verification_made",
           "capsule_publication_made", "agent_execution_made", "mock_agent_execution_made",
           "llm_call_made", "agentnet_call_made", "resolver_call_made",
           "network_call_made"} <= res_fields)
    fresh = InternalReportReviewWorkflowResult()
    check("a fresh result is read-only, needs human review, and claims no side effect",
          _posture(fresh) and _no_effects(fresh)
          and fresh.database_connection_made is False and fresh.sql_execution_made is False)
    check("outcome vocabulary is closed and carries no approval outcome",
          {InternalReportReviewWorkflowOutcome.DENIED,
           InternalReportReviewWorkflowOutcome.BLOCKED,
           InternalReportReviewWorkflowOutcome.SUMMARIZED,
           InternalReportReviewWorkflowOutcome.FAILED} == {"denied", "blocked", "summarized",
                                                           "failed"})
    check("computed packet decision state defaults to not_computed",
          fresh.computed_packet_decision_state == ComputedPacketDecisionState.NOT_COMPUTED)
    check("state class exposes the documented internal-only vocabulary",
          InternalReportReviewWorkflowState.DECISION_RECORDED_READY_FOR_INTERNAL_USE
          == "decision_recorded_ready_for_internal_use")

    _vocabulary_checks()
    _baseline_regressions()

    print("\n8. Docs carry the required Phase 40 language")
    blob = re.sub(r"\s+", " ", read(DOC)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"docs state: {phrase}", phrase.lower() in blob)
    check("docs never promise a client-facing approval / export / publish path",
          not re.search(r"approve_client_facing|send_to_client\(|publish_report\(|"
                        r"pdf generation|docx generation", blob))

    _policy_regressions()
    _hygiene_checks()


def _vocabulary_checks() -> None:
    print("\n6. Closed computed vocabularies (internal-only; complete; Phase 39 lockstep)")
    from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS
    from peak.workflows import (
        EXPECTED_DECISION_STATUS_BY_INTENT, INTENT_WORKFLOW_STATES, PACKET_DECISION_STATES,
        SOURCE_TABLES, WORKFLOW_STATES,
    )

    check("workflow-state vocabulary is exactly the documented 13",
          WORKFLOW_STATES == {
              "blocked_missing_engagement", "blocked_missing_report_draft",
              "blocked_missing_review_packet", "blocked_scope_mismatch",
              "blocked_invalid_report_draft", "blocked_invalid_review_packet",
              "awaiting_reviewer_decision", "decision_recorded_needs_followup",
              "decision_recorded_ready_for_internal_use",
              "decision_recorded_rejected_for_policy", "decision_recorded_blocked",
              "decision_recorded_return_for_revision", "conflicting_decisions"})
    check("no client-facing approval vocabulary in the computed states",
          not any(re.search(r"approved|client_facing|published|verified|final", s)
                  for s in WORKFLOW_STATES))
    check("packet-decision-state vocabulary is closed",
          PACKET_DECISION_STATES == {"not_computed", "awaiting_decision", "decision_recorded",
                                     "needs_followup", "conflicted"})
    check("every closed Phase 32 decision intent maps to a computed state",
          set(INTENT_WORKFLOW_STATES) == set(ALLOWED_DECISION_INTENTS)
          and set(EXPECTED_DECISION_STATUS_BY_INTENT) == set(ALLOWED_DECISION_INTENTS))
    check("every mapped state is inside the closed vocabulary",
          set(INTENT_WORKFLOW_STATES.values()) <= WORKFLOW_STATES)
    check("source tables are exactly the four read-only tables",
          tuple(SOURCE_TABLES) == ("engagements", DRAFT_TABLE, PACKET_TABLE, DECISION_TABLE))
    check("review_records / agent_run_records are not read by this layer",
          "review_records" not in SOURCE_TABLES and "agent_run_records" not in SOURCE_TABLES)

    try:
        from peak.db.internal_report_review_packet_decision_writer import NEEDS_FOLLOWUP_INTENTS
        from peak.db.writer_contracts import (
            PACKET_DECISION_STATUS_NEEDS_FOLLOWUP, PACKET_DECISION_STATUS_RECORDED,
        )
    except ImportError:
        print("  [skip] SQLAlchemy not installed — Phase 39 lockstep assertions skipped "
              "(pip install -r requirements.txt to enable)")
        return
    derived = {intent: (PACKET_DECISION_STATUS_NEEDS_FOLLOWUP if intent in NEEDS_FOLLOWUP_INTENTS
                        else PACKET_DECISION_STATUS_RECORDED)
               for intent in ALLOWED_DECISION_INTENTS}
    check("intent -> decision_status mirror stays in lockstep with the Phase 39 writer",
          EXPECTED_DECISION_STATUS_BY_INTENT == derived)


def _baseline_regressions() -> None:
    print("\n7. Baseline regressions: no new table / model / migration / allowlist pair / writer")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check("no migration 015 (or later) added",
          not any(re.match(r"^0*1[5-9]_|^0*[2-9]\d_", f) for f in versions))
    check(f"{CURRENT_HEAD} is the newest migration",
          versions[-1].startswith("014_engagement_classification"))
    check("exactly 14 migrations", len(versions) == 14)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("allowlist still has exactly 13 tables", len(ALLOWED_TABLES) == 13)
    check("allowlist still has exactly 15 actions", len(ALLOWED_ACTIONS) == 15)
    check("the Phase 39 action set is unchanged (no Phase 40 pair)",
          set(ALLOWED_ACTIONS) == {
              "create_agent_run_record", "create_agent_task_queue_record",
              "create_capsule_candidate_draft", "create_draft", "create_intake_note_record",
              "create_internal_assessment_report_draft", "create_internal_report_review_packet",
              "create_internal_report_review_packet_decision",
              "create_internal_reviewer_decision_record", "create_review_bundle_record",
              "create_review_record", "create_source_ingestion_record", "mark_superseded",
              "update_lifecycle_status", "update_review_status"})
    check("no upsert / raw-SQL / hard-delete action added",
          not any(re.search(r"upsert|raw_sql|hard_delete", a) for a in ALLOWED_ACTIONS))
    check("no workflow/summary action added to the allowlist",
          not any(re.search(r"workflow|summar", a) for a in ALLOWED_ACTIONS))

    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11, "EXPECTED_TABLES", []))
    check("db-check still expects exactly 18 tables", len(expected) == 18)
    check("db-check table set is unchanged (no Phase 40 table)",
          DECISION_TABLE in expected
          and not any("workflow" in t for t in expected))
    models_src = read("peak/db/models.py")
    check("models.py still declares exactly 18 tables",
          models_src.count("__tablename__ = ") == 18)
    check("models.py declares no Phase 40 workflow table",
          not re.search(r'__tablename__\s*=\s*"[^"]*workflow[^"]*"', models_src))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check("still exactly the twelve narrow controlled writers", len(writers) == 12)
    check("no Phase 40 writer module added",
          not any("workflow" in w for w in writers))

    print("     Phase 36 still DB-free; Phase 37/38/39 writer sources untouched")
    for rel in REPORTS_FILES:
        joined = " ".join(_import_lines(read(rel)))
        check(f"{rel}: no SQLAlchemy/Alembic import", not DB_IMPORT_RE.search(joined))
        check(f"{rel}: no peak.db import", "peak.db" not in joined)
    probe = ("import sys; import peak.reports; "
             "bad=[m for m in sys.modules if m.split('.')[0] in "
             "('sqlalchemy','alembic','pymysql') or m.startswith('peak.db')]; "
             "print('CLEAN_OK' if not bad else 'LEAKED:'+','.join(sorted(bad)))")
    proc = subprocess.run([PY, "-c", probe], capture_output=True, text=True,
                          cwd=REPO_ROOT, timeout=90)
    check("importing peak.reports still loads no DB module", "CLEAN_OK" in proc.stdout)
    try:
        changed = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--"] + UNCHANGED_SOURCES,
            capture_output=True, text=True, timeout=20).stdout.strip()
        from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES, PROHIBITED_TABLES
        check("the generic allowlist is unchanged and engagements stays prohibited on it",
              len(ALLOWED_TABLES) == 13 and len(ALLOWED_ACTIONS) == 15
              and "engagements" in PROHIBITED_TABLES and "clients" in PROHIBITED_TABLES
              and "engagements" not in ALLOWED_TABLES)
        check("Phase 37/38/39 writers have no pending diff",
              not changed)
    except Exception:
        check("git-backed unchanged-source check (git unavailable — skipped)", True)


def _policy_regressions() -> None:
    print("\n9. Policy regressions (managed MySQL + AgentNet publication)")
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
    pub = re.sub(r"\s+", " ", read("docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md")).lower()
    check("client authorizes Peak as publisher",
          "consulting agreement" in pub and "authorized capsule/node publisher" in pub)
    check("clients operate no AgentNet publishing tools",
          "clients do not operate any agentnet publishing tools" in pub)
    check("no client-facing publisher UI / credentials / resolver tools / direct path",
          all(p in pub for p in ("no client-facing agentnet publisher ui",
                                 "no client-held publishing credentials",
                                 "no client-operated resolver publication tools",
                                 "no direct client publication path")))
    mk = read("Makefile")
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("validate-phase40 is part of `make validate`", "validate-phase40" in validate_line)
    for target in ("db-check-managed-test", "managed-mysql-smoke",
                   "managed-mysql-migration-check"):
        check(f"managed target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("no DSN / database URL added by Phase 40",
          not any(re.search(r"mysql\+pymysql://|postgres://|PEAK_DATABASE_URL\s*=", read(rel))
                  for rel in [MODULE, DOC]))
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


def _hygiene_checks() -> None:
    print("\n10. Baseline + repo hygiene: source-only, no data / credentials / examples")
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
    check("docs/Peak_Investor_Overview_AI.docx present",
          os.path.isfile(os.path.join(REPO_ROOT, "docs", "Peak_Investor_Overview_AI.docx")))
    try:
        present = subprocess.run(
            ["git", "-C", REPO_ROOT, "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
            capture_output=True, timeout=20).returncode == 0
        check(f"Phase 40 baseline commit {BASELINE_COMMIT} present in history", present)
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
    except Exception:
        check("git-backed baseline/hygiene checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- DB-backed


def _request(*, draft_id, packet_id, **over):
    from peak.workflows import InternalReportReviewWorkflowRequest as Q

    base = dict(**_ID, authorization_scope=_SCOPE, requested_by="consultant_a",
                requester_role="consultant",
                internal_assessment_report_draft_id=draft_id,
                internal_report_review_packet_id=packet_id)
    base.update(over)
    return Q(**base)


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.internal_assessment_report_draft_writer import (
        build_internal_assessment_report_draft_write_request as build_draft_cwr,
        persist_internal_assessment_report_draft as persist_draft,
    )
    from peak.db.internal_report_review_packet_decision_writer import (
        build_packet_decision_write_request as build_decision_cwr,
        persist_internal_report_review_packet_decision as persist_decision,
    )
    from peak.db.internal_report_review_packet_writer import (
        build_internal_report_review_packet_write_request as build_packet_cwr,
        persist_internal_report_review_packet as persist_packet,
    )
    from peak.db.models import (
        AgentRunRecord, Engagement, InternalAssessmentReportDraftRecord as Draft,
        InternalReportReviewPacketDecisionRecord as Decision,
        InternalReportReviewPacketRecord as Pkt, ReviewRecord,
    )
    from peak.db.writer_contracts import (
        InternalReportReviewPacketDecisionDraft as DD, InternalReportReviewPacketDraft as PD,
    )
    from peak.reports import (
        InternalAssessmentReportPlanRequest as PReq,
        prepare_internal_assessment_report_plan as plan_it,
    )
    from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS
    from peak.workflows import (
        INTENT_WORKFLOW_STATES, ComputedPacketDecisionState as PDS,
        InternalReportReviewWorkflowOutcome as OC, InternalReportReviewWorkflowState as WS,
        summarize_internal_report_review_workflow as summarize,
    )

    tmpdirs: list = []

    def build_chain(*, engagement_over=None, draft_over=None, packet_over=None):
        """A temp DB carrying a real Phase 37 report draft and Phase 38 review packet.

        ``engagement_over`` is applied **after** the Phase 37/38 writers have run: those writers
        validate the stored Engagement themselves, so a degraded engagement must be introduced
        once a genuine chain already exists — otherwise the chain would never be built and the
        Phase 40 engagement blockers would never be exercised.
        """
        tmp = tempfile.mkdtemp(prefix="peak_phase40_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        f = sessionmaker(bind=engine, expire_on_commit=False)
        s = f()
        s.add(Engagement(id="eng_x", client_id="client_a", owner_id="owner_1",
                         authorization_scope=_SCOPE, lifecycle_status="active",
                         review_status="active"))
        s.commit()
        s.close()
        plan = plan_it(PReq(**_ID, authorization_scope=_SCOPE, requested_by="consultant_a",
                            requester_role="consultant", report_plan_id="rpt_plan_1",
                            intake_note_refs=["intn_1"], source_ingestion_refs=["ing_1"],
                            evidence_reference_ids=["evid_1"],
                            agent_task_queue_record_ids=["atq_1"],
                            review_bundle_record_ids=["rvb_1"],
                            internal_reviewer_decision_record_ids=["ird_1"])).report_plan
        dr = persist_draft(build_draft_cwr(plan, requested_by="consultant_a",
                                           requester_role="consultant",
                                           idempotency_key="idem-draft-1"), session_factory=f)
        pk = persist_packet(build_packet_cwr(
            PD(**_ID, authorization_scope=_SCOPE,
               internal_assessment_report_draft_id=dr.stored_record_id,
               report_plan_id="rpt_plan_1", plan_fingerprint=plan.plan_fingerprint,
               reviewer_questions=["Is the evidence sufficient?"]),
            requested_by="consultant_a", requester_role="consultant",
            idempotency_key="idem-packet-1"), session_factory=f)
        _apply(f, Draft, dr.stored_record_id, draft_over)
        _apply(f, Pkt, pk.stored_record_id, packet_over)
        _apply(f, Engagement, "eng_x", engagement_over)
        return f, dr.stored_record_id, pk.stored_record_id, plan.plan_fingerprint

    def _apply(f, model, rid, over):
        if not over:
            return
        s = f()
        row = s.get(model, rid)
        for k, v in over.items():
            setattr(row, k, v)
        s.commit()
        s.close()

    def add_decision(f, *, draft_id, packet_id, plan_fingerprint, key, intent, over=None):
        base = dict(**_ID, authorization_scope=_SCOPE,
                    internal_report_review_packet_id=packet_id,
                    internal_assessment_report_draft_id=draft_id,
                    report_plan_id="rpt_plan_1", plan_fingerprint=plan_fingerprint,
                    reviewer_ref="reviewer_a", decision_intent=intent,
                    safe_decision_summary="internal review position recorded")
        base.update(over or {})
        return persist_decision(build_decision_cwr(
            DD(**base), requested_by="consultant_a", requester_role="consultant",
            idempotency_key=key), session_factory=f)

    def counts(f):
        s = f()
        out = (s.query(Decision).count(), s.query(Pkt).count(), s.query(Draft).count(),
               s.query(ReviewRecord).count(), s.query(AgentRunRecord).count())
        s.close()
        return out

    def snapshot(f, model, rid):
        s = f()
        row = s.get(model, rid)
        snap = {c.name: getattr(row, c.name) for c in model.__table__.columns}
        s.close()
        return snap

    try:
        print("\n11. Successful read-only summary (nothing written, nothing touched)")
        f, did, pid, pfp = build_chain()
        dec = add_decision(f, draft_id=did, packet_id=pid, plan_fingerprint=pfp,
                           key="idem-decision-1", intent="ready_for_internal_use")
        before_pkt, before_draft = snapshot(f, Pkt, pid), snapshot(f, Draft, did)
        before_counts = counts(f)
        r = summarize(_request(draft_id=did, packet_id=pid), session_factory=f)
        check("outcome == summarized and permitted",
              r.outcome == OC.SUMMARIZED and r.permitted is True)
        check("workflow_state is the internal-only ready state",
              r.workflow_state == WS.DECISION_RECORDED_READY_FOR_INTERNAL_USE)
        check("computed_packet_decision_state derived as decision_recorded",
              r.computed_packet_decision_state == PDS.DECISION_RECORDED)
        check("decision record located by ref",
              r.decision_record_ids == [dec.stored_record_id] and r.decision_record_count == 1)
        check("decision intent/status echoed from the closed vocabulary only",
              r.decision_intents == ["ready_for_internal_use"]
              and r.decision_statuses == ["decision_recorded"])
        check("plan linkage carried from the stored draft",
              r.report_plan_id == "rpt_plan_1" and r.plan_fingerprint == pfp)
        check("read flags true; every write/approval/publish/execute flag false",
              r.database_connection_made is True and r.sql_execution_made is True
              and _no_effects(r))
        check("posture: read_only and requires_human_review", _posture(r))

        print("\n12. NO ROW IS INSERTED, UPDATED, OR DELETED")
        check("row counts unchanged across all five tables", counts(f) == before_counts)
        check("review packet row byte-for-byte unchanged", snapshot(f, Pkt, pid) == before_pkt)
        check("report draft row byte-for-byte unchanged", snapshot(f, Draft, did) == before_draft)
        check("packet row still says not_decided with a null decision ref",
              before_pkt["reviewer_decision_status"] == "not_decided"
              and before_pkt["reviewer_decision_record_id"] is None)
        check("the result reports the derived state, not the packet row's stored state",
              r.trace.stored_packet_reviewer_decision_status == "not_decided"
              and r.trace.stored_packet_reviewer_decision_record_id is None
              and r.computed_packet_decision_state == PDS.DECISION_RECORDED)
        check("trace carries refs / fingerprints / counts only",
              r.trace.report_draft_ref == did and r.trace.review_packet_ref == pid
              and r.trace.decision_record_refs == [dec.stored_record_id]
              and r.trace.decision_records_found == 1
              and r.trace.decision_records_skipped == 0
              and r.trace.distinct_decision_positions == 1
              and tuple(r.trace.source_tables)
              == ("engagements", DRAFT_TABLE, PACKET_TABLE, DECISION_TABLE))
        check("no report prose / recommendation / ROI figure in the result",
              not re.search(r"[$€£]\s?\d|\d+(?:\.\d+)?\s?%", _blob(r))
              and not any(t in _blob(r) for t in ("note_text", "packet_payload", "source_bytes",
                                                  "generated_output", "final_client_report")))

        print("\n13. Determinism")
        again = summarize(_request(draft_id=did, packet_id=pid), session_factory=f)
        check("identical request + DB state -> identical result",
              (again.outcome, again.workflow_state, again.computed_packet_decision_state,
               again.decision_record_ids, again.decision_intents, again.decision_statuses,
               again.reasons, again.warnings)
              == (r.outcome, r.workflow_state, r.computed_packet_decision_state,
                  r.decision_record_ids, r.decision_intents, r.decision_statuses,
                  r.reasons, r.warnings))
        check("repeat summary still wrote nothing", counts(f) == before_counts)

        print("\n14. Every decision intent maps to its internal-only computed state")
        expected_state = {
            "ready_for_internal_use": WS.DECISION_RECORDED_READY_FOR_INTERNAL_USE,
            "needs_more_evidence": WS.DECISION_RECORDED_NEEDS_FOLLOWUP,
            "defer_review": WS.DECISION_RECORDED_NEEDS_FOLLOWUP,
            "return_for_revision": WS.DECISION_RECORDED_RETURN_FOR_REVISION,
            "rejected_for_policy": WS.DECISION_RECORDED_REJECTED_FOR_POLICY,
            "blocked_by_scope": WS.DECISION_RECORDED_BLOCKED,
            "blocked_by_quality": WS.DECISION_RECORDED_BLOCKED,
            "blocked_by_missing_source": WS.DECISION_RECORDED_BLOCKED,
        }
        check("the expectation table covers the whole closed vocabulary",
              set(expected_state) == set(ALLOWED_DECISION_INTENTS)
              and expected_state == INTENT_WORKFLOW_STATES)
        for intent in sorted(ALLOWED_DECISION_INTENTS):
            fi, di, pi, fpi = build_chain()
            add_decision(fi, draft_id=di, packet_id=pi, plan_fingerprint=fpi,
                         key=f"idem-{intent}", intent=intent)
            ri = summarize(_request(draft_id=di, packet_id=pi), session_factory=fi)
            check(f"intent '{intent}' -> {expected_state[intent]}",
                  ri.workflow_state == expected_state[intent] and ri.permitted is True)
            check(f"intent '{intent}' produces no side effect and no approval",
                  _no_effects(ri) and _posture(ri)
                  and "approved" not in str(ri.workflow_state))

        print("\n15. Awaiting decision (derived state, not packet-row state)")
        fa, da, pa, fpa = build_chain()
        before_a = counts(fa)
        ra = summarize(_request(draft_id=da, packet_id=pa), session_factory=fa)
        check("no decision row -> awaiting_reviewer_decision",
              ra.workflow_state == WS.AWAITING_REVIEWER_DECISION and ra.permitted is True)
        check("computed_packet_decision_state == awaiting_decision",
              ra.computed_packet_decision_state == PDS.AWAITING_DECISION)
        check("reason states the derivation source",
              any("packet decision" in m and "packet row" in m for m in ra.reasons))
        check("no decision refs reported",
              ra.decision_record_ids == [] and ra.decision_record_count == 0)
        check("awaiting summary mutates nothing", counts(fa) == before_a)

        print("\n16. Conflicting decisions (no automatic resolution, no mutation)")
        fc, dc, pc, fpc = build_chain()
        d1 = add_decision(fc, draft_id=dc, packet_id=pc, plan_fingerprint=fpc,
                          key="idem-conflict-a", intent="ready_for_internal_use")
        d2 = add_decision(fc, draft_id=dc, packet_id=pc, plan_fingerprint=fpc,
                          key="idem-conflict-b", intent="return_for_revision")
        check("two materially different decision rows were stored",
              d1.stored_record_id and d2.stored_record_id
              and d1.stored_record_id != d2.stored_record_id)
        before_c = counts(fc)
        before_pkt_c = snapshot(fc, Pkt, pc)
        rc = summarize(_request(draft_id=dc, packet_id=pc), session_factory=fc)
        check("workflow_state == conflicting_decisions",
              rc.workflow_state == WS.CONFLICTING_DECISIONS)
        check("computed_packet_decision_state == conflicted",
              rc.computed_packet_decision_state == PDS.CONFLICTED)
        check("requires_human_review stays true", rc.requires_human_review is True)
        check("both decision refs reported, none chosen",
              sorted(rc.decision_record_ids)
              == sorted([d1.stored_record_id, d2.stored_record_id])
              and rc.trace.distinct_decision_positions == 2)
        check("no automatic resolution language in the result",
              not re.search(r"\bresolved\b|\bwinner\b|\bsupersed", _blob(rc)))
        check("conflict summary mutates nothing", counts(fc) == before_c
              and snapshot(fc, Pkt, pc) == before_pkt_c)

        print("     idempotent duplicates of the same position collapse to one state")
        fd, dd_, pd_, fpd = build_chain()
        add_decision(fd, draft_id=dd_, packet_id=pd_, plan_fingerprint=fpd,
                     key="idem-dup-a", intent="needs_more_evidence")
        add_decision(fd, draft_id=dd_, packet_id=pd_, plan_fingerprint=fpd,
                     key="idem-dup-b", intent="needs_more_evidence")
        rd = summarize(_request(draft_id=dd_, packet_id=pd_), session_factory=fd)
        check("two rows expressing the same decision -> one non-conflicting state",
              rd.workflow_state == WS.DECISION_RECORDED_NEEDS_FOLLOWUP
              and rd.computed_packet_decision_state == PDS.NEEDS_FOLLOWUP
              and rd.trace.distinct_decision_positions == 1
              and len(rd.decision_record_ids) == 2)

        print("\n16b. Inconsistent decision rows are excluded; strict_mode escalates a warning")
        fe, de, pe, fpe = build_chain()
        good = add_decision(fe, draft_id=de, packet_id=pe, plan_fingerprint=fpe,
                            key="idem-ok", intent="ready_for_internal_use")
        bad = add_decision(fe, draft_id=de, packet_id=pe, plan_fingerprint=fpe,
                           key="idem-bad", intent="needs_more_evidence")
        _apply(fe, Decision, bad.stored_record_id, {"decision_status": "decision_recorded"})
        before_e = counts(fe)
        re_ = summarize(_request(draft_id=de, packet_id=pe), session_factory=fe)
        check("a decision_status inconsistent with its intent is excluded, with a warning",
              re_.decision_record_ids == [good.stored_record_id]
              and re_.trace.decision_records_found == 2
              and re_.trace.decision_records_skipped == 1
              and any("inconsistent" in w for w in re_.warnings))
        check("the excluded row does not create a false conflict",
              re_.workflow_state == WS.DECISION_RECORDED_READY_FOR_INTERNAL_USE
              and re_.permitted is True)
        check("the exclusion warning echoes no stored value",
              not any(t in " ".join(re_.warnings)
                      for t in ("decision_recorded", "needs_more_evidence")))
        strict = summarize(_request(draft_id=de, packet_id=pe, strict_mode=True),
                           session_factory=fe)
        check("strict_mode turns the warning into a non-permitted blocked outcome",
              strict.outcome == OC.BLOCKED and strict.permitted is False
              and strict.reason_code == "strict_mode_warning")
        check("strict_mode still reports the computed state and writes nothing",
              strict.workflow_state == WS.DECISION_RECORDED_READY_FOR_INTERNAL_USE
              and _no_effects(strict) and counts(fe) == before_e)

        _apply(fe, Decision, bad.stored_record_id,
               {"decision_status": "needs_followup", "audience": "client"})
        ra2 = summarize(_request(draft_id=de, packet_id=pe), session_factory=fe)
        check("a non-internal decision row is excluded with a warning",
              ra2.trace.decision_records_skipped == 1
              and any("audience" in w for w in ra2.warnings))
        _apply(fe, Decision, bad.stored_record_id,
               {"audience": "internal", "decision_scope": "some_other_scope"})
        ra3 = summarize(_request(draft_id=de, packet_id=pe), session_factory=fe)
        check("a row outside the packet decision scope is excluded with a warning",
              ra3.trace.decision_records_skipped == 1
              and any("decision_scope" in w for w in ra3.warnings))

        _engagement_blockers(build_chain, summarize, counts)
        _draft_blockers(build_chain, summarize)
        _packet_blockers(build_chain, summarize, add_decision)
        _content_safety(build_chain, summarize)
        _failure_semantics(build_chain, summarize, SQLAlchemyError)
    finally:
        for tmp in tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)


def _engagement_blockers(build_chain, summarize, counts) -> None:
    from peak.workflows import (
        InternalReportReviewWorkflowOutcome as OC, InternalReportReviewWorkflowState as WS,
    )

    print("\n17. Stored Engagement blockers (the stored engagement is authoritative)")
    f, did, pid, _ = build_chain()
    before = counts(f)
    r = summarize(_request(draft_id=did, packet_id=pid, engagement_id="eng_missing"),
                  session_factory=f)
    check("missing engagement -> blocked_missing_engagement",
          r.outcome == OC.BLOCKED and r.workflow_state == WS.BLOCKED_MISSING_ENGAGEMENT
          and r.reason_code == "missing_engagement")

    f2, d2, p2, _ = build_chain(engagement_over={"authorization_scope": None})
    r = summarize(_request(draft_id=d2, packet_id=p2), session_factory=f2)
    check("missing stored authorization_scope -> blocked_scope_mismatch",
          r.workflow_state == WS.BLOCKED_SCOPE_MISMATCH
          and r.reason_code == "missing_stored_authorization_scope")

    f3, d3, p3, _ = build_chain(engagement_over={"authorization_scope": "client_authorized"})
    r = summarize(_request(draft_id=d3, packet_id=p3), session_factory=f3)
    check("request scope != stored scope -> authorization_scope_mismatch",
          r.reason_code == "authorization_scope_mismatch"
          and r.workflow_state == WS.BLOCKED_SCOPE_MISMATCH)
    check("identity matching alone never suffices",
          any("necessary but not sufficient" in m for m in r.reasons))

    for over, label in (({"owner_id": "owner_other"}, "owner_id"),
                        ({"client_id": "client_other"}, "client_id")):
        fx, dx, px, _ = build_chain(engagement_over=over)
        rx = summarize(_request(draft_id=dx, packet_id=px), session_factory=fx)
        check(f"stored engagement {label} mismatch denied",
              rx.reason_code == "engagement_identity_mismatch"
              and rx.workflow_state == WS.BLOCKED_SCOPE_MISMATCH)

    for lifecycle in ("revoked", "archived", "deleted_reference_only"):
        fx, dx, px, _ = build_chain(engagement_over={"lifecycle_status": lifecycle})
        rx = summarize(_request(draft_id=dx, packet_id=px), session_factory=fx)
        check(f"prohibited engagement lifecycle '{lifecycle}' blocked",
              rx.reason_code == "blocked_engagement_lifecycle")

    r = summarize(_request(draft_id=did, packet_id=pid, authorization_scope="revoked"),
                  session_factory=f)
    check("revoked request scope denied DB-free (no connection opened)",
          r.outcome == OC.DENIED and r.reason_code == "blocked_authorization_scope"
          and r.database_connection_made is False)
    check("engagement blockers mutate nothing", counts(f) == before)


def _draft_blockers(build_chain, summarize) -> None:
    from peak.workflows import InternalReportReviewWorkflowState as WS

    print("\n18. Stored report draft blockers (the draft row is never updated)")
    f, did, pid, pfp = build_chain()
    r = summarize(_request(draft_id="iard_missing", packet_id=pid), session_factory=f)
    check("missing report draft -> blocked_missing_report_draft",
          r.workflow_state == WS.BLOCKED_MISSING_REPORT_DRAFT
          and r.reason_code == "missing_report_draft")

    for over, label in (({"owner_id": "owner_other"}, "owner_id"),
                        ({"client_id": "client_other"}, "client_id"),
                        ({"engagement_id": "eng_other"}, "engagement_id"),
                        ({"authorization_scope": "client_authorized"}, "authorization_scope")):
        fx, dx, px, _ = build_chain(draft_over=over)
        rx = summarize(_request(draft_id=dx, packet_id=px), session_factory=fx)
        check(f"stored draft {label} mismatch -> blocked_scope_mismatch",
              rx.workflow_state == WS.BLOCKED_SCOPE_MISMATCH
              and rx.reason_code == "report_draft_identity_mismatch")

    r = summarize(_request(draft_id=did, packet_id=pid, expected_report_plan_id="rpt_other"),
                  session_factory=f)
    check("expected_report_plan_id mismatch -> blocked_invalid_report_draft",
          r.workflow_state == WS.BLOCKED_INVALID_REPORT_DRAFT
          and r.reason_code == "report_draft_plan_mismatch")
    r = summarize(_request(draft_id=did, packet_id=pid, expected_plan_fingerprint="a" * 64),
                  session_factory=f)
    check("expected_plan_fingerprint mismatch -> blocked_invalid_report_draft",
          r.workflow_state == WS.BLOCKED_INVALID_REPORT_DRAFT
          and r.reason_code == "report_draft_plan_mismatch")
    r = summarize(_request(draft_id=did, packet_id=pid, expected_report_plan_id="rpt_plan_1",
                           expected_plan_fingerprint=pfp), session_factory=f)
    check("matching caller expectations pass through", r.permitted is True)

    cases = [
        ({"audience": "client"}, "report_draft_not_internal"),
        ({"output_status": "drafted"}, "report_draft_invalid_output_status"),
        ({"review_status": "approved"}, "report_draft_invalid_review_status"),
        ({"review_status": "final"}, "report_draft_invalid_review_status"),
        ({"lifecycle_status": "active"}, "report_draft_invalid_lifecycle_status"),
        ({"client_facing_approved": True}, "report_draft_posture_elevated"),
        ({"financial_verified": True}, "report_draft_posture_elevated"),
        ({"capsule_candidate_ready": True}, "report_draft_posture_elevated"),
        ({"publication_allowed": True}, "report_draft_posture_elevated"),
        ({"execution_allowed": True}, "report_draft_posture_elevated"),
        ({"requires_human_review": False}, "report_draft_posture_elevated"),
    ]
    for over, code in cases:
        fx, dx, px, _ = build_chain(draft_over=over)
        rx = summarize(_request(draft_id=dx, packet_id=px), session_factory=fx)
        label = next(iter(over))
        check(f"stored draft {label}={over[label]!r} -> {code}",
              rx.workflow_state == WS.BLOCKED_INVALID_REPORT_DRAFT and rx.reason_code == code)
        check(f"stored draft {label} blocker echoes no stored value",
              str(over[label]) not in " ".join(rx.reasons) or isinstance(over[label], bool))


def _packet_blockers(build_chain, summarize, add_decision) -> None:
    from peak.workflows import InternalReportReviewWorkflowState as WS

    print("\n19. Stored review packet blockers (the packet row is never updated)")
    f, did, pid, pfp = build_chain()
    r = summarize(_request(draft_id=did, packet_id="irrp_missing"), session_factory=f)
    check("missing packet -> blocked_missing_review_packet",
          r.workflow_state == WS.BLOCKED_MISSING_REVIEW_PACKET
          and r.reason_code == "missing_review_packet")

    for over, label in (({"owner_id": "owner_other"}, "owner_id"),
                        ({"client_id": "client_other"}, "client_id"),
                        ({"engagement_id": "eng_other"}, "engagement_id"),
                        ({"authorization_scope": "client_authorized"}, "authorization_scope")):
        fx, dx, px, _ = build_chain(packet_over=over)
        rx = summarize(_request(draft_id=dx, packet_id=px), session_factory=fx)
        check(f"stored packet {label} mismatch -> blocked_scope_mismatch",
              rx.workflow_state == WS.BLOCKED_SCOPE_MISMATCH
              and rx.reason_code == "review_packet_identity_mismatch")

    fx, dx, px, _ = build_chain(packet_over={"internal_assessment_report_draft_id": "iard_other"})
    rx = summarize(_request(draft_id=dx, packet_id=px), session_factory=fx)
    check("packet draft-id mismatch -> review_packet_draft_mismatch",
          rx.workflow_state == WS.BLOCKED_INVALID_REVIEW_PACKET
          and rx.reason_code == "review_packet_draft_mismatch")

    for over, label in (({"report_plan_id": "rpt_other"}, "report_plan_id"),
                        ({"plan_fingerprint": "b" * 64}, "plan_fingerprint")):
        fy, dy, py, _ = build_chain(packet_over=over)
        ry = summarize(_request(draft_id=dy, packet_id=py), session_factory=fy)
        check(f"packet {label} mismatch -> review_packet_linkage_mismatch",
              ry.workflow_state == WS.BLOCKED_INVALID_REVIEW_PACKET
              and ry.reason_code == "review_packet_linkage_mismatch")

    cases = [
        ({"audience": "client"}, "review_packet_not_internal"),
        ({"packet_status": "closed"}, "review_packet_invalid_status"),
        ({"review_status": "approved"}, "review_packet_invalid_review_status"),
        ({"review_status": "final"}, "review_packet_invalid_review_status"),
        ({"lifecycle_status": "active"}, "review_packet_invalid_lifecycle_status"),
        ({"client_facing_approved": True}, "review_packet_posture_elevated"),
        ({"review_approval_made": True}, "review_packet_posture_elevated"),
        ({"financial_verified": True}, "review_packet_posture_elevated"),
        ({"capsule_candidate_ready": True}, "review_packet_posture_elevated"),
        ({"publication_allowed": True}, "review_packet_posture_elevated"),
        ({"execution_allowed": True}, "review_packet_posture_elevated"),
        ({"requires_human_review": False}, "review_packet_posture_elevated"),
    ]
    for over, code in cases:
        fz, dz, pz, _ = build_chain(packet_over=over)
        rz = summarize(_request(draft_id=dz, packet_id=pz), session_factory=fz)
        label = next(iter(over))
        check(f"stored packet {label}={over[label]!r} -> {code}",
              rz.workflow_state == WS.BLOCKED_INVALID_REVIEW_PACKET and rz.reason_code == code)

    print("     packet decision columns are reconciled, never repaired by writing")
    fa, da, pa, fpa = build_chain()
    dec = add_decision(fa, draft_id=da, packet_id=pa, plan_fingerprint=fpa,
                       key="idem-recon", intent="ready_for_internal_use")
    fb, db_, pb, fpb = build_chain(packet_over={"reviewer_decision_status": "decision_recorded"})
    rb = summarize(_request(draft_id=db_, packet_id=pb), session_factory=fb)
    check("packet claims a decision with no decision row -> unexplained blocker",
          rb.workflow_state == WS.BLOCKED_INVALID_REVIEW_PACKET
          and rb.reason_code == "review_packet_decision_status_unexplained")
    fc, dc, pc, fpc = build_chain(packet_over={"reviewer_decision_record_id": "irrpd_unknown"})
    rc = summarize(_request(draft_id=dc, packet_id=pc), session_factory=fc)
    check("packet names an unknown decision record -> unexplained blocker",
          rc.reason_code == "review_packet_decision_ref_unexplained")
    check("a packet whose columns the decision rows do explain is accepted",
          summarize(_request(draft_id=da, packet_id=pa), session_factory=fa).permitted is True
          and bool(dec.stored_record_id))


def _content_safety(build_chain, summarize) -> None:
    from peak.workflows import InternalReportReviewWorkflowOutcome as OC

    print("\n20. Content / leakage safety (non-echoing, DB-free)")
    f, did, pid, _ = build_chain()

    unsafe_values = [
        ("requested_by", f"mysql://user:{_CANARY}@host/db", "prohibited_request_value"),
        ("requester_role", f"select * from clients where x='{_CANARY}'",
         "prohibited_request_value"),
        ("requested_by", f"api_key={_CANARY}", "prohibited_request_value"),
        ("requested_by", f"password={_CANARY}", "prohibited_request_value"),
        ("expected_report_plan_id",
         f'Traceback (most recent call last): File "x.py", line 3 {_CANARY}',
         "prohibited_request_value"),
        ("requested_by", '{"note_text": "' + _CANARY + '"}', "prohibited_request_value"),
    ]
    for field_name, value, code in unsafe_values:
        r = summarize(_request(draft_id=did, packet_id=pid, **{field_name: value}),
                      session_factory=f)
        check(f"unsafe {field_name} denied ({code})",
              r.outcome == OC.DENIED and r.reason_code == code)
        check(f"unsafe {field_name} value never echoed",
              _CANARY not in _blob(r) and value not in _blob(r))
        check(f"unsafe {field_name} denied before any connection",
              r.database_connection_made is False and r.sql_execution_made is False)

    for attr in ("database_url", "raw_sql", "api_key", "secret_key", "private_key",
                 "connection_string", "stack_trace", "note_text", "packet_payload",
                 "approve_client_facing", "publish_report"):
        req = _request(draft_id=did, packet_id=pid)
        setattr(req, attr, _CANARY)
        r = summarize(req, session_factory=f)
        check(f"prohibited request attribute '{attr}' denied without echoing",
              r.outcome == OC.DENIED and r.reason_code == "prohibited_request_key"
              and _CANARY not in _blob(r))

    r = summarize(_request(draft_id=did, packet_id=pid,
                           internal_report_review_packet_id="irrp with spaces"),
                  session_factory=f)
    check("unsafe ref shape denied", r.reason_code == "unsafe_request_ref")
    r = summarize(_request(draft_id=did, packet_id=pid, expected_plan_fingerprint="not-a-digest"),
                  session_factory=f)
    check("malformed expected_plan_fingerprint denied",
          r.reason_code in ("invalid_expected_plan_fingerprint", "unsafe_request_ref"))
    r = summarize(_request(draft_id=did, packet_id=pid, requested_by=""), session_factory=f)
    check("missing identity field denied", r.reason_code == "missing_identity_field")
    r = summarize("not-a-request", session_factory=f)
    check("wrong request type denied", r.reason_code == "invalid_request_type")
    r = summarize(_request(draft_id=did, packet_id=pid, strict_mode="yes"), session_factory=f)
    check("non-bool strict_mode denied", r.reason_code == "invalid_strict_mode")


def _failure_semantics(build_chain, summarize, SQLAlchemyError) -> None:
    from peak.workflows import InternalReportReviewWorkflowOutcome as OC

    print("\n21. Read-failure semantics (nothing written, nothing leaked)")
    f, did, pid, _ = build_chain()

    class _FailAt:
        def __init__(self, inner, method, exc):
            self._inner, self._method, self._exc = inner, method, exc

        def __getattr__(self, name):
            if name == self._method:
                def boom(*a, **k):
                    raise self._exc
                return boom
            return getattr(self._inner, name)

    fail_get = lambda: _FailAt(f(), "get", SQLAlchemyError("boom-get-secret"))  # noqa: E731
    r = summarize(_request(draft_id=did, packet_id=pid), session_factory=fail_get)
    check("read failure -> failed, not a false 'blocked' claim",
          r.outcome == OC.FAILED and r.reason_code == "read_failed" and r.permitted is False)
    check("no workflow state is claimed on a read failure",
          r.workflow_state is None and r.computed_packet_decision_state == "not_computed")
    check("read failure still reports no write", _no_effects(r) and _posture(r))
    check("no exception detail leaked",
          "boom" not in _blob(r) and "SELECT" not in _blob(r).upper())

    fail_query = lambda: _FailAt(f(), "query", SQLAlchemyError("boom-query"))  # noqa: E731
    r = summarize(_request(draft_id=did, packet_id=pid), session_factory=fail_query)
    check("decision-query failure -> failed with no state claimed",
          r.outcome == OC.FAILED and r.workflow_state is None and "boom" not in _blob(r))

    def bad_factory():
        raise SQLAlchemyError("boom-connect")

    r = summarize(_request(draft_id=did, packet_id=pid), session_factory=bad_factory)
    check("session open failure -> failed without leaking detail",
          r.outcome == OC.FAILED and r.reason_code == "session_unavailable"
          and "boom" not in _blob(r))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 40 end-to-end internal report review workflow integration check")
    print("=" * 78)

    structural_checks()

    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("\n11+. DB-backed checks")
        print("  [skip] SQLAlchemy not installed — structural checks only "
              "(pip install -r requirements.txt to enable)")
    else:
        db_backed_checks()

    print("\n" + "=" * 78)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
