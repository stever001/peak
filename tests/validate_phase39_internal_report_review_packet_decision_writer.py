#!/usr/bin/env python3
"""Phase 39 controlled-DB internal-report-review-packet-decision-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/contracts/model/migration/doc files exist and
  compile; the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client
  or credential, and no Phase 22 review writer or agent-run writer; it has no update/delete/raw-SQL
  path; Phase 36 `peak/reports` stays DB-free and the Phase 37/38 writers are unchanged; the
  migration is additive schema-only (`down_revision = 011_internal_report_review_packets`); the
  Phase 17 allowlist gained exactly the one new pair (13 tables / 15 actions); every
  index/constraint name fits MySQL's 64-character identifier limit; the docs carry the required
  language; the repo stays source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database over a full Phase 37 -> 38 -> 39 chain — migration reversibility, successful create with
  the audit chain preserved, **proof that the packet and report-draft rows are not modified**,
  server-derived `decision_status`, stored-Engagement / stored-packet / stored-report-draft
  validation, idempotent replay and conflict, the closed decision-intent vocabulary, structural
  bounds, content-safety rejections (non-echoing), side-effect discipline (no `review_records` /
  `agent_run_records` write), and transaction/failure semantics. SQLite here is only a fast local
  structural smoke path — NOT the production-readiness proof path. Skipped with instructions if
  SQLAlchemy is absent (still exits 0).

Phase 39 persists an **internal-only reviewer decision** on a Phase 38 review packet. It approves
nothing for client use, verifies nothing financially, publishes nothing, executes nothing, updates
no packet or report-draft row, calls no Phase 22 review writer, and creates no
`review_records`/`agent_run_records` row.

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

BASELINE_COMMIT = "6162efa"   # Add Phase 38 internal report review packet writer

WRITER = "peak/db/internal_report_review_packet_decision_writer.py"
MIGRATION = "alembic/versions/012_internal_report_review_packet_decisions.py"
DOCS = ["docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md",
        "docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md"]
REQUIRED_FILES = [WRITER, "peak/db/writer_contracts.py", "peak/db/models.py", MIGRATION] + DOCS
WRITER_FILES = [WRITER, "peak/db/writer_contracts.py"]
COMPILE_FILES = WRITER_FILES + [
    MIGRATION, "peak/db/models.py",
    "tests/validate_phase39_internal_report_review_packet_decision_writer.py"]
REPORTS_FILES = [
    "peak/reports/__init__.py", "peak/reports/contracts.py", "peak/reports/governance.py",
    "peak/reports/internal_assessment_planner.py",
]

TABLE = "internal_report_review_packet_decisions"
ACTION = "create_internal_report_review_packet_decision"
DECISION_SCOPE = "internal_report_review_packet"
MYSQL_IDENTIFIER_LIMIT = 64

REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "internal-only",
    DECISION_SCOPE,
    "decision_recorded",
    "needs_followup",
    "ready_for_internal_use",
    "not client-facing approval",
    "insert-only",
    "never updated",
    "review_records",
    "agent_run_records",
    "server-stamped",
    "18 tables",
    ACTION,
    "managed remote mysql",
    "client isolation option a",
    "never echo",
    "64-character identifier limit",
    "missing_review_bundle_ref",   # the documented Phase 33 blocker
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

_CANARY = "ZZCANARY39ZZ"
_ID = dict(owner_id="owner_1", client_id="client_a", engagement_id="eng_x")
_SCOPE = "engagement_authorized"
_KEY = "idem-decision-1"


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


def _blob(r) -> str:
    return " ".join(list(r.reasons or []) + list(r.warnings or [])
                    + [str(r.reason_code), str(r.outcome), str(r.stored_record_id),
                       str(r.report_plan_id), str(r.plan_fingerprint), str(r.idempotency_key),
                       str(r.internal_report_review_packet_id),
                       str(r.internal_assessment_report_draft_id), str(r.decision_intent)])


def _no_effects(r) -> bool:
    return all(getattr(r, flag) is False for flag in (
        "packet_row_updated", "report_draft_row_updated", "review_records_write_made",
        "agent_run_records_write_made", "review_approval_made", "client_facing_output_created",
        "client_facing_approval_made", "financial_verification_made", "capsule_candidate_created",
        "capsule_publication_made", "agentnet_publication_made", "agent_execution_made",
        "mock_agent_execution_made", "llm_call_made", "agentnet_call_made", "resolver_call_made",
        "network_call_made"))


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Writer / contracts / model / migration / doc files present")
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
    wtext = read(WRITER)
    check("writer references no review/agent-run model",
          "ReviewRecord" not in wtext and "AgentRunRecord" not in wtext)
    check("writer executes no raw SQL",
          not re.search(r"session\.execute|engine\.execute|text\(\s*['\"]", wtext))
    check("writer performs no update/delete path",
          not re.search(r"session\.delete|\.update\(|DELETE FROM|UPDATE ", wtext))
    check("writer reads only the three authorized stored models",
          sorted(set(re.findall(r"session\.get\((\w+)", wtext)))
          == ["Engagement", "InternalAssessmentReportDraftRecord",
              "InternalReportReviewPacketRecord"])
    check("writer adds exactly one record type to the session",
          sorted(set(re.findall(r"session\.add\((\w+)", wtext))) == ["record"]
          and wtext.count("session.add(") == 1)
    check("writer reuses the closed Phase 32 decision vocabulary",
          "from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS" in wtext)

    print("\n4. Earlier phases unchanged; Phase 36 still DB-free")
    for rel in REPORTS_FILES:
        joined = " ".join(_import_lines(read(rel)))
        check(f"{rel}: no SQLAlchemy/Alembic import", not DB_IMPORT_RE.search(joined))
        check(f"{rel}: no peak.db import", "peak.db" not in joined)
    probe = ("import sys; import peak.reports; "
             "bad=[m for m in sys.modules if m.split('.')[0] in "
             "('sqlalchemy','alembic','pymysql') or m.startswith('peak.db')]; "
             "print('CLEAN_OK' if not bad else 'LEAKED:'+','.join(sorted(bad)))")
    proc = subprocess.run([sys.executable or "python3", "-c", probe],
                          capture_output=True, text=True, cwd=REPO_ROOT, timeout=90)
    check("importing peak.reports still loads no DB module", "CLEAN_OK" in proc.stdout)
    p37 = read("peak/db/internal_assessment_report_draft_writer.py")
    check("Phase 37 writer still targets its own table only",
          "internal_assessment_report_drafts" in p37 and TABLE not in p37)
    p38 = read("peak/db/internal_report_review_packet_writer.py")
    check("Phase 38 writer still targets its own table only",
          "internal_report_review_packets" in p38 and TABLE not in p38)
    check("Phase 38 writer still enforces its pre-decision posture",
          'REVIEW_PACKET_DECISION_STATUS' in p38 or "not_decided" in p38)
    p33 = read("peak/db/internal_reviewer_decision_writer.py")
    check("Phase 33 writer untouched by Phase 39 (still bundle-oriented)",
          "missing_review_bundle_ref" in p33 and TABLE not in p33)

    print("\n5. Phase 17 allowlist gained exactly the one new pair")
    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check(f"'{TABLE}' on the allowlist", TABLE in ALLOWED_TABLES)
    check(f"'{ACTION}' on the allowlist", ACTION in ALLOWED_ACTIONS)
    check("exactly one new table added (13 total)", len(ALLOWED_TABLES) == 13)
    check("exactly one new action added (15 total)", len(ALLOWED_ACTIONS) == 15)
    check("no update/delete/upsert/raw-SQL action added",
          not any(re.search(r"upsert|raw_sql|hard_delete", a) for a in ALLOWED_ACTIONS))

    print("\n6. Migration is additive, schema-only, single-head")
    mig = read(MIGRATION)
    check("down_revision = 011_internal_report_review_packets",
          re.search(r'down_revision\s*=\s*"011_internal_report_review_packets"', mig) is not None)
    check("revision id is 012_internal_report_review_packet_decisions",
          re.search(r'revision\s*=\s*"012_internal_report_review_packet_decisions"', mig)
          is not None)
    check("creates exactly one table", mig.count("op.create_table(") == 1)
    check("no INSERT / seed / data of any kind",
          not any(p in mig.lower() for p in INSERT_PATTERNS))
    check("no destructive op in upgrade",
          not re.search(r"op\.drop_table|op\.drop_column", mig.split("def downgrade")[0]))
    check("downgrade drops only the new table",
          mig.split("def downgrade")[1].count("op.drop_table(") == 1)
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check("012 is the newest migration",
          versions[-1].startswith("012_internal_report_review_packet_decisions"))
    downs = [re.search(r'down_revision\s*=\s*"?([^"\s]+)"?',
                       read(os.path.join("alembic", "versions", f))).group(1) for f in versions]
    check("migration chain stays linear (no duplicate down_revision)",
          len(downs) == len(set(downs)))

    print("\n7. Model + db-check expectations")
    try:
        from peak.db.models import ALL_MODELS, InternalReportReviewPacketDecisionRecord as Rec
    except ImportError:
        print("  [skip] SQLAlchemy not installed — model assertions skipped "
              "(pip install -r requirements.txt to enable)")
        Rec, ALL_MODELS = None, None
    _model_checks(Rec, ALL_MODELS)
    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11, "EXPECTED_TABLES", []))
    check("db-check EXPECTED_TABLES includes the new table", TABLE in expected)
    check("db-check now expects exactly 18 tables (17 prior + the decision table)",
          len(expected) == 18)
    models_src = read("peak/db/models.py")
    check("model source declares the new table", f'__tablename__ = "{TABLE}"' in models_src)
    check("model source registers the new class in ALL_MODELS",
          re.search(r"^ALL_MODELS = \[(?:.|\n)*?InternalReportReviewPacketDecisionRecord,"
                    r"(?:.|\n)*?^\]", models_src, re.M) is not None)
    named = set(re.findall(r'"(ix_irrpd_\w+|uq_internal_report_review_packet_decisions_\w+)"',
                           models_src + mig))
    check("explicit identifier names all fit the MySQL limit",
          bool(named) and all(len(n) <= MYSQL_IDENTIFIER_LIMIT for n in named))
    check("short ix_irrpd_ prefix used (convention-derived names would exceed 64)",
          "ix_irrpd_" in models_src and "ix_irrpd_" in mig)

    print("\n8. Docs carry the required Phase 39 language")
    blob = re.sub(r"\s+", " ", " ".join(read(d) for d in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"docs state: {phrase}", phrase.lower() in blob)

    _policy_regressions()
    _hygiene_checks()


def _model_checks(Rec, all_models) -> None:
    if Rec is None:
        return
    check("InternalReportReviewPacketDecisionRecord in ALL_MODELS", Rec in all_models)
    check("eighteen models registered", len(all_models) == 18)
    check(f"__tablename__ == {TABLE}", Rec.__tablename__ == TABLE)
    cols = set(Rec.__table__.columns.keys())
    required = {
        "id", "owner_id", "client_id", "engagement_id", "authorization_scope",
        "internal_report_review_packet_id", "source_packet_table",
        "internal_assessment_report_draft_id", "source_report_draft_table", "report_plan_id",
        "plan_fingerprint", "report_draft_payload_fingerprint", "packet_payload_fingerprint",
        "requested_by", "requester_role", "reviewer_ref", "decision_intent",
        "safe_decision_summary", "requested_followup_actions_json", "decision_status",
        "decision_scope", "audience", "review_status", "lifecycle_status", "reasons_json",
        "warnings_json", "client_facing_approved", "review_approval_made", "financial_verified",
        "capsule_candidate_ready", "publication_allowed", "execution_allowed",
        "requires_human_review", "idempotency_key", "payload_fingerprint", "created_at",
    }
    check("model carries every required column", required <= cols)
    uniques = [c for c in Rec.__table__.constraints
               if c.__class__.__name__ == "UniqueConstraint"]
    check("unique idempotency constraint over (owner, client, engagement, key)",
          any(sorted(col.name for col in u.columns)
              == ["client_id", "engagement_id", "idempotency_key", "owner_id"] for u in uniques))
    names = [i.name for i in Rec.__table__.indexes] + [c.name for c in Rec.__table__.constraints
                                                       if c.name]
    check("every model index/constraint name fits the MySQL 64-char identifier limit",
          all(len(n) <= MYSQL_IDENTIFIER_LIMIT for n in names))


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
    check("validate-phase39 is part of `make validate`", "validate-phase39" in validate_line)
    for target in ("db-check-managed-test", "managed-mysql-smoke",
                   "managed-mysql-migration-check"):
        check(f"managed target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("no DSN / database URL added by Phase 39",
          not any(re.search(r"mysql\+pymysql://|postgres://|PEAK_DATABASE_URL\s*=", read(rel))
                  for rel in [WRITER, MIGRATION] + DOCS))
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
        check(f"Phase 39 baseline commit {BASELINE_COMMIT} present in history", present)
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


def _decision_draft(*, packet_id, draft_id, plan_fingerprint, **over):
    from peak.db.writer_contracts import InternalReportReviewPacketDecisionDraft as DD

    base = dict(**_ID, authorization_scope=_SCOPE,
                internal_report_review_packet_id=packet_id,
                internal_assessment_report_draft_id=draft_id,
                report_plan_id="rpt_plan_1", plan_fingerprint=plan_fingerprint,
                reviewer_ref="reviewer_a", decision_intent="ready_for_internal_use",
                safe_decision_summary="internally reliable for planning",
                requested_followup_actions=[{"action_id": "act_001", "status": "open"}])
    base.update(over)
    return DD(**base)


def _build_cwr(draft, **over):
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

    subj_over = over.pop("subject_over", None) or {}
    subj_base = dict(subject_record_id="eng_x", subject_record_type="engagement",
                     owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
                     stored_authorization_scope=_SCOPE)
    subj_base.update(subj_over)
    base = dict(**_ID, requested_by="consultant_a", requester_role="consultant",
                authorization_scope=_SCOPE, target_table=TABLE, requested_action=ACTION,
                subject=ControlledWriteSubject(**subj_base), record_draft=draft,
                source_phase="phase39", lifecycle_status="active", idempotency_key=_KEY)
    base.update(over)
    return ControlledWriteRequest(**base)


# --------------------------------------------------------------------------- DB-backed


def _migration_reversibility() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    print("\n11. Migration apply / reversibility (temp SQLite structural smoke; NOT prod proof)")
    tmp = tempfile.mkdtemp(prefix="peak_phase39_mig_")
    prev = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created the table", TABLE in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns(TABLE)}
        check("table carries linkage/decision/posture/idempotency columns",
              {"internal_report_review_packet_id", "source_packet_table",
               "internal_assessment_report_draft_id", "source_report_draft_table",
               "report_plan_id", "plan_fingerprint", "report_draft_payload_fingerprint",
               "packet_payload_fingerprint", "reviewer_ref", "decision_intent",
               "safe_decision_summary", "requested_followup_actions_json", "decision_status",
               "decision_scope", "audience", "review_approval_made", "requires_human_review",
               "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"]) for i in insp.get_indexes(TABLE)}
        check("unique idempotency index over (owner, client, engagement, key)",
              idx.get("uq_internal_report_review_packet_decisions_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        check("expected short-prefix indexes present",
              all(f"ix_irrpd_{s}" in idx for s in
                  ("client_id", "engagement_id", "owner_id", "authorization_scope",
                   "review_status", "lifecycle_status", "packet_id", "report_draft_id",
                   "report_plan_id", "plan_fingerprint", "audience", "decision_scope",
                   "decision_intent", "decision_status", "idempotency_key")))
        check("every applied index name fits the MySQL identifier limit",
              all(len(n) <= MYSQL_IDENTIFIER_LIMIT for n in idx))
        command.downgrade(cfg, "011_internal_report_review_packets")
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
        build_internal_assessment_report_draft_write_request as build_draft_cwr,
        persist_internal_assessment_report_draft as persist_draft,
    )
    from peak.db.internal_report_review_packet_decision_writer import (
        MAX_FOLLOWUP_ACTIONS, MAX_NOTES,
        build_packet_decision_write_request as build_helper,
        persist_internal_report_review_packet_decision as persist,
    )
    from peak.db.internal_report_review_packet_writer import (
        build_internal_report_review_packet_write_request as build_packet_cwr,
        persist_internal_report_review_packet as persist_packet,
    )
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, InternalAssessmentReportDraftRecord as Draft,
        InternalReportReviewPacketDecisionRecord as Rec,
        InternalReportReviewPacketRecord as Pkt, ReviewRecord,
    )
    from peak.db.writer_contracts import (
        InternalReportReviewPacketDecisionWriteOutcome as OC,
        InternalReportReviewPacketDraft as PD,
    )
    from peak.reports import (
        InternalAssessmentReportPlanRequest as PReq,
        prepare_internal_assessment_report_plan as plan_it,
    )
    from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS

    _migration_reversibility()

    tmpdirs: list = []

    def build_chain(*, engagement_over=None, draft_over=None, packet_over=None):
        """A temp DB carrying a real Phase 37 report draft and Phase 38 review packet."""
        tmp = tempfile.mkdtemp(prefix="peak_phase39_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        f = sessionmaker(bind=engine, expire_on_commit=False)
        eng = dict(id="eng_x", client_id="client_a", owner_id="owner_1",
                   authorization_scope=_SCOPE, lifecycle_status="active", review_status="active")
        eng.update(engagement_over or {})
        s = f()
        s.add(Engagement(**eng))
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
        if draft_over:
            s = f()
            row = s.get(Draft, dr.stored_record_id)
            for k, v in draft_over.items():
                setattr(row, k, v)
            s.commit()
            s.close()
        if packet_over:
            s = f()
            row = s.get(Pkt, pk.stored_record_id)
            for k, v in packet_over.items():
                setattr(row, k, v)
            s.commit()
            s.close()
        return f, dr.stored_record_id, pk.stored_record_id, plan.plan_fingerprint

    def count(f, model):
        s = f()
        n = s.query(model).count()
        s.close()
        return n

    def snapshot(f, model, rid):
        s = f()
        row = s.get(model, rid)
        snap = {c.name: getattr(row, c.name) for c in model.__table__.columns}
        s.close()
        return snap

    try:
        print("\n12. Successful create (audit chain preserved; nothing else touched)")
        f, did, pid, pfp = build_chain()
        before_pkt = snapshot(f, Pkt, pid)
        before_draft = snapshot(f, Draft, did)
        r = persist(_build_cwr(_decision_draft(packet_id=pid, draft_id=did,
                                               plan_fingerprint=pfp)), session_factory=f)
        check("outcome == created", r.outcome == OC.CREATED and r.permitted is True)
        check("exactly one row created", count(f, Rec) == 1)
        check("server-generated id (irrpd_ prefix)",
              bool(r.stored_record_id) and r.stored_record_id.startswith("irrpd_"))
        check("receipt carries the full audit chain",
              r.internal_report_review_packet_id == pid
              and r.internal_assessment_report_draft_id == did
              and r.report_plan_id == "rpt_plan_1" and r.plan_fingerprint == pfp)
        check("receipt posture is internal-only",
              r.audience == "internal" and r.decision_scope == DECISION_SCOPE
              and r.review_status == "needs_review" and r.lifecycle_status == "draft")
        check("decision_status server-derived as decision_recorded",
              r.decision_status == "decision_recorded" and r.decision_intent
              == "ready_for_internal_use")
        check("flags: connection/sql/write/commit/created all True",
              r.database_connection_made and r.sql_execution_made and r.database_write_made
              and r.transaction_committed and r.stored_record_created)
        check("non-effect flags all False", _no_effects(r))
        check("receipt created_at present", bool(r.created_at))

        s = f()
        row = s.get(Rec, r.stored_record_id)
        pkt_row = s.get(Pkt, pid)
        draft_row = s.get(Draft, did)
        check("stored posture internal-only and non-approval",
              row.audience == "internal" and row.decision_scope == DECISION_SCOPE
              and row.review_status == "needs_review" and row.lifecycle_status == "draft"
              and row.client_facing_approved is False and row.review_approval_made is False
              and row.financial_verified is False and row.capsule_candidate_ready is False
              and row.publication_allowed is False and row.execution_allowed is False
              and row.requires_human_review is True)
        check("source table labels stored",
              row.source_packet_table == "internal_report_review_packets"
              and row.source_report_draft_table == "internal_assessment_report_drafts")
        check("upstream fingerprints copied from the STORED rows",
              row.packet_payload_fingerprint == pkt_row.payload_fingerprint
              and row.report_draft_payload_fingerprint == draft_row.payload_fingerprint)
        check("follow-up actions stored as labels/status only",
              all(set(i) == {"action_id", "status"} for i in row.requested_followup_actions_json))
        check("idempotency_key + payload_fingerprint persisted",
              row.idempotency_key == _KEY and bool(row.payload_fingerprint))
        stored_blob = " ".join(str(getattr(row, c)) for c in (
            "safe_decision_summary", "requested_followup_actions_json", "reasons_json",
            "warnings_json", "reviewer_ref"))
        check("no raw-content key stored",
              not any(t in stored_blob for t in (
                  "note_text", "packet_payload", "source_bytes", "generated_output",
                  "raw_evidence_text", "final_client_report")))
        check("no ROI/currency figure stored",
              not re.search(r"[$€£]\s?\d|\d+(?:\.\d+)?\s?%", stored_blob))
        s.close()

        print("\n13. THE PACKET AND REPORT DRAFT ROWS ARE NOT MODIFIED")
        check("packet row byte-for-byte unchanged", snapshot(f, Pkt, pid) == before_pkt)
        check("report draft row byte-for-byte unchanged", snapshot(f, Draft, did) == before_draft)
        check("packet still pre-decision",
              before_pkt["reviewer_decision_status"] == "not_decided"
              and snapshot(f, Pkt, pid)["reviewer_decision_record_id"] is None)
        check("NO review_records row created", count(f, ReviewRecord) == 0)
        check("NO agent_run_records row created", count(f, AgentRunRecord) == 0)
        check("clients untouched", count(f, Client) == 0)
        check("exactly one packet and one report draft still present",
              count(f, Pkt) == 1 and count(f, Draft) == 1)

        print("\n14. Decision intent vocabulary (closed Phase 32 set)")
        needs_followup = {"needs_more_evidence", "return_for_revision", "blocked_by_scope",
                          "blocked_by_quality", "blocked_by_missing_source", "defer_review"}
        for intent in sorted(ALLOWED_DECISION_INTENTS):
            fb, d2, p2, fp2 = build_chain()
            rr = persist(_build_cwr(_decision_draft(packet_id=p2, draft_id=d2,
                                                    plan_fingerprint=fp2,
                                                    decision_intent=intent)), session_factory=fb)
            want = "needs_followup" if intent in needs_followup else "decision_recorded"
            check(f"intent '{intent}' accepted with decision_status '{want}'",
                  rr.outcome == OC.CREATED and rr.decision_status == want)
            check(f"intent '{intent}' stays internal-only and non-approval",
                  rr.audience == "internal" and _no_effects(rr))
        for bad in ("approve_client_facing", "approve_internal", "send_to_client",
                    "publish_report", "final_client_report", "approve_financial_claims",
                    "publish_capsule", "agentnet_publish", "execute_agent", "call_llm",
                    "resolver_lookup"):
            fb, d2, p2, fp2 = build_chain()
            rr = persist(_build_cwr(_decision_draft(packet_id=p2, draft_id=d2,
                                                    plan_fingerprint=fp2,
                                                    decision_intent=bad)), session_factory=fb)
            check(f"approval-like intent '{bad}' denied",
                  rr.outcome == OC.DENIED and rr.reason_code == "disallowed_decision_intent"
                  and count(fb, Rec) == 0)

        print("\n15. Idempotent replay and conflict")
        f3, d3, p3, fp3 = build_chain()
        base = _decision_draft(packet_id=p3, draft_id=d3, plan_fingerprint=fp3)
        first = persist(_build_cwr(base), session_factory=f3)
        second = persist(_build_cwr(base), session_factory=f3)
        check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
        check("no second row", count(f3, Rec) == 1)
        check("existing id returned", second.stored_record_id == first.stored_record_id)
        check("replay reports read, not write",
              second.database_write_made is False and second.stored_record_created is False
              and second.existing_record_returned is True
              and second.transaction_committed is False)
        check("replay updates no upstream row", _no_effects(second))
        changed = _decision_draft(packet_id=p3, draft_id=d3, plan_fingerprint=fp3,
                                  safe_decision_summary="a materially different note")
        rc = persist(_build_cwr(changed), session_factory=f3)
        check("changed decision on the same key conflicts",
              rc.outcome == OC.DENIED and rc.reason_code == "idempotency_conflict")
        check("no mutation on conflict", count(f3, Rec) == 1)
        changed_intent = _decision_draft(packet_id=p3, draft_id=d3, plan_fingerprint=fp3,
                                         decision_intent="needs_more_evidence")
        rc2 = persist(_build_cwr(changed_intent), session_factory=f3)
        check("changed intent on the same key conflicts (decision_status participates)",
              rc2.outcome == OC.DENIED and rc2.reason_code == "idempotency_conflict")
        check("helper-built request works",
              persist(build_helper(base, requested_by="consultant_a",
                                   requester_role="consultant",
                                   idempotency_key="idem-helper"),
                      session_factory=f3).outcome == OC.CREATED)

        print("\n16. Stored-Engagement authorization denials")
        for over, code in (({"authorization_scope": None}, "missing_stored_scope"),
                           ({"authorization_scope": "a_different_scope"},
                            "stored_scope_mismatch"),
                           ({"owner_id": "other_owner"}, "identity_mismatch"),
                           ({"client_id": "other_client"}, "identity_mismatch"),
                           ({"lifecycle_status": "revoked"}, "subject_lifecycle_blocked"),
                           ({"lifecycle_status": "archived"}, "subject_lifecycle_blocked"),
                           ({"lifecycle_status": "deleted_reference_only"},
                            "subject_lifecycle_blocked")):
            fe, de, pe, fpe = build_chain()
            s = fe()
            row = s.get(Engagement, "eng_x")
            for k, v in over.items():
                setattr(row, k, v)
            s.commit()
            s.close()
            rr = persist(_build_cwr(_decision_draft(packet_id=pe, draft_id=de,
                                                    plan_fingerprint=fpe)), session_factory=fe)
            check(f"engagement {list(over)[0]}={list(over.values())[0]!r} denied",
                  rr.reason_code == code and count(fe, Rec) == 0)
        fb, db_, pb, fpb = build_chain()
        rr = persist(_build_cwr(_decision_draft(packet_id=pb, draft_id=db_, plan_fingerprint=fpb),
                                subject_over={"subject_record_id": "eng_missing"}),
                     session_factory=fb)
        check("missing stored engagement denied",
              rr.reason_code == "missing_subject" and rr.database_connection_made is True)

        print("\n17. Stored packet validation denials")
        fb, db_, pb, fpb = build_chain()
        rr = persist(_build_cwr(_decision_draft(packet_id="irrp_missing", draft_id=db_,
                                                plan_fingerprint=fpb)), session_factory=fb)
        check("missing stored packet denied",
              rr.reason_code == "missing_packet" and count(fb, Rec) == 0)
        for field, value, code in (
            ("owner_id", "other_owner", "packet_identity_mismatch"),
            ("client_id", "other_client", "packet_identity_mismatch"),
            ("engagement_id", "eng_other", "packet_identity_mismatch"),
            ("authorization_scope", "other_scope", "packet_identity_mismatch"),
            ("internal_assessment_report_draft_id", "iard_other", "packet_linkage_mismatch"),
            ("report_plan_id", "rpt_other", "packet_linkage_mismatch"),
            ("plan_fingerprint", "f" * 64, "packet_linkage_mismatch"),
            ("audience", "client", "packet_not_internal"),
            ("packet_status", "closed", "packet_invalid_status"),
            ("review_status", "approved_internal", "packet_invalid_review_status"),
            ("lifecycle_status", "active", "packet_invalid_lifecycle_status"),
            ("reviewer_decision_status", "decided", "packet_already_decided"),
            ("reviewer_decision_record_id", "irrpd_x", "packet_already_decided"),
            ("client_facing_approved", True, "packet_posture_elevated"),
            ("review_approval_made", True, "packet_posture_elevated"),
            ("financial_verified", True, "packet_posture_elevated"),
            ("capsule_candidate_ready", True, "packet_posture_elevated"),
            ("publication_allowed", True, "packet_posture_elevated"),
            ("execution_allowed", True, "packet_posture_elevated"),
            ("requires_human_review", False, "packet_posture_elevated"),
        ):
            fp_, dp_, pp_, fpp_ = build_chain(packet_over={field: value})
            rr = persist(_build_cwr(_decision_draft(packet_id=pp_, draft_id=dp_,
                                                    plan_fingerprint=fpp_)), session_factory=fp_)
            check(f"stored packet {field}={value!r} denied",
                  rr.outcome == OC.DENIED and rr.reason_code == code and count(fp_, Rec) == 0)

        print("\n18. Stored report-draft validation denials")
        for field, value, code in (
            ("owner_id", "other_owner", "report_draft_identity_mismatch"),
            ("authorization_scope", "other_scope", "report_draft_identity_mismatch"),
            ("report_plan_id", "rpt_other", "report_draft_linkage_mismatch"),
            ("plan_fingerprint", "f" * 64, "report_draft_linkage_mismatch"),
            ("audience", "client", "report_draft_not_internal"),
            ("output_status", "final", "report_draft_invalid_output_status"),
            ("review_status", "approved_internal", "report_draft_invalid_review_status"),
            ("lifecycle_status", "active", "report_draft_invalid_lifecycle_status"),
            ("client_facing_approved", True, "report_draft_posture_elevated"),
            ("financial_verified", True, "report_draft_posture_elevated"),
            ("publication_allowed", True, "report_draft_posture_elevated"),
            ("requires_human_review", False, "report_draft_posture_elevated"),
        ):
            # Only the stored REPORT DRAFT is mutated. The packet keeps its original linkage, so
            # the packet check still passes and the report-draft check is what denies — proving the
            # draft is independently verified rather than trusted via the packet.
            fd_, dd_, pd_, fpd_ = build_chain(draft_over={field: value})
            rr = persist(_build_cwr(_decision_draft(
                packet_id=pd_, draft_id=dd_, plan_fingerprint=fpd_)), session_factory=fd_)
            check(f"stored report draft {field}={value!r} denied",
                  rr.outcome == OC.DENIED and rr.reason_code == code and count(fd_, Rec) == 0)

        print("\n19. Request / draft denials (no DB connection opened)")
        fb, db_, pb, fpb = build_chain()

        def deny(**over):
            """Build a decision draft with `over` taking precedence over every default."""
            kwargs = dict(packet_id=pb, draft_id=db_, plan_fingerprint=fpb)
            kwargs.update(over)
            return persist(_build_cwr(_decision_draft(**kwargs)), session_factory=fb)

        for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
            rr = deny(**{attr: "wrong_value"})
            check(f"request/draft {attr} mismatch denied",
                  rr.reason_code == "identity_mismatch" and rr.database_connection_made is False)
        for attr, code in (("decision_record_id", "caller_supplied_id"),
                           ("created_at", "caller_supplied_timestamp")):
            check(f"caller-supplied {attr} denied",
                  deny(**{attr: "2026-07-31T00:00:00Z"}).reason_code == code)
        for attr in ("internal_report_review_packet_id", "internal_assessment_report_draft_id",
                     "report_plan_id"):
            check(f"missing {attr} denied", deny(**{attr: None}).reason_code
                  == "missing_linkage_ref")
        check("missing plan_fingerprint denied",
              deny(plan_fingerprint=None).reason_code == "missing_plan_fingerprint")
        check("malformed plan_fingerprint denied",
              deny(plan_fingerprint="not-a-sha").reason_code == "invalid_fingerprint")
        check("missing decision_intent denied",
              deny(decision_intent=None).reason_code == "missing_decision_intent")
        for audience in ("client", "external", "public"):
            check(f"audience '{audience}' denied",
                  deny(audience=audience).reason_code == "prohibited_audience")
        for flag in ("client_facing_approved", "review_approval_made", "financial_verified",
                     "capsule_candidate_ready", "publication_allowed", "execution_allowed"):
            check(f"draft {flag}=True denied",
                  deny(**{flag: True}).reason_code == "prohibited_posture")
        check("requires_human_review=False denied",
              deny(requires_human_review=False).reason_code == "prohibited_posture")
        check("unsafe reviewer_ref denied",
              deny(reviewer_ref="reviewer with spaces").reason_code
              == "unsafe_decision_reference")
        check("approval-flavoured action status denied",
              deny(requested_followup_actions=[{"action_id": "a", "status": "approved"}])
              .reason_code == "invalid_decision_status_value")
        check("unexpected action key denied",
              deny(requested_followup_actions=[{"action_id": "a", "status": "open",
                                                "note_text": "x"}]).reason_code
              == "prohibited_decision_key")
        # A missing key is caught by the earlier Phase 17 boundary (`plan_not_permitted`) before the
        # writer's own `invalid_idempotency_key` check — defence in depth. Either gate is correct,
        # so the assertion is that it is denied, before any DB connection, naming idempotency_key.
        no_key = persist(_build_cwr(_decision_draft(packet_id=pb, draft_id=db_,
                                                    plan_fingerprint=fpb), idempotency_key=None),
                         session_factory=fb)
        check("missing idempotency_key denied before any DB connection",
              no_key.outcome == OC.DENIED
              and no_key.reason_code in ("plan_not_permitted", "invalid_idempotency_key")
              and "idempotency_key" in " ".join(no_key.reasons)
              and no_key.database_connection_made is False)
        check("overlong idempotency_key denied",
              persist(_build_cwr(_decision_draft(packet_id=pb, draft_id=db_,
                                                 plan_fingerprint=fpb),
                                 idempotency_key="k" * 129),
                      session_factory=fb).reason_code == "invalid_idempotency_key")

        print("\n20. Allowlist denials")
        good = _decision_draft(packet_id=pb, draft_id=db_, plan_fingerprint=fpb)
        for table in ("review_records", "agent_run_records", "internal_reviewer_decision_records",
                      "internal_report_review_packets", "resolver_capsule_records"):
            rr = persist(_build_cwr(good, target_table=table), session_factory=fb)
            check(f"target_table '{table}' denied",
                  rr.outcome == OC.DENIED and rr.database_connection_made is False)
        for action in ("create_internal_reviewer_decision_record", "update_review_status",
                       "mark_superseded", "delete_decision", "upsert_decision", "raw_sql",
                       "publish_report", "approve_client_facing", "send_to_client",
                       "verify_financial", "publish_capsule"):
            check(f"requested_action '{action}' denied",
                  persist(_build_cwr(good, requested_action=action),
                          session_factory=fb).outcome == OC.DENIED)
        check("non-draft record_draft denied",
              persist(_build_cwr(object()), session_factory=fb).reason_code
              == "invalid_record_draft")

        class _Fake:
            pass
        check("duck-typed request denied",
              persist(_Fake(), session_factory=fb).reason_code == "invalid_request_type")

        print("\n21. Structural bounds enforced before any write")
        for family, limit, factory in (
            ("requested_followup_actions", MAX_FOLLOWUP_ACTIONS,
             lambda i: {"action_id": f"act_synth_{i:04d}", "status": "open"}),
            ("reasons", MAX_NOTES, lambda i: f"synthetic internal note {i:04d}"),
            ("warnings", MAX_NOTES, lambda i: f"synthetic internal warning {i:04d}"),
        ):
            fbb, dbb, pbb, fpbb = build_chain()
            over = {family: [factory(i) for i in range(limit + 1)]}
            d = _decision_draft(packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb, **over)
            check(f"{family} fixture really exceeds the bound",
                  len(getattr(d, family)) == limit + 1)
            rr = persist(_build_cwr(d), session_factory=fbb)
            check(f"over-limit {family} denied with decision_too_large",
                  rr.outcome == OC.DENIED and rr.reason_code == "decision_too_large")
            check(f"over-limit {family}: no row written and no DB connection",
                  count(fbb, Rec) == 0 and rr.database_connection_made is False)
            check(f"over-limit {family}: reason names the bound category only, no item echoed",
                  family in _blob(rr) and "synth" not in _blob(rr))
            check(f"over-limit {family}: no prohibited side effect", _no_effects(rr))

        print("\n22. Content / leak safety (canary never echoed, never stored)")
        prohibited_keys = ("raw_note_text", "note_text", "packet_payload", "raw_evidence_text",
                           "raw_interview_text", "source_bytes", "generated_output",
                           "final_client_report", "client_facing_output", "approve_internal",
                           "approve_client_facing", "publish_capsule", "agentnet_publish",
                           "resolver_credentials", "llm_prompt", "database_url", "raw_sql",
                           "api_key", "secret_key", "private_key", "connection_string",
                           "stack_trace")
        for key in prohibited_keys:
            fbb, dbb, pbb, fpbb = build_chain()
            d = _decision_draft(packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb)
            setattr(d, key, _CANARY)
            rr = persist(_build_cwr(d), session_factory=fbb)
            check(f"prohibited draft key '{key}' denied without echoing",
                  rr.outcome == OC.DENIED and rr.reason_code == "prohibited_decision_key"
                  and _CANARY not in _blob(rr) and count(fbb, Rec) == 0)
        marker_values = {
            "credential/secret": f"api_key={_CANARY}",
            "DB-URL/DSN": f"mysql://u:{_CANARY}@h/db",
            "raw-SQL": f"select * from clients where n='{_CANARY}'",
            "raw-content": f"source_bytes-{_CANARY}",
        }
        for label, value in marker_values.items():
            fbb, dbb, pbb, fpbb = build_chain()
            rr = persist(_build_cwr(_decision_draft(
                packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb,
                safe_decision_summary=value)), session_factory=fbb)
            check(f"{label} summary denied without echoing",
                  rr.outcome == OC.DENIED and _CANARY not in _blob(rr) and count(fbb, Rec) == 0)
        fbb, dbb, pbb, fpbb = build_chain()
        rr = persist(_build_cwr(_decision_draft(
            packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb,
            safe_decision_summary=f'File "x.py", line 1 {_CANARY}')), session_factory=fbb)
        check("stack-trace-like summary denied without echoing",
              rr.outcome == OC.DENIED and _CANARY not in _blob(rr))
        for phrase in ("Send to client once approved.", "Ready for the final client report.",
                       "Sign off on the ROI of this recommendation.",
                       "Approve for client distribution.", "Publish capsule after review."):
            fbb, dbb, pbb, fpbb = build_chain()
            rr = persist(_build_cwr(_decision_draft(
                packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb,
                safe_decision_summary=phrase)), session_factory=fbb)
            check("client-facing/approval intent in the summary denied",
                  rr.outcome == OC.DENIED
                  and rr.reason_code == "prohibited_decision_intent_language"
                  and count(fbb, Rec) == 0)
        fbb, dbb, pbb, fpbb = build_chain()
        rr = persist(_build_cwr(_decision_draft(
            packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb,
            safe_decision_summary="x" * 400)), session_factory=fbb)
        check("over-long summary denied", rr.reason_code == "unsafe_decision_reference")

        print("\n23. Transaction / failure semantics")

        class _FailAt:
            def __init__(self, inner, method, exc):
                self._inner, self._method, self._exc = inner, method, exc

            def __getattr__(self, name):
                if name == self._method:
                    def boom(*a, **k):
                        raise self._exc
                    return boom
                return getattr(self._inner, name)

        fbb, dbb, pbb, fpbb = build_chain()
        good2 = _decision_draft(packet_id=pbb, draft_id=dbb, plan_fingerprint=fpbb)
        fail_get = lambda: _FailAt(fbb(), "get", SQLAlchemyError("boom-get"))  # noqa: E731
        rr = persist(_build_cwr(good2), session_factory=fail_get)
        check("failed_before_write when a read fails",
              rr.outcome == OC.FAILED_BEFORE_WRITE and rr.stored_record_created is False)
        fail_commit = lambda: _FailAt(fbb(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
        rr = persist(_build_cwr(good2), session_factory=fail_commit)
        check("write_outcome_uncertain on commit failure",
              rr.outcome == OC.WRITE_OUTCOME_UNCERTAIN and rr.outcome_uncertain is True)
        check("uncertain never claims no record exists", "no row" not in _blob(rr).lower())
        check("no leak of exception detail in failure reasons",
              "boom" not in _blob(rr) and "SELECT" not in _blob(rr).upper())
    finally:
        for tmp in tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 39 controlled-DB internal-report-review-packet-decision-writer check")
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
