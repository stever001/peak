"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { FormMessage } from "@/components/form-message";
import type { LeadReviewState } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

const secondary =
  "inline-flex min-h-touch items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand disabled:opacity-60";

const DECISION_LABELS = { approve_internal: "Approved for internal reliance", decline: "Declined" } as const;

/**
 * Phase 226: the Lead's review of this observation, exactly as worded, and what it makes it eligible
 * for. A review drafts no recommendation and changes nothing in the observation or the Final Report.
 */
export function ObservationLeadReview({ state, action }: { state: LeadReviewState; action: Action }) {
  const e = state.eligibility;
  const current = state.history[0];
  return (
    <section className="peak-card mb-6 space-y-4" aria-labelledby="lead-review-title">
      <div>
        <h2 id="lead-review-title" className="text-lg font-semibold">Lead review</h2>
        <p className="mt-1 text-sm text-ink-muted">
          The engagement’s Lead Consultant can approve this observation, exactly as it reads now, for internal
          reliance as an operational finding, and rate its reliability. An approval rated medium or high makes
          it eligible to support a recommendation. <span className="font-medium text-ink">It does not create a
          recommendation:</span> none is drafted from it, and the Final Report does not change. If the
          observation is edited afterwards, the approval no longer applies until the Lead reviews it again.
        </p>
      </div>

      {e && (
        <div>
          <p className="font-medium">
            Recommendation eligibility: {e.recommendation_eligible ? "eligible" : "not eligible"}
          </p>
          {e.recommendation_blocked_reasons.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-sm text-ink-muted">
              {e.recommendation_blocked_reasons.map((r) => <li key={r}>{r}</li>)}
            </ul>
          )}
          {e.recommendation_eligible && (
            <p className="mt-1 text-sm text-ink-muted">Eligible only. No recommendation exists for it.</p>
          )}
        </div>
      )}

      {state.history.length > 0 && (
        <ul className="space-y-1 text-sm">
          {state.history.map((h) => (
            <li key={h.review_id}>
              Review {h.review_number}: {DECISION_LABELS[h.decision]}
              {h.reliability ? `, reliability ${h.reliability}` : ""}, by {h.reviewer ?? "an unnamed consultant"}
              {h.review_id === current?.review_id ? " (current)" : ""}
              {!h.statement_matches ? " — for an earlier wording" : ""}
            </li>
          ))}
        </ul>
      )}

      {state.you_are_lead ? (
        <LeadReviewForm action={action} statementHash={state.statement_hash} currentReviewId={current?.review_id ?? ""} />
      ) : (
        <p className="text-sm text-ink-muted">
          {state.lead
            ? `Only the Lead Consultant, ${state.lead.name ?? "the assigned consultant"}, can review this observation.`
            : "No Lead Consultant is assigned to this engagement. An Admin assigns one on the engagement."}
        </p>
      )}
    </section>
  );
}

function LeadReviewForm({ action, statementHash, currentReviewId }: {
  action: Action; statementHash: string; currentReviewId: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-3">
      <input type="hidden" name="statement_hash" value={statementHash} />
      <input type="hidden" name="current_review_id" value={currentReviewId} />
      <fieldset>
        <legend className="peak-label">Reliability (needed to approve)</legend>
        <div className="flex flex-col gap-2 sm:flex-row sm:gap-6">
          {(["low", "medium", "high"] as const).map((r) => (
            <label key={r} className="inline-flex min-h-touch items-center gap-2">
              <input type="radio" name="reliability" value={r} /> {r[0].toUpperCase() + r.slice(1)}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button type="submit" name="decision" value="approve_internal" disabled={pending} className="peak-button">
          Approve for internal reliance
        </button>
        <button type="submit" name="decision" value="decline" disabled={pending} className={secondary}>
          Decline
        </button>
      </div>
      <FormMessage state={state} />
    </form>
  );
}
