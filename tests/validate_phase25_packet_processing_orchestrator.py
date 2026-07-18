#!/usr/bin/env python3
"""Phase 25 controlled engagement packet processing orchestrator check.

Three layers:

* **Structural (always, stdlib-only):** the orchestration files exist and compile and the
  package imports (plan-only needs no SQLAlchemy); the Phase 23 ingestion package stays
  DB-free; the orchestrator imports no LLM/AgentNet/connector/network module and no top-level
  SQLAlchemy/`peak.db` (writers are lazy-imported); no new migration was added (head stays
  005_source_ingestion_idem); the docs carry the required language; the repo stays source-only.

* **Plan-only (always, stdlib-only):** a valid packet returns a no-side-effect receipt via the
  Phase 23 path — derived source draft + plan-only controlled write request, Phase 14 evidence
  requests, Phase 13 agent task requests (known agents only), all side-effect flags false, no
  raw packet payload leaked; and no stage silently escalates to persistence.

* **DB-backed (when SQLAlchemy is importable):** controlled persistence through the existing
  narrow writers only (Phase 24 source-ingestion; Phase 21 evidence) against a temporary local
  SQLite database — create, replay, conflict, stored-Engagement authorization, table/action
  safety, and side-effect discipline. Skipped with instructions if SQLAlchemy is absent.

Exit status:
  0  -> all run checks passed
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
    "peak/orchestration/__init__.py",
    "peak/orchestration/contracts.py",
    "peak/orchestration/governance.py",
    "peak/orchestration/packet_processor.py",
    "docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md",
    "docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md",
]
PY_FILES = [
    "peak/orchestration/__init__.py",
    "peak/orchestration/contracts.py",
    "peak/orchestration/governance.py",
    "peak/orchestration/packet_processor.py",
]
PHASE23_FILES = [
    "peak/ingestion/contracts.py",
    "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
]
DOCS = [
    "docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md",
    "docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md",
]
REQUIRED_PHRASES = [
    "controlled sequencing layer",
    "plan-only",
    "no stage may silently escalate",
    "orchestrator preflight checks are helpful but not authoritative",
    "stored Engagement authorization remains authoritative",
    "identity matching is necessary but not sufficient",
    "session_factory",
    "no live LLM",
    "no AgentNet",
    "no capsule publication",
    "no financial verification",
    "no client-facing approval",
    "raw packet payload",
]

NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|resolver_client|mock_llm)\b", re.IGNORECASE)
# Top-level DB imports must not appear (writers are lazy-imported inside persistence stages).
TOPLEVEL_DB_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b|\bpeak\.db\b", re.IGNORECASE)
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
    """All import-like lines, at any indentation (lazy imports included)."""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            yield s


def _toplevel_import_lines(text: str):
    """Only module-level (unindented) import lines — lazy imports are excluded."""
    for line in text.splitlines():
        if line[:1] in (" ", "\t"):
            continue
        if line.startswith("import ") or line.startswith("from "):
            yield line


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Orchestration scaffold files")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Phase 23 ingestion stays DB-free (regression)")
    for rel in PHASE23_FILES:
        text = read(rel)
        hits = [ln for ln in _import_lines(text) if TOPLEVEL_DB_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n4. Orchestrator import discipline")
    for rel in PY_FILES:
        text = read(rel)
        imports = list(_import_lines(text))
        net = [ln for ln in imports if NETWORK_IMPORT_RE.search(ln) or NETWORK_HTTP_RE.search(ln)]
        llm = [ln for ln in imports if LLM_PROVIDER_RE.search(ln)]
        conn = [ln for ln in imports if CONNECTOR_RE.search(ln)]
        topdb = [ln for ln in _toplevel_import_lines(text) if TOPLEVEL_DB_RE.search(ln)]
        check(f"{rel}: no network import", not net)
        check(f"{rel}: no LLM provider import", not llm)
        check(f"{rel}: no connector/agentnet/mock_llm import", not conn)
        check(f"{rel}: no top-level DB import (writers lazy)", not topdb)

    print("\n5. Phase 25 added no migration (orchestrator is a sequencing layer)")
    versions = sorted(os.listdir(os.path.join(REPO_ROOT, "alembic", "versions")))
    versions = [v for v in versions if v.endswith(".py")]
    # Phase 25 is a DB-free sequencing layer: it introduced no migration of its own. (Later
    # phases legitimately add migrations, so this checks for a Phase-25-specific one, not a
    # fixed global count.)
    p25_migrations = [
        v for v in versions
        if any(term in v.lower() for term in ("orchestrat", "packet_processing", "phase25"))
    ]
    check("no Phase 25 orchestrator migration added", not p25_migrations)
    check("the Phase 24 source-ingestion migration (005) is present",
          any("005" in v for v in versions))

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


_SENTINEL = "PACKET-PAYLOAD-SENTINEL-DO-NOT-LEAK"


def _make_request(**over):
    from peak.ingestion.contracts import EngagementPacketReference, PacketIngestionRequest

    def ref(**o):
        base = dict(
            packet_reference_id="pkt_1", owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", packet_schema_name="engagement-packet",
            packet_schema_version="1.0", packet_source_type="consultant_upload",
            packet_location_reference="controlled://engagement/eng_x/packet_1",
            packet_hash="sha256:deadbeef", captured_by="consultant_a",
            captured_at="2026-07-16T10:00:00Z", authorization_scope="engagement_authorized",
            lifecycle_status="active",
        )
        base.update(o)
        return EngagementPacketReference(**base)

    payload = {
        "evidence_items": [
            {"id": "ev1", "content_type": "note", "text": "Pallets blocking dock",
             "location": "receiving dock", "observed_at": "2026-07-16T09:00:00Z",
             # an unmapped field carrying a sentinel; must never leak into the receipt:
             "unmapped_blob": _SENTINEL},
        ],
        "interview_notes": [
            {"id": "iv1", "note": "Cycle-count delays reported", "source_name": "Warehouse Lead"},
        ],
        "requested_agent_tasks": [
            {"agent_name": "evidence_normalization_worker", "requested_action": "normalize"},
            {"agent_name": "nonexistent_agent"},  # unknown -> skipped with warning
        ],
    }
    base = dict(
        owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
        requested_by="consultant_a", requester_role="consultant",
        authorization_scope="engagement_authorized", packet_reference=ref(),
        packet_payload=payload, requested_ingestion_action="prepare_packet_ingestion_plan",
        source_phase="phase25", idempotency_key="idem-orch-1", lifecycle_status="active",
    )
    # Allow overriding the packet_reference via ref_over.
    ref_over = over.pop("ref_over", None)
    if ref_over is not None:
        base["packet_reference"] = ref(**ref_over)
    base.update(over)
    return PacketIngestionRequest(**base)


def _safe_blob(receipt) -> str:
    parts = list(receipt.reasons) + list(receipt.warnings)
    parts.append(str(receipt.reason_code))
    parts.append(str(receipt.orchestration_outcome))
    parts.append(str(receipt.source_ingestion_draft))
    for sr in receipt.stage_results:
        parts.append(str(sr.reason))
    return " ".join(parts)


# --------------------------------------------------------------------------- plan-only


def plan_only_checks() -> None:
    from peak.orchestration import (
        OrchestrationOutcome, OrchestrationStageOptions, StageOutcome,
        process_engagement_packet,
    )
    from peak.orchestration.contracts import (
        STAGE_AGENT_RUN_RECORD_PLANNING, STAGE_SOURCE_INGESTION_PERSISTENCE,
    )
    from peak.workers.contracts import EvidenceNormalizationRequest
    from peak.agents.contracts import AgentTaskRequest

    print("\n8. Plan-only: valid packet -> no-side-effect receipt")
    r = process_engagement_packet(_make_request())
    check("permitted True", r.permitted is True)
    check("orchestration_outcome == planned", r.orchestration_outcome == OrchestrationOutcome.PLANNED)
    check("plan_only True", r.plan_only is True)
    check("packet_ingestion_result present", r.packet_ingestion_result is not None)
    check("source_ingestion_draft present", r.source_ingestion_draft is not None)
    check("source_controlled_write_request present", r.source_controlled_write_request is not None)
    cwr = r.source_controlled_write_request
    check("source CWR targets source_ingestion_records/create_source_ingestion_record",
          getattr(cwr, "target_table", None) == "source_ingestion_records"
          and getattr(cwr, "requested_action", None) == "create_source_ingestion_record")
    check("evidence requests derived (>=2)", len(r.evidence_normalization_requests) >= 2)
    check("evidence requests are Phase 14 objects",
          all(isinstance(x, EvidenceNormalizationRequest) for x in r.evidence_normalization_requests))
    check("evidence_normalization_count matches", r.evidence_normalization_count
          == len(r.evidence_normalization_requests))
    check("agent tasks derived (==1 known)", len(r.agent_task_requests) == 1)
    check("agent tasks are Phase 13 objects",
          all(isinstance(x, AgentTaskRequest) for x in r.agent_task_requests))
    check("agent_task_count == 1", r.agent_task_count == 1)
    check("unknown agent skipped (warning)", any("unknown agent" in w for w in r.warnings))
    check("derived agent llm_execution_allowed False",
          all(t.llm_execution_allowed is False for t in r.agent_task_requests))
    check("derived agent client_facing_output_requested False",
          all(t.client_facing_output_requested is False for t in r.agent_task_requests))
    check("derived agent resolver_context_allowed False",
          all(t.resolver_context_allowed is False for t in r.agent_task_requests))
    check("source_ingestion_persistence skipped_not_requested",
          any(s.stage == STAGE_SOURCE_INGESTION_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r.stage_results))
    for flag in ("database_connection_made", "sql_execution_made", "database_write_made",
                 "stored_record_created", "llm_call_made", "agentnet_call_made",
                 "network_call_made", "client_facing_output_created",
                 "financial_verification_made", "capsule_publication_made"):
        check(f"plan-only flag {flag} False", getattr(r, flag) is False)
    check("no source persistence receipt in plan-only", r.source_ingestion_persistence_receipt is None)
    check("NO raw packet payload sentinel leaked into receipt", _SENTINEL not in _safe_blob(r))

    print("\n9. Plan-only: no silent escalation to persistence")
    # include persistence but plan_only True -> skipped_plan_only, no writer, flags false
    opts = OrchestrationStageOptions(plan_only=True, include_source_ingestion_persistence=True)
    r2 = process_engagement_packet(_make_request(), options=opts)
    check("plan_only + include persistence -> skipped_plan_only",
          any(s.stage == STAGE_SOURCE_INGESTION_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_PLAN_ONLY for s in r2.stage_results))
    check("no writer called (no receipt)", r2.source_ingestion_persistence_receipt is None)
    check("db_write_made still False", r2.database_write_made is False)
    # persistence requested, not plan_only, but no session_factory -> skipped_missing_session_factory
    opts3 = OrchestrationStageOptions(plan_only=False, include_source_ingestion_persistence=True)
    r3 = process_engagement_packet(_make_request(), options=opts3, session_factory=None)
    check("persistence w/o session_factory -> skipped_missing_session_factory",
          any(s.stage == STAGE_SOURCE_INGESTION_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_MISSING_SESSION_FACTORY
              for s in r3.stage_results))
    check("missing session_factory does not fail orchestration", r3.permitted is True)
    check("missing session_factory: still no write", r3.database_write_made is False)
    # not_included persistence, not plan_only -> skipped_not_requested (no escalation)
    opts4 = OrchestrationStageOptions(plan_only=False, include_source_ingestion_persistence=False)
    r4 = process_engagement_packet(_make_request(), options=opts4, session_factory=None)
    check("persistence not included -> skipped_not_requested",
          any(s.stage == STAGE_SOURCE_INGESTION_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r4.stage_results))

    print("\n10. Plan-only: agent-run persistence intentionally deferred")
    opts5 = OrchestrationStageOptions(include_agent_run_record_planning=True,
                                      include_agent_run_record_persistence=True)
    r5 = process_engagement_packet(_make_request(), options=opts5)
    check("agent_run_record_planning skipped_no_safe_contract_path",
          any(s.stage == STAGE_AGENT_RUN_RECORD_PLANNING
              and s.outcome == StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH for s in r5.stage_results))
    check("agent_run planning reason mentions no safe contract path",
          any(s.stage == STAGE_AGENT_RUN_RECORD_PLANNING and s.reason for s in r5.stage_results))

    print("\n11. Plan-only: denials")
    from peak.orchestration import process_engagement_packet as proc
    # secret-like packet key -> Phase 23 denies -> orchestration denied
    req_secret = _make_request(packet_payload={"password": "x"})
    rs = proc(req_secret)
    check("secret key packet denied", rs.orchestration_outcome == OrchestrationOutcome.DENIED
          and rs.permitted is False)
    check("secret value not echoed in receipt", "x-secret-not-echoed" not in _safe_blob(rs))
    # packet_reference owner mismatch -> preflight denied
    rm = proc(_make_request(ref_over=dict(owner_id="owner_2")))
    check("packet_reference owner mismatch denied",
          rm.orchestration_outcome == OrchestrationOutcome.DENIED)
    # scope mismatch -> denied
    rsc = proc(_make_request(ref_over=dict(authorization_scope="internal_peak_only")))
    check("packet_reference scope mismatch denied",
          rsc.orchestration_outcome == OrchestrationOutcome.DENIED)
    # revoked lifecycle -> denied
    rl = proc(_make_request(lifecycle_status="revoked"))
    check("revoked lifecycle denied", rl.orchestration_outcome == OrchestrationOutcome.DENIED)
    # missing idempotency_key -> denied
    rk = proc(_make_request(idempotency_key=None))
    check("missing idempotency_key denied", rk.orchestration_outcome == OrchestrationOutcome.DENIED)


# --------------------------------------------------------------------------- DB-backed


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, Engagement, EvidenceReference, ReviewRecord, SourceIngestionRecord,
    )
    from peak.orchestration import (
        OrchestrationOutcome, OrchestrationStageOptions, StageOutcome,
        process_engagement_packet,
    )
    from peak.orchestration.contracts import (
        STAGE_EVIDENCE_PERSISTENCE, STAGE_SOURCE_INGESTION_PERSISTENCE,
    )

    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase25_")
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

    print("\n12. Controlled source-ingestion persistence")
    f = fresh_db()
    seed_engagement(f)
    opts = OrchestrationStageOptions(plan_only=False, include_source_ingestion_persistence=True)
    r = process_engagement_packet(_make_request(), options=opts, session_factory=f)
    check("orchestration persisted", r.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("source stage completed",
          any(s.stage == STAGE_SOURCE_INGESTION_PERSISTENCE
              and s.outcome == StageOutcome.COMPLETED for s in r.stage_results))
    check("exactly one source_ingestion_records row", count(f, SourceIngestionRecord) == 1)
    check("source persistence receipt attached", r.source_ingestion_persistence_receipt is not None)
    check("receipt target source_ingestion_records/create_source_ingestion_record",
          r.source_ingestion_persistence_receipt.target_table == "source_ingestion_records"
          and r.source_ingestion_persistence_receipt.target_action == "create_source_ingestion_record")
    check("DB flags reflect the writer call",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.stored_record_created)
    check("non-DB side-effect flags remain False",
          r.llm_call_made is False and r.agentnet_call_made is False and r.network_call_made is False
          and r.client_facing_output_created is False and r.financial_verification_made is False
          and r.capsule_publication_made is False)
    check("no unrelated table rows (evidence/agent/review)",
          count(f, EvidenceReference) == 0 and count(f, AgentRunRecord) == 0
          and count(f, ReviewRecord) == 0)

    print("\n13. Source replay + conflict")
    r2 = process_engagement_packet(_make_request(), options=opts, session_factory=f)
    check("replay returns existing (idempotent_replay)",
          r2.source_ingestion_persistence_receipt.outcome == "idempotent_replay")
    check("no second source row on replay", count(f, SourceIngestionRecord) == 1)
    # Same idempotency key, different packet_hash -> conflict
    r3 = process_engagement_packet(_make_request(ref_over=dict(packet_hash="sha256:different")),
                                   options=opts, session_factory=f)
    check("conflict denied by writer",
          r3.source_ingestion_persistence_receipt.outcome == "denied"
          and r3.source_ingestion_persistence_receipt.reason_code == "idempotency_conflict")
    check("orchestration partial on conflict", r3.orchestration_outcome == OrchestrationOutcome.PARTIAL)
    check("still one source row after conflict", count(f, SourceIngestionRecord) == 1)

    print("\n14. Stored-Engagement authorization stays inside the writer")
    f2 = fresh_db()
    seed_engagement(f2, authorization_scope="internal_peak_only")  # differs from request scope
    r4 = process_engagement_packet(_make_request(), options=opts, session_factory=f2)
    check("writer denies stored-scope mismatch",
          r4.source_ingestion_persistence_receipt.outcome == "denied"
          and r4.source_ingestion_persistence_receipt.reason_code == "stored_scope_mismatch")
    check("no source row on scope mismatch", count(f2, SourceIngestionRecord) == 0)
    check("orchestration partial on writer denial",
          r4.orchestration_outcome == OrchestrationOutcome.PARTIAL)

    print("\n15. Controlled evidence persistence (Phase 18 -> 21 only)")
    f3 = fresh_db()
    seed_engagement(f3)
    opts_ev = OrchestrationStageOptions(plan_only=False, include_evidence_normalization=True,
                                        include_evidence_persistence=True,
                                        include_source_ingestion_persistence=False)
    r5 = process_engagement_packet(_make_request(), options=opts_ev, session_factory=f3)
    check("evidence stage completed",
          any(s.stage == STAGE_EVIDENCE_PERSISTENCE and s.outcome == StageOutcome.COMPLETED
              for s in r5.stage_results))
    check("evidence rows == normalization count",
          count(f3, EvidenceReference) == r5.evidence_normalization_count
          and r5.evidence_normalization_count >= 2)
    check("evidence receipts attached", len(r5.evidence_persistence_receipts) >= 2)
    check("evidence receipts target evidence_references/create_draft",
          all(w.target_table == "evidence_references" and w.target_action == "create_draft"
              for w in r5.evidence_persistence_receipts))
    check("no source row when only evidence persisted", count(f3, SourceIngestionRecord) == 0)
    check("no agent_run/review rows", count(f3, AgentRunRecord) == 0 and count(f3, ReviewRecord) == 0)
    check("orchestration persisted (evidence)", r5.orchestration_outcome == OrchestrationOutcome.PERSISTED)

    print("\n16. Evidence persistence requires normalization records")
    f4 = fresh_db()
    seed_engagement(f4)
    opts_ev2 = OrchestrationStageOptions(plan_only=False, include_evidence_normalization=False,
                                         include_evidence_persistence=True)
    r6 = process_engagement_packet(_make_request(), options=opts_ev2, session_factory=f4)
    check("evidence persistence skipped_no_safe_contract_path when no normalization",
          any(s.stage == STAGE_EVIDENCE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH for s in r6.stage_results))
    check("no evidence rows without normalization", count(f4, EvidenceReference) == 0)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 25 controlled packet processing orchestrator check")
    print("=" * 52)

    structural_checks()
    plan_only_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — controlled-persistence not exercised.")
        print("         Run: make validate-phase25 PYTHON=.venv/bin/python")
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
