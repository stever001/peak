#!/usr/bin/env python3
"""Phase 63 first internal test source ingestion record check.

Phase 62 planned the source/evidence requests and named the path: the unchanged Phase 24
``source_ingestion_records`` writer, with R8 (the system-of-record and data-export map) first
because it determines whether R1-R7 are fulfillable. Phase 63 registers that R8 artifact as
**one** metadata-only source ingestion record.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite,
and the operator utility is exercised with every role variable scrubbed from the child environment
so its dry-run default is proven to open no connection.

**No artifact body lives in this repository and none is read here.** The external R8 artifact is
never opened by this harness; the writer fixture uses a synthetic hash built at runtime. Only
metadata — a packet reference, schema name/version, source type, a *logical* location reference,
and a hash — may ever reach the database.

Layers: baseline · writer contract · packet · operator utility · writer behaviour · docs ·
isolation.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import hashlib
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "da75af6"   # Add Phase 62 internal test source evidence plan

TOOL_REL = "tools/create_internal_test_source_ingestion_record.py"
HARNESS_REL = "tests/validate_phase63_first_internal_test_source_ingestion.py"
DOC_REL = "docs/PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md"
PLAN_REL = "docs/PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md"
WRITER_REL = "peak/db/source_ingestion_writer.py"
MODELS_REL = "peak/db/models.py"
ALLOWLIST_REL = "peak/persistence/allowlist.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"

ANCHOR_ID = "internal_test_001"
RESERVED_CLIENT_ID = "99999"
SCOPE = "internal_peak_only"

#: The writer's own forbidden draft attributes — none may appear on the operator's draft.
FORBIDDEN_DRAFT_ATTRS = ("packet_payload", "raw_packet_content", "raw_content", "payload")

#: The artifact body must never be committed. Its filename must appear nowhere in the repo.
ARTIFACT_BASENAME = "r8_system_of_record_data_export_map_v1.json"

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!internal-test-artifact)[\w.\-]+:[^\s@'\"]+@")
SENTINEL_MARK = "sentinel-name-list"
CLIENT_LIKE_NAMES = ("acme", "contoso", "initech", "globex", "northwind")  # sentinel-name-list
CLIENT_LIKE_RE = re.compile(r"(?i)\b(" + "|".join(CLIENT_LIKE_NAMES) + r")\b")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []
_tmpdirs: list = []


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def code_only(source: str) -> str:
    """Executable code with every string literal and comment blanked out, in place.

    Blanked in place rather than dropped and re-joined: re-joining inserts whitespace between
    tokens, so a dotted expression like ``os.environ.get(...)`` would stop matching and a scan
    would silently pass on code that violates it. Stripping literals matters here because the
    operator utility's own docstring names the very patterns it must not execute.
    """
    import io
    import tokenize

    skip = {tokenize.STRING, tokenize.COMMENT}
    for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
        tok_type = getattr(tokenize, name, None)
        if tok_type is not None:
            skip.add(tok_type)

    lines = source.splitlines()
    spans = [(tok.start, tok.end)
             for tok in tokenize.generate_tokens(io.StringIO(source).readline)
             if tok.type in skip]
    for (row1, col1), (row2, col2) in reversed(spans):
        if row1 == row2:
            line = lines[row1 - 1]
            lines[row1 - 1] = line[:col1] + " " * (col2 - col1) + line[col2:]
        else:
            lines[row1 - 1] = lines[row1 - 1][:col1]
            for i in range(row1, row2 - 1):
                lines[i] = ""
            lines[row2 - 1] = " " * col2 + lines[row2 - 1][col2:]
    return "\n".join(lines)


def scannable(blob: str) -> str:
    """A file's text with the sentinel name list removed, so the detector never flags itself."""
    return "\n".join(ln for ln in blob.splitlines() if SENTINEL_MARK not in ln)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)).lower()


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def tmpdir() -> str:
    tmp = tempfile.mkdtemp(prefix="peak_phase63_")
    _tmpdirs.append(tmp)
    return tmp


