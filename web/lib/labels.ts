/** Display labels shared by the discovery screens. */
export const ANSWER_TYPE_LABELS: Record<string, string> = {
  short_text: "Short text",
  long_text: "Long text",
  yes_no: "Yes / No",
  single_choice: "Single choice",
};

export const LEVEL_LABELS: Record<string, string> = { low: "Low", medium: "Medium", high: "High" };

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(`${iso}${iso.endsWith("Z") ? "" : "Z"}`).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

/** Phase 216: what a consultant observation rests on. A label, never a promotion to evidence. */
export const BASIS_LABELS: Record<string, string> = {
  testimony: "Client testimony",
  observed: "Consultant observation on site",
  document: "Document or system record reviewed",
  measured: "Measured or counted by the consultant",
  inferred: "Consultant inference",
};

/** Phase 216 diagnostic classification vocabulary (provisional). Mirrors the server catalogue. */
export const FINDING_CLASS_LABELS: Record<string, string> = {
  ACC: "Record inaccuracy",
  CTRL: "Transaction control / authorization",
  PROC: "Process step",
  LOC: "Location / storage discipline",
  REPL: "Replenishment / reorder",
  FUL: "Picking / fulfillment",
  COND: "Returns, damaged, excess, obsolete",
  DATA: "Item master data",
  SYS: "Systems and handoffs",
  VIS: "Measurement / visibility",
  OWN: "Ownership / accountability",
  PEOPLE: "Key-person dependency / training",
  TRACE: "Lot / serial / expiry traceability",
  IMPACT: "Business consequence",
};
