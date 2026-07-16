#!/usr/bin/env python3
"""Phase 24 controlled-DB source-ingestion-writer check.

Two layers:

* **Structural (always, stdlib-only):** the writer/receipt/migration files exist and compile;
  the Phase 23 ingestion package stays DB-free (no SQLAlchemy/Alembic/peak.db import); the
  writer imports no LLM/AgentNet/connector/network client or credential; the migration is
  additive schema-only (no INSERT/seed); the docs carry the required language; the repo stays
  source-only.

* **DB-backed (when SQLAlchemy is importable):** real behavior against a temporary local
  SQLite database built from the models — migration upgrade/downgrade/re-upgrade, successful
  create (packet metadata only), idempotent replay, conflicting replay, DB-backed authorization
  (stored-scope comparison), identity mismatches, action allowlist, posture/content rejections,
  side-effect discipline, and transaction/failure semantics. If SQLAlchemy is not installed,
  this layer is skipped with instructions (run with
  ``make validate-phase24 PYTHON=.venv/bin/python``) and the harness still exits 0.

Phase 24 performs no live LLM/AgentNet/MCP/resolver/connector/network call, no client-facing
approval, no financial verification, no capsule publication, and no packet payload storage; it
creates exactly one ``source_ingestion_records`` row and never updates or deletes.

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
    "peak/db/source_ingestion_writer.py",
    "peak/db/writer_contracts.py",
    "alembic/versions/005_source_ingestion_idempotency.py",
    "docs/SOURCE_INGESTION_CONTROLLED_WRITER.md",
    "docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md",
]

WRITER_FILES = ["peak/db/source_ingestion_writer.py", "peak/db/writer_contracts.py"]
# Phase 23 ingestion package must stay DB-free (regression guard).
PHASE23_FILES = [
    "peak/ingestion/contracts.py",
    "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
]
COMPILE_FILES = WRITER_FILES + ["alembic/versions/005_source_ingestion_idempotency.py"]

DOCS = [
    "docs/SOURCE_INGESTION_CONTROLLED_WRITER.md",
    "docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md",
]

REQUIRED_PHRASES = [
    "write-time",
    "stored authorization",
    "identity matching is necessary but not sufficient",
    "idempotency",
    "idempotent_replay",
    "review-gated",
    "output_status=draft",
    "review_status=needs_review",
    "write_outcome_uncertain",
    "packet metadata only",
    "no LLM",
    "no AgentNet",
    "no capsule publication",
    "no financial verification",
    "server-controlled",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b|import\s+\.\.db\b")
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|resolver_client|connector)\b", re.IGNORECASE)
# Committed credential value (assignment form), not a mere term reference.
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b\s*[:=]\s*['\"]",
    re.IGNORECASE,
)
INSERT_PATTERNS = ("insert into", "bulk_insert", "op.execute(", ".insert(")
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

    print("\n3. Phase 23 ingestion package stays DB-free")
    for rel in PHASE23_FILES:
        text = read(rel)
        hits = [ln for ln in _import_lines(text)
                if DB_IMPORT_RE.search(ln) or PEAK_DB_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n4. Writer imports no LLM/AgentNet/connector/network/credential")
    for rel in WRITER_FILES:
        text = read(rel)
        net = [ln for ln in _import_lines(text)
               if NETWORK_IMPORT_RE.search(ln) or NETWORK_HTTP_RE.search(ln)]
        llm = [ln for ln in _import_lines(text) if LLM_PROVIDER_RE.search(ln)]
        conn = [ln for ln in _import_lines(text) if CONNECTOR_RE.search(ln)]
        check(f"{rel}: no network import", not net)
        check(f"{rel}: no LLM provider import", not llm)
        check(f"{rel}: no connector/agentnet import", not conn)
        check(f"{rel}: no credential value literal", not CREDENTIAL_RE.search(text))

    print("\n5. Migration is additive schema-only (no INSERT/seed)")
    mig = read("alembic/versions/005_source_ingestion_idempotency.py")
    low = mig.lower()
    check("migration has no insert/seed pattern", not any(p in low for p in INSERT_PATTERNS))
    check("migration defines upgrade()", "def upgrade()" in mig)
    check("migration defines downgrade()", "def downgrade()" in mig)
    check("migration targets source_ingestion_records", "source_ingestion_records" in mig)
    check("migration adds unique idempotency index", "uq_source_ingestion_records_idem" in mig)
    check("migration down_revision is 004_review_idem",
          'down_revision = "004_review_idem"' in mig)

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


# --------------------------------------------------------------------------- DB-backed


def _make_builders():
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.ingestion.contracts import (
        EngagementPacketReference,
        PacketIngestionRequest,
        SourceIngestionDraft,
    )

    def subject(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
        )
        base.update(over)
        return ControlledWriteSubject(**base)

    def draft(**over):
        base = dict(
            source_ingestion_record_id=None, owner_id="owner_1", client_id="client_a",
            engagement_id="eng_x", packet_reference_id="pkt_1",
            packet_schema_name="engagement-packet", packet_schema_version="1.0",
            packet_source_type="consultant_upload",
            packet_location_reference="controlled://engagement/eng_x/packet_1",
            packet_hash="sha256:deadbeef", output_status="draft", review_status="needs_review",
            lifecycle_status="active", authoritative=False, client_facing_approved=False,
            capsule_candidate_ready=False, reasons=["packet validated"], warnings=[],
            created_at=None,
        )
        base.update(over)
        return SourceIngestionDraft(**base)

    def preq(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            packet_reference=EngagementPacketReference(
                packet_reference_id="pkt_1", owner_id="owner_1", client_id="client_a",
                engagement_id="eng_x", authorization_scope="engagement_authorized",
                lifecycle_status="active",
            ),
            packet_payload={}, requested_ingestion_action="prepare_packet_ingestion_plan",
            idempotency_key="idem-ing-1", lifecycle_status="active",
        )
        base.update(over)
        return PacketIngestionRequest(**base)

    def build(*, draft_over=None, subject_over=None, **cwr_over):
        d = draft(**(draft_over or {}))
        subj = subject(**(subject_over or {}))
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            target_table="source_ingestion_records",
            requested_action="create_source_ingestion_record",
            subject=subj, record_draft=d, source_phase="phase23", lifecycle_status="active",
            idempotency_key="idem-ing-1",
        )
        base.update(cwr_over)
        cwr = ControlledWriteRequest(**base)
        return cwr, d, preq()

    return subject, draft, preq, build


def _migration_reversibility() -> None:
    """Apply upgrade -> downgrade -> re-upgrade against a temp SQLite DB (no production DB)."""
    from sqlalchemy import create_engine, inspect
    from alembic.config import Config
    from alembic import command

    print("\n8. Migration apply / reversibility (temp SQLite)")
    tmp = tempfile.mkdtemp(prefix="peak_phase24_mig_")
    prev_url = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "mig.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        insp = inspect(create_engine(url))
        cols = {c["name"] for c in insp.get_columns("source_ingestion_records")}
        idx = {i["name"]: (i.get("unique"), i["column_names"])
               for i in insp.get_indexes("source_ingestion_records")}
        check("upgrade adds output_status/idempotency_key/payload_fingerprint",
              {"output_status", "idempotency_key", "payload_fingerprint"} <= cols)
        check("upgrade adds unique idempotency index over (owner,client,engagement,key)",
              idx.get("uq_source_ingestion_records_idem")
              == (1, ["owner_id", "client_id", "engagement_id", "idempotency_key"]))
        command.downgrade(cfg, "004_review_idem")
        cols2 = {c["name"] for c in inspect(create_engine(url)).get_columns("source_ingestion_records")}
        check("downgrade removes the added columns", "idempotency_key" not in cols2)
        command.upgrade(cfg, "head")
        check("re-upgrade succeeds", True)
    finally:
        if prev_url is None:
            os.environ.pop("PEAK_DATABASE_URL", None)
        else:
            os.environ["PEAK_DATABASE_URL"] = prev_url
        shutil.rmtree(tmp, ignore_errors=True)


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    import peak.db.source_ingestion_writer as writer_mod
    from peak.db.source_ingestion_writer import persist_source_ingestion_record
    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, EvidenceReference, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.db.writer_contracts import SourceIngestionWriteOutcome

    _migration_reversibility()

    subject, draft, preq, build = _make_builders()
    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase24_")
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

    # ---- Successful create ----
    print("\n9. Successful create (packet metadata only)")
    f = fresh_db()
    seed_engagement(f)
    cwr, d, p = build()
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("outcome == created", r.outcome == SourceIngestionWriteOutcome.CREATED)
    check("permitted True", r.permitted is True)
    check("exactly one row created", count(f, SourceIngestionRecord) == 1)
    check("server-generated id (ing_ prefix)",
          bool(r.stored_record_id) and r.stored_record_id.startswith("ing_"))
    check("receipt created_at present", bool(r.created_at))
    check("receipt review_status needs_review", r.review_status == "needs_review")
    check("receipt output_status draft", r.output_status == "draft")
    check("flags: connection/sql/write/commit/created all True",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.transaction_committed and r.stored_record_created)
    check("flags: existing_record_returned False", r.existing_record_returned is False)
    check("flags: outcome_uncertain False", r.outcome_uncertain is False)
    s = f()
    row = s.get(SourceIngestionRecord, r.stored_record_id)
    check("stored review_status == needs_review", row.review_status == "needs_review")
    check("stored output_status == draft", row.output_status == "draft")
    check("stored lifecycle_status == active", row.lifecycle_status == "active")
    check("stored source_reference_id == packet_reference_id", row.source_reference_id == "pkt_1")
    check("packet metadata stored (schema/source/hash)",
          row.details_json.get("packet_schema_name") == "engagement-packet"
          and row.details_json.get("packet_source_type") == "consultant_upload"
          and row.details_json.get("packet_hash") == "sha256:deadbeef")
    check("NO full packet payload stored",
          "packet_payload" not in row.details_json and "raw_packet_content" not in row.details_json
          and not hasattr(row, "packet_payload"))
    check("stored idempotency_key persisted", row.idempotency_key == "idem-ing-1")
    check("stored payload_fingerprint persisted", bool(row.payload_fingerprint))
    check("stored created_at server-stamped", row.created_at is not None)
    s.close()

    # ---- Side-effect discipline ----
    print("\n10. Side-effect discipline (no unrelated table mutation)")
    check("clients untouched", count(f, Client) == 0)
    check("evidence_references untouched", count(f, EvidenceReference) == 0)
    check("agent_run_records untouched", count(f, AgentRunRecord) == 0)
    check("review_records untouched", count(f, ReviewRecord) == 0)

    # ---- Idempotent replay ----
    print("\n11. Idempotent replay")
    f = fresh_db()
    seed_engagement(f)
    cwr1, _, p1 = build()
    first = persist_source_ingestion_record(cwr1, session_factory=f, persistence_request=p1)
    cwr2, _, p2 = build()
    second = persist_source_ingestion_record(cwr2, session_factory=f, persistence_request=p2)
    check("second outcome idempotent_replay",
          second.outcome == SourceIngestionWriteOutcome.IDEMPOTENT_REPLAY)
    check("no second row", count(f, SourceIngestionRecord) == 1)
    check("existing id returned", second.stored_record_id == first.stored_record_id)
    check("replay reports no new record",
          second.stored_record_created is False and second.database_write_made is False
          and second.existing_record_returned is True)

    # ---- Conflicting replay ----
    print("\n12. Conflicting replay")
    f = fresh_db()
    seed_engagement(f)
    cwrA, _, pA = build()
    created = persist_source_ingestion_record(cwrA, session_factory=f, persistence_request=pA)
    cwrB, dB, pB = build(draft_over=dict(packet_hash="sha256:different"))
    conflict = persist_source_ingestion_record(cwrB, session_factory=f, persistence_request=pB)
    check("conflict denied", conflict.outcome == SourceIngestionWriteOutcome.DENIED)
    check("conflict reason idempotency_conflict", conflict.reason_code == "idempotency_conflict")
    check("no new row on conflict", count(f, SourceIngestionRecord) == 1)
    s = f()
    row = s.get(SourceIngestionRecord, created.stored_record_id)
    check("existing row unchanged (packet_hash)",
          row.details_json.get("packet_hash") == "sha256:deadbeef")
    s.close()

    # ---- DB-backed authorization ----
    print("\n13. DB-backed authorization (stored-scope comparison)")
    f = fresh_db()
    seed_engagement(f, authorization_scope="internal_peak_only")
    cwr, _, p = build()
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("stored-scope mismatch denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "stored_scope_mismatch")
    check("no row on scope mismatch", count(f, SourceIngestionRecord) == 0)
    check("connection+sql made, no write", r.database_connection_made and r.sql_execution_made
          and r.database_write_made is False)
    f = fresh_db()
    seed_engagement(f, authorization_scope=None)
    cwr, _, p = build()
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("missing stored scope denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "missing_stored_scope")
    f = fresh_db()
    cwr, _, p = build()
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("missing stored subject denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "missing_subject")
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build(authorization_scope=None)
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("missing request scope denied", r.outcome == SourceIngestionWriteOutcome.DENIED)
    check("missing request scope: no DB connection", r.database_connection_made is False)
    check("missing request scope: no row", count(f, SourceIngestionRecord) == 0)

    # ---- Identity mismatches ----
    print("\n14. Identity mismatches")
    f = fresh_db()
    seed_engagement(f, owner_id="owner_2")
    cwr, _, p = build()
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("stored owner mismatch denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "identity_mismatch")
    f = fresh_db()
    seed_engagement(f, client_id="client_b")
    cwr, _, p = build()
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("stored client mismatch denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "identity_mismatch")
    f = fresh_db()
    seed_engagement(f, id="eng_other")
    cwr, _, p = build()  # engagement anchor eng_x absent
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("stored engagement mismatch (subject absent) denied",
          r.outcome == SourceIngestionWriteOutcome.DENIED and r.reason_code == "missing_subject")
    f = fresh_db()
    seed_engagement(f)
    cwr, d, p = build(draft_over=dict(engagement_id="eng_y"))
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("draft engagement mismatch denied (pre-DB)",
          r.outcome == SourceIngestionWriteOutcome.DENIED and r.database_connection_made is False)

    # ---- Action allowlist ----
    print("\n15. Action allowlist")
    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build(target_table="agent_run_records")
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("wrong table denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "wrong_target_table")
    cwr, _, p = build(requested_action="update_lifecycle_status")
    r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
    check("wrong action denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "wrong_target_action")
    for bad in ("delete_record", "publish_capsule", "client_facing_approve_record",
                "verify_financial_impact", "run_raw_sql"):
        cwr, _, p = build(requested_action=bad)
        r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
        check(f"prohibited action '{bad}' denied", r.outcome == SourceIngestionWriteOutcome.DENIED)
    check("allowlist denials made no row", count(f, SourceIngestionRecord) == 0)

    # ---- Posture / content ----
    print("\n16. Posture / content")
    posture_cases = {
        "output_status not draft": (dict(output_status="reviewed"), "invalid_draft_output_status"),
        "review_status not needs_review": (dict(review_status="approved_internal"),
                                           "invalid_draft_review_status"),
        "lifecycle_status not active": (dict(lifecycle_status="superseded"),
                                        "invalid_draft_lifecycle_status"),
        "authoritative true": (dict(authoritative=True), "prohibited_authoritative"),
        "client_facing_approved true": (dict(client_facing_approved=True),
                                        "prohibited_client_facing"),
        "capsule_candidate_ready true": (dict(capsule_candidate_ready=True),
                                         "prohibited_capsule_candidate"),
        "caller-supplied id": (dict(source_ingestion_record_id="ing_caller"),
                               "caller_supplied_id"),
        "caller-supplied timestamp": (dict(created_at="2026-01-01T00:00:00"),
                                      "caller_supplied_timestamp"),
        "missing source reference": (dict(packet_reference_id=None), "missing_source_reference"),
    }
    for label, (draft_over, code) in posture_cases.items():
        f = fresh_db()
        seed_engagement(f)
        cwr, d, p = build(draft_over=draft_over)
        r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
        check(f"{label} denied ({code})",
              r.outcome == SourceIngestionWriteOutcome.DENIED and r.reason_code == code
              and r.database_connection_made is False and count(f, SourceIngestionRecord) == 0)

    # Packet-content / secret attribute injections on the draft are rejected.
    print("\n17. Packet-content / secret guard")
    for inj_attr in ("packet_payload", "raw_packet_content", "api_key", "connection_string"):
        f = fresh_db()
        seed_engagement(f)
        cwr, d, p = build()
        setattr(d, inj_attr, {"x": "y"} if inj_attr.startswith("packet") else "SENSITIVE")
        r = persist_source_ingestion_record(cwr, session_factory=f, persistence_request=p)
        check(f"draft with '{inj_attr}' rejected",
              r.outcome == SourceIngestionWriteOutcome.DENIED
              and r.reason_code == "prohibited_packet_content"
              and count(f, SourceIngestionRecord) == 0)
        # Reason must not echo the injected secret value.
        check(f"'{inj_attr}' reason does not echo value",
              "SENSITIVE" not in " ".join(r.reasons))

    # ---- Duck-typed rejection ----
    print("\n18. Duck-typed / malformed rejection")
    class _Fake:
        target_table = "source_ingestion_records"
        requested_action = "create_source_ingestion_record"
    r = persist_source_ingestion_record(_Fake(), session_factory=fresh_db())
    check("duck-typed request denied", r.outcome == SourceIngestionWriteOutcome.DENIED
          and r.reason_code == "invalid_request_type" and r.database_connection_made is False)

    # ---- Transaction / failure semantics ----
    print("\n19. Transaction and failure semantics")

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
    seed_engagement(f)
    cwr, _, p = build()
    fail_get = lambda: _FailAt(f(), "get", SQLAlchemyError("boom-read"))  # noqa: E731
    r = persist_source_ingestion_record(cwr, session_factory=fail_get, persistence_request=p)
    check("failed_before_write on read failure",
          r.outcome == SourceIngestionWriteOutcome.FAILED_BEFORE_WRITE
          and r.database_write_made is False)
    check("failed_before_write left no row", count(f, SourceIngestionRecord) == 0)

    f = fresh_db()
    seed_engagement(f)
    cwr, _, p = build()
    fail_commit = lambda: _FailAt(f(), "commit", SQLAlchemyError("boom-commit"))  # noqa: E731
    r = persist_source_ingestion_record(cwr, session_factory=fail_commit, persistence_request=p)
    check("write_outcome_uncertain on commit failure",
          r.outcome == SourceIngestionWriteOutcome.WRITE_OUTCOME_UNCERTAIN
          and r.outcome_uncertain is True)

    f = fresh_db()
    seed_engagement(f)
    cwrA, _, pA = build()
    createdA = persist_source_ingestion_record(cwrA, session_factory=f, persistence_request=pA)
    orig_find = writer_mod._find_existing
    try:
        writer_mod._find_existing = lambda *a, **k: None
        cwrB, _, pB = build()
        rrep = persist_source_ingestion_record(cwrB, session_factory=f, persistence_request=pB)
        check("race -> idempotent_replay",
              rrep.outcome == SourceIngestionWriteOutcome.IDEMPOTENT_REPLAY
              and rrep.stored_record_id == createdA.stored_record_id)
        check("race replay left one row", count(f, SourceIngestionRecord) == 1)
        cwrC, dC, pC = build(draft_over=dict(packet_hash="sha256:race_conflict"))
        rconf = persist_source_ingestion_record(cwrC, session_factory=f, persistence_request=pC)
        check("race -> conflict denied",
              rconf.outcome == SourceIngestionWriteOutcome.DENIED
              and rconf.reason_code == "idempotency_conflict")
        check("race conflict left one row", count(f, SourceIngestionRecord) == 1)
    finally:
        writer_mod._find_existing = orig_find

    print("\n20. Rollback safety")
    check("no partial row after failure paths", count(f, SourceIngestionRecord) == 1)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 24 controlled-DB source-ingestion-writer check")
    print("=" * 52)

    structural_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
        print("         Run: make validate-phase24 PYTHON=.venv/bin/python")
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