def temp_sqlite_url() -> str:
    return "sqlite:///" + os.path.join(tmpdir(), "phase63.db")


def synthetic_packet_hash(salt: str = "a") -> str:
    """A throwaway hash built at runtime. The real R8 artifact is never opened by this harness."""
    return hashlib.sha256(("phase63-synthetic-fixture-" + salt).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, nothing added")
    check(f"baseline commit {BASELINE_COMMIT} is in history",
          BASELINE_COMMIT in git("log", "--format=%h", "-40"))

    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later — Phase 63 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    # Pathspec narrowed to match the label: it read "alembic", which also covered
    # alembic/env.py and froze that file against every later phase.
    check("no migration file was added or modified by this phase",
          not git("diff", "--name-only", "HEAD", "--", "alembic/versions"))

    for rel in (TOOL_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("peak/db/models.py was not modified by this phase — no model added",
          not git("diff", "--name-only", "HEAD", "--", MODELS_REL))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])
    check("the allowlist module was not modified by this phase — no allowlist pair added",
          not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )
    check("generic allowlist unchanged — no new writer/model/allowlist pair",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES
          and len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("still exactly one anchor-creation pair", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check("engagements remains prohibited generically",
          is_prohibited_table("engagements") and not is_allowed_table("engagements"))
    check("clients remains never writable by any controlled path",
          is_never_writable_table("clients"))
    check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx"))


# --------------------------------------------------------------------------- 2. writer contract


def writer_contract_checks() -> None:
    print("\n2. source_ingestion_records honestly represents a metadata-only registration")
    from peak.ingestion.contracts import (
        SOURCE_INGESTION_ACTION, SOURCE_INGESTION_TABLE, SourceIngestionDraft,
    )
    from peak.persistence.allowlist import is_allowed_action, is_allowed_table

    check("source_ingestion_records is an allowed controlled-write table",
          is_allowed_table(SOURCE_INGESTION_TABLE))
    check("create_source_ingestion_record is an allowed controlled-write action",
          is_allowed_action(SOURCE_INGESTION_ACTION))

    fields = set(SourceIngestionDraft.__dataclass_fields__)
    check("the draft carries the packet reference persisted as source_reference_id",
          "packet_reference_id" in fields)
    check("the draft carries packet metadata only",
          {"packet_schema_name", "packet_schema_version", "packet_source_type",
           "packet_location_reference", "packet_hash"} <= fields)
    check("the draft has no raw payload field",
          not (set(FORBIDDEN_DRAFT_ATTRS) & fields))
    check("no evidence characterization is required at this stage",
          not ({"evidence_type", "reliability", "evidence_status"} & fields))

    code = code_only(read(WRITER_REL))
    check("the writer is create-only — one insert, no update, merge, or delete",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))
    check("the writer issues no raw SQL",
          not re.search(r"session\.execute\(|\btext\(|cursor\.", code))
    check("the writer refuses payload and secret-named draft attributes",
          "FORBIDDEN_CONTENT_ATTRS" in code and "SECRET_TERMS" in code)
    check("the writer loads the stored Engagement and compares stored scope",
          "Engagement" in code and "stored_scope_mismatch" in read(WRITER_REL))
    check("the writer's idempotency boundary includes owner/client/engagement",
          all(k in code for k in ("owner_id", "client_id", "engagement_id", "idempotency_key")))


# --------------------------------------------------------------------------- 3. the packet


def packet_checks() -> None:
    print("\n3. The one authorized packet is metadata-only, internal-only, and non-final")
    import create_internal_test_source_ingestion_record as tool

    check(f"packet is anchored to engagement {ANCHOR_ID} / client {RESERVED_CLIENT_ID}",
          tool.ENGAGEMENT_ID == ANCHOR_ID and tool.CLIENT_ID == RESERVED_CLIENT_ID)
    check("owner is the internal admin", tool.OWNER_ID == "peak_internal_admin")
    check(f"scope is {SCOPE}", tool.AUTHORIZATION_SCOPE == SCOPE)
    check("the packet is the R8 system-of-record map",
          "r8" in tool.PACKET_REFERENCE_ID.lower())
    check("the stored location reference is logical, not a filesystem path",
          tool.PACKET_LOCATION_REFERENCE.startswith("internal-test-artifact://")
          and not tool.PACKET_LOCATION_REFERENCE.startswith("/")
          and "\\" not in tool.PACKET_LOCATION_REFERENCE
          and os.path.expanduser("~") not in tool.PACKET_LOCATION_REFERENCE)
    check("the approved artifact lives outside the repository",
          not os.path.realpath(tool.APPROVED_ARTIFACT_DIR).startswith(
              os.path.realpath(REPO_ROOT) + os.sep))

    reasons = list(tool.REASONS)
    check("provenance notes cite the Phase 62 plan and R8",
          any("PHASE62" in r and "R8" in r for r in reasons))
    check("provenance notes explain why R8 precedes R1-R7",
          any("R1-R7" in r for r in reasons))
    check("provenance notes name the taxonomy categories",
          any("08_systems_of_record" in r and "09_data_exports" in r for r in reasons))
    check("provenance notes state the internal-only, no-real-client-data posture",
          any("no real client data" in r and "not client-facing" in r for r in reasons))
    check("provenance notes state the metadata-only content rule",
          any(r.startswith("content_rule:") and "metadata only" in r for r in reasons))
    check("provenance notes withhold evidence/report/capsule/publication authority",
          any(r.startswith("not_authorized:") and "publication" in r for r in reasons))
    check("provenance notes disclose the artifact is Peak-authored, not client-supplied",
          any("not a client-supplied export" in r for r in reasons))

    request = tool.build_request(synthetic_packet_hash())
    draft = request.record_draft
    check("the draft carries no forbidden raw payload attribute",
          not any(hasattr(draft, a) for a in FORBIDDEN_DRAFT_ATTRS))
    check("the draft leaves server-controlled fields unset",
          draft.source_ingestion_record_id is None and draft.created_at is None)
    check("the draft posture is draft / needs_review / active",
          draft.output_status == "draft" and draft.review_status == "needs_review"
          and draft.lifecycle_status == "active")
    check("the draft is non-authoritative, non-client-facing, not capsule-ready",
          draft.authoritative is False and draft.client_facing_approved is False
          and draft.capsule_candidate_ready is False)
    check("the authorization anchor is the engagement, never the packet",
          request.subject.subject_record_type == "engagement"
          and request.subject.subject_record_id == ANCHOR_ID)
    check("the request targets source_ingestion_records / create_source_ingestion_record",
          request.target_table == "source_ingestion_records"
          and request.requested_action == "create_source_ingestion_record")

    from peak.db.source_ingestion_writer import _pre_db_validate
    denial, validated = _pre_db_validate(request, None)
    check("packet passes the writer's pre-DB governance gate (no connection opened)",
          denial is None and validated is not None)


# --------------------------------------------------------------------------- 4. operator utility


def tool_checks() -> None:
    print("\n4. The operator utility writes one record and can express no other")
    src = read(TOOL_REL)
    code = code_only(src)

    check("utility defaults to dry-run — --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check("utility invokes only the existing controlled source ingestion writer",
          "persist_source_ingestion_record" in code
          and not re.search(r"persist_(?!source_ingestion_record)\w+", code))
    check("utility creates no Client, Engagement, intake, review, evidence, report, or capsule "
          "record",
          not re.search(r"(?i)\bClient\(|\bEngagement\(|IntakeNoteDraft|ReviewRecordDraft|"
                        r"persist_intake|persist_review|persist_evidence|persist_agent_run|"
                        r"persist_internal_|persist_engagement|publish", code))
    check("utility performs no UPDATE/DELETE/cleanup/stamp call",
          not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{|"
                        r"(?i)\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b|alembic\s+stamp", code))
    check("utility issues no raw SQL",
          not re.search(r"(?i)\btext\(|session\.execute\(|conn(?:ection)?\.execute\(|"
                        r"engine\.execute\(|cursor\.|\bSELECT\s+\w+\s+FROM\b", code))
    check("utility imports no migration/Alembic code",
          "alembic" not in code.lower() and "op.add_column" not in code)
    check("utility reads no environment variable directly",
          not re.search(r"os\.environ|getenv", code))
    check("utility never decodes or prints the artifact body",
          re.search(r'open\(path,\s*["\']rb["\']\)', src) is not None
          and not re.search(r"\.read\(\)\s*\.decode|print\(\s*(?:blob|body|content|chunk)", code))
    check("utility never places artifact content on the draft",
          not any(f"{a}=" in code for a in FORBIDDEN_DRAFT_ATTRS))
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    args = set(re.findall(r'add_argument\("(--[a-z-]+)"', src))
    check("utility exposes only run mode and the artifact path — no record field is a flag",
          args <= {"--dry-run", "--execute", "--artifact-path"})

    env = scrubbed_env()

    def run_tool(*extra):
        return subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL), *extra],
                              capture_output=True, text=True, timeout=120, env=env)

    run = run_tool("--dry-run")
    check("dry-run exits 0 with no credential in the environment", run.returncode == 0)
    check("dry-run reports no connection was made",
          "database_connection_made              : False" in run.stdout)
    check("dry-run reports nothing was written", "DRY-RUN PASS" in run.stdout)
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))
    check("dry-run discloses that stored-engagement authorization is not exercised",
          "NOT exercised by this dry-run" in run.stdout)
    check("dry-run prints the logical location reference, not a filesystem path",
          "internal-test-artifact://phase63/" in run.stdout)
    # Artifact-agnostic: the artifact is JSON, so any leak would carry object syntax. Matching
    # on the artifact's own key names would instead copy its internals into this repository.
    check("dry-run prints no JSON object syntax — the artifact body cannot have leaked",
          "{" not in run.stdout and "}" not in run.stdout
          and not re.search(r'(?m)^\s*"[a-z_]+"\s*:', run.stdout))
    check("dry-run output is a short sanitized summary, not a document dump",
          len(run.stdout) < 8000)
    check("dry-run prints no home-directory path outside the clearly-labelled artifact line",
          not re.search(r"(?m)^(?!.*artifact path).*" + re.escape(os.path.expanduser("~")),
                        run.stdout))

    inside = run_tool("--artifact-path", os.path.join(REPO_ROOT, "README.md"))
    check("utility refuses an artifact path inside the repository",
          inside.returncode == 1 and "inside the repository" in (inside.stderr + inside.stdout))
    outside = run_tool("--artifact-path", os.path.join(tmpdir(), "elsewhere.json"))
    check("utility refuses any path other than the approved R8 artifact",
          outside.returncode == 1
          and "not the approved" in (outside.stderr + outside.stdout))


