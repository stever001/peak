#!/usr/bin/env python3
"""Phase 38 controlled-DB internal-report-review-packet-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/contracts/model/migration/doc files exist and
  compile; the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client
  or credential, and no Phase 22 review writer or agent-run writer; the Phase 36 `peak/reports`
  package stays DB-free; the Phase 37 report-draft writer is unchanged in substance; the migration
  is additive schema-only (creates one table, no INSERT/seed,
  `down_revision = 010_internal_assessment_report_drafts`); the Phase 17 allowlist gained exactly
  the one new table/action pair; every index/constraint name fits MySQL's 64-character identifier
  limit; the docs carry the required language; the repo stays source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database — migration upgrade/downgrade/re-upgrade, successful create (labels/statuses/refs stored,
  no prose), stored-report-draft linkage validation, idempotent replay, conflicting replay,
  DB-backed authorization, identity/allowlist checks, posture rejections, structural bounds,
  content-safety rejections (non-echoing), side-effect discipline (no `review_records` /
  `agent_run_records` write), and transaction/failure semantics. SQLite here is only a fast local
  structural smoke path — NOT the production-readiness proof path (see
  docs/PRODUCTION_PARITY_DB_VALIDATION.md). Skipped with instructions if SQLAlchemy is absent
  (still exits 0).

Phase 38 persists a **reviewer packet**, not a review outcome: `packet_status` is fixed at
`ready_for_internal_review` and `reviewer_decision_status` at `not_decided`. It approves nothing,
verifies nothing financially, publishes nothing, executes nothing, calls no Phase 22 review writer,
creates no `review_records`/`agent_run_records` row, and makes no LLM/MockLLM/AgentNet/MCP/resolver/
connector/network call.

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

# Pinned baseline commit (verified by ancestry over the FULL history — see the Phase 35 follow-up).
BASELINE_COMMIT = "96b000f"   # Add Phase 37 internal assessment report draft writer

WRITER = "peak/db/internal_report_review_packet_writer.py"
MIGRATION = "alembic/versions/011_internal_report_review_packets.py"
DOCS = ["docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md",
        "docs/INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md"]
REQUIRED_FILES = [WRITER, "peak/db/writer_contracts.py", "peak/db/models.py", MIGRATION] + DOCS
WRITER_FILES = [WRITER, "peak/db/writer_contracts.py"]
COMPILE_FILES = WRITER_FILES + [MIGRATION, "peak/db/models.py",
                                "tests/validate_phase38_internal_report_review_packet_writer.py"]
REPORTS_FILES = [
    "peak/reports/__init__.py", "peak/reports/contracts.py", "peak/reports/governance.py",
    "peak/reports/internal_assessment_planner.py",
]

TABLE = "internal_report_review_packets"
ACTION = "create_internal_report_review_packet"
PACKET_STATUS = "ready_for_internal_review"
DECISION_STATUS = "not_decided"
MYSQL_IDENTIFIER_LIMIT = 64

REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "review-gated",
    "internal-only",
    PACKET_STATUS,
    DECISION_STATUS,
    "not a review outcome",
    "review_status",
    "lifecycle_status",
    "review_records",
    "agent_run_records",
    "server-stamped",
    "17 tables",
    ACTION,
    "managed remote mysql",
    "client isolation option a",
    "never echo",
    "not the production-readiness proof path",
    "64-character identifier limit",
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

_CANARY = "ZZCANARY38ZZ"
_ID = dict(owner_id="owner_1", client_id="client_a", engagement_id="eng_x")
_SCOPE = "engagement_authorized"
_KEY = "idem-packet-1"


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
    return " ".join(list(receipt.reasons or []) + list(receipt.warnings or [])
                    + [str(receipt.reason_code), str(receipt.outcome),
                       str(receipt.stored_record_id), str(receipt.report_plan_id),
                       str(receipt.plan_fingerprint), str(receipt.idempotency_key),
                       str(receipt.internal_assessment_report_draft_id)])


def _no_effects(r) -> bool:
    return all(getattr(r, flag) is False for flag in (
        "review_records_write_made", "agent_run_records_write_made", "review_approval_made",
        "client_facing_output_created", "client_facing_approval_made",
        "financial_verification_made", "capsule_candidate_created", "capsule_publication_made",
        "agentnet_publication_made", "agent_execution_made", "mock_agent_execution_made",
        "llm_call_made", "agentnet_call_made", "resolver_call_made", "network_call_made"))


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
    check("writer reads only the two authorized stored models",
          sorted(set(re.findall(r"session\.get\((\w+)", wtext)))
          == ["Engagement", "InternalAssessmentReportDraftRecord"])

    print("\n4. Phase 36 reports package stays DB-free; Phase 37 writer unchanged in substance")
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
    check("Phase 37 writer still targets its own table/action only",
          "internal_assessment_report_drafts" in p37 and TABLE not in p37)
    check("Phase 37 writer still enforces plan_persisted posture",
          'STORED_OUTPUT_STATUS = "plan_persisted"' in p37)
    check("Phase 37 writer still uses stored-Engagement authorization",
          "stored_scope_mismatch" in p37 and "session.get(Engagement" in p37)

    print("\n5. Phase 17 allowlist gained exactly the one new pair")
    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check(f"'{TABLE}' on the allowlist", TABLE in ALLOWED_TABLES)
    check(f"'{ACTION}' on the allowlist", ACTION in ALLOWED_ACTIONS)
    check("exactly one new table added (12 total)", len(ALLOWED_TABLES) == 12)
    check("exactly one new action added (14 total)", len(ALLOWED_ACTIONS) == 14)
    check("no update/delete/upsert/raw-SQL action added",
          not any(re.search(r"upsert|raw_sql|hard_delete", a) for a in ALLOWED_ACTIONS))

    print("\n6. Migration is additive, schema-only, single-head")
    mig = read(MIGRATION)
    check("down_revision = 010_internal_assessment_report_drafts",
          re.search(r'down_revision\s*=\s*"010_internal_assessment_report_drafts"', mig)
          is not None)
    check("revision id is 011_internal_report_review_packets",
          re.search(r'revision\s*=\s*"011_internal_report_review_packets"', mig) is not None)
    check("creates exactly one table", mig.count("op.create_table(") == 1)
    check("no INSERT / seed / data of any kind",
          not any(p in mig.lower() for p in INSERT_PATTERNS))
    check("no destructive op in upgrade",
          not re.search(r"op\.drop_table|op\.drop_column", mig.split("def downgrade")[0]))
    check("downgrade drops only the new table",
          mig.split("def downgrade")[1].count("op.drop_table(") == 1)
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check("011 is the newest migration",
          versions[-1].startswith("011_internal_report_review_packets"))
    downs = [re.search(r'down_revision\s*=\s*"?([^"\s]+)"?',
                       read(os.path.join("alembic", "versions", f))).group(1) for f in versions]
    check("migration chain stays linear (no duplicate down_revision)",
          len(downs) == len(set(downs)))

    print("\n7. Model + db-check expectations")
    try:
        from peak.db.models import ALL_MODELS, InternalReportReviewPacketRecord as Rec
    except ImportError:
        print("  [skip] SQLAlchemy not installed — model assertions skipped "
              "(pip install -r requirements.txt to enable)")
        Rec, ALL_MODELS = None, None
    _model_checks(Rec, ALL_MODELS)
    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11, "EXPECTED_TABLES", []))
    check("db-check EXPECTED_TABLES includes the new table", TABLE in expected)
    check("db-check now expects exactly 17 tables (16 prior + the review-packet table)",
          len(expected) == 17)
    models_src = read("peak/db/models.py")
    check("model source declares the new table", f'__tablename__ = "{TABLE}"' in models_src)
    check("model source registers the new class in ALL_MODELS",
          re.search(r"^ALL_MODELS = \[(?:.|\n)*?InternalReportReviewPacketRecord,(?:.|\n)*?^\]",
                    models_src, re.M) is not None)
    # MySQL identifier limit: the convention-derived report-draft index name would be 69 chars.
    idx_names = re.findall(r'"(ix_internal_report_review_packets_\w+)"', models_src + mig)
    idx_names += re.findall(r'f"ix_\{TABLE\}_\{col\}"', mig) and []
    check("no explicitly named index exceeds the MySQL identifier limit",
          all(len(n) <= MYSQL_IDENTIFIER_LIMIT for n in idx_names))
    check("report-draft index uses the short explicit name",
          "ix_internal_report_review_packets_report_draft" in models_src
          and "ix_internal_report_review_packets_report_draft" in mig)

    print("\n8. Docs carry the required Phase 38 language")
    blob = re.sub(r"\s+", " ", " ".join(read(d) for d in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"docs state: {phrase}", phrase.lower() in blob)

    _policy_regressions()
    _hygiene_checks()


def _model_checks(Rec, all_models) -> None:
    """SQLAlchemy-dependent model assertions (no-op when the driver is absent)."""
    if Rec is None:
        return
    check("InternalReportReviewPacketRecord in ALL_MODELS", Rec in all_models)
    check("seventeen models registered", len(all_models) == 17)
    check(f"__tablename__ == {TABLE}", Rec.__tablename__ == TABLE)
    cols = set(Rec.__table__.columns.keys())
    required = {
        "id", "owner_id", "client_id", "engagement_id", "authorization_scope",
        "internal_assessment_report_draft_id", "source_report_draft_table", "report_plan_id",
        "plan_fingerprint", "report_draft_payload_fingerprint", "requested_by", "requester_role",
        "assigned_reviewer", "packet_purpose", "audience", "packet_status", "review_status",
        "lifecycle_status", "reviewer_decision_record_id", "reviewer_decision_status",
        "section_review_checklist_json", "evidence_trace_refs_json", "open_gaps_json",
        "blocked_items_json", "reviewer_questions_json", "readiness_checklist_json",
        "required_followup_actions_json", "future_financial_verification_items_json",
        "future_capsule_candidate_items_json", "reasons_json", "warnings_json",
        "client_facing_approved", "review_approval_made", "financial_verified",
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
    check("validate-phase38 is part of `make validate`", "validate-phase38" in validate_line)
    for target in ("db-check-managed-test", "managed-mysql-smoke",
                   "managed-mysql-migration-check"):
        check(f"managed target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("no DSN / database URL added by Phase 38",
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
        check(f"Phase 38 baseline commit {BASELINE_COMMIT} present in history", present)
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


def _make_packet_draft(*, report_draft_id, plan_fingerprint, **over):
    from peak.db.writer_contracts import InternalReportReviewPacketDraft as PD

    base = dict(**_ID, authorization_scope=_SCOPE,
                internal_assessment_report_draft_id=report_draft_id,
                report_plan_id="rpt_plan_1", plan_fingerprint=plan_fingerprint,
                assigned_reviewer="reviewer_a", packet_purpose="internal readiness review",
                section_review_checklist=[
                    {"section_id": "evidence_summary", "check_id": "chk_001",
                     "status": "not_started"},
                    {"section_id": "operational_findings", "check_id": "chk_002",
                     "status": "in_review"}],
                evidence_trace_refs=["evid_1", "evid_2"],
                open_gaps=["gap_intake_summary_intake_note_refs"],
                blocked_items=["intake_summary"],
                reviewer_questions=["Is the evidence sufficient for the receiving findings?"],
                readiness_checklist=[{"check_id": "rdy_001", "status": "in_review"}],
                required_followup_actions=[{"action_id": "act_001", "status": "open"}],
                future_financial_verification_items=["rec_000"],
                future_capsule_candidate_items=["ing_1"])
    base.update(over)
    return PD(**base)


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
                source_phase="phase38", lifecycle_status="active", idempotency_key=_KEY)
    base.update(over)
    return ControlledWriteRequest(**base)


# --------------------------------------------------------------------------- DB-backed


def _migration_reversibility() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    print("\n11. Migration apply / reversibility (temp SQLite structural smoke; NOT prod proof)")
    tmp = tempfile.mkdtemp(prefix="peak_phase38_mig_")
    prev = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created the table", TABLE in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns(TABLE)}
        check("table carries linkage/packet/posture/idempotency columns",
              {"internal_assessment_report_draft_id", "source_report_draft_table",
               "report_plan_id", "plan_fingerprint", "report_draft_payload_fingerprint",
               "assigned_reviewer", "packet_purpose", "audience", "packet_status",
               "reviewer_decision_record_id", "reviewer_decision_status",
               "section_review_checklist_json", "evidence_trace_refs_json", "open_gaps_json",
               "blocked_items_json", "reviewer_questions_json", "readiness_checklist_json",
               "required_followup_actions_json", "future_financial_verification_items_json",
               "future_capsule_candidate_items_json", "review_approval_made",
               "requires_human_review", "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"]) for i in insp.get_indexes(TABLE)}
        check("unique idempotency index over (owner, client, engagement, key)",
              idx.get("uq_internal_report_review_packets_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        check("expected non-unique indexes present",
              all(f"ix_{TABLE}_{c}" in idx for c in
                  ("client_id", "engagement_id", "report_plan_id", "plan_fingerprint", "audience",
                   "packet_status", "reviewer_decision_record_id", "idempotency_key", "owner_id",
                   "authorization_scope", "review_status", "lifecycle_status")))
        check("report-draft index present under its short name",
              "ix_internal_report_review_packets_report_draft" in idx)
        check("every applied index name fits the MySQL identifier limit",
              all(len(n) <= MYSQL_IDENTIFIER_LIMIT for n in idx))
        command.downgrade(cfg, "010_internal_assessment_report_drafts")
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
    from peak.db.internal_report_review_packet_writer import (
        MAX_BLOCKED_ITEMS, MAX_EVIDENCE_TRACE_REFS, MAX_FOLLOWUP_ACTIONS, MAX_FUTURE_ITEMS,
        MAX_OPEN_GAPS, MAX_READINESS_ITEMS, MAX_REVIEWER_QUESTIONS, MAX_SECTION_REVIEW_ITEMS,
        build_internal_report_review_packet_write_request as build_pkt_cwr,
        persist_internal_report_review_packet as persist,
    )
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, InternalAssessmentReportDraftRecord as Draft,
        InternalReportReviewPacketRecord as Rec, ReviewRecord,
    )
    from peak.db.writer_contracts import InternalReportReviewPacketWriteOutcome as OC
    from peak.reports import (
        InternalAssessmentReportPlanRequest as PReq,
        prepare_internal_assessment_report_plan as plan_it,
    )

    _migration_reversibility()

    tmpdirs: list = []

    def make_plan(**over):
        base = dict(**_ID, authorization_scope=_SCOPE, requested_by="consultant_a",
                    requester_role="consultant", report_plan_id="rpt_plan_1",
                    intake_note_refs=["intn_1"], source_ingestion_refs=["ing_1"],
                    evidence_reference_ids=["evid_1", "evid_2"],
                    agent_task_queue_record_ids=["atq_1"], review_bundle_record_ids=["rvb_1"],
                    internal_reviewer_decision_record_ids=["ird_1"])
        base.update(over)
        return plan_it(PReq(**base)).report_plan

    def fresh_db(*, seed_draft=True, engagement_over=None, draft_over=None):
        """A temp SQLite DB with an Engagement and (optionally) a stored Phase 37 report draft."""
        tmp = tempfile.mkdtemp(prefix="peak_phase38_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        eng = dict(id="eng_x", client_id="client_a", owner_id="owner_1",
                   authorization_scope=_SCOPE, lifecycle_status="active", review_status="active")
        eng.update(engagement_over or {})
        s = factory()
        s.add(Engagement(**eng))
        s.commit()
        s.close()
        draft_id, plan = None, make_plan()
        if seed_draft:
            r = persist_draft(build_draft_cwr(plan, requested_by="consultant_a",
                                              requester_role="consultant",
                                              idempotency_key="idem-draft-1"),
                              session_factory=factory)
            draft_id = r.stored_record_id
            if draft_over:
                s = factory()
                row = s.get(Draft, draft_id)
                for k, v in draft_over.items():
                    setattr(row, k, v)
                s.commit()
                s.close()
        return factory, draft_id, plan

    def count(factory, model):
        s = factory()
        n = s.query(model).count()
        s.close()
        return n

    try:
        print("\n12. Successful create (labels/statuses/refs stored; no prose)")
        f, draft_id, plan = fresh_db()
        pd = _make_packet_draft(report_draft_id=draft_id,
                                plan_fingerprint=plan.plan_fingerprint)
        r = persist(_build_cwr(pd), session_factory=f)
        check("outcome == created", r.outcome == OC.CREATED and r.permitted is True)
        check("exactly one row created", count(f, Rec) == 1)
        check("server-generated id (irrp_ prefix)",
              bool(r.stored_record_id) and r.stored_record_id.startswith("irrp_"))
        check("receipt carries report-draft linkage",
              r.internal_assessment_report_draft_id == draft_id
              and r.report_plan_id == "rpt_plan_1"
              and r.plan_fingerprint == plan.plan_fingerprint)
        check("receipt posture is internal-only and pre-decision",
              r.audience == "internal" and r.packet_status == PACKET_STATUS
              and r.review_status == "needs_review" and r.lifecycle_status == "draft"
              and r.reviewer_decision_status == DECISION_STATUS)
        check("receipt counts match the packet",
              r.section_review_item_count == 2 and r.reviewer_question_count == 1
              and r.readiness_check_item_count == 1 and r.required_followup_action_count == 1
              and r.open_gap_count == 1 and r.evidence_trace_ref_count == 2)
        check("flags: connection/sql/write/commit/created all True",
              r.database_connection_made and r.sql_execution_made and r.database_write_made
              and r.transaction_committed and r.stored_record_created)
        check("non-effect flags all False", _no_effects(r))
        check("receipt created_at present", bool(r.created_at))

        s = f()
        row = s.get(Rec, r.stored_record_id)
        stored_draft = s.get(Draft, draft_id)
        check("stored posture is internal-only, pre-decision, non-final",
              row.audience == "internal" and row.packet_status == PACKET_STATUS
              and row.review_status == "needs_review" and row.lifecycle_status == "draft"
              and row.reviewer_decision_record_id is None
              and row.reviewer_decision_status == DECISION_STATUS
              and row.client_facing_approved is False and row.review_approval_made is False
              and row.financial_verified is False and row.capsule_candidate_ready is False
              and row.publication_allowed is False and row.execution_allowed is False
              and row.requires_human_review is True)
        check("report-draft linkage stored",
              row.internal_assessment_report_draft_id == draft_id
              and row.source_report_draft_table == "internal_assessment_report_drafts")
        check("report_draft_payload_fingerprint copied from the STORED draft",
              row.report_draft_payload_fingerprint == stored_draft.payload_fingerprint)
        check("section_review_checklist_json stores checklist metadata only",
              all(set(i) == {"check_id", "section_id", "status"}
                  for i in row.section_review_checklist_json))
        check("evidence_trace_refs_json stores refs only",
              row.evidence_trace_refs_json == ["evid_1", "evid_2"])
        check("open_gaps_json / blocked_items_json stored",
              row.open_gaps_json == ["gap_intake_summary_intake_note_refs"]
              and row.blocked_items_json == ["intake_summary"])
        check("reviewer_questions_json stores short internal prompts only",
              len(row.reviewer_questions_json) == 1
              and all(len(q) <= 240 and "\n" not in q for q in row.reviewer_questions_json))
        check("readiness_checklist_json stores labels/status only",
              all(set(i) == {"check_id", "status"} for i in row.readiness_checklist_json))
        check("required_followup_actions_json stores action labels/status only",
              all(set(i) == {"action_id", "status"} for i in row.required_followup_actions_json))
        check("future-gate placeholders stored as items only",
              row.future_financial_verification_items_json == ["rec_000"]
              and row.future_capsule_candidate_items_json == ["ing_1"])
        check("idempotency_key + payload_fingerprint persisted",
              row.idempotency_key == _KEY and bool(row.payload_fingerprint))
        check("created_at server-stamped", row.created_at is not None)
        stored_blob = " ".join(str(getattr(row, c)) for c in (
            "section_review_checklist_json", "evidence_trace_refs_json", "open_gaps_json",
            "blocked_items_json", "reviewer_questions_json", "readiness_checklist_json",
            "required_followup_actions_json", "reasons_json", "warnings_json"))
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
        check("the Phase 37 report draft row is unmodified", count(f, Draft) == 1)

        print("\n14. Stored report-draft linkage (mode B: the row is read, not trusted)")
        f2, draft_id2, plan2 = fresh_db()
        r = persist(_build_cwr(_make_packet_draft(
            report_draft_id="iard_missing", plan_fingerprint=plan2.plan_fingerprint)),
            session_factory=f2)
        check("missing stored report draft denied",
              r.outcome == OC.DENIED and r.reason_code == "missing_report_draft"
              and r.database_connection_made is True and count(f2, Rec) == 0)
        for field, value, code in (
            ("audience", "client", "report_draft_not_internal"),
            ("output_status", "final", "report_draft_invalid_output_status"),
            ("review_status", "approved_internal", "report_draft_invalid_review_status"),
            ("lifecycle_status", "active", "report_draft_invalid_lifecycle_status"),
            ("client_facing_approved", True, "report_draft_posture_elevated"),
            ("financial_verified", True, "report_draft_posture_elevated"),
            ("capsule_candidate_ready", True, "report_draft_posture_elevated"),
            ("publication_allowed", True, "report_draft_posture_elevated"),
            ("execution_allowed", True, "report_draft_posture_elevated"),
            ("requires_human_review", False, "report_draft_posture_elevated"),
        ):
            fb, did, pl = fresh_db(draft_over={field: value})
            rr = persist(_build_cwr(_make_packet_draft(
                report_draft_id=did, plan_fingerprint=pl.plan_fingerprint)), session_factory=fb)
            check(f"stored report draft {field}={value!r} denied",
                  rr.outcome == OC.DENIED and rr.reason_code == code and count(fb, Rec) == 0)
        for field, value in (("owner_id", "other_owner"), ("client_id", "other_client"),
                             ("engagement_id", "eng_other"),
                             ("authorization_scope", "other_scope")):
            fb, did, pl = fresh_db(draft_over={field: value})
            rr = persist(_build_cwr(_make_packet_draft(
                report_draft_id=did, plan_fingerprint=pl.plan_fingerprint)), session_factory=fb)
            check(f"stored report draft {field} mismatch denied",
                  rr.reason_code == "report_draft_identity_mismatch" and count(fb, Rec) == 0)
        fb, did, pl = fresh_db()
        rr = persist(_build_cwr(_make_packet_draft(
            report_draft_id=did, plan_fingerprint="f" * 64)), session_factory=fb)
        check("plan_fingerprint not matching the stored draft denied",
              rr.reason_code == "report_draft_provenance_mismatch" and count(fb, Rec) == 0)
        rr = persist(_build_cwr(_make_packet_draft(
            report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
            report_plan_id="rpt_other")), session_factory=fb)
        check("report_plan_id not matching the stored draft denied",
              rr.reason_code == "report_draft_provenance_mismatch" and count(fb, Rec) == 0)
        rr = persist(_build_cwr(_make_packet_draft(
            report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
            report_draft_payload_fingerprint="a" * 64)), session_factory=fb)
        check("report_draft_payload_fingerprint not matching the stored draft denied",
              rr.reason_code == "report_draft_provenance_mismatch" and count(fb, Rec) == 0)

        print("\n15. Idempotent replay and conflict")
        f3, did3, pl3 = fresh_db()
        base_draft = _make_packet_draft(report_draft_id=did3,
                                        plan_fingerprint=pl3.plan_fingerprint)
        first = persist(_build_cwr(base_draft), session_factory=f3)
        second = persist(_build_cwr(base_draft), session_factory=f3)
        check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
        check("no second row", count(f3, Rec) == 1)
        check("existing id returned", second.stored_record_id == first.stored_record_id)
        check("replay reports read, not write",
              second.database_write_made is False and second.stored_record_created is False
              and second.existing_record_returned is True
              and second.transaction_committed is False)
        changed = _make_packet_draft(report_draft_id=did3, plan_fingerprint=pl3.plan_fingerprint,
                                     open_gaps=["gap_other"])
        rc = persist(_build_cwr(changed), session_factory=f3)
        check("changed packet on the same key conflicts",
              rc.outcome == OC.DENIED and rc.reason_code == "idempotency_conflict")
        check("no mutation on conflict", count(f3, Rec) == 1)
        check("helper-built request works",
              persist(build_pkt_cwr(base_draft, requested_by="consultant_a",
                                    requester_role="consultant",
                                    idempotency_key="idem-helper"),
                      session_factory=f3).outcome == OC.CREATED)

        print("\n16. Stored-Engagement authorization denials")
        fb, did, pl = fresh_db()
        good = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint)
        r = persist(_build_cwr(good, subject_over={"subject_record_id": "eng_missing"}),
                    session_factory=fb)
        check("missing stored engagement denied",
              r.reason_code == "missing_subject" and r.database_connection_made is True)
        for over, code in (({"authorization_scope": None}, "missing_stored_scope"),
                           ({"authorization_scope": "a_different_scope"},
                            "stored_scope_mismatch"),
                           ({"owner_id": "other_owner"}, "identity_mismatch"),
                           ({"client_id": "other_client"}, "identity_mismatch"),
                           ({"lifecycle_status": "revoked"}, "subject_lifecycle_blocked"),
                           ({"lifecycle_status": "archived"}, "subject_lifecycle_blocked"),
                           ({"lifecycle_status": "deleted_reference_only"},
                            "subject_lifecycle_blocked")):
            fe, dide, ple = fresh_db(seed_draft=False, engagement_over=over)
            rr = persist(_build_cwr(_make_packet_draft(
                report_draft_id="iard_x", plan_fingerprint=ple.plan_fingerprint)),
                session_factory=fe)
            check(f"engagement {list(over)[0]}={list(over.values())[0]!r} denied",
                  rr.reason_code == code and count(fe, Rec) == 0)

        print("\n17. Identity / posture denials (no DB connection opened)")
        for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   **{attr: "wrong_value"})
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"request/packet {attr} mismatch denied",
                  r.reason_code == "identity_mismatch" and r.database_connection_made is False)
        for attr, code in (("review_packet_id", "caller_supplied_id"),
                           ("created_at", "caller_supplied_timestamp")):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   **{attr: "2026-07-31T00:00:00Z"})
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"caller-supplied {attr} denied", r.reason_code == code)
        for audience in ("client", "external", "public"):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   audience=audience)
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"audience '{audience}' denied", r.reason_code == "prohibited_audience")
        for status in ("final", "published", "client_facing", "approved", "complete"):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   packet_status=status)
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"packet_status '{status}' denied", r.reason_code == "invalid_packet_status")
        for status in ("approved_internal", "client_facing_approved"):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   review_status=status)
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"review_status '{status}' denied", r.reason_code == "invalid_review_status")
        d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                               lifecycle_status="active")
        r = persist(_build_cwr(d), session_factory=fresh_db()[0])
        check("lifecycle_status != draft denied", r.reason_code == "invalid_lifecycle_status")
        for status in ("approved", "approved_internal", "client_facing_approved", "rejected"):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   reviewer_decision_status=status)
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"reviewer_decision_status '{status}' denied",
                  r.reason_code == "invalid_reviewer_decision_status")
        d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                               reviewer_decision_record_id="ird_1")
        r = persist(_build_cwr(d), session_factory=fresh_db()[0])
        check("reviewer_decision_record_id supplied at creation denied",
              r.reason_code == "prohibited_reviewer_decision_link")
        for flag in ("client_facing_approved", "review_approval_made", "financial_verified",
                     "capsule_candidate_ready", "publication_allowed", "execution_allowed"):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   **{flag: True})
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"packet {flag}=True denied", r.reason_code == "prohibited_posture")
        d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                               requires_human_review=False)
        r = persist(_build_cwr(d), session_factory=fresh_db()[0])
        check("requires_human_review=False denied", r.reason_code == "prohibited_posture")
        for family, item in (("section_review_checklist",
                              {"section_id": "s", "check_id": "c", "status": "approved"}),
                             ("readiness_checklist", {"check_id": "c", "status": "signed_off"}),
                             ("required_followup_actions",
                              {"action_id": "a", "status": "approved"})):
            d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                                   **{family: [item]})
            r = persist(_build_cwr(d), session_factory=fresh_db()[0])
            check(f"{family} approval-flavoured status denied",
                  r.reason_code == "invalid_packet_status_value")
        d = _make_packet_draft(report_draft_id="iard_x", plan_fingerprint="a" * 64,
                               readiness_checklist=[{"check_id": "c", "status": "in_review",
                                                     "note_text": "x"}])
        r = persist(_build_cwr(d), session_factory=fresh_db()[0])
        check("checklist item with an unexpected key denied",
              r.reason_code == "prohibited_packet_key")

        print("\n18. Allowlist denials")
        for table in ("review_records", "agent_run_records", "resolver_capsule_records",
                      "capsule_publication_candidates", "internal_assessment_report_drafts"):
            r = persist(_build_cwr(good, target_table=table), session_factory=fresh_db()[0])
            check(f"target_table '{table}' denied",
                  r.outcome == OC.DENIED and r.database_connection_made is False)
        for action in ("create_review_record", "update_review_status", "mark_superseded",
                       "delete_packet", "upsert_packet", "raw_sql", "publish_report",
                       "approve_client_facing", "approve_internal", "send_to_client",
                       "verify_financial", "publish_capsule"):
            r = persist(_build_cwr(good, requested_action=action), session_factory=fresh_db()[0])
            check(f"requested_action '{action}' denied", r.outcome == OC.DENIED)
        r = persist(_build_cwr(object()), session_factory=fresh_db()[0])
        check("non-draft record_draft denied", r.reason_code == "invalid_record_draft")

        class _Fake:
            pass
        r = persist(_Fake(), session_factory=fresh_db()[0])
        check("duck-typed request denied", r.reason_code == "invalid_request_type")

        print("\n19. Structural bounds enforced before any write")
        bounds = (
            ("section_review_checklist", MAX_SECTION_REVIEW_ITEMS,
             lambda i: {"section_id": f"sec_{i:04d}", "check_id": f"chk_{i:04d}",
                        "status": "not_started"}),
            ("reviewer_questions", MAX_REVIEWER_QUESTIONS,
             lambda i: f"Synthetic internal review question {i:04d}"),
            ("readiness_checklist", MAX_READINESS_ITEMS,
             lambda i: {"check_id": f"rdy_{i:04d}", "status": "not_started"}),
            ("required_followup_actions", MAX_FOLLOWUP_ACTIONS,
             lambda i: {"action_id": f"act_{i:04d}", "status": "open"}),
            ("open_gaps", MAX_OPEN_GAPS, lambda i: f"gap_synth_{i:04d}"),
            ("blocked_items", MAX_BLOCKED_ITEMS, lambda i: f"blk_synth_{i:04d}"),
            ("evidence_trace_refs", MAX_EVIDENCE_TRACE_REFS,
             lambda i: f"evid_synth_{i:05d}"),
            ("future_financial_verification_items", MAX_FUTURE_ITEMS,
             lambda i: f"ffv_synth_{i:04d}"),
            ("future_capsule_candidate_items", MAX_FUTURE_ITEMS,
             lambda i: f"fcc_synth_{i:04d}"),
        )
        for family, limit, factory in bounds:
            fb, did, pl = fresh_db()
            over = {family: [factory(i) for i in range(limit + 1)]}
            d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                                   **over)
            check(f"{family} fixture really exceeds the bound", len(getattr(d, family)) == limit + 1)
            r = persist(_build_cwr(d), session_factory=fb)
            blob = _blob(r)
            check(f"over-limit {family} denied with packet_too_large",
                  r.outcome == OC.DENIED and r.reason_code == "packet_too_large")
            check(f"over-limit {family}: no row written", count(fb, Rec) == 0)
            check(f"over-limit {family}: denied before any DB connection",
                  r.database_connection_made is False and r.sql_execution_made is False
                  and r.database_write_made is False)
            check(f"over-limit {family}: reason names the bound category only",
                  family in blob and "synth" not in blob and "chk_0" not in blob)
            check(f"over-limit {family}: no prohibited side effect", _no_effects(r))
            check(f"over-limit {family}: no stored record and no unrelated table write",
                  r.stored_record_created is False and count(fb, ReviewRecord) == 0
                  and count(fb, AgentRunRecord) == 0)
        # Exact upper bound is accepted — the check is a ceiling, not an off-by-one.
        fb, did, pl = fresh_db()
        d = _make_packet_draft(
            report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
            reviewer_questions=[f"Synthetic internal review question {i:04d}"
                                for i in range(MAX_REVIEWER_QUESTIONS)])
        r = persist(_build_cwr(d), session_factory=fb)
        check("a packet exactly at the reviewer-question bound is accepted",
              r.outcome == OC.CREATED and r.reviewer_question_count == MAX_REVIEWER_QUESTIONS)

        print("\n20. Content / leak safety (canary never echoed, never stored)")
        prohibited_keys = ("raw_note_text", "note_text", "packet_payload", "raw_evidence_text",
                           "raw_interview_text", "source_bytes", "generated_output",
                           "final_client_report", "client_facing_output", "approve_internal",
                           "approve_client_facing", "publish_capsule", "agentnet_publish",
                           "resolver_credentials", "llm_prompt", "database_url", "raw_sql",
                           "api_key", "secret_key", "private_key", "connection_string",
                           "stack_trace")
        for key in prohibited_keys:
            fb, did, pl = fresh_db()
            d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint)
            setattr(d, key, _CANARY)
            r = persist(_build_cwr(d), session_factory=fb)
            check(f"prohibited packet key '{key}' denied without echoing",
                  r.outcome == OC.DENIED and r.reason_code == "prohibited_packet_key"
                  and _CANARY not in _blob(r) and count(fb, Rec) == 0)
        marker_values = {
            "credential/secret": f"api_key={_CANARY}",
            "DB-URL/DSN": f"mysql://u:{_CANARY}@h/db",
            "raw-SQL": f"select * from clients where n='{_CANARY}'",
            "raw-content": f"source_bytes-{_CANARY}",
        }
        for label, value in marker_values.items():
            fb, did, pl = fresh_db()
            d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                                   reviewer_questions=[value])
            r = persist(_build_cwr(d), session_factory=fb)
            check(f"{label} reviewer question denied without echoing",
                  r.outcome == OC.DENIED and _CANARY not in _blob(r) and count(fb, Rec) == 0)
        fb, did, pl = fresh_db()
        d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                               reviewer_questions=[f'File "x.py", line 1 {_CANARY}'])
        r = persist(_build_cwr(d), session_factory=fb)
        check("stack-trace-like reviewer question denied without echoing",
              r.outcome == OC.DENIED and _CANARY not in _blob(r))
        for phrase in ("Please send to client once approved.",
                       "Draft the final report for the client deliverable.",
                       "Sign off on the ROI of the recommendation.",
                       "Approve for client distribution."):
            fb, did, pl = fresh_db()
            d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                                   reviewer_questions=[phrase])
            r = persist(_build_cwr(d), session_factory=fb)
            check("client-facing/approval intent in a reviewer question denied",
                  r.outcome == OC.DENIED and r.reason_code == "prohibited_packet_intent"
                  and count(fb, Rec) == 0)
        fb, did, pl = fresh_db()
        d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                               reviewer_questions=["x" * 400])
        r = persist(_build_cwr(d), session_factory=fb)
        check("over-long reviewer question denied", r.reason_code == "unsafe_packet_reference")
        fb, did, pl = fresh_db()
        d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                               evidence_trace_refs=[f"evid with spaces {_CANARY}"])
        r = persist(_build_cwr(d), session_factory=fb)
        check("unsafe evidence trace ref denied without echoing",
              r.reason_code == "unsafe_packet_reference" and _CANARY not in _blob(r))
        fb, did, pl = fresh_db()
        d = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint,
                               packet_purpose=f"mysql://u:{_CANARY}@h/db")
        r = persist(_build_cwr(d), session_factory=fb)
        check("DSN-like packet_purpose denied without echoing",
              r.reason_code == "invalid_packet_label" and _CANARY not in _blob(r))

        print("\n21. Transaction / failure semantics")

        class _FailAt:
            def __init__(self, inner, method, exc):
                self._inner, self._method, self._exc = inner, method, exc

            def __getattr__(self, name):
                if name == self._method:
                    def boom(*a, **k):
                        raise self._exc
                    return boom
                return getattr(self._inner, name)

        fb, did, pl = fresh_db()
        good2 = _make_packet_draft(report_draft_id=did, plan_fingerprint=pl.plan_fingerprint)
        fail_get = lambda: _FailAt(fb(), "get", SQLAlchemyError("boom-get"))  # noqa: E731
        r = persist(_build_cwr(good2), session_factory=fail_get)
        check("failed_before_write when the read fails",
              r.outcome == OC.FAILED_BEFORE_WRITE and r.stored_record_created is False)
        fail_commit = lambda: _FailAt(fb(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
        r = persist(_build_cwr(good2), session_factory=fail_commit)
        check("write_outcome_uncertain on commit failure",
              r.outcome == OC.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)
        check("uncertain never claims no record exists", "no row" not in _blob(r).lower())
        check("no leak of exception detail in failure reasons",
              "boom" not in _blob(r) and "SELECT" not in _blob(r).upper())
    finally:
        for tmp in tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 38 controlled-DB internal-report-review-packet-writer check")
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
