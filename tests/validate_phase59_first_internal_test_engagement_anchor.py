#!/usr/bin/env python3
"""Phase 59 first durable internal test engagement anchor check.

Phase 58 put the classification columns in production. Phase 59 creates the **one** durable
``internal_test`` engagement anchor through the existing Phase 54/56 controlled writer — Peak's
first production application record. This harness pins what that write is allowed to be: exactly
one anchor, classified internal_test, holding no real client data, not client-accessible, in the
reserved test namespace, and durable rather than disposable smoke.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite,
and the operator utility is exercised with every role variable scrubbed from the environment, so
its dry-run default is proven to open no connection.

Layers: baseline · packet · operator utility · writer behaviour · read isolation · docs.

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

BASELINE_COMMIT = "870d890"   # Document Phase 58 production migration 014 application

TOOL_REL = "tools/create_internal_test_engagement_anchor.py"
HARNESS_REL = "tests/validate_phase59_first_internal_test_engagement_anchor.py"
DOC_REL = "docs/PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md"
WRITER_REL = "peak/db/engagement_authorization_anchor_writer.py"
MODELS_REL = "peak/db/models.py"
ISOLATION_REL = "peak/db/engagement_read_isolation.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"

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


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def temp_sqlite_url() -> str:
    tmp = tempfile.mkdtemp(prefix="peak_phase59_")
    _tmpdirs.append(tmp)
    return "sqlite:///" + os.path.join(tmp, "phase59.db")


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
        print("        reason: phase59_baseline_commit_not_ancestor")

    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later — Phase 59 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))

    for rel in (TOOL_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("the operator utility is not itself a writer", not TOOL_REL.endswith("_writer.py"))

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
          is_never_writable_table("clients") and not is_allowed_table("clients"))


# --------------------------------------------------------------------------- 2. the packet


def packet_checks() -> None:
    print("\n2. The one authorized packet is a durable internal test anchor")
    import create_internal_test_engagement_anchor as tool
    from peak.persistence.governance import (
        ALLOWED_ANCHOR_INITIAL_LIFECYCLE, ALLOWED_ANCHOR_INITIAL_STATUS,
        ENGAGEMENT_CATEGORY_INTERNAL_TEST, is_reserved_internal_test_client_id,
        validate_engagement_classification,
    )

    a = tool.ANCHOR
    check("packet is internal_test", a["engagement_category"] == ENGAGEMENT_CATEGORY_INTERNAL_TEST)
    check("packet client_id uses the reserved internal-test namespace",
          is_reserved_internal_test_client_id(a["client_id"]))
    check("packet real_client_data is False", a["real_client_data"] is False)
    check("packet client_accessible is False", a["client_accessible"] is False)
    check("packet capsule_publication_authorized is True",
          a["capsule_publication_authorized"] is True)
    check("packet classification passes the Phase 55/56 policy gate",
          validate_engagement_classification(
              a["engagement_category"], a["real_client_data"], a["client_accessible"],
              a["capsule_publication_authorized"], a["client_id"]) == [])
    check("packet uses an allowed initial engagement status",
          a["status"] in ALLOWED_ANCHOR_INITIAL_STATUS)
    check("packet uses an allowed initial lifecycle",
          a["lifecycle_status"] in ALLOWED_ANCHOR_INITIAL_LIFECYCLE)
    check("packet review_status is the server-stamped needs_review",
          a["review_status"] == "needs_review")

    # Durable, not disposable smoke; and not a fixture.
    check("packet scope is not fixture_test — this is a durable record, not a fixture",
          a["authorization_scope"] != "fixture_test")
    check("packet lifecycle is active, not a disposable/archived posture",
          a["lifecycle_status"] == "active")
    check("idempotency key is a deterministic constant, not random per run",
          isinstance(tool.IDEMPOTENCY_KEY, str)
          and not re.search(r"(?i)uuid|random|token_hex|time\(\)",
                            code_no_docstrings(read(TOOL_REL))))

    # Classification must live in real columns, never smuggled into free text or an id prefix.
    check("classification is not smuggled into details_json/label/scope",
          "internal_test" not in str(a["engagement_label"]).lower()
          and "internal_test" not in a["authorization_scope"])

    # The request the tool builds must pass the writer's own gate with no DB connection.
    from peak.db.engagement_authorization_anchor_writer import _pre_db_validate
    denial, draft = _pre_db_validate(tool.build_request())
    check("packet passes the writer's pre-DB governance gate (no connection opened)",
          denial is None and draft is not None)


# --------------------------------------------------------------------------- 3. operator utility


def tool_checks() -> None:
    print("\n3. The operator utility is dry-run by default and can express only this record")
    src = read(TOOL_REL)
    code = code_no_docstrings(src)

    check("utility defaults to dry-run — --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check("utility invokes only the existing controlled anchor writer",
          "persist_engagement_authorization_anchor" in code
          and not re.search(r"persist_(?!engagement_authorization_anchor)\w+", code))
    # Precise patterns: the tool legitimately has an ``--execute`` flag and a message that uses
    # the word "delete", so match real mutation/SQL call sites rather than the words.
    check("utility performs no UPDATE/DELETE/cleanup/stamp call",
          not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{|"
                        r"(?i)\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b|"
                        r"\bTRUNCATE\b|alembic\s+stamp", code))
    check("utility issues no raw SQL",
          not re.search(r"(?i)\btext\(|session\.execute\(|conn(?:ection)?\.execute\(|"
                        r"engine\.execute\(|cursor\.|\bSELECT\s+\w+\s+FROM\b", code))
    check("utility imports no migration/Alembic code",
          "alembic" not in code.lower() and "op.add_column" not in code)
    check("utility creates no Client, intake note, or downstream record",
          not re.search(r"(?i)\bClient\(|persist_intake_note|persist_review|persist_evidence|"
                        r"persist_agent_run|persist_source_ingestion|publish", code))
    check("utility reads no environment variable itself",
          "os.environ" not in code and "getenv" not in code)
    check("utility never echoes the engagement_label",
          "<withheld>" in src and "engagement_label" not in
          re.sub(r"(?s).*RECEIPT_FIELDS = \(", "", src).split(")")[0])
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    # The packet is a constant: no record field may be supplied on the command line.
    args = set(re.findall(r'add_argument\("(--[a-z-]+)"', src))
    check("utility accepts only --dry-run/--execute — no record field is caller-supplied",
          args <= {"--dry-run", "--execute"})

    # Dry-run must work with every role variable scrubbed: proof it opens no connection.
    env = scrubbed_env()
    run = subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL), "--dry-run"],
                         capture_output=True, text=True, timeout=120, env=env)
    check("dry-run exits 0 with no credential in the environment", run.returncode == 0)
    check("dry-run reports no connection was made",
          "database_connection_made        : False" in run.stdout)
    check("dry-run reports nothing was written", "DRY-RUN PASS" in run.stdout)
    check("dry-run withholds the engagement_label", "<withheld>" in run.stdout
          and "Internal Test Engagement" not in run.stdout)
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))


# --------------------------------------------------------------------------- 4. writer behaviour


def writer_checks() -> None:
    print("\n4. The writer creates exactly one anchor, and is still create-only")
    code = code_no_docstrings(read(WRITER_REL))
    check("anchor writer is still create-only",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.models import Client, Engagement

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    receipt = persist_engagement_authorization_anchor(tool.build_request(),
                                                      session_factory=factory)
    check("first invocation creates the anchor", receipt.outcome == "created")
    check("receipt reports one stored record created", receipt.stored_record_created is True)
    check("receipt reports the internal_test classification",
          receipt.engagement_category == "internal_test"
          and receipt.real_client_data is False and receipt.client_accessible is False
          and receipt.capsule_publication_authorized is True)
    check("receipt reports no Client record write", receipt.client_record_write_made is False)
    check("receipt reports no other-table write", receipt.other_table_write_made is False)
    check("receipt reports no update and no delete",
          receipt.update_made is False and receipt.delete_made is False)
    check("receipt reports no capsule publication",
          receipt.capsule_publication_made is False
          and receipt.agentnet_publication_made is False)
    check("receipt reports no approval or client-facing output",
          receipt.review_approval_made is False
          and receipt.client_facing_output_created is False)
    check("receipt reports no agent/LLM/network call",
          receipt.agent_execution_made is False and receipt.llm_call_made is False
          and receipt.network_call_made is False)
    check("receipt never echoes the engagement_label",
          not any("Internal Test Engagement" in str(v)
                  for v in vars(receipt).values()))

    session = factory()
    check("exactly one engagements row exists", session.query(Engagement).count() == 1)
    check("no Client row was created", session.query(Client).count() == 0)
    row = session.query(Engagement).one()
    check("stored row carries the classification in real columns",
          row.engagement_category == "internal_test" and row.real_client_data is False
          and row.client_accessible is False and row.capsule_publication_authorized is True)
    check("stored row is in the reserved client namespace", row.client_id == "99999")
    session.close()

    # Replay: identical packet must not write a second row.
    replay = persist_engagement_authorization_anchor(tool.build_request(),
                                                     session_factory=factory)
    check("identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    session = factory()
    check("still exactly one engagements row after replay",
          session.query(Engagement).count() == 1)
    session.close()

    # A changed definition under the same anchor id must be denied, never overwritten.
    conflicting = tool.build_request()
    conflicting.record_draft.engagement_label = "Internal Test Engagement 002"
    conflict = persist_engagement_authorization_anchor(conflicting, session_factory=factory)
    check("a changed definition under the same anchor id is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("the existing anchor was not modified by the conflicting attempt",
          session.query(Engagement).one().engagement_label == "Internal Test Engagement 001")
    session.close()

    # The utility cannot express a real_client record: its packet is a constant.
    check("the utility's packet cannot be a real_client record",
          tool.ANCHOR["engagement_category"] == "internal_test")
    from peak.persistence.governance import validate_engagement_classification
    hypothetical = dict(tool.ANCHOR, engagement_category="real_client")
    check("the same identity as a real_client record would be rejected by policy",
          validate_engagement_classification(
              hypothetical["engagement_category"], hypothetical["real_client_data"],
              hypothetical["client_accessible"], hypothetical["capsule_publication_authorized"],
              hypothetical["client_id"]) != [])


# --------------------------------------------------------------------------- 5. read isolation


def isolation_checks() -> None:
    print("\n5. The anchor is excluded from client-facing reads")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.engagement_read_isolation import (
        apply_read_isolation, is_client_visible, is_internal_test, is_publication_eligible,
    )
    from peak.db.models import Engagement

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    persist_engagement_authorization_anchor(tool.build_request(), session_factory=factory)

    session = factory()
    row = session.query(Engagement).one()
    check("the anchor is not client-visible", is_client_visible(row) is False)
    check("the anchor reads as an internal test engagement", is_internal_test(row) is True)
    check("the anchor is publication-eligible under the compound rule",
          is_publication_eligible(row) is True)
    check("a client-facing query returns no rows",
          apply_read_isolation(session.query(Engagement)).count() == 0)
    check("an internal/admin query that opts in returns the anchor",
          apply_read_isolation(session.query(Engagement), mode="internal_admin",
                               include_internal_test=True).count() == 1)
    session.close()


# --------------------------------------------------------------------------- 6. docs


def doc_checks() -> None:
    print("\n6. Docs state what was written to production, and what was not")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        # Fail the layer without a traceback, so the rest of the run still reports.
        check("doc content checks (skipped: the doc is missing)", False)
        return
    doc = read(DOC_REL)
    f = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", doc, flags=re.MULTILINE).lower())
    for phrase, label in (
        ("one durable internal_test engagement anchor was created in production",
         "one durable internal_test anchor was created in production"),
        ("not disposable smoke", "it is not disposable smoke data"),
        ("no real client data", "it contains no real client data"),
        ("not client-accessible", "it is not client-accessible"),
        ("reserved", "it uses a reserved internal/test namespace"),
        ("compound", "publication eligibility follows from the compound rule"),
        ("no intake note", "no intake note or capsule was created"),
        ("no real client record was created", "no real client record was created"),
        ("only through the controlled writer",
         "runtime credential was used only through the controlled writer path"),
        ("runtime delete is unavailable", "runtime DELETE is unavailable"),
        ("future real-client read paths must use", "future real-client reads must use Phase 57"),
        ("disposable production smoke record", "disposable smoke records remain disallowed"),
        ("writer enablement", "unauthorized writer enablement remains disallowed"),
    ):
        check(f"doc states: {label}", phrase in f)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md",
                "docs/PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md",
                "docs/PHASE57_INTERNAL_TEST_READ_ISOLATION.md",
                "docs/PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md"):
        blob = re.sub(r"\s+", " ", read(rel)).lower()
        check(f"{os.path.basename(rel)} records the Phase 59 anchor",
              "phase 59" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase59", "validate-phase59" in mk)
    check("validate depends on validate-phase59",
          re.search(r"^validate:.*validate-phase59", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify|create_internal_test)", mk,
                    re.MULTILINE) is None)
    check("the anchor-creation utility is not wired into validate",
          "create_internal_test_engagement_anchor" not in mk)


# --------------------------------------------------------------------------- 7. self-isolation


def self_isolation_checks() -> None:
    print("\n7. This harness contacts no production")
    src = read(HARNESS_REL)
    urls = re.findall(r'create_engine\(\s*([a-z_]+)\(', src)
    check("this harness builds only temporary SQLite database URLs",
          set(urls) <= {"temp_sqlite_url"} and 'sqlite:///' in src)
    check("this harness scrubs every role variable from child processes",
          all(v in src for v in ROLE_VARS))
    # Match the call sites themselves, not the word: this file necessarily mentions --execute
    # when asserting that the utility requires it.
    check("this harness never passes --execute to the operator utility",
          re.search(r'TOOL_REL\)[^)]*"--execute"', src) is None)
    check("this harness embeds no real-looking DSN", not REAL_DSN_RE.search(src))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 59 first internal test engagement anchor check")
    print("=" * 70)
    try:
        baseline_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed — packet/writer/isolation layers not run.")
            print("         Run: make validate-phase59 PYTHON=.venv/bin/python")
        else:
            packet_checks()
            tool_checks()
            writer_checks()
            isolation_checks()

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
