#!/usr/bin/env python3
"""Phase 60 intake taxonomy V0 + first internal test intake note check.

Phase 59 created the durable internal test engagement anchor. Phase 60 does two things: it defines
the **Peak Intake Question Taxonomy V0** — the rule that intake questions are derived from
downstream deliverables rather than invented as form fields — and creates **one** durable
internal_test intake note against that anchor through the unchanged Phase 34 controlled writer.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite, and
the operator utility is exercised with every role variable scrubbed from the environment so its
dry-run default is proven to open no connection.

**No intake prose lives in this repository.** The writer's standing rule is that note bodies belong
only in the managed DB — never in Git, fixtures, examples, sample packets, logs, or test data. This
harness therefore synthesises a throwaway body at runtime for its temp-SQLite exercise and asserts
that neither the operator utility nor the docs carry note content.

Layers: baseline · taxonomy doc · operator utility · writer behaviour · docs · self-isolation.

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

BASELINE_COMMIT = "1a3d75e"   # Create Phase 59 internal test engagement anchor

TOOL_REL = "tools/create_internal_test_intake_note.py"
HARNESS_REL = "tests/validate_phase60_first_internal_test_intake_note.py"
DOC_REL = "docs/PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md"
TAXONOMY_REL = "docs/PEAK_INTAKE_QUESTION_TAXONOMY_V0.md"
WRITER_REL = "peak/db/intake_note_writer.py"
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
    tmp = tempfile.mkdtemp(prefix="peak_phase60_")
    _tmpdirs.append(tmp)
    return tmp


def temp_sqlite_url() -> str:
    return "sqlite:///" + os.path.join(tmpdir(), "phase60.db")


def synthetic_note_body() -> str:
    """A throwaway body built at runtime. Never written to the repo, never committed."""
    return ("Internal test data only. No real client data. "
            "Synthetic body used to exercise the controlled intake path offline.")


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
    check("no migration 015 or later — Phase 60 adds no migration",
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
    check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx"))


# --------------------------------------------------------------------------- 2. taxonomy


def taxonomy_checks() -> None:
    print("\n2. The intake taxonomy is V0 and derives questions from deliverables")
    check(f"{TAXONOMY_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, TAXONOMY_REL)))
    tx = read(TAXONOMY_REL)
    f = re.sub(r"\s+", " ", tx).lower()

    check("taxonomy says V0 is not the final client-facing questionnaire",
          "not the final client-facing questionnaire" in f)
    check("taxonomy states the derivation rule",
          "supports a downstream decision" in f and "evidence need" in f
          and "report section" in f and "readiness judgment" in f)
    check("taxonomy says questions are not arbitrary form fields",
          "not arbitrary form fields" in f)

    for deliverable in ("inventory / warehouse operations assessment",
                        "prioritized improvement plan", "evidence map",
                        "data / source quality review", "ai / agentnet readiness view",
                        "capsule / publication readiness"):
        check(f"taxonomy names the downstream deliverable: {deliverable}", deliverable in f)

    for n, name in ((1, "engagement context"), (2, "current inventory pain points"),
                    (3, "item / sku master"), (4, "warehouse / facility / location structure"),
                    (5, "receiving, putaway, picking, packing, shipping"),
                    (6, "cycle counts"), (7, "stockouts, overstocks"),
                    (8, "systems of record"), (9, "data exports and reporting"),
                    (10, "sops, approvals, exceptions"), (11, "evidence availability"),
                    (12, "ai / agentnet readiness"),
                    (13, "publication and capsule boundaries"),
                    (14, "success metrics and urgency")):
        check(f"taxonomy category {n}: {name}", name in f)

    check("every category states what it feeds", f.count("**feeds:**".lower()) >= 14)
    check("taxonomy covers AgentNet / capsule readiness",
          "agentnet" in f and "capsule" in f)
    check("taxonomy says future forms are generated from it, not guessed",
          "generated from this taxonomy, not guessed" in f)

    check("taxonomy carries the future GeoSites strategy note", "geosites" in f)
    for term in ("geo/aeo", "structured data", "generative-discovery"):
        check(f"GeoSites note names {term}", term in f)
    check("GeoSites note says questions are derived from deliverables (the reusable rule)",
          "questions are derived from deliverables" in f)
    check("no GeoSites code is built here", "no geosites code" in f)

    # No client-like content of any kind in the taxonomy.
    check("taxonomy names no company, client, or example record",
          not re.search(r"\b(?:acme|contoso|initech|globex|widgets?\s+inc)\b", f)
          and not re.search(r"\b(?:eng|engrec|clnt|intn)_[a-z0-9]{2,}\b", f))
    check("taxonomy embeds no real-looking DSN", not REAL_DSN_RE.search(tx))


# --------------------------------------------------------------------------- 3. operator utility


def tool_checks() -> None:
    print("\n3. The operator utility targets one anchor and stores no intake prose")
    src = read(TOOL_REL)
    code = code_no_docstrings(src)

    check("utility defaults to dry-run — --execute is required to write",
          "--execute" in src and "if not args.execute:" in code)
    check(f"utility targets only engagement {ANCHOR_ID}",
          f'ENGAGEMENT_ID = "{ANCHOR_ID}"' in code
          and not re.search(r'add_argument\("--engagement', src))
    check(f"utility targets only the reserved client {RESERVED_CLIENT_ID}",
          f'CLIENT_ID = "{RESERVED_CLIENT_ID}"' in code
          and not re.search(r'add_argument\("--client', src))
    check("utility invokes only the existing controlled intake-note writer",
          "persist_intake_note_record" in code
          and not re.search(r"persist_(?!intake_note_record)\w+", code))
    check("utility creates no Client, Engagement, evidence, source, report, or capsule record",
          not re.search(r"(?i)\bClient\(|\bEngagement\(|persist_evidence|persist_source|"
                        r"persist_review|persist_agent_run|persist_internal_|publish", code))
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
    # The tool prints the literal label "note_text" alongside <withheld>; what must never appear
    # is the note_text *variable* interpolated into output.
    check("utility never prints the note body",
          "<withheld>" in src
          and not re.search(r"print\([^)]*\{\s*note_text\s*[}:!]", code)
          and not re.search(r"print\(\s*note_text\s*\)", code))
    check("utility refuses a note file inside the repository", "REPO_ROOT + os.sep" in code)
    check("utility embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    # The only caller-supplied value is the note body's location.
    args = set(re.findall(r'add_argument\("(--[a-z-]+)"', src))
    check("utility exposes no record field as a flag — only run mode and body source",
          args <= {"--dry-run", "--execute", "--note-file", "--stdin"})

    # No intake prose is committed in this file. The narrative may mention the categories, but
    # nothing note-shaped: no multi-line prose constant other than the docstring.
    import ast
    tree = ast.parse(src)
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))
    body_like = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and id(n) not in docstring_nodes and len(n.value) > 300]
    check("utility embeds no note-body-sized string constant", not body_like)

    # Dry-run with every role variable scrubbed: proof it opens no connection.
    note_path = os.path.join(tmpdir(), "note.txt")
    with open(note_path, "w", encoding="utf-8") as fh:
        fh.write(synthetic_note_body())
    env = scrubbed_env()
    run = subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL),
                          "--dry-run", "--note-file", note_path],
                         capture_output=True, text=True, timeout=120, env=env)
    check("dry-run exits 0 with no credential in the environment", run.returncode == 0)
    check("dry-run reports no connection was made",
          "database_connection_made        : False" in run.stdout)
    check("dry-run reports nothing was written", "DRY-RUN PASS" in run.stdout)
    check("dry-run withholds the note body",
          "<withheld>" in run.stdout and "Synthetic body used to exercise" not in run.stdout)
    check("dry-run prints no DSN", not REAL_DSN_RE.search(run.stdout))

    # A missing body must stop before validating anything.
    missing = subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL),
                              "--dry-run", "--note-file",
                              os.path.join(tmpdir(), "absent.txt")],
                             capture_output=True, text=True, timeout=120, env=env)
    check("a missing note body stops the run", missing.returncode == 2
          and "NO NOTE BODY" in missing.stdout)

    # A note file inside the repo must be refused.
    inrepo = os.path.join(REPO_ROOT, "README.md")
    refused = subprocess.run([PY, os.path.join(REPO_ROOT, TOOL_REL),
                              "--dry-run", "--note-file", inrepo],
                             capture_output=True, text=True, timeout=120, env=env)
    check("a note file inside the repository is refused",
          refused.returncode == 2 and "inside the repository" in refused.stdout)


# --------------------------------------------------------------------------- 4. writer behaviour


def writer_checks() -> None:
    print("\n4. The writer creates exactly one intake note, and is still create-only")
    code = code_no_docstrings(read(WRITER_REL))
    check("intake-note writer is still create-only",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))
    check("intake-note writer was not modified by this phase",
          not git("diff", "--name-only", "HEAD", "--", WRITER_REL))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import create_internal_test_engagement_anchor as anchor_tool
    import create_internal_test_intake_note as tool
    from peak.db.base import Base
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )
    from peak.db.intake_note_writer import persist_intake_note_record
    from peak.db.models import Client, Engagement, IntakeNoteRecord

    engine = create_engine(temp_sqlite_url())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # The anchor the note attaches to — created by the Phase 59 path, not hand-built.
    anchor = persist_engagement_authorization_anchor(anchor_tool.build_request(),
                                                     session_factory=factory)
    check("the internal_test anchor exists for the note to attach to",
          anchor.outcome == "created" and anchor.engagement_category == "internal_test")

    body = synthetic_note_body()
    receipt = persist_intake_note_record(tool.build_request(body), session_factory=factory)
    check("first invocation creates the intake note", receipt.outcome == "created")
    check("receipt reports one stored record created", receipt.stored_record_created is True)
    check("the note is review-gated and non-final",
          receipt.review_status == "needs_review" and receipt.lifecycle_status == "draft")
    for field in ("client_facing_approved", "financial_verified", "capsule_candidate_ready",
                  "publication_allowed", "execution_allowed"):
        if hasattr(receipt, field):
            check(f"receipt reports {field} is False", getattr(receipt, field) is False)
    check("receipt reports no client-facing output or capsule publication",
          getattr(receipt, "client_facing_output_created", False) is False
          and getattr(receipt, "capsule_publication_made", False) is False
          and getattr(receipt, "agentnet_publication_made", False) is False)
    check("receipt reports no review or agent-run record",
          getattr(receipt, "review_record_created", False) is False
          and getattr(receipt, "agent_run_record_created", False) is False)
    check("receipt reports no update and no delete",
          getattr(receipt, "update_made", False) is False
          and getattr(receipt, "delete_made", False) is False)
    check("receipt never echoes the note body",
          not any(isinstance(v, str) and "Synthetic body used to exercise" in v
                  for v in vars(receipt).values()))

    session = factory()
    check("exactly one intake note row exists", session.query(IntakeNoteRecord).count() == 1)
    check("no Client row was created", session.query(Client).count() == 0)
    check("still exactly one engagement row — no second Engagement was created",
          session.query(Engagement).count() == 1)
    note = session.query(IntakeNoteRecord).one()
    check(f"the note is tied to {ANCHOR_ID} / {RESERVED_CLIENT_ID}",
          note.engagement_id == ANCHOR_ID and note.client_id == RESERVED_CLIENT_ID)
    check("the note carries the internal_peak_only scope",
          note.authorization_scope == "internal_peak_only")
    check("the note's engagement is classified internal_test",
          session.get(Engagement, note.engagement_id).engagement_category == "internal_test")
    session.close()

    # Replay: identical body must not write a second row.
    replay = persist_intake_note_record(tool.build_request(body), session_factory=factory)
    check("identical replay is idempotent, not a second write",
          replay.outcome == "idempotent_replay" and replay.database_write_made is False)
    session = factory()
    check("still exactly one intake note row after replay",
          session.query(IntakeNoteRecord).count() == 1)
    session.close()

    # A changed body under the same idempotency key must conflict, never overwrite.
    conflict = persist_intake_note_record(
        tool.build_request(body + " Changed."), session_factory=factory)
    check("a changed payload under the same idempotency key is denied",
          conflict.reason_code == "idempotency_conflict" and conflict.permitted is False)
    session = factory()
    check("still exactly one intake note row after the conflict",
          session.query(IntakeNoteRecord).count() == 1)
    check("the existing note was not overwritten",
          session.query(IntakeNoteRecord).one().id == receipt.stored_record_id)
    session.close()


# --------------------------------------------------------------------------- 5. docs


def doc_checks() -> None:
    print("\n5. Docs state what was written to production, and what was not")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("doc content checks (skipped: the doc is missing)", False)
        return
    doc = read(DOC_REL)
    f = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", doc, flags=re.MULTILINE).lower())
    for phrase, label in (
        ("one durable internal_test intake note was created in production",
         "one durable internal_test intake note was created in production"),
        (f"{ANCHOR_ID}", "it is tied to internal_test_001"),
        (f"{RESERVED_CLIENT_ID}", "it is tied to client 99999"),
        ("no real client data", "it contains no real client data"),
        ("not client-facing", "it is not client-facing"),
        ("not disposable smoke", "it is not disposable smoke data"),
        ("no client record", "no Client record was created"),
        ("no additional engagement", "no additional Engagement record was created"),
        ("no downstream", "no downstream record was created"),
        ("no capsule", "no capsule was created or published"),
        ("v0 taxonomy", "intake questions are grounded in the V0 taxonomy"),
        ("generated from the taxonomy, not guessed",
         "future forms are generated from the taxonomy"),
        ("geosites", "future GeoSites intake replicates the approach"),
    ):
        check(f"doc states: {label}", phrase in f)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("doc reproduces no intake note body",
          "warehouse walkaround" not in f or "note body" in f)

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md",
                "docs/PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md"):
        blob = re.sub(r"\s+", " ", read(rel)).lower()
        check(f"{os.path.basename(rel)} records the Phase 60 intake note", "phase 60" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase60", "validate-phase60" in mk)
    check("validate depends on validate-phase60",
          re.search(r"^validate:.*validate-phase60", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)
    check("the note-creation utility is not wired into validate",
          "create_internal_test_intake_note" not in mk)


# --------------------------------------------------------------------------- 6. self-isolation


def self_isolation_checks() -> None:
    print("\n6. This harness contacts no production and commits no note prose")
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
    check("this harness writes no note body into the repository",
          not re.search(r'open\(\s*os\.path\.join\(\s*REPO_ROOT[^)]*\)\s*,\s*"w"', src))

    # Nothing note-shaped is committed anywhere this phase touched.
    # Scanned on the files this phase adds as *content*; this harness is excluded because it
    # necessarily contains the detector's own name list.
    for rel in (TOOL_REL, TAXONOMY_REL):
        blob = read(rel)
        check(f"{os.path.basename(rel)} contains no obviously client-like organisation name",
              not re.search(r"(?i)\b(acme|contoso|initech|globex|northwind)\b", blob))
    check("this harness embeds no note-body-sized string constant",
          not [m for m in re.findall(r'"""(.*?)"""|"([^"\n]{300,})"', src, re.S)
               if m[1]])


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 60 intake taxonomy V0 + first internal test intake note check")
    print("=" * 70)
    try:
        baseline_checks()
        taxonomy_checks()

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("\n  [skip] SQLAlchemy not installed — tool/writer layers not exercised.")
            print("         Run: make validate-phase60 PYTHON=.venv/bin/python")
        else:
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
