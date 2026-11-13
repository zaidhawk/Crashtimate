import type {
  CostRange,
  Damage,
  EstimateLine,
  Panel,
  PriceRequest,
  ShareRequest,
  VehicleOptions,
} from "./types";

export interface PanelGroup {
  panel: Panel;
  lines: EstimateLine[];
  cost: CostRange;
}

/** Estimate lines grouped by panel, in the order the panels first appear. */
export function groupByPanel(lines: EstimateLine[]): PanelGroup[] {
  const groups = new Map<Panel, PanelGroup>();
  for (const line of lines) {
    const group = groups.get(line.panel) ?? {
      panel: line.panel,
      lines: [],
      cost: { low: 0, high: 0 },
    };
    group.lines.push(line);
    group.cost = {
      low: group.cost.low + line.cost.low,
      high: group.cost.high + line.cost.high,
    };
    groups.set(line.panel, group);
  }
  return [...groups.values()];
}

/** Damage the user added by hand, with nothing to show on a photo. */
export function newDamage(panel: Panel = "front_bumper"): Damage {
  return {
    panel,
    damage_type: "dent",
    severity: "moderate",
    description: "Added by hand.",
    confidence: 1,
    box: null,
    photo: 0,
  };
}

function vehicleFields(options: VehicleOptions) {
  const vin = options.vin.trim();
  const postalCode = options.postalCode.trim();
  return {
    vin: vin || null,
    postal_code: postalCode || null,
    // The server only uses these when there's no VIN it can decode.
    vehicle_size: options.size,
    vehicle_tier: options.tier,
  };
}

export function priceRequest(damages: Damage[], options: VehicleOptions): PriceRequest {
  return {
    damages: damages.map(({ panel, damage_type, severity, confidence }) => ({
      panel,
      damage_type,
      severity,
      confidence,
    })),
    ...vehicleFields(options),
  };
}

export const MAX_DESCRIPTION_LENGTH = 300;

export function shareRequest(
  photoHashes: string[],
  damages: Damage[],
  options: VehicleOptions,
): ShareRequest {
  return {
    photos: photoHashes,
    damages: damages.map((damage) => ({
      ...damage,
      description: damage.description.slice(0, MAX_DESCRIPTION_LENGTH),
    })),
    ...vehicleFields(options),
  };
}
