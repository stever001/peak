# Peak Advisory Engagement Boundary

Specialized authority for Contract **C21** (Phase 217). Enforced in code by
`peak/workspace/advisory_boundary.py`.

## Rule

Default Peak engagement work is **advisory and improvement-oriented**.

It may examine workflows, records, policies, controls, physical operations, employee practices,
operational consistency and supporting evidence, to understand how the business operates and to
identify practical improvements.

It MUST NOT be framed, generated, executed, scored, labelled or reported as:

- an audit;
- a compliance test;
- certification;
- assurance;
- a finding of non-compliance;
- a control deficiency determination;

unless the engagement was explicitly created under a separate governed audit capability. **Peak has
no such capability** (`GOVERNED_AUDIT_CAPABILITY_AVAILABLE = False`). Adding one would be a separate,
deliberate phase with its own authority; it can never be reached by relabelling advisory work.

Normal Peak language emphasizes observed workflow, variance, friction, inconsistency, rework,
delay, error, operational impact, improvement opportunity and recommended process change.

## Where it is enforced

| Surface | Enforcement |
|---|---|
| Roadmap item framing (title, problem, rationale, expected outcome) | refused with `advisory_boundary` (422) |
| Engagement phase title, scope and origin note | refused with `advisory_boundary` |
| Guided task framing (title, instructions, why, what to observe, questions, expected result, inclusion reason) | refused with `advisory_boundary` |
| Peak Method phase templates | every string checked by the Phase 217 harness |
| Vocabularies (roadmap, phase and task statuses, origins, record kinds, readiness codes) | contain no audit, compliance, pass/fail or scoring term (harness) |
| Readiness | answers "is the required work complete?", never "did the client pass?" |

The framing check matches, case-insensitively on word boundaries: *audit\**, *(non-)complian\**,
*certif\**, *assurance*, *attest\**, *deficienc\**, *material weakness\**, *violation\**. "Controls"
is permitted: examining how controls work in practice is advisory work.

**Not filtered:** consultant notes and task records. They record what actually happened, which can
legitimately include, for example, "the client's external auditor visits in March". Recording a fact
is not framing the work.

## Existing material

The Phase 216 discovery instrument already states that Peak does not certify compliance, and cites
some audit and control literature (COSO, AU-C 501) as *source provenance* for question design. Those
citations describe where a question's wording came from; they do not frame Peak work as an audit.
The `control check` purpose type in the instrument is a question purpose label, not a test result.
Both are acceptable under this rule and are not changed by Phase 217.
