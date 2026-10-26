import Link from "next/link";

import { completePhase } from "@/app/work-plan-actions";
import { ActionButton } from "@/components/work-plan-actions";
import { PhaseStatusPill, ReadinessPanel, TaskCard } from "@/components/work-plan-parts";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type EngagementPhaseDetail } from "@/lib/api";
import { formatDate } from "@/lib/labels";
import { nextTask } from "@/lib/work-plan";

/** Phase 218: the phase workspace. What to do next, what is blocked, done or optional. */
export default async function PhasePage(props: PageProps<"/phases/[id]">) {
  await requireConsultant();
  const { id } = await props.params;
  const { phase: p } = await apiGet<{ phase: EngagementPhaseDetail }>(`/phases/${encodeURIComponent(id)}`);
  const plan = p.tasks.filter((t) => t.status !== "suggested");
  const suggested = p.tasks.filter((t) => t.status === "suggested");
  const next = p.status === "authorized" ? nextTask(plan) : null;
  const a = p.authorization;

  return (
    <>
      <Link href={`/engagements/${p.engagement_id}#work-plans`}
            className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← Engagement
      </Link>
      <div className="mb-2"><PhaseStatusPill status={p.status} /></div>
      <PageHeader title={p.title} intro={p.scope_summary} />

      <section className="peak-card mb-6">
        <dl className="grid gap-5 sm:grid-cols-2">
          {p.roadmap_item && (
            <div>
              <dt className="text-sm text-ink-muted">From roadmap item</dt>
              <dd className="mt-0.5">{p.roadmap_item.title}</dd>
            </div>
          )}
          {p.origin === "manual" && p.origin_note && (
            <div>
              <dt className="text-sm text-ink-muted">Why this phase exists</dt>
              <dd className="mt-0.5 whitespace-pre-line">{p.origin_note}</dd>
            </div>
          )}
          <div className="sm:col-span-2">
            <dt className="text-sm text-ink-muted">What the client agreed to</dt>
            <dd className="mt-0.5 whitespace-pre-line">
              {a?.basis ?? <span className="text-ink-muted">Not authorized yet</span>}
            </dd>
            {a && (
              <p className="mt-1 text-sm text-ink-muted">
                {[a.reference && `Reference: ${a.reference}`, a.authorized_by && `Recorded by ${a.authorized_by}`,
                  formatDate(a.authorized_at)].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
        </dl>
      </section>

      {p.status === "planned" && (
        <p role="status" className="peak-card mb-6 border-l-4 border-l-highlight">
          This phase is planned but not authorized. Work cannot be recorded until the engagement Lead or an
          Admin records what the client agreed to. You can read the work plan below to prepare.
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
        <section aria-labelledby="work-plan" className="space-y-4">
          <h2 id="work-plan" className="text-xl font-semibold text-brand">Work plan</h2>
          {next && (
            <Link href={`/phases/${p.id}/tasks/${next.id}`}
                  className="flex min-h-touch items-center justify-between gap-3 rounded-peak bg-brand px-5 py-4 text-on-brand hover:bg-brand-strong">
              <span><span className="block text-sm opacity-80">Next up</span>
                <span className="font-semibold">Task {next.sequence}: {next.title}</span></span>
              <span aria-hidden="true">→</span>
            </Link>
          )}
          {plan.length === 0 ? (
            <p className="peak-card text-ink-muted">
              This phase has no work plan tasks yet, so there is nothing to do here yet.
            </p>
          ) : (
            <ol className="space-y-3">
              {plan.map((t) => <TaskCard key={t.id} task={t} phaseId={p.id} isNext={t.id === next?.id} />)}
            </ol>
          )}
          {suggested.length > 0 && (
            <>
              <h3 className="pt-2 text-lg font-semibold">Suggested tasks</h3>
              <p className="text-sm text-ink-muted">
                Not part of the agreed work until you accept them. Open one to review it.
              </p>
              <ul className="space-y-3">
                {suggested.map((t) => <TaskCard key={t.id} task={t} phaseId={p.id} isNext={false} />)}
              </ul>
            </>
          )}
        </section>

        <aside className="space-y-4 xl:sticky xl:top-6">
          <ReadinessPanel phase={p} />
          {p.status === "authorized" && p.readiness.ready && (
            <div className="peak-card">
              <p className="mb-3 text-sm text-ink-muted">
                All required work is resolved. Marking the phase complete closes its work plan.
              </p>
              <ActionButton action={completePhase.bind(null, p.id)} label="Mark phase work complete"
                            pendingLabel="Completing…" />
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
