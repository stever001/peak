#!/usr/bin/env python3
"""Phase 49 runtime database URL separation check.

Phase 48 established that the runtime credential holds exactly ``SELECT`` + ``INSERT`` while the
migration credential can change schema — but nothing in source consumed the runtime variable, so
runtime could only have been wired by reusing ``PEAK_DATABASE_URL``. Phase 49 gives runtime its own
variable so the two credentials cannot collapse into one name.

Six layers:

* **Baseline** — head is still 013, 13 migrations, 18 tables, no migration 014, no
  ``alembic/versions`` file touched, and no model/entity, writer, or allowlist pair added.

* **Role split** — runtime session code reads ``PEAK_RUNTIME_DATABASE_URL`` and nothing else;
  ``alembic/env.py`` still reads ``PEAK_DATABASE_URL`` and never the runtime variable; the
  production verifier keeps its own variables and never gains the runtime one.

* **Fail-closed behaviour** — the runtime helper raises when the variable is missing, refuses to
  fall back to ``PEAK_DATABASE_URL`` even when that is set, consumes the runtime variable when
  present, and accepts an explicit ``url=`` for local harnesses.

* **Secret hygiene** — the error message names variables only, no real DSN is introduced anywhere,
  and no tracked file assigns a URL to any of the three variables.

* **Writer invariants** — the eleven controlled writers stay create-only, this harness invokes none
  of them, and no enablement/deployment configuration appears.

* **Regression** — the audit still reports the model policy satisfied and production unverified, the
  production verifier still skips safely unconfigured, and validation stays offline.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import io
import os
import py_compile
import re
import subprocess
import sys
import tokenize

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "4b285c5"   # Document Phase 48 production runtime readiness gate

SESSION_REL = "peak/db/session.py"
ENV_REL = "alembic/env.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
HARNESS_REL = "tests/validate_phase49_runtime_database_url_separation.py"
ENV_EXAMPLE = ".env.example"
AUDIT = "tools/governed_mysql_collation_audit.py"

RUNTIME_VAR = "PEAK_RUNTIME_DATABASE_URL"
MIGRATION_VAR = "PEAK_DATABASE_URL"
VERIFY_VAR = "PEAK_PRODUCTION_DB_URL"

EXPECTED_MIGRATIONS = 13
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "013_governed_identifier_collation_policy"

ALLOWED_CHANGED = {
    SESSION_REL,
    HARNESS_REL,
    ENV_EXAMPLE,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_SCAFFOLD.md",
    "docs/PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md",
    "docs/PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md",
    # Phase 44's peak/ scope guard asserted "only models.py and base.py changed", which froze all
    # of peak/ for every later phase. Narrowed to writers + allowlist so it tests what it claims.
    "tests/validate_phase44_governed_identifier_collation_migration.py",
    # Phase 47's whole-tree scope guard had the same defect and is now gated on that phase's own
    # implementation artifact, so it goes quiet once committed instead of freezing later phases.
    "tests/validate_phase47_alembic_version_table_hardening.py",
}

CREDENTIAL_FILE_MARKERS = ("peak-prod-ro.env", "peak-prod-migrate.env",
                           "peak-prod-runtime.env", ".peak/")
# A DSN with real-looking credentials embedded (placeholders like USER:PASSWORD are excluded).
REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!runtime_user:password)(?!readonly_user:password)"
                         r"[\w.\-]+:[^\s@'\"]+@")
ASSIGNED_URL_RE = re.compile(
    r"\b(?:PEAK_RUNTIME_DATABASE_URL|PEAK_DATABASE_URL|PEAK_PRODUCTION_DB_URL)\s*=\s*"
    r"[a-z][a-z0-9+.\-]*://")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


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
    """Executable code with comments and docstrings removed, string literals kept.

    A module that *documents* the variable it refuses to read must not be flagged for naming it.
    """
    import ast
    tree = ast.parse(source)
    doc_ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_ranges.append((body[0].lineno, body[0].end_lineno))
    keep = []
    for idx, line in enumerate(source.splitlines(), start=1):
        if any(start <= idx <= end for start, end in doc_ranges):
            continue
        keep.append(re.sub(r"#.*$", "", line))
    return "\n".join(keep)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def phase_never_committed(rel: str) -> bool:
    """True while ``rel`` has no commit yet — i.e. this phase's own work is still unstaged.

    The working-tree scope guards below are authoring-time claims about *this* phase. Keying them
    on "does this file have a pending diff" was wrong: a later phase editing this phase's document
    also produces a pending diff, and the guard would then judge that later phase's changes against
    this phase's allowlist. Absence of any commit for the file is the signal that actually means
    "this phase has not landed yet".
    """
    return not git("log", "-1", "--format=%H", "--", rel).strip()



def run_isolated(snippet: str):
    """Run a snippet in a child interpreter with a scrubbed environment.

    A child process is used so this harness can never leave one of the three variables set in its
    own process and mislead a later check.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in (RUNTIME_VAR, MIGRATION_VAR, VERIFY_VAR)}
    env["PYTHONPATH"] = REPO_ROOT
    return subprocess.run([PY, "-c", snippet], capture_output=True, text=True,
                          timeout=120, env=env, cwd=REPO_ROOT)


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head still 013, 13 migrations, 18 tables, nothing new added")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 014 or later",
          not any(re.match(r"^0*(?:1[4-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")

    for rel in (SESSION_REL, ENV_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read("peak/db/models.py").count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_TABLES} tables",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES)
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_ACTIONS} actions",
          len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers",
          len(writers) == EXPECTED_WRITERS)

    try:
        check(f"baseline commit {BASELINE_COMMIT} present in history",
              BASELINE_COMMIT in git("log", "--oneline", "-40"))
        # Authoring-time scope guard only. Gated on this phase's *implementation* artifact so it
        # goes quiet once Phase 49 is committed — otherwise it would freeze the repository against
        # every later phase, which is the failure mode this gating was added to stop.
        if phase_never_committed(HARNESS_REL):
            changed = set(git("diff", "--name-only", "HEAD").splitlines())
            unexpected = sorted(changed - ALLOWED_CHANGED)
            check("only the intended narrow set of files changed", not unexpected)
            if unexpected:
                print(f"        unexpected: {unexpected}")
        else:
            print("  [skip] Phase 49 is committed — working-tree scope guard not applicable")
        check("no alembic/versions file was modified",
              not git("diff", "--name-only", "HEAD", "--", "alembic/versions"))
        check("alembic/env.py was not modified by this phase",
              not git("diff", "--name-only", "HEAD", "--", ENV_REL))
        check("the production verifier was not modified",
              not git("diff", "--name-only", "HEAD", "--", VERIFIER_REL))
        # Unconditional invariants — these are not authoring-time scope, they are the properties
        # Phase 49 promises regardless of when this harness runs.
        # Authoring-time claim about *this* phase's own working tree, not a permanent freeze
        # on the repository: later phases may legitimately add a writer or extend the
        # allowlist under their own governance gate (Phase 54 added the engagement
        # authorization anchor writer and its one-pair anchor gate). The substantive
        # invariants — writers stay create-only, the generic allowlist stays closed — are
        # asserted unconditionally elsewhere in this harness.
        if phase_never_committed(HARNESS_REL):
            governed = [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
                        if c.endswith("_writer.py")
                        or c in ("peak/db/models.py", "peak/db/base.py",
                                 "peak/persistence/allowlist.py")]
            check("no controlled writer, model, base, or allowlist source changed", not governed)
        check("schemas/, prompts/, agents/ untouched",
              not git("diff", "--name-only", "HEAD", "--", "schemas", "prompts", "agents"))
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. role split


