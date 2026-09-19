"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

export function NorthStarForm({ action, northStar, context }: {
  action: Action; northStar: string | null; context: string | null;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="mt-4 space-y-4">
      <Field label="North Star" htmlFor="north_star"
             hint="The one outcome this discovery effort is aiming at, e.g. reduce inventory discrepancies.">
        <input id="north_star" name="north_star" maxLength={1000} defaultValue={northStar ?? ""}
               className="peak-input" />
      </Field>
      <Field label="Supporting context (optional)" htmlFor="north_star_context">
        <textarea id="north_star_context" name="north_star_context" rows={3}
                  defaultValue={context ?? ""} className="peak-input min-h-24 py-3" />
      </Field>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button">
        {pending ? "Saving…" : "Save North Star"}
      </button>
    </form>
  );
}
