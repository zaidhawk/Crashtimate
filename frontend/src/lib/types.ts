// Short names for the API's types. api-schema.ts is generated from the backend's OpenAPI
// schema (npm run gen:api), so these can't drift from what the server sends.
import type { components } from "./api-schema";

type Schemas = components["schemas"];

export type Panel = Schemas["Panel"];
export type DamageType = Schemas["DamageType"];
export type Severity = Schemas["Severity"];
export type Operation = Schemas["Operation"];
export type BodySize = Schemas["BodySize"];
export type VehicleTier = Schemas["VehicleTier"];

export type BoundingBox = Schemas["BoundingBox"];
export type Damage = Schemas["DetectedDamage"];
export type DamageReport = Schemas["DamageReport"];
export type PhotoAnalysis = Schemas["AnalyzeResponse"];
export type EstimateResponse = Schemas["EstimateResponse"];

export type CostRange = Schemas["CostRange"];
export type HoursRange = Schemas["HoursRange"];
export type Estimate = Schemas["Estimate"];
export type EstimateLine = Schemas["EstimateLine"];
export type EstimateTotals = Schemas["EstimateTotals"];
export type UnpricedDamage = Schemas["UnpricedDamage"];
export type Vehicle = Schemas["Vehicle"];

export type PriceRequest = Schemas["PriceRequest"];
export type ShareRequest = Schemas["ShareRequest"];
export type SharedEstimate = Schemas["SharedEstimate"];

/** What the user told us about the vehicle. Sent with every pricing request. */
export interface VehicleOptions {
  vin: string;
  postalCode: string;
  size: BodySize;
  tier: VehicleTier;
}
