#!/usr/bin/env python3
"""Phase 61 internal test intake review decision check.

Phase 60 created the internal_test intake note. Phase 61 reviews it and records **one** governed
review decision through the unchanged Phase 22 ``review_records`` writer, determining that the note
is sufficient to begin source/evidence collection as an internal/admin workflow — and nothing more.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite, and
the operator utility is exercised with every role variable scrubbed from the environment so its
dry-run default is proven to open no connection.

**No intake prose lives in this repository.** The review's findings are category labels and gap
descriptors, never note body text. This harness synthesises a throwaway note body at runtime for its
temp-SQLite fixture and asserts no note content is committed anywhere.

Layers: baseline · writer selection · packet · operator utility · writer behaviour · docs.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

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

BASELINE_COMMIT = "3444376"   # Add Phase 60 internal test intake taxonomy and note

TOOL_REL = "tools/create_internal_test_intake_review_decision.py"
HARNESS_REL = "tests/validate_phase61_internal_test_intake_review_decision.py"
DOC_REL = "docs/PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md"
TAXONOMY_REL = "docs/PEAK_INTAKE_QUESTION_TAXONOMY_V0.md"
WRITER_REL = "peak/db/review_writer.py"
MODELS_REL = "peak/db/models.py"

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
INTAKE_NOTE_ID = "intn_b8b86b8c196c4595"

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"[\w.\-]+:[^\s@'\"]+@")

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


def code_no_docstrings(source: str) -> str:
    import ast
    tree = ast.parse(source)
    doc = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = getattr(n, "body", None)
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                doc.append((b[0].lineno, b[0].end_lineno))
    return "\n".join(re.sub(r"#.*$", "", ln)
                     for i, ln in enumerate(source.splitlines(), 1)
                     if not any(a <= i <= b for a, b in doc))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def tmpdir() -> str:
    tmp = tempfile.mkdtemp(prefix="peak_phase61_")
    _tmpdirs.append(tmp)
    return tmp


def temp_sqlite_url() -> str:
    return "sqlite:///" + os.path.join(tmpdir(), "phase61.db")


def synthetic_note_body() -> str:
    """A throwaway body built at runtime. Never written to the repo, never committed."""
    return ("Internal test data only. No real client data. "
            "Synthetic body used to exercise the controlled review path offline.")


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
    check("no migration 015 or later — Phase 61 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))

    for rel in (TOOL_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("peak/db/models.py was not modified by this phase",
          not git("diff", "--name-only", "HEAD", "--", MODELS_REL))
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )
    check("generic allowlist unchanged — no pair added",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES
          and len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("still exactly one anchor-creation pair", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check("engagements remains prohibited generically",
          is_prohibited_table("engagements") and not is_allowed_table("engagements"))
    check("clients remains never writable by any controlled path",
          is_never_writable_table("clients"))
    check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx"))


# --------------------------------------------------------------------------- 2. writer selection


def writer_selection_checks() -> None:
    print("\n2. review_records is an appropriate writer for an intake-note review decision")
    from peak.db.review_writer import (
        ALLOWED_DECISIONS, PROHIBITED_DECISIONS, SUPPORTED_SUBJECT_TYPES,
    )
    from peak.review.persistence_contracts import ReviewRecordDraft

    fields = set(ReviewRecordDraft.__dataclass_fields__)
    check("the draft carries a reviewed target distinct from the authorization anchor",
          {"subject_record_id", "subject_record_type"} <= fields)
    check("the authorization anchor must still be an engagement",
          SUPPORTED_SUBJECT_TYPES == frozenset({"engagement"}))
    check("the draft can carry concise findings", "reasons" in fields)
    check("the draft carries the client-facing and capsule posture flags",
          {"client_facing_approved", "capsule_candidate_ready", "authoritative"} <= fields)
    check("approve_internal is an allowed decision", "approve_internal" in ALLOWED_DECISIONS)
    check("client-facing approval, financial verification, and capsule publication are refused",
          {"client_facing_approve", "verify_financial_impact", "publish_capsule"}
          <= PROHIBITED_DECISIONS)

    # The rejected alternative is shaped around a review bundle, not a reviewed target.
    from peak.reviewer_decisions.contracts import InternalReviewerDecisionDraft
    alt = set(InternalReviewerDecisionDraft.__dataclass_fields__)
    check("the internal_reviewer_decision draft has no reviewed-target field "
          "(why it was not selected)",
          "subject_record_id" not in alt and "subject_record_type" not in alt)
    check("the internal_reviewer_decision draft is bundle-shaped",
          {"review_bundle_ref", "review_plan_item_refs"} <= alt)


# --------------------------------------------------------------------------- 3. the packet


def packet_checks() -> None:
    print("\n3. The one authorized decision packet is internal-only and non-final")
    import create_internal_test_intake_review_decision as tool

    check(f"decision targets the Phase 60 intake note {INTAKE_NOTE_ID}",
          tool.SUBJECT_RECORD_ID == INTAKE_NOTE_ID
          and tool.SUBJECT_RECORD_TYPE == "intake_note")
    check(f"decision is written under engagement {ANCHOR_ID} / client {RESERVED_CLIENT_ID}",
          tool.ENGAGEMENT_ID == ANCHOR_ID and tool.CLIENT_ID == RESERVED_CLIENT_ID)
    check("scope is internal_peak_only", tool.AUTHORIZATION_SCOPE == "internal_peak_only")
    check("decision is approve_internal (internal reliance only)",
          tool.DECISION == "approve_internal")
    check("approve_internal lands on approved_internal, as the writer requires",
          tool.NEXT_REVIEW_STATUS == "approved_internal")
    check("the output stays non-final", tool.NEXT_OUTPUT_STATUS == "draft")
    check("the decision is not marked authoritative", tool.AUTHORITATIVE is False)

    reasons = list(tool.REASONS)
    check("findings reference the V0 taxonomy",
          any("PEAK_INTAKE_QUESTION_TAXONOMY_V0" in r for r in reasons))
    check("findings record covered taxonomy categories",
          any(r.startswith("covered_") for r in reasons))
    check("findings record incomplete taxonomy categories",
          len([r for r in reasons if r.startswith("incomplete")]) >= 5)
    check("findings record the next evidence requests",
          len([r for r in reasons if r.startswith("evidence_next:")]) >= 8)
    for needed in ("inventory export", "item/SKU master", "adjustment history",
                   "receiving and putaway", "cycle count", "stockout",
                   "SOP", "system-of-record"):
        check(f"evidence request names: {needed}",
              any(needed.lower() in r.lower() for r in reasons
                  if r.startswith("evidence_next:")))
    check("findings record the internal-only, no-real-client-data posture",
          any("no real client data" in r and "not client-facing" in r for r in reasons))
    check("findings name source/evidence collection as the next step",
          any(r.startswith("next_step:") and "source" in r for r in reasons))
    check("findings explicitly withhold report/capsule/publication authority",
          any(r.startswith("not_authorized:") and "publication" in r for r in reasons))

    from peak.db.review_writer import _pre_db_validate
    denial, draft = _pre_db_validate(tool.build_request(), None)
    check("packet passes the writer's pre-DB governance gate (no connection opened)",
          denial is None and draft is not None)


# --------------------------------------------------------------------------- 4. operator utility


def tool_checks() -> None:
    print("\n4. The operator utility targets one record and can express no other")
    src = read(TOOL_REL)
    code = code_no_docstrings(src)

    check("utility defaults to dry-run — --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check("utility invokes only the existing controlled review writer",
          "persist_review_record" in code
          and not re.search(r"persist_(?!review_record)\w+", code))
    check("utility creates no Client, Engagement, intake, source, evidence, report, or capsule "
          "record",
          not re.search(r"(?i)\bClient\(|\bEngagement\(|IntakeNoteDraft|persist_intake|"
                        r"persist_evidence|persist_source|persist_agent_run|persist_internal_|"
                        r"publish", code))
    check("utility performs no UPDATE/DELETE/cleanup/stamp call",
          not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{|"
                        r"(?i)\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b|alembic\s+stamp", code))
    check("utility issues no raw SQL",
          not re.search(r"(?i)\btext\(|session\.execute\(|conn(?:ection)?\.execute\(|"
                        r"engine\.execute\(|cursor\.|\bSELECT\s+\w+\s+FROM\b", code))
    check("utility imports no migration/Alembic code",
          "alembic" not in code.lower() and "op.add_column" not in code)
    check("utility reads no environment variable directly",
          "os.environ" not in code and "getenv" not in code)
    check("utility never opens or reads the intake note body",
          "phase60_internal_test_intake_note" not in src and "note_text" not in code)
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    args = set(re.findall(r'add_argument\("(--[a-z-]+)"', src))
    check("utility exposes no record field as a flag — only run mode",
          args <= {"--dry-run", "--execute"})

    env = scrubbed_env()
    run = subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL), "--dry-run"],
                         capture_output=True, text=True, timeout=120, env=env)
    check("dry-run exits 0 with no credential in the environment", run.returncode == 0)
    check("dry-run reports no connection was made",
          "database_connection_made              : False" in run.stdout)
    check("dry-run reports nothing was written", "DRY-RUN PASS" in run.stdout)
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))
    check("dry-run discloses that stored-engagement authorization is not exercised",
          "NOT exercised by this dry-run" in run.stdout)


# --------------------------------------------------------------------------- 5. writer behaviour


def writer_checks() -> None:
    print("\n5. The writer creates exactly one decision, and is still create-only")
    code = code_no_docstrings(read(WRITER_REL))
    check("review writer is still create-only",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as anchor_tool
    import create_internal_test_intake_note as note_tool
    import create_internal_test_intake_review_decision as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.intake_note_writer import persist_intake_note_record
    from peak.db.models import (
        Client, Engagement, EvidenceReference, IntakeNoteRecord, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.db.review_writer import persist_review_record

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # Rebuild the Phase 59 anchor and a Phase 60-shaped note, via their own writers.
    anchor = persist_engagement_authorization_anchor(anchor_tool.build_request(),
                                                     session_factory=factory)
    note = persist_intake_note_record(note_tool.build_request(synthetic_note_body()),
                                      session_factory=factory)
    check("the anchor and intake note exist for the review to target",
          anchor.outcome == "created" and note.outcome == "created")

    # Point the request at the note this fixture actually created.
    request = tool.build_request()
    request.record_draft.subject_record_id = note.stored_record_id

    receipt = persist_review_record(request, session_factory=factory)
    check("first invocation creates the review decision", receipt.outcome == "created")
    check("receipt reports one stored record created", receipt.stored_record_created is True)
    check("the decision is approve_internal", getattr(receipt, "decision", None)
          in (None, "approve_internal"))
    check("receipt reports no client-facing approval or capsule candidacy",
          getattr(receipt, "client_facing_approved", False) is False
          and getattr(receipt, "capsule_candidate_ready", False) is False)
    check("receipt reports no client-facing output or capsule publication",
          getattr(receipt, "client_facing_output_created", False) is False
          and getattr(receipt, "capsule_publication_made", False) is False
          and getattr(receipt, "agentnet_publication_made", False) is False)
    check("receipt reports no update and no delete",
          getattr(receipt, "update_made", False) is False
          and getattr(receipt, "delete_made", False) is False)

    session = factory()
    check("exactly one review record exists", session.query(ReviewRecord).count() == 1)
    row = session.query(ReviewRecord).one()
    check("the review record targets the intake note",
          row.target_id == note.stored_record_id and row.subject_record_type == "intake_note")
    check("the review record is tied to the internal_test engagement",
          row.engagement_id == ANCHOR_ID and row.client_id == RESERVED_CLIENT_ID
          and row.authorization_scope == "internal_peak_only")
    check("the reviewed engagement is classified internal_test",
          session.get(Engagement, row.engagement_id).engagement_category == "internal_test")
    check("the stored decision is approve_internal and non-authoritative",
          row.decision == "approve_internal" and bool(row.authoritative) is False)
    check("the stored findings carry covered, incomplete, and evidence_next entries",
          any(r.startswith("covered_") for r in row.details_json["reasons"])
          and any(r.startswith("incomplete") for r in row.details_json["reasons"])
          and any(r.startswith("evidence_next:") for r in row.details_json["reasons"]))
    check("the stored findings carry no intake note body text",
          not any("Synthetic body used to exercise" in r
                  for r in row.details_json["reasons"]))

    # Nothing else was written.
    check("no Client row was created", session.query(Client).count() == 0)
    check("still exactly one engagement row", session.query(Engagement).count() == 1)
    check("still exactly one intake note row", session.query(IntakeNoteRecord).count() == 1)
    check("no source ingestion record was created",
          session.query(SourceIngestionRecord).count() == 0)
    check("no evidence reference was created", session.query(EvidenceReference).count() == 0)
    session.close()

    # Replay: identical payload must not write a second row.
    replay_request = tool.build_request()
    replay_request.record_draft.subject_record_id = note.stored_record_id
    replay = persist_review_record(replay_request, session_factory=factory)
    check("identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    session = factory()
    check("still exactly one review record after replay",
          session.query(ReviewRecord).count() == 1)
    session.close()

    # A changed payload under the same idempotency key must conflict, never overwrite.
    conflicting = tool.build_request()
    conflicting.record_draft.subject_record_id = note.stored_record_id
    conflicting.record_draft.reasons = list(tool.REASONS) + ["evidence_next: changed"]
    conflict = persist_review_record(conflicting, session_factory=factory)
    check("a changed payload under the same idempotency key is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("still exactly one review record after the conflict",
          session.query(ReviewRecord).count() == 1)
    check("the existing decision was not overwritten",
          session.query(ReviewRecord).one().id == receipt.stored_record_id)
    session.close()


# --------------------------------------------------------------------------- 6. docs


def doc_checks() -> None:
    print("\n6. Docs state the decision, its limits, and the next step")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("doc content checks (skipped: the doc is missing)", False)
        return
    doc = read(DOC_REL)
    f = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", doc, flags=re.MULTILINE).lower())
    for phrase, label in (
        ("one internal review decision record was created",
         "one internal review/decision record was created"),
        (INTAKE_NOTE_ID, "for the Phase 60 intake note"),
        ("internal-only", "the note remains internal-only"),
        ("non-client-facing", "the note remains non-client-facing"),
        ("no client record", "no Client record was created"),
        ("no additional engagement", "no additional Engagement was created"),
        ("no second intake note", "no second intake note was created"),
        ("no source", "no source record was created"),
        ("no evidence", "no evidence record was created"),
        ("no report", "no report record was created"),
        ("no capsule", "no capsule record was created"),
        ("source/evidence collection", "the decision authorizes source/evidence collection"),
        ("not report or capsule publication",
         "it does not authorize report or capsule publication"),
        ("v0 taxonomy", "covered/missing categories derive from the V0 taxonomy"),
        ("covered", "covered categories are recorded"),
        ("incomplete", "incomplete categories are recorded"),
        ("next evidence request", "next evidence requests are identified"),
        ("taxonomy-derived, not guessed",
         "future real-client forms should be taxonomy-derived"),
    ):
        check(f"doc states: {label}", phrase in f)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md",
                "docs/PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md", TAXONOMY_REL):
        blob = re.sub(r"\s+", " ", read(rel)).lower()
        check(f"{os.path.basename(rel)} records the Phase 61 review decision",
              "phase 61" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase61", "validate-phase61" in mk)
    check("validate depends on validate-phase61",
          re.search(r"^validate:.*validate-phase61", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)
    check("the decision-creation utility is not wired into validate",
          "create_internal_test_intake_review_decision" not in mk)


# --------------------------------------------------------------------------- 7. self-isolation


def self_isolation_checks() -> None:
    print("\n7. This harness contacts no production and commits no note prose")
    src = read(HARNESS_REL)
    urls = re.findall(r'create_engine\(\s*([a-z_]+)\(', src)
    check("this harness builds only temporary SQLite database URLs",
          set(urls) <= {"temp_sqlite_url"} and "sqlite:///" in src)
    check("this harness scrubs every role variable from child processes",
          all(v in src for v in ROLE_VARS))
    check("this harness never passes --execute to the operator utility",
          re.search(r'subprocess\.run\(\[[^\]]*TOOL_REL[^\]]*"--execute"', src) is None)
    check("this harness embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("this harness's note body is synthetic and built at runtime",
          "def synthetic_note_body" in src)
    # Reading the external body would require resolving a home-directory path; this harness
    # resolves none (it uses tempfile only). Matching on the filename would match this check.
    check("this harness never reads the external intake note body",
          re.search(r"expanduser\s*\(", code_no_docstrings(src)) is None)

    # The Phase 60 note body must remain absent from the repository entirely.
    tracked = git("ls-files").splitlines()
    check("no intake note body file is tracked in the repository",
          not [t for t in tracked if "internal_test_intake_note" in t and t.endswith(".txt")])
    for rel in (TOOL_REL, TAXONOMY_REL):
        blob = read(rel)
        check(f"{os.path.basename(rel)} contains no obviously client-like organisation name",
              not re.search(r"(?i)\b(acme|contoso|initech|globex|northwind)\b", blob))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 61 internal test intake review decision check")
    print("=" * 70)
    try:
        baseline_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed — packet/writer layers not exercised.")
            print("         Run: make validate-phase61 PYTHON=.venv/bin/python")
        else:
            writer_selection_checks()
            packet_checks()
            tool_checks()
            writer_checks()

        doc_checks()
        self_isolation_checks()
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
