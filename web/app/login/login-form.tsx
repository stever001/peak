"use client";

import { useActionState } from "react";

import { login, type FormState } from "@/app/actions";
import { FormMessage } from "@/components/form-message";

export function LoginForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(login, {});
  return (
    <form action={action} className="space-y-5">
      <div>
        <label htmlFor="email" className="peak-label">Email</label>
        <input id="email" name="email" type="email" autoComplete="username" required
               className="peak-input" />
      </div>
      <div>
        <label htmlFor="password" className="peak-label">Password</label>
        <input id="password" name="password" type="password" autoComplete="current-password"
               required className="peak-input" />
      </div>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full">
        {pending ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
