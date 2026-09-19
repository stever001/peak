"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { KeyPerson } from "@/lib/api";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

/** Pick a client key person (fills name/title) or type the interviewee directly. */
export function InterviewStartForm({ action, keyPersonnel, cancelHref }: {
  action: Action; keyPersonnel: KeyPerson[]; cancelHref: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  return (
    <form action={formAction} className="peak-card space-y-5">
      {keyPersonnel.length > 0 && (
        <Field label="Choose a key person (optional)" htmlFor="key_person">
          <select id="key_person" className="peak-input" defaultValue=""
                  onChange={(e) => {
                    const person = keyPersonnel[Number(e.target.value)];
                    setName(person?.name ?? "");
                    setTitle(person?.role ?? "");
                  }}>
            <option value="">Someone else</option>
            {keyPersonnel.map((p, i) => (
              <option key={i} value={i}>{p.role ? `${p.name} — ${p.role}` : p.name}</option>
            ))}
          </select>
        </Field>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Interviewee name" htmlFor="interviewee_name">
          <input id="interviewee_name" name="interviewee_name" required maxLength={255} value={name}
                 onChange={(e) => setName(e.target.value)} className="peak-input" />
        </Field>
        <Field label="Role / title" htmlFor="interviewee_title">
          <input id="interviewee_title" name="interviewee_title" maxLength={255} value={title}
                 onChange={(e) => setTitle(e.target.value)} className="peak-input" />
        </Field>
        <Field label="Notes / context (optional)" htmlFor="notes" wide>
          <textarea id="notes" name="notes" rows={3} className="peak-input min-h-24 py-3" />
        </Field>
      </div>
      <FormMessage state={state} />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Link href={cancelHref}
              className="inline-flex min-h-touch items-center justify-center rounded-peak border border-line px-6 font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={pending} className="peak-button">
          {pending ? "Starting…" : "Start interview"}
        </button>
      </div>
    </form>
  );
}
