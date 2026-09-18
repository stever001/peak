import type { Role } from "@/lib/api";

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
      role === "admin" ? "bg-highlight text-ink" : "bg-accent text-ink"
    }`}>
      {role === "admin" ? "Admin" : "Consultant"}
    </span>
  );
}
