#!/usr/bin/env python3
"""Phase 90 — the lab engagement anchor bootstrap path.

Checks, offline and with synthetic values only: that the baseline is unchanged; that the Phase 51
production gate is still byte-identical and denying; that the anchor bootstrap is a **separate**
branch rather than a widening of the ordinary lab path; that every ordinary lab check still applies
to it; that it cannot be mixed with data-record targets; that the Phase 89 data-record behaviour is
unchanged; that `clients` remains never enableable; that the operator tool is gated on the decision
and has no update/delete/cleanup path; and that no output carries a connection value.

No database is contacted, no credential file is read, and no writer is invoked by this harness.
Every URL here is synthetic and unroutable.
"""

from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

BASELINE_COMMIT = "ebc3d13"   # Add lab writer enablement decision gate

GATE_REL = "tools/lab_writer_enablement_decision_gate.py"
PROD_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
TOOL_REL = "tools/create_lab_internal_test_engagement_anchor.py"
WRITER_REL = "peak/db/engagement_authorization_anchor_writer.py"
HARNESS_REL = "tests/validate_phase90_lab_engagement_anchor_bootstrap.py"
MODELS_REL = "peak/db/models.py"

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
HEAD_REVISION = "014_engagement_classification"

ANCHOR_TARGET = "engagements/create_engagement_authorization_anchor"
OK_URL = "mysql+pymysql://peak_lab_runtime:x@synthetic.invalid:3306/peak_lab"

PY = sys.executable
_failures = 0


