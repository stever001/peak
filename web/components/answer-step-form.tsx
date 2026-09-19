"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { FormMessage } from "@/components/form-message";
import type { InterviewSession } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;
type Step = InterviewSession["questions"][number];

function Choice({ value, label, checked }: { value: string; label: string; checked: boolean }) {
  return (
    <label className="flex min-h-touch cursor-pointer items-center gap-3 rounded-peak border border-line bg-surface px-4 py-3 has-[:checked]:border-brand has-[:checked]:bg-canvas">
      <input type="radio" name="answer" value={value} defaultChecked={checked} className="size-5 accent-brand" />
      <span className="text-base">{label}</span>
    </label>
  );
}

/** One question: a large answer control and Back / Save / Save & next. */
export function AnswerStepForm({ action, step, hasPrev }: {
  action: Action; step: Step; hasPrev: boolean;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form key={step.id} action={formAction} className="space-y-5">
      {step.answer_type === "yes_no" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Choice value="yes" label="Yes" checked={step.answer === "yes"} />
          <Choice value="no" label="No" checked={step.answer === "no"} />
        </div>
      )}
      {step.answer_type === "single_choice" && (
        <div className="grid gap-3">
          {step.choices.map((c) => <Choice key={c} value={c} label={c} checked={step.answer === c} />)}
        </div>
      )}
      {step.answer_type === "short_text" && (
        <input name="answer" aria-label="Answer" maxLength={1000} defaultValue={step.answer ?? ""}
               className="peak-input" autoFocus />
      )}
      {step.answer_type === "long_text" && (
        <textarea name="answer" aria-label="Answer" rows={6} defaultValue={step.answer ?? ""}
                  className="peak-input min-h-40 py-3" autoFocus />
      )}
      <FormMessage state={state} />
      <div className="grid grid-cols-2 gap-3 sm:flex sm:justify-between">
        <button type="submit" name="intent" value="prev" disabled={pending || !hasPrev}
                className="min-h-touch rounded-peak border border-line bg-surface px-5 font-medium disabled:opacity-40">
          Back
        </button>
        <div className="col-span-2 row-start-1 grid grid-cols-2 gap-3 sm:col-span-1 sm:row-start-auto sm:flex">
          <button type="submit" name="intent" value="stay" disabled={pending}
                  className="min-h-touch rounded-peak border border-line bg-surface px-5 font-medium">
            Save
          </button>
          <button type="submit" name="intent" value="next" disabled={pending} className="peak-button">
            {pending ? "Saving…" : "Save & next"}
          </button>
        </div>
      </div>
    </form>
  );
}
