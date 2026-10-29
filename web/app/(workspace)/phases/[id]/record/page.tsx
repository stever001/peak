import Link from "next/link";
import type { ReactNode } from "react";

import { ObservationCard } from "@/components/discovery-section";
import { EvidenceThumb } from "@/components/linked-evidence";
import { PageHeader } from "@/components/page-header";
import { Pill, PhaseStatusPill, ReadinessPanel, RecordList } from "@/components/work-plan-parts";
import {
  apiGet, apiPublicUrl, getPhaseWorkRecord, requireConsultant, type EngagementPhaseDetail,
  type WorkOutcome, type WorkRecordTask,
} from "@/lib/api";
import { EVIDENCE_KIND_LABELS } from "@/lib/evidence";
import { formatDate } from "@/lib/labels";

const OUTCOME_LABELS: Record<WorkOutcome, string> = {
  completed: "Done",
  not_applicable: "Not applicable",
  does_not_apply: "Did not apply",
  open: "Not finished",
};

function Count({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="rounded-peak bg-canvas px-4 py-3">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="text-2xl font-semibold text-brand">{value}</dd>
      {note && <dd className="text-sm text-ink-muted">{note}</dd>}
    </div>
  );
}

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-line pt-4">
      <h3 className="mb-3 font-semibold">{title}</h3>
      {children}
    </div>
  );
}

/** What the task came to, in the consultant's own words. */
function Outcome({ t }: { t: WorkRecordTask }) {
  const who = (verb: string) => [t.completed_by && `${verb} by ${t.completed_by}`, formatDate(t.completed_at)]
    .filter(Boolean).join(" · ");
  if (t.outcome === "completed") {
    return (
      <div className="rounded-peak border-l-4 border-l-accent bg-canvas px-4 py-3">
        <p className="text-sm font-medium text-ink-muted">Result summary</p>
        <p className="mt-1 whitespace-pre-line">{t.result_summary}</p>
        <p className="mt-2 text-sm text-ink-muted">{who("Completed")}</p>
      </div>
    );
  }
  if (t.outcome === "not_applicable") {
    return (
      <div className="rounded-peak border-l-4 border-l-line bg-canvas px-4 py-3">
        <p className="text-sm font-medium text-ink-muted">Why it did not apply here</p>
        <p className="mt-1 whitespace-pre-line">{t.not_applicable_reason}</p>
        <p className="mt-2 text-sm text-ink-muted">{who("Resolved")}</p>
      </div>
    );
  }
  return (
    <p className="rounded-peak bg-canvas px-4 py-3 text-ink-muted">
      {t.outcome === "does_not_apply"
        ? "Its condition was not met, so this task did not apply."
        : "This task has not been finished yet."}
    </p>
  );
}

/**
 * Phase 223: the phase work record. Everything recorded during one phase in one place, composed by
 * the API on each request. Read-only: nothing on this page writes, and nothing in it is generated.
 */
