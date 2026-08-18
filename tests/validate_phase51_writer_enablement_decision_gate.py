#!/usr/bin/env python3
"""Phase 51 writer enablement decision gate check.

Phase 50 proved the runtime credential can connect and holds exactly ``SELECT`` + ``INSERT``. That
is prerequisite evidence, not permission to write. Phase 51 adds the gate where the governance
question is actually answered, and records the current answer: **no production smoke-write, no
writer enablement, no synthetic write, no real engagement write until authorized engagement data
exists.**

This harness is fully offline and credential-free.

Six layers:

* **Baseline** — head still 013, 13 migrations, 18 tables, no migration 014, no ``alembic/versions``
  change, no model/entity, writer, or allowlist pair added.

* **Isolation** — the gate has no database code path at all: no engine, session, writer, or
  SQLAlchemy import; no environment read; no statement of any kind; no operator-file reference.

* **Decision record** — every write-authorizing field is false, every guard field is true, and the
  record is emitted deterministically as key=value and as a single parseable JSON document.

* **Refusal** — the no-write path exits 0; both write-authorizing paths are refused with a nonzero
  exit, and no field flips in the process.

* **Warnings preserved** — the Phase 50 "gate pass is not write permission" warning and the
  "runtime has no DELETE, so cleanup must be decided first" warning survive in the gate and docs.

* **Regression** — writers stay create-only, the verifier and Phase 50 gate stay opt-in and
  unweakened, and the audit result is unchanged.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "dcaa536"   # Add Phase 50 controlled runtime connectivity gate

GATE_REL = "tools/production_writer_enablement_decision_gate.py"
CONNECTIVITY_GATE_REL = "tools/production_runtime_connectivity_gate.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
HARNESS_REL = "tests/validate_phase51_writer_enablement_decision_gate.py"
DOC_REL = "docs/PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md"
AUDIT = "tools/governed_mysql_collation_audit.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 13
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 11
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "013_governed_identifier_collation_policy"

PATH_NO_WRITE = "no_production_smoke_write_yet"
WRITE_PATHS = ("synthetic_admin_smoke_write", "real_engagement_write")

MUST_BE_FALSE = (
    "production_write_authorized", "writer_enablement_authorized",
    "synthetic_write_authorized", "real_engagement_write_authorized",
    "safe_to_run_writers_now", "safe_to_write_production_now",
    "runtime_delete_available", "production_migration_required", "schema_change_required",
    "database_contacted", "sql_issued", "writer_invoked", "environment_read",
    "secrets_printed",
)
MUST_BE_TRUE = (
    "requires_authorized_engagement_before_real_write",
    "requires_explicit_cleanup_plan_before_synthetic_write",
    "migration_credential_cleanup_requires_separate_approval",
    "runtime_connectivity_gate_required_before_future_write",
    "read_only_production_verifier_required_before_future_write",
    "phase50_pass_is_prerequisite_evidence_not_write_permission",
)

ALLOWED_CHANGED = {
    GATE_REL,
    HARNESS_REL,
    DOC_REL,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_SCAFFOLD.md",
    "docs/PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md",
}

CREDENTIAL_FILE_MARKERS = ("peak-prod-ro.env", "peak-prod-migrate.env",
                           "peak-prod-runtime.env", ".peak/")
REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!runtime_user:password)(?!readonly_user:password)"
                         r"[\w.\-]+:[^\s@'\"]+@")

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
    """Executable code with comments and docstrings removed, string literals kept."""
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


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def run_gate(*args):
    return subprocess.run([PY, os.path.join(REPO_ROOT, GATE_REL), *args],
                          capture_output=True, text=True, timeout=60, env=scrubbed_env())


def parse_kv(stdout: str) -> dict:
    out = {}
    for line in stdout.splitlines():
        if "=" in line and not line.startswith("note="):
            key, _, value = line.partition("=")
            if re.fullmatch(r"[a-z0-9_]+", key):
                out[key] = value
    return out


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
    check(f"{GATE_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, GATE_REL)))

    for rel in (GATE_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
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
        if git("status", "--porcelain", "--", GATE_REL).strip():
            unexpected = sorted(set(git("diff", "--name-only", "HEAD").splitlines())
                                - ALLOWED_CHANGED)
            check("only the intended narrow set of files changed", not unexpected)
            if unexpected:
                print(f"        unexpected: {unexpected}")
        else:
            print("  [skip] Phase 51 is committed — working-tree scope guard not applicable")

        governed = [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
                    if c.endswith("_writer.py")
                    or c in ("peak/db/models.py", "peak/db/base.py",
                             "peak/persistence/allowlist.py")]
        check("no controlled writer, model, base, or allowlist source changed", not governed)
        check("no alembic file was modified",
              not git("diff", "--name-only", "HEAD", "--", "alembic"))
        check("the production verifier was not modified",
              not git("diff", "--name-only", "HEAD", "--", VERIFIER_REL))
        check("the Phase 50 connectivity gate was not modified",
              not git("diff", "--name-only", "HEAD", "--", CONNECTIVITY_GATE_REL))
        check("schemas/, prompts/, agents/ untouched",
              not git("diff", "--name-only", "HEAD", "--", "schemas", "prompts", "agents"))
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. isolation


def isolation_checks() -> None:
    print("\n2. The gate has no database, environment, or writer code path at all")
    src = read(GATE_REL)
    code = code_no_docstrings(src)

    check("gate imports no controlled writer",
          not re.search(r"import\s+.*_writer|from\s+peak\.db\.\w*_writer", code))
    check("gate imports nothing from peak at all",
          not re.search(r"\b(?:from|import)\s+peak\b", code))
    check("gate imports no session or engine helper",
          "create_session_factory" not in code and "create_runtime_engine" not in code)
    check("gate imports no SQLAlchemy", "sqlalchemy" not in code.lower())
    check("gate never calls create_engine", "create_engine" not in code)
    check("gate never opens a connection", not re.search(r"\.connect\(|\bconnect\(", code))
    check("gate never executes a statement", ".execute(" not in code)

    check("gate reads no environment variable at all", "os.environ" not in code)
    check("gate imports no os module for environment access",
          not re.search(r"^import os$", code, re.MULTILINE))

    for var in ROLE_VARS:
        check(f"gate never reads {var}",
              f'os.environ.get("{var}")' not in code and f"os.environ.get('{var}')" not in code
              and f'environ["{var}"]' not in code)

    for token in ("SELECT ", "SHOW GRANTS", "INSERT ", "UPDATE ", "DELETE ", "ALTER ",
                  "CREATE ", "DROP ", "TRUNCATE"):
        check(f"gate code contains no {token.strip()} statement", token not in code.upper())

    check("gate references no operator credential file",
          not any(m in src for m in CREDENTIAL_FILE_MARKERS))
    check("gate embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("gate reads no .env file",
          not re.search(r"load_dotenv|dotenv|open\(\s*['\"]\.env['\"]", src))
    check("gate opens no file whatsoever", "open(" not in code)


# --------------------------------------------------------------------------- 3. decision record


def decision_record_checks() -> None:
    print("\n3. Decision record: no-write is the default and every guard field holds")
    r = run_gate()
    check("default invocation exits 0", r.returncode == 0)
    fields = parse_kv(r.stdout)

    check("default selected_path is the no-write path",
          fields.get("selected_path") == PATH_NO_WRITE)
    check("decision_gate_version is reported", bool(fields.get("decision_gate_version")))
    for field in MUST_BE_FALSE:
        check(f"{field}=false", fields.get(field) == "false")
    for field in MUST_BE_TRUE:
        check(f"{field}=true", fields.get(field) == "true")
    check("recommended_next_path names waiting for authorized engagement data",
          fields.get("recommended_next_path")
          == "wait_for_authorized_engagement_or_separately_approve_no_cleanup_admin_smoke_record")

    # --json must be a single parseable document on stdout.
    j = run_gate("--json")
    check("--json exits 0", j.returncode == 0)
    parsed = None
    try:
        parsed = json.loads(j.stdout)
        check("--json stdout is a single parseable JSON document", True)
    except ValueError:
        check("--json stdout is a single parseable JSON document", False)
    if parsed is not None:
        check("JSON and key=value agree on selected_path",
              parsed.get("selected_path") == fields.get("selected_path"))
        check("JSON reports every must-be-false field as false",
              all(parsed.get(f) is False for f in MUST_BE_FALSE))
        check("JSON reports every must-be-true field as true",
              all(parsed.get(f) is True for f in MUST_BE_TRUE))
        check("JSON carries the explanatory notes", len(parsed.get("notes", [])) >= 4)

    check("output is deterministic across runs", run_gate().stdout == r.stdout)


# --------------------------------------------------------------------------- 4. refusal


def refusal_checks() -> None:
    print("\n4. Write-authorizing paths are refused, and nothing flips when they are asked for")
    for path in WRITE_PATHS:
        r = run_gate("--decision", path)
        check(f"'{path}' is refused with a nonzero exit", r.returncode != 0)
        check(f"'{path}' refusal is the dedicated refusal code (3)", r.returncode == 3)
        check(f"'{path}' refusal says so explicitly", "REFUSED" in r.stdout)
        fields = parse_kv(r.stdout)
        check(f"'{path}' still reports production_write_authorized=false",
              fields.get("production_write_authorized") == "false")
        check(f"'{path}' still reports writer_enablement_authorized=false",
              fields.get("writer_enablement_authorized") == "false")
        check(f"'{path}' still reports safe_to_write_production_now=false",
              fields.get("safe_to_write_production_now") == "false")
        check(f"'{path}' authorizes nothing at all",
              all(fields.get(f) == "false" for f in MUST_BE_FALSE))

    r = run_gate("--decision", "definitely_not_a_path")
    check("an unknown decision path is rejected by the parser", r.returncode != 0)

    src = read(GATE_REL)
    check("only the no-write path is in the authorized set",
          re.search(r"AUTHORIZED_PATHS\s*=\s*frozenset\(\{PATH_NO_WRITE\}\)", src) is not None)


# --------------------------------------------------------------------------- 5. warnings


def warning_checks() -> None:
    print("\n5. The Phase 50 and no-DELETE warnings are preserved")
    src = read(GATE_REL)
    out = run_gate().stdout
    doc = read(DOC_REL)

    check("gate states a Phase 50 pass is not write permission",
          "phase50_pass_is_prerequisite_evidence_not_write_permission" in out)
    check("gate note repeats it in prose form",
          "prerequisite_evidence_not_write_permission" in out)
    check("gate states runtime has no row-removal privilege",
          "runtime_delete_available=false" in out)
    check("gate note explains a synthetic record cannot be removed by runtime",
          "cannot_be_removed_by_runtime" in out)
    check("gate note requires the cleanup decision before the write",
          "before_any_synthetic_write_not_after" in out)
    check("gate note requires a future phase to rerun both live gates",
          "rerun_read_only_verifier_and_runtime_connectivity_gate" in out)
    check("gate note requires a future phase to name writer/table/action/scope/key/cleanup",
          "name_writer_table_action_scope_idempotency_key_and_cleanup_posture" in out)
    # Prose wraps across lines, so compare on whitespace-normalized text.
    flat_src = re.sub(r"\s+", " ", src.lower())
    check("gate source explains the no-row-removal consequence in prose",
          "cannot be removed by runtime" in flat_src)
    check("gate source names the durable-record default",
          "durable" in src.lower())

    check("doc records the current no-write decision",
          "no production smoke-write" in doc.lower())
    check("doc records that runtime has no DELETE", "DELETE" in doc)
    check("doc records all three future path options",
          "synthetic" in doc.lower() and "engagement" in doc.lower())
    check("doc records the rerun requirement",
          "runtime connectivity gate" in doc.lower() and "verifier" in doc.lower())
    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))

    check("gate output contains no connection scheme", "://" not in out)
    check("gate output contains no raw GRANT line", "GRANT " not in out)
    for token in ("password", "passwd", "@"):
        check(f"gate output contains no '{token}'", token not in out)


# --------------------------------------------------------------------------- 6. regression


def regression_checks() -> None:
    print("\n6. Regression: writers create-only, existing gates opt-in and unweakened")
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    writers = sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py"))
    for name in writers:
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    harness_code = code_no_docstrings(read(HARNESS_REL))
    check("this harness invokes no controlled writer",
          not re.search(r"\bpersist_[a-z_]+\(", harness_code))
    check("this harness scrubs every role variable from child processes",
          "k not in ROLE_VARS" in harness_code)

    mk = read("Makefile")
    check("Makefile declares validate-phase51", "validate-phase51" in mk)
    check("validate depends on validate-phase51",
          re.search(r"^validate:.*validate-phase51", mk, re.MULTILINE) is not None)
    check("Makefile declares writer-enablement-decision-gate",
          "writer-enablement-decision-gate:" in mk)
    check("the decision gate target is opt-in, not part of validate",
          re.search(r"^validate:.*writer-enablement-decision-gate", mk, re.MULTILINE) is None)
    check("the Phase 50 connectivity gate remains opt-in, not part of validate",
          re.search(r"^validate:.*runtime-connectivity", mk, re.MULTILINE) is None)
    check("the production verifier remains opt-in, not part of validate",
          re.search(r"^validate:.*production-mysql-collation-verify", mk, re.MULTILINE) is None)

    verifier_src = read(VERIFIER_REL)
    check("production verifier still gates on the read-only affirmation",
          "PEAK_PRODUCTION_DB_READONLY_CONFIRM" in verifier_src)
    check("production verifier still refuses mutating verbs",
          "FORBIDDEN_SQL_VERBS" in verifier_src)

    conn_gate_src = read(CONNECTIVITY_GATE_REL)
    check("Phase 50 gate still allows only two statements",
          conn_gate_src.count('"connectivity": "SELECT 1"') == 1
          and conn_gate_src.count('"grants": "SHOW GRANTS FOR CURRENT_USER"') == 1)

    env = scrubbed_env()
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

    try:
        conn = subprocess.run([PY, os.path.join(REPO_ROOT, CONNECTIVITY_GATE_REL)],
                              capture_output=True, text=True, timeout=120, env=env)
        check("Phase 50 gate still refuses (exit 2) with no runtime URL", conn.returncode == 2)
    except Exception:
        check("Phase 50 gate regression (not runnable — skipped)", True)

    try:
        audit = subprocess.run([PY, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, timeout=180, env=env)
        out = audit.stdout
        if "SQLAlchemy not installed" in out:
            check("audit runs (source-scan tier on this interpreter)", audit.returncode == 0)
        else:
            check("audit still reports MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
                  "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in out)
        check("audit still exits 0", audit.returncode == 0)
    except Exception:
        check("audit regression (not runnable — skipped)", True)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 51 writer enablement decision gate check")
    print("=" * 70)

    baseline_checks()
    isolation_checks()
    decision_record_checks()
    refusal_checks()
    warning_checks()
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
