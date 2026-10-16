"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import { STATUS_LABELS } from "@/components/status-badge";
import { InternalTestBadge } from "@/components/internal-test-badge";
import type { ClientSummary, ConsultantOption, Engagement } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;
const EDITABLE_STATUSES = ["active", "on_hold", "closed"] as const;

/** The confirmation an Internal Test / Training engagement needs before save (Phase 215). The server
 *  requires it too and forces the classification itself; this text is not the protection. */
export const INTERNAL_TEST_CONFIRMATION =
  "This engagement is for internal testing, training, or practice only. It will be marked internal_test, " +
  "will not be treated as real client data, and will not be client-accessible. Continue?";

type Kind = "real_client" | "internal_test";

/**
 * Phase 215: on create, the engagement type. Real Client uses the client the form was opened from.
 * Internal Test / Training clears that client and offers only internal test clients (the reserved
 * `internal_test_` namespace), plus a link to create one, and requires the confirmation.
 */
function ClientChoice({ realClient, testClients, initialKind, initialTestClientId, canAssign }: {
  realClient: { id: string; name: string | null } | null;
  testClients: ClientSummary[];
  initialKind: Kind;
  initialTestClientId: string;
  /** An Admin assigns the Lead as usual; anyone else becomes the Lead of their Internal Test engagement. */
  canAssign: boolean;
}) {
  const [kind, setKind] = useState<Kind>(initialKind);
  const [testClientId, setTestClientId] = useState(initialTestClientId);
  const clientId = kind === "internal_test" ? testClientId : realClient?.id ?? "";
  return (
    <fieldset className="space-y-4">
      <legend className="mb-2 font-medium">Engagement type</legend>
      <input type="hidden" name="client_id" value={clientId} />
      <div className="flex flex-col gap-3 sm:flex-row">
        {([["real_client", "Real Client"], ["internal_test", "Internal Test / Training"]] as const).map(([value, label]) => (
          <label key={value} className="flex min-h-touch flex-1 items-center gap-3 rounded-peak border border-line px-4">
            <input type="radio" name="engagement_type" value={value} checked={kind === value}
                   onChange={() => setKind(value)} className="h-5 w-5" />
            <span className="font-medium">{label}</span>
          </label>
        ))}
      </div>
      {kind === "real_client" ? (
        realClient ? (
          <p className="text-sm text-ink-muted">Client: <span className="font-medium text-ink">{realClient.name}</span></p>
        ) : (
          <p className="text-sm text-ink-muted">
            Real Client engagements are added from the client.{" "}
            <Link href="/clients" className="font-medium text-brand">Choose a client</Link>.
          </p>
        )
      ) : (
        <div className="space-y-4 rounded-peak border border-line p-4">
          <InternalTestBadge />
          <input type="hidden" name="internal_test" value="true" />
          <Field label="Internal test client" htmlFor="internal_test_client_id"
                 hint="Only internal test clients are listed. Use synthetic details, never real client data.">
            <select id="internal_test_client_id" required value={testClientId}
                    onChange={(e) => setTestClientId(e.target.value)} className="peak-input">
              <option value="">Choose an internal test client</option>
              {testClients.map((c) => <option key={c.id} value={c.id}>{c.organization_label}</option>)}
            </select>
          </Field>
          <Link href="/clients/new?internal_test=1" className="inline-flex text-sm font-medium text-brand">
            Create internal test client
          </Link>
          {!canAssign && (
            <p className="text-sm font-medium">You will be assigned as the Lead Consultant for this training engagement.</p>
          )}
          <label className="flex items-start gap-3">
            <input type="checkbox" name="internal_test_confirmed" value="true" required className="mt-1 h-5 w-5" />
            <span className="text-sm">{INTERNAL_TEST_CONFIRMATION}</span>
          </label>
        </div>
      )}
    </fieldset>
  );
}

export function EngagementForm({ action, engagement, client, creation, consultants, cancelHref, submitLabel, canAssign }: {
  action: Action;
  engagement?: Engagement;
  /** Editing: the engagement's client, which cannot change. */
  client?: { id: string; name: string | null };
  /** Creating (Phase 215): the client the form was opened from, if real, and the internal test clients. */
  creation?: { realClient: { id: string; name: string | null } | null; testClients: ClientSummary[];
               initialKind: Kind; initialTestClientId: string };
  consultants: ConsultantOption[];
  cancelHref: string;
  submitLabel: string;
  /** Only an Admin may set the assigned consultant: they give the Lead Consultant approval. */
  canAssign: boolean;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const status = EDITABLE_STATUSES.find((s) => s === engagement?.status) ?? "active";

  return (
    <form action={formAction} className="peak-card space-y-5">
      {creation ? (
        <ClientChoice {...creation} canAssign={canAssign} />
      ) : client && (
        <>
          <input type="hidden" name="client_id" value={client.id} />
          <p className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
            Client: <span className="font-medium text-ink">{client.name}</span>
            {engagement?.engagement_classification === "internal_test" && <InternalTestBadge />}
          </p>
        </>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Engagement name" htmlFor="engagement_label" wide>
          <input id="engagement_label" name="engagement_label" required maxLength={255}
                 defaultValue={engagement?.engagement_label ?? ""} className="peak-input" />
        </Field>
        <Field label="Assigned consultant" htmlFor="assigned_consultant_id"
               hint={canAssign ? "Gives the Lead Consultant approval of report versions."
                 : "Only an Admin can change this. The assigned consultant gives the Lead Consultant approval."}>
          {/* A disabled select is not submitted, so a non-Admin save leaves the assignment as it is. */}
          <select id="assigned_consultant_id" name="assigned_consultant_id" disabled={!canAssign}
                  defaultValue={engagement?.assigned_consultant?.id ?? ""} className="peak-input disabled:opacity-60">
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