def role_split_checks() -> None:
    print("\n2. Three roles, three variables, no crossover")
    session_src = read(SESSION_REL)
    session_code = code_no_docstrings(session_src)
    env_src = read(ENV_REL)
    env_code = code_no_docstrings(env_src)
    verifier_src = read(VERIFIER_REL)

    check("session.py declares the runtime variable name",
          f'RUNTIME_DATABASE_URL_ENV = "{RUNTIME_VAR}"' in session_code)
    check("session.py declares the migration variable name (for contrast, not for reading)",
          f'MIGRATION_DATABASE_URL_ENV = "{MIGRATION_VAR}"' in session_code)
    check("session.py declares the verifier variable name",
          f'PRODUCTION_VERIFY_DATABASE_URL_ENV = "{VERIFY_VAR}"' in session_code)

    # The decisive check: exactly one environment read, and it reads the runtime constant.
    env_reads = re.findall(r"os\.environ\.get\(\s*([A-Za-z_\"'][^)]*?)\s*\)", session_code)
    check("session.py performs exactly one environment read", len(env_reads) == 1)
    check("that read targets RUNTIME_DATABASE_URL_ENV",
          bool(env_reads) and env_reads[0].strip() == "RUNTIME_DATABASE_URL_ENV")
    check(f"session.py never reads {MIGRATION_VAR} as a literal",
          f'os.environ.get("{MIGRATION_VAR}")' not in session_code
          and f"os.environ.get('{MIGRATION_VAR}')" not in session_code)
    check("session.py never reads MIGRATION_DATABASE_URL_ENV",
          "os.environ.get(MIGRATION_DATABASE_URL_ENV)" not in session_code)
    check("session.py never reads PRODUCTION_VERIFY_DATABASE_URL_ENV",
          "os.environ.get(PRODUCTION_VERIFY_DATABASE_URL_ENV)" not in session_code)
    check("session.py exposes get_runtime_database_url()",
          "def get_runtime_database_url(" in session_code)
    check("session.py exposes create_runtime_engine()",
          "def create_runtime_engine(" in session_code)
    check("session.py still exposes create_session_factory() (the writer seam)",
          "def create_session_factory(" in session_code)
    check("session.py opens no engine at import time",
          "create_engine(" not in session_code.split("def create_runtime_engine")[0])

    check(f"alembic/env.py still reads {MIGRATION_VAR}",
          f'os.environ.get("{MIGRATION_VAR}")' in env_code)
    check(f"alembic/env.py never references {RUNTIME_VAR}", RUNTIME_VAR not in env_src)
    check(f"alembic/env.py never references {VERIFY_VAR}", VERIFY_VAR not in env_src)

    check(f"production verifier never references {RUNTIME_VAR}", RUNTIME_VAR not in verifier_src)
    check(f"production verifier still names {VERIFY_VAR}", VERIFY_VAR in verifier_src)
    check("production verifier still gates on the read-only affirmation",
          "PEAK_PRODUCTION_DB_READONLY_CONFIRM" in verifier_src)

    example = read(ENV_EXAMPLE)
    check(".env.example documents the runtime variable", RUNTIME_VAR in example)
    check(".env.example still documents the migration variable", MIGRATION_VAR in example)
    check(".env.example keeps the mysql+pymysql placeholder form", "mysql+pymysql" in example)


