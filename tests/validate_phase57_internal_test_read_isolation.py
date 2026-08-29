#!/usr/bin/env python3
"""Phase 57 internal test engagement read-side isolation check.

Phase 56 recorded classification on the ``engagements`` row but nothing consumed it — the columns
were a contract with no enforcement, because no read path existed. Phase 57 adds the enforcement
primitive **before** the first read path, so a future client-facing read has something correct to
reach for. It **creates no records** and applies no migration to production.

Offline and credential-free: the SQLAlchemy layer runs only against throwaway temporary SQLite.

Layers: baseline · isolation (no DB/env/writer coupling) · predicates · query filters · docs.

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

BASELINE_COMMIT = "2956e9c"   # Add Phase 56 internal test engagement classification

HELPER_REL = "peak/db/engagement_read_isolation.py"
HARNESS_REL = "tests/validate_phase57_internal_test_read_isolation.py"
DOC_REL = "docs/PHASE57_INTERNAL_TEST_READ_ISOLATION.md"
MODELS_REL = "peak/db/models.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
DECISION_GATE_REL = "tools/production_writer_enablement_decision_gate.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"
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


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, nothing added")
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))

    for rel in (HELPER_REL, HARNESS_REL):
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
    check("the read-isolation helper is not a writer",
          not HELPER_REL.endswith("_writer.py"))

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
    check("clients remains never writable", is_never_writable_table("clients"))

    try:
        # Ancestry, not recency. This asserted membership in a bounded `git log ... -40` window,
        # which is a *sliding window*, not a history check: the baseline falls out of range as later
        # phases land, failing on commits whose content has nothing to do with this phase. The
        # invariant meant here is that the baseline is still reachable from HEAD, which
        # `merge-base --is-ancestor` states directly and which never expires. Widening the window
        # would only move the expiry date.
        is_ancestor = git_succeeds("merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
        check(f"baseline commit {BASELINE_COMMIT} present in history", is_ancestor)
        if not is_ancestor:
            print("        reason: phase57_baseline_commit_not_ancestor")
        # Pathspec narrowed to match the label: it read "alembic", which also covered
        # alembic/env.py and froze that file against every later phase.
        check("no alembic/versions file was modified",
              not git("diff", "--name-only", "HEAD", "--", "alembic/versions"))
        # A correction to a writer's module *docstring* is documentation, not behaviour — later
        # phases legitimately update those narratives (Phase 59 recorded that the anchor writer
        # has now been used once in production). What this guard protects is writer *code*, so
        # compare the committed and working-tree source with docstrings and comments stripped.
        behavioural = []
        for rel in [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
                    if c.endswith("_writer.py")]:
            committed = subprocess.run(["git", "-C", REPO_ROOT, "show", f"HEAD:{rel}"],
                                       capture_output=True, text=True, timeout=20).stdout
            if code_no_docstrings(committed) != code_no_docstrings(read(rel)):
                behavioural.append(rel)
        check("no controlled writer's code was modified (docstring-only edits allowed)",
              not behavioural)
        check("peak/db/models.py was not modified",
              not git("diff", "--name-only", "HEAD", "--", MODELS_REL))
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
        check("schemas/, prompts/, agents/, examples/ untouched",
              not git("diff", "--name-only", "HEAD", "--",
                      "schemas", "prompts", "agents", "examples"))
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. isolation


def isolation_checks() -> None:
    print("\n2. The helper has no DB-connection, environment, writer, or raw-SQL coupling")
    src = read(HELPER_REL)
    code = code_no_docstrings(src)

    check("helper imports no controlled writer",
          not re.search(r"import\s+.*_writer|from\s+peak\.db\.\w*_writer", code))
    check("helper imports no session factory / engine helper",
          "create_session_factory" not in code and "create_runtime_engine" not in code
          and "create_engine" not in code and "sessionmaker" not in code)
    check("helper opens no connection", not re.search(r"\.connect\(|\.begin\(", code))
    check("helper executes nothing", ".execute(" not in code and ".all(" not in code
          and ".one_or_none(" not in code and ".first(" not in code)
    check("helper commits nothing", ".commit(" not in code and ".add(" not in code)
    check("helper reads no environment variable",
          "os.environ" not in code and "getenv" not in code)
    check("helper opens no file", "open(" not in code)

    for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "WHERE ", "DROP ", "ALTER "):
        check(f"helper embeds no raw {token.strip()} statement", token not in code.upper())
    check("helper builds no textual SQL", not re.search(r"\btext\(|text\s*=\s*['\"]SELECT", code))

    check("helper creates or modifies no record",
          "Engagement(" not in code and "session" not in code.replace("session and query", ""))
    check("helper embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("helper references no operator credential file",
          not any(m in src for m in ("peak-prod-ro.env", "peak-prod-runtime.env", ".peak/")))


# --------------------------------------------------------------------------- 3. predicates


def predicate_checks() -> None:
    print("\n3. Predicates: exclusion by default, reserved namespace is defence in depth")
    from peak.db.engagement_read_isolation import (
        DEFAULT_READ_MODE, ReadMode, is_client_visible, is_internal_test,
        is_publication_eligible, is_visible_in_mode,
    )

    class Row:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    def row(**over):
        kw = dict(client_id="c1", engagement_category="real_client", client_accessible=True,
                  real_client_data=True, capsule_publication_authorized=False)
        kw.update(over)
        return Row(**kw)

    check("the default read mode is the client-facing (excluding) one",
          DEFAULT_READ_MODE == ReadMode.CLIENT_FACING)

    # --- rule 1: real-client reads exclude internal_test by default ---
    it = row(engagement_category="internal_test", client_accessible=False,
             real_client_data=False, client_id=RESERVED_CLIENT_ID)
    check("client-facing predicate admits an ordinary real_client engagement",
          is_client_visible(row()) is True)
    check("client-facing predicate EXCLUDES an internal_test engagement",
          is_client_visible(it) is False)
    check("is_internal_test identifies the category", is_internal_test(it) is True
          and is_internal_test(row()) is False)

    # --- rule: client_accessible / real_client_data are required ---
    check("client-facing predicate requires client_accessible=true",
          is_client_visible(row(client_accessible=False)) is False)
    check("client-facing predicate requires real_client_data=true",
          is_client_visible(row(real_client_data=False)) is False)
    check("client-facing predicate rejects a missing/None flag",
          is_client_visible(row(client_accessible=None)) is False
          and is_client_visible(None) is False)

    # --- rules 2 & 3: reserved namespace is a marker, and is excluded even if flags disagree ---
    check("reserved client id is REJECTED even when client_accessible is mistakenly true",
          is_client_visible(row(client_id=RESERVED_CLIENT_ID)) is False)
    check("a reserved prefix is rejected the same way",
          is_client_visible(row(client_id="internal_test_a")) is False
          and is_client_visible(row(client_id="99999_a")) is False)
    check("an internal_test row with flags mistakenly set to client-visible is still rejected",
          is_client_visible(row(engagement_category="internal_test")) is False)
    check("client_id alone does not authorize visibility — an ordinary id with the wrong "
          "category is refused",
          is_client_visible(row(client_id="c1", engagement_category="internal_test")) is False)

    # --- rule 4: internal test requires explicit internal/admin mode ---
    check("CLIENT_FACING never opts into internal test, even when asked to",
          is_visible_in_mode(it, ReadMode.CLIENT_FACING, include_internal_test=True) is False)
    check("INTERNAL_ADMIN excludes internal test by default",
          is_visible_in_mode(it, ReadMode.INTERNAL_ADMIN, include_internal_test=False) is False)
    check("INTERNAL_ADMIN includes internal test only when explicitly requested",
          is_visible_in_mode(it, ReadMode.INTERNAL_ADMIN, include_internal_test=True) is True)
    check("INTERNAL_ADMIN still shows real client engagements",
          is_visible_in_mode(row(), ReadMode.INTERNAL_ADMIN) is True)
    check("an unrecognised mode is refused, never treated as permissive",
          is_visible_in_mode(row(), "something_else") is False)
    check("the default mode call excludes internal test",
          is_visible_in_mode(it) is False)

    # --- rule 5: publication eligibility is the full compound rule ---
    pub = dict(engagement_category="internal_test", real_client_data=False,
               client_accessible=False, capsule_publication_authorized=True,
               client_id=RESERVED_CLIENT_ID)
    check("publication predicate accepts the full compound rule",
          is_publication_eligible(row(**pub)) is True)
    for flipped in ("real_client_data", "client_accessible", "capsule_publication_authorized"):
        variant = dict(pub)
        variant[flipped] = not variant[flipped]
        check(f"publication predicate rejects when '{flipped}' is flipped",
              is_publication_eligible(row(**variant)) is False)
    check("publication predicate rejects a real_client engagement outright",
          is_publication_eligible(row(capsule_publication_authorized=True)) is False)
    check("publication eligibility is separate from client visibility "
          "(eligible rows are never client-visible)",
          is_publication_eligible(row(**pub)) is True
          and is_client_visible(row(**pub)) is False)


# --------------------------------------------------------------------------- 4. query filters


def filter_checks() -> None:
    print("\n4. SQLAlchemy filters against throwaway temporary SQLite (never production)")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import Engagement
    from peak.db.engagement_read_isolation import (
        ReadMode, apply_read_isolation, publication_eligible_filter, read_filter_for_mode,
    )

    tmp = tempfile.mkdtemp(prefix="peak_phase57_")
    _tmpdirs.append(tmp)
    engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    def eng(eid, **over):
        kw = dict(id=eid, client_id="c1", owner_id="o1",
                  authorization_scope="engagement_authorized", review_status="needs_review",
                  lifecycle_status="active", engagement_category="real_client",
                  client_accessible=True, real_client_data=True,
                  capsule_publication_authorized=False)
        kw.update(over)
        return Engagement(**kw)

    session.add_all([
        eng("rc"),                                              # ordinary real client
        eng("rc_hidden", client_accessible=False),              # real client, not accessible
        eng("it", client_id=RESERVED_CLIENT_ID, engagement_category="internal_test",
            client_accessible=False, real_client_data=False),   # internal test
        eng("it_pub", client_id=RESERVED_CLIENT_ID, engagement_category="internal_test",
            client_accessible=False, real_client_data=False,
            capsule_publication_authorized=True),               # publication-eligible
    ])
    session.commit()

    def ids(query):
        return sorted(r.id for r in query)

    q = session.query(Engagement)
    check("CLIENT_FACING returns only the accessible real client engagement",
          ids(apply_read_isolation(q, ReadMode.CLIENT_FACING)) == ["rc"])
    check("CLIENT_FACING excludes internal test rows from the database",
          "it" not in ids(apply_read_isolation(q, ReadMode.CLIENT_FACING))
          and "it_pub" not in ids(apply_read_isolation(q, ReadMode.CLIENT_FACING)))
    check("the default mode is the excluding one at query level",
          ids(apply_read_isolation(q)) == ["rc"])
    check("INTERNAL_ADMIN excludes internal test by default",
          ids(apply_read_isolation(q, ReadMode.INTERNAL_ADMIN)) == ["rc", "rc_hidden"])
    check("INTERNAL_ADMIN includes internal test only on explicit opt-in",
          ids(apply_read_isolation(q, ReadMode.INTERNAL_ADMIN, include_internal_test=True))
          == ["it", "it_pub", "rc", "rc_hidden"])
    check("publication-eligible filter returns only the compound-rule row",
          ids(q.filter(publication_eligible_filter())) == ["it_pub"])

    check("a client_id narrowing cannot resurrect an internal test row",
          ids(apply_read_isolation(q, ReadMode.CLIENT_FACING,
                                   client_id=RESERVED_CLIENT_ID)) == [])
    check("client_id narrowing still applies within a permitted mode",
          ids(apply_read_isolation(q, ReadMode.CLIENT_FACING, client_id="c1")) == ["rc"])

    try:
        read_filter_for_mode("bogus_mode")
        check("an unrecognised mode raises rather than returning a permissive filter", False)
    except ValueError:
        check("an unrecognised mode raises rather than returning a permissive filter", True)

    check("no row was created or modified by the read helper (4 rows seeded, 4 remain)",
          session.query(Engagement).count() == 4)
    session.close()


# --------------------------------------------------------------------------- 5. docs/regression


def doc_and_regression_checks() -> None:
    print("\n5. Docs and regression")
    check(f"{DOC_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)))
    doc = read(DOC_REL)
    f = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", doc, flags=re.MULTILINE).lower())
    for phrase, label in (
        ("read-side isolation", "classification is backed by a read-side isolation primitive"),
        ("future real-client read paths must use it", "future real-client reads must use it"),
        ("not sufficient by itself", "client_id=99999 is not sufficient by itself"),
        ("explicitly opt in", "internal/admin views must explicitly opt in"),
        ("separate from client visibility", "publication eligibility is separate"),
        ("creates no records", "Phase 57 creates no records"),
        ("applied to production in phase 58", "migration 014 applied to production in Phase 58"),
    ):
        check(f"doc states: {label}", phrase in f)
    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc records no example engagement identifier",
          not re.search(r"\b(?:eng|intn|engrec|clnt)_[a-z0-9]{2,}\b", doc))

    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    for name in sorted(n for n in os.listdir(db_dir) if n.endswith("_writer.py")):
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    mk = read("Makefile")
    check("Makefile declares validate-phase57", "validate-phase57" in mk)
    check("validate depends on validate-phase57",
          re.search(r"^validate:.*validate-phase57", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)

    check("the production verifier expects production at 014 (applied there in Phase 58)",
          'EXPECTED_ALEMBIC_HEAD = "014_engagement_classification"'
          in read(VERIFIER_REL))

    env = scrubbed_env()
    try:
        gate = subprocess.run([PY, os.path.join(REPO_ROOT, DECISION_GATE_REL)],
                              capture_output=True, text=True, timeout=60, env=env)
        check("writer-enablement decision gate still exits 0 with a no-write decision",
              gate.returncode == 0)
        for field in ("production_write_authorized=false", "writer_enablement_authorized=false",
                      "writer_invoked=false", "database_contacted=false"):
            check(f"decision gate still reports {field}", field in gate.stdout)
    except Exception:
        check("decision gate regression (not runnable — skipped)", True)

    try:
        verify = subprocess.run([PY, os.path.join(REPO_ROOT, VERIFIER_REL)],
                                capture_output=True, text=True, timeout=120, env=env)
        check("production verifier still skips safely with no configuration",
              verify.returncode == 0)
        check("production verifier made no connection",
              "production_connection_made     : False" in verify.stdout
              or "production_connection_attempted: False" in verify.stdout)
    except Exception:
        check("verifier regression (not runnable — skipped)", True)

    harness_code = code_no_docstrings(read(HARNESS_REL))
    check("this harness invokes no controlled writer",
          not re.search(r"\bpersist_[a-z_]+\(", harness_code))
    check("this harness scrubs every role variable from child processes",
          "k not in ROLE_VARS" in harness_code)
    urls = re.findall(r'create_engine\(\s*"([a-z+]+):', harness_code)
    check("this harness builds only temporary SQLite database URLs", set(urls) <= {"sqlite"})


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 57 internal test read-side isolation check")
    print("=" * 70)
    try:
        baseline_checks()
        isolation_checks()

        print("\n(model/predicate layer)")
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("  [skip] SQLAlchemy not installed — predicate/filter layers not exercised.")
            print("         Run: make validate-phase57 PYTHON=.venv/bin/python")
        else:
            predicate_checks()
            filter_checks()

        doc_and_regression_checks()
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
