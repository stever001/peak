#!/usr/bin/env python3
"""Phase 72 R10 measured location model answer set source ingestion check.

R9 defines the location question set; Phase 71 fixed a fifteen-item checklist of measured answers
required before R1 can support a location-dimension `evidence_reference`. Phase 72 collects **R10**,
the measured answer set, as **exactly one** metadata-only source ingestion record through the
unchanged Phase 24 writer.

Collection is not review and not validation. This harness therefore checks not only that one row is
written correctly, but that the phase withholds everything it must withhold: no evidence reference,
no review record, no report, no capsule, no publication, no lifting of R1's provisional marking, and
no inventory-quantity claim.

**It also checks the property that makes an answer set trustworthy: that the unfavourable answers
are still in it.** An answer set which quietly dropped the questions that came back negative would
look like readiness while establishing none, so the checks below assert that all fifteen checklist
items are present and that negative, unknown, and blocked states are actually recorded. Those
assertions are made against the *operator's own provenance notes* — never by opening the artifact,
which stays outside the repository.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite, and
the operator utility is exercised with every role variable scrubbed from the child environment so
its dry-run default is proven to open no connection.

**No artifact body lives in this repository and none is read here.** The external artifact is never
opened by this harness; the writer fixture uses synthetic hashes built at runtime. Only metadata - a
packet reference, schema name/version, source type, a *logical* location reference, and a hash - may
ever reach the database.

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

BASELINE_COMMIT = "fb1ffdb"   # Fix Phase 71 harness to diff the baseline commit, not HEAD

TOOL_REL = "tools/create_internal_test_r10_source_ingestion_record.py"
PHASE63_TOOL_REL = "tools/create_internal_test_source_ingestion_record.py"
PHASE65_TOOL_REL = "tools/create_internal_test_r1_r2_source_ingestion_records.py"
PHASE69_TOOL_REL = "tools/create_internal_test_r9_source_ingestion_record.py"

#: Prior-phase *harnesses* Phase 72 also had to touch, and why. Each scoped its "this phase changed
#: nothing outside" check to the working tree, which is only correct at a commit boundary: once
#: Phase 72 had uncommitted files, all three flagged Phase 72's work as their own. They are pinned
#: to their own commit ranges instead. These are validation files only - no production operator,
#: writer, model, migration, or allowlist was touched, and that is asserted separately below.
PRIOR_HARNESS_FIXES = (
    "tests/validate_phase69_r9_location_bin_model_source_ingestion.py",
    "tests/validate_phase70_r9_source_ingestion_review_decision.py",
    "tests/validate_phase71_r1_r9_evidence_readiness_plan.py",
)
HARNESS_REL = "tests/validate_phase72_r10_location_model_answer_set_source_ingestion.py"
DOC_REL = "docs/PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md"
PLAN_REL = "docs/PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md"
PHASE70_DOC_REL = "docs/PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md"
PHASE69_DOC_REL = "docs/PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md"
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

#: The writer's own forbidden draft attributes - none may appear on the operator draft.
FORBIDDEN_DRAFT_ATTRS = ("packet_payload", "raw_packet_content", "raw_content", "payload")

#: The artifact body must never be committed. Its filename must appear nowhere in the repo.
ARTIFACT_BASENAMES = ("r10_location_model_answer_set_v1.json",)

#: Identity of the records Phase 72 must NOT be able to re-express. A flag that could reach any of
#: these would mean the tool is not the fixed single-packet utility it claims to be.
OTHER_PACKET_MARKERS = ("pkt_internal_test_r1_inventory_sku_location_001",
                        "pkt_internal_test_r2_sku_item_master_001",
                        "pkt_internal_test_r9_location_bin_model_001",
                        "phase65_internal_test_source_ingestion_r1_001",
                        "phase65_internal_test_source_ingestion_r2_001",
                        "phase69_internal_test_source_ingestion_r9_001")

#: The nine answer states the R10 answer set may use.
ANSWER_STATES = ("answered_yes", "answered_no", "partial", "unknown", "not_present",
                 "not_measured", "blocked_by_r8", "blocked_by_r5", "requires_follow_up")

#: States that represent an unfavourable or unresolved answer. At least one must be recorded, or
#: the answer set is not credible as a measurement.
UNFAVOURABLE_STATES = ("answered_no", "unknown", "not_measured", "blocked_by_r8", "blocked_by_r5")

#: Row-like values that must never appear: item/SKU values, quantities, and location/bin/aisle/
#: rack/warehouse/site *values*. Schema field names such as ``location_identifier`` are not values.
ROW_LIKE_RE = re.compile(r"(?i)\b(sku|item)[-_ ]?(?:id|code|no|number)?\s*[:=]\s*[\"\']?[A-Z0-9]{3,}"
                         r"|\bqty\s*[:=]\s*\d|\bquantity_on_hand\s*[:=]\s*\d"
                         r"|\b(?:bin|aisle|rack|bay|warehouse|site)\s*[:=]\s*[\"\']?[A-Z0-9]{2,}")

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


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def flat(text: str) -> str:
    """Prose flattened for phrase checks: blockquotes, code spans, and bold/italic asterisks
    removed, so a check tests the claim rather than the markdown formatting. Only ``*`` is
    stripped - ``_`` is part of identifiers such as ``evidence_reference``."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    stripped = stripped.replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", stripped).lower()


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def tmpdir() -> str:
    tmp = tempfile.mkdtemp(prefix="peak_phase72_")
    _tmpdirs.append(tmp)
    return tmp


