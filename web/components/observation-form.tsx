"use client";

import Link from "next/link";
import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { Observation, QuestionOption, SessionSummary } from "@/lib/api";
import { BASIS_LABELS, FINDING_CLASS_LABELS, LEVEL_LABELS } from "@/lib/labels";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

function LevelSelect({ name, label, value }: { name: string; label: string; value?: string | null }) {
  return (
    <Field label={label} htmlFor={name}>
      <select id={name} name={name} defaultValue={value ?? ""} className="peak-input">
        <option value="">Not estimated</option>
        {Object.entries(LEVEL_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </Field>
  );
}

export function ObservationForm({ action, observation, sessions, questions, submitLabel, cancelHref }: {
  action: Action;
  observation?: Observation;
  sessions?: SessionSummary[];
  /** Questions this engagement asks, for "Prompted by" (Phase 216). */
  questions: QuestionOption[];
  submitLabel: string;
  cancelHref?: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const categories = [...new Set(questions.map((q) => q.category))];
  const linked = observation?.question;
  return (
    // Keyed on the success message so the form clears after each new observation.
    <form key={state.success} action={formAction} className="space-y-4">
      <Field label="Observation" htmlFor="observation_text">
        <textarea id="observation_text" name="observation_text" rows={4} required
                  defaultValue={observation?.observation_text ?? ""}
                  className="peak-input min-h-28 py-3" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Category (optional)" htmlFor="category" hint="A finding-class code such as CTRL, or your own label.">
          <input id="category" name="category" maxLength={64} list="finding-classes"
                 defaultValue={observation?.category ?? ""} className="peak-input" />
          <datalist id="finding-classes">
            {Object.entries(FINDING_CLASS_LABELS).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </datalist>
        </Field>
        <Field label="Basis (optional)" htmlFor="basis" hint="What this rests on. Discovery material is never evidence.">
          <select id="basis" name="basis" defaultValue={observation?.basis ?? ""} className="peak-input">
            <option value="">Not recorded</option>
            {Object.entries(BASIS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="Prompted by question (optional)" htmlFor="question_id" wide>
          <select id="question_id" name="question_id" defaultValue={linked?.id ?? ""} className="peak-input">
            <option value="">Not linked to a question</option>
            {linked && !questions.some((q) => q.id === linked.id) && (
              <option value={linked.id}>{linked.prompt ?? "Linked question (no longer active)"}</option>
            )}
            {categories.map((c) => (
              <optgroup key={c} label={c}>
                {questions.filter((q) => q.category === c).map((q) => (
                  <option key={q.id} value={q.id}>{q.prompt.length > 90 ? `${q.prompt.slice(0, 90)}…` : q.prompt}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </Field>
        {sessions && (
          <Field label="From interview (optional)" htmlFor="session_id">
            <select id="session_id" name="session_id" defaultValue="" className="peak-input">
              <option value="">Not linked to an interview</option>
              {sessions.map((s) => <option key={s.id} value={s.id}>{s.interviewee_name}</option>)}
            </select>
          </Field>
        )}
        <LevelSelect name="estimated_effort" label="Estimated effort" value={observation?.estimated_effort} />
        <LevelSelect name="estimated_value" label="Estimated value" value={observation?.estimated_value} />
      </div>
      <label className="flex min-h-touch items-center gap-3 rounded-peak border border-line bg-surface px-4">
        <input type="checkbox" name="low_hanging_fruit" defaultChecked={observation?.low_hanging_fruit}
               className="size-5 accent-brand" />
        <span className="font-medium">Low-hanging fruit — an immediate opportunity</span>
      </label>
      <FormMessage state={state} />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        {cancelHref && (
          <Link href={cancelHref}
                className="inline-flex min-h-touch items-center justify-center rounded-peak border border-line px-6 font-medium">
            Cancel
          </Link>
        )}
        <button type="submit" disabled={pending} className="peak-button">
          {pending ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
