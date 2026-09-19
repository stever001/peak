import type { ReactNode } from "react";

/** Labelled form control; stacks on phones, sits in the parent grid on wider screens. */
export function Field({
  label, htmlFor, children, hint, wide = false,
}: { label: string; htmlFor: string; children: ReactNode; hint?: string; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <label htmlFor={htmlFor} className="peak-label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-sm text-ink-muted">{hint}</p>}
    </div>
  );
}

/** A read-only label/value pair for detail pages. */
export function Detail({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="mt-0.5 break-words">{value || <span className="text-ink-muted">—</span>}</dd>
    </div>
  );
}
