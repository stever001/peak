import Link from "next/link";

import { Coverage, EvidenceFindingCard, Pill, Section, Trace, type MaterialKind } from "@/components/assessment-view";
import type { FinalReport, ReportSectionKey } from "@/lib/api";
import { LEVEL_LABELS } from "@/lib/labels";

const SECTION_KIND: Record<ReportSectionKey, MaterialKind> = {
  executive_overview: "report",
  discovery_summary: "discovery",
  low_hanging_fruit: "discovery",
  evidence_findings: "evidence",
  recommendations: "evidence",
  limitations: "report",
};

/** Section headings without the parenthetical material note — the pill carries that on screen. */
function shortTitle(title: string) {
  return title.replace(/\s*\(.*\)$/, "");
}

function Bullets({ items, empty = "None recorded." }: { items: string[]; empty?: string }) {
  return items.length > 0 ? (
    <ul className="list-disc space-y-1 pl-5 text-sm text-ink-muted">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  ) : <p className="text-sm text-ink-muted">{empty}</p>;
}

function Overview({ r, engagementId }: { r: FinalReport; engagementId: string }) {
  const o = r.executive_overview;
  return (
    <>
      <dl className="grid gap-5 sm:grid-cols-2">
        <div>
          <dt className="text-sm text-ink-muted">Engagement</dt>
          <dd className="mt-0.5">{o.engagement_label ?? "Untitled engagement"}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Client</dt>
          <dd className="mt-0.5">{o.client_name ?? "Not recorded"}</dd>
        </div>
      </dl>
      <div className="mt-5 rounded-peak border border-line bg-surface p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">North Star</h3>
          <Pill tone="bg-highlight">Consultant working material</Pill>
        </div>
        {o.north_star ? (
          <>
            <p className="text-lg">{o.north_star}</p>
            {o.north_star_context && <p className="mt-2 whitespace-pre-line text-ink-muted">{o.north_star_context}</p>}
          </>
        ) : (
          <p className="text-ink-muted">
            No North Star recorded.{" "}
            <Link href={`/engagements/${engagementId}#discovery`} className="font-medium text-brand">Set one in Discovery</Link>.
          </p>
        )}
      </div>
      <h3 className="mt-5 mb-2 font-semibold">Summary</h3>
      <Bullets items={o.summary} />
    </>
  );
}

function Discovery({ r }: { r: FinalReport }) {
  const s = r.discovery_summary;
  return (
    <>
      <p className="mb-4 text-sm text-ink-muted">
        Recorded during interviews. Not reviewed evidence — no review status, reliability rating, or recommendation
        eligibility.
      </p>
      {s.coverage ? <Coverage c={s.coverage} /> : (
        <p className="text-ink-muted">No discovery material has been recorded for this engagement.</p>
      )}
      <h3 className="mt-6 mb-3 font-semibold">Discovery-derived findings ({s.findings.length})</h3>
      {s.findings.length > 0 ? (
        <ul className="grid gap-3 lg:grid-cols-2">
          {s.findings.map((f) => (
            <li key={f.finding_id} className="rounded-peak border border-line bg-surface p-4">
              {f.category && <p className="mb-1 text-sm text-ink-muted">{f.category}</p>}
              <p className="whitespace-pre-line">{f.statement}</p>
              <Trace trace={f.trace} />
            </li>
          ))}
        </ul>
      ) : <p className="text-sm text-ink-muted">No consultant observation has been recorded.</p>}
      <h3 className="mt-6 mb-2 font-semibold">Discovery limitations</h3>
      <Bullets items={s.limitations} />
    </>
  );
}