export default async function PhaseRecordPage(props: PageProps<"/phases/[id]/record">) {
  await requireConsultant();
  const { id } = await props.params;
  const { phase: p } = await apiGet<{ phase: EngagementPhaseDetail }>(`/phases/${encodeURIComponent(id)}`);
  // Optional: null when the API cannot compose the record; the page then says so.
  const rec = await getPhaseWorkRecord(p.id);
  const apiUrl = apiPublicUrl();
  const back = (
    <Link href={`/phases/${p.id}`} className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
      ← {p.title}
    </Link>
  );

  if (!rec) {
    return (
      <>
        {back}
        <PageHeader title="Phase work record" intro={p.title} />
        <p className="peak-card text-ink-muted">The phase work record is currently unavailable here.</p>
      </>
    );
  }

  const ph = rec.phase;
  const a = ph.authorization;
  const n = rec.totals;
  const links = { ev: { engagement_id: rec.engagement.id, available: [], links: rec.evidence_links }, apiUrl };

  return (
    <>
      {back}
      <div className="mb-2"><PhaseStatusPill status={ph.status} /></div>
      <PageHeader title="Phase work record"
                  intro={[rec.engagement.client_name, rec.engagement.engagement_label, ph.title].filter(Boolean).join(" · ")} />

      <section className="peak-card mb-6 space-y-2">
        <p>
          What was recorded during this phase, gathered in one place: each agreed task&apos;s outcome, the
          records, photos and documents, and the observations written while doing it. Every word here was
          written by a consultant. Peak adds nothing and draws no conclusion from it.
        </p>
        <details className="text-sm text-ink-muted">
          <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">
            How this record is put together
          </summary>
          <p className="mt-1">{rec.composition.rule}</p>
        </details>
      </section>

      <section className="peak-card mb-6">
        <dl className="grid gap-5 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="text-sm text-ink-muted">Scope</dt>
            <dd className="mt-0.5 whitespace-pre-line">{ph.scope_summary}</dd>
          </div>
          {ph.roadmap_item && (
            <div>
              <dt className="text-sm text-ink-muted">From roadmap item</dt>
              <dd className="mt-0.5">{ph.roadmap_item.title}</dd>
            </div>
          )}
          <div className="sm:col-span-2">
            <dt className="text-sm text-ink-muted">What the client agreed to</dt>
            <dd className="mt-0.5 whitespace-pre-line">
              {a?.basis ?? <span className="text-ink-muted">Not authorized yet</span>}
            </dd>
            {a && (
              <dd className="mt-1 text-sm text-ink-muted">
                {[a.reference && `Reference: ${a.reference}`, a.authorized_by && `Recorded by ${a.authorized_by}`,
                  formatDate(a.authorized_at)].filter(Boolean).join(" · ")}
              </dd>
            )}
          </div>
          {ph.status === "completed" && (
            <div className="sm:col-span-2">
              <dt className="text-sm text-ink-muted">Phase work completed</dt>
              <dd className="mt-0.5">
                {[ph.completed_by && `By ${ph.completed_by}`, formatDate(ph.completed_at)].filter(Boolean).join(" · ")}
              </dd>
            </div>
          )}
        </dl>
      </section>

      {ph.status === "planned" && (
        <p role="status" className="peak-card mb-6 border-l-4 border-l-highlight">
          This phase is not authorized yet, so no work has been recorded during it.
        </p>
      )}

      <section aria-labelledby="totals" className="peak-card mb-6">
        <h2 id="totals" className="mb-4 text-lg font-semibold">At a glance</h2>
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Count label="Tasks done" value={n.completed} note={`of ${n.tasks} agreed`} />
          <Count label="Not applicable or did not apply" value={n.not_applicable + n.does_not_apply} />
          <Count label="Not finished" value={n.open} />
          <Count label="Records" value={n.records}
                 note={n.corrected_records ? `${n.corrected_records} earlier versions kept` : undefined} />
          <Count label="Photos and documents" value={n.captures}
                 note={n.replaced_captures ? `${n.replaced_captures} replaced versions kept` : undefined} />
          <Count label="Observations" value={n.observations} />
        </dl>
        {rec.suggested_not_accepted > 0 && (
          <p className="mt-4 text-sm text-ink-muted">
            {rec.suggested_not_accepted} suggested {rec.suggested_not_accepted === 1 ? "task was" : "tasks were"} not
            accepted into the work plan and {rec.suggested_not_accepted === 1 ? "is" : "are"} not part of this record.
          </p>
        )}
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
        <section aria-labelledby="by-task" className="space-y-4">
          <h2 id="by-task" className="text-xl font-semibold text-brand">Task by task</h2>
          {rec.tasks.length === 0 && (
            <p className="peak-card text-ink-muted">This phase has no agreed work plan tasks.</p>
          )}
          {rec.tasks.map((t) => (
            <article key={t.id} aria-labelledby={`task-${t.id}`} className="peak-card space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 id={`task-${t.id}`} className="text-lg font-semibold">
                  <Link href={`/phases/${p.id}/tasks/${t.id}`} className="inline-flex min-h-touch items-center text-brand">
                    Task {t.sequence}: {t.title}
                  </Link>
                </h3>
                <span className="flex flex-wrap gap-2">
                  <Pill>{t.required ? "Required" : "Optional"}</Pill>
                  <Pill tone={t.outcome === "completed" ? "bg-accent" : "bg-line"}>{OUTCOME_LABELS[t.outcome]}</Pill>
                  {t.added_after_authorization && <Pill tone="bg-highlight">Added after authorization</Pill>}
                </span>
              </div>
              <Outcome t={t} />

              <Part title="Records">
                {t.records.length === 0 ? <p className="text-ink-muted">No records.</p>
                  : <RecordList records={t.records} />}
              </Part>

              <Part title="Photos and documents">
                {t.captures.length === 0 ? <p className="text-ink-muted">None captured.</p> : (
                  <ul className="grid gap-3 sm:grid-cols-2">
                    {t.captures.map((e) => (
                      <li key={e.id} className="flex gap-3 rounded-peak border border-line p-2">
                        <EvidenceThumb e={e} apiUrl={apiUrl} />
                        <div className="min-w-0 flex-1">
                          {e.caption ? <p className="whitespace-pre-line">{e.caption}</p>
                            : <p className="text-ink-muted">No caption.</p>}
                          <p className="text-sm text-ink-muted">
                            {[EVIDENCE_KIND_LABELS[e.evidence_kind], e.uploaded_by, formatDate(e.created_at)].filter(Boolean).join(" · ")}
                          </p>
                          <a href={`${apiUrl}${e.content_path}`} target="_blank" rel="noreferrer noopener"
                             className="inline-flex min-h-touch items-center text-sm font-medium text-brand">
                            Open full size
                          </a>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                {t.replaced_captures > 0 && (
                  <p className="mt-2 text-sm text-ink-muted">
                    {t.replaced_captures} replaced {t.replaced_captures === 1 ? "version is" : "versions are"} kept on the task.
                  </p>
                )}
              </Part>

              <Part title="Observations">
                {t.observations.length === 0 ? <p className="text-ink-muted">None written during this task.</p> : (
                  <ul className="grid gap-3">
                    {t.observations.map((o) => <ObservationCard key={o.id} o={o} evidence={links} hereTask={t.id} />)}
                  </ul>
                )}
              </Part>
            </article>
          ))}
        </section>

        <aside className="space-y-4 xl:sticky xl:top-6">
          <ReadinessPanel phase={{ ...p, readiness: rec.readiness }} />
        </aside>
      </div>
    </>
  );
}
