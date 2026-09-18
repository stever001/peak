"use client";

import { useActionState } from "react";

import { addConsultant, type FormState } from "@/app/actions";
import { FormMessage } from "@/components/form-message";

export function AddConsultantForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(addConsultant, {});
  return (
    // Keyed on the success message so the fields reset after each account is created.
    <form key={state.success} action={action} className="space-y-4">
      <div>
        <label htmlFor="name" className="peak-label">Name</label>
        <input id="name" name="name" required maxLength={255} autoComplete="off" className="peak-input" />
      </div>
      <div>
        <label htmlFor="email" className="peak-label">Email</label>
        <input id="email" name="email" type="email" required autoComplete="off" className="peak-input" />
      </div>
      <div>
        <label htmlFor="role" className="peak-label">Role</label>
        <select id="role" name="role" defaultValue="consultant" className="peak-input">
          <option value="consultant">Consultant</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div>
        <label htmlFor="password" className="peak-label">Initial password</label>
        <input id="password" name="password" type="password" required minLength={12}
               autoComplete="new-password" className="peak-input" />
        <p className="mt-1 text-sm text-ink-muted">At least 12 characters. Share it privately.</p>
      </div>
      <div>
        <label htmlFor="confirm" className="peak-label">Confirm password</label>
        <input id="confirm" name="confirm" type="password" required minLength={12}
               autoComplete="new-password" className="peak-input" />
      </div>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full">
        {pending ? "Adding…" : "Add consultant"}
      </button>
    </form>
  );
}
