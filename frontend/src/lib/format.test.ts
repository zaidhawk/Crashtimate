import { describe, expect, it } from "vitest";

import { formatCost, formatHours, vehicleName } from "./format";
import { panelLabel } from "./labels";
import type { Vehicle } from "./types";

const vehicle = (fields: Partial<Vehicle>): Vehicle => ({
  tier: "standard",
  size: "car",
  ...fields,
});

describe("formatCost", () => {
  it("shows a range in whole dollars", () => {
    expect(formatCost({ low: 1246, high: 3562 })).toBe("$1,246 – $3,562");
  });

  it("shows one number when the range is a single price", () => {
    expect(formatCost({ low: 125, high: 125 })).toBe("$125");
  });
});

describe("formatHours", () => {
  it("keeps one decimal", () => {
    expect(formatHours({ low: 1.5, high: 3 })).toBe("1.5 – 3.0 h");
    expect(formatHours({ low: 2.2, high: 2.2 })).toBe("2.2 h");
  });
});

describe("vehicleName", () => {
  it("title-cases the make but leaves initials alone", () => {
    expect(vehicleName(vehicle({ year: 2019, make: "HONDA", model: "Civic" }))).toBe(
      "2019 Honda Civic",
    );
    expect(vehicleName(vehicle({ year: 2021, make: "BMW", model: "330i" }))).toBe("2021 BMW 330i");
    expect(vehicleName(vehicle({ make: "MERCEDES-BENZ" }))).toBe("Mercedes-Benz");
  });

  it("is null for a typical vehicle with no details", () => {
    expect(vehicleName(vehicle({}))).toBeNull();
  });
});

describe("panelLabel", () => {
  it("turns the API name into words", () => {
    expect(panelLabel("left_front_fender")).toBe("Left front fender");
  });
});
