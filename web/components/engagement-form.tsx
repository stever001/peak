"use client";

import Link from "next/link";
import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import { STATUS_LABELS } from "@/components/status-badge";
import type { ConsultantOption, Engagement } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;
const EDITABLE_STATUSES = ["active", "on_hold", "closed"] as const;

export function EngagementForm({ action, engagement, client, consultants, cancelHref, submitLabel }: {
  action: Action;
  engagement?: Engagement;
  client: { id: string; name: string | null };
  consultants: ConsultantOption[];
  cancelHref: string;
  submitLabel: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const status = EDITABLE_STATUSES.find((s) => s === engagement?.status) ?? "active";

  return (
    <form action={formAction} className="peak-card space-y-5">
      <input type="hidden" name="client_id" value={client.id} />
      <p className="text-sm text-ink-muted">
        Client: <span className="font-medium text-ink">{client.name}</span>
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Engagement name" htmlFor="engagement_label" wide>
          <input id="engagement_label" name="engagement_label" required maxLength={255}
                 defaultValue={engagement?.engagement_label ?? ""} className="peak-input" />
        </Field>
        <Field label="Assigned consultant" htmlFor="assigned_consultant_id">
          <select id="assigned_consultant_id" name="assigned_consultant_id"
                  defaultValue={engagement?.assigned_consultant?.id ?? ""} className="peak-input">
            <option value="">Unassigned</option>
            {consultants.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Status" htmlFor="status">
          <select id="status" name="status" defaultValue={status} className="peak-input">
            {EDITABLE_STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
          </select>
        </Field>
        <Field label="Current phase" htmlFor="current_phase" wide
               hint="A simple label, for example Discovery, Analysis or Recommendations.">
          <input id="current_phase" name="current_phase" maxLength={128}
                 defaultValue={engagement?.current_phase ?? ""} className="peak-input" />
        </Field>
        <Field label="Objective" htmlFor="objective" wide>
          <textarea id="objective" name="objective" rows={4}
                    defaultValue={engagement?.objective ?? ""} className="peak-input min-h-32 py-3" />
        </Field>
      </div>
      <FormMessage state={state} />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Link href={cancelHref}
              className="inline-flex min-h-touch items-center justify-center rounded-peak border border-line px-6 font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={pending} className="peak-button">
          {pending ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
