#!/usr/bin/env python3
"""Phase 7 repo-hygiene / data-artifact guard.

Lightweight, stdlib-only. Enforces that the repository stores source assets only and
is not framed around redaction:

  1. Policy docs present    - DATA_HANDLING_POLICY.md and FIXTURE_STRATEGY.md exist and
                              contain their required markers.
  2. No stored data artifacts - forbidden paths (e.g. examples/, the old
                              REDACTION_GUIDE.md, any *.example.json / *.example.md,
                              sample outputs, redacted notes) must NOT exist.
  3. No redaction framing   - tracked docs/code must not reintroduce redaction-policy
                              framing. A historical mention that it was *removed* is
                              allowed (a line containing "remov").

Exit status:
  0  -> repo is clean of data artifacts and redaction framing; policy docs present
  1  -> a forbidden artifact/path exists, a required doc/marker is missing, or
        redaction framing was reintroduced
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 1. required policy docs -------------------------------------------------
REQUIRED_DOCS = {
    "docs/DATA_HANDLING_POLICY.md": [
        "purpose and scope",
        "not open source",
        "source assets only",
        "must not be committed",
        "controlled engagement",
        "resolver",
        "authorized",
        "governance",
        "human review",
        "agentnet",
        "future work",
    ],
    "docs/FIXTURE_STRATEGY.md": [
        "no data artifacts are stored",
        "synthetic",
        "temporary",
        "not committed",
        "real client data is never used",
        "resolver",
    ],
}

# --- 2. forbidden stored-artifact paths --------------------------------------
FORBIDDEN_PATHS = [
    "examples",
    "docs/REDACTION_GUIDE.md",
]

# --- 3. redaction-framing scan -----------------------------------------------
# Directories/files to scan for reintroduced redaction framing.
SCAN_ROOTS = ["README.md", "Makefile", "docs", "tests", "tools", "prompts", "schemas", "agents"]
SCAN_EXTS = (".md", ".py", ".json", ".txt", "Makefile")
# These files legitimately discuss that redaction framing was *removed*; they are the
# only sanctioned places the word may appear. Everything else must be free of it.
SCAN_SKIP = {
    os.path.abspath(__file__),
    # Sibling guards that enforce the same source-only/no-artifact rules and therefore
    # legitimately name the forbidden paths.
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase8_architecture.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase9_governance.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase10_database_plan.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase11_db_scaffold.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "docs", "DATA_HANDLING_POLICY.md")),
    os.path.abspath(os.path.join(REPO_ROOT, "docs", "FIXTURE_STRATEGY.md")),
}

PASS = "PASS"
FAIL = "FAIL"


def iter_scan_files():
    for root in SCAN_ROOTS:
        p = os.path.join(REPO_ROOT, root)
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for dirpath, _, files in os.walk(p):
                for f in files:
                    fp = os.path.join(dirpath, f)
                    if fp.endswith(SCAN_EXTS) or os.path.basename(fp) == "Makefile":
                        yield fp


def find_forbidden_globs():
    """Recursively flag any *.example.json / *.example.md artifacts anywhere."""
    hits = []
    for dirpath, dirnames, files in os.walk(REPO_ROOT):
        if ".git" in dirpath.split(os.sep):
            continue
        for f in files:
            if f.endswith(".example.json") or f.endswith(".example.md") or "redacted" in f:
                hits.append(os.path.relpath(os.path.join(dirpath, f), REPO_ROOT))
    return hits


def main() -> int:
    print("Peak Phase 7 repo-hygiene / data-artifact guard")
    print("=" * 47)

    failures: list[str] = []

    # 1. Required policy docs.
    print("\n1. Policy docs")
    for rel, needles in REQUIRED_DOCS.items():
        path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(path):
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().lower()
        missing = [n for n in needles if n not in text]
        if missing:
            failures.append(f"{rel}: missing " + ", ".join(missing))
            print(f"  [{FAIL}] {rel}: missing " + ", ".join(missing))
        else:
            print(f"  [{PASS}] {rel}: all {len(needles)} markers present")

    # 2. Forbidden stored-artifact paths.
    print("\n2. No stored data artifacts")
    for rel in FORBIDDEN_PATHS:
        if os.path.exists(os.path.join(REPO_ROOT, rel)):
            failures.append(f"forbidden path exists: {rel}")
            print(f"  [{FAIL}] forbidden path exists: {rel}")
        else:
            print(f"  [{PASS}] absent: {rel}")
    globs = find_forbidden_globs()
    if globs:
        for g in globs:
            failures.append(f"forbidden artifact: {g}")
            print(f"  [{FAIL}] forbidden artifact: {g}")
    else:
        print(f"  [{PASS}] no *.example.* or redacted artifacts found")

    # 3. Redaction-framing scan.
    print("\n3. No redaction framing (historical 'removed' mentions allowed)")
    offenders = []
    for fp in iter_scan_files():
        if os.path.abspath(fp) in SCAN_SKIP:
            continue
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    low = line.lower()
                    if "redact" in low and "remov" not in low:
                        offenders.append(f"{os.path.relpath(fp, REPO_ROOT)}:{i}")
        except (OSError, UnicodeDecodeError):
            continue
    if offenders:
        for o in offenders:
            failures.append(f"redaction framing: {o}")
            print(f"  [{FAIL}] redaction framing at {o}")
    else:
        print(f"  [{PASS}] no active redaction framing in tracked docs/code")

    print("\n" + "=" * 47)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
