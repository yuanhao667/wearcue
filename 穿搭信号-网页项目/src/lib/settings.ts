import { DEFAULT_SETTINGS, STORAGE_KEYS } from "@/config/defaults";
import type { UserSettings } from "@/domain/types";

export function loadSettings(): UserSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEYS.settings);
    if (!stored) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) } as UserSettings;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: UserSettings) {
  window.localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(settings));
}

export function loadRecentlyShown(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEYS.recentlyShown) ?? "[]") as string[];
  } catch {
    return [];
  }
}

export function rememberShown(templateId: string) {
  const updated = [templateId, ...loadRecentlyShown().filter((id) => id !== templateId)].slice(0, 6);
  window.localStorage.setItem(STORAGE_KEYS.recentlyShown, JSON.stringify(updated));
}

export function isFeedbackDue(settings: UserSettings, now = new Date()) {
  if (settings.feedbackCadence === "off") return false;
  if (!settings.feedbackLastAnsweredAt) return true;
  const days = { daily: 1, three_days: 3, weekly: 7 }[settings.feedbackCadence];
  const elapsed = now.getTime() - new Date(settings.feedbackLastAnsweredAt).getTime();
  return elapsed >= days * 24 * 60 * 60 * 1000;
}