function Fruit({ r }: { r: FinalReport }) {
  const s = r.low_hanging_fruit;
  if (s.groups.length === 0) {
    return <p className="text-ink-muted">The consultant has flagged no low-hanging fruit for this engagement.</p>;
  }
  return (
    <>
      <div className="mb-5 space-y-2 text-sm text-ink-muted">
        <p>{s.grouping_note}</p>
        <p>{s.not_ranked_note}</p>
      </div>
      <div className="space-y-6">
        {s.groups.map((g) => (
          <div key={g.label}>
            <h3 className="mb-3 flex flex-wrap gap-2">
              <Pill>Value: {g.estimated_value ? LEVEL_LABELS[g.estimated_value] : "Not stated"}</Pill>
              <Pill>Effort: {g.estimated_effort ? LEVEL_LABELS[g.estimated_effort] : "Not stated"}</Pill>
            </h3>
            <ul className="grid gap-3 lg:grid-cols-2">
              {g.candidates.map((c) => (
                <li key={c.finding_id} className="rounded-peak border border-line bg-surface p-4">
                  {c.category && <p className="mb-1 text-sm text-ink-muted">{c.category}</p>}
                  <p className="whitespace-pre-line">{c.statement}</p>
                  <Trace trace={c.trace} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}

function Evidence({ r }: { r: FinalReport }) {
  const s = r.evidence_findings;
  return (
    <>
      {s.findings.length > 0 ? (
        <ul className="grid gap-3 lg:grid-cols-2">
          {s.findings.map((f) => <EvidenceFindingCard key={f.finding_id} f={f} />)}
        </ul>
      ) : (
        <p className="text-ink-muted">No evidence currently supports an operational finding for this engagement.</p>
      )}
      {s.confidence_notes.length > 0 && (
        <>
          <h3 className="mt-5 mb-2 font-semibold">Evidence confidence</h3>
          <Bullets items={s.confidence_notes} />
        </>
      )}
    </>
  );
}

function Recommendations({ r }: { r: FinalReport }) {
  const s = r.recommendations;
  if (s.recommendations.length === 0) {
    return (
      <>
        <p className="text-ink-muted">
          None available from the current evidence posture, and none was drafted. Discovery material and
          low-hanging-fruit flags do not produce a formal recommendation.
        </p>
        {s.blocked_reasons.length > 0 && <div className="mt-2"><Bullets items={s.blocked_reasons} /></div>}
      </>
    );
  }
  return (
    <ul className="space-y-3">
      {s.recommendations.map((rec) => (
        <li key={rec.recommendation_id} className="rounded-peak border border-line bg-surface p-4">
          <p>{rec.text}</p>
          <p className="mt-2 text-sm text-ink-muted">
            Internal only · requires human review · for finding {rec.finding_id}
          </p>
        </li>
      ))}
    </ul>
  );
}

function Limitations({ r }: { r: FinalReport }) {
  const s = r.limitations;
  return (
    <>
      <Bullets items={s.boundary_statements} />
      <h3 className="mt-5 mb-2 font-semibold">Evidence limitations</h3>
      <Bullets items={s.assessment_limitations} />
      <h3 className="mt-5 mb-2 font-semibold">Discovery limitations</h3>
      <Bullets items={s.discovery_limitations} />
    </>
  );
}

/**
 * The internal Final Report foundation: the assessment rearranged into report sections. Each section
 * keeps its material label, so discovery working material is never mistaken for governed evidence.
 * Internal draft only — not client-facing, not approved, not exported.
 */
export function FinalReportView({ r, markdown, engagementId }: { r: FinalReport; markdown: string; engagementId: string }) {
  const body: Record<ReportSectionKey, React.ReactNode> = {
    executive_overview: <Overview r={r} engagementId={engagementId} />,
    discovery_summary: <Discovery r={r} />,
    low_hanging_fruit: <Fruit r={r} />,
    evidence_findings: <Evidence r={r} />,
    recommendations: <Recommendations r={r} />,
    limitations: <Limitations r={r} />,
  };
  const counts: Partial<Record<ReportSectionKey, number>> = {
    low_hanging_fruit: r.low_hanging_fruit.groups.reduce((n, g) => n + g.candidates.length, 0),
    evidence_findings: r.evidence_findings.findings.length,
    recommendations: r.recommendations.recommendations.length,
  };
  return (
    <div className="space-y-6">
      <section className="peak-card border-attention">
        <p className="text-sm">
          <span className="font-semibold">Internal draft report.</span> Not client-facing, not approved for client
          use, and not exported. Composed from the internal assessment; it requires consultant review before any part
          of it is used with a client.
        </p>
      </section>

      <nav aria-label="Report sections" className="flex flex-wrap gap-2">
        {r.section_order.map((key) => (
          <a key={key} href={`#${key}`}
             className="inline-flex min-h-touch items-center rounded-full border border-line bg-surface px-4 text-sm font-medium hover:border-brand">
            {shortTitle(r.section_titles[key])}
          </a>
        ))}
      </nav>

      {r.section_order.map((key) => (
        <Section key={key} id={key} title={shortTitle(r.section_titles[key])} kind={SECTION_KIND[key]} count={counts[key]}>
          {body[key]}
        </Section>
      ))}

      <section className="peak-card">
        <details>
          <summary className="inline-flex min-h-touch cursor-pointer items-center font-semibold">Markdown source</summary>
          <pre className="mt-3 max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded-peak border border-line bg-surface p-4 font-mono text-xs">
            {markdown}
          </pre>
        </details>
      </section>
    </div>
  );
}
