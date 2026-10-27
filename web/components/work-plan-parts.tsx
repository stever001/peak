import Link from "next/link";
import type { ReactNode } from "react";

import type { EngagementPhaseDetail, PhaseStatus, PhaseTask, TaskRecord, TaskStatus } from "@/lib/api";
import { BASIS_LABELS, formatDate } from "@/lib/labels";
import {
  PHASE_STATUS_LABELS, RECORD_FORMS, RECORD_KIND_LABELS, sentence, splitRecords, TASK_STATUS_LABELS,
  taskFlags,
} from "@/lib/work-plan";

export function Pill({ children, tone = "bg-line" }: { children: ReactNode; tone?: string }) {
  return (
    <span className={`inline-flex shrink-0 rounded-full px-3 py-1 text-xs font-semibold text-ink ${tone}`}>
      {children}
    </span>
  );
}

export function PhaseStatusPill({ status }: { status: PhaseStatus }) {
  const tone = status === "authorized" ? "bg-accent" : status === "planned" ? "bg-highlight" : "bg-line";
  return <Pill tone={tone}>{PHASE_STATUS_LABELS[status] ?? status}</Pill>;
}

export function TaskStatusPill({ status }: { status: TaskStatus }) {
  const tone = status === "in_progress" ? "bg-accent" : status === "suggested" ? "bg-highlight" : "bg-line";
  return <Pill tone={tone}>{TASK_STATUS_LABELS[status]}</Pill>;
}

/** One task in the ordered work plan: a large tap target, never a table row. */
export function TaskCard({ task, phaseId, isNext }: { task: PhaseTask; phaseId: string; isNext: boolean }) {
  const flags = taskFlags(task);
  const done = task.status === "completed" || task.status === "not_applicable";
  return (
    <li>
      <Link href={`/phases/${phaseId}/tasks/${task.id}`}
            className={`flex min-h-20 gap-4 rounded-peak border bg-surface px-4 py-4 hover:border-brand ${isNext ? "border-brand border-2" : "border-line"}`}>
        <span aria-hidden="true"
              className={`flex size-10 shrink-0 items-center justify-center rounded-full text-base font-semibold ${done ? "bg-brand text-on-brand" : "bg-canvas text-brand"}`}>
          {done ? "✓" : task.sequence}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-start justify-between gap-2">
            <span className={`font-semibold ${done ? "text-ink-muted" : "text-brand"}`}>
              <span className="sr-only">Task {task.sequence}: </span>{task.title}
            </span>
            <span className="flex flex-wrap gap-2">
              {isNext && <Pill tone="bg-highlight">Next</Pill>}
              <Pill>{task.required ? "Required" : "Optional"}</Pill>
              <TaskStatusPill status={task.status} />
            </span>
          </span>
          {flags.length > 0 && (
            <span className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink-muted">
              {flags.map((f) => <span key={f}>· {f}</span>)}
            </span>
          )}
        </span>
      </Link>
    </li>
  );
}

