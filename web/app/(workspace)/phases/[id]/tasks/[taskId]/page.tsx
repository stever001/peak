import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import {
  acceptSuggestedTask, completeTask, recordTaskWork, resolveTaskNotApplicable,
} from "@/app/work-plan-actions";
import { ActionButton, CompleteTaskForm, NotApplicableForm } from "@/components/work-plan-actions";
import { Pill, RecordList, TaskStatusPill } from "@/components/work-plan-parts";
import { RecordForm } from "@/components/work-plan-record-form";
import { apiGet, requireConsultant, type EngagementPhaseDetail } from "@/lib/api";
import { formatDate } from "@/lib/labels";
import {
  conditionText, isOpen, MEDIA_KINDS, nextTask, RECORD_KIND_LABELS, splitRecords,
} from "@/lib/work-plan";

function Guide({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold tracking-wide text-ink-muted uppercase">{title}</h3>
      <div className="mt-1 text-base">{children}</div>
    </div>
  );
}

/** Phase 218: one task, guidance first, then what the consultant actually recorded and the actions. */
export default async function TaskPage(props: PageProps<"/phases/[id]/tasks/[taskId]">) {
  await requireConsultant();
  const { id, taskId } = await props.params;
  const search = await props.searchParams;
  const { phase: p } = await apiGet<{ phase: EngagementPhaseDetail }>(`/phases/${encodeURIComponent(id)}`);
  const t = p.tasks.find((x) => x.id === taskId);
  if (!t) notFound();

  const plan = p.tasks.filter((x) => x.status !== "suggested");
  const w = t.work_state;
  const authorized = p.status === "authorized";
  const workable = authorized && isOpen(t);
  const here = `/phases/${p.id}/tasks/${t.id}`;
  const { current } = splitRecords(t.records);
  const correcting = typeof search.correct === "string" && workable
    ? current.find((r) => r.id === search.correct) : undefined;
  const next = authorized ? nextTask(plan.filter((x) => x.id !== t.id)) : null;
  const capturable = t.suggested_evidence.filter((k) => !MEDIA_KINDS.includes(k));
  const deferred = t.suggested_evidence.filter((k) => MEDIA_KINDS.includes(k));
  const condition = conditionText(t);

  return (
    <>
      <Link href={`/phases/${p.id}`} className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← {p.title}
      </Link>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-ink-muted">
          {t.status === "suggested" ? "Suggested task" : `Task ${t.sequence} of ${plan.length}`}
        </span>
        <Pill>{t.required ? "Required" : "Optional"}</Pill>
        <TaskStatusPill status={t.status} />
        {t.added_after_authorization && <Pill tone="bg-highlight">Added after authorization</Pill>}
      </div>
      <h1 className="mb-6 text-2xl font-semibold text-brand md:text-3xl">{t.title}</h1>

      {/* What remains: decided by the API, shown as given. */}
      {t.status === "suggested" ? (
        <section className="peak-card mb-6 border-l-4 border-l-highlight">
          <h2 className="font-semibold">Suggested, not yet part of the agreed work</h2>
          <p className="mt-1 text-ink-muted">
            Review the guidance below. Accept it to add it to the work plan, or leave it as a suggestion.
          </p>
          {p.status !== "completed" && (
            <div className="mt-4">
              <ActionButton action={acceptSuggestedTask.bind(null, p.id, t.id)}
                            label="Accept into the work plan" pendingLabel="Accepting…" />
            </div>
          )}
        </section>
      ) : t.status === "completed" ? (
        <section className="peak-card mb-6 border-l-4 border-l-accent">
          <h2 className="font-semibold">Done</h2>
          <p className="mt-1 whitespace-pre-line">{t.result_summary}</p>
          <p className="mt-2 text-sm text-ink-muted">
            {[t.completed_by && `Completed by ${t.completed_by}`, formatDate(t.completed_at)].filter(Boolean).join(" · ")}
          </p>
        </section>
      ) : t.status === "not_applicable" ? (
        <section className="peak-card mb-6 border-l-4 border-l-line">
          <h2 className="font-semibold">Not applicable</h2>
          <p className="mt-1 whitespace-pre-line">{t.not_applicable_reason}</p>
          <p className="mt-2 text-sm text-ink-muted">
            {[t.completed_by && `Resolved by ${t.completed_by}`, formatDate(t.completed_at)].filter(Boolean).join(" · ")}
          </p>
        </section>
      ) : !authorized ? (
        <section className="peak-card mb-6 border-l-4 border-l-highlight">
          <h2 className="font-semibold">
            {p.status === "planned" ? "This phase is not authorized yet" : "This phase is completed"}
          </h2>
          <p className="mt-1 text-ink-muted">
            {p.status === "planned"
              ? "You can read the guidance to prepare. Recording and completing open once the client's agreement is recorded."
              : "Its work plan is closed."}
          </p>
        </section>
      ) : (
        <section className={`peak-card mb-6 border-l-4 ${w.completion_blockers.length ? "border-l-attention" : "border-l-accent"}`}>
          <h2 className="font-semibold">
            {w.applies === false ? "This task does not apply"
              : w.completion_blockers.length ? "Before you can complete this task" : "Ready to complete"}
          </h2>
          {w.applies === false ? (
            <p className="mt-1 text-ink-muted">Its condition was not met, so it does not hold the phase back.</p>
          ) : w.completion_blockers.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {w.completion_blockers.map((b) => <li key={b.code}>{b.message}</li>)}
            </ul>
          ) : (
            <p className="mt-1 text-ink-muted">Write your result summary below when the work is done.</p>
          )}
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
        {/* Guidance: Peak Method instructions. Never a record of what was found. */}
        <section aria-labelledby="guidance" className="rounded-peak border border-line bg-canvas p-5 md:p-6">
          <h2 id="guidance" className="mb-4 text-lg font-semibold">Guidance · what to do</h2>
          <div className="space-y-5">
            <Guide title="What to do"><p className="whitespace-pre-line">{t.instructions}</p></Guide>
            {t.what_to_observe && <Guide title="What to look for"><p className="whitespace-pre-line">{t.what_to_observe}</p></Guide>}
            {t.follow_up_questions.length > 0 && (
              <Guide title="Questions to ask">
                <ul className="list-disc space-y-1 pl-5">{t.follow_up_questions.map((q) => <li key={q}>{q}</li>)}</ul>
              </Guide>
            )}
            {t.suggested_evidence.length > 0 && (
              <Guide title="Useful records">
                <ul className="flex flex-wrap gap-2">
                  {capturable.map((k) => <li key={k}><Pill>{RECORD_KIND_LABELS[k]}</Pill></li>)}
                  {deferred.map((k) => <li key={k}><Pill tone="bg-surface border border-line">{RECORD_KIND_LABELS[k]}</Pill></li>)}
                </ul>
                {deferred.length > 0 && (
                  <p className="mt-2 text-sm text-ink-muted">
                    Photo and document capture is not available yet. Record a note describing the item and where it is kept.
                  </p>
                )}
              </Guide>
            )}
            {t.expected_result && <Guide title="Expected result"><p className="whitespace-pre-line">{t.expected_result}</p></Guide>}
            {t.why_it_matters && <Guide title="Why it matters"><p className="whitespace-pre-line">{t.why_it_matters}</p></Guide>}
            {w.prerequisites.length > 0 && (
              <Guide title="Do these first">
                <ul className="space-y-1">
                  {w.prerequisites.map((d) => (
                    <li key={d.task_id}>
                      <Link href={`/phases/${p.id}/tasks/${d.task_id}`} className="inline-flex min-h-touch items-center font-medium text-brand">
                        {d.resolved ? "✓" : "○"} Task {d.sequence}: {d.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </Guide>
            )}
            {condition && <Guide title="When this task applies"><p>{condition}</p></Guide>}
            {t.requires_record && (
              <p className="text-sm text-ink-muted">This task needs at least one record before it can be completed.</p>
            )}
            {t.inclusion_reason && (
              <details className="text-sm text-ink-muted">
                <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">
                  Why this task is in the plan
                </summary>
                <p className="mt-1">{t.inclusion_reason}</p>
              </details>
            )}
          </div>
        </section>

        {/* What the consultant actually recorded. */}
        <div className="space-y-6">
          <section id="records" aria-labelledby="your-records" className="peak-card">
            <h2 id="your-records" className="mb-4 text-lg font-semibold">Your records</h2>
            {t.records.length === 0 ? (
              <p className="mb-4 text-ink-muted">Nothing recorded for this task yet.</p>
            ) : (
              <div className="mb-6">
                <RecordList records={t.records}
                            correctHref={workable ? (r) => `${here}?correct=${r.id}#record-form` : undefined} />
              </div>
            )}
            {workable && w.applies !== false && (
              <div id="record-form" className="border-t border-line pt-5">
                <h3 className="mb-3 font-semibold">{correcting ? "Correct a record" : "Record what you found"}</h3>
                <RecordForm key={correcting?.id ?? "new"} action={recordTaskWork.bind(null, p.id, t.id)}
                            correcting={correcting} cancelHref={correcting ? `${here}#records` : undefined} />
              </div>
            )}
          </section>

          {workable && w.applies !== false && (
            <section aria-labelledby="finish" className="peak-card">
              <h2 id="finish" className="mb-4 text-lg font-semibold">Finish this task</h2>
              <CompleteTaskForm action={completeTask.bind(null, p.id, t.id)} expected={t.expected_result} />
            </section>
          )}
          {workable && (
            <details className="peak-card">
              <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">
                This task does not apply here
              </summary>
              <div className="mt-3"><NotApplicableForm action={resolveTaskNotApplicable.bind(null, p.id, t.id)} /></div>
            </details>
          )}
        </div>
      </div>

      {next && (
        <Link href={`/phases/${p.id}/tasks/${next.id}`}
              className="mt-8 flex min-h-touch items-center justify-between gap-3 rounded-peak border border-brand bg-surface px-5 py-4 hover:bg-canvas">
          <span><span className="block text-sm text-ink-muted">Next task</span>
            <span className="font-semibold text-brand">Task {next.sequence}: {next.title}</span></span>
          <span aria-hidden="true" className="text-brand">→</span>
        </Link>
      )}
    </>
  );
}
