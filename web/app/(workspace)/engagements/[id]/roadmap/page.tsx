import Link from "next/link";

import {
  addSuggestionToRoadmap, createManualPhase, createPhaseFromRoadmapItem, createRoadmapItem,
  decideRoadmapItem, reviseRoadmapItem,
} from "@/app/phase-setup-actions";
import { PageHeader } from "@/components/page-header";
import {
  CreatePhaseForm, ManualPhaseForm, RoadmapDecisionForm, RoadmapItemForm,
} from "@/components/phase-setup-forms";
import { PhaseSetupCard, RoadmapStatusPill } from "@/components/phase-setup-parts";
import { ActionButton } from "@/components/work-plan-actions";
import { Pill } from "@/components/work-plan-parts";
import {
  apiGet, requireConsultant, type Discovery, type Engagement, type EngagementPhaseSummary,
  type Observation, type PhaseTemplate, type Roadmap, type RoadmapItem,
} from "@/lib/api";
import { formatDate } from "@/lib/labels";
import { phaseHref, ROADMAP_ORIGIN_LABELS } from "@/lib/phase-setup";

const DETAILS = "rounded-peak border border-line p-4";
const SUMMARY = "inline-flex min-h-touch cursor-pointer items-center font-medium text-brand";

function Framing({ problem, rationale, outcome }: { problem: string; rationale: string; outcome: string }) {
  return (
    <dl className="space-y-3">
      {[["Operational issue or opportunity", problem], ["Why it matters", rationale], ["Expected outcome", outcome]]
        .map(([label, value]) => (
          <div key={label}>
            <dt className="text-sm text-ink-muted">{label}</dt>
            <dd className="mt-0.5 whitespace-pre-line break-words">{value}</dd>
          </div>
        ))}
    </dl>
  );
}

