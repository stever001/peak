#!/usr/bin/env python3
"""Phase 23 engagement-packet-ingestion-boundary check.

Stdlib-only. Verifies the Engagement Packet Ingestion Boundary: the files exist and
import/compile, a valid in-memory packet prepares a **no-side-effect** ingestion plan
(review-gated `SourceIngestionDraft`, derived Phase 14 evidence requests, derived Phase 13
agent tasks for known agents only, all direct write/call flags false), governance rejects the
disallowed cases (including identity/scope mismatch and secret-key payloads), the package
makes no network/database/SQLAlchemy/peak.db/LLM imports, the docs carry the required
boundary language, and the repo stays source-only.

Phase 23 is an ingestion boundary, not a direct importer: no direct DB write, no DB
connection, no SQL execution, no stored packet, no live LLM/AgentNet/MCP/resolver/network
call, no client-facing approval, no financial verification, no capsule publication.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

REQUIRED_FILES = [
    "peak/ingestion/__init__.py",
    "peak/ingestion/contracts.py",
    "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
    "docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md",
    "docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md",
]

PY_FILES = [
    "peak/ingestion/__init__.py",
    "peak/ingestion/contracts.py",
    "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
]

DOCS = [
    "docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md",
    "docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md",
]

REQUIRED_PHRASES = [
    "ingestion boundary",
    "no direct DB writes from packet ingestion",
    "packet contents are not stored",
    "ingestion plans are not writes",
    "production-shaped",
    "review-gated",
    "future source ingestion writer",
    "idempotency_key",
    "owner/client/engagement matching is necessary but not sufficient",
    "credentials/secrets",
    "no live LLM",
    "no AgentNet",
    "no database call",
    "no client-facing approval",
    "no financial verification",
    "no capsule publication",
]

NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b|import\s+\.\.db\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
# A committed *credential value* looks like `api_key = "..."` / `secret_key: '...'`. This is
# deliberately assignment-scoped so the ingestion secret-key *guard list* (which names terms
# like "api_key" to reject them in packet payloads) is not a false positive.
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE,
)

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


def _synthetic():
    """Build in-memory synthetic packet ingestion request builders (no stored data)."""
    from peak.ingestion.contracts import EngagementPacketReference, PacketIngestionRequest

    def ref(**over):
        base = dict(
            packet_reference_id="pkt_1", owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", packet_schema_name="engagement-packet",
            packet_schema_version="1.0", packet_source_type="consultant_upload",
            packet_location_reference="controlled://engagement/eng_x/packet_1",
            packet_hash="sha256:deadbeef", captured_by="consultant_a",
            captured_at="2026-07-16T10:00:00Z", authorization_scope="engagement_authorized",
            lifecycle_status="active",
        )
        base.update(over)
        return EngagementPacketReference(**base)

    def payload(**over):
        base = {
            "evidence_items": [
                {"id": "ev1", "content_type": "note", "text": "Pallets blocking dock",
                 "location": "receiving dock", "observed_at": "2026-07-16T09:00:00Z"},
                "not-an-object",  # should be skipped with a warning
            ],
            "interview_notes": [
                {"id": "iv1", "note": "Stakeholder reports cycle-count delays",
                 "source_name": "Warehouse Lead"},
            ],
            "walkaround_observations": [
                {"id": "wa1", "observation_context": "Aisle congestion near staging"},
            ],
            "requested_agent_tasks": [
                {"agent_name": "evidence_normalization_worker", "requested_action": "normalize"},
                {"agent_name": "nonexistent_agent"},  # unknown -> skipped with warning
                "not-an-object",  # skipped with warning
            ],
        }
        base.update(over)
        return base

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized", packet_reference=ref(),
            packet_payload=payload(),
            requested_ingestion_action="prepare_packet_ingestion_plan",
            source_phase="phase2_packet", idempotency_key="idem-pkt-1",
            lifecycle_status="active",
        )
        base.update(over)
        return PacketIngestionRequest(**base)

    return ref, payload, req


def main() -> int:
    print("Peak Phase 23 engagement-packet-ingestion-boundary check")
    print("=" * 52)

    print("\n1. Ingestion scaffold files")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Package import")
    ingestion = None
    try:
        import peak.ingestion as ingestion  # noqa: F401
        check("peak.ingestion imports", True)
    except Exception as exc:  # noqa: BLE001
        check(f"peak.ingestion imports ({exc})", False)

    ref = payload = req = None

    print("\n4. Valid packet -> no-side-effect ingestion plan")
    if ingestion is not None:
        from peak.ingestion.packet_mapper import prepare_packet_ingestion
        from peak.workers.contracts import EvidenceNormalizationRequest
        from peak.agents.contracts import AgentTaskRequest

        ref, payload, req = _synthetic()
        result = prepare_packet_ingestion(req())
        plan = result.ingestion_plan
        draft = plan.source_ingestion_draft if plan is not None else None
        ev = plan.evidence_plan if plan is not None else None
        at = plan.agent_task_plan if plan is not None else None
        checks = {
            "permitted == True": result.permitted is True,
            "plan present": plan is not None,
            "draft.source_ingestion_record_id is None": draft is not None
            and draft.source_ingestion_record_id is None,
            "draft.created_at is None": draft is not None and draft.created_at is None,
            "draft.output_status == draft": draft is not None and draft.output_status == "draft",
            "draft.review_status == needs_review": draft is not None
            and draft.review_status == "needs_review",
            "draft.authoritative == False": draft is not None and draft.authoritative is False,
            "draft.client_facing_approved == False": draft is not None
            and draft.client_facing_approved is False,
            "draft.capsule_candidate_ready == False": draft is not None
            and draft.capsule_candidate_ready is False,
            "evidence requests derived (>=3)": ev is not None and ev.evidence_request_count >= 3,
            "evidence requests are Phase 14 objects": ev is not None
            and all(isinstance(r, EvidenceNormalizationRequest) for r in ev.evidence_requests),
            "non-object evidence item skipped (warning)": ev is not None
            and any("not an object" in w for w in ev.warnings),
            "agent tasks derived (==1 known)": at is not None
            and at.agent_task_request_count == 1,
            "agent task is Phase 13 object": at is not None
            and all(isinstance(t, AgentTaskRequest) for t in at.agent_task_requests),
            "unknown agent skipped (warning)": at is not None
            and any("unknown agent" in w for w in at.warnings),
            "derived agent llm_execution_allowed False": at is not None
            and all(t.llm_execution_allowed is False for t in at.agent_task_requests),
            "derived agent client_facing_output_requested False": at is not None
            and all(t.client_facing_output_requested is False for t in at.agent_task_requests),
            "derived agent review_status needs_review": at is not None
            and all(t.review_status == "needs_review" for t in at.agent_task_requests),
            "controlled_write_requests present (plan only)": plan is not None
            and len(plan.controlled_write_requests) == 1,
            "direct_database_write_made == False": result.direct_database_write_made is False,
            "database_connection_made == False": result.database_connection_made is False,
            "sql_execution_made == False": result.sql_execution_made is False,
            "stored_record_created == False": result.stored_record_created is False,
            "llm_call_made == False": result.llm_call_made is False,
            "agentnet_call_made == False": result.agentnet_call_made is False,
            "network_call_made == False": result.network_call_made is False,
            "capsule_publication_made == False": result.capsule_publication_made is False,
            "client_facing_output_created == False": result.client_facing_output_created is False,
            "plan carries 'ingestion plans are not writes' warning": plan is not None
            and any("not writes" in w for w in plan.warnings),
        }
        for label, ok in checks.items():
            check(label, ok)

        # The derived source_ingestion write request targets the right table/action.
        if plan is not None and plan.controlled_write_requests:
            cwr = plan.controlled_write_requests[0]
            check("CWR target_table == source_ingestion_records",
                  cwr.target_table == "source_ingestion_records")
            check("CWR requested_action == create_source_ingestion_record",
                  cwr.requested_action == "create_source_ingestion_record")
            check("CWR record_draft is the SourceIngestionDraft",
                  cwr.record_draft is draft)

    print("\n5. Governance rejections")
    if ingestion is not None:
        from peak.ingestion.governance import evaluate_packet_ingestion_request as gov

        cases = {
            "missing owner_id": req(owner_id=None),
            "missing client_id": req(client_id=None),
            "missing engagement_id": req(engagement_id=None),
            "missing requested_by": req(requested_by=None),
            "missing requester_role": req(requester_role=None),
            "missing authorization_scope": req(authorization_scope=None),
            "missing packet_reference": req(packet_reference=None),
            "missing packet_payload": req(packet_payload=None),
            "missing idempotency_key": req(idempotency_key=None),
            "wrong ingestion action": req(requested_ingestion_action="import_now"),
            "packet_ref owner mismatch": req(packet_reference=ref(owner_id="owner_2")),
            "packet_ref client mismatch": req(packet_reference=ref(client_id="client_b")),
            "packet_ref engagement mismatch": req(packet_reference=ref(engagement_id="eng_y")),
            "packet_ref scope mismatch": req(
                packet_reference=ref(authorization_scope="internal_peak_only")
            ),
            "request lifecycle revoked": req(lifecycle_status="revoked"),
            "packet_ref lifecycle archived": req(packet_reference=ref(lifecycle_status="archived")),
            "payload not a dict": req(packet_payload=["not", "a", "dict"]),
            "payload with password key": req(packet_payload={"password": "x"}),
            "payload with nested api_key": req(
                packet_payload={"evidence_items": [{"api_key": "x"}]}
            ),
            "payload with connection_string": req(packet_payload={"connection_string": "y"}),
        }
        for label, request in cases.items():
            check(f"rejected: {label}", not gov(request).permitted)

    print("\n6. Secret values are not echoed in denial reasons")
    if ingestion is not None:
        from peak.ingestion.governance import evaluate_packet_ingestion_request as gov

        secret_value = "TOP-SECRET-VALUE-12345"
        decision = gov(req(packet_payload={"api_key": secret_value}))
        blob = " ".join(decision.reasons + decision.warnings)
        check("denied on secret key", not decision.permitted)
        check("secret value not echoed in reasons", secret_value not in blob)

    print("\n7. No network / database / SQLAlchemy / peak.db / LLM imports in peak/ingestion/")
    net_hits, db_hits, llm_hits = [], [], []
    for rel in PY_FILES:
        text = read(rel)
        for line in _import_lines(text):
            if NETWORK_IMPORT_RE.search(line) or NETWORK_HTTP_RE.search(line):
                net_hits.append(f"{rel}: {line}")
            if DB_IMPORT_RE.search(line) or PEAK_DB_RE.search(line):
                db_hits.append(f"{rel}: {line}")
        if LLM_PROVIDER_RE.search(text) or CREDENTIAL_RE.search(text):
            llm_hits.append(rel)
    check("no network imports", not net_hits)
    check("no database/ORM/peak.db imports", not db_hits)
    check("no LLM provider/credential literals", not llm_hits)

    print("\n8. Doc language")
    blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"phrase present: '{phrase}'", phrase.lower() in blob)

    print("\n9. Source-only discipline")
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
