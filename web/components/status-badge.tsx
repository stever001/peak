/** Engagement status. "Paused" is stored as the existing `on_hold` value. */
export const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  on_hold: "Paused",
  closed: "Closed",
  prospective: "Prospective",
  complete: "Complete",
};

export function StatusBadge({ status }: { status: string | null }) {
  const tone =
    status === "active" ? "bg-accent text-ink"
    : status === "on_hold" ? "bg-highlight text-ink"
    : "bg-line text-ink";
  return (
    <span className={`inline-flex shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${tone}`}>
      {status ? (STATUS_LABELS[status] ?? status) : "No status"}
    </span>
  );
}
