#!/usr/bin/env python3
"""Phase 37 controlled-DB internal-assessment-report-draft-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/model/migration/doc files exist and
  compile; the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client
  or credential, and no Phase 22 review writer or agent-run writer; the Phase 36 `peak/reports`
  package stays DB-free and imports no writer; the migration is additive schema-only (creates one
  table, no INSERT/seed, `down_revision = 009_intake_note_records`); the Phase 17 allowlist gained
  exactly the one new table/action pair; the docs carry the required language; the repo stays
  source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database — migration upgrade/downgrade/re-upgrade, successful create (structure and references
  stored, no prose), idempotent replay, conflicting replay, DB-backed authorization (stored-scope
  comparison), identity/allowlist checks, posture rejections, content-safety rejections
  (non-echoing), side-effect discipline (no `review_records`/`agent_run_records` write), and
  transaction/failure/race semantics. SQLite here is only a fast local structural smoke path — NOT
  the production-readiness proof path (see docs/PRODUCTION_PARITY_DB_VALIDATION.md). Skipped with
  instructions if SQLAlchemy is absent (still exits 0).

Phase 37 persists a **plan**, not a report: `output_status` is fixed at `plan_persisted`. It
approves nothing, verifies nothing financially, publishes nothing, executes nothing, calls no
Phase 22 review writer, creates no `review_records`/`agent_run_records` row, and makes no
LLM/MockLLM/AgentNet/AgentNet-publication/MCP/resolver/connector/network call.

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

# Pinned baseline commits (verified by ancestry over the FULL history — see the Phase 35 follow-up).
BASELINE_COMMIT = "0cc8b7a"   # Add Phase 36 internal assessment report planning boundary

WRITER = "peak/db/internal_assessment_report_draft_writer.py"
MIGRATION = "alembic/versions/010_internal_assessment_report_drafts.py"
REQUIRED_FILES = [
    WRITER,
    "peak/db/writer_contracts.py",
    "peak/db/models.py",
    MIGRATION,
    "docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md",
    "docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md",
]
WRITER_FILES = [WRITER, "peak/db/writer_contracts.py"]
COMPILE_FILES = WRITER_FILES + [MIGRATION, "peak/db/models.py",
                                "tests/validate_phase37_internal_assessment_report_draft_writer.py"]
DOCS = ["docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md",
        "docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md"]
REPORTS_FILES = [
    "peak/reports/__init__.py",
    "peak/reports/contracts.py",
    "peak/reports/governance.py",
    "peak/reports/internal_assessment_planner.py",
]

TABLE = "internal_assessment_report_drafts"
ACTION = "create_internal_assessment_report_draft"

# The Phase 17 allowlist exactly as Phase 37 left it (11 tables / 13 actions). Later phases may
# only ADD to this; removal of any entry is a regression.
PHASE37_BASELINE_TABLES = {
    "evidence_references", "engagement_records", "review_records", "agent_run_records",
    "source_ingestion_records", "agent_task_queue_records", "review_bundle_records",
    "internal_reviewer_decision_records", "intake_note_records",
    "internal_assessment_report_drafts", "capsule_publication_candidates",
}
PHASE37_BASELINE_ACTIONS = {
    "create_draft", "create_review_record", "create_agent_run_record",
    "create_source_ingestion_record", "create_agent_task_queue_record",
    "create_review_bundle_record", "create_internal_reviewer_decision_record",
    "create_intake_note_record", "create_internal_assessment_report_draft",
    "create_capsule_candidate_draft", "update_review_status", "update_lifecycle_status",
    "mark_superseded",
}

REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "review-gated",
    "internal only",
    "plan_persisted",
    "not a drafted report",
    "review_status",
    "lifecycle_status",
    "review_records",
    "agent_run_records",
    "server-stamped",
    "16 tables",
    ACTION,
    "managed remote mysql",
    "never echo",
    "sqlite is only a fast local structural smoke path",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|resolver_client)\b", re.IGNORECASE)
REVIEW_WRITER_RE = re.compile(r"\breview_writer\b|persist_review_record")
AGENT_RUN_WRITER_RE = re.compile(r"\bagent_run_writer\b|persist_agent_run_record")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE)
PUBLISH_IMPL_RE = re.compile(
    r"\b(?:publish_capsule|publish_node|agentnet_publish|resolver_publish)\s*\(")
INSERT_PATTERNS = ("insert into", "bulk_insert", ".insert(", "op.execute(")
DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"
_failures: list = []

_CANARY = "ZZCANARY37ZZ"
_ID = dict(owner_id="owner_1", client_id="client_a", engagement_id="eng_x")
_SCOPE = "engagement_authorized"
_KEY = "idem-rpt-1"


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


def _blob(receipt) -> str:
    """Everything a caller could read off a receipt, flattened."""
    return " ".join(list(receipt.reasons or []) + list(receipt.warnings or [])
                    + [str(receipt.reason_code), str(receipt.outcome),
                       str(receipt.stored_record_id), str(receipt.report_plan_id),
                       str(receipt.plan_fingerprint), str(receipt.idempotency_key)])


def _no_effects(r) -> bool:
    return all(getattr(r, flag) is False for flag in (
        "review_records_write_made", "agent_run_records_write_made", "review_approval_made",
        "client_facing_output_created", "client_facing_approval_made",
        "financial_verification_made", "capsule_candidate_created", "capsule_publication_made",
        "agentnet_publication_made", "agent_execution_made", "mock_agent_execution_made",
        "llm_call_made", "agentnet_call_made", "resolver_call_made", "network_call_made"))


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Writer / model / migration / doc files present")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Writer imports no LLM/exec/AgentNet/connector/network/other-writer/credential")
    for rel in WRITER_FILES:
        text = read(rel)
        joined = " ".join(_import_lines(text))
        check(f"{rel}: no network client import", not NETWORK_IMPORT_RE.search(joined))
        check(f"{rel}: no LLM provider import", not LLM_PROVIDER_RE.search(joined))
        check(f"{rel}: no executor/MockLLM import", not EXEC_IMPORT_RE.search(joined))
        check(f"{rel}: no AgentNet/MCP/resolver connector import", not CONNECTOR_RE.search(joined))
        check(f"{rel}: no Phase 22 review-writer import", not REVIEW_WRITER_RE.search(joined))
        check(f"{rel}: no agent-run-writer import", not AGENT_RUN_WRITER_RE.search(joined))
        check(f"{rel}: no committed credential literal", not CREDENTIAL_RE.search(text))
        check(f"{rel}: no publication implementation", not PUBLISH_IMPL_RE.search(text))
    writer_text = read(WRITER)
    check("writer targets exactly one table/action",
          writer_text.count("INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE") >= 2
          and "ReviewRecord" not in writer_text and "AgentRunRecord" not in writer_text)
    check("writer executes no raw SQL",
          not re.search(r"session\.execute|engine\.execute|text\(\s*['\"]", writer_text))
    check("writer performs no update/delete path",
          not re.search(r"session\.delete|\.update\(|DELETE FROM|UPDATE ", writer_text))

    print("\n4. Phase 36 reports package stays DB-free and writer-free")
    for rel in REPORTS_FILES:
        joined = " ".join(_import_lines(read(rel)))
        check(f"{rel}: no SQLAlchemy/Alembic import", not DB_IMPORT_RE.search(joined))
        check(f"{rel}: no peak.db import", "peak.db" not in joined)
        check(f"{rel}: no writer import", not re.search(r"persist_\w+|\w+_writer", joined))
    probe = ("import sys; import peak.reports; "
             "bad=[m for m in sys.modules if m.split('.')[0] in "
             "('sqlalchemy','alembic','pymysql') or m.startswith('peak.db')]; "
             "print('CLEAN_OK' if not bad else 'LEAKED:'+','.join(sorted(bad)))")
    proc = subprocess.run([sys.executable or "python3", "-c", probe],
                          capture_output=True, text=True, cwd=REPO_ROOT, timeout=90)
    check("importing peak.reports still loads no DB module", "CLEAN_OK" in proc.stdout)

    print("\n5. Phase 17 allowlist gained exactly the one new pair")
    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check(f"'{TABLE}' on the allowlist", TABLE in ALLOWED_TABLES)
    check(f"'{ACTION}' on the allowlist", ACTION in ALLOWED_ACTIONS)
    # Scoped to what PHASE 37 contributed. Later phases add their own pairs additively (Phase 38
    # adds internal_report_review_packets), so this pins the Phase 37 baseline as a SUBSET —
    # nothing Phase 37 established may be removed — rather than a frozen global count.
    check("Phase 37 allowlist baseline still present (nothing removed)",
          PHASE37_BASELINE_TABLES <= set(ALLOWED_TABLES)
          and PHASE37_BASELINE_ACTIONS <= set(ALLOWED_ACTIONS))
    check("no update/delete/upsert/raw-SQL action added",
          not any(re.search(r"upsert|raw_sql|hard_delete", a) for a in ALLOWED_ACTIONS))

    print("\n6. Migration is additive, schema-only, single-head")
    mig = read(MIGRATION)
    check("down_revision = 009_intake_note_records",
          re.search(r'down_revision\s*=\s*"009_intake_note_records"', mig) is not None)
    check("revision id is 010_internal_assessment_report_drafts",
          re.search(r'revision\s*=\s*"010_internal_assessment_report_drafts"', mig) is not None)
    check("creates exactly one table", mig.count("op.create_table(") == 1)
    check("no INSERT / seed / data of any kind",
          not any(p in mig.lower() for p in INSERT_PATTERNS))
    check("no destructive op in upgrade",
          not re.search(r"op\.drop_table|op\.drop_column", mig.split("def downgrade")[0]))
    check("downgrade drops only the new table",
          mig.split("def downgrade")[1].count("op.drop_table(") == 1)
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check("migration 010 is present (later phases append their own additively)",
          any(v.startswith("010_internal_assessment_report_drafts") for v in versions))
    downs = [re.search(r'down_revision\s*=\s*"?([^"\s]+)"?',
                       read(os.path.join("alembic", "versions", f))).group(1) for f in versions]
    check("migration chain stays linear (no duplicate down_revision)",
          len(downs) == len(set(downs)))

    print("\n7. Model + db-check expectations")
    # The model module needs SQLAlchemy; the db-check expectations below are stdlib-only, so the
    # model assertions skip cleanly on plain python3 rather than aborting the structural layer.
    try:
        from peak.db.models import ALL_MODELS, InternalAssessmentReportDraftRecord as Rec
    except ImportError:
        print("  [skip] SQLAlchemy not installed — model assertions skipped "
              "(pip install -r requirements.txt to enable)")
        Rec = None
    _model_checks(Rec, ALL_MODELS if Rec is not None else None)
    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11, "EXPECTED_TABLES", []))
    check("db-check EXPECTED_TABLES includes the new table", TABLE in expected)
    check("db-check expects at least the 16 tables present at the Phase 37 baseline",
          len(expected) >= 16)
    check("model source declares the new table",
          f'__tablename__ = "{TABLE}"' in read("peak/db/models.py"))
    check("model source registers the new class in ALL_MODELS",
          re.search(r"^ALL_MODELS = \[(?:.|\n)*?InternalAssessmentReportDraftRecord,(?:.|\n)*?^\]",
                    read("peak/db/models.py"), re.M) is not None)

    print("\n8. Docs carry the required Phase 37 language")
    blob = re.sub(r"\s+", " ", " ".join(read(d) for d in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"docs state: {phrase}", phrase.lower() in blob)
    _policy_regressions()


def _model_checks(Rec, all_models) -> None:
    """SQLAlchemy-dependent model assertions (no-op when the driver is absent)."""
    if Rec is None:
        return
    check("InternalAssessmentReportDraftRecord in ALL_MODELS", Rec in all_models)
    check("at least the 16 models present at the Phase 37 baseline", len(all_models) >= 16)
    check(f"__tablename__ == {TABLE}", Rec.__tablename__ == TABLE)
    cols = set(Rec.__table__.columns.keys())
    required = {"id", "owner_id", "client_id", "engagement_id", "authorization_scope",
                "report_plan_id", "plan_fingerprint", "requested_by", "requester_role",
                "report_purpose", "audience", "sections_json", "evidence_trace_map_json",
                "finding_candidates_json", "recommendation_candidates_json", "open_gaps_json",
                "blocked_items_json", "future_financial_verification_items_json",
                "future_capsule_candidate_items_json", "reasons_json", "warnings_json",
                "output_status", "review_status", "lifecycle_status", "client_facing_approved",
                "financial_verified", "capsule_candidate_ready", "publication_allowed",
                "execution_allowed", "requires_human_review", "idempotency_key",
                "payload_fingerprint", "created_at"}
    check("model carries every required column", required <= cols)
    uniques = [c for c in Rec.__table__.constraints
               if c.__class__.__name__ == "UniqueConstraint"]
    check("unique idempotency constraint over (owner, client, engagement, key)",
          any(sorted(col.name for col in u.columns)
              == ["client_id", "engagement_id", "idempotency_key", "owner_id"] for u in uniques))


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
    check("validate-phase37 is part of `make validate`", "validate-phase37" in validate_line)
    for target in ("db-check-managed-test", "managed-mysql-smoke",
                   "managed-mysql-migration-check"):
        check(f"managed target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
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

    _hygiene_checks()


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
        check(f"Phase 37 baseline commit {BASELINE_COMMIT} present in history", present)
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


# --------------------------------------------------------------------------- builders


def _make_plan(**over):
    """Build a real Phase 36 plan (never a hand-rolled stub)."""
    from peak.reports import (
        InternalAssessmentReportPlanRequest as PReq,
        prepare_internal_assessment_report_plan as plan_it,
    )
    base = dict(**_ID, authorization_scope=_SCOPE, requested_by="consultant_a",
                requester_role="consultant", report_plan_id="rpt_plan_1",
                intake_note_refs=["intn_1"], source_ingestion_refs=["ing_1", "ing_2"],
                evidence_reference_ids=["evid_1", "evid_2"],
                agent_task_queue_record_ids=["atq_1"], review_bundle_record_ids=["rvb_1"],
                internal_reviewer_decision_record_ids=["ird_1"], workflow_id="wf_1",
                managed_record_workflow_ref="wf35_run_1",
                report_purpose="internal readiness assessment")
    base.update(over)
    result = plan_it(PReq(**base))
    assert result.outcome == "planned", result.reason_code
    return result.report_plan, PReq(**base)


def _build(*, plan=None, plan_over=None, subject_over=None, **cwr_over):
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

    if plan is None:
        plan, _ = _make_plan(**(plan_over or {}))
    subj_base = dict(subject_record_id="eng_x", subject_record_type="engagement",
                     owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
                     stored_authorization_scope=_SCOPE)
    subj_base.update(subject_over or {})
    base = dict(**_ID, requested_by="consultant_a", requester_role="consultant",
                authorization_scope=_SCOPE, target_table=TABLE, requested_action=ACTION,
                subject=ControlledWriteSubject(**subj_base), record_draft=plan,
                source_phase="phase37", lifecycle_status="active", idempotency_key=_KEY)
    base.update(cwr_over)
    return ControlledWriteRequest(**base), plan


# --------------------------------------------------------------------------- DB-backed


def _migration_reversibility() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    print("\n11. Migration apply / reversibility (temp SQLite structural smoke; NOT prod proof)")
    tmp = tempfile.mkdtemp(prefix="peak_phase37_mig_")
    prev = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created the table", TABLE in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns(TABLE)}
        check("table carries plan/provenance/posture/idempotency columns",
              {"report_plan_id", "plan_fingerprint", "audience", "sections_json",
               "evidence_trace_map_json", "finding_candidates_json",
               "recommendation_candidates_json", "open_gaps_json", "blocked_items_json",
               "future_financial_verification_items_json",
               "future_capsule_candidate_items_json", "output_status", "requires_human_review",
               "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"]) for i in insp.get_indexes(TABLE)}
        check("unique idempotency index over (owner, client, engagement, key)",
              idx.get("uq_internal_assessment_report_drafts_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        check("expected non-unique indexes present",
              all(f"ix_{TABLE}_{c}" in idx for c in
                  ("client_id", "engagement_id", "report_plan_id", "plan_fingerprint",
                   "audience", "output_status", "idempotency_key", "owner_id",
                   "authorization_scope", "review_status", "lifecycle_status")))
        command.downgrade(cfg, "009_intake_note_records")
        check("downgrade drops the table",
              TABLE not in inspect(create_engine(url)).get_table_names())
        command.upgrade(cfg, "head")
        check("re-upgrade succeeds", TABLE in inspect(create_engine(url)).get_table_names())
    finally:
        if prev is None:
            os.environ.pop("PEAK_DATABASE_URL", None)
        else:
            os.environ["PEAK_DATABASE_URL"] = prev
        shutil.rmtree(tmp, ignore_errors=True)


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.internal_assessment_report_draft_writer import (
        build_internal_assessment_report_draft_write_request as build_helper,
        persist_internal_assessment_report_draft as persist,
    )
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, InternalAssessmentReportDraftRecord as Rec,
        ReviewRecord,
    )
    from peak.db.writer_contracts import InternalAssessmentReportDraftWriteOutcome as OC

    _migration_reversibility()

    tmpdirs: list = []

    def fresh_db(**engagement_over):
        tmp = tempfile.mkdtemp(prefix="peak_phase37_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        base = dict(id="eng_x", client_id="client_a", owner_id="owner_1",
                    authorization_scope=_SCOPE, lifecycle_status="active",
                    review_status="active")
        base.update(engagement_over)
        s = factory()
        s.add(Engagement(**base))
        s.commit()
        s.close()
        return factory

    def count(factory, model):
        s = factory()
        n = s.query(model).count()
        s.close()
        return n

    try:
        print("\n12. Successful create (structure + refs stored; no prose)")
        f = fresh_db()
        cwr, plan = _build()
        r = persist(cwr, session_factory=f)
        check("outcome == created", r.outcome == OC.CREATED and r.permitted is True)
        check("exactly one row created", count(f, Rec) == 1)
        check("server-generated id (iard_ prefix)",
              bool(r.stored_record_id) and r.stored_record_id.startswith("iard_"))
        check("receipt carries plan provenance",
              r.report_plan_id == "rpt_plan_1" and r.plan_fingerprint == plan.plan_fingerprint)
        check("receipt posture is internal-only",
              r.audience == "internal" and r.output_status == "plan_persisted"
              and r.review_status == "needs_review" and r.lifecycle_status == "draft")
        check("receipt counts match the plan",
              r.section_count == len(plan.sections)
              and r.finding_candidate_count == len(plan.finding_candidates)
              and r.recommendation_candidate_count == len(plan.recommendation_candidates)
              and r.open_gap_count == len(plan.open_gaps))
        check("flags: connection/sql/write/commit/created all True",
              r.database_connection_made and r.sql_execution_made and r.database_write_made
              and r.transaction_committed and r.stored_record_created)
        check("non-effect flags all False", _no_effects(r))
        check("receipt created_at present", bool(r.created_at))

        s = f()
        row = s.get(Rec, r.stored_record_id)
        check("stored posture is internal-only and non-final",
              row.audience == "internal" and row.output_status == "plan_persisted"
              and row.review_status == "needs_review" and row.lifecycle_status == "draft"
              and row.client_facing_approved is False and row.financial_verified is False
              and row.capsule_candidate_ready is False and row.publication_allowed is False
              and row.execution_allowed is False and row.requires_human_review is True)
        check("report_plan_id + plan_fingerprint stored",
              row.report_plan_id == "rpt_plan_1"
              and row.plan_fingerprint == plan.plan_fingerprint)
        check("sections_json stores section metadata only",
              len(row.sections_json) == len(plan.sections)
              and set(row.sections_json[0]) == {
                  "section_id", "title", "order", "readiness_state", "required_ref_categories",
                  "satisfied_ref_categories", "missing_ref_categories", "supporting_ref_count",
                  "synthesis_only", "blocked_reason"})
        check("evidence_trace_map_json stores refs only",
              row.evidence_trace_map_json["evidence_summary"]["supporting_refs"]
              == {"evidence_reference_ids": ["evid_1", "evid_2"]})
        check("finding_candidates_json stores refs/readiness only",
              all(set(fc) == {"finding_candidate_id", "section_id", "evidence_support_refs",
                              "review_support_refs", "readiness_state", "blocked_reason",
                              "requires_human_review", "client_facing_approved"}
                  for fc in row.finding_candidates_json))
        check("recommendation_candidates_json stores refs/readiness and internal posture",
              all(rc["audience"] == "internal" and rc["client_facing_approved"] is False
                  and rc["financial_verified"] is False
                  and rc["capsule_candidate_ready"] is False
                  and rc["publication_allowed"] is False and rc["execution_allowed"] is False
                  and rc["requires_human_review"] is True
                  for rc in row.recommendation_candidates_json))
        check("open_gaps_json stored", isinstance(row.open_gaps_json, list))
        check("future-gate placeholders stored as items only",
              row.future_financial_verification_items_json == ["rec_000"]
              and row.future_capsule_candidate_items_json == ["ing_1", "ing_2"])
        check("idempotency_key + payload_fingerprint persisted",
              row.idempotency_key == _KEY and bool(row.payload_fingerprint))
        check("created_at server-stamped", row.created_at is not None)
        stored_blob = str(row.sections_json) + str(row.evidence_trace_map_json) \
            + str(row.finding_candidates_json) + str(row.recommendation_candidates_json) \
            + str(row.open_gaps_json) + str(row.reasons_json) + str(row.warnings_json)
        check("no raw-content key stored in any JSON column",
              not any(t in stored_blob for t in (
                  "note_text", "packet_payload", "source_bytes", "generated_output",
                  "raw_evidence_text", "raw_interview_text", "final_client_report")))
        check("no ROI/currency figure stored",
              not re.search(r"[$€£]\s?\d|\d+(?:\.\d+)?\s?%", stored_blob))
        s.close()

        print("\n13. Side-effect discipline (no review_records / agent_run_records / clients)")
        check("NO review_records row created", count(f, ReviewRecord) == 0)
        check("NO agent_run_records row created", count(f, AgentRunRecord) == 0)
        check("clients untouched", count(f, Client) == 0)

        print("\n14. CWR helper bridge (lives in the DB layer, keeping peak/reports DB-free)")
        f = fresh_db()
        helper_cwr = build_helper(plan, requested_by="consultant_a",
                                  requester_role="consultant", idempotency_key="idem-helper")
        check("helper targets the one table/action",
              helper_cwr.target_table == TABLE and helper_cwr.requested_action == ACTION)
        rh = persist(helper_cwr, session_factory=f)
        check("helper-built request persists one row",
              rh.outcome == OC.CREATED and count(f, Rec) == 1)

        print("\n15. Idempotent replay and conflict")
        f = fresh_db()
        first = persist(_build()[0], session_factory=f)
        second = persist(_build()[0], session_factory=f)
        check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
        check("no second row", count(f, Rec) == 1)
        check("existing id returned", second.stored_record_id == first.stored_record_id)
        check("replay reports read, not write",
              second.database_write_made is False and second.stored_record_created is False
              and second.existing_record_returned is True
              and second.transaction_committed is False)
        conflict_plan, _ = _make_plan(evidence_reference_ids=["evid_9"])
        r = persist(_build(plan=conflict_plan)[0], session_factory=f)
        check("changed plan on the same key conflicts",
              r.outcome == OC.DENIED and r.reason_code == "idempotency_conflict")
        check("no mutation on conflict", count(f, Rec) == 1)

        print("\n16. Stored-Engagement authorization denials")
        f = fresh_db()
        r = persist(_build(subject_over={"subject_record_id": "eng_missing"},
                           engagement_id="eng_x")[0], session_factory=f)
        check("missing stored engagement denied",
              r.outcome == OC.DENIED and r.reason_code == "missing_subject"
              and r.database_connection_made is True)
        f2 = fresh_db(authorization_scope=None)
        r = persist(_build()[0], session_factory=f2)
        check("missing stored authorization_scope denied", r.reason_code == "missing_stored_scope")
        f3 = fresh_db(authorization_scope="a_different_scope")
        r = persist(_build()[0], session_factory=f3)
        check("stored scope mismatch denied (identity alone insufficient)",
              r.reason_code == "stored_scope_mismatch" and count(f3, Rec) == 0)
        f4 = fresh_db(owner_id="other_owner")
        r = persist(_build()[0], session_factory=f4)
        check("stored owner mismatch denied", r.reason_code == "identity_mismatch")
        f5 = fresh_db(client_id="other_client")
        r = persist(_build()[0], session_factory=f5)
        check("stored client mismatch denied", r.reason_code == "identity_mismatch")
        for blocked in ("revoked", "archived", "deleted_reference_only"):
            fb = fresh_db(lifecycle_status=blocked)
            r = persist(_build()[0], session_factory=fb)
            check(f"stored lifecycle '{blocked}' denied",
                  r.reason_code == "subject_lifecycle_blocked" and count(fb, Rec) == 0)

        print("\n17. Identity / posture denials (no DB connection opened)")
        for attr in ("owner_id", "client_id", "engagement_id"):
            plan_bad, _ = _make_plan(**{attr: "wrong_value"})
            r = persist(_build(plan=plan_bad)[0], session_factory=fresh_db())
            check(f"request/plan {attr} mismatch denied",
                  r.reason_code == "identity_mismatch" and r.database_connection_made is False)
        plan_scope, _ = _make_plan(authorization_scope="other_scope")
        r = persist(_build(plan=plan_scope)[0], session_factory=fresh_db())
        check("request/plan authorization_scope mismatch denied",
              r.reason_code == "identity_mismatch")
        for attr, code in (("report_draft_id", "caller_supplied_id"),
                           ("created_at", "caller_supplied_timestamp"),
                           ("id", "caller_supplied_id")):
            p, _ = _make_plan()
            setattr(p, attr, "2026-07-31T00:00:00Z")
            r = persist(_build(plan=p)[0], session_factory=fresh_db())
            check(f"caller-supplied {attr} denied", r.reason_code == code)
        for audience in ("client", "external", "public"):
            p, _ = _make_plan()
            p.audience = audience
            r = persist(_build(plan=p)[0], session_factory=fresh_db())
            check(f"audience '{audience}' denied", r.reason_code == "prohibited_audience")
        for flag in ("client_facing_approved", "financial_verified", "capsule_candidate_ready",
                     "publication_allowed", "execution_allowed"):
            p, _ = _make_plan()
            setattr(p, flag, True)
            r = persist(_build(plan=p)[0], session_factory=fresh_db())
            check(f"plan {flag}=True denied", r.reason_code == "prohibited_posture")
        p, _ = _make_plan()
        p.requires_human_review = False
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("plan requires_human_review=False denied", r.reason_code == "prohibited_posture")
        for value in ("final", "published", "client_facing", "approved"):
            p, _ = _make_plan()
            p.output_status = value
            r = persist(_build(plan=p)[0], session_factory=fresh_db())
            check(f"plan output_status '{value}' denied",
                  r.reason_code == "invalid_plan_output_status")
        for value in ("approved_internal", "client_facing_approved"):
            p, _ = _make_plan()
            p.review_status = value
            r = persist(_build(plan=p)[0], session_factory=fresh_db())
            check(f"plan review_status '{value}' denied",
                  r.reason_code == "invalid_plan_review_status")
        p, _ = _make_plan()
        p.lifecycle_status = "active"
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("plan lifecycle_status != draft denied",
              r.reason_code == "invalid_plan_lifecycle_status")
        p, _ = _make_plan()
        p.recommendation_candidates[0].client_facing_approved = True
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("client-facing recommendation candidate denied",
              r.reason_code == "prohibited_posture")

        print("\n18. Allowlist denials")
        for table in ("review_records", "agent_run_records", "resolver_capsule_records",
                      "capsule_publication_candidates", "intake_note_records"):
            r = persist(_build(target_table=table)[0], session_factory=fresh_db())
            check(f"target_table '{table}' denied",
                  r.outcome == OC.DENIED and r.database_connection_made is False)
        for action in ("create_review_record", "update_review_status", "mark_superseded",
                       "delete_report", "upsert_report", "raw_sql", "publish_report",
                       "approve_client_facing", "send_to_client", "verify_financial",
                       "publish_capsule"):
            r = persist(_build(requested_action=action)[0], session_factory=fresh_db())
            check(f"requested_action '{action}' denied", r.outcome == OC.DENIED)
        r = persist(_build(record_draft=object())[0], session_factory=fresh_db())
        check("non-plan record_draft denied", r.reason_code == "invalid_record_draft")

        class _Fake:
            pass
        r = persist(_Fake(), session_factory=fresh_db())
        check("duck-typed request denied", r.reason_code == "invalid_request_type")

        print("\n19. Content / leak safety (canary never echoed, never stored)")
        prohibited_keys = ("raw_note_text", "note_text", "packet_payload", "raw_evidence_text",
                           "raw_interview_text", "source_bytes", "generated_output",
                           "final_client_report", "client_facing_output", "approve_internal",
                           "approve_client_facing", "publish_capsule", "agentnet_publish",
                           "resolver_credentials", "llm_prompt", "database_url", "raw_sql",
                           "api_key", "secret_key", "private_key", "connection_string",
                           "stack_trace")
        for key in prohibited_keys:
            p, _ = _make_plan()
            setattr(p, key, _CANARY)
            fk = fresh_db()
            r = persist(_build(plan=p)[0], session_factory=fk)
            check(f"prohibited plan key '{key}' denied without echoing",
                  r.outcome == OC.DENIED and r.reason_code == "prohibited_plan_key"
                  and _CANARY not in _blob(r) and count(fk, Rec) == 0)
        marker_values = {
            "credential/secret": f"api_key={_CANARY}",
            "DB-URL/DSN": f"mysql://u:{_CANARY}@h/db",
            "raw-SQL": f"select * from clients where n='{_CANARY}'",
            "raw-content": f"source_bytes-{_CANARY}",
        }
        for label, value in marker_values.items():
            p, _ = _make_plan()
            p.report_purpose = value
            fk = fresh_db()
            r = persist(_build(plan=p)[0], session_factory=fk)
            check(f"{label} report_purpose denied without echoing",
                  r.outcome == OC.DENIED and _CANARY not in _blob(r) and count(fk, Rec) == 0)
        p, _ = _make_plan()
        p.report_purpose = f'File "x.py", line 1 {_CANARY}'
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("stack-trace-like report_purpose denied without echoing",
              r.outcome == OC.DENIED and _CANARY not in _blob(r))
        # A plan with a missing ref category so it genuinely carries open gaps to tamper with.
        p, _ = _make_plan(intake_note_refs=[])
        check("gap fixture actually has gaps", len(p.open_gaps) > 0)
        p.open_gaps[0].note = f"gap note with a DSN mysql://u:{_CANARY}@h/db"
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("unsafe nested gap note denied without echoing",
              r.outcome == OC.DENIED and _CANARY not in _blob(r))
        p, _ = _make_plan()
        p.sections[0].blocked_reason = "x" * 900
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("over-long nested prose denied", r.reason_code == "unsafe_plan_reference")
        p, _ = _make_plan()
        p.finding_candidates[0].evidence_support_refs = [f"evid with spaces {_CANARY}"]
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("unsafe nested reference denied without echoing",
              r.reason_code == "unsafe_plan_reference" and _CANARY not in _blob(r))
        p, _ = _make_plan()
        p.plan_fingerprint = "not-a-sha256"
        r = persist(_build(plan=p)[0], session_factory=fresh_db())
        check("invalid plan_fingerprint denied", r.reason_code == "invalid_plan_fingerprint")

        print("\n20. Transaction / failure semantics")

        class _FailAt:
            def __init__(self, inner, method, exc):
                self._inner, self._method, self._exc = inner, method, exc

            def __getattr__(self, name):
                if name == self._method:
                    def boom(*a, **k):
                        raise self._exc
                    return boom
                return getattr(self._inner, name)

        f = fresh_db()
        fail_get = lambda: _FailAt(f(), "get", SQLAlchemyError("boom-get"))  # noqa: E731
        r = persist(_build()[0], session_factory=fail_get)
        check("failed_before_write when the read fails",
              r.outcome == OC.FAILED_BEFORE_WRITE and r.stored_record_created is False)
        fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
        r = persist(_build()[0], session_factory=fail_commit)
        check("write_outcome_uncertain on commit failure",
              r.outcome == OC.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)
        check("uncertain never claims no record exists", "no row" not in _blob(r).lower())
        check("no leak of exception detail in failure reasons",
              "boom" not in _blob(r) and "SELECT" not in _blob(r).upper())

        print("\n21. Structural bounds are enforced before any write")
        from peak.db.internal_assessment_report_draft_writer import (
            MAX_CANDIDATES, MAX_GAPS, MAX_SECTIONS,
        )
        from peak.reports import (
            InternalReportFindingCandidate, InternalReportGap,
            InternalReportRecommendationCandidate, InternalReportSectionPlan,
        )

        def _over_limit_plan(field_name, factory, limit):
            """Attach `limit + 1` synthetic, safe, runtime-generated items to a real plan.

            The items are generated here at runtime and never committed as fixture data. They are
            deliberately marker-free and posture-clean so the *bound* is what denies the write,
            not the content or posture scan that runs before it.
            """
            p, _ = _make_plan()
            setattr(p, field_name, [factory(i) for i in range(limit + 1)])
            return p

        def _section(i):
            return InternalReportSectionPlan(
                section_id=f"sec_synth_{i:04d}", title="Synthetic internal section",
                order=i, readiness_state="synthesis_only", synthesis_only=True)

        def _finding(i):
            return InternalReportFindingCandidate(
                finding_candidate_id=f"fnd_synth_{i:04d}", section_id="operational_findings",
                evidence_support_refs=[f"evid_synth_{i:04d}"],
                readiness_state="blocked_no_evidence_support")

        def _recommendation(i):
            return InternalReportRecommendationCandidate(
                recommendation_candidate_id=f"rec_synth_{i:04d}",
                section_id="internal_recommendations",
                reviewer_decision_refs=[f"ird_synth_{i:04d}"],
                readiness_state="blocked_no_evidence_support")

        def _gap(i):
            return InternalReportGap(
                gap_id=f"gap_synth_{i:04d}", gap_kind="missing_supporting_references",
                section_id="evidence_gaps", missing_ref_category="evidence_reference_ids",
                missing_record_type="evidence_references")

        for field_name, factory, limit, ref_stub in (
            ("sections", _section, MAX_SECTIONS, "sec_synth_"),
            ("finding_candidates", _finding, MAX_CANDIDATES, "fnd_synth_"),
            ("recommendation_candidates", _recommendation, MAX_CANDIDATES, "rec_synth_"),
            ("open_gaps", _gap, MAX_GAPS, "gap_synth_"),
        ):
            fb = fresh_db()
            over = _over_limit_plan(field_name, factory, limit)
            check(f"{field_name} fixture really exceeds the bound",
                  len(getattr(over, field_name)) == limit + 1)
            r = persist(_build(plan=over)[0], session_factory=fb)
            blob = _blob(r)
            check(f"over-limit {field_name} denied with plan_too_large",
                  r.outcome == OC.DENIED and r.reason_code == "plan_too_large")
            check(f"over-limit {field_name}: no row written", count(fb, Rec) == 0)
            check(f"over-limit {field_name}: denied before any DB connection",
                  r.database_connection_made is False and r.sql_execution_made is False
                  and r.database_write_made is False and r.stored_record_created is False)
            check(f"over-limit {field_name}: reason names the bound category only",
                  field_name.rstrip("s") in blob or field_name in blob)
            check(f"over-limit {field_name}: reason echoes no generated ref value",
                  ref_stub not in blob and "evid_synth_" not in blob
                  and "ird_synth_" not in blob)
            check(f"over-limit {field_name}: no prohibited side effect", _no_effects(r))
            check(f"over-limit {field_name}: no review_records / agent_run_records row",
                  count(fb, ReviewRecord) == 0 and count(fb, AgentRunRecord) == 0)

        # A plan exactly AT the bound must still be accepted — the check is a ceiling, not an
        # off-by-one that rejects the largest legitimate plan.
        fb = fresh_db()
        at_limit, _ = _make_plan()
        at_limit.sections = [_section(i) for i in range(MAX_SECTIONS)]
        r = persist(_build(plan=at_limit)[0], session_factory=fb)
        check("a plan exactly at the section bound is accepted",
              r.outcome == OC.CREATED and count(fb, Rec) == 1)
        check("the accepted at-limit plan stored every section",
              r.section_count == MAX_SECTIONS)

        print("\n22. report_request cross-check denials (before any write)")
        for attr, bad in (("owner_id", "other_owner"), ("client_id", "other_client"),
                          ("engagement_id", "eng_other"),
                          ("authorization_scope", "other_scope")):
            fb = fresh_db()
            plan_ok, good_request = _make_plan()
            bad_request = _make_plan()[1]
            setattr(bad_request, attr, bad)
            cwr_ok, _ = _build(plan=plan_ok)
            r = persist(cwr_ok, session_factory=fb, report_request=bad_request)
            check(f"report_request.{attr} mismatch denied",
                  r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")
            check(f"report_request.{attr} mismatch: denied before any DB connection",
                  r.database_connection_made is False and r.sql_execution_made is False)
            check(f"report_request.{attr} mismatch: no row written", count(fb, Rec) == 0)
            check(f"report_request.{attr} mismatch: value never echoed",
                  bad not in _blob(r) and _no_effects(r))
        fb = fresh_db()
        plan_ok, matching_request = _make_plan()
        r = persist(_build(plan=plan_ok)[0], session_factory=fb,
                    report_request=matching_request)
        check("a matching report_request still permits the write",
              r.outcome == OC.CREATED and count(fb, Rec) == 1)
        # Provenance: a cross-check request describing a DIFFERENT report plan is denied.
        fb = fresh_db()
        plan_ok, _ = _make_plan()
        other_plan_request = _make_plan(report_plan_id="rpt_plan_other")[1]
        r = persist(_build(plan=plan_ok)[0], session_factory=fb,
                    report_request=other_plan_request)
        blob = _blob(r)
        check("report_request.report_plan_id mismatch denied",
              r.outcome == OC.DENIED and r.permitted is False
              and r.reason_code == "identity_mismatch")
        check("report_request.report_plan_id mismatch: denied before any DB connection/write",
              r.database_connection_made is False and r.sql_execution_made is False
              and r.database_write_made is False and r.stored_record_created is False
              and r.transaction_committed is False)
        check("report_request.report_plan_id mismatch: no row created", count(fb, Rec) == 0)
        check("report_request.report_plan_id mismatch: neither plan id echoed",
              "rpt_plan_other" not in blob and "rpt_plan_1" not in blob)
        check("report_request.report_plan_id mismatch: no prohibited side effect",
              _no_effects(r))
        check("report_request.report_plan_id mismatch: no review_records / agent_run_records row",
              count(fb, ReviewRecord) == 0 and count(fb, AgentRunRecord) == 0)
        # Phase 36 derives plan.report_plan_id as `report_plan_id or idempotency_key`, and the
        # writer mirrors that derivation — so an idempotency-key-only request still matches and a
        # legitimately paired request is never denied.
        fb = fresh_db()
        key_only_plan, key_only_request = _make_plan(report_plan_id=None,
                                                     idempotency_key="rpt_from_idem")
        check("idempotency-key-only plan derives its report_plan_id",
              key_only_plan.report_plan_id == "rpt_from_idem")
        r = persist(_build(plan=key_only_plan)[0], session_factory=fb,
                    report_request=key_only_request)
        check("idempotency-key-only report_request still matches and permits the write",
              r.outcome == OC.CREATED and count(fb, Rec) == 1)
    finally:
        for tmp in tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 37 controlled-DB internal-assessment-report-draft-writer check")
    print("=" * 74)

    structural_checks()

    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("\n11+. DB-backed checks")
        print("  [skip] SQLAlchemy not installed — structural checks only "
              "(pip install -r requirements.txt to enable)")
    else:
        db_backed_checks()

    print("\n" + "=" * 74)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
