# Phase 91 — Drift, Test-Sprawl, and Parallel Workflow Review

**Type:** Review and policy. Docs-only (one `README.md` accuracy correction).

**What this phase did not do.** No database of any kind was contacted — not production, not
`peak_lab`, not `peak_lab_scenario`. No environment file was sourced and no environment value was
read. No provider, cloud, or API command was run. No Alembic `upgrade`, `downgrade`, or `stamp` was
issued. **No migration 015 was created.** No writer was invoked, no record was created, no scenario
row was read or touched, no schema was added, no model or writer was added, and
`docs/Peak_Investor_Overview_AI.docx` was not touched. This phase inspected the repository, ran
offline validation, and wrote documentation.

**Baseline:** the committed Phase 90 commit `64a8e0b` — *Bootstrap lab engagement anchor*.

---

## 1. Why this phase exists

Phases 84–90 were each individually defensible, but the aggregate shape had become a concern: the
repository now carries 72 phase validation harnesses producing 9,292 pass lines, and prior-phase
harnesses have repeatedly frozen later legitimate work and needed repair. This phase asks whether
validation cost is still proportionate to risk, and whether guardrail maintenance is displacing
the workflow the guardrails exist to protect.

## 2. Drift assessment

**The objective is unchanged and still correct:** turn scenario measurements into controlled Peak
records, and then into evidence, source-ingestion, and review records.

**Progress against it is thinner than the phase count suggests.** Of Phases 84–90:

| Class | Phases | Note |
|---|---|---|
| Directly advanced the workflow | 85, 88, 90 | 85 seeded the lab scenario; 88 measured it read-only; 90 created **one** record |
| Guardrail repair or new gate | 84, 86, 89 | 84 fixed the Alembic target guard; 86 swept 22 expiring ancestry checks; 89 added the lab writer gate |
| Documentation / navigation repair | 87 | The phase index |

Three of seven phases advanced the workflow, and only one of those produced a durable Peak record.
The measurement-to-record leg — the actual objective — remains one row deep.

**The highest-risk form of drift is not the safety posture; it is that the safety posture has
become self-generating.** Concretely:

- Every phase that ships code has shipped a harness, at a near-constant rate of roughly one per
  phase from Phase 33 through Phase 72. This is habit, not risk assessment.
- Harnesses now break each other. Phase 84 had to repair 12 prior harnesses, Phase 89 repaired
  Phase 72's, and Phase 90 repaired Phase 89's **one commit after it was written**. Time-to-breakage
  is shrinking faster than the sweep cadence that fixes it.
- The plan's last four "Next" entries are all statements of what remains *unauthorized*. No
  affirmative next workflow step is currently named.

**Acceptable safety work:** the Alembic target guard (84), the production writer enablement gate,
the lab writer enablement gate (89), and the runtime connectivity separation. These encode durable,
non-obvious invariants that would be expensive to rediscover.

**Necessary but regrettable test repair:** Phases 86 and the embedded repairs inside 84, 89, and 90.
Regrettable because the defect class was known — an equivalent commit-window bug had already been
fixed once before the wider window was reintroduced.

**Possible overengineering:** the per-phase harness convention itself, and the practice of proving
by assertion that a documentation paragraph exists.

## 3. Test-sprawl inventory

| Measure | Value |
|---|---|
| `tests/validate_phase*.py` harnesses | 72 |
| Make targets | 87 (72 `validate-phaseN`, plus `validate`, `db-check`, and gate/audit targets) |
| Pass lines from `make validate` | 9,292, 0 failures |
| Harness source lines | ~39,400 |
| Harnesses pinning a baseline commit SHA | 35 |
| Harnesses pinning `EXPECTED_MIGRATIONS` / `EXPECTED_TABLE_COUNT` | 31 each |
| Harnesses pinning `HEAD_REVISION` / `EXPECTED_WRITERS` | 27 each |
| Harnesses using working-tree file freezes | 34 |
| Harnesses using an authoring-time gate | 5 |

Assertion mass is concentrated in the record-chain harnesses: the ten largest each carry 150–185
checks, and Phases 59–72 alone contribute fourteen near-identical harnesses each proving "one more
record was created and nothing else moved."

### High-value tests — keep

- **Decision gates with real decision tables:** the production writer enablement gate, the lab
  writer enablement gate, the Alembic lab/production target guard, the runtime connectivity gate,
  and runtime database URL separation. These are behavioural, they exercise deny branches, and they
  assert that failure output carries no connection value.
- **Output-safety invariants:** no password, host, port, certificate path, query parameter, or whole
  connection string in any tool's output.
- **Schema contract checks:** enum parity against the schema contracts, governance/audit column
  presence on every controlled table, and the governed identifier collation policy.
- **Repo hygiene:** source-only repository, no committed data artifacts or credentials.
- **Writer behaviour proven against a local throwaway database:** insert-only, receipt shape,
  allowlist membership, no update or delete path, no raw SQL, idempotent replay.

### Brittle, duplicative, or over-specific — do not expand

- **Prose assertions.** The dominant brittleness class: harnesses asserting that an exact sentence
  appears in a document. These fail on rewording, not on regression. One harness already carries a
  dash-tolerant regex, which is direct evidence that prose drift has broken this pattern before.
- **Frozen global constants replicated across files.** `EXPECTED_MIGRATIONS`, `EXPECTED_TABLE_COUNT`,
  `HEAD_REVISION`, and `EXPECTED_WRITERS` are re-declared in 27–31 harnesses each. The next
  migration or the next writer fails all of them at once. This has already fired twice. It is the
  same "pin a moving global into N files" shape as the commit-window bug, in a slower form.
