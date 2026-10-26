import type { PhaseTask, RecordKind, TaskRecord, TaskStatus, WorkRecordKind } from "@/lib/api";

/**
 * Phase 218: display and form helpers for guided work plans. Pure functions, no rules: whether a
 * task applies, is blocked or can be completed comes from the API (`work_state`, `readiness`).
 */

export type RecordField = { name: string; label: string; hint?: string; multiline?: boolean;
                            required?: boolean; numeric?: boolean };

/** The record kinds a consultant can enter, with the fields each form shows. */
export const RECORD_FORMS: Record<WorkRecordKind, {
  label: string; description: string; text: RecordField; structured: RecordField[];
}> = {
  note: {
    label: "Note",
    description: "A factual note of what you saw or did.",
    text: { name: "record_text", label: "What you found", multiline: true, required: true },
    structured: [],
  },
  interview_response: {
    label: "Interview response",
    description: "What someone told you, in their words.",
    text: { name: "record_text", label: "What they said", multiline: true, required: true },
    structured: [
      { name: "question", label: "Question you asked" },
      { name: "interviewee_role", label: "Who answered (role, not name)",
        hint: "For example: receiving lead, second shift." },
    ],
  },
  measurement: {
    label: "Measurement",
    description: "Something you counted, timed or measured yourself.",
    text: { name: "record_text", label: "What the measurement shows", multiline: true,
            required: true },
    structured: [
      { name: "measure", label: "What you measured", hint: "For example: dock-to-stock time." },
      { name: "value", label: "Value", numeric: true },
      { name: "unit", label: "Unit", hint: "For example: minutes, cases, lines." },
    ],
  },
  mismatch: {
    label: "Mismatch",
    description: "A difference between what a record says and what you found.",
    text: { name: "record_text", label: "Describe the mismatch", multiline: true, required: true },
    structured: [
      { name: "reference", label: "Reference", hint: "The PO, packing slip, location or item." },
      { name: "expected", label: "Expected (per the record)" },
      { name: "observed", label: "Observed (what you found)" },
      { name: "resolution", label: "How staff resolved it (optional)" },
    ],
  },
};

export const WORK_RECORD_KINDS = Object.keys(RECORD_FORMS) as WorkRecordKind[];

export const RECORD_KIND_LABELS: Record<RecordKind, string> = {
  note: "Note",
  interview_response: "Interview response",
  measurement: "Measurement",
  mismatch: "Mismatch",
  photo: "Photo",
  document_photo: "Photo of a document",
  document: "Document",
};

/** Kinds a task may suggest but that cannot be captured yet (Phase 217 reserves them). */
export const MEDIA_KINDS: RecordKind[] = ["photo", "document_photo", "document"];

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  suggested: "Suggested",
  open: "Not started",
  in_progress: "In progress",
  completed: "Done",
  not_applicable: "Not applicable",
};

export const PHASE_STATUS_LABELS: Record<string, string> = {
  planned: "Planned · awaiting authorization",
  authorized: "Authorized",
  completed: "Completed",
};

/**
 * The API body for one task record, from the form's fields. Blank optional fields are left out;
 * a numeric "value" is sent as a number. Never adds content the consultant did not enter.
 */
export function recordPayload(fields: Record<string, string>) {
  const kind = fields.record_kind as WorkRecordKind;
  const form = RECORD_FORMS[kind];
  const structured: Record<string, string | number> = {};
  for (const f of form?.structured ?? []) {
    const raw = (fields[`structured_${f.name}`] ?? "").trim();
    if (!raw) continue;
    structured[f.name] = f.numeric && /^-?\d+(\.\d+)?$/.test(raw) ? Number(raw) : raw;
  }
  return {
    record_kind: kind,
    record_text: (fields.record_text ?? "").trim(),
    ...(Object.keys(structured).length ? { structured } : {}),
    ...(fields.basis ? { basis: fields.basis } : {}),
    ...(fields.supersedes_record_id ? { supersedes_record_id: fields.supersedes_record_id } : {}),
  };
}

/** Current records (not yet corrected) and earlier versions, each oldest first. */
export function splitRecords(records: TaskRecord[]) {
  return {
    current: records.filter((r) => !r.superseded_by),
    earlier: records.filter((r) => r.superseded_by),
  };
}

/** A task is unresolved while it is in the plan and neither done nor not applicable. */
export function isOpen(t: Pick<PhaseTask, "status">) {
  return t.status === "open" || t.status === "in_progress";
}

/**
 * The task to work on next: the first open task in sequence that applies and is not waiting on a
 * prerequisite, as the API reports them. Null when nothing is workable.
 */
export function nextTask(tasks: PhaseTask[]): PhaseTask | null {
  return tasks.find((t) => isOpen(t) && t.work_state.applies !== false
    && !t.work_state.completion_blockers.some((b) => b.code === "prerequisites_incomplete")) ?? null;
}

/** Short, plain-language flags for a task card, from the API's work state. */
export function taskFlags(t: PhaseTask): string[] {
  const w = t.work_state;
  const flags: string[] = [];
  if (t.status === "suggested") flags.push("Suggested · not in the plan until accepted");
  if (isOpen(t)) {
    const waiting = w.prerequisites.filter((p) => !p.resolved).map((p) => p.sequence);
    if (waiting.length) flags.push(`Waiting on task ${waiting.join(", ")}`);
    if (w.applies === null && w.condition_task) {
      flags.push(`Applies only if task ${w.condition_task.sequence} records a `
        + `${RECORD_KIND_LABELS[t.condition!.record_kind].toLowerCase()}`);
    }
    if (w.applies === false) flags.push("Does not apply · its condition was not met");
    else if (w.record_missing) flags.push("Record still needed");
  }
  if (t.added_after_authorization) flags.push("Added after authorization");
  return flags;
}

/** "Applies only if task 2 records a mismatch", for the task's guidance. */
export function conditionText(t: PhaseTask): string | null {
  const c = t.work_state.condition_task;
  if (!c || !t.condition) return null;
  const kind = RECORD_KIND_LABELS[t.condition.record_kind].toLowerCase();
  const state = t.work_state.applies === true ? " It does, so this task applies."
    : t.work_state.applies === false ? " It did not, so this task does not apply."
    : "";
  return `Applies only if task ${c.sequence} (${c.title}) records a ${kind}.${state}`;
}

/** First letter upper-case: the API's readiness reasons are sentence fragments. */
export function sentence(text: string | null | undefined): string {
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}