/** The phase's deterministic readiness, as the API computes it. Never a score. */
export function ReadinessPanel({ phase }: { phase: EngagementPhaseDetail }) {
  const r = phase.readiness;
  const byId = new Map(phase.tasks.map((t) => [t.id, t]));
  const optional = r.notes.filter((n) => n.code === "optional_incomplete");
  const other = r.notes.filter((n) => n.code !== "optional_incomplete" && n.code !== "added_after_authorization");
  const added = r.notes.filter((n) => n.code === "added_after_authorization");
  const name = (taskId?: string) => {
    const t = taskId ? byId.get(taskId) : undefined;
    return t ? `Task ${t.sequence}: ${t.title}` : "";
  };
  const link = (taskId: string | undefined, children: ReactNode) => taskId
    ? <Link href={`/phases/${phase.id}/tasks/${taskId}`} className="inline-flex min-h-touch items-center font-medium text-brand underline-offset-2 hover:underline">{children}</Link>
    : children;
  return (
    <section aria-labelledby="readiness" className={`peak-card border-l-4 ${r.ready ? "border-l-accent" : "border-l-attention"}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="readiness" className="text-lg font-semibold">
          {phase.status === "completed" ? "Phase work completed"
            : r.ready ? "Ready to move forward" : "Not ready yet"}
        </h2>
        <span className="text-sm text-ink-muted">
          {r.required_resolved} of {r.required_tasks} required {r.required_tasks === 1 ? "task" : "tasks"} resolved
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full bg-brand"
             style={{ width: `${r.required_tasks ? (r.required_resolved / r.required_tasks) * 100 : 0}%` }} />
      </div>
      {r.blocking.length > 0 && (
        <>
          <h3 className="mt-4 font-semibold">Still needed before this phase can move forward</h3>
          <ul className="mt-2 space-y-2">
            {r.blocking.map((b, i) => (
              <li key={`${b.code}-${b.task_id ?? i}`} className="rounded-peak bg-canvas px-4 py-3">
                {link(b.task_id, b.task_id ? name(b.task_id) : sentence(b.reason_text))}
                {b.task_id && <span className="block text-sm text-ink-muted">{sentence(b.reason_text)}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {optional.length > 0 && (
        <>
          <h3 className="mt-4 font-semibold">Optional work not done (does not hold the phase back)</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {optional.map((n) => <li key={n.task_id}>{link(n.task_id, name(n.task_id))}</li>)}
          </ul>
        </>
      )}
      {other.length > 0 && (
        <>
          <h3 className="mt-4 font-semibold">Resolved without completing</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {other.map((n) => (
              <li key={`${n.code}-${n.task_id}`}>
                {link(n.task_id, name(n.task_id))}: <span className="text-ink-muted">{sentence(n.reason_text)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {added.length > 0 && (
        <p className="mt-4 text-sm text-ink-muted">
          {added.length} {added.length === 1 ? "task was" : "tasks were"} added after the phase was authorized
          (a visible change to the agreed scope).
        </p>
      )}
      <details className="mt-4 text-sm text-ink-muted">
        <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">How readiness is decided</summary>
        <p className="mt-1">{r.rule}</p>
      </details>
    </section>
  );
}

function RecordBody({ r }: { r: TaskRecord }) {
  const fields = RECORD_FORMS[r.record_kind as keyof typeof RECORD_FORMS]?.structured ?? [];
  const shown = fields.filter((f) => r.structured[f.name] !== undefined);
  return (
    <>
      {shown.length > 0 && (
        <dl className="mb-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
          {shown.map((f) => (
            <div key={f.name}>
              <dt className="inline text-ink-muted">{f.label.replace(/ \(.*\)$/, "")}: </dt>
              <dd className="inline font-medium">{String(r.structured[f.name])}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="whitespace-pre-line">{r.record_text}</p>
    </>
  );
}

/** What the consultant recorded: current records, with corrected versions kept below. */
export function RecordList({ records, correctHref }: {
  records: TaskRecord[];
  /** Link to correct a record; omitted when the task no longer accepts records. */
  correctHref?: (r: TaskRecord) => string;
}) {
  const byId = new Map(records.map((r) => [r.id, r]));
  const { current, earlier } = splitRecords(records);
  const meta = (r: TaskRecord) => [r.recorded_by, formatDate(r.created_at),
                                   r.basis ? `Basis: ${BASIS_LABELS[r.basis]}` : null].filter(Boolean).join(" · ");
  return (
    <>
      <ul className="space-y-3">
        {current.map((r) => (
          <li key={r.id} className="rounded-peak border border-line bg-surface p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Pill tone="bg-accent">{RECORD_KIND_LABELS[r.record_kind]}</Pill>
              {r.supersedes_record_id && byId.has(r.supersedes_record_id) && <Pill>Correction</Pill>}
            </div>
            <RecordBody r={r} />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-ink-muted">
              <span>{meta(r)}</span>
              {correctHref && (
                <Link href={correctHref(r)} className="inline-flex min-h-touch items-center font-medium text-brand">
                  Correct this record
                </Link>
              )}
            </div>
          </li>
        ))}
      </ul>
      {earlier.length > 0 && (
        <details className="mt-4 rounded-peak border border-line p-4">
          <summary className="inline-flex min-h-touch cursor-pointer items-center font-medium text-brand">
            Earlier versions ({earlier.length}) · kept, replaced by a correction
          </summary>
          <ul className="mt-3 space-y-3">
            {earlier.map((r) => (
              <li key={r.id} className="rounded-peak bg-canvas p-4 text-ink-muted">
                <div className="mb-2"><Pill>{RECORD_KIND_LABELS[r.record_kind]} · corrected</Pill></div>
                <div className="line-through decoration-ink-muted/60"><RecordBody r={r} /></div>
                <p className="mt-2 text-sm">{meta(r)}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}
