#!/usr/bin/env python3
"""Phase 71 R1/R9 evidence-readiness plan check.

Phase 70 reviewed R9 and recorded that it is a **question set, not an answered model**. Phase 71
turns that finding into a plan: it defines the measured answers required before R1 can support a
location-dimension `evidence_reference`, and recommends collecting an **R10 measured answer set**
rather than creating a narrow R9 evidence reference now.

**Phase 71 is planning-only, and this harness's main job is to prove that negative.** A planning
phase is only trustworthy if it demonstrably wrote nothing, so the checks below establish that no
production record was created, no writer was invoked, no credential path was added, no operator
utility exists, and nothing under `peak/` or `alembic/` moved — alongside checking that the plan
document actually says what a plan of this kind must say.

Offline and credential-free: this harness opens no database at all (there is nothing to write), and
it reads no external artifact.

Layers: baseline - no-write-surface - plan content - isolation.

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

BASELINE_COMMIT = "d177c5f"   # Add Phase 70 R9 source ingestion review decision
#: The last commit belonging to Phase 71 itself. Pinning the range keeps later phases' files
#: out of "what this phase touched".
PHASE_COMMIT = "fb1ffdb"   # Fix Phase 71 harness to diff the baseline commit, not HEAD

DOC_REL = "docs/PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md"
HARNESS_REL = "tests/validate_phase71_r1_r9_evidence_readiness_plan.py"
PHASE70_DOC_REL = "docs/PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md"
PHASE69_DOC_REL = "docs/PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md"
MODELS_REL = "peak/db/models.py"
ALLOWLIST_REL = "peak/persistence/allowlist.py"

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
EXPECTED_TOOL_COUNT_UNCHANGED = True
HEAD_REVISION = "014_engagement_classification"

ANCHOR_ID = "internal_test_001"
RESERVED_CLIENT_ID = "99999"
SCOPE = "internal_peak_only"

#: The full production chain the plan must reproduce.
CHAIN_IDS = ("intn_b8b86b8c196c4595", "rev_b82ff6f00790418f", "ing_4fb70519cbf84401",
             "ing_884c94df03c34908", "ing_a2abb497f471458e", "rev_bf7f18a13d8f461c",
             "evid_56437d9b9c764560", "rev_de2b6e73f6c94c67", "ing_64b2e2648ac1402b",
             "rev_3ecc0891f4fe48ce")

#: Every writer entry point. None may appear in anything Phase 71 added.
WRITER_CALLS = ("persist_review_record", "persist_evidence_reference",
                "persist_source_ingestion_record", "persist_intake_note",
                "persist_engagement_authorization_anchor", "persist_agent_run_record")

#: Artifact bodies must never be committed. Their filenames must appear nowhere in this phase.
ARTIFACT_BASENAMES = ("r1_current_inventory_sku_location_v1.json",
                      "r2_sku_item_master_export_v1.json",
                      "r8_system_of_record_data_export_map_v1.json",
                      "r9_location_bin_naming_model_v1.json")

#: Row-like content: item/SKU values, quantities, and location/bin/aisle/rack/warehouse/site
#: *values*. Schema field names such as ``location_identifier`` are not values and must not match.
ROW_LIKE_RE = re.compile(r"(?i)\b(sku|item)[-_ ]?(?:id|code|no|number)?\s*[:=]\s*[\"']?[A-Z0-9]{3,}"
                         r"|\bqty\s*[:=]\s*\d|\bquantity_on_hand\s*[:=]\s*\d"
                         r"|\b(?:bin|aisle|rack|bay|zone|warehouse|site)\s*[:=]\s*[\"']?[A-Z0-9]{2,}")

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!internal-test-artifact)[\w.\-]+:[^\s@'\"]+@")
SENTINEL_MARK = "sentinel-name-list"
CLIENT_LIKE_NAMES = ("acme", "contoso", "initech", "globex", "northwind")  # sentinel-name-list
CLIENT_LIKE_RE = re.compile(r"(?i)\b(" + "|".join(CLIENT_LIKE_NAMES) + r")\b")

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


def code_only(source: str) -> str:
    """Executable code with every string literal and comment blanked out, in place.

    Blanked in place rather than dropped and re-joined: re-joining inserts whitespace between
    tokens, so a dotted expression like ``os.environ.get(...)`` would stop matching and a scan
    would silently pass on code that violates it.
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
    """Prose flattened for phrase checks: blockquotes, backticks, and whitespace normalized away,
    so a check tests the claim rather than the markdown formatting."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    stripped = stripped.replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", stripped).lower()


def changed_files() -> list:
    """Every path **this phase** touched, as a fixed commit range.

    Two traps are avoided here. Diffing ``HEAD`` goes empty once the phase is committed, so every
    "this phase added only X" check would pass vacuously rather than testing anything. Diffing the
    baseline against the *working tree* fixes that, but then sweeps in every later phase's files
    once Phase 72 and beyond exist. Pinning both ends to the phase's own commits gives the same
    answer forever: before the commit the range is empty and the untracked/uncommitted fallback
    supplies the files; after it, the range is authoritative.
    """
    committed = [c for c in git("diff", "--name-only",
                                f"{BASELINE_COMMIT}..{PHASE_COMMIT}").splitlines() if c]
    if committed:
        return sorted(set(committed))
    pending = [c for c in git("diff", "--name-only", BASELINE_COMMIT).splitlines() if c]
    untracked = [c for c in git("ls-files", "--others", "--exclude-standard").splitlines() if c]
    return sorted(set(pending + untracked))


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
        print("        reason: phase71_baseline_commit_not_ancestor")

    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later - Phase 71 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check("no file under alembic/ was changed by this phase",
          not git("diff", "--name-only", f"{BASELINE_COMMIT}..{PHASE_COMMIT}", "--", "alembic"))
    check("no file under peak/ was changed by this phase",
          not git("diff", "--name-only", f"{BASELINE_COMMIT}..{PHASE_COMMIT}", "--", "peak"))

    try:
        py_compile.compile(os.path.join(REPO_ROOT, HARNESS_REL), doraise=True)
        check(f"{HARNESS_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{HARNESS_REL} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers - no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("the allowlist module was not modified - no allowlist pair added",
          not git("diff", "--name-only", f"{BASELINE_COMMIT}..{PHASE_COMMIT}", "--", ALLOWLIST_REL))

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
          not git("diff", "--name-only", f"{BASELINE_COMMIT}..{PHASE_COMMIT}", "--", "docs/Peak_Investor_Overview_AI.docx"))


# --------------------------------------------------------------------------- 2. no write surface


def no_write_surface_checks() -> None:
    print("\n2. Phase 71 added no way to write anything - the planning-only claim, enforced")
    touched = changed_files()

    check("this phase touched only docs, its own harness, and the Makefile",
          all(c.startswith("docs/") or c == HARNESS_REL or c == "Makefile" for c in touched))
    check("no operator utility was added under tools/",
          not [c for c in touched if c.startswith("tools/")])
    check("no new test file other than this harness was added",
          not [c for c in touched if c.startswith("tests/") and c != HARNESS_REL])

    # Every Python file this phase added must contain no writer call and no credential path.
    py_added = [c for c in touched if c.endswith(".py")]
    check("this phase added exactly one Python file - its harness", py_added == [HARNESS_REL])
    for rel in py_added:
        code = code_only(read(rel))
        name = os.path.basename(rel)
        check(f"{name} invokes no writer",
              not any(call + "(" in code for call in WRITER_CALLS))
        check(f"{name} opens no database engine or session",
              not re.search(r"create_engine\(|create_session_factory\(|sessionmaker\(", code))
        check(f"{name} reads no environment variable",
              not re.search(r"os\.environ|getenv", code))
        check(f"{name} issues no raw SQL",
              not re.search(r"(?i)\btext\(|session\.execute\(|cursor\.|\bSELECT\s+\w+\s+FROM\b",
                            code))
        check(f"{name} imports no migration/Alembic code", "alembic" not in code.lower())
        check(f"{name} opens no external artifact",
              not any(n in code for n in ARTIFACT_BASENAMES)
              and "peak-internal-test-artifacts" not in code)

    mk_diff = git("diff", "-U0", f"{BASELINE_COMMIT}..{PHASE_COMMIT}", "--", "Makefile")
    added_mk = [ln[1:].strip() for ln in mk_diff.splitlines()
                if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip()]
    removed_mk = [ln[1:].strip() for ln in mk_diff.splitlines()
                  if ln.startswith("-") and not ln.startswith("---") and ln[1:].strip()]
    check("every line the Makefile change adds is about the Phase 71 harness",
          all("validate-phase71" in ln or "validate_phase71" in ln for ln in added_mk))
    # The .PHONY and `validate:` lines are rewritten whole, so their pre-existing target names
    # show up as "+" without being new. Compare token sets so only genuinely new names count.
    def tokens(lines):
        return set(re.findall(r"[A-Za-z0-9_.\-/]+", " ".join(lines)))
    new_tokens = tokens(added_mk) - tokens(removed_mk)
    check("the Makefile change introduces no production or credential target",
          not {t for t in new_tokens
               if re.search(r"(?i)production|runtime-connectivity|prod-ro|prod-runtime"
                            r"|^PEAK_", t)})
    check("the only new Makefile targets are the Phase 71 harness ones",
          all("phase71" in t.lower() or not t.startswith("validate-") for t in new_tokens))


# --------------------------------------------------------------------------- 3. plan content


def plan_checks() -> None:
    print("\n3. The plan says what a planning document of this kind must say")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("plan content checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    f = flat(doc)

    # --- planning-only status, and the explicit negatives
    for phrase, label in (
        ("planning-only", "the phase is planning-only"),
        ("no production database", "no production database was contacted"),
        ("no environment file", "no environment file was sourced"),
        ("invoked no writer", "no writer was invoked"),
        ("no production record", "no production record was created"),
        ("no evidence_reference", "no evidence_reference was created"),
        ("no review_record", "no review_record was created"),
        ("no source_ingestion_record", "no source_ingestion_record was created"),
        ("no report", "no report was created"),
        ("no capsule", "no capsule was created"),
        ("no client-facing output", "no client-facing output was created"),
        ("no agentnet", "no AgentNet publication was created"),
    ):
        check(f"plan states: {label}", phrase in f)

    # --- posture carried in
    for phrase, label in (
        ("question set, not an answered model",
         "R9 is a question set, not an answered model"),
        ("non-authoritative", "R9 remains non-authoritative"),
        ("remains provisional", "R1's location dimension remains provisional"),
        ("r5 wms scope", "R5 WMS scope is named as unresolved"),
        ("authority precedence", "R8 authority precedence is named as unconfirmed"),
        (ANCHOR_ID, "the engagement anchor is named"),
        (SCOPE, "the authorization scope is named"),
        (RESERVED_CLIENT_ID, "the reserved internal-test client id is named"),
    ):
        check(f"plan states: {label}", phrase in f)
    check("plan states: R3-R7 remain deferred",
          re.search(r"r3[-–—]r7", f) is not None and "defer" in f)
    check("plan reproduces the full production chain through the R9 review",
          all(rid in doc for rid in CHAIN_IDS))

    # --- the core finding, in substance
    check("plan states the core finding: R9 defines the questions but does not answer them",
          "defines the questions that must be answered" in f
          and "does not answer them" in f)
    check("plan states the next need is a measured answer set, not another evidence reference",
          "measured location-model answer set, not another evidence reference" in f)

    # --- the required measured answers
    for phrase, label in (
        ("which hierarchy levels actually exist", "which hierarchy levels exist"),
        ("map to each hierarchy level", "which R1 fields map to each level"),
        ("mixed", "whether the location identifier is a mixed field"),
        ("availability status", "availability status versus physical position"),
        ("quarantine", "hold/damaged/quarantine/unavailable representation"),
        ("non-nettable", "non-nettable inventory representation"),
        ("in-transit", "in-transit inventory representation"),
        ("which system owns the location model", "which system owns the location model"),
        ("hybrid", "hybrid ownership is a candidate answer"),
        ("align or diverge", "whether ERP and WMS identifiers align or diverge"),
        ("crosswalk", "normalization, aliasing, or crosswalk needs"),
        ("stable enough", "whether location names are stable enough for evidence use"),
        ("time-aligned", "whether quantities are time-aligned with the location model"),
        ("reconcilable to r2", "whether R1 item identifiers reconcile to R2"),
        ("is readable", "the threshold for the dimension being readable"),
        ("not reliable enough", "the threshold for it not being reliable enough"),
        ("dependent on r8", "what remains dependent on R8 review"),
        ("dependent on r5", "what remains dependent on R5 clarification"),
    ):
        check(f"plan requires a measured answer for: {label}", phrase in f)

    # --- non-claims
    for phrase, label in (
        ("no inventory accuracy conclusion", "no inventory accuracy conclusion"),
        ("no quantity reliability conclusion", "no quantity reliability conclusion"),
        ("no r1 location validation", "no R1 location validation"),
        ("no report drafting", "no report drafting"),
        ("no capsule publication", "no capsule publication"),
        ("no agentnet resolver publication", "no AgentNet resolver publication"),
    ):
        check(f"plan excludes: {label}", phrase in f)

    # --- the recommendation
    for phrase, label in (
        ("phase 72", "Phase 72 is recommended as the next phase"),
        ("r10", "R10 is named"),
        ("answer set", "R10 is an answer set"),
        ("pkt_internal_test_r10_location_model_answer_set_001",
         "the suggested R10 packet reference is given"),
        ("internal-test-artifact://phase72/r10-location-model-answer-set-v1",
         "the suggested R10 logical location reference is given"),
        ("internal_test_export", "the suggested packet source type follows convention"),
        ("needs_review", "R10 would land needs_review"),
        ("authoritative", "R10 would be non-authoritative"),
        ("until reviewed", "R10 stays non-authoritative until reviewed"),
        ("a recommendation, not an authorization",
         "the sequence is a recommendation, not an authorization"),
    ):
        check(f"plan recommends: {label}", phrase in f)
    check("plan names the recommended sequence through Phase 75",
          all(p in f for p in ("phase 73", "phase 74", "phase 75")))

    # --- the deferred alternative
    check("plan documents the narrow R9 evidence reference as the alternative",
          "narrow r9" in f and "evidence_reference" in f)
    check("plan explains the alternative would mostly prove a reviewed question set exists",
          "reviewed question set" in f)
    check("plan defers that alternative rather than foreclosing it",
          "defer" in f and ("audit completeness" in f or "foreclos" in f))

    # --- hygiene
    check("plan embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("plan prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("plan carries no row-like item/quantity/location value", not ROW_LIKE_RE.search(doc))
    check("plan contains no committed artifact filename other than the proposed R10 name",
          not any(n in doc for n in ARTIFACT_BASENAMES))


# --------------------------------------------------------------------------- 4. isolation


def isolation_checks() -> None:
    print("\n4. No artifact body, no fixture, and the updated docs agree")
    tracked = git("ls-files").splitlines()
    check("no artifact body file is tracked in the repository",
          not [t for t in tracked if any(n in os.path.basename(t) for n in ARTIFACT_BASENAMES)])
    check("no internal-test-artifact directory is tracked in the repository",
          not [t for t in tracked if "peak-internal-test-artifacts" in t])
    check("no fixtures/examples/sample-packet directory is tracked",
          not [t for t in tracked
               if re.match(r"^(fixtures|examples|samples|sample_packets)/", t)])
    check("no sample or fixture packet file is tracked",
          not [t for t in tracked
               if re.search(r"(?i)(fixture|sample|example)[^/]*\.(json|ya?ml|csv|txt)$", t)])
    check("no .json/.csv/.txt artifact was added by this phase",
          not [c for c in changed_files() if c.endswith((".json", ".csv", ".txt"))])

    for rel in (DOC_REL, HARNESS_REL):
        if not os.path.isfile(os.path.join(REPO_ROOT, rel)):
            continue
        blob = read(rel)
        name = os.path.basename(rel)
        check(f"{name} contains no obviously client-like organisation name",
              not CLIENT_LIKE_RE.search(scannable(blob)))
        check(f"{name} embeds no secret-like assignment",
              not re.search(r"(?i)(password|api[_-]?key|secret|private[_-]?key|access[_-]?key)"
                            r"\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{8,}", blob))

    for rel in ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                "docs/DATABASE_SCAFFOLD.md", PHASE70_DOC_REL, PHASE69_DOC_REL):
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records Phase 71", "phase 71" in blob)
        check(f"{name} states Phase 71 is planning-only", "planning-only" in blob)
        check(f"{name} states no production record was created",
              "no production record" in blob or "no database record" in blob
              or "no credential" in blob)
        check(f"{name} states R1 remains provisional", "remains provisional" in blob)
        check(f"{name} states R9 is a question set, not an answered model",
              "question set, not an answered model" in blob)
        check(f"{name} names R10 as the likely next production step", "r10" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase71", "validate-phase71" in mk)
    check("validate depends on validate-phase71",
          re.search(r"^validate:.*validate-phase71", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 71 R1/R9 evidence-readiness plan check")
    print("=" * 70)
    baseline_checks()
    no_write_surface_checks()
    plan_checks()
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
