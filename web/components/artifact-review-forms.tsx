"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { FormMessage } from "@/components/form-message";
import type { ConsultantOption } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

const secondary =
  "inline-flex min-h-touch items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand disabled:opacity-60";

export function SubmitVersionForm({ action, label }: { action: Action; label: string }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-3">
      <button type="submit" disabled={pending} className="peak-button">
        {pending ? "Preparing package…" : label}
      </button>
      <FormMessage state={state} />
    </form>
  );
}

/** Approve or reject the exact release package (both renditions) shown on screen, by its package hash. */
export function DecisionForm({ action, packageHash, level }: {
  action: Action; packageHash: string; level: "Lead Consultant" | "Final Approver";
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const id = `note-${level === "Lead Consultant" ? "lead" : "final"}`;
  return (
    <form action={formAction} className="space-y-3">
      <input type="hidden" name="package_hash" value={packageHash} />
      <fieldset>
        <legend className="peak-label">Which rendition did you review?</legend>
        <p className="mb-2 text-sm text-ink-muted">Your decision covers the whole package: the web page and the DOCX.</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:gap-6">
          <label className="inline-flex min-h-touch items-center gap-2">
            <input type="radio" name="reviewed_rendition" value="web" required /> The web page
          </label>
          <label className="inline-flex min-h-touch items-center gap-2">
            <input type="radio" name="reviewed_rendition" value="docx" required /> The DOCX file
          </label>
        </div>
      </fieldset>
      <div>
        <label htmlFor={id} className="peak-label">Note (optional; give the reason for a rejection)</label>
        <textarea id={id} name="note" rows={2} maxLength={2000} className="peak-input min-h-20 py-3" />
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button type="submit" name="decision" value="approved" disabled={pending} className="peak-button">
          {level} approve
        </button>
        <button type="submit" name="decision" value="rejected" disabled={pending} className={secondary}>
          {level} reject
        </button>
      </div>
      <FormMessage state={state} />
    </form>
  );
}

export function DesignateForm({ action, options, reassign }: {
  action: Action; options: ConsultantOption[]; reassign: boolean;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-3">
      <div>
        <label htmlFor="consultant_id" className="peak-label">
          {reassign ? "Reassign Final Approver" : "Choose the Final Approver"}
        </label>
        <select id="consultant_id" name="consultant_id" required defaultValue="" className="peak-input">
          <option value="" disabled>Select a consultant</option>
          {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </div>
      <button type="submit" disabled={pending || options.length === 0} className={reassign ? secondary : "peak-button"}>
        {pending ? "Saving…" : reassign ? "Reassign" : "Designate"}
      </button>
      <FormMessage state={state} />
    </form>
  );
}

export function ReleaseForm({ action, packageHash }: { action: Action; packageHash: string }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-3">
      <input type="hidden" name="package_hash" value={packageHash} />
      <button type="submit" disabled={pending} className="peak-button">
        {pending ? "Releasing…" : "Release this package"}
      </button>
      <FormMessage state={state} />
    </form>
  );
}
