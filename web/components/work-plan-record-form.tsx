"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { TaskRecord, WorkRecordKind } from "@/lib/api";
import { BASIS_LABELS } from "@/lib/labels";
import { RECORD_FORMS, WORK_RECORD_KINDS } from "@/lib/work-plan";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

/**
 * Record what you actually found while doing a task. Starts empty: nothing from the task's guidance
 * is copied in. A correction keeps the original's kind and supersedes it; the original is kept.
 */
export function RecordForm({ action, correcting, cancelHref }: {
  action: Action;
  /** The record being corrected, if any. */
  correcting?: TaskRecord;
  cancelHref?: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const fixedKind = correcting?.record_kind as WorkRecordKind | undefined;
  const [kind, setKind] = useState<WorkRecordKind>(fixedKind ?? "note");
  const form = RECORD_FORMS[kind];
  const prior = correcting?.structured ?? {};
  return (
    // Keyed on the success message so the form clears after each saved record.
    <form key={state.success} action={formAction} className="space-y-4">
      {correcting ? (
        <>
          <input type="hidden" name="record_kind" value={kind} />
          <input type="hidden" name="supersedes_record_id" value={correcting.id} />
          <p className="rounded-peak bg-canvas px-4 py-3 text-sm">
            Correcting a {form.label.toLowerCase()}. The original stays in the history, marked as
            corrected.
          </p>
        </>
      ) : (
        <fieldset>
          <legend className="peak-label">What are you recording?</legend>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {WORK_RECORD_KINDS.map((k) => (
              <label key={k}
                     className={`flex min-h-touch cursor-pointer flex-col justify-center rounded-peak border px-3 py-2 ${k === kind ? "border-brand bg-canvas" : "border-line bg-surface"}`}>
                <span className="flex items-center gap-2 font-medium">
                  <input type="radio" name="record_kind" value={k} checked={k === kind}
                         onChange={() => setKind(k)} className="size-5 accent-brand" />
                  {RECORD_FORMS[k].label}
                </span>
              </label>
            ))}
          </div>
          <p className="mt-2 text-sm text-ink-muted">{form.description}</p>
        </fieldset>
      )}

      {form.structured.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {form.structured.map((f) => (
            <Field key={`${kind}-${f.name}`} label={f.label} htmlFor={`structured_${f.name}`} hint={f.hint}>
              <input id={`structured_${f.name}`} name={`structured_${f.name}`} maxLength={1000}
                     inputMode={f.numeric ? "decimal" : undefined} enterKeyHint="next"
                     defaultValue={prior[f.name] === undefined ? "" : String(prior[f.name])}
                     className="peak-input" />
            </Field>
          ))}
        </div>
      )}

      <Field label={form.text.label} htmlFor="record_text">
        <textarea id="record_text" name="record_text" rows={4} required maxLength={10000}
                  defaultValue={correcting?.record_text ?? ""} className="peak-input min-h-28 py-3" />
      </Field>

      <Field label="Basis (optional)" htmlFor="basis" hint="What this record rests on.">
        <select id="basis" name="basis" defaultValue={correcting?.basis ?? ""} className="peak-input">
          <option value="">Not recorded</option>
          {Object.entries(BASIS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </Field>

      <FormMessage state={state} />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        {cancelHref && (
          <Link href={cancelHref}
                className="inline-flex min-h-touch items-center justify-center rounded-peak border border-line px-6 font-medium">
            Cancel
          </Link>
        )}
        <button type="submit" disabled={pending} className="peak-button">
          {pending ? "Saving…" : correcting ? "Save correction" : `Save ${form.label.toLowerCase()}`}
        </button>
      </div>
    </form>
  );
}