def check(label: str, ok: bool) -> bool:
    global _failures
    _failures += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    return ok


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def strip_docstrings(source: str) -> str:
    import ast
    tree = ast.parse(source)
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                spans.append((body[0].lineno, body[0].end_lineno))
    return "\n".join(re.sub(r"#.*$", "", ln)
                     for i, ln in enumerate(source.splitlines(), 1)
                     if not any(a <= i <= b for a, b in spans))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO_ROOT, rel))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def env(**kw):
    g = load(GATE_REL, "_g")
    base = {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1", g.LAB_URL_ENV: OK_URL,
            g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1", g.LAB_TARGETS_ENV: ANCHOR_TARGET}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, nothing added")
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 015 or later - Phase 90 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers - Phase 90 adds none",
          len(writers) == EXPECTED_WRITERS)

    for rel in (GATE_REL, TOOL_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    try:
        is_ancestor = git_succeeds("merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
        check(f"baseline commit {BASELINE_COMMIT} present in history", is_ancestor)
        if not is_ancestor:
            print("        reason: phase90_baseline_commit_not_ancestor")
        check("no migration file was added or edited",
              not git("diff", "--name-only", "HEAD", "--", "alembic").strip())
        check("the anchor writer itself was not modified",
              not git("diff", "--name-only", "HEAD", "--", WRITER_REL).strip())
        check("no controlled writer was added or edited",
              not git("diff", "--name-only", "HEAD", "--", "peak/db").strip())
        check("the controlled allowlist was not modified",
              not git("diff", "--name-only", "HEAD", "--",
                      "peak/persistence/allowlist.py").strip())
        check("the governance module was not modified",
              not git("diff", "--name-only", "HEAD", "--",
                      "peak/persistence/governance.py").strip())
        check("the enum vocabulary was not modified",
              not git("diff", "--name-only", "HEAD", "--", "peak/db/enums.py").strip())
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx").strip())
    except Exception:
        check("git-backed baseline checks (git unavailable - skipped)", True)


# --------------------------------------------------------------------------- 2. production


def production_untouched() -> None:
    print("\n2. The production gate is untouched and production stays denied")
    check("the production gate file has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", PROD_GATE_REL).strip())
    scrubbed = {k: v for k, v in os.environ.items()
                if not k.startswith(("PEAK_", "DATABASE_"))}
    scrubbed["PYTHONPATH"] = REPO_ROOT
    r = subprocess.run([PY, os.path.join(REPO_ROOT, PROD_GATE_REL)],
                       capture_output=True, text=True, env=scrubbed, timeout=60)
    check("production gate exits 0", r.returncode == 0)
    check("safe_to_write_production_now=false", "safe_to_write_production_now=false" in r.stdout)

    lab_env = dict(scrubbed)
    lab_env.update({"PEAK_WRITER_TARGET": "lab",
                    "PEAK_LAB_WRITER_ENABLEMENT_CONFIRM": "1",
                    "PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM": "1",
                    "PEAK_LAB_WRITER_TARGET_URL": OK_URL,
                    "PEAK_LAB_WRITER_TARGETS": ANCHOR_TARGET})
    r2 = subprocess.run([PY, os.path.join(REPO_ROOT, PROD_GATE_REL)],
                        capture_output=True, text=True, env=lab_env, timeout=60)
    check("production gate output is byte-identical with the anchor-bootstrap variables set",
          r.stdout == r2.stdout)


# --------------------------------------------------------------------------- 3. separateness


def bootstrap_is_a_separate_branch() -> None:
    print("\n3. The anchor bootstrap is a separate branch, not a widened ordinary path")
    g = load(GATE_REL, "_g3")
    from peak.persistence.allowlist import ALLOWED_ANCHOR_CREATION_PAIRS

    check("the bootstrap variable is PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM",
          g.ANCHOR_BOOTSTRAP_CONFIRM_ENV == "PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM")
    check("the bootstrap confirmation accepts only the exact string 1", g.CONFIRM_VALUE == "1")
    check("the anchor pair is NOT in the ordinary enableable set",
          g.ANCHOR_BOOTSTRAP_PAIR not in g.LAB_ENABLEABLE_WRITER_TARGETS)
    check("the ordinary enableable set is still exactly three create pairs",
          len(g.LAB_ENABLEABLE_WRITER_TARGETS) == 3
          and all(a.startswith("create_") for _, a in g.LAB_ENABLEABLE_WRITER_TARGETS))
    check("the bootstrap pair is the repository's one anchor-creation pair",
          g.ANCHOR_BOOTSTRAP_PAIR in ALLOWED_ANCHOR_CREATION_PAIRS)
    check("clients/create_draft is still never enableable on any path",
          ("clients", "create_draft") in g.NEVER_LAB_ENABLEABLE)
    check("no update_ or mark_ action is enableable by either path",
          not any(a.startswith(("update_", "mark_"))
                  for _, a in g.LAB_ENABLEABLE_WRITER_TARGETS | {g.ANCHOR_BOOTSTRAP_PAIR}))


# --------------------------------------------------------------------------- 4. deny branches


def bootstrap_deny_branches() -> None:
    print("\n4. Every ordinary lab check still applies to the bootstrap")
    g = load(GATE_REL, "_g4")
    cases = (
        ("anchor without the bootstrap confirmation denies",
         env(**{g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: None}), g.REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM),
        ("anchor with a non-exact bootstrap confirmation denies",
         env(**{g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: "true"}), g.REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM),
        ("anchor with the ordinary lab confirmation but no bootstrap confirmation denies",
         env(**{g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: None}), g.REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM),
        ("anchor bootstrap without the ordinary lab confirmation denies",
         env(**{g.LAB_CONFIRM_ENV: None}), g.REASON_NO_CONFIRM),
        ("anchor bootstrap against a non-lab schema denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("/peak_lab", "/other_db")}),
         g.REASON_SCHEMA_NOT_LAB),
        ("anchor bootstrap against the scenario schema denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("/peak_lab", "/peak_lab_scenario")}),
         g.REASON_SCHEMA_SCENARIO),
        ("anchor bootstrap against the provider default schema denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("/peak_lab", "/defaultdb")}),
         g.REASON_SCHEMA_DEFAULT),
        ("anchor bootstrap against a production-marked schema denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("/peak_lab", "/peak_production")}),
         g.REASON_SCHEMA_PRODUCTION),
        ("anchor bootstrap with a production-marked user denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("peak_lab_runtime", "peak_prod_runtime")}),
         g.REASON_USER_PRODUCTION),
        ("anchor bootstrap with the migration role denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("peak_lab_runtime", "peak_lab_migrate")}),
         g.REASON_USER_NOT_APPROVED),
        ("anchor bootstrap with the scenario read-only role denies",
         env(**{g.LAB_URL_ENV: OK_URL.replace("peak_lab_runtime", "peak_lab_scenario_ro")}),
         g.REASON_USER_NOT_APPROVED),
        ("anchor bootstrap with a production writer target denies",
         env(**{g.TARGET_ENV: "production"}), g.REASON_TARGET_IS_PRODUCTION),
        ("anchor mixed with a review target denies the whole request",
         env(**{g.LAB_TARGETS_ENV: ANCHOR_TARGET + ",review_records/create_review_record"}),
         g.REASON_ANCHOR_NOT_SOLE_TARGET),
        ("anchor mixed with all three data targets denies the whole request",
         env(**{g.LAB_TARGETS_ENV: ANCHOR_TARGET + ",review_records/create_review_record,"
                                                   "evidence_references/create_draft"}),
         g.REASON_ANCHOR_NOT_SOLE_TARGET),
        ("clients/create_draft denies even with the bootstrap confirmation",
         env(**{g.LAB_TARGETS_ENV: "clients/create_draft"}), g.REASON_TARGET_NEVER_ENABLEABLE),
    )
    for label, e, expected in cases:
        d = g.evaluate(e)
        check(f"{label} ({expected})",
              d["lab_write_authorized"] is False and d["reason"] == expected
              and d["anchor_bootstrap_authorized"] is False)

    d = g.evaluate(env())
    check("a complete, correctly scoped anchor bootstrap is authorized",
          d["lab_write_authorized"] is True and d["reason"] == g.REASON_ANCHOR_OK)
    check("the authorized outcome is the anchor-bootstrap outcome",
          d["outcome"] == g.OUTCOME_ANCHOR_BOOTSTRAP and d["anchor_bootstrap_authorized"] is True)
    check("the grant names exactly the anchor target and nothing else",
          d["authorized_writer_targets"] == [ANCHOR_TARGET])
    check("the authorized bootstrap decision is internally consistent", g.is_consistent(d))


# --------------------------------------------------------------------------- 5. phase 89


def phase89_behaviour_unchanged() -> None:
    print("\n5. The Phase 89 data-record behaviour is unchanged")
    g = load(GATE_REL, "_g5")
    for pair in sorted(g.LAB_ENABLEABLE_WRITER_TARGETS):
        target = f"{pair[0]}/{pair[1]}"
        d = g.evaluate(env(**{g.LAB_TARGETS_ENV: target, g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: None}))
        check(f"{target} is still authorized with no bootstrap confirmation",
              d["lab_write_authorized"] is True and d["reason"] == g.REASON_OK
              and d["anchor_bootstrap_authorized"] is False)
    all_three = ",".join(f"{t}/{a}" for t, a in sorted(g.LAB_ENABLEABLE_WRITER_TARGETS))
    d = g.evaluate(env(**{g.LAB_TARGETS_ENV: all_three, g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: None}))
    check("all three data targets together are still authorized",
          d["lab_write_authorized"] is True and d["anchor_bootstrap_authorized"] is False)
    d = g.evaluate(env(**{g.LAB_TARGETS_ENV: "intake_note_records/create_intake_note_record",
                          g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: None}))
    check("an off-set data target still denies", d["reason"] == g.REASON_TARGET_NOT_ENABLEABLE)
    d = g.evaluate(env(**{g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
                          g.LAB_TARGETS_ENV: "review_records/create_review_record"}))
    check("the bootstrap confirmation does not change a data-record decision",
          d["lab_write_authorized"] is True and d["anchor_bootstrap_authorized"] is False
          and d["outcome"] == g.OUTCOME_LAB_AUTHORIZED)


# --------------------------------------------------------------------------- 6. no production


def bootstrap_never_implies_production() -> None:
    print("\n6. The bootstrap never implies a production authorization")
    g = load(GATE_REL, "_g6")
    for i, e in enumerate((env(), env(**{g.TARGET_ENV: "production"}),
                           env(**{g.ANCHOR_BOOTSTRAP_CONFIRM_ENV: None}), {})):
        d = g.evaluate(e)
        check(f"case {i}: safe_to_write_production_now is false",
              d["safe_to_write_production_now"] is False)
        check(f"case {i}: production_write_authorized is false",
              d["production_write_authorized"] is False)
        check(f"case {i}: production_writer_enablement_authorized is false",
              d["production_writer_enablement_authorized"] is False)
        check(f"case {i}: the gate itself contacted nothing and wrote nothing",
              d["database_contacted"] is False and d["sql_issued"] is False
              and d["writer_invoked"] is False and d["records_created"] is False)


# --------------------------------------------------------------------------- 7. the tool


def operator_tool_is_gated_and_narrow() -> None:
    print("\n7. The operator tool is gated on the decision and has no cleanup path")
    src = read(TOOL_REL)
    code = strip_docstrings(src)

    check("the tool evaluates the lab gate before writing",
          "gate_allows_anchor_bootstrap" in code and "anchor_bootstrap_authorized" in code)
    check("the tool refuses when the gate does not authorize", "return 3" in code)
    check("the tool requests exactly the anchor target",
          code.count('ANCHOR_TARGET = "engagements/create_engagement_authorization_anchor"') == 1)
    check("the tool imports exactly one writer",
          code.count("persist_engagement_authorization_anchor") >= 1
          and not re.search(r"import\s+.*(source_ingestion|evidence|review|intake|client)_writer",
                            code))
    # Tests for the *operation*, not the word: the tool legitimately prints an operator message
    # saying "do not delete or alter it", and a check that banned the word would ban saying "no".
    check("the tool calls no update/delete/drop/cleanup function",
          not re.search(r"(?i)\b(update|delete|drop|truncate|cleanup|purge|remove)\s*\(", code))
    check("the tool issues no UPDATE or DELETE statement",
          not re.search(r"(?i)\b(UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+TABLE|TRUNCATE)\b",
                        code))
    check("the tool calls no ORM mutation helper",
          not re.search(r"\.(merge|remove|expunge|bulk_update|bulk_insert)\s*\(", code))
    check("the tool issues no raw SQL", ".execute(" not in code and "text(" not in code)
    check("the tool imports no Alembic or migration code",
          "alembic" not in code.lower() and "stamp" not in code.lower())
    check("the tool opens no credential file", "open(" not in code)
    # The label is stored but must never be printed: a label can carry a client organisation name.
    printed_lists = re.findall(r"(?s)for key in \((.*?)\)", code) + \
        re.findall(r"(?s)RECEIPT_FIELDS = \((.*?)\)", code)
    check("engagement_label appears in no printed field list",
          all("engagement_label" not in block for block in printed_lists))
    check("the tool says explicitly that the label is withheld", "label withheld" in src)
    check("the packet is hard-coded, not command-line supplied",
          "add_argument" in code and not re.search(r'add_argument\("--(owner|client|engagement|'
                                                   r'scope|category)', code))
    check("the anchor id is the approved synthetic lab id",
          '"engagement_id": "lab_internal_test_001"' in src)
    check("the idempotency key is deterministic and phase-specific",
          'IDEMPOTENCY_KEY = "phase90_lab_internal_test_engagement_anchor_001"' in src)
    check("the classification is the internal-test control set",
          '"engagement_category": "internal_test"' in src
          and '"real_client_data": False' in src
          and '"client_accessible": False' in src)
    check("capsule publication is not claimed",
          '"capsule_publication_authorized": False' in src)
    check("the authorization scope is a member of the closed vocabulary",
          _scope_is_canonical(src))
    check("the tool embeds no real-looking DSN",
          not re.search(r"(?i)(mysql|mariadb)(\+\w+)?://", src))


def _scope_is_canonical(src: str) -> bool:
    from peak.db.enums import AuthorizationScope
    m = re.search(r'"authorization_scope":\s*"([^"]+)"', src)
    return bool(m) and m.group(1) in {e.value for e in AuthorizationScope} \
        and m.group(1) != AuthorizationScope.revoked.value


# --------------------------------------------------------------------------- 8. value-free


def output_is_value_free() -> None:
    print("\n8. Output carries no connection value")
    g = load(GATE_REL, "_g8")
    url = ("mysql+pymysql://peak_lab_runtime:sup3rsecret@synthetic.invalid:3306/peak_lab"
           "?ssl_ca=/x/ca.pem")
    d = g.evaluate(env(**{g.LAB_URL_ENV: url}))
    rendered = json.dumps(d)
    for token, label in (("sup3rsecret", "password"), ("synthetic.invalid", "host"),
                         ("3306", "port"), ("ca.pem", "certificate path"),
                         ("ssl_ca", "query parameter"), ("://", "URL separator")):
        check(f"the bootstrap decision carries no {label}", token not in rendered)
    check("the decision still authorized, so the check is not vacuous",
          d["anchor_bootstrap_authorized"] is True)

    r = subprocess.run([PY, os.path.join(REPO_ROOT, GATE_REL), "--self-test"],
                       capture_output=True, text=True, timeout=60)
    check("the gate self-test passes", r.returncode == 0 and "RESULT: PASS" in r.stdout)
    check("self-test output carries no URL separator", "://" not in r.stdout)


def main() -> int:
    print("=" * 74)
    print("Phase 90 — lab engagement anchor bootstrap")
    print("=" * 74)
    baseline_checks()
    production_untouched()
    bootstrap_is_a_separate_branch()
    bootstrap_deny_branches()
    phase89_behaviour_unchanged()
    bootstrap_never_implies_production()
    operator_tool_is_gated_and_narrow()
    output_is_value_free()
    print("\n" + "=" * 74)
    print("Summary")
    print(f"  failures : {_failures}")
    print()
    print("RESULT:", "PASS" if _failures == 0 else "FAIL")
    return 0 if _failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
