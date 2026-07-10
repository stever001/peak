#!/usr/bin/env python3
"""Phase 5 packet-runner smoke check (temporary synthetic fixture).

Lightweight, stdlib-only. Confirms the human-in-the-loop packet runner works on a
`--packet` file and stays honest about what it does NOT do. The runner has no demo or
sample mode; this test generates a **temporary synthetic packet** with `tempfile`,
passes it to `--packet`, inspects the output, and deletes the temp file afterwards.
The synthetic packet is a test-only fixture, not a workflow feature and not committed.

Checks:
  * tools/packet_runner.py exists;
  * running `--packet <temp fixture>` exits 0;
  * output contains the fixture's packet_id, the prompt-contract list, and the
    no-LLM / no-AgentNet / not-stored disclaimers;
  * the runner writes no files (nothing is stored).

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synthetic_fixtures as sf  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(REPO_ROOT, "tools", "packet_runner.py")

REQUIRED_OUTPUT = [
    ("synthetic packet_id", "pkt_synthetic_fixture"),
    ("prompt-contract list header", "AVAILABLE PROMPT CONTRACTS"),
    ("intake contract", "prompts/intake/normalize-client-intake.prompt.md"),
    ("learning contract", "prompts/learning/extract-engagement-lessons.prompt.md"),
    ("no-LLM disclaimer", "No LLM call was made"),
    ("no-AgentNet disclaimer", "No AgentNet lookup was made"),
    ("not-stored disclaimer", "No packet was written, stored, or committed"),
]

PASS = "PASS"
FAIL = "FAIL"


def main() -> int:
    print("Peak Phase 5 packet-runner smoke check (--packet temp fixture)")
    print("=" * 62)

    failures: list[str] = []

    if not os.path.isfile(RUNNER):
        print(f"  [{FAIL}] tools/packet_runner.py: file not found")
        print(f"\nRESULT: {FAIL} (1 issue)")
        return 1
    print(f"  [{PASS}] tools/packet_runner.py exists")

    # Generate a temporary synthetic packet, run --packet on it, then delete it.
    # Use a separate empty cwd so we can confirm the runner writes nothing.
    with tempfile.TemporaryDirectory(prefix="peak-runner-fixture-") as fixture_dir, \
         tempfile.TemporaryDirectory(prefix="peak-runner-cwd-") as cwd:
        packet_path = os.path.join(fixture_dir, "engagement-packet.synthetic.json")
        with open(packet_path, "w", encoding="utf-8") as fh:
            json.dump(sf.synthetic_engagement_packet(), fh)

        proc = subprocess.run(
            [sys.executable, RUNNER, "--packet", packet_path],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        wrote_files = sorted(os.listdir(cwd))
    # (both temp dirs — the fixture and the cwd — are deleted on exit)

    if proc.returncode == 0:
        print(f"  [{PASS}] --packet <temp fixture> exits 0")
    else:
        failures.append(f"runner exited {proc.returncode}")
        print(f"  [{FAIL}] runner exited {proc.returncode}")
        if proc.stderr.strip():
            print("        stderr:", proc.stderr.strip().splitlines()[-1])

    out = proc.stdout
    for label, needle in REQUIRED_OUTPUT:
        if needle in out:
            print(f"  [{PASS}] output contains {label}")
        else:
            failures.append(f"output missing {label} ('{needle}')")
            print(f"  [{FAIL}] output missing {label} ('{needle}')")

    if wrote_files:
        failures.append(f"runner wrote files: {wrote_files}")
        print(f"  [{FAIL}] runner wrote files to cwd: {wrote_files}")
    else:
        print(f"  [{PASS}] runner stored nothing (empty cwd after run)")

    print("\n" + "=" * 62)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
