#!/usr/bin/env python3
"""Phase 5 packet-runner smoke check.

Lightweight, stdlib-only. Confirms the human-in-the-loop packet runner works and
stays honest about what it does NOT do. It runs the runner as a subprocess against
the example packet and inspects its output.

Checks:
  * tools/packet_runner.py exists;
  * the documented example command exits 0;
  * output contains the packet_id, the engagement_label, the prompt-contract list,
    and the no-LLM / no-AgentNet disclaimers.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(REPO_ROOT, "tools", "packet_runner.py")
PACKET = os.path.join(REPO_ROOT, "examples", "engagement-packet.example.json")

# (label, substring that must appear in stdout)
REQUIRED_OUTPUT = [
    ("packet_id", "pkt_alpha_2026"),
    ("engagement_label", "Client Alpha - initial inventory assessment"),
    ("prompt-contract list header", "AVAILABLE PROMPT CONTRACTS"),
    ("intake contract", "prompts/intake/normalize-client-intake.prompt.md"),
    ("learning contract", "prompts/learning/extract-engagement-lessons.prompt.md"),
    ("no-LLM disclaimer", "No LLM call was made"),
    ("no-AgentNet disclaimer", "No AgentNet lookup was made"),
    ("no client-facing disclaimer", "No client-facing output was generated automatically"),
]

PASS = "PASS"
FAIL = "FAIL"


def main() -> int:
    print("Peak Phase 5 packet-runner smoke check")
    print("=" * 38)

    failures: list[str] = []

    if not os.path.isfile(RUNNER):
        print(f"  [{FAIL}] tools/packet_runner.py: file not found")
        print(f"\nRESULT: {FAIL} (1 issue)")
        return 1
    print(f"  [{PASS}] tools/packet_runner.py exists")

    proc = subprocess.run(
        [sys.executable, RUNNER, "--packet", PACKET],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if proc.returncode == 0:
        print(f"  [{PASS}] example command exits 0")
    else:
        failures.append(f"example command exited {proc.returncode}")
        print(f"  [{FAIL}] example command exited {proc.returncode}")
        if proc.stderr.strip():
            print("        stderr:", proc.stderr.strip().splitlines()[-1])

    out = proc.stdout
    for label, needle in REQUIRED_OUTPUT:
        if needle in out:
            print(f"  [{PASS}] output contains {label}")
        else:
            failures.append(f"output missing {label} ('{needle}')")
            print(f"  [{FAIL}] output missing {label} ('{needle}')")

    print("\n" + "=" * 38)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
