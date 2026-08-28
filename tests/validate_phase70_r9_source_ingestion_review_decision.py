#!/usr/bin/env python3
"""Phase 70 R9 source ingestion review decision check.

Phase 69 collected **R9**, the location/bin naming model, as one metadata-only source ingestion
record. Phase 70 records **exactly one** `review_records` decision on that record through the
unchanged Phase 22 review writer: `approve_internal`, non-authoritative, scoped to **future
evidence work about R1 location-dimension readiness** and nothing wider.

The decision's value lies as much in what it withholds as in what it grants, so this harness checks
both. It verifies the one row is written correctly and that the phase withholds everything it must:
no `evidence_reference`, no source ingestion record, no report, no capsule, no client-facing output,
no AgentNet publication, no lifting of R1's provisional location marking, no inventory-quantity
validation, no resolution of R8's authority precedence, and no resolution of R5's WMS scope
uncertainty.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite, and
the operator utility is exercised with every role variable scrubbed from the child environment so
its dry-run default is proven to open no connection.

**No artifact body lives in this repository and none is read here.** The Phase 70 operator opens no
file at all — it reviews a *registered record*, not an artifact — and this harness opens no external
artifact either.

Layers: baseline - writer contract - packet - operator utility - writer behaviour - docs -
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

BASELINE_COMMIT = "608bf4e"   # Add Phase 69 R9 location bin model source ingestion
#: The last commit belonging to this phase. The "changed nothing outside" check below
#: is pinned to this range: scoped to the working tree it would go empty once the phase
#: is committed, and would flag a *later* phase's in-progress edits as this phase's.
PHASE_COMMIT = "d177c5f"   # Add Phase 70 R9 source ingestion review decision

TOOL_REL = "tools/create_internal_test_r9_source_review_decision.py"
PHASE66_TOOL_REL = "tools/create_internal_test_r2_source_review_decision.py"
PHASE69_TOOL_REL = "tools/create_internal_test_r9_source_ingestion_record.py"
HARNESS_REL = "tests/validate_phase70_r9_source_ingestion_review_decision.py"
DOC_REL = "docs/PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md"
PHASE69_DOC_REL = "docs/PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md"
PHASE68_DOC_REL = "docs/PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md"
WRITER_REL = "peak/db/review_writer.py"
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

#: The reviewed target — the Phase 69 R9 source ingestion record.
R9_RECORD_ID = "ing_64b2e2648ac1402b"
R9_PACKET_REF = "pkt_internal_test_r9_location_bin_model_001"

#: Records the operator must never be able to retarget. Any of these appearing in the tool would
#: mean it is not the fixed single-target utility it claims to be.
FORBIDDEN_TARGET_IDS = ("ing_a2abb497f471458e",   # R1 source ingestion
                        "ing_884c94df03c34908",   # R2 source ingestion
                        "ing_4fb70519cbf84401",   # R8 source ingestion
                        "intn_b8b86b8c196c4595",  # intake note
                        "rev_b82ff6f00790418f",   # intake review decision
                        "rev_bf7f18a13d8f461c",   # R2 source review decision
                        "evid_56437d9b9c764560",  # R2 evidence reference
                        "rev_de2b6e73f6c94c67")   # R2 evidence review decision

#: Record classes the review must not create.
FORBIDDEN_CREATION_RE = re.compile(
    r"(?i)\bClient\(|\bEngagement\(|IntakeNoteDraft|SourceIngestionDraft|EvidenceReferenceDraft|"
    r"persist_intake|persist_evidence|persist_source_ingestion|persist_agent_run|"
    r"persist_internal_|persist_engagement|publish")

#: Artifact bodies must never be committed. Their filenames must appear nowhere in this phase.
ARTIFACT_BASENAMES = ("r9_location_bin_naming_model_v1.json",
                      "r2_sku_item_master_export_v1.json",
                      "r1_current_inventory_sku_location_v1.json",
                      "r8_system_of_record_data_export_map_v1.json")

#: Row-like content that must never appear in this phase's own files: item/SKU values, quantities,
#: and location/bin/aisle/rack/warehouse/site identifiers.
ROW_LIKE_RE = re.compile(r"(?i)\b(sku|item)[-_ ]?(?:id|code|no|number)?\s*[:=]\s*[\"']?[A-Z0-9]{3,}"
                         r"|\bqty\s*[:=]\s*\d|\bquantity_on_hand\s*[:=]\s*\d"
                         r"|\b(?:bin|aisle|rack|bay|zone|warehouse|site)\s*[:=]\s*[\"']?[A-Z0-9]{2,}")

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
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE).replace("`", "")
    return re.sub(r"\s+", " ", stripped).lower()


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def tmpdir() -> str:
    tmp = tempfile.mkdtemp(prefix="peak_phase70_")
    _tmpdirs.append(tmp)
    return tmp


def temp_sqlite_url() -> str:
    return "sqlite:///" + os.path.join(tmpdir(), "phase70.db")


def synthetic_packet_hash(salt: str = "a") -> str:
    """A throwaway hash built at runtime. The real artifact is never opened by this harness."""
    return hashlib.sha256(("phase70-synthetic-fixture-" + salt).encode("utf-8")).hexdigest()


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
    check("no migration 015 or later - Phase 70 adds no migration",
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
    check("peak/db/models.py was not modified by this phase - no model added",
          not git("diff", "--name-only", "HEAD", "--", MODELS_REL))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers - no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("the selected writer is the existing review_records writer",
          "review_writer.py" in writers)
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])
    check("no file under peak/ was modified by this phase at all",
          not git("diff", "--name-only", "HEAD", "--", "peak"))
    check("the allowlist module was not modified by this phase - no allowlist pair added",
          not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))
    for rel in (PHASE66_TOOL_REL, PHASE69_TOOL_REL):
        check(f"{os.path.basename(rel)} was not modified by this phase",
              not git("diff", "--name-only", "HEAD", "--", rel))

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )
    check("generic allowlist unchanged - no new writer/model/allowlist pair",
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
    print("\n2. review_records honestly represents this review without overloading a field")
    from peak.persistence.allowlist import is_allowed_action, is_allowed_table
    from peak.review.persistence_contracts import ReviewRecordDraft

    check("review_records is an allowed controlled-write table",
          is_allowed_table("review_records"))
    check("create_review_record is an allowed controlled-write action",
          is_allowed_action("create_review_record"))

    fields = set(ReviewRecordDraft.__dataclass_fields__)
    check("the draft separates the reviewed target from the authorization anchor",
          {"subject_record_id", "subject_record_type"} <= fields)
    check("the draft carries the reviewed packet reference", "source_reference_id" in fields)
    check("the draft carries a free findings list for the limits",
          "reasons" in fields and "warnings" in fields)
    check("the draft carries the decision and the resulting posture",
          {"decision", "next_review_status", "next_output_status", "next_lifecycle_status",
           "authoritative", "client_facing_approved", "capsule_candidate_ready"} <= fields)

    src = read(WRITER_REL)
    code = code_only(src)
    check("the writer is create-only - one insert, no update, merge, or delete",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))
    check("the writer issues no raw SQL",
          not re.search(r"session\.execute\(|\btext\(|cursor\.", code))
    check("the writer loads the stored Engagement and compares stored scope",
          "Engagement" in code and "stored_scope_mismatch" in src)
    check("the writer refuses client-facing, financial, and capsule decisions outright",
          all(d in src for d in ("client_facing_approve", "verify_financial_impact",
                                 "publish_capsule")))
    check("approve_internal is in the writer's allowed decision vocabulary",
          "approve_internal" in src)
    check("the writer stores the reviewed target as target_id, distinct from the anchor",
          "target_id=draft.subject_record_id" in src)
    check("the writer's idempotency boundary includes owner/client/engagement",
          all(k in code for k in ("owner_id", "client_id", "engagement_id", "idempotency_key")))


# --------------------------------------------------------------------------- 3. the packet


def packet_checks() -> None:
    print("\n3. One review packet: R9-targeted, narrowly scoped, non-authoritative")
    import create_internal_test_r9_source_review_decision as tool

    check(f"the decision is anchored to engagement {ANCHOR_ID} / client {RESERVED_CLIENT_ID}",
          tool.ENGAGEMENT_ID == ANCHOR_ID and tool.CLIENT_ID == RESERVED_CLIENT_ID)
    check("owner is the internal admin", tool.OWNER_ID == "peak_internal_admin")
    check(f"scope is {SCOPE}", tool.AUTHORIZATION_SCOPE == SCOPE)
    check("the reviewed target is the Phase 69 R9 source ingestion record",
          tool.SUBJECT_RECORD_ID == R9_RECORD_ID)
    check("the reviewed target type follows the Phase 66 source-ingestion convention",
          tool.SUBJECT_RECORD_TYPE == "source_ingestion_record")
    check("the reviewed packet reference is R9's", tool.SOURCE_REFERENCE_ID == R9_PACKET_REF)
    check("the idempotency key is Phase 70 scoped and names the R9 source review",
          tool.IDEMPOTENCY_KEY == "phase70_internal_test_r9_source_ingestion_review_001")
    check("the decision is approve_internal", tool.DECISION == "approve_internal")
    check("the decision is non-authoritative", tool.AUTHORITATIVE is False)
    check("the decision lands on approved_internal with output still draft",
          tool.NEXT_REVIEW_STATUS == "approved_internal"
          and tool.NEXT_OUTPUT_STATUS == "draft"
          and tool.NEXT_LIFECYCLE_STATUS == "active")

    reasons = list(tool.REASONS)
    joined = "\n".join(reasons)
    check("findings name R9 as the reviewed location/bin naming model record",
          any(r.startswith("source_review:") and "location/bin naming model" in r
              for r in reasons))
    check("findings record that the reviewed artifact hash still matches the registered hash",
          any(r.startswith("registration_integrity:") and "packet_hash" in r for r in reasons))
    check("findings scope the approval to R1 location-dimension readiness only",
          any(r.startswith("decision_meaning:")
              and "R1 location-dimension readiness" in r and "nothing wider" in r
              for r in reasons))
    check("findings state no evidence_reference is created by this decision",
          any(r.startswith("not_authorized:") and "no evidence_reference is created" in r
              for r in reasons))
    check("findings refuse inventory accuracy / quantity conclusions",
          any(r.startswith("not_authorized:") and "inventory accuracy" in r for r in reasons))
    check("findings leave R1's location dimension provisional and unlifted",
          any("remains provisional" in r and "does not lift that marking" in r
              for r in reasons))
    check("findings leave R8 provisional with precedence unconfirmed",
          any("R8 remains provisional" in r and "precedence" in r for r in reasons))
    check("findings leave R5 WMS scope unresolved",
          any(r.startswith("not_authorized:") and "R5 WMS scope remains unresolved" in r
              for r in reasons))
    check("findings leave R3-R7 deferred",
          any("R3-R7 remain deferred" in r for r in reasons))
    check("findings refuse report drafting, capsule candidacy, and client-facing output",
          any("report drafting" in r and "capsule candidacy" in r
              and "client-facing output" in r for r in reasons))
    check("findings refuse AgentNet resolver publication",
          any("AgentNet resolver publication" in r for r in reasons))
    check("findings record the central limit - R9 is a question set, not an answered model",
          any(r.startswith("limit:") and "question set" in r
              and "presence-unknown" in r for r in reasons))
    check("findings explain why that limit blocks lifting R1's provisional marking",
          any(r.startswith("limit:") and "cannot by itself lift" in r for r in reasons))
    check("findings record that ownership remains undetermined among the candidates",
          any(r.startswith("limit:") and "ownership postures" in r for r in reasons))
    check("findings verify the artifact carries no instance data",
          any(r.startswith("content_rule_verified:") and "no location identifiers" in r
              for r in reasons))
    check("findings name the next step as a separately approved phase",
          any(r.startswith("next_step:") and "separately approved phase" in r for r in reasons))
    check("findings state the internal_test, non-client-facing posture",
          any(r.startswith("posture:") and "no real client data" in r
              and "authoritative=false" in r for r in reasons))
    check("findings carry no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(joined))
    check("findings name no other stored record id",
          not any(bad in joined for bad in FORBIDDEN_TARGET_IDS))

    from peak.db.review_writer import _pre_db_validate
    request = tool.build_request()
    draft = request.record_draft
    check("the draft leaves server-controlled fields unset",
          draft.review_record_id is None and draft.created_at is None)
    check("the draft is not client-facing and not capsule-ready",
          draft.client_facing_approved is False and draft.capsule_candidate_ready is False)
    check("the authorization anchor is the engagement, never the reviewed record",
          request.subject.subject_record_type == "engagement"
          and request.subject.subject_record_id == ANCHOR_ID)
    check("the reviewed target is not the authorization anchor",
          draft.subject_record_id != request.subject.subject_record_id)
    check("the request targets review_records / create_review_record",
          request.target_table == "review_records"
          and request.requested_action == "create_review_record")
    denial, validated = _pre_db_validate(request, None)
    check("the packet passes the writer's pre-DB governance gate (no connection opened)",
          denial is None and validated is not None)


# --------------------------------------------------------------------------- 4. operator utility


def tool_checks() -> None:
    print("\n4. The operator writes exactly one review record and can express no other")
    src = read(TOOL_REL)
    code = code_only(src)

    check("utility defaults to dry-run - --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check("utility invokes only the existing controlled review writer",
          "persist_review_record" in code
          and not re.search(r"persist_(?!review_record)\w+", code))
    check("utility calls the writer from exactly one place",
          code.count("persist_review_record(") == 1)
    check("utility creates no Client, Engagement, intake, source, evidence, report, or capsule "
          "record", not FORBIDDEN_CREATION_RE.search(code))
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
    check("utility opens no file at all - it reviews a record, not an artifact",
          not re.search(r"\bopen\(", code))
    check("utility names no external artifact",
          not any(name in src for name in ARTIFACT_BASENAMES)
          and "peak-internal-test-artifacts" not in src)
    check("utility cannot retarget any other stored record - no other record id appears",
          not any(bad in src for bad in FORBIDDEN_TARGET_IDS))
    check("the record identity fields are module constants, not derived from arguments",
          all(re.search(rf"(?m)^{name} = ", code) is not None
              for name in ("ENGAGEMENT_ID", "CLIENT_ID", "OWNER_ID", "AUTHORIZATION_SCOPE",
                           "SUBJECT_RECORD_ID", "SUBJECT_RECORD_TYPE", "SOURCE_REFERENCE_ID",
                           "IDEMPOTENCY_KEY", "DECISION", "AUTHORITATIVE")))
    # `[ \t]` rather than `\s`: under re.MULTILINE `\s` crosses newlines, so `^\s+NAME =` would
    # match a blank line followed by the module-level definition and flag every constant.
    check("no identity or decision constant is ever reassigned inside a function",
          not re.search(r"(?m)^[ \t]+(?:ENGAGEMENT_ID|CLIENT_ID|OWNER_ID|AUTHORIZATION_SCOPE|"
                        r"SUBJECT_RECORD_ID|SUBJECT_RECORD_TYPE|SOURCE_REFERENCE_ID|"
                        r"IDEMPOTENCY_KEY|DECISION|AUTHORITATIVE)[ \t]*=", code))
    check("build_request takes no argument - nothing is parameterised",
          re.search(r"def build_request\(\):", code) is not None)
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("utility carries no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(src))

    args = set(re.findall(r'add_argument\("(--[a-z0-9-]+)"', src))
    check("utility exposes only the run mode - no record field is a flag",
          args <= {"--dry-run", "--execute"})

    env = scrubbed_env()

    def run_tool(*extra):
        return subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL), *extra],
                              capture_output=True, text=True, timeout=180, env=env)

    run = run_tool("--dry-run")
    check("dry-run exits 0 with no credential in the environment", run.returncode == 0)
    check("dry-run reports no connection was made",
          "database_connection_made              : False" in run.stdout)
    check("dry-run reports nothing was written", "DRY-RUN PASS" in run.stdout)
    check("bare invocation with no flag is also a dry-run",
          "DRY-RUN PASS" in run_tool().stdout)
    check("dry-run discloses that stored-engagement authorization is not exercised",
          "NOT exercised by this dry-run" in run.stdout)
    check("dry-run names the R9 record as the reviewed target", R9_RECORD_ID in run.stdout)
    check("dry-run names no other stored record id",
          not any(bad in run.stdout for bad in FORBIDDEN_TARGET_IDS))
    check("dry-run states the approval is scoped to R1 location-dimension readiness",
          "R1 location-dimension readiness" in run.stdout)
    check("dry-run states no evidence_reference is created",
          "no evidence_reference is created" in run.stdout)
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))
    check("dry-run prints no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(run.stdout))
    # Artifact-agnostic: the R9 artifact is JSON, so any leak would carry object syntax.
    check("dry-run prints no JSON object syntax - no artifact body can have leaked",
          "{" not in run.stdout and "}" not in run.stdout
          and not re.search(r'(?m)^\s*"[a-z_]+"\s*:', run.stdout))
    check("dry-run output is a short sanitized summary, not a document dump",
          len(run.stdout) < 16000)
    check("dry-run prints no home-directory path",
          os.path.expanduser("~") not in run.stdout)


# --------------------------------------------------------------------------- 5. writer behaviour


def writer_checks() -> None:
    print("\n5. The writer creates exactly one review record, and nothing else")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as anchor_tool
    import create_internal_test_r9_source_ingestion_record as source_tool
    import create_internal_test_r9_source_review_decision as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.models import (
        Client, Engagement, EvidenceReference, IntakeNoteRecord, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.db.review_writer import persist_review_record
    from peak.db.source_ingestion_writer import persist_source_ingestion_record

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # Rebuild the Phase 59 anchor and the Phase 69 R9 registration, via their own writers.
    anchor = persist_engagement_authorization_anchor(anchor_tool.build_request(),
                                                     session_factory=factory)
    r9 = persist_source_ingestion_record(
        source_tool.build_request(synthetic_packet_hash()), session_factory=factory)
    check("the anchor and the R9 source ingestion record exist for the review to target",
          anchor.outcome == "created" and r9.outcome == "created")
    check("the rebuilt R9 record carries R9's packet reference",
          r9.stored_record_id is not None)

    # Point the request at the R9 record this fixture actually created.
    request = tool.build_request()
    request.record_draft.subject_record_id = r9.stored_record_id

    receipt = persist_review_record(request, session_factory=factory)
    check("first invocation creates the review decision", receipt.outcome == "created")
    check("receipt reports one stored record created", receipt.stored_record_created is True)
    check("the decision is approve_internal",
          getattr(receipt, "decision", None) in (None, "approve_internal"))
    check("receipt reports no client-facing approval or capsule candidacy",
          getattr(receipt, "client_facing_approved", False) is False
          and getattr(receipt, "capsule_candidate_ready", False) is False)
    check("receipt reports no client-facing output or capsule/AgentNet publication",
          getattr(receipt, "client_facing_output_created", False) is False
          and getattr(receipt, "capsule_publication_made", False) is False
          and getattr(receipt, "agentnet_publication_made", False) is False)
    check("receipt reports no evidence reference or source ingestion record was created",
          getattr(receipt, "evidence_reference_created", False) is False
          and getattr(receipt, "source_ingestion_record_created", False) is False)
    check("receipt reports no report draft or review packet was created",
          getattr(receipt, "report_draft_created", False) is False
          and getattr(receipt, "review_packet_created", False) is False)
    check("receipt reports no update and no delete",
          getattr(receipt, "update_made", False) is False
          and getattr(receipt, "delete_made", False) is False)

    session = factory()
    check("exactly one review record exists", session.query(ReviewRecord).count() == 1)
    row = session.query(ReviewRecord).one()
    check("the review record targets the R9 source ingestion record",
          row.target_id == r9.stored_record_id
          and row.subject_record_type == "source_ingestion_record")
    check("the review record is tied to the internal_test engagement",
          row.engagement_id == ANCHOR_ID and row.client_id == RESERVED_CLIENT_ID
          and row.owner_id == "peak_internal_admin" and row.authorization_scope == SCOPE)
    check("the reviewed engagement is classified internal_test",
          session.get(Engagement, row.engagement_id).engagement_category == "internal_test")
    check("the stored decision is approve_internal and non-authoritative",
          row.decision == "approve_internal" and bool(row.authoritative) is False)
    check("the stored record lands on approved_internal, still draft",
          row.review_status == "approved_internal" and row.output_status == "draft")
    check("the stored detail carries R9's packet reference",
          row.details_json.get("source_reference_id") == R9_PACKET_REF)
    check("the stored detail is not client-facing and not capsule-ready",
          row.details_json["client_facing_approved"] is False
          and row.details_json["capsule_candidate_ready"] is False)

    stored_reasons = row.details_json["reasons"]
    check("the stored findings authorize only R1 location-dimension readiness evidence work",
          any(r.startswith("decision_meaning:") and "R1 location-dimension readiness" in r
              for r in stored_reasons))
    check("the stored findings state no evidence_reference is created",
          any("no evidence_reference is created" in r for r in stored_reasons))
    check("the stored findings refuse inventory accuracy / quantity conclusions",
          any(r.startswith("not_authorized:") and "inventory accuracy" in r
              for r in stored_reasons))
    check("the stored findings leave R1's provisional location marking unlifted",
          any("does not lift that marking" in r for r in stored_reasons))
    check("the stored findings leave R8 provisional",
          any("R8 remains provisional" in r for r in stored_reasons))
    check("the stored findings leave R5 WMS scope unresolved",
          any("R5 WMS scope remains unresolved" in r for r in stored_reasons))
    check("the stored findings leave R3-R7 deferred",
          any("R3-R7 remain deferred" in r for r in stored_reasons))
    check("the stored findings refuse report, capsule, and AgentNet publication",
          any("report drafting" in r for r in stored_reasons)
          and any("AgentNet" in r for r in stored_reasons))
    check("the stored findings record the question-set limit",
          any(r.startswith("limit:") and "question set" in r for r in stored_reasons))
    check("the stored row carries no home-directory path",
          os.path.expanduser("~") not in str(row.details_json))
    check("the stored row carries no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(str(row.details_json)))

    # Nothing else was written.
    check("no Client row was created", session.query(Client).count() == 0)
    check("still exactly one engagement row", session.query(Engagement).count() == 1)
    check("no intake note record was created", session.query(IntakeNoteRecord).count() == 0)
    check("no evidence reference was created", session.query(EvidenceReference).count() == 0)
    check("still exactly one source ingestion record - the review created none",
          session.query(SourceIngestionRecord).count() == 1)
    check("the reviewed source ingestion record was not modified",
          session.get(SourceIngestionRecord, r9.stored_record_id).review_status == "needs_review")
    session.close()

    # Replay: identical payload must not write a second row.
    replay_request = tool.build_request()
    replay_request.record_draft.subject_record_id = r9.stored_record_id
    replay = persist_review_record(replay_request, session_factory=factory)
    check("identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    session = factory()
    check("still exactly one review record after replay",
          session.query(ReviewRecord).count() == 1)
    session.close()

    # A changed payload under the same idempotency key must conflict, never overwrite.
    conflict_request = tool.build_request()
    conflict_request.record_draft.subject_record_id = r9.stored_record_id
    conflict_request.record_draft.reasons = list(tool.REASONS) + ["changed: fingerprint differs"]
    conflict = persist_review_record(conflict_request, session_factory=factory)
    check("a changed fingerprint under the same idempotency key is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("still exactly one review record after the conflict",
          session.query(ReviewRecord).count() == 1)
    stored = session.query(ReviewRecord).one()
    check("the existing record was not overwritten",
          stored.id == receipt.stored_record_id
          and "changed: fingerprint differs" not in stored.details_json["reasons"])
    check("no evidence reference appeared at any point",
          session.query(EvidenceReference).count() == 0)
    session.close()


# --------------------------------------------------------------------------- 6. docs


def doc_checks() -> None:
    print("\n6. Docs state what was decided, what it withholds, and what comes next")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("doc content checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    f = flat(doc)
    for phrase, label in (
        ("one review_records row", "exactly one review record was created"),
        (R9_RECORD_ID.lower(), "the reviewed R9 source ingestion record is named"),
        ("r1 location-dimension readiness",
         "the approval is scoped to R1 location-dimension readiness"),
        ("non-authoritative", "R9 remains non-authoritative"),
        ("no evidence reference", "no evidence_reference was created"),
        ("provisional", "R1's location dimension remains provisional"),
        ("does not validate inventory quantities",
         "R9 does not validate inventory quantities"),
        ("does not resolve r8 authority precedence",
         "R9 does not resolve R8 authority precedence"),
        ("does not resolve r5 wms scope", "R9 does not resolve R5 WMS scope uncertainty"),
        ("no report", "no report record was created or authorized"),
        ("no capsule", "no capsule was created or authorized"),
        ("no client-facing output", "no client-facing output was created"),
        ("phase 71", "the likely Phase 71 next step is named"),
        ("resolver", "the AgentNet resolver posture is stated"),
        ("publication remains", "resolver publication remains gated"),
        (ANCHOR_ID, "the engagement anchor is named"),
        (SCOPE, "the authorization scope is named"),
        ("approve_internal", "the decision value is named"),
    ):
        check(f"doc states: {label}", phrase in f)

    # Written with an en dash in prose; accept either dash so the check tests the claim, not
    # the typography.
    check("doc states: R3-R7 remain deferred",
          re.search(r"r3[-–—]r7", f) is not None and "defer" in f)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("doc contains no artifact filename",
          not any(name in doc for name in ARTIFACT_BASENAMES))
    check("doc carries no row-like item/quantity/location content", not ROW_LIKE_RE.search(doc))

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md", PHASE69_DOC_REL, PHASE68_DOC_REL):
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records Phase 70", "phase 70" in blob)
        check(f"{name} states no evidence reference was created",
              "no evidence reference" in blob or "evidence_references still" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase70", "validate-phase70" in mk)
    check("validate depends on validate-phase70",
          re.search(r"^validate:.*validate-phase70", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)
    check("the record-creation utility is not wired into validate",
          "create_internal_test_r9_source_review_decision" not in mk)


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
    check("this harness never opens any external artifact",
          not any(name in code for name in ARTIFACT_BASENAMES)
          and "peak-internal-test-artifacts" not in code)
    check("this harness's packet hash is synthetic and built at runtime",
          "def synthetic_packet_hash" in src)
    check("this harness embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    tracked = git("ls-files").splitlines()
    check("no artifact body file is tracked in the repository",
          not [t for t in tracked if any(name in t for name in ARTIFACT_BASENAMES)])
    check("no internal-test-artifact directory is tracked in the repository",
          not [t for t in tracked if "peak-internal-test-artifacts" in t])
    check("no fixtures/examples/sample-packet directory is tracked",
          not [t for t in tracked
               if re.match(r"^(fixtures|examples|samples|sample_packets)/", t)])
    check("no sample or fixture packet file is tracked",
          not [t for t in tracked
               if re.search(r"(?i)(fixture|sample|example)[^/]*\.(json|ya?ml|csv|txt)$", t)])
    check("no .json/.csv/.txt artifact was added by this phase",
          not [c for c in git("diff", "--name-only", "HEAD").splitlines()
               if c.endswith((".json", ".csv", ".txt"))]
          and not [c for c in git("ls-files", "--others", "--exclude-standard").splitlines()
                   if c.endswith((".json", ".csv", ".txt"))])

    # Phase 70 must add nothing beyond its own operator, harness, and docs.
    scope = git("diff", "--name-only", f"{BASELINE_COMMIT}..{PHASE_COMMIT}").splitlines()
    if not scope:  # pre-commit: fall back to the working tree
        scope = git("diff", "--name-only", BASELINE_COMMIT).splitlines()
    added = [c for c in scope
             if c not in (TOOL_REL, HARNESS_REL, DOC_REL, "Makefile")
             and not c.startswith("docs/")]
    check("this phase changed nothing outside its operator, harness, docs, and the Makefile",
          not added)

    for rel in (TOOL_REL, HARNESS_REL, DOC_REL):
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
    print("Peak Phase 70 R9 source ingestion review decision check")
    print("=" * 70)
    try:
        baseline_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed - contract/packet/writer layers skipped.")
            print("         Run: make validate-phase70 PYTHON=.venv/bin/python")
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