/** The consultant observations a roadmap item or suggestion rests on, by their own words. */
function Grounding({ ids, byId, summary }: { ids: string[]; byId: Map<string, Observation>; summary: string }) {
  const shown = ids.map((id) => byId.get(id)).filter((o): o is Observation => !!o);
  if (!shown.length) return null;
  return (
    <details className="mt-3 text-sm">
      <summary className={SUMMARY}>{summary}</summary>
      <ul className="mt-2 space-y-2">
        {shown.map((o) => (
          <li key={o.id} className="rounded-peak bg-canvas px-4 py-3">
            <span className="whitespace-pre-line break-words">{o.observation_text}</span>
            <span className="mt-1 block text-ink-muted">
              {[o.recorded_by, formatDate(o.created_at)].filter(Boolean).join(" · ")}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function ItemCard({ item, engagementId, phase, byId, scope = "" }: {
  item: RoadmapItem; engagementId: string; phase?: EngagementPhaseSummary; byId: Map<string, Observation>;
  /** The scope the phase will start with: the template's scope, else the expected outcome. */
  scope?: string;
}) {
  const muted = item.status === "declined" || item.status === "superseded";
  const n = item.source_observation_ids.length;
  return (
    <li className={`peak-card space-y-4 ${muted ? "bg-canvas" : ""}`}>
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <RoadmapStatusPill status={item.status} />
          {item.supersedes_item_id && <Pill>Revised</Pill>}
        </div>
        <h3 className="break-words text-lg font-semibold text-brand">{item.title}</h3>
        <p className="mt-1 text-sm text-ink-muted">{ROADMAP_ORIGIN_LABELS[item.origin]}</p>
      </div>
      <Framing problem={item.problem_framing} rationale={item.rationale} outcome={item.expected_outcome} />
      <Grounding ids={item.source_observation_ids} byId={byId}
                 summary={`Rests on ${n} discovery observation${n === 1 ? "" : "s"}`} />
      {(item.decided_at || item.status_note) && (
        <p className="text-sm text-ink-muted">
          {[item.status_note && `Note: ${item.status_note}`,
            item.decided_by && `Decided by ${item.decided_by}`, formatDate(item.decided_at)].filter(Boolean).join(" · ")}
        </p>
      )}

      {phase ? (
        <Link href={phaseHref(phase)}
              className="flex min-h-touch items-center justify-between gap-3 rounded-peak border border-brand px-4 py-3 font-medium text-brand">
          <span>Phase created: {phase.title}</span><span aria-hidden="true">→</span>
        </Link>
      ) : item.status === "accepted" ? (
        <div className="space-y-4 rounded-peak border-2 border-brand p-4">
          <h4 className="font-semibold">Create the engagement phase for this work</h4>
          <CreatePhaseForm action={createPhaseFromRoadmapItem.bind(null, engagementId, item.id)} itemId={item.id}
                           defaultTitle={item.title} defaultScope={scope} />
          {item.decisions.length > 0 && (
            <details className={DETAILS}>
              <summary className={SUMMARY}>Change the decision instead</summary>
              <div className="mt-3">
                <RoadmapDecisionForm action={decideRoadmapItem.bind(null, engagementId, item.id)}
                                     decisions={item.decisions} itemId={item.id} />
              </div>
            </details>
          )}
        </div>
      ) : item.decisions.length > 0 ? (
        <RoadmapDecisionForm action={decideRoadmapItem.bind(null, engagementId, item.id)}
                             decisions={item.decisions} itemId={item.id} />
      ) : item.status === "declined" ? (
        <p className="text-sm text-ink-muted">Declined. Kept on the roadmap for the record.</p>
      ) : null}

      {item.revisable && (
        <details className={DETAILS}>
          <summary className={SUMMARY}>Revise the wording</summary>
          <p className="mt-2 text-sm text-ink-muted">
            A revision becomes a new proposed item; this version is kept as an earlier version.
          </p>
          <div className="mt-3">
            <RoadmapItemForm action={reviseRoadmapItem.bind(null, engagementId, item.id)} item={item}
                             submitLabel="Save revision" />
          </div>
        </details>
      )}
    </li>
  );
}

/** Phase 219: proposed work, decisions, and creating the engagement phase that work becomes. */
export default async function RoadmapPage(props: PageProps<"/engagements/[id]/roadmap">) {
  await requireConsultant();
  const { id } = await props.params;
  const eid = encodeURIComponent(id);
  const [{ engagement: e }, { roadmap }, { phases }, { discovery }, { templates }] = await Promise.all([
    apiGet<{ engagement: Engagement }>(`/engagements/${eid}`),
    apiGet<{ roadmap: Roadmap }>(`/engagements/${eid}/roadmap`),
    apiGet<{ phases: EngagementPhaseSummary[] }>(`/engagements/${eid}/phases`),
    apiGet<{ discovery: Discovery }>(`/engagements/${eid}/discovery`),
    apiGet<{ templates: PhaseTemplate[] }>("/phase-templates"),
  ]);
  const templateScope = new Map(templates.map((t) => [t.template_key, t.scope_summary]));
  const byId = new Map(discovery.observations.map((o) => [o.id, o]));
  const phaseById = new Map(phases.map((p) => [p.id, p]));
  const empty = roadmap.items.length === 0 && roadmap.suggestions.length === 0;

  return (
    <>
      <Link href={`/engagements/${e.id}#work-plans`} className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← {e.engagement_label ?? "Engagement"}
      </Link>
      <PageHeader title="Roadmap and phase setup"
                  intro="Decide which proposed work is worth doing, turn accepted work into an engagement phase, record the client's authorization, and load the work plan." />

      {!roadmap.enabled ? (
        <p className="peak-card text-ink-muted">
          Roadmap and phase setup are available for engagements created in the consultant workspace.
        </p>
      ) : (
        <div className="space-y-8">
          <ol className="peak-card grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-5" aria-label="How phase setup works">
            {["Propose work worth doing", "Accept it with the client", "Create the engagement phase",
              "Load the work plan and record authorization", "Open the work plan"].map((s, i) => (
              <li key={s} className="flex items-center gap-2">
                <span aria-hidden="true" className="flex size-7 shrink-0 items-center justify-center rounded-full bg-canvas font-semibold text-brand">{i + 1}</span>
                {s}
              </li>
            ))}
          </ol>

          <section aria-labelledby="suggested" className="space-y-3">
            <h2 id="suggested" className="text-xl font-semibold text-brand">Suggested by Peak</h2>
            <p className="text-sm text-ink-muted">
              Worked out from your discovery observations each time this page opens. A suggestion is not saved and is
              not on the roadmap until you add it.
            </p>
            {roadmap.suggestions.length === 0 ? (
              <p className="peak-card text-ink-muted">
                {discovery.observations.length === 0
                  ? "No suggestions yet. Peak suggests work once discovery observations are recorded."
                  : "No further suggestions from the observations recorded so far."}
              </p>
            ) : (
              <ul className="space-y-3">
                {roadmap.suggestions.map((s) => (
                  <li key={s.template_key} className="space-y-4 rounded-peak border-2 border-dashed border-line bg-surface p-5 md:p-6">
                    <div>
                      <div className="mb-2"><Pill tone="bg-highlight">Suggested by Peak · not saved</Pill></div>
                      <h3 className="break-words text-lg font-semibold text-brand">{s.title}</h3>
                    </div>
                    <Framing problem={s.problem_framing} rationale={s.rationale} outcome={s.expected_outcome} />
                    <Grounding ids={s.source_observation_ids} byId={byId} summary={`Based on ${s.grounding.replace(/\.$/, "")}`} />
                    <ActionButton action={addSuggestionToRoadmap.bind(null, e.id, s.template_key)}
                                  label="Add to roadmap" pendingLabel="Adding…" />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="roadmap" className="space-y-3">
            <h2 id="roadmap" className="text-xl font-semibold text-brand">On the roadmap</h2>
            <p className="text-sm text-ink-muted">
              Proposed work saved for this engagement. Accepting an item records that the client wants it; it does not
              authorize any work.
            </p>
            {roadmap.items.length === 0 ? (
              <p className="peak-card text-ink-muted">Nothing on the roadmap yet. Add a suggestion or your own proposed work.</p>
            ) : (
              <ul className="space-y-4">
                {roadmap.items.map((item) => (
                  <ItemCard key={item.id} item={item} engagementId={e.id} byId={byId}
                            scope={(item.template_key && templateScope.get(item.template_key)) || item.expected_outcome}
                            phase={item.phase_id ? phaseById.get(item.phase_id) : undefined} />
                ))}
              </ul>
            )}
            {roadmap.superseded.length > 0 && (
              <details className={DETAILS}>
                <summary className={SUMMARY}>Earlier versions ({roadmap.superseded.length}) · replaced by a revision</summary>
                <ul className="mt-3 space-y-3">
                  {roadmap.superseded.map((item) => (
                    <ItemCard key={item.id} item={item} engagementId={e.id} byId={byId} />
                  ))}
                </ul>
              </details>
            )}
            <details className={`${DETAILS} bg-surface`} open={empty}>
              <summary className={SUMMARY}>Add your own proposed work</summary>
              <div className="mt-3">
                <RoadmapItemForm action={createRoadmapItem.bind(null, e.id)} observations={discovery.observations}
                                 submitLabel="Add to roadmap" />
              </div>
            </details>
          </section>

          <section aria-labelledby="phases" className="space-y-3">
            <h2 id="phases" className="text-xl font-semibold text-brand">Engagement phases</h2>
            {phases.length === 0 ? (
              <p className="peak-card text-ink-muted">No engagement phases yet. Accept a roadmap item, then create its phase.</p>
            ) : (
              <ul className="grid gap-3 lg:grid-cols-2">
                {phases.map((p) => <li key={p.id}><PhaseSetupCard phase={p} /></li>)}
              </ul>
            )}
            <details className={`${DETAILS} bg-surface`}>
              <summary className={SUMMARY}>Create a phase without a roadmap item</summary>
              <p className="mt-2 text-sm text-ink-muted">
                For agreed work that did not come from the roadmap. The phase is marked as created manually, with your reason.
              </p>
              <div className="mt-3"><ManualPhaseForm action={createManualPhase.bind(null, e.id)} /></div>
            </details>
          </section>
        </div>
      )}
    </>
  );
}
