import { describe, expect, it } from "vitest";

import { groupByPanel, newDamage, priceRequest, shareRequest } from "./estimate";
import { PANEL_OPTIONS, PANELS } from "./labels";
import type { EstimateLine, Panel, VehicleOptions } from "./types";

const line = (panel: Panel, low: number, high: number): EstimateLine => ({
  panel,
  operation: "repair",
  description: "",
  body_hours: null,
  refinish_hours: null,
  parts: null,
  sublet: null,
  cost: { low, high },
});

const options: VehicleOptions = { vin: "", postalCode: "", size: "suv", tier: "luxury" };

describe("groupByPanel", () => {
  it("groups lines under their panel, keeping first-seen order, and adds up the cost", () => {
    const groups = groupByPanel([
      line("hood", 100, 200),
      line("front_bumper", 50, 80),
      line("hood", 10, 20),
    ]);

    expect(groups.map((group) => group.panel)).toEqual(["hood", "front_bumper"]);
    expect(groups[0].lines).toHaveLength(2);
    expect(groups[0].cost).toEqual({ low: 110, high: 220 });
    expect(groups[1].cost).toEqual({ low: 50, high: 80 });
  });

  it("handles an empty estimate", () => {
    expect(groupByPanel([])).toEqual([]);
  });
});

describe("priceRequest", () => {
  it("sends only what pricing needs", () => {
    const request = priceRequest([{ ...newDamage("hood"), description: "long text" }], options);

    expect(request.damages).toEqual([
      { panel: "hood", damage_type: "dent", severity: "moderate", confidence: 1 },
    ]);
  });

  it("sends blank fields as null and always includes the vehicle type", () => {
    const request = priceRequest([], { ...options, vin: "  ", postalCode: " m5v 2t6 " });

    expect(request).toMatchObject({
      vin: null,
      postal_code: "m5v 2t6",
      vehicle_size: "suv",
      vehicle_tier: "luxury",
    });
  });
});

describe("shareRequest", () => {
  it("keeps descriptions within the limit the server accepts", () => {
    const damage = { ...newDamage(), description: "x".repeat(500) };

    const request = shareRequest(["a".repeat(64)], [damage], options);

    expect(request.damages[0].description).toHaveLength(300);
    expect(request.photos).toEqual(["a".repeat(64)]);
  });
});

describe("panel options", () => {
  it("offer every panel exactly once", () => {
    const offered = PANEL_OPTIONS.flatMap((option) => option.panels);

    expect(offered).toHaveLength(30);
    expect(new Set(offered)).toEqual(new Set(PANELS));
  });
});