def temp_sqlite_url() -> str:
    return "sqlite:///" + os.path.join(tmpdir(), "phase72.db")


def synthetic_packet_hash(salt: str) -> str:
    """A throwaway hash built at runtime. The real artifact is never opened by this harness."""
    return hashlib.sha256(("phase72-synthetic-fixture-" + salt).encode("utf-8")).hexdigest()


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
        print("        reason: phase72_baseline_commit_not_ancestor")

    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later - Phase 72 adds no migration",
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
    check("the selected writer is the existing source ingestion writer",
          "source_ingestion_writer.py" in writers)
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])
    check("no file under peak/ was modified by this phase at all",
          not git("diff", "--name-only", "HEAD", "--", "peak"))
    check("the allowlist module was not modified by this phase - no allowlist pair added",
          not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))
    for rel in (PHASE63_TOOL_REL, PHASE65_TOOL_REL, PHASE69_TOOL_REL):
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
    check("the writer is create-only - one insert, no update, merge, or delete",
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


# --------------------------------------------------------------------------- 3. the R9 packet


def packet_checks() -> None:
    print("\n3. One R10 packet: an answer set that keeps its unfavourable answers")
    import create_internal_test_r10_source_ingestion_record as tool

    check(f"the packet is anchored to engagement {ANCHOR_ID} / client {RESERVED_CLIENT_ID}",
          tool.ENGAGEMENT_ID == ANCHOR_ID and tool.CLIENT_ID == RESERVED_CLIENT_ID)
    check("owner is the internal admin", tool.OWNER_ID == "peak_internal_admin")
    check(f"scope is {SCOPE}", tool.AUTHORIZATION_SCOPE == SCOPE)
    check("the approved artifact directory lives outside the repository",
          not os.path.realpath(tool.APPROVED_ARTIFACT_DIR).startswith(
              os.path.realpath(REPO_ROOT) + os.sep))
    check("the idempotency key is Phase 72 scoped and names R10",
          tool.IDEMPOTENCY_KEY == "phase72_internal_test_source_ingestion_r10_001")
    check("the packet reference id names R10 and the location model answer set",
          tool.PACKET_REFERENCE_ID == "pkt_internal_test_r10_location_model_answer_set_001")
    check("the approved artifact filename is the R10 answer set",
          tool.ARTIFACT_NAME == ARTIFACT_BASENAMES[0])
    check("the stored location reference is logical, not a filesystem path",
          tool.PACKET_LOCATION_REFERENCE
          == "internal-test-artifact://phase72/r10-location-model-answer-set-v1"
          and not tool.PACKET_LOCATION_REFERENCE.startswith("/")
          and "\\" not in tool.PACKET_LOCATION_REFERENCE
          and os.path.expanduser("~") not in tool.PACKET_LOCATION_REFERENCE)
    check("packet schema and source type match the internal-test convention",
          tool.PACKET_SCHEMA_NAME == "engagement_packet"
          and tool.PACKET_SCHEMA_VERSION == "v0"
          and tool.PACKET_SOURCE_TYPE == "internal_test_export")

    reasons = list(tool.REASONS)
    joined = "\n".join(reasons)

    check("provenance notes name R10 as the measured location model answer set",
          any(r.startswith("source_ingestion:") and "measured location model answer set" in r
              for r in reasons))
    check("provenance notes record that R10 responds to the R9 question set",
          any(r.startswith("responds_to:") and "question set" in r for r in reasons))
    check("provenance notes cite the Phase 71 readiness plan",
          any("PHASE71_R1_R9_EVIDENCE_READINESS_PLAN" in r for r in reasons))
    check("provenance notes state R9 defines the questions and R10 supplies the answers",
          any("R9 defines the questions and R10 supplies the measured answers" in r
              for r in reasons))

    # --- the answer set must be complete and must keep its unfavourable answers
    check("provenance notes state all 15 Phase 71 checklist items are answered",
          any(r.startswith("structure:") and "15" in r and "checklist" in r for r in reasons))
    check("provenance notes state no checklist item was dropped, merged, or softened",
          any("none was dropped, merged or softened" in r for r in reasons))
    check("provenance notes enumerate the answer-state vocabulary used",
          any(r.startswith("structure:") and "answer states used are" in r for r in reasons))
    # Every state the notes enumerate must come from the approved vocabulary — an invented
    # state would let an unfavourable answer be relabelled into something that reads as settled.
    enumerated = [r for r in reasons if "answer states used are" in r]
    check("the answer-state vocabulary is enumerated exactly once", len(enumerated) == 1)
    declared_states = set(re.findall(r"\b(?:answered_\w+|partial|unknown|not_present|"
                                     r"not_measured|blocked_by_\w+|requires_follow_up)\b",
                                     enumerated[0] if enumerated else ""))
    check("every enumerated answer state is in the approved vocabulary",
          bool(declared_states) and declared_states <= set(ANSWER_STATES))
    check("the enumerated states include at least one unfavourable state",
          bool(declared_states & set(UNFAVOURABLE_STATES)))
    check("provenance notes record that negative/unknown/blocked answers were retained",
          any(r.startswith("negative_answers_retained:") and "rather than omitted" in r
              for r in reasons))
    check("provenance notes record at least one unfavourable answer state",
          any(st in joined for st in UNFAVOURABLE_STATES))
    check("provenance notes state the measurement basis honestly - no live system was measured",
          any(r.startswith("measurement_basis:") and "no live ERP, WMS, production or client "
              "system exists" in r for r in reasons))
    check("provenance notes carry the headline finding that R1 is not currently readable",
          any(r.startswith("headline_finding:") and "not currently readable" in r
              for r in reasons))
    check("provenance notes state R10 does not make R1 readable",
          any(r.startswith("headline_finding:") and "does not make R1 readable" in r
              for r in reasons))

    # --- the withholdings
    check("provenance notes state R10 does not validate inventory quantities",
          any(r.startswith("does_not_validate:")
              and "does not validate any inventory quantity" in r for r in reasons))
    check("provenance notes state R10 creates no inventory accuracy conclusion",
          any(r.startswith("does_not_validate:")
              and "does not create an inventory accuracy conclusion" in r for r in reasons))
    check("provenance notes state R10 does not lift R1's provisional location marking",
          any(r.startswith("provisional:") and "does not lift R1's provisional location marking" in r
              for r in reasons))
    check("provenance notes state R10 does not make R1 evidence-ready by itself",
          any(r.startswith("provisional:") and "evidence-ready by itself" in r for r in reasons))
    check("provenance notes state R10 does not confirm R8 authority precedence",
          any(r.startswith("unconfirmed:") and "does not confirm R8 authority precedence" in r
              for r in reasons))
    check("provenance notes state R10 does not resolve R5 WMS scope",
          any(r.startswith("unconfirmed:") and "does not resolve R5 WMS scope" in r
              for r in reasons))
    check("provenance notes state R10 must be reviewed before evidence use",
          any(r.startswith("review_required:") and "evidence_reference" in r for r in reasons))
    check("provenance notes withhold evidence/report/capsule/publication authority",
          any(r.startswith("not_authorized:") and "publication" in r for r in reasons))
    check("provenance notes name the R10 review as the next separately approved step",
          any(r.startswith("next_step:") and "separately approved phase" in r for r in reasons))
    check("provenance notes state the artifact carries no location identifiers or quantities",
          any(r.startswith("scope_note:") and "no location identifiers" in r
              and "quantities" in r for r in reasons))
    check("provenance notes state the internal-only, no-real-client-data posture",
          any("no real client data" in r and "not client-facing" in r for r in reasons))
    check("provenance notes state the metadata-only content rule",
          any(r.startswith("content_rule:") and "metadata only" in r for r in reasons))
    check("provenance notes disclose the artifact is Peak-authored, not client-supplied",
          any("not a client-supplied export" in r for r in reasons))
    check("provenance notes carry no row-like item/quantity/location value",
          not ROW_LIKE_RE.search(joined))
    check("provenance notes name no other request's packet identity",
          not any(m in joined for m in OTHER_PACKET_MARKERS
                  if not m.startswith("pkt_internal_test_r9")))

    from peak.db.source_ingestion_writer import _pre_db_validate
    request = tool.build_request(synthetic_packet_hash("packet"))
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
    denial, validated = _pre_db_validate(request, None)
    check("the R10 packet passes the writer's pre-DB governance gate (no connection opened)",
          denial is None and validated is not None)


# --------------------------------------------------------------------------- 4. operator utility


def tool_checks() -> None:
    print("\n4. The operator writes exactly one record and can express no other")
    src = read(TOOL_REL)
    code = code_only(src)

    check("utility defaults to dry-run - --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check("utility invokes only the existing controlled source ingestion writer",
          "persist_source_ingestion_record" in code
          and not re.search(r"persist_(?!source_ingestion_record)\w+", code))
    check("utility calls the writer from exactly one place",
          code.count("persist_source_ingestion_record(") == 1)
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
    check("utility never decodes or prints an artifact body",
          re.search(r'open\(path,\s*["\']rb["\']\)', src) is not None
          and not re.search(r"\.read\(\)\s*\.decode|print\(\s*(?:blob|body|content|chunk)", code))
    check("utility never places artifact content on a draft",
          not any(f"{a}=" in code for a in FORBIDDEN_DRAFT_ATTRS))
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    # R9's packet reference legitimately appears once, as the question set R10 answers. Every
    # other prior packet identity - and R9's own idempotency key, which would be a retarget -
    # must be absent.
    check("utility cannot retarget R1, R2, R8 or R9 - no other packet identity appears",
          not any(m in src for m in OTHER_PACKET_MARKERS
                  if m != "pkt_internal_test_r9_location_bin_model_001"))
    check("utility references R9 only as the answered question set, never as its own target",
          src.count("pkt_internal_test_r9_location_bin_model_001") <= 1
          and "phase69_internal_test_source_ingestion_r9_001" not in src)
    check("the record identity fields are module constants, not derived from arguments",
          all(re.search(rf"(?m)^{name} = ", code) is not None
              for name in ("ENGAGEMENT_ID", "CLIENT_ID", "OWNER_ID", "AUTHORIZATION_SCOPE",
                           "IDEMPOTENCY_KEY", "PACKET_REFERENCE_ID",
                           "PACKET_LOCATION_REFERENCE")))
    check("no identity constant is ever reassigned inside a function",
          not re.search(r"(?m)^[ \t]+(?:ENGAGEMENT_ID|CLIENT_ID|OWNER_ID|AUTHORIZATION_SCOPE|"
                        r"IDEMPOTENCY_KEY|PACKET_REFERENCE_ID|PACKET_LOCATION_REFERENCE)[ \t]*=",
                        code))
    check("build_request takes only the packet hash - no identity is parameterised",
          re.search(r"def build_request\(packet_hash\b[^)]*\):", code) is not None)

    args = set(re.findall(r'add_argument\("(--[a-z0-9-]+)"', src))
    check("utility exposes only run mode and the artifact path - no record field is a flag",
          args <= {"--dry-run", "--execute", "--artifact-path"})

    env = scrubbed_env()

    def run_tool(*extra):
        return subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL), *extra],
                              capture_output=True, text=True, timeout=180, env=env)

    run = run_tool("--dry-run")
    check("dry-run exits 0 with no credential in the environment", run.returncode == 0)
    check("dry-run reports no connection was made",
          run.stdout.count("database_connection_made              : False") == 1)
    check("dry-run reports nothing was written", "DRY-RUN PASS" in run.stdout)
    check("dry-run validates exactly one packet",
          run.stdout.count("packet passes the writer's own pre-DB governance gate") == 1)
    check("bare invocation with no flag is also a dry-run",
          "DRY-RUN PASS" in run_tool().stdout)
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))
    check("dry-run discloses that stored-engagement authorization is not exercised",
          "NOT exercised by this dry-run" in run.stdout)
    check("dry-run prints the logical location reference, not a filesystem path",
          "internal-test-artifact://phase72/r10-location-model-answer-set-v1"
          in run.stdout)
    check("dry-run states R9 does not validate any inventory quantity",
          "does not validate any inventory quantity" in run.stdout)
    check("dry-run states R9 does not confirm R8 authority precedence",
          "does not confirm R8 authority precedence" in run.stdout)
    check("dry-run names no other request's packet reference or idempotency key",
          not any(m in run.stdout for m in OTHER_PACKET_MARKERS
                  if m != "pkt_internal_test_r9_location_bin_model_001"))
    # Artifact-agnostic: the artifact is JSON, so any leak would carry object syntax. Matching on
    # its own key names would instead copy its internals into this repository.
    check("dry-run prints no JSON object syntax - the artifact body cannot have leaked",
          "{" not in run.stdout and "}" not in run.stdout
          and not re.search(r'(?m)^\s*"[a-z_]+"\s*:', run.stdout))
    check("dry-run output is a short sanitized summary, not a document dump",
          len(run.stdout) < 16000)
    check("dry-run prints no home-directory path outside the clearly-labelled artifact line",
          not re.search(r"(?m)^(?!.*artifact path).*" + re.escape(os.path.expanduser("~")),
                        run.stdout))

    inside = run_tool("--artifact-path", os.path.join(REPO_ROOT, "README.md"))
    check("utility refuses an artifact path inside the repository",
          inside.returncode == 1
          and "inside the repository" in (inside.stderr + inside.stdout))
    inside_nested = run_tool("--artifact-path",
                             os.path.join(REPO_ROOT, "docs", ARTIFACT_BASENAMES[0]))
    check("utility refuses an in-repo path even under the approved artifact name",
          inside_nested.returncode == 1
          and "inside the repository" in (inside_nested.stderr + inside_nested.stdout))
    outside = run_tool("--artifact-path", os.path.join(tmpdir(), "elsewhere.json"))
    check("utility refuses any path other than the approved artifact",
          outside.returncode == 1
          and "not the approved" in (outside.stderr + outside.stdout))

    # Missing and empty approved artifacts, exercised in-process against a temp directory so the
    # real external artifact is never touched.
    import create_internal_test_r10_source_ingestion_record as tool

    fake_dir = tmpdir()
    real_dir = tool.APPROVED_ARTIFACT_DIR
    try:
        tool.APPROVED_ARTIFACT_DIR = fake_dir
        try:
            tool.resolve_artifact_path(None)
            check("utility refuses a missing approved artifact", False)
        except SystemExit as exc:
            check("utility refuses a missing approved artifact", "does not exist" in str(exc))

        empty = os.path.join(fake_dir, tool.ARTIFACT_NAME)
        with open(empty, "wb"):
            pass
        try:
            tool.artifact_metadata(tool.resolve_artifact_path(None))
            check("utility refuses an empty approved artifact", False)
        except SystemExit as exc:
            check("utility refuses an empty approved artifact", "is empty" in str(exc))
    finally:
        tool.APPROVED_ARTIFACT_DIR = real_dir


