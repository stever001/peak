import Link from "next/link";

import { PhaseStatusPill } from "@/components/work-plan-parts";
import type { EngagementPhaseSummary } from "@/lib/api";

const WORK_PLAN_LABELS: Record<EngagementPhaseSummary["work_plan_status"], string> = {
  not_started: "No work plan tasks yet",
  draft: "Work plan ready to read",
  active: "Work in progress",
  closed: "Work plan closed",
};

/** Phase 218: the engagement's phases, each opening its guided work plan. */
export function WorkPlanSection({ phases }: { phases: EngagementPhaseSummary[] }) {
  return (
    <section id="work-plans" className="mt-8 space-y-4">
      <h2 className="text-xl font-semibold text-brand">Engagement phases and work plans</h2>
      {phases.length === 0 ? (
        <p className="peak-card text-ink-muted">
          No engagement phases yet. A phase is a separately agreed piece of follow-on work; once one exists,
          its guided work plan opens here.
        </p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {phases.map((p) => (
            <li key={p.id}>
              <Link href={`/phases/${p.id}`}
                    className="flex min-h-20 flex-col gap-2 rounded-peak border border-line bg-surface px-5 py-4 hover:border-brand">
                <span className="flex flex-wrap items-start justify-between gap-2">
                  <span className="font-semibold text-brand">{p.title}</span>
                  <PhaseStatusPill status={p.status} />
                </span>
                <span className="text-sm text-ink-muted">{WORK_PLAN_LABELS[p.work_plan_status]}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
