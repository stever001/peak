# Tools

Local, human-in-the-loop helpers for Peak consultants. **Not an agent runtime.**
Nothing here calls an LLM, API, database, AgentNet, or any network service.

## `packet_runner.py`

A read-only helper that takes an `EngagementPacket` and orients a consultant toward
the right Phase 3 prompt contracts. It does **not** run the workflow — the consultant
runs the LLM by hand and owns the output.

```bash
python3 tools/packet_runner.py --packet examples/engagement-packet.example.json
# or:
make packet-summary
```

### What it does
1. Loads the packet JSON locally.
2. Structurally checks it. If `jsonschema` is installed it additionally validates
   against `schemas/engagement-packet.schema.json` with **offline** `$ref` resolution
   (same approach as `tests/validate_phase2.py`); otherwise it falls back to a
   dependency-free structural check. Either way, **no network**.
3. Prints a consultant-readable summary: `packet_id`, `engagement_label`,
   `assessment_stage`, client organization, inventory environment, known systems, and
   counts of evidence / interviews / visual observations / workflow observations.
4. Lists the available prompt contracts by workflow (intake → discovery → evidence →
   reporting → proposal → qa → learning).
5. Suggests the sample-output target file for each workflow.
6. Prints next-step instructions: open the contract, paste the packet JSON into its
   reusable body, review, and save to the target.

### What it explicitly does NOT do
- No LLM call.
- No AgentNet lookup (AgentNet is intended future grounding architecture, not
  integrated).
- No client-facing output generated automatically.
- No API, database, or network request.

### Exit codes
| Code | Meaning |
| --- | --- |
| `0` | Packet loaded and summarized (structural check passed). |
| `1` | Packet missing, invalid JSON, or failed the structural check. |
| `2` | Bad CLI usage. |

### Tested by
`tests/validate_phase5_runner.py` (stdlib-only), part of `make validate`.