# --------------------------------------------------------------------------- 5. writer behaviour


def writer_checks() -> None:
    print("\n5. The writer creates exactly one R10 record and nothing else")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as anchor_tool
    import create_internal_test_r10_source_ingestion_record as tool
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

    packet_hash = synthetic_packet_hash("R9")
    receipt = persist_source_ingestion_record(tool.build_request(packet_hash),
                                              session_factory=factory)
    check("the R10 invocation creates a source ingestion record", receipt.outcome == "created")
    check("the receipt reports one stored record created", receipt.stored_record_created is True)
    check("the receipt reports the record is review-gated",
          receipt.review_status == "needs_review" and receipt.output_status == "draft")

    session = factory()
    check("exactly one source ingestion record exists",
          session.query(SourceIngestionRecord).count() == 1)
    row = session.get(SourceIngestionRecord, receipt.stored_record_id)
    check("the row carries the R10 packet reference id",
          row.source_reference_id == tool.PACKET_REFERENCE_ID)
    check("the record is tied to the internal_test engagement",
          row.engagement_id == ANCHOR_ID and row.client_id == RESERVED_CLIENT_ID
          and row.owner_id == "peak_internal_admin" and row.authorization_scope == SCOPE)
    check("the ingesting engagement is classified internal_test",
          session.get(Engagement, row.engagement_id).engagement_category == "internal_test")
    check("stored detail is metadata only - schema, source type, location, hash",
          {"packet_schema_name", "packet_source_type", "packet_location_reference",
           "packet_hash"} <= set(row.details_json))
    check("the stored hash is the packet hash, not artifact content",
          row.details_json["packet_hash"] == packet_hash)
    check("the stored location reference is logical, not a filesystem path",
          row.details_json["packet_location_reference"] == tool.PACKET_LOCATION_REFERENCE
          and row.details_json["packet_location_reference"].startswith(
              "internal-test-artifact://"))
    check("the row stores no raw artifact payload anywhere",
          not any(k in row.details_json for k in FORBIDDEN_DRAFT_ATTRS))
    check("the row carries no home-directory path",
          os.path.expanduser("~") not in str(row.details_json))
    check("the record is non-authoritative and not capsule-ready",
          row.details_json["authoritative"] is False
          and row.details_json["client_facing_approved"] is False
          and row.details_json["capsule_candidate_ready"] is False)

    stored_reasons = row.details_json.get("reasons", [])
    check("the row records that R10 does not validate any inventory quantity",
          any("does not validate any inventory quantity" in r for r in stored_reasons))
    check("the row records that R10 must be reviewed before evidence use",
          any("must be reviewed before" in r for r in stored_reasons))
    check("the row records the unconfirmed R8 precedence posture",
          any("does not confirm R8 authority precedence" in r for r in stored_reasons))
    check("the row records the unresolved R5 WMS scope posture",
          any("does not resolve R5 WMS scope" in r for r in stored_reasons))
    check("the row records that R1's provisional location marking is not lifted",
          any("does not lift R1's provisional location marking" in r for r in stored_reasons))
    check("the row retains the negative/unknown/blocked answer states",
          any("negative_answers_retained" in r for r in stored_reasons)
          and any(st in str(stored_reasons) for st in UNFAVOURABLE_STATES))
    check("the row records the headline finding that R1 is not currently readable",
          any("not currently readable" in r for r in stored_reasons))
    check("the row carries no row-like item/quantity/location value",
          not ROW_LIKE_RE.search(str(row.details_json)))
    check("the stored provenance names no other request's packet identity",
          not any(m in str(row.details_json) for m in OTHER_PACKET_MARKERS
                  if m != "pkt_internal_test_r9_location_bin_model_001"))

    # Nothing else was written.
    check("no Client row was created", session.query(Client).count() == 0)
    check("still exactly one engagement row", session.query(Engagement).count() == 1)
    check("no intake note record was created", session.query(IntakeNoteRecord).count() == 0)
    check("no review record was created", session.query(ReviewRecord).count() == 0)
    check("no evidence reference was created", session.query(EvidenceReference).count() == 0)
    session.close()

    # Replay: an identical payload must not write a second row.
    replay = persist_source_ingestion_record(tool.build_request(packet_hash),
                                             session_factory=factory)
    check("an identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    session = factory()
    check("still exactly one source ingestion record after replay",
          session.query(SourceIngestionRecord).count() == 1)
    session.close()

    # A changed artifact hash under the same idempotency key must conflict, never overwrite.
    conflict = persist_source_ingestion_record(
        tool.build_request(synthetic_packet_hash("R9-changed")), session_factory=factory)
    check("a changed artifact hash under the same idempotency key is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("still exactly one source ingestion record after the conflict",
          session.query(SourceIngestionRecord).count() == 1)
    stored = session.get(SourceIngestionRecord, receipt.stored_record_id)
    check("the existing record was not overwritten",
          stored is not None and stored.details_json["packet_hash"] == packet_hash)
    check("no evidence reference or review record appeared at any point",
          session.query(EvidenceReference).count() == 0
          and session.query(ReviewRecord).count() == 0)
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
        ("one r10 source ingestion record", "exactly one R10 record was created"),
        ("measured location model answer set", "R10 is a measured answer set"),
        ("question set", "R10 responds to R9's question set"),
        ("negative", "the answer set includes negative answers"),
        ("unknown", "the answer set includes unknown answers"),
        ("outside the repository", "the artifact body lives outside the repository"),
        ("metadata", "only metadata was persisted"),
        ("packet_hash", "the hash is named as what was persisted"),
        ("internal-test-artifact://", "the logical location reference is recorded"),
        ("needs_review", "R10 remains needs_review"),
        ("authoritative=false", "R10 remains non-authoritative"),
        ("must be reviewed", "R10 must be reviewed before evidence use"),
        ("does not validate inventory quantities",
         "R10 does not validate inventory quantities"),
        ("does not lift r1's provisional location marking",
         "R10 does not lift R1's provisional location marking"),
        ("does not resolve r8 authority precedence",
         "R10 does not resolve R8 authority precedence"),
        ("does not resolve r5 wms scope", "R10 does not resolve R5 WMS scope"),
        ("no evidence reference", "no evidence_reference was created"),
        ("no review record", "no review record was created"),
        ("no report", "no report record was created"),
        ("no capsule", "no capsule was created"),
        ("no client-facing output", "no client-facing output was created"),
        ("resolver", "the AgentNet resolver posture is stated"),
        ("publication remains", "resolver publication remains gated"),
        ("phase 73", "the likely Phase 73 next step is named"),
        (ANCHOR_ID, "the engagement anchor is named"),
        (SCOPE, "the authorization scope is named"),
    ):
        check(f"doc states: {label}", phrase in f)

    check("doc states: R3-R7 remain deferred",
          re.search(r"r3[-\u2013\u2014]r7", f) is not None and "defer" in f)
    check("doc records the headline finding rather than only the mechanics",
          "not currently readable" in f or "not reliable enough" in f)
    check("doc states no checklist item was omitted",
          "15" in f and ("dropped" in f or "omitted" in f or "none was" in f))

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("doc contains no artifact filesystem path",
          not any(name in doc for name in ARTIFACT_BASENAMES))
    check("doc carries no row-like item/quantity/location value", not ROW_LIKE_RE.search(doc))

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md", PLAN_REL, PHASE70_DOC_REL, PHASE69_DOC_REL):
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records Phase 72", "phase 72" in blob)
        check(f"{name} states no evidence reference was created",
              any(t in blob for t in ("no evidence reference", "no evidence_reference",
                                      "evidence_references still")))
        check(f"{name} states R1 remains provisional", "remains provisional" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase72", "validate-phase72" in mk)
    check("validate depends on validate-phase72",
          re.search(r"^validate:.*validate-phase72", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)
    check("the record-creation utility is not wired into validate",
          "create_internal_test_r10_source_ingestion_record" not in mk)


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
    check("this harness never opens the external artifact",
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

    # Phase 72 must add nothing beyond its own operator, harness, and docs. Authoring-time only:
    # gated on whether this phase has landed, because the diff is taken from Phase 72's baseline and
    # would otherwise judge every later phase's files against Phase 72's allowlist — a permanent
    # freeze on the repository rather than a claim about this phase. Phase 84 is the first later
    # phase to add a non-docs file (the Alembic migration target guard) and tripped it.
    scope = git("diff", "--name-only", BASELINE_COMMIT).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    if not git("log", "-1", "--format=%H", "--", HARNESS_REL).strip():
        allowed = {TOOL_REL, HARNESS_REL, DOC_REL, "Makefile", *PRIOR_HARNESS_FIXES}
        added = [c for c in set(scope + untracked)
                 if c and c not in allowed and not c.startswith("docs/")]
        check("this phase changed nothing outside its operator, harness, docs, the Makefile, and "
              "the three named prior-phase harness fixes", not added)
        if added:
            print(f"        unexpected: {sorted(added)}")
    else:
        print("  [skip] Phase 72 is committed — working-tree scope guard not applicable")
    # The prior-harness exception must stay an exception: it may cover test files only.
    check("every prior-phase file this fix touched is a validation harness, not production code",
          all(h.startswith("tests/") and h.endswith(".py") for h in PRIOR_HARNESS_FIXES))
    check("no prior-phase operator utility was modified",
          not [c for c in set(scope + untracked)
               if c.startswith("tools/") and c != TOOL_REL])

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
        # No instance-level inventory data may be copied into the repository by this phase.
        check(f"{name} contains no bare quantity-like assignment",
              not re.search(r"(?i)\b(qty|quantity|on_hand|onhand)\s*[:=]\s*[\"']?\d", blob))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 72 R10 measured location model answer set source ingestion check")
    print("=" * 70)
    try:
        baseline_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed - contract/packet/writer layers skipped.")
            print("         Run: make validate-phase72 PYTHON=.venv/bin/python")
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
