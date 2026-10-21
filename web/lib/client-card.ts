import type { ClientSummary } from "@/lib/api";

type CardFields = Pick<ClientSummary, "city" | "country" | "contact_name" | "engagement_count">;

/**
 * A Clients card's secondary line, in order: location, main contact, active engagements. A missing
 * value is left out rather than described, and a client with no active engagement shows no count.
 */
export function clientCardDetails(c: CardFields): string[] {
  const location = [c.city, c.country].filter(Boolean).join(", ");
  const active = c.engagement_count > 0
    ? `${c.engagement_count} active ${c.engagement_count === 1 ? "engagement" : "engagements"}`
    : "";
  return [location, c.contact_name ?? "", active].filter(Boolean);
}
