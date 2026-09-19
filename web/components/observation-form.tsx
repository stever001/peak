"use client";

import Link from "next/link";
import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { Observation, SessionSummary } from "@/lib/api";
import { LEVEL_LABELS } from "@/lib/labels";

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

export function ObservationForm({ action, observation, sessions, submitLabel, cancelHref }: {
  action: Action;
  observation?: Observation;
  sessions?: SessionSummary[];
  submitLabel: string;
  cancelHref?: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    // Keyed on the success message so the form clears after each new observation.
    <form key={state.success} action={formAction} className="space-y-4">
      <Field label="Observation" htmlFor="observation_text">
        <textarea id="observation_text" name="observation_text" rows={4} required
                  defaultValue={observation?.observation_text ?? ""}
                  className="peak-input min-h-28 py-3" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Category (optional)" htmlFor="category">
          <input id="category" name="category" maxLength={64} defaultValue={observation?.category ?? ""}
                 className="peak-input" />
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