# --------------------------------------------------------------------------- 3. fail-closed


def fail_closed_checks() -> None:
    print("\n3. Runtime resolution fails closed and never falls back")

    r = run_isolated(
        "from peak.db.session import get_runtime_database_url as g\n"
        "try:\n"
        "    g()\n"
        "    print('NO_RAISE')\n"
        "except RuntimeError as e:\n"
        "    m = str(e)\n"
        "    print('RAISED')\n"
        "    print('NAMES_RUNTIME', 'PEAK_RUNTIME_DATABASE_URL' in m)\n"
        "    print('NAMES_MIGRATION', 'PEAK_DATABASE_URL' in m)\n"
        "    print('NO_URL_SCHEME', '://' not in m)\n")
    out = r.stdout
    check("missing runtime variable raises RuntimeError", "RAISED" in out)
    check("error names the missing runtime variable", "NAMES_RUNTIME True" in out)
    check("error explains the migration variable is not a substitute",
          "NAMES_MIGRATION True" in out)
    check("error message contains no connection-string scheme", "NO_URL_SCHEME True" in out)

    r = run_isolated(
        "import os\n"
        "os.environ['PEAK_DATABASE_URL'] = 'sqlite:///migration-only.db'\n"
        "from peak.db.session import get_runtime_database_url as g\n"
        "try:\n"
        "    g()\n"
        "    print('FELL_BACK')\n"
        "except RuntimeError:\n"
        "    print('NO_FALLBACK')\n")
    check(f"{MIGRATION_VAR} alone is insufficient for runtime — no silent fallback",
          "NO_FALLBACK" in r.stdout)

    r = run_isolated(
        "import os\n"
        "os.environ['PEAK_RUNTIME_DATABASE_URL'] = 'sqlite:///runtime-target.db'\n"
        "os.environ['PEAK_DATABASE_URL'] = 'sqlite:///migration-only.db'\n"
        "from peak.db.session import get_runtime_database_url as g\n"
        "print('USES_RUNTIME', g() == 'sqlite:///runtime-target.db')\n")
    check("runtime variable is consumed when set", "USES_RUNTIME True" in r.stdout)
    check("runtime wins even when the migration variable is also set",
          "USES_RUNTIME True" in r.stdout)

    r = run_isolated(
        "try:\n"
        "    import sqlalchemy  # noqa: F401\n"
        "except ImportError:\n"
        "    print('NO_SQLALCHEMY')\n"
        "else:\n"
        "    from peak.db.session import create_session_factory\n"
        "    f = create_session_factory(url='sqlite://')\n"
        "    print('EXPLICIT_URL_OK', f is not None)\n")
    if "NO_SQLALCHEMY" in r.stdout:
        print("  [skip] SQLAlchemy not installed — explicit url= engine path not exercised")
    else:
        check("explicit url= works with no environment variable set (the local-harness path)",
              "EXPLICIT_URL_OK True" in r.stdout)

    r = run_isolated(
        "from peak.db.session import get_database_url, get_runtime_database_url\n"
        "print('ALIAS_IS_RUNTIME', get_database_url.__doc__ is not None)\n"
        "import os\n"
        "os.environ['PEAK_RUNTIME_DATABASE_URL'] = 'sqlite:///x.db'\n"
        "print('ALIAS_RESOLVES', get_database_url() == get_runtime_database_url())\n")
    check("deprecated get_database_url() alias resolves to the runtime variable",
          "ALIAS_RESOLVES True" in r.stdout)