- **Ungated working-tree file freezes.** 34 harnesses assert a path has no pending diff, and only 5
  harnesses use the authoring-time gate that makes such a claim correct. An ungated freeze judges
  *every later phase's* uncommitted work against a past phase's allowlist. This is the exact defect
  repaired three separate times, and it is still present in the newest harnesses, including freezes
  on `alembic`, `peak/db`, `peak/db/enums.py`, and the controlled allowlist.
- **Phase-history assertions.** Harnesses whose bulk is proving that a past phase's document
  paragraph still exists. That is a changelog assertion, not a contract.
- **Makefile self-registration.** 36 harnesses assert their own Make target exists, so no harness
  can be retired without a cascade.

### Test patterns to avoid

1. Asserting exact prose or document wording.
2. Any recency-shaped history check — commit windows, `HEAD~N`, "last N commits". Ancestry via
   merge-base is the durable form.
3. Duplicating a moving global constant into many files instead of one shared module.
4. Freezing a file path without an authoring-time gate.
5. Adding a harness whose only job is to prove a phase happened.

## 4. Consolidation recommendation

**Recommended, but not in this phase.** All 9,292 checks currently pass and there is no active
failure or false red, so nothing was deleted or weakened here. Consolidation should be its own
scoped phase, taken in this order:

1. Extract the repeated baseline constants into one shared invariants module, so the next schema
   change is a one-file edit rather than a thirty-file edit. **This is the highest-value change and
   the one most likely to unblock future work.**
2. Extract the duplicated git helper pair and the source-only hygiene block into a shared helper.
3. Add the authoring-time gate to the remaining ungated file freezes.
4. Only then consider retiring phase-history assertions, which requires also unwinding the Makefile
   self-registration convention.

Steps 1–3 remove freeze risk without reducing coverage. Step 4 reduces coverage and needs its own
justification.

## 5. Validation policy for future phases

- **Do not add a phase harness by default.** A phase may ship without one.
- Add a harness only when it protects a **durable safety invariant** or a **repeatable contract**.
- Prefer shared helpers over repeated inline snippets.
- Prefer behaviour and property checks over commit-window or exact-prose checks.
- Do not add tests that freeze future legitimate work.
- Do not add a phase-specific test whose only purpose is proving a document paragraph exists.
- Keep validation cost proportional to risk.
- **A phase may be docs-only without adding a harness.**
- A lab measurement or writer phase may rely on the existing gates plus targeted verification
  instead of adding another permanent harness.
- A temporary out-of-repo script is acceptable for one-time measurement, provided the durable result
  is documented and the script does not become product behaviour.

## 6. Parallel agentic workflow guidance

Parallel read-only agents are an accepted way to speed up inspection, documentation, and measurement
work. **This phase used three of them** — one for the documentation families, one for harness
classification, and one for harness repair history — under bounded read-only prompts. Their claims
were re-verified directly before being recorded here.

**Acceptable for:**

- Independent read-only repository inspection.
- Documentation link checking.
- Test inventory.
- Comparing phase documents against commits.
- Summarizing risks across different document families.
- Running independent offline validations.
- Preparing candidate recommendations for the primary session to reconcile.
- Read-only lab measurement **only** when a phase explicitly authorizes it.

**Not acceptable for:**

- Simultaneous writes to the same files.
- Unsupervised commits or pushes.
- Database writes, migrations, or writer invocation.
- Environment or secret reads.
- Production access.
- Provider, cloud, or API commands.
- Destructive cleanup.
- Changing grants or credentials.
- AgentNet publication.

**Coordination rules:**

- **One primary session owns the final diff.** Parallel agents inspect and draft; the primary
  session reconciles conflicts and is accountable for what lands.
- Parallel agents receive bounded read-only prompts.
- If any agent needs live database, environment, cloud, or write access, **stop and get explicit
  approval**.
- No agent may print secrets, connection strings, hosts, ports, environment values, local secret
  paths, row bodies, or client data.
- Parallel output is summarized into value-free findings before entering documentation, and
  material claims are re-verified by the primary session before being recorded.

## 7. What Phase 92 should do

**Return to workflow execution.** Phase 92 should be the first lab source-ingestion write: take a
measurement already established read-only in Phase 88 and turn it into a controlled Peak
source-ingestion record against `peak_lab`, using the Phase 89 gate as-is.

It should name, before it runs: the writer, the records and expected count, the source measurement,
the authorization scope drawn from the closed vocabulary, the idempotency keys, the expected
receipts, the verification plan, and the cleanup posture — the last decided before the write, since
the runtime role has no removal path.

It should **not** add a new permanent harness unless a specific unsafe condition requires one, and
it should not create migration 015 or add schema, models, or writers.

**One defect was found and corrected in this phase.** `README.md`'s status banner read that the
repository "does not yet contain production agent logic, a database, or a frontend" — materially
false against 14 migrations, 18 controlled tables, and 12 writers. The banner now states the
controlled schema, the narrow create-only writers, and the validation and enablement gates, and
records that production write enablement remains false, that writer rehearsal happens only in the
controlled lab, and that there is still no frontend or client-facing application. The edit is
confined to the banner; no harness asserts that text, and the `source assets only` marker Phase 8
requires is elsewhere in the file and untouched.

## 8. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` (single head, linear chain) |
| Migrations | 14 |
| Controlled Peak tables | 18 |
| Controlled writers | 12 |
| Migration 015 | Does not exist |
| Production write enablement | None standing; gate reports false |
| Lab write enablement | Unchanged from Phase 90 |
| Phase 91 database activity | None of any kind |

Phase 91 changed no migration, table, writer, gate, or harness. Its only non-documentation-record
change is the `README.md` status-banner accuracy correction described above.
