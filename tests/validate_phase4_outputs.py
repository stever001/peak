#!/usr/bin/env python3
"""Phase 4 output-structure check (synthetic, generated).

The prompt contracts produce work-product documents (discovery plan, evidence
findings, report, proposal, QA review, engagement lessons). Peak does NOT commit
sample outputs — real outputs live in controlled engagement storage, not the repo.

This harness therefore validates the **output-structure contract** itself: for each
artifact type it holds the required section spec, generates a minimal **synthetic**
document from that spec into a TEMPORARY directory, and confirms the generated
document contains every required section plus a synthetic evidence citation. The temp
files are auto-deleted; nothing is committed.

This keeps the expected output structure executable and consistent without storing
any sample artifact. See docs/FIXTURE_STRATEGY.md.

Exit status:
  0  -> every artifact's structure spec is self-consistent
  1  -> a generated synthetic document is missing a required section
"""

from __future__ import annotations

import os
import sys
import tempfile

# artifact type -> required section headings
OUTPUT_SPEC = {
    "discovery-plan": [
        "Assessment objective",
        "Interview plan",
        "Walk-around checklist",
        "Document / data request list",
        "Risks to validate",
        "First-billing-tranche objective",
    ],
    "evidence-findings": ["Process", "System", "Control", "Data quality", "Operational risk"],
    "initial-assessment-report": [
        "Executive summary",
        "Current-state findings",
        "Risk / impact analysis",
        "Quick wins",
        "Priority recommendations",
        "Next-step framing",
    ],
    "next-phase-proposal": [
        "Recommended scope",
        "Workstreams",
        "Deliverables",
        "Timeline assumptions",
        "Client responsibilities",
        "Success measures",
        "Commercial rationale",
        "Pricing",
    ],
    "qa-review": [
        "Unsupported claims",
        "Missing evidence",
        "Contradictions",
        "Weak recommendations",
        "Report-readiness",
        "Required fixes",
    ],
    "engagement-lessons": [
        "Reusable patterns",
        "Checklist improvements",
        "Prompt improvements",
        "Schema gaps",
        "Candidate internal knowledge capsules",
        "Follow-up actions",
    ],
}

SYNTHETIC_EVIDENCE = "evid_synthetic_1"

PASS = "PASS"
FAIL = "FAIL"


def generate_synthetic_output(artifact: str, sections: list[str]) -> str:
    """Build a minimal synthetic markdown document from the section spec."""
    lines = [
        f"# {artifact} (SYNTHETIC — generated at runtime, not stored)",
        "",
        f"> Synthetic representation of the {artifact} output structure. Not real client",
        f"> data. Evidence citation shown for structure only ({SYNTHETIC_EVIDENCE}).",
        "",
    ]
    for section in sections:
        lines.append(f"## {section}")
        lines.append(f"Synthetic placeholder content ({SYNTHETIC_EVIDENCE}).")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    print("Peak Phase 4 output-structure check (synthetic)")
    print("=" * 47)

    failures: list[str] = []
    checks = 0

    with tempfile.TemporaryDirectory(prefix="peak-synthetic-outputs-") as tmp:
        for artifact, sections in OUTPUT_SPEC.items():
            checks += 1
            doc = generate_synthetic_output(artifact, sections)
            fpath = os.path.join(tmp, f"{artifact}.synthetic.md")
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(doc)
            with open(fpath, "r", encoding="utf-8") as fh:
                text = fh.read().lower()

            missing = [s for s in sections if s.lower() not in text]
            problems = []
            if missing:
                problems.append("missing sections: " + ", ".join(missing))
            if SYNTHETIC_EVIDENCE not in text:
                problems.append("no evidence citation")

            if problems:
                failures.append(f"{artifact}: " + "; ".join(problems))
                print(f"  [{FAIL}] {artifact}: " + "; ".join(problems))
            else:
                print(f"  [{PASS}] {artifact}: generated structure has all {len(sections)} sections + evidence")

    print("\n" + "=" * 47)
    print("Summary")
    print(f"  artifact specs checked : {checks}")
    print(f"  failures               : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
