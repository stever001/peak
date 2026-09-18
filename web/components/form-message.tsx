import type { FormState } from "@/app/actions";

export function FormMessage({ state }: { state: FormState }) {
  if (state.error) {
    return (
      <p role="alert" className="rounded-peak border-l-4 border-attention bg-canvas px-4 py-3 text-sm">
        {state.error}
      </p>
    );
  }
  if (state.success) {
    return (
      <p role="status" className="rounded-peak border-l-4 border-accent bg-canvas px-4 py-3 text-sm">
        {state.success}
      </p>
    );
  }
  return null;
}
