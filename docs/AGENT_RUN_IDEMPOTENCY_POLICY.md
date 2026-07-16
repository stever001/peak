# Agent Run Idempotency Policy (Phase 20)

How the Phase 20 controlled writer ([`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md))
guarantees that a repeated authorized write of the same agent run does not create duplicate
`agent_run_records` rows, and how it distinguishes an exact replay from a conflicting reuse
of the same idempotency key.

## Why idempotency is DB-enforced

Application-only "check then insert" has a race: two concurrent writes can both pass the
check and both insert. Phase 20 relies on a **database uniqueness constraint** as the source
of truth, and treats an `IntegrityError` as an authoritative signal that a row already
exists. The application pre-check is only a fast path; correctness comes from the DB.

## Uniqueness boundary

The unique index `uq_agent_run_records_idem` covers:

```
(owner_id, client_id, engagement_id, idempotency_key)
```

Including the identity context (owner, client, engagement) — not the key alone — means an
idempotency key **cannot collide across clients or engagements**. The record type/action is
fixed for this table (`create_agent_run_record`), so it is implicit in the target table
rather than a separate column. This matches the existing schema convention where governance
identity fields are real indexed columns.

## Payload fingerprint (replay vs. replay conflict)

Alongside the key, each row stores a `payload_fingerprint`: a deterministic SHA-256 over the
canonical, order-independent payload/identity —

- `owner_id`, `client_id`, `engagement_id`, `subject_record_id`;
- `agent_name`, `workflow`, `requested_action`, `prompt_contract_path`;
- the **sorted** `input_record_ids`.

Two requests are the *same write* iff they share the idempotency boundary **and** the same
fingerprint. This is how **payload equivalence or conflict is determined**.

## Outcomes

At **write-time**, given a request whose identity and **stored authorization** scope have
already been validated against the DB:

- **Exact authorized replay** — same boundary, same fingerprint:
  - do **not** create a second row;
  - return an `idempotent_replay` receipt;
  - safely identify the existing stored record (by its id);
  - do **not** mutate the existing row;
  - the receipt reports no newly created record.

- **Conflicting replay** — same idempotency boundary, **different** fingerprint (or
  otherwise conflicting identity/payload):
  - **deny** the write (`reason_code = idempotency_conflict`);
  - do **not** create a new row;
  - leave the existing row unchanged;
  - do **not** treat it as a successful replay.

The two outcomes are reached both by the pre-insert lookup (the common case) and by the
post-insert `IntegrityError` re-query (the race case), using the same fingerprint comparison,
so behavior is identical whether or not a race occurred.

## Transaction and uncertain-outcome semantics

The insert and its read-back run in a controlled transaction. Distinguished outcomes:

- `created` — inserted and committed;
- `idempotent_replay` — equivalent row already present; no write;
- `denied` — governance/authorization/idempotency-conflict failure; no write;
- `failed_before_write` — infrastructure failure **before** any insert was attempted;
- `write_outcome_uncertain` — the commit outcome could not be confirmed.

`failed_before_write` is never reported after a commit may have occurred. On
`write_outcome_uncertain` the create/commit booleans are indeterminate and must be read
through the uncertain outcome; the receipt does not claim a record definitely does or does
not exist.

## Review-gate and side-effect invariants

Idempotency never changes the governance posture. A created row is always review-gated
(`output_status=draft`, `review_status=needs_review`), all server-controlled fields are
stamped by the writer, and the writer performs **no LLM**, **no AgentNet**, and **no capsule
publication** — see the side-effect boundary in
[`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md).
