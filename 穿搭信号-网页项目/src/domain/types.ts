export type GarmentCollection = "mens" | "womens" | "accessory";

export interface City {
  id: string;
  name: string;
  admin1?: string;
  country: string;
  latitude: number;
  longitude: number;
  timezone: string;
}