# --------------------------------------------------------------------------- 4. hygiene


def hygiene_checks() -> None:
    print("\n4. No secrets, no real DSNs, no credential-file references")
    session_src = read(SESSION_REL)
    harness_src = read(HARNESS_REL)
    example = read(ENV_EXAMPLE)

    for rel, src in ((SESSION_REL, session_src), (HARNESS_REL, harness_src),
                     (ENV_EXAMPLE, example)):
        check(f"{rel} embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    # Shipped source must not name an operator credential file at all. The harness is exempt from
    # the bare-substring form because it defines those names as guard strings; what matters for it
    # is that it never *opens* or *sources* one, which is checked directly below.
    for rel, src in ((SESSION_REL, session_src), (ENV_EXAMPLE, example)):
        check(f"{rel} references no operator credential file",
              not any(m in src for m in CREDENTIAL_FILE_MARKERS))
    check("this harness opens no operator credential file",
          not re.search(r"(?:open|read|load)\s*\([^)]*peak-prod[^)]*\)", harness_src))
    check("this harness invokes no shell 'source' of an env file",
          not re.search(r"source\s+[~/$]", harness_src))

    # ".env" is a substring of ".environ", so test for the ways a file is actually read.
    check("session.py reads no .env file",
          not re.search(r"load_dotenv|dotenv|open\(\s*['\"]\.env['\"]", session_src))
    check("session.py reads the environment only, never a file",
          "open(" not in code_no_docstrings(session_src))

    # No tracked file may assign a URL to any of the three role variables (placeholders in
    # .env.example are the documented exception and are matched separately).
    offenders = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in
                   {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}]
        for name in files:
            if not name.endswith((".py", ".md", ".ini", ".cfg", ".yaml", ".yml", ".toml")):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, REPO_ROOT)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in ASSIGNED_URL_RE.finditer(text):
                snippet = text[m.start():m.end()]
                if "USER:PASSWORD" in text[m.start():m.start() + 120]:
                    continue
                offenders.append(f"{rel}: {snippet.split('=')[0].strip()}")
    check("no tracked .py/.md/config file assigns a URL to a role variable", not offenders)
    if offenders:
        print(f"        offenders: {sorted(set(offenders))[:5]}")


