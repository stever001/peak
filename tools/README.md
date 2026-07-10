# Tools

Local, human-in-the-loop helpers for Peak consultants. **Not an agent runtime.**
Nothing here calls an LLM, API, database, AgentNet, or any network service, and nothing
is stored.

## `packet_runner.py`

A read-only helper that takes an `EngagementPacket` and orients a consultant toward the
right prompt contracts. It does **not** run the workflow — the consultant runs the LLM
by hand and owns the output.

```bash
# A real packet from controlled engagement storage (not the repo):
python3 tools/packet_runner.py --packet /path/to/engagement-packet.json

# Via the Makefile (PACKET is required):
make packet-summary PACKET=/path/to/engagement-packet.json
```

`--packet` is **required** — there is no demo or sample mode. The repo stores no
packet; point `--packet` at a real packet held in controlled engagement storage (an
authorized engagement workspace). Tests may pass a temporary synthetic fixture file,
but that is test-only, not a workflow feature.

### What it does
1. Loads the packet JSON from the `--packet` path.
2. Runs a lightweight structural check.
3. Prints a consultant-readable summary: `packet_id`, `engagement_label`,
   `assessment_stage`, client organization, inventory environment, known systems, and
   counts of evidence / interviews / visual / workflow observations.
4. Lists the available prompt contracts by workflow (intake → … → learning).
5. Prints next-step instructions: open the contract, paste the packet JSON into its
   reusable body, review, and save the reviewed output to controlled engagement storage
   (not the repo).

### What it explicitly does NOT do
- No LLM call.
- No AgentNet lookup (AgentNet is intended future grounding architecture, not
  integrated).
- No client-facing output generated automatically.
- No API, database, or network request.
- **No packet written, stored, or committed** — the runner only reads and prints.

### Exit codes
| Code | Meaning |
| --- | --- |
| `0` | Packet loaded/summarized (structural check passed). |
| `1` | Packet missing, invalid JSON, or failed the structural check. |
| `2` | Bad CLI usage (`--packet` missing). |

### Tested by
`tests/validate_phase5_runner.py` (stdlib-only), part of `make validate`.
