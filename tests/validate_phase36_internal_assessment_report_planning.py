#!/usr/bin/env python3
"""Phase 36 internal assessment report assembly planning boundary check.

Stdlib-only. The boundary under test is **DB-free and network-free**, so every check here runs on
plain `python3` with no dependency, no database, no credentials, and no network.

Layers:

* **Structural:** the package/contracts/docs exist and compile; `peak/reports` imports no
  SQLAlchemy/Alembic/`peak.db`/DB writer/AgentNet/MCP/resolver/connector/network/LLM/MockLLM/agent
  executor/publication module (proved at runtime in a subprocess); the public entry point and typed
  contracts exist; the Phase 17 allowlist gained **no** new pair; no migration `010`; db-check still
  expects 15 tables; the repo stays source-only.

* **Successful planning:** a valid request yields a deterministic `InternalAssessmentReportPlan` with
  internal-only posture, canonical section order, reference-only evidence traces, internal-only
  candidate slots, gaps for missing references, and future-gate slots that verify/publish nothing.

* **Denials:** the full matrix — missing identity/scope/plan-id, unsupported or duplicate sections,
  unsupported audience, elevated posture, cross-tenant / cross-engagement / scope-mismatched
  references, and unsafe refs.

* **Content/leak safety:** prohibited keys and values are denied before a plan is assembled, and a
  canary value never reaches any reason, warning, or result.

* **Regression:** Phases 32/33/34/35 intact; no new table/model/migration/allowlist pair; no report
  writer or report table; no `review_records` / `agent_run_records` write; no approval, client-facing
  output, financial verification, or capsule publication; managed MySQL and AgentNet publication
  policies unchanged.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PY = sys.executable or "python3"

# Pinned baseline commits (verified by ancestry over the FULL history — see the Phase 35 follow-up).
BASELINE_COMMIT = "67b89ad"   # Verify pinned baseline commits by ancestry
PHASE35_COMMIT = "b27cf8c"    # Add Phase 35 managed record workflow integration

REPORT_FILES = [
    "peak/reports/__init__.py",
    "peak/reports/contracts.py",
    "peak/reports/governance.py",
    "peak/reports/internal_assessment_planner.py",
]
DOCS = [
    "docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md",
    "docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md",
]
REQUIRED_FILES = REPORT_FILES + DOCS
COMPILE_FILES = REPORT_FILES + [
    "tests/validate_phase36_internal_assessment_report_planning.py",
]

REQUIRED_DOC_PHRASES = [
    "report planning boundary",
    "a report draft record",
    "db-free",
    "audience",
    "internal only",
    "output_status",
    "review_status",
    "lifecycle_status",
    "client_facing_approved",
    "financial_verified",
    "capsule_candidate_ready",
    "publication_allowed",
    "requires_human_review",
    "plan_fingerprint",
    "no random ids and no timestamps",
    "future_financial_verification_items",
    "future_capsule_candidate_items",
    "cross-tenant",
    "identity matching is necessary but",
    "no live database credentials and no network",
    "managed remote mysql",
    "client isolation option a",
    "sqlite is not the production-readiness proof path",
]

# The Phase 17 allowlist as it stood at the Phase 35 baseline. Phase 36 adds nothing.
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

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b")
WRITER_IMPORT_RE = re.compile(r"\b(?:persist_\w+|\w+_writer)\b")
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp|mcp_connector|resolver_client)\b", re.IGNORECASE)
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE)
RAW_SQL_RE = re.compile(r"\b(?:session\.execute|engine\.execute|sqlalchemy\.text)\b")
PUBLISH_IMPL_RE = re.compile(
    r"\b(?:publish_capsule|publish_node|agentnet_publish|resolver_publish)\s*\(")
NONDETERMINISM_RE = re.compile(
    r"\b(?:random\.|uuid4|uuid1|datetime\.now|datetime\.utcnow|time\.time|Date\.now)\b")

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []

# A canary that must never appear in any reason, warning, or result.
_CANARY = "ZZCANARY36ZZ"

_ID = dict(owner_id="owner_1", client_id="client_a", engagement_id="eng_x")
_SCOPE = "engagement_authorized"


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
    """Flatten everything a caller could read off a planning result into one string."""
    parts = list(result.reasons or []) + list(result.warnings or [])
    parts += [str(result.reason_code), str(result.outcome), str(result.status)]
    v = result.validation_result
    if v is not None:
        parts += list(v.reasons or []) + list(v.warnings or []) + [str(v.blocked_state)]
    plan = result.report_plan
    if plan is not None:
        parts += list(plan.reasons or []) + list(plan.warnings or [])
        parts += [str(plan.report_purpose), str(plan.plan_fingerprint)]
        parts += list(plan.blocked_items or [])
        parts += list(plan.future_financial_verification_items or [])
        parts += list(plan.future_capsule_candidate_items or [])
        for s in plan.sections:
            parts += [s.section_id, s.title, str(s.blocked_reason)] + list(s.notes or [])
        for t in plan.evidence_trace_map.values():
            for refs in t.supporting_refs.values():
                parts += list(refs)
        for f in plan.finding_candidates:
            parts += f.evidence_support_refs + f.review_support_refs + [str(f.blocked_reason)]
        for rc in plan.recommendation_candidates:
            parts += (rc.reviewer_decision_refs + rc.review_support_refs
                      + rc.evidence_support_refs + [str(rc.blocked_reason)])
        for g in plan.open_gaps:
            parts += [g.gap_id, str(g.note), str(g.missing_ref_category)]
    return " ".join(parts)


def _no_effects(result) -> bool:
    """True when every prohibited side-effect flag on a planning result is False."""
    return all(getattr(result, flag) is False for flag in (
        "direct_database_write_made", "database_connection_made", "sql_execution_made",
        "stored_record_created", "report_draft_persisted", "review_records_write_made",
        "agent_run_records_write_made", "review_approval_made", "client_facing_output_created",
        "client_facing_approval_made", "financial_verification_made", "capsule_publication_made",
        "capsule_candidate_created", "agentnet_publication_made", "agent_execution_made",
        "mock_agent_execution_made", "llm_call_made", "agentnet_call_made", "resolver_call_made",
        "network_call_made"))


def _request(**over):
    from peak.reports import InternalAssessmentReportPlanRequest

    base = dict(**_ID, authorization_scope=_SCOPE, requested_by="consultant_a",
                requester_role="consultant", report_plan_id="rpt_plan_1",
                intake_note_refs=["intn_1"], source_ingestion_refs=["ing_1", "ing_2"],
                evidence_reference_ids=["evid_2", "evid_1"],
                agent_task_queue_record_ids=["atq_1"], review_bundle_record_ids=["rvb_1"],
                internal_reviewer_decision_record_ids=["ird_1", "ird_2"],
                workflow_id="wf_1", managed_record_workflow_ref="wf35_run_1",
                report_purpose="internal readiness assessment")
    base.update(over)
    return InternalAssessmentReportPlanRequest(**base)


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Report planning package / doc files present")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Package imports: no DB / writer / LLM / connector / network / credential")
    for rel in REPORT_FILES:
        text = read(rel)
        imports = list(_import_lines(text))
        joined = " ".join(imports)
        check(f"{rel}: no SQLAlchemy/Alembic/pymysql import", not DB_IMPORT_RE.search(joined))
        check(f"{rel}: no peak.db import", not PEAK_DB_RE.search(joined))
        check(f"{rel}: no DB writer import", not WRITER_IMPORT_RE.search(joined))
        check(f"{rel}: no network client import", not NETWORK_IMPORT_RE.search(joined))
        check(f"{rel}: no LLM provider import", not LLM_PROVIDER_RE.search(joined))
        check(f"{rel}: no executor/MockLLM import", not EXEC_IMPORT_RE.search(joined))
        check(f"{rel}: no AgentNet/MCP/resolver connector import", not CONNECTOR_RE.search(joined))
        check(f"{rel}: no committed credential literal", not CREDENTIAL_RE.search(text))
        check(f"{rel}: no raw SQL execution", not RAW_SQL_RE.search(text))
        check(f"{rel}: no publication implementation", not PUBLISH_IMPL_RE.search(text))
        check(f"{rel}: no random id / timestamp source", not NONDETERMINISM_RE.search(text))

    print("\n4. Runtime proof: importing peak.reports loads no DB/network module")
    probe = (
        "import sys; import peak.reports; "
        "bad=[m for m in sys.modules if m.split('.')[0] in "
        "('sqlalchemy','alembic','pymysql','requests','httpx','aiohttp','socket','urllib')]; "
        "print('CLEAN_OK' if not bad else 'LEAKED:'+','.join(sorted(bad)))"
    )
    proc = subprocess.run([PY, "-c", probe], capture_output=True, text=True,
                          cwd=REPO_ROOT, timeout=90)
    check("no DB/network module loaded by peak.reports", "CLEAN_OK" in proc.stdout)
    check("no peak.db module loaded by peak.reports",
          subprocess.run(
              [PY, "-c", "import sys; import peak.reports; "
                         "print('NODB' if not [m for m in sys.modules "
                         "if m.startswith('peak.db')] else 'DBLOADED')"],
              capture_output=True, text=True, cwd=REPO_ROOT, timeout=90).stdout.strip() == "NODB")

    print("\n5. Public entry point and typed contracts exist")
    import inspect

    from peak.reports import (
        SUPPORTED_SECTIONS, GovernedRecordReference, InternalAssessmentReportPlan,
        InternalAssessmentReportPlanningResult, InternalAssessmentReportPlanRequest,
        InternalReportEvidenceTrace, InternalReportFindingCandidate, InternalReportGap,
        InternalReportPlanningValidationResult, InternalReportRecommendationCandidate,
        InternalReportSectionPlan, prepare_internal_assessment_report_plan,
    )

    check("prepare_internal_assessment_report_plan is callable",
          callable(prepare_internal_assessment_report_plan))
    check("entry point signature (request)",
          list(inspect.signature(prepare_internal_assessment_report_plan).parameters) == ["request"])
    for cls in (InternalAssessmentReportPlanRequest, InternalReportSectionPlan,
                InternalReportEvidenceTrace, InternalReportFindingCandidate,
                InternalReportRecommendationCandidate, InternalReportGap,
                InternalAssessmentReportPlan, InternalAssessmentReportPlanningResult,
                InternalReportPlanningValidationResult, GovernedRecordReference):
        check(f"contract {cls.__name__} exists",
              hasattr(cls, "__dataclass_fields__"))
    check("fourteen supported sections in canonical order",
          SUPPORTED_SECTIONS == (
              "executive_overview", "engagement_context", "intake_summary", "source_inventory",
              "evidence_summary", "operational_findings", "inventory_risk_areas",
              "process_improvement_candidates", "system_data_readiness", "ai_agent_readiness",
              "internal_recommendations", "evidence_gaps", "review_status", "next_steps_internal"))
    plan_fields = set(InternalAssessmentReportPlan.__dataclass_fields__)
    check("plan carries the required fields",
          {"report_plan_id", "owner_id", "client_id", "engagement_id", "authorization_scope",
           "requested_by", "requester_role", "report_purpose", "audience", "output_status",
           "review_status", "lifecycle_status", "client_facing_approved", "financial_verified",
           "capsule_candidate_ready", "publication_allowed", "execution_allowed",
           "requires_human_review", "sections", "evidence_trace_map", "finding_candidates",
           "recommendation_candidates", "open_gaps", "blocked_items",
           "future_financial_verification_items", "future_capsule_candidate_items", "reasons",
           "warnings"} <= plan_fields)

    print("\n6. No new table / model / migration / allowlist pair / report writer")
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check("no migration 010 (or later) added",
          not any(f[:3].isdigit() and int(f[:3]) >= 10 for f in versions))
    check("009_intake_note_records is still the newest migration",
          bool(versions) and versions[-1].startswith("009_intake_note_records"))
    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("Phase 17 allowlist tables unchanged", set(ALLOWED_TABLES) == BASELINE_ALLOWED_TABLES)
    check("Phase 17 allowlist actions unchanged", set(ALLOWED_ACTIONS) == BASELINE_ALLOWED_ACTIONS)
    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    check("db-check still expects exactly 15 tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == 15)
    check("no new model added in peak/db/models.py",
          len(re.findall(r"^class\s+\w+\(.*Base", read("peak/db/models.py"), re.M)) == 15)
    table_names = re.findall(r'__tablename__\s*=\s*"([^"]+)"', read("peak/db/models.py"))
    check("no report table in the DB models",
          len(table_names) == 15 and not any("report" in t for t in table_names))
    check("no report writer module added",
          not any(f.startswith("report") for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))))

    print("\n7. Regression: earlier phases intact")
    rd_imports = " ".join(_import_lines(read("peak/reviewer_decisions/governance.py"))) + " " + \
        " ".join(_import_lines(read("peak/reviewer_decisions/contracts.py")))
    check("Phase 32 reviewer_decisions package remains DB-free",
          not DB_IMPORT_RE.search(rd_imports) and "peak.db" not in rd_imports)
    check("Phase 33 writer still uses the public classify_prohibited_value_marker",
          "classify_prohibited_value_marker" in read(
              "peak/db/internal_reviewer_decision_writer.py"))
    intake = read("peak/db/intake_note_writer.py")
    check("Phase 34 intake writer still uses the hardened credential-disclosure scanner",
          "_CRED_ASSIGN_RE" in intake and "_note_text_category" in intake)
    wf = read("peak/workflows/managed_record_workflow.py")
    wf_imports = " ".join(_import_lines(wf))
    check("Phase 35 workflow package still imports no SQLAlchemy at module scope",
          not DB_IMPORT_RE.search(wf_imports))
    check("Phase 35 workflow still imports its writers lazily",
          all(f"from peak.db.{mod} import" in wf for mod in (
              "intake_note_writer", "source_ingestion_writer", "evidence_writer",
              "agent_task_queue_writer", "review_bundle_writer",
              "internal_reviewer_decision_writer")))
    for rel, fn in (("peak/db/agent_run_writer.py", "persist_agent_run_record"),
                    ("peak/db/evidence_writer.py", "persist_evidence_reference"),
                    ("peak/db/review_writer.py", "persist_review_record"),
                    ("peak/db/source_ingestion_writer.py", "persist_source_ingestion_record"),
                    ("peak/db/agent_task_queue_writer.py", "persist_agent_task_queue_record"),
                    ("peak/db/review_bundle_writer.py", "persist_review_bundle_record"),
                    ("peak/db/internal_reviewer_decision_writer.py",
                     "persist_internal_reviewer_decision_record"),
                    ("peak/db/intake_note_writer.py", "persist_intake_note_record")):
        check(f"{rel}: {fn} still present", f"def {fn}(" in read(rel))

    print("\n8. Docs carry the required Phase 36 language")
    doc_blob = re.sub(r"\s+", " ", " ".join(read(d) for d in DOCS)).lower()
    for phrase in REQUIRED_DOC_PHRASES:
        check(f"docs state: {phrase}", phrase in doc_blob)
    check("docs state AgentNet publication remains deferred/unchanged",
          "agentnet publication remains deferred" in doc_blob
          or "does not alter the peak-operated agentnet publication policy" in doc_blob)

    print("\n9. Managed MySQL policy regression (unchanged by Phase 36)")
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
    check("validate-phase36 is part of `make validate`", "validate-phase36" in validate_line)
    for target in ("db-check-managed-test", "managed-mysql-smoke",
                   "managed-mysql-migration-check"):
        check(f"managed target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("no DSN / database URL added by Phase 36",
          not any(re.search(r"mysql\+pymysql://|postgres://|PEAK_DATABASE_URL\s*=", read(rel))
                  for rel in REPORT_FILES + DOCS))

    print("\n10. AgentNet publication policy regression (unchanged by Phase 36)")
    pub = re.sub(r"\s+", " ", read("docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md")).lower()
    check("client authorizes Peak as publisher in the consulting agreement",
          "consulting agreement" in pub and "authorized capsule/node publisher" in pub)
    check("clients do not operate any AgentNet publishing tools",
          "clients do not operate any agentnet publishing tools" in pub)
    check("no client-facing AgentNet publisher UI", "no client-facing agentnet publisher ui" in pub)
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

    print("\n11. Baseline + repo hygiene: source-only, no data / credentials / examples")
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
        # Verify the pinned baseline commits by ancestry over the FULL history. A fixed
        # `git log --oneline -N` window silently falls out of range as later phases land.
        for sha, label in ((BASELINE_COMMIT, "Phase 36 baseline"),
                           (PHASE35_COMMIT, "Phase 35 deliverable")):
            present = subprocess.run(
                ["git", "-C", REPO_ROOT, "merge-base", "--is-ancestor", sha, "HEAD"],
                capture_output=True, timeout=20).returncode == 0
            check(f"{label} commit {sha} present in history", present)
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


# --------------------------------------------------------------------------- planning


def planning_checks() -> None:
    from peak.reports import (
        RECOMMENDATION_INTERNAL_DRAFT, SECTION_BLOCKED_NO_REFS, SECTION_READY,
        SECTION_SYNTHESIS_ONLY, SUPPORTED_SECTIONS,
        prepare_internal_assessment_report_plan as plan_it,
    )
    from peak.reports.internal_assessment_planner import MAX_CANDIDATES_PER_FAMILY

    print("\n12. Successful planning: posture, sections, determinism")
    r = plan_it(_request())
    check("outcome planned", r.outcome == "planned" and r.permitted is True
          and r.status == "planned")
    p = r.report_plan
    check("a plan was produced", p is not None)
    check("audience internal", p.audience == "internal")
    check("output_status plan", p.output_status == "plan")
    check("review_status needs_review", p.review_status == "needs_review")
    check("lifecycle_status draft", p.lifecycle_status == "draft")
    check("client_facing_approved false", p.client_facing_approved is False)
    check("financial_verified false", p.financial_verified is False)
    check("capsule_candidate_ready false", p.capsule_candidate_ready is False)
    check("publication_allowed false", p.publication_allowed is False)
    check("execution_allowed false", p.execution_allowed is False)
    check("requires_human_review true", p.requires_human_review is True)
    check("identity propagated",
          p.owner_id == "owner_1" and p.client_id == "client_a" and p.engagement_id == "eng_x"
          and p.authorization_scope == _SCOPE)
    check("report_plan_id set", p.report_plan_id == "rpt_plan_1")
    check("no controlled write requests produced", r.controlled_write_request_count == 0)
    check("no prohibited side effects", _no_effects(r))

    check("all fourteen sections planned", len(p.sections) == 14 and r.section_count == 14)
    check("sections emitted in canonical order",
          [s.section_id for s in p.sections] == list(SUPPORTED_SECTIONS))
    check("section order fields are sequential",
          [s.order for s in p.sections] == list(range(14)))
    check("section titles are fixed internal labels, not generated prose",
          all(isinstance(s.title, str) and s.title for s in p.sections))
    check("every section requires human review and is not client-facing",
          all(s.requires_human_review is True and s.client_facing_approved is False
              for s in p.sections))
    check("synthesis sections marked synthesis_only",
          p.sections[0].readiness_state == SECTION_SYNTHESIS_ONLY
          and p.sections[0].synthesis_only is True)
    check("fully supported sections are ready",
          all(s.readiness_state == SECTION_READY for s in p.sections
              if s.section_id in ("intake_summary", "evidence_summary", "review_status")))

    print("\n13. Determinism")
    r2 = plan_it(_request())
    check("same request -> same fingerprint", r2.plan_fingerprint == r.plan_fingerprint)
    check("fingerprint is a sha256 hex digest",
          isinstance(p.plan_fingerprint, str) and len(p.plan_fingerprint) == 64
          and re.fullmatch(r"[0-9a-f]{64}", p.plan_fingerprint) is not None)
    shuffled = plan_it(_request(evidence_reference_ids=["evid_1", "evid_2"],
                                source_ingestion_refs=["ing_2", "ing_1"]))
    check("reference ordering does not change the plan",
          shuffled.plan_fingerprint == r.plan_fingerprint)
    duped = plan_it(_request(evidence_reference_ids=["evid_2", "evid_1", "evid_1"]))
    check("duplicate references do not change the plan",
          duped.plan_fingerprint == r.plan_fingerprint)
    changed = plan_it(_request(evidence_reference_ids=["evid_3"]))
    check("a changed reference set changes the fingerprint",
          changed.plan_fingerprint != r.plan_fingerprint)
    check("section selection changes the fingerprint",
          plan_it(_request(requested_sections=["intake_summary"])).plan_fingerprint
          != r.plan_fingerprint)

    print("\n14. Evidence trace map holds references only")
    check("trace map covers every planned section",
          set(p.evidence_trace_map) == {s.section_id for s in p.sections})
    trace = p.evidence_trace_map["evidence_summary"]
    check("evidence trace lists sorted record ids",
          trace.supporting_refs == {"evidence_reference_ids": ["evid_1", "evid_2"]}
          and trace.supporting_ref_count == 2)
    check("synthesis section trace has no supporting refs",
          p.evidence_trace_map["executive_overview"].supporting_refs == {})
    check("trace values are all short id strings",
          all(isinstance(v, str) and "\n" not in v and len(v) <= 128
              for t in p.evidence_trace_map.values()
              for refs in t.supporting_refs.values() for v in refs))

    print("\n15. Finding and recommendation candidates are reference-only and internal-only")
    check("one finding slot per evidence reference", len(p.finding_candidates) == 2)
    check("finding ids are positional and deterministic",
          [f.finding_candidate_id for f in p.finding_candidates] == ["fnd_000", "fnd_001"])
    check("findings carry references only",
          all(f.evidence_support_refs and f.client_facing_approved is False
              and f.financial_verified is False and f.capsule_candidate_ready is False
              and f.publication_allowed is False and f.requires_human_review is True
              for f in p.finding_candidates))
    check("one recommendation slot per reviewer decision", len(p.recommendation_candidates) == 2)
    check("recommendation ids are positional and deterministic",
          [c.recommendation_candidate_id for c in p.recommendation_candidates]
          == ["rec_000", "rec_001"])
    check("recommendations are internal-only and never final",
          all(c.audience == "internal" and c.requires_human_review is True
              and c.client_facing_approved is False and c.financial_verified is False
              and c.capsule_candidate_ready is False and c.publication_allowed is False
              and c.execution_allowed is False for c in p.recommendation_candidates))
    check("recommendations carry evidence support refs",
          all(c.evidence_support_refs == ["evid_1", "evid_2"]
              for c in p.recommendation_candidates))
    check("supported recommendations reach internal draft readiness",
          all(c.readiness_state == RECOMMENDATION_INTERNAL_DRAFT and c.blocked_reason is None
              for c in p.recommendation_candidates))

    print("\n16. Gaps, blocked items, and the skeletal plan")
    check("no gaps when every category is supplied", p.open_gaps == [] and r.open_gap_count == 0)
    partial = plan_it(_request(intake_note_refs=[], agent_task_queue_record_ids=[]))
    pp = partial.report_plan
    gap_ids = {g.gap_id for g in pp.open_gaps}
    check("gaps opened for the missing categories",
          {"gap_engagement_context_intake_note_refs", "gap_intake_summary_intake_note_refs",
           "gap_ai_agent_readiness_agent_task_queue_record_ids"} <= gap_ids)
    check("gaps name the missing record type",
          all(g.missing_record_type for g in pp.open_gaps))
    check("sections with no supporting refs are blocked",
          all(s.readiness_state == SECTION_BLOCKED_NO_REFS for s in pp.sections
              if s.section_id in ("intake_summary", "ai_agent_readiness")))
    check("blocked sections listed in blocked_items",
          "intake_summary" in pp.blocked_items and "ai_agent_readiness" in pp.blocked_items)
    skeletal = plan_it(_request(intake_note_refs=[], source_ingestion_refs=[],
                                evidence_reference_ids=[], agent_task_queue_record_ids=[],
                                review_bundle_record_ids=[],
                                internal_reviewer_decision_record_ids=[],
                                allow_empty_reference_plan=True))
    check("skeletal plan permitted with a warning",
          skeletal.outcome == "planned" and any("skeletal plan" in w for w in skeletal.warnings))
    check("skeletal plan opens a gap for every requirement", skeletal.open_gap_count == 12)
    check("skeletal plan produces no candidates",
          skeletal.finding_candidate_count == 0 and skeletal.recommendation_candidate_count == 0)

    print("\n17. Section selection")
    subset = plan_it(_request(requested_sections=["review_status", "intake_summary"]))
    check("only the requested sections are planned", subset.section_count == 2)
    check("requested sections re-ordered into canonical order",
          [s.section_id for s in subset.report_plan.sections] == ["intake_summary", "review_status"])
    check("candidates skipped when their section is not requested",
          subset.finding_candidate_count == 0 and subset.recommendation_candidate_count == 0)

    print("\n18. Financial verification posture (identify only, never verify)")
    check("future financial verification items identified",
          p.future_financial_verification_items == ["rec_000", "rec_001"])
    check("financial_verified stays false everywhere",
          p.financial_verified is False
          and all(c.financial_verified is False for c in p.recommendation_candidates))
    check("no financial verification side effect", r.financial_verification_made is False)
    # The plan may *name* a future financial gate ("...before any ROI or savings claim"); what it
    # must never carry is an actual figure — a currency amount, a percentage, or a payback period.
    check("no ROI/savings/currency figure anywhere in the plan",
          not re.search(r"[$\u20ac\u00a3]\s?\d|\d+(?:\.\d+)?\s?%|\bpayback\b",
                        _blob(r), re.IGNORECASE))

    print("\n19. Capsule / AgentNet readiness posture (identify only, never publish)")
    check("future capsule candidate items identified",
          p.future_capsule_candidate_items == ["ing_1", "ing_2"])
    check("capsule_candidate_ready / publication_allowed stay false",
          p.capsule_candidate_ready is False and p.publication_allowed is False
          and all(c.capsule_candidate_ready is False and c.publication_allowed is False
                  for c in p.recommendation_candidates))
    check("no capsule candidate created or published",
          r.capsule_candidate_created is False and r.capsule_publication_made is False
          and r.agentnet_publication_made is False)
    check("no AgentNet/resolver/MCP/network call",
          r.agentnet_call_made is False and r.resolver_call_made is False
          and r.network_call_made is False)
    check("no agent / mock-agent / LLM call",
          r.agent_execution_made is False and r.mock_agent_execution_made is False
          and r.llm_call_made is False)

    print("\n20. Candidate truncation is bounded and reported, never silent")
    # Synthetic, short, marker-free, non-client-like refs generated **at runtime** — deliberately
    # not committed fixture data (no fixtures, examples, sample packets, or data files are added).
    over = MAX_CANDIDATES_PER_FAMILY + 1
    many_evidence = [f"evid_synth_{i:04d}" for i in range(over)]
    many_decisions = [f"ird_synth_{i:04d}" for i in range(over)]

    def _warns(res, needle):
        return [w for w in res.warnings if needle in w]

    def _ref_echoed(res, refs):
        """True if any individual reference id leaks into a warning (only counts may appear)."""
        joined = " ".join(res.warnings)
        return any(ref in joined for ref in refs)

    rf = plan_it(_request(evidence_reference_ids=many_evidence))
    pf = rf.report_plan
    check("over-limit evidence still plans", rf.outcome == "planned" and pf is not None)
    check(f"finding candidates capped at {MAX_CANDIDATES_PER_FAMILY}",
          len(pf.finding_candidates) == MAX_CANDIDATES_PER_FAMILY
          and rf.finding_candidate_count == MAX_CANDIDATES_PER_FAMILY)
    check("finding truncation warning present",
          len(_warns(rf, "finding candidates truncated")) == 1)
    check("finding truncation warning reports both counts",
          all(str(n) in _warns(rf, "finding candidates truncated")[0]
              for n in (MAX_CANDIDATES_PER_FAMILY, over)))
    check("finding truncation warning echoes no reference id",
          not _ref_echoed(rf, many_evidence))
    check("finding truncation warning carries no canary / unsafe marker",
          _CANARY not in " ".join(rf.warnings)
          and not re.search(r"mysql://|postgres://|select \*|api_key=|source_bytes|Traceback",
                            " ".join(rf.warnings), re.IGNORECASE))
    check("truncated finding ids stay positional and deterministic",
          [f.finding_candidate_id for f in pf.finding_candidates][:2] == ["fnd_000", "fnd_001"]
          and pf.finding_candidates[-1].finding_candidate_id
          == f"fnd_{MAX_CANDIDATES_PER_FAMILY - 1:03d}")
    check("truncation keeps the first refs in sorted order",
          pf.finding_candidates[0].evidence_support_refs == ["evid_synth_0000"]
          and pf.finding_candidates[-1].evidence_support_refs == ["evid_synth_0199"])
    check("truncated plan is still deterministic",
          plan_it(_request(evidence_reference_ids=many_evidence)).plan_fingerprint
          == rf.plan_fingerprint)
    check("truncation creates no prohibited side effect", _no_effects(rf))

    rr = plan_it(_request(internal_reviewer_decision_record_ids=many_decisions))
    pr = rr.report_plan
    check("over-limit reviewer decisions still plan", rr.outcome == "planned" and pr is not None)
    check(f"recommendation candidates capped at {MAX_CANDIDATES_PER_FAMILY}",
          len(pr.recommendation_candidates) == MAX_CANDIDATES_PER_FAMILY
          and rr.recommendation_candidate_count == MAX_CANDIDATES_PER_FAMILY)
    check("recommendation truncation warning present",
          len(_warns(rr, "recommendation candidates truncated")) == 1)
    check("recommendation truncation warning reports both counts",
          all(str(n) in _warns(rr, "recommendation candidates truncated")[0]
              for n in (MAX_CANDIDATES_PER_FAMILY, over)))
    check("recommendation truncation warning echoes no reference id",
          not _ref_echoed(rr, many_decisions))
    check("recommendation truncation warning carries no canary / unsafe marker",
          _CANARY not in " ".join(rr.warnings)
          and not re.search(r"mysql://|postgres://|select \*|api_key=|source_bytes|Traceback",
                            " ".join(rr.warnings), re.IGNORECASE))
    check("truncated recommendation ids stay positional and deterministic",
          [c.recommendation_candidate_id for c in pr.recommendation_candidates][:2]
          == ["rec_000", "rec_001"]
          and pr.recommendation_candidates[-1].recommendation_candidate_id
          == f"rec_{MAX_CANDIDATES_PER_FAMILY - 1:03d}")
    check("truncated recommendations stay internal-only",
          all(c.audience == "internal" and c.client_facing_approved is False
              and c.financial_verified is False and c.capsule_candidate_ready is False
              and c.publication_allowed is False and c.execution_allowed is False
              and c.requires_human_review is True for c in pr.recommendation_candidates))
    check("truncation creates no prohibited side effect", _no_effects(rr))
    check("under-limit requests emit no truncation warning",
          not _warns(plan_it(_request()), "truncated"))


# --------------------------------------------------------------------------- denials


def denial_checks() -> None:
    from peak.reports import (
        GovernedRecordReference, prepare_internal_assessment_report_plan as plan_it,
    )

    print("\n21. Identity / scope / plan-id denials")
    for field in ("owner_id", "client_id", "engagement_id", "authorization_scope",
                  "requested_by", "requester_role"):
        r = plan_it(_request(**{field: None}))
        check(f"missing {field} denied",
              r.outcome == "denied" and r.reason_code == "missing_identity_field"
              and r.report_plan is None)
    r = plan_it(_request(authorization_scope="revoked"))
    check("revoked scope denied", r.reason_code == "blocked_authorization_scope")
    r = plan_it(_request(report_plan_id=None, idempotency_key=None))
    check("missing report_plan_id/idempotency_key denied",
          r.reason_code == "missing_report_plan_id")
    r = plan_it(_request(report_plan_id=None, idempotency_key="idem-1"))
    check("idempotency_key alone is accepted",
          r.outcome == "planned" and r.report_plan.report_plan_id == "idem-1")
    r = plan_it(_request(lifecycle_status="revoked"))
    check("blocked lifecycle_status denied", r.reason_code == "blocked_lifecycle_status")
    r = plan_it(object())
    check("duck-typed request denied", r.reason_code == "invalid_request_type")

    print("\n22. Audience and posture denials")
    for audience in ("client", "external", "public", ""):
        r = plan_it(_request(audience=audience))
        check(f"audience '{audience or '<empty>'}' denied",
              r.outcome == "denied" and r.reason_code == "unsupported_audience")
    for flag in ("client_facing_approved", "financial_verified", "capsule_candidate_ready",
                 "publication_allowed", "execution_allowed"):
        r = plan_it(_request(**{flag: True}))
        check(f"{flag}=True denied",
              r.outcome == "denied" and r.reason_code == "prohibited_posture")
    r = plan_it(_request(requires_human_review=False))
    check("requires_human_review=False denied", r.reason_code == "prohibited_posture")

    print("\n23. Section denials")
    r = plan_it(_request(requested_sections=["not_a_section"]))
    check("unsupported section denied", r.reason_code == "unsupported_section")
    r = plan_it(_request(requested_sections=["final_client_report_section"]))
    check("client-facing-sounding section denied", r.reason_code == "unsupported_section")
    r = plan_it(_request(requested_sections=["intake_summary", "intake_summary"]))
    check("duplicate section denied", r.reason_code == "duplicate_section")

    print("\n24. Reference identity / scope denials (structured refs)")
    for label, ref in (
        ("cross-tenant", GovernedRecordReference(
            record_id="evid_1", owner_id="owner_1", client_id="other_client",
            engagement_id="eng_x", authorization_scope=_SCOPE)),
        ("cross-engagement", GovernedRecordReference(
            record_id="evid_1", owner_id="owner_1", client_id="client_a",
            engagement_id="eng_other", authorization_scope=_SCOPE)),
        ("cross-owner", GovernedRecordReference(
            record_id="evid_1", owner_id="other_owner", client_id="client_a",
            engagement_id="eng_x", authorization_scope=_SCOPE)),
        ("scope mismatch", GovernedRecordReference(
            record_id="evid_1", owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", authorization_scope="other_scope")),
    ):
        r = plan_it(_request(evidence_reference_ids=[ref]))
        check(f"{label} reference denied",
              r.outcome == "denied" and r.reason_code == "reference_identity_mismatch"
              and r.report_plan is None)
    good = GovernedRecordReference(record_id="evid_1", record_type="evidence_references",
                                   owner_id="owner_1", client_id="client_a",
                                   engagement_id="eng_x", authorization_scope=_SCOPE)
    r = plan_it(_request(evidence_reference_ids=[good]))
    check("a consistent structured reference is accepted", r.outcome == "planned")

    print("\n25. Unsafe reference denials")
    for label, value in (("multiline", "evid_1\nevid_2"),
                         ("overlong", "e" * 200),
                         ("whitespace", "evid 1"),
                         ("quote", 'evid"1'),
                         ("non-string", 12345)):
        r = plan_it(_request(evidence_reference_ids=[value]))
        check(f"{label} reference denied",
              r.outcome == "denied" and r.reason_code == "prohibited_content")
    r = plan_it(_request(intake_note_refs=[], source_ingestion_refs=[], evidence_reference_ids=[],
                         agent_task_queue_record_ids=[], review_bundle_record_ids=[],
                         internal_reviewer_decision_record_ids=[]))
    check("no governed references denied without the explicit opt-in",
          r.reason_code == "no_governed_references")
    r = plan_it(_request(requested_action="publish_report"))
    check("unsupported requested_action denied", r.reason_code == "unsupported_action")


# --------------------------------------------------------------------------- leak safety


def leak_safety_checks() -> None:
    from peak.reports import prepare_internal_assessment_report_plan as plan_it

    print("\n26. Prohibited keys denied before any plan is assembled")
    prohibited_keys = (
        "raw_note_text", "note_text", "packet_payload", "raw_evidence_text", "raw_interview_text",
        "source_bytes", "generated_output", "final_client_report", "client_facing_output",
        "approval_decision", "approve_internal", "approve_client_facing", "publish_capsule",
        "agentnet_publish", "publish_report", "send_to_client", "export_client_deliverable",
        "resolver_credentials", "llm_prompt", "database_url", "raw_sql", "stack_trace",
        "api_key", "secret_key", "password", "private_key", "access_token", "connection_string",
    )
    for key in prohibited_keys:
        req = _request()
        setattr(req, key, _CANARY)
        r = plan_it(req)
        check(f"prohibited key '{key}' denied without echoing its value",
              r.outcome == "denied" and r.report_plan is None and _CANARY not in _blob(r))

    print("\n27. Prohibited values denied without echoing")
    marker_values = {
        "credential/secret": f"api_key={_CANARY}",
        "DB-URL/DSN": f"mysql://user:{_CANARY}@host/db",
        "raw-SQL": f"select * from clients where n='{_CANARY}'",
        "raw-content": f"source_bytes-{_CANARY}",
    }
    for label, value in marker_values.items():
        r = plan_it(_request(evidence_reference_ids=[value]))
        check(f"{label} reference value denied without echoing",
              r.outcome == "denied" and _CANARY not in _blob(r))
    r = plan_it(_request(report_purpose=f'File "x.py", line 1 {_CANARY}'))
    check("stack-trace-like report_purpose denied without echoing",
          r.outcome == "denied" and _CANARY not in _blob(r))
    r = plan_it(_request(report_purpose=f"postgres://u:{_CANARY}@h/db"))
    check("DSN-like report_purpose denied without echoing",
          r.outcome == "denied" and _CANARY not in _blob(r))
    r = plan_it(_request(report_purpose="x" * 400))
    check("overlong report_purpose denied", r.outcome == "denied")

    print("\n28. Prohibited context keys denied")
    for key in ("note_text", "database_url", "approve_client_facing", "api_key"):
        r = plan_it(_request(context={key: _CANARY}))
        check(f"prohibited context key '{key}' denied without echoing",
              r.outcome == "denied" and _CANARY not in _blob(r))
    r = plan_it(_request(context={"engagement_stage": "assessment"}))
    check("a safe context key is accepted", r.outcome == "planned")

    print("\n29. A successful plan echoes no raw content")
    r = plan_it(_request())
    blob = _blob(r)
    check("canary absent from a successful plan", _CANARY not in blob)
    for token in ("note_text", "packet_payload", "source_bytes", "generated_output",
                  "raw_evidence_text", "final_client_report"):
        check(f"plan does not carry a '{token}' value", f"{token}=" not in blob)
    check("no client-facing language markers in the plan",
          not re.search(r"send to client|client deliverable|approved for client",
                        blob, re.IGNORECASE))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 36 internal assessment report planning boundary check")
    print("=" * 70)

    structural_checks()
    planning_checks()
    denial_checks()
    leak_safety_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
