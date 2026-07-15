#!/usr/bin/env python3
"""Phase 18 evidence-persistence-mapping check.

Stdlib-only. Verifies the Evidence Persistence Mapping scaffold: the files exist and
import/compile, a valid in-memory Phase 14 normalized evidence result + stored parent
subject snapshot maps to a **no-side-effect** controlled write plan targeting
``evidence_references`` / ``create_draft`` (production-shaped but review-gated draft, no DB
connection, no SQL, no stored record), governance rejects the disallowed cases — including a
``request.authorization_scope`` that does not match the subject's
``stored_authorization_scope`` — the package makes no network/database/SQLAlchemy/peak.db/LLM
imports, the docs carry the required mapping language, and the repo stays source-only.

Phase 18 is **DB-aware but not DB-writing**: no live database connection, no SQL execution,
no stored records, no live LLM/AgentNet/MCP/resolver/network call, and no client-facing
output.

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

REQUIRED_FILES = [
    "peak/evidence/__init__.py",
    "peak/evidence/persistence_contracts.py",
    "peak/evidence/persistence_governance.py",
    "peak/evidence/evidence_record_mapper.py",
    "docs/EVIDENCE_PERSISTENCE_MAPPING.md",
    "docs/EVIDENCE_WRITE_PLAN_POLICY.md",
]

PY_FILES = [
    "peak/evidence/__init__.py",
    "peak/evidence/persistence_contracts.py",
    "peak/evidence/persistence_governance.py",
    "peak/evidence/evidence_record_mapper.py",
]

DOCS = ["docs/EVIDENCE_PERSISTENCE_MAPPING.md", "docs/EVIDENCE_WRITE_PLAN_POLICY.md"]

REQUIRED_PHRASES = [
    "DB-aware but not DB-writing",
    "write plans are not writes",
    "production-shaped",
    "review-gated",
    "future controlled DB writer",
    "idempotency_key",
    "stored_authorization_scope",
    "owner/client/engagement matching is necessary but not sufficient",
    "evidence workers still do not write directly to the DB",
    "no live database connection",
    "no SQL execution",
    "no stored records",
    "no client-facing approval",
    "no financial verification",
    "no capsule publication",
]

# Network imports must not appear in the evidence package.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
# Database / ORM / peak.db imports must not appear.
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b")
# Live LLM provider libs / credentials must not appear anywhere in the package.
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b", re.IGNORECASE
)

DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"


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


def _synthetic():
    """Build in-memory synthetic evidence-persistence-request builders (no stored data)."""
    from peak.workers.contracts import EvidenceNormalizationResult, NormalizedEvidenceRecord
    from peak.evidence.persistence_contracts import (
        EvidencePersistenceRequest,
        EvidencePersistenceSubjectSnapshot,
    )

    def record(**over):
        base = dict(
            evidence_record_id=None, owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", source_reference_id="src_1", evidence_type="visual_observation",
            normalized_title="[draft] visual_observation — receiving_dock / receiving",
            normalized_summary="Worker-normalized, review-gated evidence.",
            observed_condition="Pallets blocking receiving dock", operational_area="receiving_dock",
            inventory_process_area="receiving", source_type="site_walk",
            source_location="receiving dock", confidence_level="medium",
            output_status="draft", review_status="needs_review", lifecycle_status="active",
            authoritative=False, client_facing_approved=False, capsule_candidate_ready=False,
            warnings=[], reasons=[],
        )
        base.update(over)
        return NormalizedEvidenceRecord(**base)

    def result(**over):
        base = dict(
            permitted=True, status="normalized_draft", normalized_record=None,
            output_status="draft", review_status="needs_review", lifecycle_status="active",
            authoritative=False, client_facing_approved=False, database_write_made=False,
            llm_call_made=False, agentnet_call_made=False, network_call_made=False,
            capsule_publication_made=False, reasons=[], warnings=[],
        )
        base.update(over)
        return EvidenceNormalizationResult(**base)

    def snapshot(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement_record",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
            stored_output_status="active", stored_review_status="approved_internal",
            stored_lifecycle_status="active", source_reference_id="src_1",
        )
        base.update(over)
        return EvidencePersistenceSubjectSnapshot(**base)

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            normalization_result=result(), normalized_record=record(),
            subject_snapshot=snapshot(),
            requested_persistence_action="prepare_evidence_reference_write_plan",
            source_phase="phase14", idempotency_key="idem-evid-1", lifecycle_status="active",
        )
        base.update(over)
        return EvidencePersistenceRequest(**base)

    return record, result, snapshot, req


def main() -> int:
    print("Peak Phase 18 evidence-persistence-mapping check")
    print("=" * 48)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Evidence-persistence scaffold files")
    for rel in REQUIRED_FILES:
        if os.path.isfile(os.path.join(REPO_ROOT, rel)):
            print(f"  [{PASS}] {rel}")
        else:
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")

    # 2. Python files compile.
    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            print(f"  [{PASS}] {rel} compiles")
        except py_compile.PyCompileError:
            failures.append(f"{rel}: compile error")
            print(f"  [{FAIL}] {rel}: compile error")

    # 3. Package import.
    print("\n3. Package import")
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    evidence = None
    try:
        import peak.evidence as evidence  # noqa: F401
        print(f"  [{PASS}] peak.evidence imports")
    except Exception as exc:
        failures.append(f"peak.evidence import failed: {exc}")
        print(f"  [{FAIL}] peak.evidence import failed: {exc}")

    record = result = snapshot = req = None

    # 4. Valid mapping → no-side-effect controlled write plan.
    print("\n4. Evidence mapping is DB-aware but not DB-writing")
    if evidence is not None:
        from peak.evidence.evidence_record_mapper import prepare_evidence_persistence

        record, result, snapshot, req = _synthetic()
        # Link the record into the result the way the worker would.
        base_req = req()
        base_req.normalization_result = result(normalized_record=base_req.normalized_record)
        mapping = prepare_evidence_persistence(base_req)
        draft = mapping.evidence_persistence_draft
        cwr = mapping.controlled_write_request
        cwres = mapping.controlled_write_result
        plan = getattr(cwres, "write_plan", None)
        checks = {
            "permitted == True": mapping.permitted is True,
            "draft present": draft is not None,
            "draft.evidence_record_id is None": draft is not None and draft.evidence_record_id is None,
            "draft.created_at is None": draft is not None and draft.created_at is None,
            "draft.output_status == draft": draft is not None and draft.output_status == "draft",
            "draft.review_status == needs_review": draft is not None
            and draft.review_status == "needs_review",
            "draft.authoritative == False": draft is not None and draft.authoritative is False,
            "draft.client_facing_approved == False": draft is not None
            and draft.client_facing_approved is False,
            "draft.capsule_candidate_ready == False": draft is not None
            and draft.capsule_candidate_ready is False,
            "cwr.target_table == evidence_references": cwr is not None
            and cwr.target_table == "evidence_references",
            "cwr.requested_action == create_draft": cwr is not None
            and cwr.requested_action == "create_draft",
            "plan.requires_controlled_db_writer == True": plan is not None
            and plan.requires_controlled_db_writer is True,
            "database_write_made == False": mapping.database_write_made is False,
            "database_connection_made == False": mapping.database_connection_made is False,
            "sql_execution_made == False": mapping.sql_execution_made is False,
            "stored_record_created == False": mapping.stored_record_created is False,
            "llm_call_made == False": mapping.llm_call_made is False,
            "agentnet_call_made == False": mapping.agentnet_call_made is False,
            "network_call_made == False": mapping.network_call_made is False,
            "capsule_publication_made == False": mapping.capsule_publication_made is False,
            "client_facing_output_created == False": mapping.client_facing_output_created is False,
        }
        for label, ok in checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"result: {label} failed")
                print(f"  [{FAIL}] result: {label} failed")

    # 5. Governance rejections.
    print("\n5. Governance rejections")
    if evidence is not None:
        from peak.evidence.persistence_governance import (
            evaluate_evidence_persistence_request as gov,
        )

        def rq(**over):
            r = req()
            for k, v in over.items():
                setattr(r, k, v)
            return r

        cases = {
            "missing owner_id": rq(owner_id=None),
            "missing client_id": rq(client_id=None),
            "missing engagement_id": rq(engagement_id=None),
            "missing requested_by": rq(requested_by=None),
            "missing requester_role": rq(requester_role=None),
            "missing authorization_scope": rq(authorization_scope=None),
            "missing normalization_result": rq(normalization_result=None),
            "missing normalized_record": rq(normalized_record=None),
            "missing subject_snapshot": rq(subject_snapshot=None),
            "missing idempotency_key": rq(idempotency_key=None),
            "wrong persistence action": rq(requested_persistence_action="write_now"),
            "subject owner mismatch": rq(subject_snapshot=snapshot(owner_id="owner_2")),
            "subject client mismatch": rq(subject_snapshot=snapshot(client_id="client_b")),
            "subject engagement mismatch": rq(subject_snapshot=snapshot(engagement_id="eng_y")),
            "record owner mismatch": rq(normalized_record=record(owner_id="owner_2")),
            "record client mismatch": rq(normalized_record=record(client_id="client_b")),
            "record engagement mismatch": rq(normalized_record=record(engagement_id="eng_y")),
            "stored scope mismatch": rq(
                subject_snapshot=snapshot(stored_authorization_scope="internal_peak_only")
            ),
            "missing stored scope": rq(subject_snapshot=snapshot(stored_authorization_scope=None)),
            "request lifecycle revoked": rq(lifecycle_status="revoked"),
            "subject lifecycle archived": rq(
                subject_snapshot=snapshot(stored_lifecycle_status="archived")
            ),
            "unpermitted normalization_result": rq(normalization_result=result(permitted=False)),
            "normalization db_write flag": rq(
                normalization_result=result(database_write_made=True)
            ),
            "normalization llm flag": rq(normalization_result=result(llm_call_made=True)),
            "normalization agentnet flag": rq(normalization_result=result(agentnet_call_made=True)),
            "normalization network flag": rq(normalization_result=result(network_call_made=True)),
            "normalization capsule flag": rq(
                normalization_result=result(capsule_publication_made=True)
            ),
            "record authoritative": rq(normalized_record=record(authoritative=True)),
            "record client_facing_approved": rq(
                normalized_record=record(client_facing_approved=True)
            ),
            "record capsule_candidate_ready": rq(
                normalized_record=record(capsule_candidate_ready=True)
            ),
            "record wrong output_status": rq(normalized_record=record(output_status="reviewed")),
            "record wrong review_status": rq(
                normalized_record=record(review_status="approved_internal")
            ),
        }
        for label, request in cases.items():
            if not gov(request).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 6. Denied request produces no plan (fully side-effect-free denial).
    print("\n6. Denial is side-effect-free")
    if evidence is not None:
        from peak.evidence.evidence_record_mapper import prepare_evidence_persistence

        denied_req = req()
        denied_req.subject_snapshot = snapshot(stored_authorization_scope="internal_peak_only")
        denied = prepare_evidence_persistence(denied_req)
        denial_checks = {
            "permitted == False": denied.permitted is False,
            "evidence_persistence_draft is None": denied.evidence_persistence_draft is None,
            "controlled_write_request is None": denied.controlled_write_request is None,
            "controlled_write_result is None": denied.controlled_write_result is None,
            "database_write_made == False": denied.database_write_made is False,
            "database_connection_made == False": denied.database_connection_made is False,
            "sql_execution_made == False": denied.sql_execution_made is False,
            "stored_record_created == False": denied.stored_record_created is False,
            "has a denial reason": bool(denied.reasons),
        }
        for label, ok in denial_checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"denial: {label} failed")
                print(f"  [{FAIL}] denial: {label} failed")

    # 7. No network / database / ORM / peak.db / LLM imports in the package.
    print("\n7. No network / database / SQLAlchemy / peak.db / LLM imports")
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
    for label, hits in (("network import", net_hits),
                        ("database/ORM/peak.db import", db_hits),
                        ("LLM provider/credential", llm_hits)):
        if hits:
            for h in hits:
                failures.append(f"{label}: {h}")
                print(f"  [{FAIL}] {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s")

    # 8. Doc language.
    print("\n8. Mapping doc language")
    doc_blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() in doc_blob:
            print(f"  [{PASS}] phrase present: '{phrase}'")
        else:
            failures.append(f"missing doc phrase: {phrase}")
            print(f"  [{FAIL}] missing doc phrase: '{phrase}'")

    # 9. Source-only discipline.
    print("\n9. Source-only discipline")
    if os.path.exists(os.path.join(REPO_ROOT, "examples")):
        failures.append("examples/ exists")
        print(f"  [{FAIL}] examples/ exists")
    else:
        print(f"  [{PASS}] no examples/ directory")
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
    for label, hits in (("data artifact", artifacts), ("database file", dbfiles)):
        if hits:
            for h in hits:
                failures.append(f"forbidden {label}: {h}")
                print(f"  [{FAIL}] forbidden {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s found (except allowed .env.example)")

    print("\n" + "=" * 48)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
