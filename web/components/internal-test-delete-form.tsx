"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { FormMessage } from "@/components/form-message";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

/**
 * Admin-only logical deletion of an internal test engagement (Phase 215). The Admin must retype the
 * engagement name. Nothing is destroyed: the engagement leaves the active lists and accepts no new work,
 * and its discovery and artifact history are kept.
 */
export function InternalTestDeleteForm({ action, label }: { action: Action; label: string }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="peak-card mt-6 space-y-4">
      <h2 className="text-lg font-semibold">Delete this internal test engagement</h2>
      <p className="text-sm text-ink-muted">
        It leaves the active lists and accepts no new interviews, reports, packages or approvals. Its
        history (discovery, versions, packages, approvals and releases) is kept for audit. Type
        <span className="font-medium text-ink"> {label} </span> to confirm.
      </p>
      <input name="confirm_engagement_label" required aria-label="Engagement name" autoComplete="off"
             className="peak-input" />
      <FormMessage state={state} />
      <button type="submit" disabled={pending}
              className="inline-flex min-h-touch items-center justify-center rounded-peak border border-ink px-6 font-medium">
        {pending ? "Deleting…" : "Delete internal test engagement"}
      </button>
    </form>
  );
}
