export type Audience = "mens" | "womens";
export type SceneId = "commute" | "date" | "travel";
export type Thickness = "thin" | "regular" | "thick";
export type OutfitSlot = "top" | "bottom" | "outerwear" | "onepiece" | "shoes" | "equipment";

export interface BackendCity {
  id: string;
  name: string;
  admin1?: string | null;
  country?: string | null;
  latitude: number;
  longitude: number;
  timezone: string;
}

export interface BackendSettings {
  id?: number;
  city_id: string;
  city_name: string;
  latitude: number;
  longitude: number;
  timezone: string;
  audience: Audience;
  cold_offset: number;
  reminder_enabled: boolean;
  reminder_time: string;
  reminder_days: number[];
  updated_at: string;
}

export interface HourlyWeather {
  time: string;
  temperature: number;
  apparent_temperature: number;
  precipitation_probability: number;
  precipitation: number;
  snowfall: number;
  wind_speed: number;
  wind_gust: number;
}

export interface TodayWeather {
  city: string;
  latitude: number;
  longitude: number;
  date: string;
  timezone: string;
  current_temperature: number;
  current_apparent_temperature: number;
  apparent_min: number;
  apparent_max: number;
  temperature_min: number;
  temperature_max: number;
  max_precipitation_probability: number;
  total_precipitation: number;
  total_snowfall: number;
  max_wind_speed: number;
  max_wind_gust: number;
  uv_index_max: number;
  weather_code: number;
  hourly: HourlyWeather[];
  fetched_at: string;
  provider: string;
}

export interface OutfitComponent {
  slot: OutfitSlot;
  functional_icon_key: string;
  variant_type: string;
  color_type?: "solid" | "pattern";
  color_name: string;
  color_value?: string | null;
  pattern_description?: string | null;
  thickness: Thickness;
  confidence?: number;
  approximate?: boolean;
  suggested?: boolean;
  asset_key?: string | null;
}

export interface ReplicationGuide {
  formula: string;
  steps: string[];
  styling_points: string[];
  weather_note: string;
  substitute: string;
}

export interface SuggestedTemperature {
  min: number;
  max: number;
}

export interface OutfitAnalysis {
  summary: string;
  structure_points: string[];
  completion_advice: string[];
}

export interface RecommendationConstraints {
  thermal_band: string;
  calibrated_apparent_min: number;
  apparent_delta: number;
  warnings: string[];
  needs_removable_layer: boolean;
  needs_waterproof: boolean;
  needs_windproof: boolean;
  needs_sun_protection: boolean;
}

export interface BackendRecommendation {
  source: "official" | "personal" | "ai" | "system_ai";
  template_id: string;
  label: string;
  scene: SceneId;
  audience: Audience;
  constraints: RecommendationConstraints;
  items: OutfitComponent[];
  outfit_analysis?: OutfitAnalysis | null;
  replication_guide: ReplicationGuide;
}

export interface Outfit {
  id: string;
  label: string;
  audience: Audience;
  source: "manual" | "inspiration" | "system";
  components: OutfitComponent[];
  scene_ids: SceneId[];
  suitable_min: number;
  suitable_max: number;
  favorite: boolean;
  in_pool: boolean;
  inspiration_id?: string | null;
  skip_count: number;
  created_at: string;
  updated_at: string;
  outfit_analysis?: OutfitAnalysis;
  replication_guide?: ReplicationGuide;
}

export interface VisionResult {
  model_version: string;
  garment_audience: Audience | "unisex";
  image_coverage: "full_body" | "partial" | "unknown";
  requires_user_confirmation: boolean;
  suggested_scenes: SceneId[];
  suggested_temperature: SuggestedTemperature;
  suggested_season: "spring-autumn" | "winter" | "summer";
  components: OutfitComponent[];
  outfit_analysis: OutfitAnalysis;
  replication_guide: ReplicationGuide;
}

export interface Inspiration {
  id: string;
  upload_key: string;
  content_hash: string;
  original_name: string;
  media_type: string;
  status: "queued" | "needs_review" | "ready";
  provider: "mock" | "external";
  result: Partial<VisionResult>;
  created_at: string;
  updated_at: string;
  deduplicated?: boolean;
}

export interface RecommendationRequest {
  apparent_min: number;
  apparent_max: number;
  max_precipitation_probability: number;
  total_precipitation: number;
  total_snowfall: number;
  max_wind_speed: number;
  max_wind_gust: number;
  uv_index_max: number;
  cold_offset: number;
  scene: SceneId;
  audience: Audience;
  city_id: string;
  local_date: string;
  excluded_template_ids: string[];
}
