import Link from "next/link";

import type {
  AssessmentFinding,
  DiscoveryAssessmentContext,
  DiscoveryFinding,
  DiscoveryTrace,
  InternalAssessment,
  LowHangingFruitCandidate,
} from "@/lib/api";
import { LEVEL_LABELS } from "@/lib/labels";

function Pill({ children, tone = "bg-line" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold text-ink ${tone}`}>{children}</span>;
}

/**
 * Says what kind of material a section holds. The whole point of the page is that a consultant
 * never has to guess whether what they are reading is governed evidence or their own notes.
 */
function MaterialLabel({ kind }: { kind: "discovery" | "evidence" }) {
  return kind === "discovery" ? (
    <Pill tone="bg-highlight">Consultant working material</Pill>
  ) : (
    <Pill tone="bg-accent">Evidence-backed · governed</Pill>
  );
}

function Section({
  title, kind, count, children,
}: { title: string; kind: "discovery" | "evidence"; count?: number; children: React.ReactNode }) {
  return (
    <section className="peak-card">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold">
          {title}
          {count !== undefined && <span className="ml-2 text-ink-muted">({count})</span>}
        </h2>
        <MaterialLabel kind={kind} />
      </div>
      {children}
    </section>
  );
}

/** "Where did this come from?" — the person and interview first, identifiers in the details. */
function Trace({ trace }: { trace: DiscoveryTrace }) {
  const ids = [
    trace.observation_id && `observation ${trace.observation_id}`,
    trace.session_id && `session ${trace.session_id}`,
    trace.question_id && `question ${trace.question_id}`,
    trace.answer_id && `answer ${trace.answer_id}`,
  ].filter(Boolean) as string[];
  return (
    <div className="mt-3 border-t border-line pt-3 text-sm text-ink-muted">
      <p>
        {trace.session_id && trace.interviewee_name ? (
          <>
            From the interview with{" "}
            <Link href={`/interviews/${trace.session_id}`} className="font-medium text-brand">
              {trace.interviewee_name}
            </Link>
          </>
        ) : (
          "Recorded outside an interview"
        )}
        {trace.recorded_by && <> · recorded by {trace.recorded_by}</>}
        {trace.observation_id && (
          <>
            {" · "}
            <Link href={`/observations/${trace.observation_id}/edit`} className="font-medium text-brand">
              Open observation
            </Link>
          </>
        )}
      </p>
      {trace.question_prompt && <p className="mt-1">Question: “{trace.question_prompt}”</p>}
      {ids.length > 0 && (
        <details className="mt-1">
          <summary className="inline-flex min-h-touch cursor-pointer items-center">Record identifiers</summary>
          <p className="break-words font-mono text-xs">{ids.join(" · ")}</p>
        </details>
      )}
    </div>
  );
}

function LevelPills({ value, effort }: { value: string | null; effort: string | null }) {
  return (
    <>
      {value && <Pill>Value: {LEVEL_LABELS[value] ?? value}</Pill>}
      {effort && <Pill>Effort: {LEVEL_LABELS[effort] ?? effort}</Pill>}
    </>
  );
}

function DiscoveryFindingCard({ f }: { f: DiscoveryFinding }) {
  return (
    <li className="rounded-peak border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {f.low_hanging_fruit && <Pill tone="bg-highlight">Low-hanging fruit</Pill>}
        <LevelPills value={f.estimated_value} effort={f.estimated_effort} />
        {f.category && <span className="text-sm text-ink-muted">{f.category}</span>}
      </div>
      <p className="whitespace-pre-line">{f.statement}</p>
      <p className="mt-2 text-sm text-ink-muted">
        Not reviewed evidence — this does not support a formal recommendation on its own.
      </p>
      <Trace trace={f.trace} />
    </li>
  );
}

function FruitCard({ c }: { c: LowHangingFruitCandidate }) {
  return (
    <li className="rounded-peak border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <LevelPills value={c.estimated_value} effort={c.estimated_effort} />
        {c.category && <span className="text-sm text-ink-muted">{c.category}</span>}
      </div>
      <p className="whitespace-pre-line">{c.statement}</p>
      <p className="mt-2 text-sm text-ink-muted">
        The consultant’s own flag on their own observation. Not an approved recommendation.
      </p>
      <Trace trace={c.trace} />
    </li>
  );
}

function EvidenceFindingCard({ f }: { f: AssessmentFinding }) {
  return (
    <li className="rounded-peak border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Pill tone={f.recommendation_eligible ? "bg-accent" : "bg-line"}>
          {f.recommendation_eligible ? "Recommendation eligible" : "Recommendation blocked"}
        </Pill>
        <Pill>Review: {f.review_status || "unknown"}</Pill>
        {f.reliability && <Pill>Reliability: {f.reliability}</Pill>}
      </div>
      <p className="whitespace-pre-line">
        {f.statement_available ? f.statement : (
          <span className="text-ink-muted">No persisted finding statement is available for this evidence.</span>
        )}
      </p>
      {f.recommendation_blocked_reasons.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-sm text-ink-muted">
          {f.recommendation_blocked_reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
      <div className="mt-3 border-t border-line pt-3 text-sm text-ink-muted">
        <details>
          <summary className="inline-flex min-h-touch cursor-pointer items-center">Record identifiers</summary>
          <p className="break-words font-mono text-xs">
            {[`evidence ${f.evidence_id}`, ...f.source_reference_ids.map((s) => `source ${s}`),
              ...f.supporting_review_ids.map((r) => `review ${r}`)].join(" · ")}
          </p>
        </details>
      </div>
    </li>
  );
}

function Coverage({ d }: { d: DiscoveryAssessmentContext }) {
  const c = d.coverage;
  const stat = (label: string, value: string | number) => (
    <div key={label} className="rounded-peak border border-line bg-surface px-4 py-3">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="mt-0.5 text-2xl font-semibold text-brand">{value}</dd>
    </div>
  );
  return (
    <>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stat("Interviews completed", c.completed_sessions)}
        {stat("In progress", c.in_progress_sessions)}
        {stat("People interviewed", c.interviewees.length)}
        {stat("Questions answered", c.answered_questions)}
      </dl>
      {c.branching_makes_percentage_ambiguous && (
        <p className="mt-4 text-sm text-ink-muted">
          {c.answered_unbranched_questions} of the {c.unbranched_active_questions} question(s) every interview
          sees have been answered. No pool-wide percentage is shown: follow-up questions appear only for some
          interviewees, so the denominator would differ per interview.
        </p>
      )}
      {c.sessions.length > 0 && (
        <ul className="mt-4 grid gap-3 lg:grid-cols-2">
          {c.sessions.map((s) => (
            <li key={s.session_id}>
              <Link href={`/interviews/${s.session_id}`}
                    className="flex min-h-20 flex-col gap-1 rounded-peak border border-line bg-surface px-5 py-4 hover:border-brand">
                <span className="flex items-start justify-between gap-3">
                  <span className="font-semibold text-brand">{s.interviewee_name}</span>
                  <Pill tone={s.status === "completed" ? "bg-line" : "bg-accent"}>
                    {s.status === "completed" ? "Completed" : "In progress"}
                  </Pill>
                </span>
                <span className="text-sm text-ink-muted">
                  {[s.interviewee_title, `${s.answered_count} answered`, s.conducted_by].filter(Boolean).join(" · ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/**
 * The internal assessment: discovery material and evidence-backed material side by side, each
 * under its own label. It is a working document, not a client deliverable and not a final report.
 */
export function AssessmentView({ a, engagementId }: { a: InternalAssessment; engagementId: string }) {
  const d = a.discovery;
  return (
    <div className="space-y-6">
      <section className="peak-card border-attention">
        <p className="text-sm">
          <span className="font-semibold">Internal working document.</span> Not client-facing, not approved, and
          not a deliverable. Every finding here requires human review before it is used with a client.
        </p>
      </section>

      <Section title="North Star" kind="discovery">
        {d?.north_star ? (
          <>
            <p className="text-lg">{d.north_star}</p>
            {d.north_star_context && <p className="mt-2 whitespace-pre-line text-ink-muted">{d.north_star_context}</p>}
            <p className="mt-3 text-sm text-ink-muted">
              Orientation for this engagement. Findings are not scored or aligned against it.
            </p>
          </>
        ) : (
          <p className="text-ink-muted">
            No North Star recorded.{" "}
            <Link href={`/engagements/${engagementId}#discovery`} className="font-medium text-brand">Set one in Discovery</Link>.
          </p>
        )}
      </Section>

      <Section title="Discovery summary" kind="discovery">
        {d?.available ? <Coverage d={d} /> : (
          <p className="text-ink-muted">
            No discovery material recorded.{" "}
            <Link href={`/engagements/${engagementId}#discovery`} className="font-medium text-brand">Start an interview</Link>.
          </p>
        )}
      </Section>

      <Section title="Discovery-derived findings" kind="discovery" count={d?.findings.length ?? 0}>
        {d && d.findings.length > 0 ? (
          <ul className="grid gap-3 lg:grid-cols-2">
            {d.findings.map((f) => <DiscoveryFindingCard key={f.finding_id} f={f} />)}
          </ul>
        ) : (
          <p className="text-ink-muted">
            No consultant observation recorded yet. Observations recorded during discovery appear here as findings.
          </p>
        )}
      </Section>

      <Section title="Low-hanging-fruit candidates" kind="discovery" count={d?.low_hanging_fruit.length ?? 0}>
        {d && d.low_hanging_fruit.length > 0 ? (
          <>
            <p className="mb-4 text-sm text-ink-muted">
              Grouped for reading by the effort and value the consultant entered. A display grouping, not a score,
              a ranking, or a priority order — and no ROI is calculated.
            </p>
            <ul className="grid gap-3 lg:grid-cols-2">
              {d.low_hanging_fruit.map((c) => <FruitCard key={c.finding_id} c={c} />)}
            </ul>
          </>
        ) : (
          <p className="text-ink-muted">Flag an observation as low-hanging fruit during discovery to list it here.</p>
        )}
      </Section>

      <Section title="Evidence-backed findings" kind="evidence" count={a.findings.length}>
        {a.findings.length > 0 ? (
          <ul className="grid gap-3 lg:grid-cols-2">
            {a.findings.map((f) => <EvidenceFindingCard key={f.finding_id} f={f} />)}
          </ul>
        ) : (
          <p className="text-ink-muted">
            No reviewed evidence currently supports an operational finding for this engagement.
          </p>
        )}
      </Section>

      <Section title="Internal recommendations" kind="evidence" count={a.recommendations.length}>
        {a.recommendations.length > 0 ? (
          <ul className="space-y-3">
            {a.recommendations.map((r) => (
              <li key={r.recommendation_id} className="rounded-peak border border-line bg-surface p-4">
                <p>{r.text}</p>
                <p className="mt-2 text-sm text-ink-muted">
                  Internal only · requires human review · for finding {r.finding_id}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <>
            <p className="text-ink-muted">
              None available from the current evidence posture, and none was drafted. Discovery material does not
              produce a formal recommendation on its own.
            </p>
            {a.recommendation_blocked_reasons.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-ink-muted">
                {a.recommendation_blocked_reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            )}
          </>
        )}
      </Section>

      <Section title="Review status and limitations" kind="evidence">
        <dl className="grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-ink-muted">Status</dt>
            <dd className="mt-0.5">{a.status}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink-muted">Client-facing</dt>
            <dd className="mt-0.5">{a.client_facing ? "yes" : "no"}</dd>
          </div>
        </dl>
        {a.confidence_notes.length > 0 && (
          <ul className="mt-4 list-disc pl-5 text-sm text-ink-muted">
            {a.confidence_notes.map((n) => <li key={n}>{n}</li>)}
          </ul>
        )}
        <h3 className="mt-5 font-semibold">Open limitations</h3>
        {a.limitations.length > 0 ? (
          <ul className="mt-2 list-disc pl-5 text-sm text-ink-muted">
            {a.limitations.map((l) => <li key={l}>{l}</li>)}
          </ul>
        ) : <p className="mt-2 text-ink-muted">None recorded.</p>}
      </Section>
    </div>
  );
}
