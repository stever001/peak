# Phase 115 — Persisted Finding Statement

**Baseline:** `726dbb3` — *Persist Phase 114 evidence claim scope*.

## 1. Status

**Small product-functionality phase. No database access, no migration, no new writer, no new field.**
The persisted evidence → packet view → reporting path now carries a durable, human-readable **finding
statement** taken from stored state, so a report input no longer depends on caller-supplied summary
text.

With Phase 114's `claim_scope` and this phase's statement, **evidence created from here on carries
everything the reporting path needs**: what it is entitled to claim, and what it says.

## 2. Where the statement is persisted — an existing field, reused

`evidence_references.summary`. **No new field and no `details_json` key were added.**

The column already existed, and the Phase 21 controlled writer already populates it from
`draft.normalized_summary`. Its semantics are exactly right for this purpose and are documented in
two places already:

- the model: *"non-sensitive summary only"*;
- `schemas/evidence-reference.schema.json`, where `summary` is a **required** property described as
  *"Consultant-readable, non-sensitive summary or excerpt of the evidence. Do not place raw sensitive
  content here."*

So the statement is a governed short text field by contract, not a row body. **No migration `015`,
no schema change, no writer change, and no new write-time validation** — nothing new is being
written, so there is nothing new to validate.

### Why Phase 113 refused to read it, and what changed

Phase 113 declined to select `summary` under a blanket "no narrative column" rule, adopted when
nothing governed what an evidence item was entitled to claim. That rule was correct in general but
over-broad for this one field. Two things now make reading it safe and useful:

1. **Phase 114 governs the claim.** A statement is only ever carried into a finding by evidence whose
   persisted `claim_scope` is `operational_finding`.
2. **A server-side sensitivity guard.** The fetch selects the statement through a `CASE` that returns
   `NULL` whenever `sensitive_data_flag` is set, so a row flagged sensitive **transfers no text at
   all**.

`review_records.reason`, `engagements.engagement_label`, `source_system_references.location_descriptor`,
`details_json` bodies, packet bodies, and every other narrative column remain **never selected**.

## 3. Precedence and fallback

| Situation | Behaviour |
|---|---|
| Row carries a persisted `summary` | **Authoritative.** The caller's statement is not consulted and cannot override it |
| Row carries none (legacy) | Falls back to `ClaimScopePolicy.summaries`, now a **legacy fallback only** |
| Neither | **Stays missing.** The finding input's `finding_statement` is `None`, a warning names the evidence, and the packet view reports the text as not supplied |
| Row is `sensitive_data_flag` | Statement withheld at the database; treated as missing |
| Evidence is `source_availability_only` | Produces **no operational finding at all**, statement or not |

This mirrors the precedence Phase 114 established for `claim_scope`, deliberately — one rule, not two.

**Nothing generates prose.** No LLM call, no paraphrase, no inference, no template. A missing
statement is reported as missing.

## 4. What reporting receives

`ReportFindingInput` gains one field, `finding_statement`, carrying the cited evidence's persisted
statement exactly as stored. The `AgentTaskRequest` is unchanged and still carries only
finding-backed record ids.

## 5. What is unchanged

- **Recommendations and client-facing output remain blocked.** A statement makes a finding readable,
  not approved: the cited evidence is still unreviewed and low-reliability.
- **The Phase 107 row `evid_8151dad609974ea0` remains legacy.** It was not retrofitted, no update
  writer was added, no duplicate evidence was created, and `peak_lab` was not contacted or mutated.
  It reaches the reporting path through the legacy fallback, which is why the fallback was kept.
- Every controlled writer remains create-only. No migration, model, enum, table, allowlist, gate,
  prompt, schema, tool, or Makefile change.

## 6. Proof

The existing Phase 113 harness was extended again rather than a new one added:
**67 checks, passing** (was 58). It proves the persisted statement reaches the reporting input with
no caller policy, that a caller statement cannot override a persisted one, that a missing statement
stays missing and is never fabricated, that a legacy row still accepts the fallback, that
source-availability evidence produces no operational finding even when it carries a statement, that
the Phase 94 review still supports nothing, and that recommendations and client-facing output stay
blocked.

## 7. Expected transient validation state

While `peak/db/engagement_packet_reader.py` is uncommitted, two historical harnesses fail:

| Harness | Check |
|---|---|
| `validate_phase89_lab_writer_enablement_gate.py` | no controlled writer was added or edited |
| `validate_phase90_lab_engagement_anchor_bootstrap.py` | no controlled writer was added or edited |

Both check `git diff HEAD -- peak/db` — **the whole directory**, which is broader than the label.
**No controlled writer was edited in this phase** (`git diff HEAD -- peak/db/*_writer.py` is empty);
the only `peak/db` file touched is the read-only fetch module. These are authoring-time working-tree
freezes that self-resolve on commit, exactly as the four in Phase 114 did. They were deliberately
**not modified**.

## 8. Next product step

The persistence plumbing for the MVP reporting path is now complete: identity, relationships, review
targets, claim scope, and statement all come from stored state. **The next step should produce a
useful internal assessment — not more persistence plumbing.** The open question is what a consultant
actually receives from a finding-backed engagement, and what still has to be true before evidence can
be reviewed and a recommendation earned.
