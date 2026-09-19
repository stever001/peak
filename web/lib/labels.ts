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
