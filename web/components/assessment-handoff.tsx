import Link from "next/link";

import type { AssessmentHandoff } from "@/lib/api";

function countText(h: AssessmentHandoff): string {
  if (h.observations === 0) {
    return "No observation has been written from this phase's work, so nothing from it is in the internal assessment yet.";
  }
  return h.observations === 1
    ? "1 observation from this phase's work is in the internal assessment."
    : `${h.observations} observations from this phase's work are in the internal assessment.`;
}

/**
 * Phase 224: what reaches the assessment from this phase, on the phase workspace. Read-only and
 * derived: it blocks nothing and is not a state. The full list is on the work record.
 */
export function AssessmentHandoffNote({ phaseId, h }: { phaseId: string; h: AssessmentHandoff }) {
  return (
    <div className="peak-card">
      <h2 className="font-semibold">What reaches the assessment</h2>
      <p className="mt-1 text-sm text-ink-muted">
        {countText(h)} Observations can still be written after this phase is completed.
      </p>
      <Link href={`/phases/${phaseId}/record#assessment-handoff`}
            className="mt-1 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        Review in the phase work record
      </Link>
    </div>
  );
}

/** Phase 224: the same on the work record, with the tasks that have no observation. Links only. */
export function AssessmentHandoffSection({ phaseId, engagementId, h }: {
  phaseId: string; engagementId: string; h: AssessmentHandoff;
}) {
  return (
    <section id="assessment-handoff" aria-labelledby="assessment-handoff-title" className="peak-card mb-6 space-y-3">
      <h2 id="assessment-handoff-title" className="text-lg font-semibold">What reaches the assessment</h2>
      <p>{countText(h)}</p>
      <p className="text-sm text-ink-muted">{h.rule}</p>
      {h.without_observation.length > 0 && (
        <div>
          <h3 className="font-semibold">Recorded work with no observation</h3>
          <p className="mt-1 text-sm text-ink-muted">
            Nothing from these tasks is in the assessment. Whether any of it should be is your call.
          </p>
          <ul className="mt-2 divide-y divide-line">
            {h.without_observation.map((t) => (
              <li key={t.task_id} className="flex flex-wrap items-center justify-between gap-x-3 py-1">
                <span>Task {t.sequence}: {t.title}</span>
                <Link href={`/phases/${phaseId}/tasks/${t.task_id}?observe=1#observations`}
                      className="inline-flex min-h-touch items-center text-sm font-medium text-brand">
                  Write an observation
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <Link href={`/engagements/${engagementId}/assessment`}
            className="inline-flex min-h-touch items-center font-medium text-brand">
        Open the internal assessment →
      </Link>
    </section>
  );
}