# --------------------------------------------------------------------------- 5. writer behaviour


def writer_checks() -> None:
    print("\n5. The writer creates exactly one record, and nothing else")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as anchor_tool
    import create_internal_test_source_ingestion_record as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.models import (
        Client, Engagement, EvidenceReference, IntakeNoteRecord, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.db.source_ingestion_writer import persist_source_ingestion_record

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    anchor = persist_engagement_authorization_anchor(anchor_tool.build_request(),
                                                     session_factory=factory)
    check("the engagement anchor exists for the ingestion to be written under",
          anchor.outcome == "created")

    packet_hash = synthetic_packet_hash()
    receipt = persist_source_ingestion_record(tool.build_request(packet_hash),
                                              session_factory=factory)
    check("first invocation creates the source ingestion record", receipt.outcome == "created")
    check("receipt reports one stored record created", receipt.stored_record_created is True)
    check("receipt reports the record is review-gated",
          receipt.review_status == "needs_review" and receipt.output_status == "draft")

    session = factory()
    check("exactly one source ingestion record exists",
          session.query(SourceIngestionRecord).count() == 1)
    row = session.query(SourceIngestionRecord).one()
    check("the record is tied to the internal_test engagement",
          row.engagement_id == ANCHOR_ID and row.client_id == RESERVED_CLIENT_ID
          and row.owner_id == "peak_internal_admin" and row.authorization_scope == SCOPE)
    check("the ingesting engagement is classified internal_test",
          session.get(Engagement, row.engagement_id).engagement_category == "internal_test")
    check("the record's source reference is the packet reference",
          row.source_reference_id == tool.PACKET_REFERENCE_ID)
    check("the stored detail is metadata only — schema, source type, location, hash",
          {"packet_schema_name", "packet_source_type", "packet_location_reference",
           "packet_hash"} <= set(row.details_json))
    check("the stored hash is the packet hash, not artifact content",
          row.details_json["packet_hash"] == packet_hash)
    check("the stored location reference is logical, not a filesystem path",
          row.details_json["packet_location_reference"].startswith("internal-test-artifact://"))
    check("no raw artifact payload was stored anywhere on the row",
          not any(k in row.details_json for k in FORBIDDEN_DRAFT_ATTRS))
    check("the stored row carries no home-directory path",
          os.path.expanduser("~") not in str(row.details_json))
    check("the record is non-authoritative and not capsule-ready",
          row.details_json["authoritative"] is False
          and row.details_json["client_facing_approved"] is False
          and row.details_json["capsule_candidate_ready"] is False)

    # Nothing else was written.
    check("no Client row was created", session.query(Client).count() == 0)
    check("still exactly one engagement row", session.query(Engagement).count() == 1)
    check("no intake note record was created", session.query(IntakeNoteRecord).count() == 0)
    check("no review record was created", session.query(ReviewRecord).count() == 0)
    check("no evidence reference was created", session.query(EvidenceReference).count() == 0)
    session.close()

    # Replay: identical payload must not write a second row.
    replay = persist_source_ingestion_record(tool.build_request(packet_hash),
                                             session_factory=factory)
    check("identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    session = factory()
    check("still exactly one source ingestion record after replay",
          session.query(SourceIngestionRecord).count() == 1)
    session.close()

    # A changed artifact hash under the same idempotency key must conflict, never overwrite.
    conflict = persist_source_ingestion_record(
        tool.build_request(synthetic_packet_hash("b")), session_factory=factory)
    check("a changed artifact hash under the same idempotency key is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("still exactly one source ingestion record after the conflict",
          session.query(SourceIngestionRecord).count() == 1)
    stored = session.query(SourceIngestionRecord).one()
    check("the existing record was not overwritten",
          stored.id == receipt.stored_record_id
          and stored.details_json["packet_hash"] == packet_hash)
    session.close()


# --------------------------------------------------------------------------- 6. docs


def doc_checks() -> None:
    print("\n6. Docs state what was written, what was not, and what comes next")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("doc content checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    f = flat(doc)
    for phrase, label in (
        ("one", "exactly one record is described"),
        ("source ingestion record", "a source ingestion record was created"),
        ("system-of-record", "the R8 system-of-record/data-export map is the subject"),
        ("outside the repository", "the artifact body lives outside the repository"),
        ("metadata", "only metadata was persisted"),
        ("packet_hash", "the hash is named as what was persisted"),
        ("internal-test-artifact://", "the logical location reference is recorded"),
        ("no evidence reference", "no evidence_reference was created yet"),
        ("no report", "no report record was created"),
        ("no capsule", "no capsule was created"),
        ("no client-facing output", "no client-facing output was created"),
        ("precondition", "this closes the first Phase 62 precondition"),
        ("evidence_references", "evidence_references are named as coming later"),
        ("after source ingestion", "evidence still comes after source ingestion"),
        (ANCHOR_ID, "the engagement anchor is named"),
        (SCOPE, "the authorization scope is named"),
    ):
        check(f"doc states: {label}", phrase in f)

    # Written with an en dash in prose; accept either dash so the check tests the claim, not
    # the typography.
    check("doc states: later R1-R7 evidence collection is named",
          re.search(r"r1[-\u2013\u2014]r7", f) is not None)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("doc contains no artifact filesystem path",
          ARTIFACT_BASENAME not in doc)

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md", PLAN_REL,
                "docs/PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md"):
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records Phase 63", "phase 63" in blob)
        check(f"{name} states no evidence reference was created yet",
              "no evidence reference" in blob or "evidence_references still" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase63", "validate-phase63" in mk)
    check("validate depends on validate-phase63",
          re.search(r"^validate:.*validate-phase63", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)
    check("the record-creation utility is not wired into validate",
          "create_internal_test_source_ingestion_record" not in mk)


# --------------------------------------------------------------------------- 7. isolation


def isolation_checks() -> None:
    print("\n7. No production contact, no artifact body, no fixture in the repository")
    src = read(HARNESS_REL)
    code = code_only(src)

    urls = re.findall(r"create_engine\(\s*([a-z_]+)\(", src)
    check("this harness builds only temporary SQLite database URLs",
          set(urls) <= {"temp_sqlite_url"})
    check("this harness scrubs every role variable from child processes",
          all(v in src for v in ROLE_VARS))
    check("this harness never passes --execute to the operator utility",
          not re.search(r'run_tool\(\s*["\']--execute', src))
    check("this harness reads no role/environment variable for a connection",
          not re.search(r"os\.environ\s*\[", code))
    check("this harness never opens the external R8 artifact",
          ARTIFACT_BASENAME not in code and "peak-internal-test-artifacts" not in code)
    check("this harness's packet hash is synthetic and built at runtime",
          "def synthetic_packet_hash" in src)
    check("this harness embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    tracked = git("ls-files").splitlines()
    check("no artifact body file is tracked in the repository",
          not [t for t in tracked if ARTIFACT_BASENAME in t])
    check("no internal-test-artifact directory is tracked in the repository",
          not [t for t in tracked if "peak-internal-test-artifacts" in t])
    check("no fixtures/examples/sample-packet directory is tracked",
          not [t for t in tracked
               if re.match(r"^(fixtures|examples|samples|sample_packets)/", t)])
    check("no sample or fixture packet file is tracked",
          not [t for t in tracked
               if re.search(r"(?i)(fixture|sample|example)[^/]*\.(json|ya?ml|csv|txt)$", t)])
    check("no intake note body file is tracked in the repository",
          not [t for t in tracked if "internal_test_intake_note" in t and t.endswith(".txt")])
    check("no .json or .txt artifact was added by this phase",
          not [c for c in git("diff", "--name-only", "HEAD").splitlines()
               if c.endswith((".json", ".txt"))]
          and not [c for c in git("ls-files", "--others", "--exclude-standard").splitlines()
                   if c.endswith((".json", ".txt"))])

    for rel in (TOOL_REL, HARNESS_REL, DOC_REL, PLAN_REL):
        if not os.path.isfile(os.path.join(REPO_ROOT, rel)):
            continue
        blob = read(rel)
        name = os.path.basename(rel)
        check(f"{name} contains no obviously client-like organisation name",
              not CLIENT_LIKE_RE.search(scannable(blob)))
        check(f"{name} embeds no secret-like assignment",
              not re.search(r"(?i)(password|api[_-]?key|secret|private[_-]?key|access[_-]?key)"
                            r"\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{8,}", blob))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 63 first internal test source ingestion record check")
    print("=" * 70)
    try:
        baseline_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed — contract/packet/writer layers skipped.")
            print("         Run: make validate-phase63 PYTHON=.venv/bin/python")
        else:
            writer_contract_checks()
            packet_checks()
            tool_checks()
            writer_checks()

        doc_checks()
        isolation_checks()
    finally:
        for tmp in _tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
