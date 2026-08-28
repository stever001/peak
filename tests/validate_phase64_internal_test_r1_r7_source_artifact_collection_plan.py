#!/usr/bin/env python3
"""Phase 64 internal test R1-R7 source artifact collection plan check.

Phase 63 registered the R8 system-of-record and data-export map. Phase 64 specifies the seven
artifacts that follow it and names what Phase 65 should register first. It is **planning-only**:
no production connection, no writer invocation, no environment read, **no production record**, and
**no artifact body**.

This harness is offline and credential-free. It reads repository files and the pure allowlist and
contract modules; it opens no database, builds no engine, spawns no operator utility, and never
reads the external artifact directory.

Layers: baseline · plan doc · per-request coverage · example-data ban · doc propagation ·
isolation.

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

BASELINE_COMMIT = "2569f38"   # Add Phase 63 first internal test source ingestion record

DOC_REL = "docs/PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md"
HARNESS_REL = "tests/validate_phase64_internal_test_r1_r7_source_artifact_collection_plan.py"
MODELS_REL = "peak/db/models.py"
ALLOWLIST_REL = "peak/persistence/allowlist.py"

#: Every file Phase 64 is permitted to add or modify. Declared explicitly rather than derived from
#: ``git diff``: a pending-diff scan goes empty the moment this phase is committed, and the content
#: checks below would then silently pass by scanning nothing.
PHASE_FILES = (
    DOC_REL,
    HARNESS_REL,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_SCAFFOLD.md",
    "docs/PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md",
    "docs/PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md",
)

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"

REQUESTS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")

#: The Phase 63 artifact body must stay out of the repository, as must any Phase 65 artifact.
ARTIFACT_BASENAMES = ("r8_system_of_record_data_export_map_v1.json",)
ARTIFACT_DIR_MARK = "peak-internal-test-artifacts"

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
    return "\n".join(ln for ln in blob.splitlines() if SENTINEL_MARK not in ln)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)).lower()


def request_blocks(doc: str) -> "dict[str, str]":
    """Split the plan's per-request subsections into {request_id: body}.

    Each body is cut at the next level-2 heading or horizontal rule. Without that the final
    request would absorb the rest of the document, and a per-request requirement could be
    satisfied by prose belonging to a later section.
    """
    parts = re.split(r"(?m)^###\s+(R[1-7])\s+—[^\n]*$", doc)
    blocks = {}
    for i in range(1, len(parts) - 1, 2):
        body = re.split(r"(?m)^(?:##\s|---\s*$)", parts[i + 1])[0]
        blocks[parts[i]] = body
    return blocks


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
    check("no migration 015 or later — Phase 64 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    # Pathspec narrowed to match the label: it read "alembic", which also covered
    # alembic/env.py and froze that file against every later phase.
    check("no migration file was added or modified by this phase",
          not git("diff", "--name-only", "HEAD", "--", "alembic/versions"))

    try:
        py_compile.compile(os.path.join(REPO_ROOT, HARNESS_REL), doraise=True)
        check(f"{HARNESS_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{HARNESS_REL} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("peak/db/models.py was not modified by this phase — no model added",
          not git("diff", "--name-only", "HEAD", "--", MODELS_REL))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])
    check("the allowlist module was not modified by this phase — no allowlist pair added",
          not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))
    # Scoped to Phase 64's own claim — that *this* phase shipped no operator utility. It must not
    # forbid a source-ingestion operator outright: Phase 65 is the phase authorized to add one, and
    # Section 6 above recommends exactly that. An unscoped working-tree diff would instead fail the
    # moment the recommended phase is executed.
    check("no Phase 64 operator/record-creation utility was added",
          not [t for t in os.listdir(os.path.join(REPO_ROOT, "tools"))
               if "phase64" in t.lower()]
          and not [c for c in git("diff", "--name-only", "HEAD", "--", "tools").splitlines()
                   if c in PHASE_FILES])

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )
    check("generic allowlist unchanged — no new writer/model/allowlist pair",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES
          and len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("still exactly one anchor-creation pair", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check("engagements remains prohibited generically",
          is_prohibited_table("engagements") and not is_allowed_table("engagements"))
    check("clients remains never writable by any controlled path",
          is_never_writable_table("clients"))
    check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx"))
    check("docs/Peak_Investor_Overview_AI.docx is still tracked and untouched",
          "docs/Peak_Investor_Overview_AI.docx" in git("ls-files", "docs"))


# --------------------------------------------------------------------------- 2. plan doc


def plan_doc_checks() -> None:
    print("\n2. The Phase 64 plan states its decision and its limits")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("plan content checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    f = flat(doc)
    for phrase, label in (
        ("planning-only", "the phase decision is planning-only"),
        ("no production write", "no production write is authorized"),
        ("no production record was created", "no production record was created"),
        ("no artifact body was created or committed", "no artifact body was committed"),
        ("needs_review", "R8 remains needs_review"),
        ("authoritative=false", "R8 remains non-authoritative"),
        ("internal_test artifacts only", "R1-R7 are internal_test artifacts only"),
        ("metadata only", "source ingestion persists metadata only"),
        ("outside the repository", "artifact bodies live outside the repository"),
        ("evidence_references", "evidence_references are named"),
        ("after source ingestion", "evidence_references come after source ingestion"),
        ("report drafting and capsule publication are not authorized",
         "report drafting and capsule publication are not authorized"),
        ("agentnet", "the AgentNet resolver is addressed"),
        ("resolver is live", "the AgentNet resolver is described as live"),
        ("gated and unauthorized", "publication remains gated and unauthorized"),
        ("phase 65", "the Phase 65 execution order is named"),
        ("source_ingestion_records", "source_ingestion_records is the Phase 65 target"),
        ("internal_test_001", "the engagement anchor is named"),
        ("internal_peak_only", "the authorization scope is named"),
        ("ing_4fb70519cbf84401", "the Phase 63 R8 record is cited"),
    ):
        check(f"plan states: {label}", phrase in f)

    check("plan states the hash requirement as SHA-256 over exact bytes",
          "sha-256" in f and "exact bytes" in f)
    check("plan states a changed hash must conflict rather than overwrite",
          "idempotency_conflict" in f and "never an overwrite" in f)
    check("plan embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("plan prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("plan contains no obviously client-like organisation name",
          not CLIENT_LIKE_RE.search(scannable(doc)))


# --------------------------------------------------------------------------- 3. per-request


def request_coverage_checks() -> None:
    print("\n3. R1 through R7 are each fully specified")
    if not os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)):
        check("request coverage checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    blocks = request_blocks(doc)
    check("the plan defines a section for each of R1 through R7",
          all(r in blocks for r in REQUESTS))
    missing = [r for r in REQUESTS if r not in blocks]
    if missing:
        print("        missing sections: " + ", ".join(missing))

    required = (
        ("purpose", "**Purpose:**"),
        ("dependency on R8", "**Dependency on R8:**"),
        ("artifact type", "**Artifact type:**"),
        ("external filename", "**External filename:**"),
        ("logical location reference", "**Logical location reference:**"),
        ("packet_reference_id", "**`packet_reference_id`:**"),
        ("schema name/version", "**`packet_schema_name` / version:**"),
        ("packet_source_type", "**`packet_source_type`:**"),
        ("hash requirement", "**Hash requirement:**"),
        ("taxonomy categories", "**Taxonomy categories:**"),
        ("downstream deliverable", "**Downstream deliverable:**"),
        ("evidence_reference implications", "**Future `evidence_reference` implications:**"),
        ("internal_test-only safety", "**Internal_test-only safety:**"),
    )
    problems: list = []
    for rid in REQUESTS:
        body = blocks.get(rid, "")
        for label, marker in required:
            if marker not in body:
                problems.append(f"{rid}:{label}")

    check("every request states purpose, R8 dependency, type, filename, logical reference, "
          "packet id, schema, source type, hash, taxonomy, deliverable, evidence implications, "
          "and safety",
          not problems)
    if problems:
        print("        missing: " + ", ".join(problems[:16]))

    # Minimum expected fields or document sections — one or the other, per artifact type.
    no_fields = [r for r in REQUESTS
                 if not re.search(r"\*\*Minimum expected (?:fields|document sections):\*\*",
                                  blocks.get(r, ""))]
    check("every request states its minimum expected fields or document sections", not no_fields)
    if no_fields:
        print("        missing minimums: " + ", ".join(no_fields))

    # Structural conventions, per request.
    bad_ref, bad_dir, bad_tax, bad_safety = [], [], [], []
    for rid in REQUESTS:
        body = blocks.get(rid, "")
        slug = rid.lower()
        if not re.search(rf"internal-test-artifact://phase65/{slug}-[a-z0-9-]+-v1", body):
            bad_ref.append(rid)
        if not re.search(rf"\*\*External filename:\*\*\s*`{slug}_[a-z0-9_]+_v1\.", body):
            bad_dir.append(rid)
        tax = re.search(r"\*\*Taxonomy categories:\*\*(.+?)(?=\n- \*\*)", body, re.S)
        if not tax or not re.search(r"\b(0[1-9]|1[0-4])\b", tax.group(1)):
            bad_tax.append(rid)
        if not ("no real client data" in body.lower()
                and "not be committed" in body.lower()):
            bad_safety.append(rid)

    check("every logical reference follows internal-test-artifact://phase65/<slug>-v1",
          not bad_ref)
    check("every external filename is versioned and matches its request", not bad_dir)
    check("every request maps to at least one numbered Intake Taxonomy V0 category", not bad_tax)
    check("every request states it must hold no real client data and must not be committed",
          not bad_safety)
    for name, bad in (("reference", bad_ref), ("filename", bad_dir),
                      ("taxonomy", bad_tax), ("safety", bad_safety)):
        if bad:
            print(f"        {name} problems: " + ", ".join(bad))

    check("the plan names the approved out-of-repo Phase 65 artifact directory",
          "peak-internal-test-artifacts/phase65" in doc)
    check("the plan gives an explicit Phase 65 recommendation with reasons",
          re.search(r"(?mi)^\*\*Recommendation:", doc) is not None
          and "why this rather than" in flat(doc))
    check("the plan states Phase 65 creates source ingestion records only, not evidence",
          "creates source ingestion records only" in flat(doc))


# --------------------------------------------------------------------------- 4. no example data


def example_data_checks() -> None:
    print("\n4. Field names only — no example rows, fixtures, or artifact bodies")
    if not os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)):
        check("example-data checks (skipped: the doc is missing)", False)
        return
    doc = read(DOC_REL)

    check("the plan states no example rows were committed",
          "no example rows" in flat(doc))
    # A fake SKU reads as an uppercase alphabetic prefix joined to digits by a dash or an
    # underscore. The only legitimate token of that shape in this plan is the hash algorithm
    # name, so it is exempted by name rather than by loosening the pattern.
    TECHNICAL_TOKENS = {"SHA-256", "SHA-512", "UTF-8"}
    idents = set(re.findall(r"\b[A-Z]{2,}[-_]\d{2,}\b", doc)) - TECHNICAL_TOKENS
    check("the plan contains no SKU-like sample identifier", not idents)
    if idents:
        print("        sample identifiers: " + ", ".join(sorted(idents)))
    check("the plan contains no CSV-style data row",
          not re.search(r"(?m)^\s*[A-Za-z0-9_-]+\s*,\s*[A-Za-z0-9_-]+\s*,\s*\d+", doc))
    check("the plan embeds no JSON object literal that could carry sample data",
          not re.search(r"(?m)^\s*[\{\[]\s*$", doc))
    check("the plan quotes no quantity-with-unit sample value",
          not re.search(r"(?i)\b\d{2,}\s*(?:units|eaches|cases|pallets|ea\b)", doc))

    tracked = git("ls-files").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    both = tracked + untracked
    for base in ARTIFACT_BASENAMES:
        check(f"no artifact body '{base}' is tracked or staged in the repository",
              not [t for t in both if base in t])
    check("no internal-test-artifact directory is tracked or staged",
          not [t for t in both if ARTIFACT_DIR_MARK in t])
    check("no fixtures/examples/sample-packet directory is tracked",
          not [t for t in tracked
               if re.match(r"^(fixtures|examples|samples|sample_packets)/", t)])
    check("no sample or fixture packet file is tracked",
          not [t for t in tracked
               if re.search(r"(?i)(fixture|sample|example)[^/]*\.(json|ya?ml|csv|txt)$", t)])
    check("this phase adds no .json, .csv, or .txt artifact",
          not [c for c in PHASE_FILES if c.endswith((".json", ".csv", ".txt"))]
          and not [c for c in untracked if c.endswith((".json", ".csv", ".txt"))])
    check("no intake note body file is tracked in the repository",
          not [t for t in tracked if "internal_test_intake_note" in t and t.endswith(".txt")])


# --------------------------------------------------------------------------- 5. doc propagation


def doc_propagation_checks() -> None:
    print("\n5. The surrounding docs record Phase 64 and what it does not authorize")
    targets = ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
               "docs/DATABASE_SCAFFOLD.md",
               "docs/PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md",
               "docs/PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md")
    for rel in targets:
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records that Phase 63 registered R8",
              "phase 63" in blob and "r8" in blob)
        check(f"{name} records that Phase 64 defines the R1-R7 artifact collection",
              "phase 64" in blob
              and re.search(r"r1[-–—]r7 artifact collection", blob) is not None)
        check(f"{name} states Phase 65 registers source ingestion, not evidence yet",
              "phase 65" in blob and "source_ingestion_records" in blob
              and "not `evidence_references` yet".replace("`", "") in blob.replace("`", ""))
        check(f"{name} states artifact bodies remain outside the repository",
              "outside the repository" in blob)
        check(f"{name} states capsule publication remains unauthorized despite the live resolver",
              "capsule publication remains unauthorized" in blob and "agentnet" in blob)

    mk = read("Makefile")
    check("Makefile declares validate-phase64", "validate-phase64" in mk)
    check("validate depends on validate-phase64",
          re.search(r"^validate:.*validate-phase64", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)


# --------------------------------------------------------------------------- 6. isolation


def isolation_checks() -> None:
    print("\n6. Phase 64 contacts no production and creates no record")
    src = read(HARNESS_REL)
    code = code_only(src)

    check("this harness creates no engine and opens no database connection",
          "create_engine" not in code and "create_session_factory" not in code)
    check("this harness imports no writer and invokes no persist_* function",
          not re.search(r"persist_\w+\s*\(", code) and "source_ingestion_writer" not in code)
    check("this harness reads no role/environment variable",
          not re.search(r"os\.environ", code))
    check("this harness names the role variables only as a scrub list, never reading one",
          all(v in src for v in ROLE_VARS))
    check("this harness resolves no home-directory path", "expanduser" not in code)
    check("this harness never reads the external artifact directory",
          not re.search(r"open\s*\(\s*[a-z_]*artifact", code))
    check("this harness embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    check("this phase's files are only docs, this harness, and the Makefile",
          all(c.startswith("docs/") or c == HARNESS_REL or c == "Makefile"
              for c in PHASE_FILES))
    absent = [c for c in PHASE_FILES if not os.path.isfile(os.path.join(REPO_ROOT, c))]
    check("every declared Phase 64 file is present in the repository", not absent)
    if absent:
        print("        missing: " + ", ".join(absent))
    check("this phase declares no writer, model, allowlist, migration, or tool file",
          not [c for c in PHASE_FILES
               if c.startswith(("peak/", "tools/", "alembic/")) or c.endswith("_writer.py")])

    for rel in PHASE_FILES:
        if not os.path.isfile(os.path.join(REPO_ROOT, rel)):
            continue
        blob = read(rel)
        name = os.path.basename(rel)
        check(f"{name} contains no obviously client-like organisation name",
              not CLIENT_LIKE_RE.search(scannable(blob)))
        check(f"{name} embeds no real-looking DSN", not REAL_DSN_RE.search(blob))
        check(f"{name} embeds no secret-like assignment",
              not re.search(r"(?i)(password|api[_-]?key|secret|private[_-]?key|access[_-]?key)"
                            r"\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{8,}", blob))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 64 internal test R1-R7 source artifact collection plan check")
    print("=" * 70)

    baseline_checks()
    plan_doc_checks()
    request_coverage_checks()
    example_data_checks()
    doc_propagation_checks()
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
