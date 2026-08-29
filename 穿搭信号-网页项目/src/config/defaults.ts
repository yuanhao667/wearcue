import type { City, UserSettings } from "@/domain/types";

export const DEFAULT_CITY: City = {
  id: "1816670",
  name: "北京",
  admin1: "北京市",
  country: "中国",
  latitude: 39.9042,
  longitude: 116.4074,
  timezone: "Asia/Shanghai",
};

export const DEFAULT_SETTINGS: UserSettings = {
  city: DEFAULT_CITY,
  scene: "commute",
  garmentPresentation: "unset",
  coldOffset: 0,
  reminderEnabled: false,
  reminderTime: "07:30",
  feedbackCadence: "weekly",
};

export const STORAGE_KEYS = {
  settings: "wearwise.settings.v1",
  recentlyShown: "wearwise.recently-shown.v1",
} as const;
