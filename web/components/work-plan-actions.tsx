"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";

type FormAction = (prev: FormState, formData: FormData) => Promise<FormState>;
type ButtonAction = () => Promise<FormState>;

/** Complete a task with a result summary the consultant writes. The API checks every blocker. */
export function CompleteTaskForm({ action, expected }: { action: FormAction; expected: string | null }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-4">
      <Field label="Result summary, in your words" htmlFor="result_summary"
             hint={expected ? `The guidance expects: ${expected}` : undefined}>
        <textarea id="result_summary" name="result_summary" rows={4} required maxLength={10000}
                  className="peak-input min-h-28 py-3" />
      </Field>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full sm:w-auto">
        {pending ? "Completing…" : "Complete task"}
      </button>
    </form>
  );
}

/** Resolve a task as not applicable; the reason is required and shown in readiness. */
export function NotApplicableForm({ action }: { action: FormAction }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-4">
      <Field label="Why this task does not apply" htmlFor="reason">
        <textarea id="reason" name="reason" rows={3} required maxLength={4000}
                  className="peak-input min-h-24 py-3" />
      </Field>
      <FormMessage state={state} />
      <button type="submit" disabled={pending}
              className="inline-flex min-h-touch w-full items-center justify-center rounded-peak border border-ink px-6 font-medium sm:w-auto">
        {pending ? "Saving…" : "Mark not applicable"}
      </button>
    </form>
  );
}

/** A single confirmed action with no fields (accept a suggested task, complete the phase). */
export function ActionButton({ action, label, pendingLabel }: {
  action: ButtonAction; label: string; pendingLabel: string;
}) {
  const [state, formAction, pending] = useActionState<FormState>(action, {});
  return (
    <form action={formAction} className="space-y-3">
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full sm:w-auto">
        {pending ? pendingLabel : label}
      </button>
    </form>
  );
}
