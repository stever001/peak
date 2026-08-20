#!/usr/bin/env python3
"""Phase 58 production migration 014 verification check.

Phase 58 applied migration ``014_engagement_classification`` **to production** — a schema change
only. This harness pins the posture that followed: the production verifier's expected head moved
013 -> 014, migration 014 itself stayed additive and data-free, no writer was enabled, and the docs
state plainly what was and was not done to production.

Offline and credential-free. It **opens no database connection**, reads no ``.env``, invokes no
writer, runs no migration, and prints no environment value. Every role variable is scrubbed from
child processes.

Layers: baseline · migration shape · verifier head pin · decision gate · docs.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "3861626"   # Add Phase 57 internal test read isolation

HARNESS_REL = "tests/validate_phase58_production_014_verification.py"
DOC_REL = "docs/PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md"
MIGRATION_REL = "alembic/versions/014_engagement_classification.py"
MODELS_REL = "peak/db/models.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
DECISION_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
ISOLATION_REL = "peak/db/engagement_read_isolation.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"
PRIOR_REVISION = "013_governed_identifier_collation_policy"

#: The four classification columns migration 014 puts on ``engagements`` in production.
CLASSIFICATION_COLUMNS = ("engagement_category", "real_client_data", "client_accessible",
                          "capsule_publication_authorized")

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
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


def code_no_strings(source: str) -> str:
    """``code_no_docstrings`` plus every string literal blanked.

    The self-isolation checks below scan this file for connection/writer/``.env`` markers. Those
    markers appear here as *search patterns* inside string literals, so they must be removed before
    scanning or the harness would report itself.
    """
    import ast

    class _Blank(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                return ast.copy_location(ast.Constant(value=""), node)
            return node

    tree = ast.fix_missing_locations(_Blank().visit(ast.parse(source)))
    return ast.unparse(tree)   # unparse also drops comments, so scan patterns cannot hide there


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
    check("no migration 015 or later — Phase 58 applied 014, it did not write a successor",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))

    try:
        py_compile.compile(os.path.join(REPO_ROOT, HARNESS_REL), doraise=True)
        check(f"{HARNESS_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{HARNESS_REL} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("the read-side isolation primitive still exists",
          os.path.isfile(os.path.join(REPO_ROOT, ISOLATION_REL)))

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_prohibited_table,
    )
    check("generic allowlist unchanged — no pair added",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES
          and len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("still exactly one anchor-creation pair", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check("engagements remains prohibited generically",
          is_prohibited_table("engagements") and not is_allowed_table("engagements"))


# --------------------------------------------------------------------------- 2. migration shape


def migration_checks() -> None:
    print("\n2. Migration 014 is additive, data-free, and is what production received")
    mig = read(MIGRATION_REL)
    code = code_no_docstrings(mig)
    check(f'revision is "{HEAD_REVISION}"', f'revision = "{HEAD_REVISION}"' in mig)
    check(f'down_revision is "{PRIOR_REVISION}"',
          f'down_revision = "{PRIOR_REVISION}"' in mig)
    for column in CLASSIFICATION_COLUMNS:
        check(f"014 adds engagements.{column}", f'"{column}"' in code)
    check("014 adds the engagement_category index",
          "create_index" in code and "engagement_category" in code)
    check("014 pins the governed collation on engagement_category",
          "utf8mb4_bin" in mig)

    check("014 issues no INSERT, seed data, or bulk_insert",
          not re.search(r"(?i)\bbulk_insert\b|\binsert\(|INSERT\s+INTO", code))
    check("014 drops no table and removes no column on upgrade",
          "drop_table" not in code.split("def downgrade")[0]
          and "drop_column" not in code.split("def downgrade")[0])
    check("014 executes no raw SQL", "op.execute(" not in code)
    check("014 touches only the engagements table",
          set(re.findall(r'op\.\w+\(\s*\n?\s*(?:TABLE|"(\w+)")', code)) <= {"engagements", ""})
    check("014 imports no application code", "from peak" not in code)

    check("this harness runs no migration",
          not re.search(r"alembic\s+upgrade|command\.upgrade|op\.add_column",
                        code_no_strings(read(HARNESS_REL))))


# --------------------------------------------------------------------------- 3. verifier posture


def verifier_checks() -> None:
    print("\n3. The production verifier now expects production at 014")
    tool = read(VERIFIER_REL)
    check('EXPECTED_ALEMBIC_HEAD is "014_engagement_classification"',
          f'EXPECTED_ALEMBIC_HEAD = "{HEAD_REVISION}"' in tool)
    check("the verifier no longer pins production at 013",
          f'EXPECTED_ALEMBIC_HEAD = "{PRIOR_REVISION}"' not in tool)
    check("the head pin is documented as tracking the live production head, not the repo head",
          re.search(r"(?i)live posture|live production head", tool) is not None)
    check("the verifier still gates on the read-only affirmation",
          "PEAK_PRODUCTION_DB_READONLY_CONFIRM" in tool)
    check("the verifier still performs no schema mutation, write, or migration",
          "no schema mutation" in tool and "no migration" in tool)

    code = code_no_docstrings(tool)
    check("the verifier issues no INSERT/UPDATE/DELETE/ALTER",
          not re.search(r"(?i)\b(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|ALTER\s+TABLE)\b", code))
    check("the verifier imports and invokes no writer",
          "persist_" not in code and "_writer" not in code)

    # engagement_category must be covered by the governed (deterministic) posture in production.
    try:
        from governed_mysql_collation_audit import DETERMINISTIC_REQUIRED, classify
    except ImportError:
        check("engagement_category is a governed column the verifier covers", False)
    else:
        check("engagement_category is a governed column the verifier covers",
              classify("engagement_category", "String") in DETERMINISTIC_REQUIRED)

    # The harnesses that pin or assert the production head must agree with the tool.
    # They may still name migration 013 in other contexts; what must not survive is a
    # *production head* pinned or asserted at 013.
    for rel in ("tests/validate_phase43_production_mysql_collation_verification.py",
                "tests/validate_phase56_internal_test_engagement_support.py",
                "tests/validate_phase57_internal_test_read_isolation.py"):
        src = read(rel)
        name = os.path.basename(rel)
        check(f"{name} pins no production head at 013",
              f'PRODUCTION_ALEMBIC_HEAD = "{PRIOR_REVISION}"' not in src
              and f'EXPECTED_ALEMBIC_HEAD = "{PRIOR_REVISION}"' not in src)
        check(f"{name} agrees production is at {HEAD_REVISION}", HEAD_REVISION in src)


# --------------------------------------------------------------------------- 4. decision gate


def decision_gate_checks() -> None:
    print("\n4. No writer was enabled and no production write is authorized")
    env = scrubbed_env()
    try:
        gate = subprocess.run([PY, os.path.join(REPO_ROOT, DECISION_GATE_REL)],
                              capture_output=True, text=True, timeout=60, env=env)
        check("writer-enablement decision gate still exits 0 with a no-write decision",
              gate.returncode == 0)
        for field in ("production_write_authorized=false", "writer_enablement_authorized=false",
                      "writer_invoked=false", "database_contacted=false",
                      "secrets_printed=false"):
            check(f"decision gate still reports {field}", field in gate.stdout)
    except (OSError, subprocess.SubprocessError) as exc:
        check(f"writer-enablement decision gate runs ({type(exc).__name__})", False)

    for name in sorted(n for n in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                       if n.endswith("_writer.py")):
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))


# --------------------------------------------------------------------------- 5. docs


def doc_checks() -> None:
    print("\n5. Docs state the Phase 58 production posture")
    check(f"{DOC_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)))
    doc = read(DOC_REL)
    f = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", doc, flags=re.MULTILINE).lower())
    for phrase, label in (
        ("migration 014 was applied to production in phase 58",
         "migration 014 was applied to production in Phase 58"),
        ("production schema now supports the engagement classification fields",
         "production schema now supports Engagement classification fields"),
        ("expected head is now `014", "production verifier expected head is now 014"),
        ("no production application record was created",
         "no production app records were created"),
        ("no internal test engagement was created",
         "no internal test engagement was created"),
        ("separately approved", "first internal test engagement anchor remains separately approved"),
        ("future client-facing paths must actually use it",
         "read-side isolation primitive must be used by future client-facing paths"),
        ("`engagement_category = internal_test`", "gated test records need internal_test"),
        ("`real_client_data = false`", "gated test records need real_client_data=false"),
        ("`client_accessible = false`", "gated test records need client_accessible=false"),
        ("reserved test namespace/value", "gated test records need a reserved test namespace"),
        ("no writer was invoked", "no writer was invoked"),
        ("no runtime credential was used", "no runtime credential was used"),
    ):
        check(f"doc states: {label}", phrase in f)

    check("doc embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("doc prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("doc records no example engagement identifier",
          not re.search(r"\b(?:eng|intn|engrec|clnt)_[a-z0-9]{2,}\b", doc))

    for rel in ("docs/DATABASE_SCAFFOLD.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/IMPLEMENTATION_PLAN.md", "docs/PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md",
                "docs/PHASE57_INTERNAL_TEST_READ_ISOLATION.md"):
        blob = re.sub(r"\s+", " ", read(rel)).lower()
        check(f"{os.path.basename(rel)} records that 014 is applied to production",
              "phase 58" in blob and "applied to production" in blob)
        check(f"{os.path.basename(rel)} no longer claims 014 is unapplied in production",
              "014 has not been applied" not in blob
              and "production is still at 013" not in blob
              and "014 is still not applied" not in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase58", "validate-phase58" in mk)
    check("validate depends on validate-phase58",
          re.search(r"^validate:.*validate-phase58", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)


# --------------------------------------------------------------------------- 6. self-isolation


def isolation_checks() -> None:
    print("\n6. This harness contacts nothing")
    code = code_no_strings(read(HARNESS_REL))
    check("this harness opens no database connection",
          not re.search(r"create_engine\(|\.connect\(|pymysql|mysql\.connector", code))
    # ``os.environ`` contains the substring ".env", so match a real dotenv path/loader instead.
    check("this harness loads no dotenv file",
          not re.search(r"dotenv|(?<![A-Za-z_])\.env(?![A-Za-z])", code))
    check("this harness opens exactly one file path, its own repo-relative reader",
          code.count("open(") == 1)
    check("this harness invokes no controlled writer", "persist_" not in code)
    check("this harness scrubs every role variable from child processes",
          all(v in read(HARNESS_REL) for v in ROLE_VARS))
    check("this harness prints no environment value",
          not re.search(r"print\(.*os\.environ", code))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 58 production migration 014 verification check")
    print("=" * 70)
    baseline_checks()
    migration_checks()
    verifier_checks()
    decision_gate_checks()
    doc_checks()
    isolation_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
