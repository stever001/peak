"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { Client, KeyPerson } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;
const EMPTY_PERSON: KeyPerson = { name: "", role: "", email: "", phone: "" };

function Text({ name, label, value, type = "text", wide, required }: {
  name: string; label: string; value?: string | null; type?: string; wide?: boolean;
  required?: boolean;
}) {
  return (
    <Field label={label} htmlFor={name} wide={wide}>
      <input id={name} name={name} type={type} defaultValue={value ?? ""} required={required}
             className="peak-input" />
    </Field>
  );
}

export function ClientForm({ action, client, cancelHref, submitLabel }: {
  action: Action; client?: Client; cancelHref: string; submitLabel: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const [people, setPeople] = useState<KeyPerson[]>(client?.key_personnel ?? []);
  const setPerson = (i: number, key: keyof KeyPerson, value: string) =>
    setPeople((rows) => rows.map((row, j) => (j === i ? { ...row, [key]: value } : row)));

  return (
    <form action={formAction} className="space-y-6">
      <section className="peak-card">
        <h2 className="mb-4 text-lg font-semibold">Company</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Text name="organization_label" label="Company name" value={client?.organization_label}
                wide required />
          <Field label="Description" htmlFor="description" wide>
            <textarea id="description" name="description" rows={4}
                      defaultValue={client?.description ?? ""}
                      className="peak-input min-h-32 py-3" />
          </Field>
        </div>
      </section>

      <section className="peak-card">
        <h2 className="mb-4 text-lg font-semibold">Address</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Text name="address_line1" label="Address line 1" value={client?.address_line1} wide />
          <Text name="address_line2" label="Address line 2 (optional)" value={client?.address_line2}
                wide />
          <Text name="city" label="City" value={client?.city} />
          <Text name="region" label="State / region" value={client?.region} />
          <Text name="postal_code" label="Postal code" value={client?.postal_code} />
          <Text name="country" label="Country" value={client?.country} />
        </div>
      </section>

      <section className="peak-card">
        <h2 className="mb-4 text-lg font-semibold">Main contact</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Text name="contact_name" label="Name" value={client?.contact_name} />
          <Text name="contact_title" label="Title / role" value={client?.contact_title} />
          <Text name="contact_email" label="Email" type="email" value={client?.contact_email} />
          <Text name="contact_phone" label="Phone" type="tel" value={client?.contact_phone} />
        </div>
      </section>

      <section className="peak-card">
        <h2 className="mb-1 text-lg font-semibold">Key personnel</h2>
        <p className="mb-4 text-sm text-ink-muted">Name is required; role, email and phone are optional.</p>
        <input type="hidden" name="key_personnel" value={JSON.stringify(people)} />
        <ul className="space-y-4">
          {people.map((person, i) => (
            <li key={i} className="rounded-peak border border-line p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {(["name", "role", "email", "phone"] as const).map((key) => (
                  <div key={key}>
                    <label htmlFor={`kp-${i}-${key}`} className="peak-label capitalize">{key}</label>
                    <input id={`kp-${i}-${key}`} value={person[key] ?? ""}
                           type={key === "email" ? "email" : key === "phone" ? "tel" : "text"}
                           onChange={(e) => setPerson(i, key, e.target.value)}
                           className="peak-input" />
                  </div>
                ))}
              </div>
              <button type="button" onClick={() => setPeople((rows) => rows.filter((_, j) => j !== i))}
                      className="mt-3 min-h-touch rounded-peak px-3 text-sm font-medium text-ink-muted hover:text-ink">
                Remove person
              </button>
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => setPeople((rows) => [...rows, { ...EMPTY_PERSON }])}
                className="mt-4 min-h-touch rounded-peak border border-line px-4 font-medium hover:border-brand">
          Add person
        </button>
      </section>

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
