import type { InspirationLook } from "@/domain/inspiration";

export const INSPIRATION_STORAGE_KEY = "wearwise.inspiration-looks.v1";
const MAX_SAVED_LOOKS = 24;

export function loadInspirationLooks(): InspirationLook[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(INSPIRATION_STORAGE_KEY) ?? "[]") as InspirationLook[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((look) => look && typeof look.id === "string" && Array.isArray(look.items));
  } catch {
    return [];
  }
}

export function saveInspirationLook(look: InspirationLook): InspirationLook[] {
  const current = loadInspirationLooks();
  const updated = [look, ...current.filter((item) => item.id !== look.id)]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, MAX_SAVED_LOOKS);
  window.localStorage.setItem(INSPIRATION_STORAGE_KEY, JSON.stringify(updated));
  return updated;
}

export function deleteInspirationLook(id: string): InspirationLook[] {
  const updated = loadInspirationLooks().filter((look) => look.id !== id);
  window.localStorage.setItem(INSPIRATION_STORAGE_KEY, JSON.stringify(updated));
  return updated;
}
