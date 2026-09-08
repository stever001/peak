# Phase 103 — Closing the Intake → Discovery Prompt Seam

**Baseline.** `7792273` — *Exercise Phase 102 discovery workflow*.

**Classification.** Small product-facing prompt edit, plus a narrow repair to nine stale harness
freeze checks that the edit exposed. **Not a governance expansion.**
No database was contacted. No env file was read. No writer was invoked. No record was created. No
migration `015` was created. No schema, model, enum, writer, allowlist, or gate changed; **no new
harness was added**, and no executor or registry change was needed. `peak_lab` remains at **four
application rows by documented state only** — this phase did not connect to verify that.

---

## The seam

Exercising the two workflows back to back exposed a gap between them:

- **Intake's** useful human output is a consultant-readable brief, but its contract named only a
  `ClientIntake` JSON draft.
- **Discovery's** declared input was an `EngagementPacket` JSON containing `client_intake`, but the
  practical thing coming out of intake is that brief.

Nothing converted one to the other, so the hand-off these workflows exist to make routine was the
one step a consultant had to bridge by hand. Both exercises worked anyway — the substance was
present and the grounding rules are about substance — but the contracts did not describe how the
work is actually done.

## What changed

**Two prompt contracts, wording only.** No behaviour was removed and no output expectation was
weakened.

**Intake** (`prompts/intake/normalize-client-intake.prompt.md`)

- A **consultant intake brief** is now an allowed output *in addition to* the `ClientIntake` draft,
  for when a handoff is needed before a packet exists. The brief restates grounded material in
  prose; it never replaces the draft, and no field may appear in it that is not supported above it.
- **Thin first-call notes may produce a question-heavy brief, and that is the correct result** — not
  a failure. Return the questions rather than filling gaps with plausible warehouse facts.

**Discovery** (`prompts/discovery/generate-discovery-plan.prompt.md`)

- An `EngagementPacket` remains the **preferred** input — it is structured and its ids are
  referenceable. A **consultant intake brief is now accepted where no packet exists yet.**
- **A brief's unknowns stay unknown.** Where the brief names no system, SKU count, volume,
  headcount, site size, or financial context, none may appear in the plan; an absence is something
  to ask about, not a gap to fill.
- A first-tranche objective must not be sharpened when the intake gives no basis for one — say what
  would define it instead. The quality checklist now allows that case explicitly.

Both contracts keep their ten required sections and their copy-paste bodies, and the reusable bodies
were updated to match so an operator pasting the prompt gets the same rules.

`prompts/README.md` was updated in two table cells so its summary of each contract's input still
matches the contracts.

## What did not change

`ClientIntake` and `EngagementPacket` remain exactly as they were — **no schema was touched**, and
the brief is a handoff option, not a schema replacement. The registry paths still resolve, and the
mock executor needed no change: this is a prompt-level contract change, and the executor plans runs
without reading prompt text. Both agents were re-run through it after the edits and returned
`planned_mock_no_execution` at `draft` / `needs_review` with every side-effect flag false, unchanged.

## The nine stale harness freezes this exposed

The prompt edits are two files of wording, and they failed **nine** existing harnesses — every one on
the same check, and none on anything substantive:

```
check("schemas/, prompts/, agents/ untouched",
      not git("diff", "--name-only", "HEAD", "--", "schemas", "prompts", "agents"))
```

Phases 44, 49, 50, 51, 53, 54, 55, 56 and 57 each asserted this **unconditionally**. Each was an
authoring-time claim about *that phase's own* working tree, frozen into a permanent repository-wide
prohibition: any later phase editing any file under `prompts/`, `schemas/`, or `agents/` failed all
nine. Closing a prompt seam is exactly the kind of legitimate product work the freeze blocked.

The pattern was already recognised. In several of these files the checks immediately above and below
are guarded with `if phase_never_committed(HARNESS_REL):`, and a comment explains why — *"working-tree
freezes on shared files were authoring-time claims about this phase."* This one was simply left
unguarded.

**The repair applies that existing guard to the nine checks, and nothing else.** Each file has the
same number of `check()` calls before and after; the only lines removed are the nine freeze checks
themselves, each re-added inside the guard. Writer, model, allowlist, gate, migration-count,
table-count, collation, no-secrets, and no-client-data invariants remain unconditional, as does the
`docs/Peak_Investor_Overview_AI.docx` pending-diff check that sits directly beside several of them.
Three harnesses needed the small `phase_never_committed` helper added alongside their existing `git`
helper; one (Phase 44) uses `subprocess` directly and got the equivalent guard in its own local
style.

This is the same repair Phase 96 made for eight harnesses, and the liability Phase 99 named as the
largest live one in the repo. It is now nine more instances closed, and the class is worth a
deliberate sweep rather than a repair per phase.

## Next

Resume **evidence normalization**, DB-free, using the improved hand-off. Continue practical workflow
delivery.
