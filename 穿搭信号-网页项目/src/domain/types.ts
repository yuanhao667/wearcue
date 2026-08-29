export type Scene = "commute" | "date" | "travel";
export type ThermalBand = "hot" | "warm" | "mild" | "cool" | "cold" | "freezing" | "severe";
export type FeedbackCadence = "daily" | "three_days" | "weekly" | "off";
export type GarmentCollection = "mens" | "womens" | "accessory";
export type UserGarmentPresentation = "unset" | "mens" | "womens";
export type GarmentThickness = "thin" | "regular" | "thick";

export interface City {
  id: string;
  name: string;
  admin1?: string;
  country: string;
  latitude: number;
  longitude: number;
  timezone: string;
}

export interface HourlyWeather {
  time: string;
  temperature: number;
  apparentTemperature: number;
  precipitationProbability: number;
  precipitation: number;
  rain: number;
  snowfall: number;
  weatherCode: number;
  windSpeed: number;
  windGust: number;
}

export interface WeatherSnapshot {
  city: City;
  date: string;
  timezone: string;
  currentTemperature: number;
  currentApparentTemperature: number;
  apparentMin: number;
  apparentMax: number;
  temperatureMin: number;
  temperatureMax: number;
  maxPrecipitationProbability: number;
  totalPrecipitation: number;
  totalSnowfall: number;
  maxWindSpeed: number;
  maxWindGust: number;
  uvIndexMax: number;
  weatherCode: number;
  hourly: HourlyWeather[];
  fetchedAt: string;
}

export interface GarmentItem {
  id: string;
  name: string;
  category: "top" | "bottom" | "outerwear" | "shoes" | "accessory";
  icon: "tee" | "shirt" | "sweater" | "jacket" | "coat" | "down" | "pants" | "shorts" | "skirt" | "sneaker" | "boot" | "umbrella" | "cap";
  color: string;
  /** Exact user-library SVG and sampled colour, when this item came from a saved look. */
  sourceIconKey?: string;
  colorHex?: string;
  /** Apparel only. Shoes and accessories express warmth through their item type. */
  thickness?: GarmentThickness;
}

export interface OutfitTemplate {
  id: string;
  thermalBand: ThermalBand;
  scenes: Scene[];
  label: string;
  styleTags: string[];
  items: GarmentItem[];
  rationale: string;
  audiences?: Array<Exclude<GarmentCollection, "accessory">>;
  source?: "built-in" | "personal";
}

export interface WeatherAdjustments {
  needsRemovableLayer: boolean;
  needsWaterproof: boolean;
  needsHeavyRainProtection: boolean;
  needsSnowProtection: boolean;
  needsWindproof: boolean;
  avoidUmbrella: boolean;
  needsSunProtection: boolean;
  needsStrongSunProtection: boolean;
}

export interface Recommendation {
  thermalBand: ThermalBand;
  template: OutfitTemplate;
  items: GarmentItem[];
  summary: string;
  weatherTags: string[];
  tips: string[];
  adjustments: WeatherAdjustments;
}

export interface UserSettings {
  city: City;
  scene: Scene;
  garmentPresentation: UserGarmentPresentation;
  coldOffset: number;
  reminderEnabled: boolean;
  reminderTime: string;
  feedbackCadence: FeedbackCadence;
  feedbackLastShownAt?: string;
  feedbackLastAnsweredAt?: string;
}
