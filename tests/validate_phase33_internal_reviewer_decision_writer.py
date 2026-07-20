#!/usr/bin/env python3
"""Phase 33 controlled-DB internal-reviewer-decision-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/migration/doc files exist and compile;
  the Phase 32 ``peak/reviewer_decisions`` package stays DB-free; the writer imports no
  LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential, and no Phase
  22 review writer; the migration is additive schema-only (creates one table, no INSERT/seed,
  down_revision 007); the docs carry the required language; the repo stays source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local SQLite
  database — migration upgrade/downgrade/re-upgrade, successful create (safe references only),
  idempotent replay, conflicting replay, DB-backed authorization (stored-scope comparison),
  identity/allowlist checks, decision-intent/posture/content rejections, non-approval posture,
  the Phase 32 value-safety hardening preserved at write time, side-effect discipline (no
  ``review_records``/``agent_run_records`` write), and transaction/failure semantics. Skipped with
  instructions if SQLAlchemy is absent (still exits 0).

Phase 33 approves nothing, calls no Phase 22 review writer, creates no ``review_records`` or
``agent_run_records`` row, never calls ``approve_internal``, executes no agent, makes no
LLM/MockLLM/AgentNet/MCP/resolver/connector/network call, and performs no client-facing output /
financial verification / capsule publication. It creates exactly one review-gated, non-approval
``internal_reviewer_decision_records`` row. ``ready_for_internal_use`` is not approval.

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
    "peak/db/internal_reviewer_decision_writer.py",
    "peak/db/writer_contracts.py",
    "alembic/versions/008_internal_reviewer_decision_records.py",
    "docs/INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md",
    "docs/INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md",
]
WRITER_FILES = ["peak/db/internal_reviewer_decision_writer.py", "peak/db/writer_contracts.py"]
PHASE32_FILES = [
    "peak/reviewer_decisions/__init__.py",
    "peak/reviewer_decisions/contracts.py",
    "peak/reviewer_decisions/governance.py",
    "peak/reviewer_decisions/decision_mapper.py",
]
COMPILE_FILES = WRITER_FILES + ["alembic/versions/008_internal_reviewer_decision_records.py"]
DOCS = ["docs/INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md",
        "docs/INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md"]
REQUIRED_PHRASES = [
    "write-time",
    "stored engagement is authoritative",
    "identity matching is necessary but not sufficient",
    "idempotent_replay",
    "idempotency_conflict",
    "write_outcome_uncertain",
    "review-gated",
    "non-approval",
    "ready_for_internal_use",
    "approve_internal",
    "output_status=draft",
    "review_status=needs_review",
    "lifecycle_status=draft",
    "review_records",
    "server-stamped",
    "14 tables",
    "create_internal_reviewer_decision_record",
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
    r"\b(?:agentnet|mcp_connector|resolver_client)\b", re.IGNORECASE)
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

    print("\n3. Phase 32 reviewer_decisions package stays DB-free")
    for rel in PHASE32_FILES:
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

    print("\n4b. Public value-marker classifier (public API boundary, not a private helper)")
    import peak.reviewer_decisions.governance as gov
    check("classify_prohibited_value_marker is public (exported, no leading underscore)",
          hasattr(gov, "classify_prohibited_value_marker"))
    # DB-free: the classifier's module imports no SQLAlchemy/Alembic/peak.db.
    gov_imports = list(_import_lines(read("peak/reviewer_decisions/governance.py")))
    check("classifier module stays DB-free",
          not [ln for ln in gov_imports if DB_IMPORT_RE.search(ln) or PEAK_DB_RE.search(ln)])
    classify = getattr(gov, "classify_prohibited_value_marker", None)
    if callable(classify):
        check("classifier: credential -> 'credential/secret'",
              classify("api_key=zzz") == "credential/secret")
        check("classifier: DSN -> 'DB-URL/DSN'",
              classify("postgres://u@h:5432/db") == "DB-URL/DSN")
        check("classifier: SELECT * -> 'raw-SQL'",
              classify("SELECT * FROM engagements") == "raw-SQL")
        check("classifier: UPDATE ... SET -> 'raw-SQL'",
              classify("UPDATE engagements SET x=1") == "raw-SQL")
        check("classifier: JSON blob -> 'JSON/object'", classify('{"a": 1}') == "JSON/object")
        check("classifier: benign note -> None",
              classify("please update the review note") is None)
        check("classifier: non-string -> None", classify(None) is None)
    else:
        check("classify_prohibited_value_marker callable", False)
    # The writer must consume the PUBLIC classifier, not the private helper.
    writer_src = read("peak/db/internal_reviewer_decision_writer.py")
    check("writer imports the public classifier",
          "classify_prohibited_value_marker" in writer_src)
    check("writer does not reference the private _value_marker_category",
          "_value_marker_category" not in writer_src)

    print("\n5. Migration is additive, creates one table, schema-only (no INSERT/seed)")
    mig = read("alembic/versions/008_internal_reviewer_decision_records.py")
    low = mig.lower()
    check("migration has no insert/seed pattern", not any(p in low for p in INSERT_PATTERNS))
    check("migration defines upgrade()", "def upgrade()" in mig)
    check("migration defines downgrade()", "def downgrade()" in mig)
    check("migration creates the table", "op.create_table" in mig)
    check("migration targets internal_reviewer_decision_records",
          "internal_reviewer_decision_records" in mig)
    check("migration adds unique idempotency index",
          "uq_internal_reviewer_decision_records_idem" in mig)
    check("migration down_revision is 007_review_bundle_records",
          'down_revision = "007_review_bundle_records"' in mig)
    check("downgrade drops the table", "op.drop_table" in mig)

    print("\n6. Doc language")
    blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"phrase present: '{phrase}'", phrase.lower() in blob)

    print("\n7. Allowlist recognizes exactly the new table/action (no broadening)")
    from peak.persistence.allowlist import (
        is_allowed_action, is_allowed_table, is_prohibited_action,
    )
    check("internal_reviewer_decision_records allowed",
          is_allowed_table("internal_reviewer_decision_records"))
    check("create_internal_reviewer_decision_record allowed",
          is_allowed_action("create_internal_reviewer_decision_record"))
    for bad in ("approve_internal", "update_internal_reviewer_decision",
                "delete_internal_reviewer_decision", "publish_capsule", "verify_financial_impact",
                "run_raw_sql", "client_facing_approve_decision"):
        check(f"prohibited/absent action '{bad}' not allowed",
              not is_allowed_action(bad) or is_prohibited_action(bad))

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

_SENTINEL = "SENSITIVE-DO-NOT-LEAK"
_CANARY = "CANARY-DO-NOT-LEAK"
_KEY = "idem-ird-1"


def _make_builders():
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.reviewer_decisions.contracts import (
        InternalReviewerDecisionDraft, InternalReviewerDecisionRequest,
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
            reviewer_decision_id=None, owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", review_bundle_ref="rvb_ref_1", review_bundle_record_id="rvb_1",
            review_bundle_draft_ref="rvb_draft_1",
            review_plan_item_refs=["rpi_1", "rpi_2"], evidence_reference_ids=["evid_1"],
            source_ingestion_record_ids=["ing_1"], agent_task_queue_record_ids=["atq_1"],
            reviewer_role="internal_reviewer", decision_intent="ready_for_internal_use",
            decision_reason_code="meets_internal_bar",
            safe_decision_summary="internally reliable for planning",
            return_to_stage=None, requested_followup_actions=["schedule_internal_followup"],
            authorization_scope="engagement_authorized", output_status="draft",
            review_status="needs_review", lifecycle_status="draft", authoritative=False,
            client_facing_approved=False, capsule_candidate_ready=False, financial_verified=False,
            execution_allowed=False, approval_allowed=False, publication_allowed=False,
            requires_human_review=True, client_facing_output_created=False,
            review_approval_made=False, reasons=[], warnings=["decision plan only"], created_at=None)
        base.update(over)
        return InternalReviewerDecisionDraft(**base)

    def dreq(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized", idempotency_key=_KEY,
            requested_action="prepare_internal_reviewer_decision", lifecycle_status="active")
        base.update(over)
        return InternalReviewerDecisionRequest(**base)

    def build(*, draft_over=None, subject_over=None, **cwr_over):
        d = draft(**(draft_over or {}))
        subj = subject(**(subject_over or {}))
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            target_table="internal_reviewer_decision_records",
            requested_action="create_internal_reviewer_decision_record",
            subject=subj, record_draft=d, source_phase="phase32", lifecycle_status="active",
            idempotency_key=_KEY)
        base.update(cwr_over)
        return ControlledWriteRequest(**base), d, dreq()

    return subject, draft, dreq, build


def _migration_reversibility() -> None:
    from sqlalchemy import create_engine, inspect
    from alembic.config import Config
    from alembic import command

    print("\n9. Migration apply / reversibility (temp SQLite)")
    tmp = tempfile.mkdtemp(prefix="peak_phase33_mig_")
    prev_url = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        check("upgrade created internal_reviewer_decision_records",
              "internal_reviewer_decision_records" in insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns("internal_reviewer_decision_records")}
        check("table carries posture + routing + idempotency columns",
              {"decision_intent", "route_to", "approval_allowed", "financial_verified",
               "publication_allowed", "requires_human_review", "review_approval_made",
               "client_facing_output_created", "idempotency_key", "payload_fingerprint"} <= cols)
        idx = {i["name"]: (i.get("unique"), i["column_names"])
               for i in insp.get_indexes("internal_reviewer_decision_records")}
        check("unique idempotency index over (owner,client,engagement,key)",
              idx.get("uq_internal_reviewer_decision_records_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        command.downgrade(cfg, "007_review_bundle_records")
        check("downgrade drops the table",
              "internal_reviewer_decision_records"
              not in inspect(create_engine(url)).get_table_names())
        command.upgrade(cfg, "head")
        check("re-upgrade succeeds", True)
    finally:
        if prev_url is None:
            os.environ.pop("PEAK_DATABASE_URL", None)
        else:
            os.environ["PEAK_DATABASE_URL"] = prev_url
        shutil.rmtree(tmp, ignore_errors=True)


def _blob(receipt) -> str:
    return " ".join(list(receipt.reasons or []) + list(receipt.warnings or []))


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    import peak.db.internal_reviewer_decision_writer as writer_mod
    from peak.db.internal_reviewer_decision_writer import (
        build_decision_controlled_write_request, persist_internal_reviewer_decision_record,
    )
    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, InternalReviewerDecisionRecord, ReviewRecord,
    )
    from peak.db.writer_contracts import InternalReviewerDecisionWriteOutcome as OC

    _migration_reversibility()

    subject, draft, dreq, build = _make_builders()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase33_")
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
    print("\n10. Successful create (safe references only, non-approval)")
    f = fresh_db()
    seed(f)
    cwr, d, dr = build()
    r = persist_internal_reviewer_decision_record(cwr, session_factory=f, decision_request=dr)
    check("outcome == created", r.outcome == OC.CREATED)
    check("permitted True", r.permitted is True)
    check("exactly one row created", count(f, InternalReviewerDecisionRecord) == 1)
    check("server-generated id (ird_ prefix)",
          bool(r.stored_record_id) and r.stored_record_id.startswith("ird_"))
    check("receipt created_at present", bool(r.created_at))
    check("receipt decision posture",
          r.review_status == "needs_review" and r.output_status == "draft"
          and r.lifecycle_status == "draft" and r.decision_intent == "ready_for_internal_use"
          and r.route_to == "internal_report_planning_candidate")
    check("flags: connection/sql/write/commit/created all True",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.transaction_committed and r.stored_record_created)
    check("flags: existing_record_returned / outcome_uncertain False",
          r.existing_record_returned is False and r.outcome_uncertain is False)
    check("non-effect flags all False",
          r.review_records_write_made is False and r.review_approval_made is False
          and r.client_facing_output_created is False and r.financial_verification_made is False
          and r.capsule_publication_made is False and r.agent_execution_made is False
          and r.llm_call_made is False and r.agentnet_call_made is False
          and r.resolver_call_made is False and r.network_call_made is False)
    s = f()
    row = s.get(InternalReviewerDecisionRecord, r.stored_record_id)
    check("stored posture columns safe (non-approval)",
          row.output_status == "draft" and row.review_status == "needs_review"
          and row.lifecycle_status == "draft" and row.authoritative is False
          and row.client_facing_approved is False and row.capsule_candidate_ready is False
          and row.financial_verified is False and row.execution_allowed is False
          and row.approval_allowed is False and row.publication_allowed is False
          and row.requires_human_review is True and row.client_facing_output_created is False
          and row.review_approval_made is False)
    check("stored reviewer_role / decision_intent / route_to / reason_code",
          row.reviewer_role == "internal_reviewer"
          and row.decision_intent == "ready_for_internal_use"
          and row.route_to == "internal_report_planning_candidate"
          and row.decision_reason_code == "meets_internal_bar")
    check("ready_for_internal_use stored but NOT approval",
          row.decision_intent == "ready_for_internal_use" and row.approval_allowed is False
          and row.review_approval_made is False and row.client_facing_approved is False)
    check("stored safe review-bundle refs",
          row.review_bundle_ref == "rvb_ref_1" and row.review_bundle_record_id == "rvb_1"
          and row.review_bundle_draft_ref == "rvb_draft_1")
    check("safe references stored (plan/evidence/source/task ids + followups)",
          row.details_json.get("review_plan_item_refs") == ["rpi_1", "rpi_2"]
          and row.details_json.get("evidence_reference_ids") == ["evid_1"]
          and row.details_json.get("source_ingestion_record_ids") == ["ing_1"]
          and row.details_json.get("agent_task_queue_record_ids") == ["atq_1"]
          and row.details_json.get("requested_followup_actions") == ["schedule_internal_followup"])
    check("NO raw payload/content/approval stored",
          all(k not in row.details_json for k in
              ("packet_payload", "raw_evidence_text", "raw_interview_text", "source_bytes",
               "generated_output", "approval_decision"))
          and not hasattr(row, "packet_payload"))
    check("idempotency_key + payload_fingerprint persisted",
          bool(row.idempotency_key) and bool(row.payload_fingerprint))
    check("created_at server-stamped", row.created_at is not None)
    s.close()

    print("\n11. Side-effect discipline (no review_records / agent_run_records / unrelated)")
    check("NO review_records row created", count(f, ReviewRecord) == 0)
    check("NO agent_run_records row created", count(f, AgentRunRecord) == 0)
    check("clients untouched", count(f, Client) == 0)

    # ---- Planning helper builds an equivalent CWR ----
    print("\n12. Phase 33 CWR planning helper (DB-layer bridge)")
    f = fresh_db()
    seed(f)
    d2 = draft()
    cwr2 = build_decision_controlled_write_request(
        d2, requested_by="consultant_a", requester_role="consultant", idempotency_key="idem-ird-h")
    check("helper targets the one table/action",
          cwr2.target_table == "internal_reviewer_decision_records"
          and cwr2.requested_action == "create_internal_reviewer_decision_record")
    rh = persist_internal_reviewer_decision_record(cwr2, session_factory=f)
    check("helper-built request persists one row",
          rh.outcome == OC.CREATED and count(f, InternalReviewerDecisionRecord) == 1)

    # ---- Idempotent replay ----
    print("\n13. Idempotent replay")
    f = fresh_db()
    seed(f)
    first = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    second = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    check("second outcome idempotent_replay", second.outcome == OC.IDEMPOTENT_REPLAY)
    check("no second row", count(f, InternalReviewerDecisionRecord) == 1)
    check("existing id returned", second.stored_record_id == first.stored_record_id)
    check("replay reports no new record",
          second.stored_record_created is False and second.database_write_made is False
          and second.existing_record_returned is True)

    # ---- Conflicting replay ----
    print("\n14. Conflicting replay")
    f = fresh_db()
    seed(f)
    created = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    conflict = persist_internal_reviewer_decision_record(
        build(draft_over=dict(decision_reason_code="a_different_reason"))[0], session_factory=f)
    check("conflict denied", conflict.outcome == OC.DENIED)
    check("conflict reason idempotency_conflict", conflict.reason_code == "idempotency_conflict")
    check("no new row on conflict", count(f, InternalReviewerDecisionRecord) == 1)
    s = f()
    check("existing row unchanged (decision_reason_code)",
          s.get(InternalReviewerDecisionRecord, created.stored_record_id).decision_reason_code
          == "meets_internal_bar")
    s.close()

    # ---- DB-backed authorization ----
    print("\n15. DB-backed authorization (stored-scope comparison)")
    f = fresh_db()
    seed(f, authorization_scope="internal_peak_only")
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    check("stored-scope mismatch denied",
          r.outcome == OC.DENIED and r.reason_code == "stored_scope_mismatch")
    check("no row on scope mismatch", count(f, InternalReviewerDecisionRecord) == 0)
    check("connection+sql made, no write",
          r.database_connection_made and r.sql_execution_made and r.database_write_made is False)
    f = fresh_db()
    seed(f, authorization_scope=None)
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    check("missing stored scope denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_stored_scope")
    f = fresh_db()
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    check("missing stored subject denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")
    f = fresh_db()
    seed(f)
    r = persist_internal_reviewer_decision_record(build(authorization_scope=None)[0], session_factory=f)
    check("missing request scope denied (pre-DB)",
          r.outcome == OC.DENIED and r.database_connection_made is False)
    check("missing request scope: no row", count(f, InternalReviewerDecisionRecord) == 0)
    f = fresh_db()
    seed(f, lifecycle_status="revoked")
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    check("prohibited stored lifecycle denied",
          r.outcome == OC.DENIED and r.reason_code == "subject_lifecycle_blocked")

    # ---- Stored identity mismatches ----
    print("\n16. Stored identity mismatches")
    for over, label in ((dict(owner_id="owner_2"), "owner"), (dict(client_id="client_b"), "client")):
        f = fresh_db()
        seed(f, **over)
        r = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
        check(f"stored {label} mismatch denied",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch")
    f = fresh_db()
    seed(f, id="eng_other")
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    check("stored engagement mismatch (subject absent) denied",
          r.outcome == OC.DENIED and r.reason_code == "missing_subject")

    # ---- Draft/request identity (pre-DB) ----
    print("\n17. Draft/request identity mismatches (pre-DB)")
    for attr in ("owner_id", "client_id", "engagement_id"):
        r = persist_internal_reviewer_decision_record(
            build(draft_over={attr: "WRONG"})[0], session_factory=fresh_db())
        check(f"draft {attr} mismatch denied (pre-DB)",
              r.outcome == OC.DENIED and r.reason_code == "identity_mismatch"
              and r.database_connection_made is False)
    r = persist_internal_reviewer_decision_record(
        build(draft_over={"authorization_scope": "other"})[0], session_factory=fresh_db())
    check("draft↔request scope mismatch denied (pre-DB)",
          r.outcome == OC.DENIED and r.reason_code == "identity_mismatch"
          and r.database_connection_made is False)
    r = persist_internal_reviewer_decision_record(
        build(authorization_scope="other")[0], session_factory=fresh_db())
    check("request↔subject scope mismatch denied (pre-DB)",
          r.outcome == OC.DENIED and r.database_connection_made is False)

    # ---- Table/action allowlist ----
    print("\n18. Table/action allowlist")
    r = persist_internal_reviewer_decision_record(
        build(target_table="review_records")[0], session_factory=fresh_db())
    check("review_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_internal_reviewer_decision_record(
        build(target_table="agent_run_records")[0], session_factory=fresh_db())
    check("agent_run_records target rejected",
          r.outcome == OC.DENIED and r.reason_code == "wrong_target_table")
    r = persist_internal_reviewer_decision_record(
        build(requested_action="create_review_record")[0], session_factory=fresh_db())
    check("wrong action denied", r.outcome == OC.DENIED and r.reason_code == "wrong_target_action")
    for bad in ("approve_internal", "update_internal_reviewer_decision",
                "delete_internal_reviewer_decision", "publish_capsule", "execute_agent",
                "client_facing_approve_decision", "verify_financial_impact", "run_raw_sql"):
        r = persist_internal_reviewer_decision_record(
            build(requested_action=bad)[0], session_factory=fresh_db())
        check(f"prohibited action '{bad}' denied", r.outcome == OC.DENIED)

    # ---- Decision-intent denials ----
    print("\n19. Decision-intent denials (approval/publication/execution/financial/client-facing)")
    for bad in ("approve_internal", "approve_client_facing", "final_approval", "publish_capsule",
                "verify_financial_impact", "execute_agent", "create_report_for_client",
                "send_to_client"):
        f = fresh_db()
        seed(f)
        r = persist_internal_reviewer_decision_record(
            build(draft_over=dict(decision_intent=bad))[0], session_factory=f)
        check(f"decision_intent '{bad}' denied",
              r.outcome == OC.DENIED and r.reason_code == "disallowed_decision_intent"
              and r.database_connection_made is False
              and count(f, InternalReviewerDecisionRecord) == 0)
    for intent in ("needs_more_evidence", "return_for_revision", "ready_for_internal_use",
                   "blocked_by_scope", "blocked_by_quality", "blocked_by_missing_source",
                   "rejected_for_policy", "defer_review"):
        f = fresh_db()
        seed(f)
        over = dict(decision_intent=intent)
        if intent == "return_for_revision":
            over["return_to_stage"] = "evidence"
        r = persist_internal_reviewer_decision_record(
            build(draft_over=over)[0], session_factory=f)
        check(f"allowed intent '{intent}' persists",
              r.outcome == OC.CREATED and count(f, InternalReviewerDecisionRecord) == 1)

    # ---- Posture / caller-field rejections (pre-DB) ----
    print("\n20. Posture / caller-field rejections")
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
        "client_facing_output_created true": (dict(client_facing_output_created=True),
                                              "prohibited_client_facing_output"),
        "review_approval_made true": (dict(review_approval_made=True), "prohibited_review_approval"),
        "requires_human_review false": (dict(requires_human_review=False),
                                        "prohibited_no_human_review"),
        "caller-supplied id": (dict(reviewer_decision_id="ird_caller"), "caller_supplied_id"),
        "caller-supplied timestamp": (dict(created_at="2026-01-01T00:00:00"),
                                      "caller_supplied_timestamp"),
    }
    for label, (draft_over, code) in posture_cases.items():
        f = fresh_db()
        seed(f)
        r = persist_internal_reviewer_decision_record(
            build(draft_over=draft_over)[0], session_factory=f)
        check(f"{label} denied ({code})",
              r.outcome == OC.DENIED and r.reason_code == code
              and r.database_connection_made is False
              and count(f, InternalReviewerDecisionRecord) == 0)

    # ---- Content / decision / secret attribute guard ----
    print("\n21. Content / decision / secret attribute guard (rejected without echoing values)")
    for inj_attr in ("packet_payload", "raw_evidence_text", "raw_interview_text", "source_bytes",
                     "generated_output", "database_url", "raw_sql", "approval_decision", "api_key",
                     "connection_string", "token", "credential"):
        f = fresh_db()
        seed(f)
        cwr, d, dr = build()
        setattr(d, inj_attr, {"x": "y"} if inj_attr.endswith("payload") else _SENTINEL)
        r = persist_internal_reviewer_decision_record(cwr, session_factory=f, decision_request=dr)
        check(f"draft with '{inj_attr}' rejected",
              r.outcome == OC.DENIED and r.reason_code == "prohibited_content"
              and count(f, InternalReviewerDecisionRecord) == 0)
        check(f"'{inj_attr}' reason does not echo value", _SENTINEL not in _blob(r))

    # ---- Value-safety hardening (Phase 32 markers preserved at write time) ----
    print("\n22. Value-safety hardening on summary/followup (non-echoing)")
    f = fresh_db()
    seed(f)
    r_sec = persist_internal_reviewer_decision_record(
        build(draft_over=dict(safe_decision_summary=f"api_key={_CANARY}"))[0], session_factory=f)
    check("summary with credential marker -> denied blocked_secret_like_content",
          r_sec.outcome == OC.DENIED and r_sec.reason_code == "blocked_secret_like_content"
          and count(f, InternalReviewerDecisionRecord) == 0)
    check("summary secret value not echoed", _CANARY not in _blob(r_sec))
    r_dsn = persist_internal_reviewer_decision_record(
        build(draft_over=dict(safe_decision_summary=f"postgres://u@h:5432/{_CANARY}"))[0],
        session_factory=fresh_db())
    check("summary with 'postgres://' -> denied blocked_raw_content",
          r_dsn.outcome == OC.DENIED and r_dsn.reason_code == "blocked_raw_content")
    check("summary DSN value not echoed", _CANARY not in _blob(r_dsn))
    r_sql = persist_internal_reviewer_decision_record(
        build(draft_over=dict(safe_decision_summary=f"SELECT * FROM engagements WHERE id='{_CANARY}'"))[0],
        session_factory=fresh_db())
    check("summary with 'SELECT *' -> denied blocked_raw_content",
          r_sql.outcome == OC.DENIED and r_sql.reason_code == "blocked_raw_content")
    check("summary raw-SQL value not echoed", _CANARY not in _blob(r_sql))
    r_upd = persist_internal_reviewer_decision_record(
        build(draft_over=dict(safe_decision_summary="UPDATE engagements SET flag=1"))[0],
        session_factory=fresh_db())
    check("summary with 'UPDATE ... SET' -> denied blocked_raw_content",
          r_upd.outcome == OC.DENIED and r_upd.reason_code == "blocked_raw_content")
    r_fu = persist_internal_reviewer_decision_record(
        build(draft_over=dict(requested_followup_actions=[f"token={_CANARY}"]))[0],
        session_factory=fresh_db())
    check("followup with secret marker -> denied blocked_secret_like_content",
          r_fu.outcome == OC.DENIED and r_fu.reason_code == "blocked_secret_like_content")
    check("followup secret value not echoed", _CANARY not in _blob(r_fu))
    # Harmless "please update the review note" summary remains allowed.
    f = fresh_db()
    seed(f)
    r_ok = persist_internal_reviewer_decision_record(
        build(draft_over=dict(safe_decision_summary="please update the review note"))[0],
        session_factory=f)
    check("harmless 'please update the review note' summary allowed",
          r_ok.outcome == OC.CREATED and count(f, InternalReviewerDecisionRecord) == 1)

    # ---- Duck-typed rejection ----
    print("\n23. Duck-typed / malformed rejection")
    class _Fake:
        target_table = "internal_reviewer_decision_records"
        requested_action = "create_internal_reviewer_decision_record"
    r = persist_internal_reviewer_decision_record(_Fake(), session_factory=fresh_db())
    check("duck-typed request denied",
          r.outcome == OC.DENIED and r.reason_code == "invalid_request_type"
          and r.database_connection_made is False)
    cwr_bad, _, _ = build()
    cwr_bad.record_draft = object()  # present (passes Phase 17) but not an InternalReviewerDecisionDraft
    r = persist_internal_reviewer_decision_record(cwr_bad, session_factory=fresh_db())
    check("non-draft record_draft denied",
          r.outcome == OC.DENIED and r.reason_code == "invalid_record_draft"
          and r.database_connection_made is False)

    # ---- Transaction / failure semantics ----
    print("\n24. Transaction and failure semantics")

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
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=fail_get)
    check("failed_before_write on read failure",
          r.outcome == OC.FAILED_BEFORE_WRITE and r.database_write_made is False)
    check("failed_before_write left no row", count(f, InternalReviewerDecisionRecord) == 0)

    f = fresh_db()
    seed(f)
    fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
    r = persist_internal_reviewer_decision_record(build()[0], session_factory=fail_commit)
    check("write_outcome_uncertain on commit failure",
          r.outcome == OC.WRITE_OUTCOME_UNCERTAIN and r.outcome_uncertain is True)
    check("uncertain does not claim no record", "no row" not in _blob(r).lower())

    # IntegrityError race branch (force pre-check miss).
    f = fresh_db()
    seed(f)
    createdA = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
    orig_find = writer_mod._find_existing
    try:
        writer_mod._find_existing = lambda *a, **k: None
        rrep = persist_internal_reviewer_decision_record(build()[0], session_factory=f)
        check("race -> idempotent_replay",
              rrep.outcome == OC.IDEMPOTENT_REPLAY
              and rrep.stored_record_id == createdA.stored_record_id)
        check("race replay left one row", count(f, InternalReviewerDecisionRecord) == 1)
        rconf = persist_internal_reviewer_decision_record(
            build(draft_over=dict(decision_reason_code="race_conflict"))[0], session_factory=f)
        check("race -> conflict denied",
              rconf.outcome == OC.DENIED and rconf.reason_code == "idempotency_conflict")
        check("race conflict left one row", count(f, InternalReviewerDecisionRecord) == 1)
    finally:
        writer_mod._find_existing = orig_find

    print("\n25. Rollback safety")
    check("no partial row after failure paths", count(f, InternalReviewerDecisionRecord) == 1)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 33 controlled-DB internal-reviewer-decision-writer check")
    print("=" * 66)

    structural_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
        print("         Run: make validate-phase33 PYTHON=.venv/bin/python")
    else:
        print(f"  SQLAlchemy {sqlalchemy.__version__} present — running DB-backed checks.")
        db_backed_checks()

    print("\n" + "=" * 66)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    if _failures:
        print(f"\nRESULT: {FAIL} ({len(_failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
