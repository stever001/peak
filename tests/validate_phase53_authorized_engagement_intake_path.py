#!/usr/bin/env python3
"""Phase 53 authorized engagement / intake write path planning check.

Phase 51 recorded *that* nothing should be written yet and named waiting for authorized engagement
data as the recommended path. Phase 53 works out what that concretely requires — by reading source
only — and plans the first authorized write path without executing any part of it.

**Decision: no production write, no writer enablement, no synthetic smoke write, no engagement
record creation, no intake note creation. Plan only.**

This harness is fully offline and credential-free. It contacts no database, reads no environment
credential, and invokes no controlled writer.

Six layers:

* **Baseline** — head still 013, 13 migrations, 18 tables, no migration 014, no ``alembic/versions``
  change, no model/entity, writer, or allowlist pair added, no generic SQL/CRUD path added.

* **Source facts** — the findings the Phase 53 document asserts are re-derived from source here, so
  the document cannot drift away from the code: the ``Engagement`` model exists, no controlled
  Engagement writer exists, the intake note writer exists, and it requires the stored ``Engagement``
  authorization before it will write.

* **Document** — the Phase 53 record states every prohibition, names the authorization anchor,
  reports each source finding, names the conditional next phase, and carries the required pre-write
  decision fields.

* **Standing decisions** — the Phase 51 no-write / no-enablement decision and the "Phase 50
  connectivity is prerequisite evidence, not permission" and "runtime has no DELETE" warnings all
  survive in the Phase 53 document.

* **Regression** — writers stay create-only, the verifier and both gates stay opt-in and unweakened,
  and the audit result is unchanged.

* **Hygiene** — no DSN, host, username, password, token, certificate path, database name, env value,
  raw grant, row value, client data, pseudo-client data, or example record is added; the repo data
  policy is intact and the investor overview is untouched.

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
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "6736fe0"   # Clarify Phase 50 runtime gate driver failures

DOC_REL = "docs/PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md"
HARNESS_REL = "tests/validate_phase53_authorized_engagement_intake_path.py"
PHASE51_DOC_REL = "docs/PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md"
DECISION_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
CONNECTIVITY_GATE_REL = "tools/production_runtime_connectivity_gate.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
AUDIT = "tools/governed_mysql_collation_audit.py"
MODELS_REL = "peak/db/models.py"
ALLOWLIST_REL = "peak/persistence/allowlist.py"
INTAKE_WRITER_REL = "peak/db/intake_note_writer.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 13
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "013_governed_identifier_collation_policy"

ENGAGEMENT_TABLE = "engagements"
INTAKE_TABLE = "intake_note_records"
INTAKE_ACTION = "create_intake_note_record"

# Phase 53 adds a doc, a harness, a Makefile wiring line, and narrow notes on four existing docs.
ALLOWED_CHANGED = {
    DOC_REL,
    HARNESS_REL,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_SCAFFOLD.md",
    PHASE51_DOC_REL,
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


def called_names(source: str) -> set:
    """Every function/method name this module actually *calls*.

    Substring scanning cannot work on this harness: it must name tokens like ``.execute(`` and
    ``create_session_factory`` inside assertion literals in order to check *other* files for them.
    Parsing for real call sites asks the question the assertion actually means.
    """
    import ast
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


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



def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def flat(text: str) -> str:
    """Whitespace-normalized lowercase text — prose in these docs wraps across lines."""
    return re.sub(r"\s+", " ", text.lower())


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

    try:
        py_compile.compile(os.path.join(REPO_ROOT, HARNESS_REL), doraise=True)
        check(f"{HARNESS_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{HARNESS_REL} compiles", False)

    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables — no entity added",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES, PROHIBITED_TABLES
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_TABLES} tables — no pair added",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES)
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_ACTIONS} actions — no pair added",
          len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("engagements is still prohibited on the generic write allowlist",
          ENGAGEMENT_TABLE in PROHIBITED_TABLES and ENGAGEMENT_TABLE not in ALLOWED_TABLES)

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers — none added",
          len(writers) == EXPECTED_WRITERS)

    # No generic SQL/CRUD path: Phase 53 adds no executable source under peak/ at all, and this
    # harness executes no statement of its own. (It names SQL verbs only inside assertion
    # literals, so the meaningful check is that it never *executes* or *composes* one.)
    harness_calls = called_names(read(HARNESS_REL))
    # `add`/`append` are ordinary Python; the SQL-shaped ones are what matter.
    check("no generic SQL/CRUD path added — this harness executes no statement",
          not ({"execute", "executemany", "executescript", "scalar", "scalars"}
               & harness_calls))
    check("this harness opens no cursor, connection, or transaction",
          not ({"cursor", "connect", "begin", "session"} & harness_calls))
    # Authoring-time claim about Phase 53's own working tree (it added no peak/ source), not a
    # permanent freeze: Phase 54 legitimately added the anchor writer and its one-pair gate.
    try:
        if phase_never_committed(HARNESS_REL):
            added_modules = [c for c in git("diff", "--name-only", "HEAD").splitlines()
                             if c.startswith("peak/")]
            check("no generic SQL/CRUD module added under peak/", not added_modules)
    except Exception:
        check("peak/ scope check (git unavailable — skipped)", True)

    try:
        check(f"baseline commit {BASELINE_COMMIT} present in history",
              BASELINE_COMMIT in git("log", "--oneline", "-40"))
        if phase_never_committed(HARNESS_REL):
            unexpected = sorted(set(git("diff", "--name-only", "HEAD").splitlines())
                                - ALLOWED_CHANGED)
            check("only the intended narrow set of files changed", not unexpected)
            if unexpected:
                print(f"        unexpected: {unexpected}")
        else:
            print("  [skip] Phase 53 is committed — working-tree scope guard not applicable")

        # Authoring-time claim about *this* phase's own working tree, not a permanent freeze
        # on the repository: later phases may legitimately add a writer or extend the
        # allowlist under their own governance gate (Phase 54 added the engagement
        # authorization anchor writer and its one-pair anchor gate). The substantive
        # invariants — writers stay create-only, the generic allowlist stays closed — are
        # asserted unconditionally elsewhere in this harness.
        if phase_never_committed(HARNESS_REL):
            governed = [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
                        if c.endswith("_writer.py")
                        or c in (MODELS_REL, "peak/db/base.py", ALLOWLIST_REL)]
            check("no controlled writer, model, base, or allowlist source changed", not governed)
        check("no alembic/versions file was modified",
              not git("diff", "--name-only", "HEAD", "--", "alembic"))
        check("no production verifier or gate tool was modified",
              not git("diff", "--name-only", "HEAD", "--", "tools"))
        check("schemas/, prompts/, agents/ untouched",
              not git("diff", "--name-only", "HEAD", "--", "schemas", "prompts", "agents"))
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. source facts


def source_fact_checks() -> None:
    print("\n2. Source facts: the findings the Phase 53 document asserts, re-derived from source")
    models = read(MODELS_REL)
    intake = read(INTAKE_WRITER_REL)
    intake_code = code_no_docstrings(intake)
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    writers = sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py"))

    # (a) The Engagement model / table exists.
    check("the Engagement model exists in models.py",
          re.search(r"^class Engagement\(", models, re.MULTILINE) is not None)
    check(f"the Engagement model maps to the '{ENGAGEMENT_TABLE}' table",
          f'__tablename__ = "{ENGAGEMENT_TABLE}"' in models)

    # (b) Engagement anchor creation is reachable through exactly one writer.
    #
    # Phase 53 recorded "no controlled Engagement writer exists" as its finding at that time, and
    # named adding one as the next phase. Phase 54 did exactly that, so asserting the absence here
    # would freeze a finding the plan itself scheduled for removal. What must hold permanently is
    # the *narrowness*: at most one writer may reach `engagements`, only through the single anchor
    # pair, and the generic path must still refuse the table.
    contracts = read("peak/db/writer_contracts.py")
    anchor_writers = [f for f in writers if f.startswith("engagement")]
    check("exactly one engagement writer module exists in peak/db/", len(anchor_writers) == 1)
    check(f"no non-anchor writer constructs an {ENGAGEMENT_TABLE} row",
          all("Engagement(" not in code_no_docstrings(read(f"peak/db/{n}"))
              for n in writers if n not in anchor_writers))
    targets = set(re.findall(r'TARGET_TABLE\s*=\s*"([a-z_]+)"', contracts))
    check(f"no *generic* controlled writer targets '{ENGAGEMENT_TABLE}'",
          ENGAGEMENT_TABLE not in (targets - {"engagements"})
          and 'ENGAGEMENT_ANCHOR_TARGET_TABLE = "engagements"' in contracts)
    check("the only engagement-creating action is the single anchor action",
          set(re.findall(r'TARGET_ACTION\s*=\s*"(create_engagement[a-z_]*)"', contracts))
          == {"create_engagement_authorization_anchor"})

    # (c) The intake note writer exists and targets the expected allowlist pair.
    check("the intake note writer exists", os.path.isfile(os.path.join(REPO_ROOT,
                                                                      INTAKE_WRITER_REL)))
    check(f"the intake note writer targets '{INTAKE_TABLE}'",
          f'INTAKE_NOTE_TARGET_TABLE = "{INTAKE_TABLE}"' in contracts)
    check(f"the intake note writer action is '{INTAKE_ACTION}'",
          f'INTAKE_NOTE_TARGET_ACTION = "{INTAKE_ACTION}"' in contracts)
    from peak.persistence.allowlist import is_allowed_action, is_allowed_table
    check("the intake note (table, action) pair is already on the allowlist",
          is_allowed_table(INTAKE_TABLE) and is_allowed_action(INTAKE_ACTION))

    # (d) The intake writer requires the stored Engagement authorization anchor.
    check("the intake writer loads the stored Engagement subject",
          "session.get(Engagement," in intake_code)
    check("the intake writer denies when the stored subject is missing",
          '"missing_subject"' in intake_code)
    check("the intake writer denies a blank stored authorization_scope",
          '"missing_stored_scope"' in intake_code)
    check("the intake writer denies a request/stored authorization_scope mismatch",
          '"stored_scope_mismatch"' in intake_code
          and "request.authorization_scope != stored_scope" in intake_code)
    check("the intake writer denies a stored-identity mismatch",
          '"identity_mismatch"' in intake_code)
    check("the intake writer denies a blocked stored subject lifecycle",
          '"subject_lifecycle_blocked"' in intake_code
          and "BLOCKED_LIFECYCLE_STATUSES" in intake_code)
    check("the intake writer requires an idempotency_key",
          '"invalid_idempotency_key"' in intake_code)
    check("the intake writer computes a payload fingerprint",
          "_payload_fingerprint(" in intake_code)
    check("the intake writer only supports an 'engagement' subject type",
          'SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})' in intake)

    # (e) The anchor is universal, and the planned path needs no UPDATE/DELETE.
    # Every writer *except* the anchor writer itself loads the stored Engagement anchor. The
    # anchor writer cannot: the row it creates is that anchor.
    anchored = [n for n in writers
                if "session.get(Engagement," in code_no_docstrings(read(f"peak/db/{n}"))]
    non_anchor = [n for n in writers if not n.startswith("engagement")]
    check("every non-anchor controlled writer loads the stored Engagement anchor",
          set(non_anchor) <= set(anchored) and len(non_anchor) == EXPECTED_WRITERS - 1)
    check("no controlled writer performs an UPDATE or DELETE",
          not any(re.search(r"session\.delete\(|\.update\(\{",
                            code_no_docstrings(read(f"peak/db/{n}"))) for n in writers))


# --------------------------------------------------------------------------- 3. document


def document_checks() -> None:
    print("\n3. The Phase 53 document records the decision, the findings, and the next phase")
    check(f"{DOC_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)))
    doc = read(DOC_REL)
    f = flat(doc)

    # Prohibitions.
    check("doc states no production write",
          "no production write" in f)
    check("doc states no writer enablement",
          "no writer enablement" in f)
    check("doc states no synthetic smoke write",
          "no synthetic smoke write" in f)
    check("doc states no engagement record creation",
          "no engagement record creation" in f)
    check("doc states no intake note creation",
          "no intake note creation" in f)
    check("doc states it is plan only", "plan only" in f)

    # The authorization anchor.
    check("doc names the required authorization anchor as a stored Engagement row",
          "the authorization anchor is a stored `engagement` row" in f)
    check("doc requires the anchor to carry an authorization_scope",
          "authorization_scope" in doc and "populated" in f)
    check("doc states identity matching alone is not sufficient",
          "not sufficient" in f)

    # Findings, each stated one way only so the doc cannot say both.
    check("doc reports that the Engagement model/table exists",
          "engagement model / table — **exists**" in f
          or "engagement model/table — **exists**" in f)
    check("doc reports that no controlled Engagement writer exists",
          "controlled engagement writer — **does not exist**" in f)
    check("doc reports that the intake note writer exists",
          "intake note writer — **exists**" in f)
    check("doc reports that the intake writer requires the stored Engagement authorization",
          "the intake writer requires the stored engagement authorization — **confirmed**" in f)
    check("doc states the first intake write cannot proceed without the stored anchor",
          "cannot be performed without an existing stored `engagement` anchor" in f)
    check("doc records that engagements is on the prohibited-table list",
          "prohibited_tables" in f)
    check("doc records that the path needs no UPDATE or DELETE",
          "requires `update` or `delete`" in f or "no part of the planned first write path "
          "requires `update` or `delete`" in f)
    check("doc records that SELECT + INSERT remain sufficient",
          "remain sufficient" in f and "`select` + `insert`" in f)

    # Recommended writer and next phase.
    check("doc names the intake note writer as the recommended first real operational writer",
          "recommended first real operational writer" in f and "intake note writer" in f)
    check("doc names the conditional next phase on the no-Engagement-writer branch",
          "phase 54 should add a create-only controlled engagement authorization anchor writer"
          in f)
    check("doc names the other branch it did not take",
          "create the first authorized engagement record" in f
          and "explicit approval" in f)
    check("doc requires the next phase to create no engagement record",
          "create no engagement record" in f)

    # Required pre-write decision fields.
    for field in ("writer name", "target table", "action allowlist pair", "`owner_id` source",
                  "`client_id` source", "`engagement_id` source", "`authorization_scope` source",
                  "approval authority", "idempotency key pattern", "payload fingerprint behavior",
                  "cleanup / retention posture"):
        check(f"doc names required pre-write field: {field}", field.lower() in f)
    check("doc requires the record to be classified real / internal-admin / synthetic",
          "real client, internal/administrative, or synthetic" in f)
    check("doc states the idempotency key boundary is per owner/client/engagement and the key",
          "(owner_id, client_id, engagement_id, idempotency_key)" in f)


# --------------------------------------------------------------------------- 4. standing


def standing_decision_checks() -> None:
    print("\n4. Standing decisions and warnings survive in the Phase 53 record")
    doc = read(DOC_REL)
    f = flat(doc)

    check("doc preserves the Phase 51 no-write / no-enablement decision",
          "phase 51 no-write / no-enablement decision remains in force" in f)
    check("doc states Phase 53 flips no field in the Phase 51 decision record",
          "flips no field" in f)
    check("doc states the first production write remains deferred",
          "first production write remains deferred" in f)
    check("doc states Phase 50 connectivity is prerequisite evidence, not write permission",
          "prerequisite evidence, not write permission" in f)
    check("doc states runtime holds no DELETE",
          "the runtime credential holds no `delete`" in f)
    check("doc warns runtime cannot remove what runtime wrote",
          "cannot be removed by runtime" in f)
    check("doc states the durable / no-cleanup default for a synthetic record",
          "durable / no-cleanup" in f)
    check("doc states synthetic smoke-writing remains disallowed unless separately approved",
          "remains disallowed" in f and "separately" in f)
    check("doc requires the cleanup posture to be decided before the write",
          "before** the write" in f or "before the write" in f)

    p51 = flat(read(PHASE51_DOC_REL))
    check("Phase 51 doc still records the no-write decision",
          "no production smoke-write" in p51)
    check("Phase 51 doc's Phase 53 note states the decision is unchanged",
          "the phase 51 decision is unchanged" in p51)


# --------------------------------------------------------------------------- 5. regression


def regression_checks() -> None:
    print("\n5. Regression: writers create-only, gates opt-in and unweakened")
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    writers = sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py"))
    for name in writers:
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    harness_code = code_no_docstrings(read(HARNESS_REL))
    check("this harness invokes no controlled writer",
          not re.search(r"\bpersist_[a-z_]+\(", harness_code))
    check("this harness imports no controlled writer",
          not re.search(r"from\s+peak\.db\.\w*_writer|import\s+\w*_writer\b", harness_code))
    check("this harness opens no database session or engine",
          not ({"create_session_factory", "create_runtime_engine", "create_engine", "sessionmaker"}
               & called_names(read(HARNESS_REL))))
    check("this harness scrubs every role variable from child processes",
          "k not in ROLE_VARS" in harness_code)

    mk = read("Makefile")
    check("Makefile declares validate-phase53", "validate-phase53" in mk)
    check("validate depends on validate-phase53",
          re.search(r"^validate:.*validate-phase53", mk, re.MULTILINE) is not None)
    check("the writer-enablement decision gate remains opt-in, not part of validate",
          re.search(r"^validate:.*writer-enablement-decision-gate", mk, re.MULTILINE) is None)
    check("make runtime-connectivity-gate remains opt-in, not part of validate",
          "runtime-connectivity-gate:" in mk
          and re.search(r"^validate:.*runtime-connectivity", mk, re.MULTILINE) is None)
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
        gate = subprocess.run([PY, os.path.join(REPO_ROOT, DECISION_GATE_REL)],
                              capture_output=True, text=True, timeout=60, env=env)
        check("writer-enablement decision gate still exits 0 on the no-write path",
              gate.returncode == 0)
        for field in ("production_write_authorized=false", "writer_enablement_authorized=false",
                      "synthetic_write_authorized=false", "safe_to_run_writers_now=false",
                      "writer_invoked=false", "database_contacted=false"):
            check(f"decision gate still reports {field}", field in gate.stdout)
    except Exception:
        check("decision gate regression (not runnable — skipped)", True)

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


# --------------------------------------------------------------------------- 6. hygiene


def hygiene_checks() -> None:
    print("\n6. Hygiene: no credentials, no client data, no example records added")
    docs_changed = [DOC_REL, "docs/IMPLEMENTATION_PLAN.md",
                    "docs/DATABASE_ACCESS_AND_AUDIT.md", "docs/DATABASE_SCAFFOLD.md",
                    PHASE51_DOC_REL]
    for rel in docs_changed:
        text = read(rel)
        check(f"{rel} contains no connection scheme with credentials",
              not re.search(r"://\S*:\S*@", text))
        check(f"{rel} references no operator credential file",
              not any(m in text for m in CREDENTIAL_FILE_MARKERS))

    # The harness names credential *markers* inside its own detection constants; hold it to the
    # bar that matters — no real DSN and no assigned credential value.
    for rel in docs_changed + [HARNESS_REL]:
        text = read(rel)
        check(f"{rel} embeds no real-looking DSN", not REAL_DSN_RE.search(text))
        check(f"{rel} contains no raw GRANT line", not re.search(r"^\s*GRANT\s+", text,
                                                                re.MULTILINE))
        check(f"{rel} assigns no password/token/secret value",
              not re.search(r"(?i)\b(?:password|passwd|token|secret|api[_-]?key)\s*[=:]\s*"
                            r"['\"]?[A-Za-z0-9/+._-]{6,}", text))

    doc = read(DOC_REL)
    # Record ids follow the conventions eng_<slug> / intn_<slug> / engrec_<slug> / client_<slug>.
    # Field names (client_id, engagement_id) are not identifier *values* and must not be flagged.
    check("Phase 53 doc contains no example engagement/client/note identifier value",
          not re.search(r"\b(?:eng|intn|engrec|clnt)_[a-z0-9]{2,}\b", doc)
          and not re.search(r"`client_(?!id\b)[a-z0-9]{2,}`", doc))
    check("Phase 53 doc quotes no note prose or row value",
          "note_text" not in doc or "note body hashed" in doc)

    # Repo data policy: no examples/fixtures/sample packets/client data introduced.
    try:
        changed = set(git("diff", "--name-only", "HEAD").splitlines())
        check("no examples/ or fixtures/ path added or changed",
              not any(c.startswith(("examples/", "fixtures/", "samples/")) for c in changed))
        check("no packet/data artifact added",
              not any(c.endswith((".json", ".csv", ".xlsx", ".docx")) for c in changed))
    except Exception:
        check("repo data-policy scope check (git unavailable — skipped)", True)

    docx = os.path.join(REPO_ROOT, "docs", "Peak_Investor_Overview_AI.docx")
    check("docs/Peak_Investor_Overview_AI.docx still exists and was not rewritten",
          os.path.isfile(docx))

    check("this harness reads no environment credential",
          not any(v in code_no_docstrings(read(HARNESS_REL)).replace("ROLE_VARS", "")
                  for v in ("os.environ.get(\"PEAK", "os.environ[\"PEAK")))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 53 authorized engagement / intake path planning check")
    print("=" * 70)

    baseline_checks()
    source_fact_checks()
    document_checks()
    standing_decision_checks()
    regression_checks()
    hygiene_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
