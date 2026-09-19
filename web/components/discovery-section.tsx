import Link from "next/link";

import { createObservation, saveNorthStar } from "@/app/discovery-actions";
import { NorthStarForm } from "@/components/north-star-form";
import { ObservationForm } from "@/components/observation-form";
import type { Discovery, Observation } from "@/lib/api";
import { formatDate, LEVEL_LABELS } from "@/lib/labels";

function Pill({ children, tone = "bg-line" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold text-ink ${tone}`}>{children}</span>;
}

function ObservationCard({ o }: { o: Observation }) {
  return (
    <li className="rounded-peak border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {o.low_hanging_fruit && <Pill tone="bg-highlight">Low-hanging fruit</Pill>}
        {o.estimated_value && <Pill>Value: {LEVEL_LABELS[o.estimated_value]}</Pill>}
        {o.estimated_effort && <Pill>Effort: {LEVEL_LABELS[o.estimated_effort]}</Pill>}
        {o.category && <span className="text-sm text-ink-muted">{o.category}</span>}
      </div>
      <p className="whitespace-pre-line">{o.observation_text}</p>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-ink-muted">
        <span>
          {[o.recorded_by, formatDate(o.created_at),
            o.session ? `from interview with ${o.session.interviewee_name}` : null].filter(Boolean).join(" · ")}
        </span>
        <Link href={`/observations/${o.id}/edit`} className="inline-flex min-h-touch items-center font-medium text-brand">
          Edit
        </Link>
      </div>
    </li>
  );
}

/** Engagement Discovery: North Star, interviews, low-hanging fruit and observations. */
export function DiscoverySection({ engagementId, d }: { engagementId: string; d: Discovery }) {
  if (!d.discovery_enabled) {
    return (
      <section id="discovery" className="peak-card mt-6 text-ink-muted">
        Discovery is available for engagements created in the consultant workspace.
      </section>
    );
  }
  const lhf = d.observations.filter((o) => o.low_hanging_fruit);
  return (
    <section id="discovery" className="mt-8 space-y-6">
      <h2 className="text-xl font-semibold text-brand">Discovery</h2>

      <div className="peak-card">
        <h3 className="text-lg font-semibold">North Star</h3>
        {d.north_star ? (
          <>
            <p className="mt-2 text-lg">{d.north_star}</p>
            {d.north_star_context && <p className="mt-1 whitespace-pre-line text-ink-muted">{d.north_star_context}</p>}
          </>
        ) : <p className="mt-2 text-ink-muted">Not set yet. What outcome is this discovery effort aiming at?</p>}
        <details className="mt-3">
          <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">
            {d.north_star ? "Edit North Star" : "Set North Star"}
          </summary>
          <NorthStarForm action={saveNorthStar.bind(null, engagementId)}
                         northStar={d.north_star} context={d.north_star_context} />
        </details>
      </div>

      <div className="peak-card">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="text-lg font-semibold">Interviews</h3>
          <Link href={`/engagements/${engagementId}/interviews/new`} className="peak-button">Start interview</Link>
        </div>
        {d.sessions.length === 0 ? <p className="text-ink-muted">No interviews yet.</p> : (
          <ul className="grid gap-3 lg:grid-cols-2">
            {d.sessions.map((s) => (
              <li key={s.id}>
                <Link href={`/interviews/${s.id}`}
                      className="flex min-h-20 flex-col gap-1 rounded-peak border border-line bg-surface px-5 py-4 hover:border-brand">
                  <span className="flex items-start justify-between gap-3">
                    <span className="font-semibold text-brand">{s.interviewee_name}</span>
                    <Pill tone={s.status === "completed" ? "bg-line" : "bg-accent"}>
                      {s.status === "completed" ? "Completed" : "In progress — resume"}
                    </Pill>
                  </span>
                  <span className="text-sm text-ink-muted">
                    {[s.interviewee_title, `${s.answered_count} answered`, s.conducted_by,
                      formatDate(s.started_at)].filter(Boolean).join(" · ")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="peak-card">
        <h3 className="mb-4 text-lg font-semibold">Low-hanging fruit ({lhf.length})</h3>
        {lhf.length === 0 ? (
          <p className="text-ink-muted">Flag an observation as low-hanging fruit to list it here.</p>
        ) : <ul className="grid gap-3 lg:grid-cols-2">{lhf.map((o) => <ObservationCard key={o.id} o={o} />)}</ul>}
      </div>

      <div className="peak-card">
        <h3 className="mb-4 text-lg font-semibold">Observations ({d.observations.length})</h3>
        <details className="mb-5 rounded-peak border border-line p-4" open={d.observations.length === 0}>
          <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">
            Add observation
          </summary>
          <div className="mt-3">
            <ObservationForm action={createObservation.bind(null, engagementId)} sessions={d.sessions}
                             submitLabel="Record observation" />
          </div>
        </details>
        {d.observations.length > 0 && (
          <ul className="grid gap-3 lg:grid-cols-2">{d.observations.map((o) => <ObservationCard key={o.id} o={o} />)}</ul>
        )}
      </div>
    </section>
  );
}
