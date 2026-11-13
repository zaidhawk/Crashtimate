import { describe, expect, it } from "vitest";

import { checkVin, cleanVin } from "./vin";

describe("checkVin", () => {
  it("accepts real VINs, ignoring case, spaces and dashes", () => {
    expect(checkVin("1HGCM82633A004352")).toEqual({ status: "valid", vin: "1HGCM82633A004352" });
    expect(checkVin(" 1hgcm-82633 a004352 ")).toEqual({
      status: "valid",
      vin: "1HGCM82633A004352",
    });
    // Check digit X
    expect(checkVin("1M8GDM9AXKP042788").status).toBe("valid");
  });

  it("catches a typo through the check digit", () => {
    expect(checkVin("1HGCM82643A004352").status).toBe("invalid");
  });

  it("reports progress while the VIN is being typed", () => {
    expect(checkVin("")).toEqual({ status: "empty" });
    expect(checkVin("1HGCM")).toEqual({ status: "incomplete", length: 5 });
  });

  it("rejects characters a VIN cannot contain", () => {
    expect(checkVin("1HGCM82O33A004352")).toMatchObject({ status: "invalid" });
    expect(checkVin("1HGCM826_3")).toMatchObject({ status: "invalid" });
    expect(checkVin("1HGCM82633A0043521")).toMatchObject({ status: "invalid" });
  });
});

describe("cleanVin", () => {
  it("upper-cases and strips separators", () => {
    expect(cleanVin("1hg cm-826")).toBe("1HGCM826");
  });
});
