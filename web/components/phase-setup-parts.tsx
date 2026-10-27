import Link from "next/link";

import { PhaseStatusPill, Pill } from "@/components/work-plan-parts";
import type { EngagementPhaseSummary, RoadmapStatus } from "@/lib/api";
import {
  phaseHref, ROADMAP_STATUS_LABELS, SETUP_STAGE_LABELS, setupStage, type SetupStep,
} from "@/lib/phase-setup";

export function RoadmapStatusPill({ status }: { status: RoadmapStatus }) {
  const tone = status === "accepted" ? "bg-accent" : status === "proposed" ? "bg-highlight" : "bg-line";
  return <Pill tone={tone}>{ROADMAP_STATUS_LABELS[status]}</Pill>;
}

/** One phase as a large tap target: its setup until setup is finished, then its work plan. */
export function PhaseSetupCard({ phase }: { phase: EngagementPhaseSummary }) {
  const stage = setupStage(phase);
  const ready = stage === "ready";
  return (
    <Link href={phaseHref(phase)}
          className={`flex min-h-20 flex-col gap-2 rounded-peak border bg-surface px-5 py-4 hover:border-brand ${ready ? "border-2 border-brand" : "border-line"}`}>
      <span className="flex flex-wrap items-start justify-between gap-2">
        <span className="min-w-0 break-words font-semibold text-brand">{phase.title}</span>
        <PhaseStatusPill status={phase.status} />
      </span>
      <span className="text-sm text-ink-muted">
        {SETUP_STAGE_LABELS[stage]}
        {phase.origin === "manual" ? " · created manually" : ""}
      </span>
      <span className="text-sm font-medium text-brand">
        {ready ? "Open work plan →" : stage === "completed" ? "View work plan →" : "Continue setup →"}
      </span>
    </Link>
  );
}

/** The fixed setup steps, each done or not from the phase's records. */
export function SetupChecklist({ steps }: { steps: SetupStep[] }) {
  return (
    <ol className="space-y-2" aria-label="Phase setup progress">
      {steps.map((s, i) => (
        <li key={s.key} className="flex min-h-touch items-center gap-3 rounded-peak bg-canvas px-4 py-2">
          <span aria-hidden="true"
                className={`flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${s.done ? "bg-brand text-on-brand" : "border border-line bg-surface text-ink-muted"}`}>
            {s.done ? "✓" : i + 1}
          </span>
          <span className={s.done ? "" : "text-ink-muted"}>
            {s.label}<span className="sr-only">{s.done ? " (done)" : " (not yet)"}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