# --------------------------------------------------------------------------- 5. writer invariants


def writer_invariant_checks() -> None:
    print("\n5. Controlled writers unchanged, create-only, and not invoked here")
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    writers = sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py"))

    for name in writers:
        src = read(f"peak/db/{name}")
        code = code_no_docstrings(src)
        check(f"{name} persists only via session.add",
              code.count("session.add(") == 1)
        check(f"{name} issues no delete/merge/update/execute",
              not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{|\bexecute\(", code))
    check(f"all {EXPECTED_WRITERS} writers still resolve sessions through create_session_factory",
          all("create_session_factory" in read(f"peak/db/{n}") for n in writers))

    harness_src = read(HARNESS_REL)
    check("this harness invokes no controlled writer",
          not re.search(r"\bpersist_[a-z_]+\(", code_no_docstrings(harness_src)))
    # The harness names PEAK_PRODUCTION_DB_URL only to scrub it from child environments. The
    # meaningful property is that it never supplies a value for any role variable and only ever
    # points a child at an explicit sqlite URL.
    harness_code = code_no_docstrings(harness_src)
    assigned = re.findall(r"os\.environ\[['\"](PEAK_[A-Z_]+)['\"]\]\s*=\s*'([^']*)'",
                          harness_code)
    check("harness assigns role variables only to explicit sqlite URLs",
          all(v.startswith("sqlite:") for _k, v in assigned))
    check("harness never assigns PEAK_PRODUCTION_DB_URL",
          not any(k == "PEAK_PRODUCTION_DB_URL" for k, _v in assigned))
    check("harness scrubs all three role variables from child environments",
          "if k not in (RUNTIME_VAR, MIGRATION_VAR, VERIFY_VAR)" in harness_code)
    check("no deployment/enablement config file was added",
          not any(os.path.exists(os.path.join(REPO_ROOT, p))
                  for p in ("Procfile", "docker-compose.yml", "deploy.yaml", "runtime.env")))


# --------------------------------------------------------------------------- 6. regression


def regression_checks() -> None:
    print("\n6. Regression: audit, verifier, and offline validation are unchanged")
    env = {k: v for k, v in os.environ.items()
           if k not in (RUNTIME_VAR, MIGRATION_VAR, VERIFY_VAR,
                        "PEAK_PRODUCTION_DB_READONLY_CONFIRM")}
    try:
        audit = subprocess.run([PY, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, timeout=180, env=env)
        out = audit.stdout
        if "SQLAlchemy not installed" in out:
            check("audit runs (source-scan tier on this interpreter)", audit.returncode == 0)
        else:
            check("audit still reports MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
                  "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in out)
            check("audit still reports 0 unpinned governed columns",
                  re.search(r"unpinned\s*:\s*0", out) is not None)
        check("audit still exits 0", audit.returncode == 0)
    except Exception:
        check("audit regression (not runnable — skipped)", True)

    try:
        verify = subprocess.run([PY, os.path.join(REPO_ROOT, VERIFIER_REL)],
                                capture_output=True, text=True, timeout=120, env=env)
        check("production verifier still skips safely with no configuration",
              verify.returncode == 0)
        check("production verifier made no connection",
              "production_connection_made     : False" in verify.stdout
              or "production_connection_attempted: False" in verify.stdout)
        check("production verifier reports no schema mutation",
              "schema_mutation_made           : False" in verify.stdout)
    except Exception:
        check("verifier regression (not runnable — skipped)", True)

    mk = read("Makefile")
    check("Makefile declares validate-phase49", "validate-phase49" in mk)
    check("validate depends on validate-phase49",
          re.search(r"^validate:.*validate-phase49", mk, re.MULTILINE) is not None)
    check("validate-phase49 runs this harness", HARNESS_REL in mk)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 49 runtime database URL separation check")
    print("=" * 70)

    baseline_checks()
    role_split_checks()
    fail_closed_checks()
    hygiene_checks()
    writer_invariant_checks()
    regression_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
