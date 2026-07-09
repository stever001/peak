# Redacted Examples

Worked examples of **raw-ish engagement notes converted into safe, anonymized form**,
following [`../../docs/REDACTION_GUIDE.md`](../../docs/REDACTION_GUIDE.md) and
[`../../docs/DATA_HANDLING_POLICY.md`](../../docs/DATA_HANDLING_POLICY.md).

> **Everything here is fictional.** These files do not describe any real client,
> person, site, system, vendor, or price. They exist to show consultants what "already
> redacted" notes look like — the safe target state for anything entering the repo.

## Files

| File | Shows |
| --- | --- |
| `redacted-intake-notes.example.md` | Messy intake-call notes, redacted |
| `redacted-visual-observation-notes.example.md` | Walk-around observations, redacted |
| `redacted-interview-notes.example.md` | A stakeholder interview, redacted |

## How to read these

Each file is written the way notes should look **after** redaction: consistent aliases
(`client_alpha`, `operations_manager_alpha`, `site_alpha`, `vendor_alpha`), no named
products, ranges instead of exact figures, and `[REDACTED_PRICING]` in place of real
costs. The operational insight is preserved; the identifying detail is gone.

They line up with the fictional `client_alpha` engagement used elsewhere in
[`../`](../) (the `EngagementPacket` and sample outputs), so you can see how redacted
notes feed the structured objects.

## Reminder

Real, unredacted notes must **never** be committed. Redact first (outside the repo),
then bring the safe version in. See the redaction checklist in
[`../../docs/REDACTION_GUIDE.md`](../../docs/REDACTION_GUIDE.md).
