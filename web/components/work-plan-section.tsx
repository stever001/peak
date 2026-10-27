import Link from "next/link";

import { PhaseSetupCard } from "@/components/phase-setup-parts";
import type { EngagementPhaseSummary, Roadmap } from "@/lib/api";

/**
 * Phase 218/219: the engagement's phases, each opening its setup until setup is finished and its
 * guided work plan after, with the way into the roadmap and phase setup.
 */
export function WorkPlanSection({ engagementId, phases, roadmap }: {
  engagementId: string; phases: EngagementPhaseSummary[]; roadmap: Roadmap;
}) {
  const accepted = roadmap.items.filter((i) => i.status === "accepted" && !i.phase_id).length;
  const proposed = roadmap.items.filter((i) => i.status === "proposed").length;
  const summary = [
    roadmap.suggestions.length && `${roadmap.suggestions.length} suggested by Peak`,
    proposed && `${proposed} proposed`,
    accepted && `${accepted} accepted, awaiting a phase`,
  ].filter(Boolean).join(" · ");
  return (
    <section id="work-plans" className="mt-8 space-y-4">
      <h2 className="text-xl font-semibold text-brand">Engagement phases and work plans</h2>
      {roadmap.enabled && (
        <Link href={`/engagements/${engagementId}/roadmap`}
              className="flex min-h-touch items-center justify-between gap-3 rounded-peak border border-line bg-surface px-5 py-4 hover:border-brand">
          <span className="min-w-0">
            <span className="block font-semibold text-brand">Roadmap and phase setup</span>
            <span className="block text-sm text-ink-muted">
              {summary || "Propose follow-on work and prepare its engagement phase."}
            </span>
          </span>
          <span aria-hidden="true" className="text-brand">→</span>
        </Link>
      )}
      {phases.length === 0 ? (
        <p className="peak-card text-ink-muted">
          No engagement phases yet. A phase is a separately authorized piece of follow-on work; create one from an
          accepted roadmap item, and its guided work plan opens here once it is set up.
        </p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {phases.map((p) => <li key={p.id}><PhaseSetupCard phase={p} /></li>)}
        </ul>
      )}
    </section>
  );
}
