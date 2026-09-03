#!/usr/bin/env python3
"""Phase 67 first internal test evidence reference check.

Phase 65 registered the R2 (SKU/item master) source ingestion record; Phase 66 approved it
internally for exactly one narrow next step. Phase 67 takes that step: **one** ``evidence_references``
row for the approved R2 source-ingestion chain, scoped to **item-master source availability and data
readiness only**. It supports no inventory accuracy conclusion, relies on no R1 location claim,
treats R8 as non-authoritative, leaves R3-R7 deferred, and authorizes no report drafting, capsule
candidacy, client-facing output, or AgentNet resolver publication.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite, and
the operator utility is exercised with every role variable scrubbed from the child environment so
its dry-run default is proven to open no connection.

**No artifact body lives in this repository and none is read here.** The external R2 artifact is
never opened by this harness, and the Phase 67 operator opens no artifact at all — its stored text
is sanitized structural counts and record ids, not artifact content.

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

BASELINE_COMMIT = "5c537d4"   # Add Phase 66 R2 source ingestion review decision

TOOL_REL = "tools/create_internal_test_r2_evidence_reference.py"
HARNESS_REL = "tests/validate_phase67_first_internal_test_evidence_reference.py"
DOC_REL = "docs/PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md"
PHASE66_DOC_REL = "docs/PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md"
PHASE65_DOC_REL = "docs/PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md"
WRITER_REL = "peak/db/evidence_writer.py"
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

#: The evidenced source — the Phase 65 R2 source ingestion record.
R2_RECORD_ID = "ing_884c94df03c34908"
R2_PACKET_REF = "pkt_internal_test_r2_sku_item_master_001"
#: The Phase 66 review that authorized this narrow evidence reference (a support reference).
SUPPORT_REVIEW_ID = "rev_bf7f18a13d8f461c"
#: Records the operator must never be able to retarget or rely on.
FORBIDDEN_TARGET_IDS = ("ing_a2abb497f471458e",   # R1
                        "ing_4fb70519cbf84401",   # R8
                        "intn_b8b86b8c196c4595",  # intake note
                        "rev_b82ff6f00790418f")   # intake review decision

#: Artifact bodies must never be committed. Their filenames must appear nowhere in this phase.
ARTIFACT_BASENAMES = ("r2_sku_item_master_export_v1.json",
                      "r1_current_inventory_sku_location_v1.json",
                      "r8_system_of_record_data_export_map_v1.json")

#: Row-like content that must never appear in this phase's own files or stored text.
ROW_LIKE_RE = re.compile(r"(?i)\b(sku|item)[-_ ]?(?:id|code|no|number)?\s*[:=]\s*[\"']?[A-Z0-9]{3,}"
                         r"|\bqty\s*[:=]\s*\d|\bquantity_on_hand\s*[:=]\s*\d"
                         r"|\bbin\s*[:=]\s*[\"']?[A-Z0-9]{2,}")

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!internal-test-artifact)(?!peak-record)[\w.\-]+:[^\s@'\"]+@")
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


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def phase_never_committed(rel: str) -> bool:
    """True while ``rel`` has no commit yet — i.e. this phase's own work is still unstaged.

    The whole-tree ``peak/`` freeze below is an *authoring-time* claim about **this** phase. Keyed
    on "does the path have a pending diff", it judged every later phase's uncommitted work against
    this phase's allowlist: Phase 96 legitimately owns the Phase 36 planning-boundary change, and
    the ungated freeze failed it. Absence of any commit for this harness is the signal that
    actually means "this phase has not landed yet". The substantive invariants this harness cares
    about — no model, no writer, no allowlist pair — stay unconditional above and below.
    See docs/PHASE91_DRIFT_TEST_SPRAWL_PARALLEL_WORKFLOW_REVIEW.md, recommendation 3.
    """
    return not git("log", "-1", "--format=%H", "--", rel).strip()


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)).lower()


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def tmpdir() -> str:
    tmp = tempfile.mkdtemp(prefix="peak_phase67_")
    _tmpdirs.append(tmp)
    return tmp


def temp_sqlite_url() -> str:
    return "sqlite:///" + os.path.join(tmpdir(), "phase67.db")


def synthetic_packet_hash(salt: str = "a") -> str:
    """A throwaway hash built at runtime. No real artifact is opened by this harness."""
    return hashlib.sha256(("phase67-synthetic-fixture-" + salt).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, nothing added")
    # Ancestry, not recency. This asserted membership in a bounded `git log ... -40` window,
    # which is a *sliding window*, not a history check: the baseline falls out of range as later
    # phases land, failing on commits whose content has nothing to do with this phase. The
    # invariant meant here is that the baseline is still reachable from HEAD, which
    # `merge-base --is-ancestor` states directly and which never expires. Widening the window
    # would only move the expiry date.
    is_ancestor = git_succeeds("merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
    check(f"baseline commit {BASELINE_COMMIT} is in history", is_ancestor)
    if not is_ancestor:
        print("        reason: phase67_baseline_commit_not_ancestor")

    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later - Phase 67 adds no migration",
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
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])
    if phase_never_committed(HARNESS_REL):
        check("no file under peak/ was modified by this phase at all",
              not git("diff", "--name-only", "HEAD", "--", "peak"))
    check("the allowlist module was not modified by this phase - no allowlist pair added",
          not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))

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
    check("resolver_capsule_records remains prohibited - no publication path exists",
          is_prohibited_table("resolver_capsule_records"))
    check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx"))


# --------------------------------------------------------------------------- 2. writer contract


def writer_contract_checks() -> None:
    print("\n2. The existing evidence writer honestly represents a source-availability claim")
    from peak.db.writer_contracts import EVIDENCE_TARGET_ACTION, EVIDENCE_TARGET_TABLE
    from peak.evidence.persistence_contracts import EvidencePersistenceDraft
    from peak.persistence.allowlist import is_allowed_action, is_allowed_table

    check("the selected writer is the existing evidence_references writer",
          EVIDENCE_TARGET_TABLE == "evidence_references")
    check("evidence_references is an allowed controlled-write table",
          is_allowed_table(EVIDENCE_TARGET_TABLE))
    check("the evidence action is an allowed controlled-write action",
          is_allowed_action(EVIDENCE_TARGET_ACTION))

    fields = set(EvidencePersistenceDraft.__dataclass_fields__)
    check("the draft carries a source reference for the registered packet",
          "source_reference_id" in fields)
    check("the draft carries a source locator distinct from the packet reference",
          "source_location" in fields)
    check("the draft carries the evidence and source classification fields",
          {"evidence_type", "source_type", "confidence_level"} <= fields)
    check("the draft carries free descriptive text for the claim and its limits",
          {"normalized_title", "normalized_summary", "observed_condition"} <= fields)
    check("the draft carries the review-gate posture fields",
          {"output_status", "review_status", "lifecycle_status"} <= fields)
    check("the draft carries the non-final posture flags",
          {"authoritative", "client_facing_approved", "capsule_candidate_ready"} <= fields)

    writer_src = read(WRITER_REL)
    code = code_only(writer_src)
    check("the evidence writer refuses an authoritative draft",
          "prohibited_authoritative" in writer_src)
    check("the evidence writer refuses a client-facing or capsule-ready draft",
          "prohibited_client_facing" in writer_src
          and "prohibited_capsule_candidate" in writer_src)
    check("the evidence writer server-stamps needs_review / draft, it does not trust the caller",
          'review_status="needs_review"' in writer_src and 'output_status="draft"' in writer_src)
    check("the evidence writer is create-only - one insert, no update, merge, or delete",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))
    check("the evidence writer issues no raw SQL",
          not re.search(r"session\.execute\(|\btext\(|cursor\.", code))
    check("the evidence writer loads the stored Engagement and compares stored scope",
          "Engagement" in code and "stored_scope_mismatch" in writer_src)
    check("the evidence writer requires the authorization anchor to be an engagement",
          "SUPPORTED_SUBJECT_TYPES" in code)
    check("the evidence writer's idempotency boundary includes owner/client/engagement",
          all(k in code for k in ("owner_id", "client_id", "engagement_id", "idempotency_key")))

    # The table itself carries no authoritative column, so the claim is structurally impossible.
    from peak.db.models import EvidenceReference
    cols = set(EvidenceReference.__table__.columns.keys())
    check("evidence_references has no authoritative column - the claim cannot be made at all",
          "authoritative" not in cols)
    check("evidence_references carries the governance columns the review gate needs",
          {"review_status", "output_status", "lifecycle_status", "authorization_scope"} <= cols)


# --------------------------------------------------------------------------- 3. the packet


def packet_checks() -> None:
    print("\n3. The one evidence packet is scoped to R2 source availability / data readiness")
    import create_internal_test_r2_evidence_reference as tool

    check(f"packet is anchored to engagement {ANCHOR_ID} / client {RESERVED_CLIENT_ID}",
          tool.ENGAGEMENT_ID == ANCHOR_ID and tool.CLIENT_ID == RESERVED_CLIENT_ID)
    check("owner is the internal admin", tool.OWNER_ID == "peak_internal_admin")
    check(f"scope is {SCOPE}", tool.AUTHORIZATION_SCOPE == SCOPE)
    check("the evidenced source is the R2 source ingestion record",
          tool.SOURCE_INGESTION_RECORD_ID == R2_RECORD_ID)
    check("the registered packet reference is R2's",
          tool.SOURCE_REFERENCE_ID == R2_PACKET_REF)
    check("the source locator is a logical in-Peak pointer at the R2 record, not a file path",
          tool.SOURCE_LOCATION.startswith("peak-record://source_ingestion_records/")
          and tool.SOURCE_LOCATION.endswith(R2_RECORD_ID)
          and not tool.SOURCE_LOCATION.startswith("/"))
    check("the supporting reference is the Phase 66 R2 review decision",
          tool.SUPPORTING_REVIEW_RECORD_ID == SUPPORT_REVIEW_ID)
    check("evidence_type and source_type are schema-valid and claim only a document",
          tool.EVIDENCE_TYPE == "document" and tool.SOURCE_TYPE == "document")
    check("no system_export is claimed - the artifact carries no rows",
          "system_export" not in (tool.EVIDENCE_TYPE, tool.SOURCE_TYPE))
    check("reliability is the cautious, non-authoritative value",
          tool.CONFIDENCE_LEVEL == "low")
    check("the idempotency key is Phase 67 scoped",
          tool.IDEMPOTENCY_KEY.startswith("phase67_"))

    text = " ".join((tool.NORMALIZED_TITLE, tool.OBSERVED_CONDITION, tool.NORMALIZED_SUMMARY))
    low = text.lower()
    check("the stored text names the evidence scope as item-master source availability",
          "item-master source availability" in low)
    check("the stored text names data readiness as the evidence scope",
          "data readiness" in low)
    check("the stored text names the evidenced source ingestion record",
          R2_RECORD_ID in text and R2_PACKET_REF in text)
    check("the stored text names the supporting review record",
          SUPPORT_REVIEW_ID in text)
    check("the stored text records the sanitized structural finding",
          "10 described fields" in low or "10 item-master fields" in low)
    check("the stored text records the unconfirmed unit-of-measure posture",
          "unit-of-measure posture is unconfirmed" in low)
    check("the stored text records the unconfirmed item-status posture",
          "item-status posture is unconfirmed" in low)
    check("the stored text records the duplicate/normalization risks",
          "duplicate and normalization risks" in low)

    check("the evidence does NOT support an inventory accuracy conclusion",
          "not support an inventory accuracy conclusion" in low)
    check("the evidence does NOT rely on R1 location claims",
          "not rely on r1 location claims" in low and "provisional" in low)
    check("the evidence does NOT treat R8 as authoritative",
          "not treat r8 as authoritative" in low and "needs_review" in low)
    check("R3-R7 remain deferred", "r3-r7 remain deferred" in low)
    check("the evidence authorizes no report drafting or capsule candidacy",
          "report drafting" in low and "capsule candidacy" in low)
    check("the evidence authorizes no client-facing output",
          "client-facing output" in low)
    check("the evidence authorizes no AgentNet resolver publication",
          "agentnet" in low and "resolver publication" in low)
    check("the stored text states the internal-only, no-real-client-data posture",
          "no real client data" in low and "not client-facing" in low
          and "not authoritative" in low)
    check("the stored text carries no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(text))
    check("the stored text carries no home-directory path",
          os.path.expanduser("~") not in text)

    request = tool.build_request()
    draft = request.record_draft
    check("the draft points at R2's packet reference and locator",
          draft.source_reference_id == R2_PACKET_REF
          and draft.source_location.endswith(R2_RECORD_ID))
    check("the draft leaves server-controlled fields unset",
          draft.evidence_record_id is None and draft.created_at is None)
    check("the draft is review-gated: draft / needs_review / active",
          draft.output_status == "draft" and draft.review_status == "needs_review"
          and draft.lifecycle_status == "active")
    check("the draft is non-authoritative, non-client-facing, not capsule-ready",
          draft.authoritative is False and draft.client_facing_approved is False
          and draft.capsule_candidate_ready is False)
    check("the authorization anchor is the engagement, never the evidenced source record",
          request.subject.subject_record_type == "engagement"
          and request.subject.subject_record_id == ANCHOR_ID)
    check("the request targets evidence_references / create_draft",
          request.target_table == "evidence_references"
          and request.requested_action == "create_draft")

    from peak.db.evidence_writer import _pre_db_validate
    denial, validated = _pre_db_validate(request, None)
    check("packet passes the writer's pre-DB governance gate (no connection opened)",
          denial is None and validated is not None)


# --------------------------------------------------------------------------- 4. operator utility


def tool_checks() -> None:
    print("\n4. The operator utility writes one evidence reference and can target nothing else")
    src = read(TOOL_REL)
    code = code_only(src)

    check("utility defaults to dry-run - --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check("utility invokes only the existing controlled evidence writer",
          "persist_evidence_reference" in code
          and not re.search(r"persist_(?!evidence_reference)\w+", code))
    check("utility creates no Client, Engagement, intake, source, review, report, or capsule "
          "record",
          not re.search(r"(?i)\bClient\(|\bEngagement\(|IntakeNoteDraft|SourceIngestionDraft|"
                        r"ReviewRecordDraft|persist_intake|persist_source|persist_review|"
                        r"persist_agent_run|persist_internal_|persist_engagement|publish", code))
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
    check("utility opens no file at all - it reads no artifact body",
          not re.search(r"\bopen\s*\(", code))
    check("utility computes no artifact hash - the reviewed body is never touched",
          "hashlib" not in code)
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("utility contains no artifact filename",
          not any(name in src for name in ARTIFACT_BASENAMES))
    check("utility carries no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(src))

    # Retargeting: the evidenced source is a constant, and no other record id is assignable.
    check("the evidenced source is a module constant, not derived from a flag",
          re.search(r"(?m)^SOURCE_INGESTION_RECORD_ID\s*=\s*[\"']" + R2_RECORD_ID + r"[\"']", src)
          is not None)
    check("utility names no other stored record id anywhere - it cannot retarget R1, R8, the "
          "intake note, or the intake review",
          not any(rid in src for rid in FORBIDDEN_TARGET_IDS))
    check("utility assigns the packet reference only from its own constant",
          re.search(r"source_reference_id\s*=\s*SOURCE_REFERENCE_ID", code) is not None
          and not re.search(r"source_reference_id\s*=\s*(?!SOURCE_REFERENCE_ID)[a-z_]+\.", code))
    check("utility assigns the source locator only from its own constant",
          re.search(r"source_location\s*=\s*SOURCE_LOCATION", code) is not None)
    check("utility builds the locator only from the R2 constant",
          re.search(r"(?m)^SOURCE_LOCATION\s*=\s*[^\n]*\+\s*SOURCE_INGESTION_RECORD_ID", src)
          is not None)

    args = set(re.findall(r'add_argument\("(--[a-z0-9-]+)"', src))
    check("utility exposes only the run mode - no record field or target is a flag",
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
    check("dry-run prints the evidenced R2 record and packet reference",
          R2_RECORD_ID in run.stdout and R2_PACKET_REF in run.stdout)
    check("dry-run names no other stored record id than R2 and its Phase 66 review",
          not any(rid in run.stdout for rid in FORBIDDEN_TARGET_IDS))
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))
    check("dry-run discloses that stored-engagement authorization is not exercised",
          "NOT exercised by this dry-run" in run.stdout)
    check("dry-run prints no JSON object syntax - no artifact body can have leaked",
          "{" not in run.stdout and "}" not in run.stdout
          and not re.search(r'(?m)^\s*"[a-z_]+"\s*:', run.stdout))
    check("dry-run prints the stored text only as a character count, never its body",
          re.search(r"normalized_summary\s*:\s*\d+ chars, sanitized", run.stdout) is not None)
    check("dry-run prints no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(run.stdout))
    check("dry-run output is a short sanitized summary, not a document dump",
          len(run.stdout) < 12000)
    check("dry-run prints no home-directory path", os.path.expanduser("~") not in run.stdout)


# --------------------------------------------------------------------------- 5. writer behaviour


def writer_checks() -> None:
    print("\n5. The writer creates exactly one evidence reference, and nothing else")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as anchor_tool
    import create_internal_test_r1_r2_source_ingestion_records as source_tool
    import create_internal_test_r2_evidence_reference as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.evidence_writer import persist_evidence_reference
    from peak.db.models import (
        Client, Engagement, EvidenceReference, IntakeNoteRecord, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.db.source_ingestion_writer import persist_source_ingestion_record

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # Rebuild the Phase 59 anchor and the Phase 65 R2 registration, via their own writers.
    anchor = persist_engagement_authorization_anchor(anchor_tool.build_request(),
                                                     session_factory=factory)
    r2_packet = source_tool.PACKETS[0]
    check("the R2 packet is the first Phase 65 packet", r2_packet["key"] == "R2")
    r2 = persist_source_ingestion_record(
        source_tool.build_request(r2_packet, synthetic_packet_hash()), session_factory=factory)
    check("the anchor and the R2 source ingestion record exist for the evidence to reference",
          anchor.outcome == "created" and r2.outcome == "created")

    receipt = persist_evidence_reference(tool.build_request(), session_factory=factory)
    check("first invocation creates the evidence reference", receipt.outcome == "created")
    check("receipt reports one stored record created", receipt.stored_record_created is True)
    check("receipt reports the review-gated posture",
          receipt.review_status == "needs_review" and receipt.output_status == "draft")
    check("receipt targets evidence_references / create_draft",
          receipt.target_table == "evidence_references"
          and receipt.target_action == "create_draft")

    session = factory()
    check("exactly one evidence_references row exists",
          session.query(EvidenceReference).count() == 1)
    row = session.query(EvidenceReference).one()
    check("the evidence reference is tied to the internal_test engagement",
          row.engagement_id == ANCHOR_ID and row.client_id == RESERVED_CLIENT_ID
          and row.owner_id == "peak_internal_admin" and row.authorization_scope == SCOPE)
    check("the evidenced engagement is classified internal_test",
          session.get(Engagement, row.engagement_id).engagement_category == "internal_test")
    check("the evidence reference is review-gated and non-final",
          row.review_status == "needs_review" and row.output_status == "draft"
          and row.lifecycle_status == "active")
    check("the stored evidence claims only a document, never a system export",
          row.evidence_type == "document" and row.source_type == "document")
    check("the stored reliability is the cautious value", row.reliability == "low")
    check("the stored evidence_status is the collected default, never verified",
          row.evidence_status == "collected")
    check("no sensitive data is flagged or stored", bool(row.sensitive_data_flag) is False)
    check("the stored id follows the evid_ convention", row.id.startswith("evid_"))

    # The tie to the R2 source ingestion record, checked against the row the fixture created.
    stored_r2 = session.query(SourceIngestionRecord).one()
    check("the stored evidence points at the same packet reference the R2 registration carries",
          row.details_json.get("source_reference_id") == R2_PACKET_REF
          and stored_r2.source_reference_id == R2_PACKET_REF)
    check("the stored evidence carries the logical locator for the R2 source ingestion record",
          row.details_json.get("source_location", "").endswith(R2_RECORD_ID))
    check("the stored evidence records its Phase 67 provenance",
          row.details_json.get("source_phase") == "phase67")
    check("the stored evidence records the coarse areas, not a location identifier",
          row.details_json.get("operational_area") == "back_office"
          and row.details_json.get("inventory_process_area") == "inventory_control")

    stored_text = " ".join(str(v) for v in (row.summary,
                                            row.details_json.get("normalized_title"),
                                            row.details_json.get("observed_condition")))
    low = stored_text.lower()
    check("the stored row states the evidence scope in its own text",
          "item-master source availability" in low and "data readiness" in low)
    check("the stored row names the evidenced source and the supporting review",
          R2_RECORD_ID in stored_text and SUPPORT_REVIEW_ID in stored_text)
    check("the stored row refuses an inventory accuracy conclusion in its own text",
          "not support an inventory accuracy conclusion" in low)
    check("the stored row leaves R1 location claims and R8 authority out of scope",
          "not rely on r1 location claims" in low and "not treat r8 as authoritative" in low)
    check("the stored row leaves R3-R7 deferred", "r3-r7 remain deferred" in low)
    check("the stored row refuses report, capsule, client-facing, and AgentNet publication",
          "report drafting" in low and "capsule candidacy" in low
          and "client-facing output" in low and "agentnet" in low)
    check("the stored row carries no home-directory path",
          os.path.expanduser("~") not in str(row.details_json) + str(row.summary))
    check("the stored row carries no row-like item/quantity/location content",
          not ROW_LIKE_RE.search(stored_text))

    # Nothing else was written.
    check("no Client row was created", session.query(Client).count() == 0)
    check("still exactly one engagement row", session.query(Engagement).count() == 1)
    check("no intake note record was created", session.query(IntakeNoteRecord).count() == 0)
    check("no review record was created", session.query(ReviewRecord).count() == 0)
    check("still exactly one source ingestion record - the evidence write created none",
          session.query(SourceIngestionRecord).count() == 1)
    session.close()

    # Replay: identical payload must not write a second row.
    replay = persist_evidence_reference(tool.build_request(), session_factory=factory)
    check("identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    check("replay returns the same stored record, unmodified",
          replay.stored_record_id == receipt.stored_record_id
          and replay.existing_record_returned is True)
    session = factory()
    check("still exactly one evidence reference after replay",
          session.query(EvidenceReference).count() == 1)
    session.close()

    # A changed payload under the same idempotency key must conflict, never overwrite.
    conflict_request = tool.build_request()
    conflict_request.record_draft.normalized_summary = (
        tool.NORMALIZED_SUMMARY + " changed: fingerprint differs"
    )
    conflict = persist_evidence_reference(conflict_request, session_factory=factory)
    check("a changed fingerprint under the same idempotency key is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("still exactly one evidence reference after the conflict",
          session.query(EvidenceReference).count() == 1)
    stored = session.query(EvidenceReference).one()
    check("the existing record was not overwritten",
          stored.id == receipt.stored_record_id
          and "changed: fingerprint differs" not in (stored.summary or ""))
    session.close()


# --------------------------------------------------------------------------- 6. docs


def doc_checks() -> None:
    print("\n6. Docs state what was evidenced, what it claims, and what stays shut")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("doc content checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    f = flat(doc)
    for phrase, label in (
        ("one evidence_reference", "exactly one evidence_reference is described"),
        ("r2", "the R2 source ingestion record is the evidenced source"),
        ("source ingestion", "the evidenced source is a source ingestion record"),
        ("item-master source availability", "the evidence scope is named"),
        ("data readiness", "data readiness is named as the evidence scope"),
        ("inventory accuracy", "inventory accuracy conclusions are addressed"),
        ("needs_review", "R8 remains needs_review"),
        ("provisional", "R1's location dimension remains provisional"),
        ("no report", "no report record was created"),
        ("no capsule", "no capsule was created"),
        ("no client-facing output", "no client-facing output was created"),
        ("resolver", "the AgentNet resolver posture is stated"),
        ("publication remains unauthorized", "resolver publication remains unauthorized"),
        (ANCHOR_ID, "the engagement anchor is named"),
        (SCOPE, "the authorization scope is named"),
        (R2_RECORD_ID, "the evidenced record id is named"),
        (SUPPORT_REVIEW_ID, "the supporting Phase 66 review is named"),
    ):
        check(f"doc states: {label}", phrase in f)

    check("doc states: R3-R7 remain deferred",
          re.search(r"r3[-–—]r7", f) is not None and "defer" in f)
    check("doc states: no inventory accuracy conclusion was made",
          "no inventory accuracy conclusion" in f)
    check("doc states: no AgentNet publication was created",
          "no agentnet" in f and "publication" in f)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("doc contains no artifact filename",
          not any(name in doc for name in ARTIFACT_BASENAMES))
    check("doc carries no row-like item/quantity/location content", not ROW_LIKE_RE.search(doc))

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md", PHASE66_DOC_REL, PHASE65_DOC_REL):
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records Phase 67", "phase 67" in blob)
        check(f"{name} states the evidence scope is source availability / data readiness",
              "item-master source availability" in blob and "data readiness" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase67", "validate-phase67" in mk)
    check("validate depends on validate-phase67",
          re.search(r"^validate:.*validate-phase67", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)
    check("the record-creation utility is not wired into validate",
          "create_internal_test_r2_evidence_reference" not in mk)


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
    print("Peak Phase 67 first internal test evidence reference check")
    print("=" * 70)
    try:
        baseline_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed - contract/packet/writer layers skipped.")
            print("         Run: make validate-phase67 PYTHON=.venv/bin/python")
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
