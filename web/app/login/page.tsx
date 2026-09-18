import type { Metadata } from "next";

import { PeakMark } from "@/components/peak-mark";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in · Peak" };

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-brand px-4 py-10">
      <div className="w-full max-w-md rounded-peak bg-surface p-6 shadow-xl sm:p-10">
        <div className="mb-8 flex items-center gap-3">
          <PeakMark />
          <div>
            <p className="text-xl font-semibold text-brand">Peak</p>
            <p className="text-sm text-ink-muted">Consultant Workspace</p>
          </div>
        </div>
        <h1 className="mb-6 text-2xl font-semibold">Sign in</h1>
        <LoginForm />
        <p className="mt-6 text-sm text-ink-muted">
          Accounts are created by a Peak Admin. There is no self-registration.
        </p>
      </div>
    </main>
  );
}
