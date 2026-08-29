import type { GarmentCollection, GarmentThickness } from "./types";

export interface ExtractedGarment {
  id: string;
  iconKey: string;
  label: string;
  category: string;
  colorName: string;
  colorHex: string;
  thickness: GarmentThickness;
  confidence: number;
  note?: string;
}

export interface ImageAnalysisResult {
  mode: "ai" | "demo";
  summary: string;
  items: ExtractedGarment[];
}

export interface InspirationLook {
  id: string;
  title: string;
  note: string;
  imageDataUrl: string;
  collection: Exclude<GarmentCollection, "accessory">;
  createdAt: string;
  updatedAt: string;
  items: ExtractedGarment[];
  /** When enabled, this look can replace a built-in outfit on the Today page. */
  recommendationEnabled?: boolean;
}
