// Mirrors the backend's VIN check so obvious typos are caught without a request.

const VALUES: Record<string, number> = {
  A: 1,
  B: 2,
  C: 3,
  D: 4,
  E: 5,
  F: 6,
  G: 7,
  H: 8,
  J: 1,
  K: 2,
  L: 3,
  M: 4,
  N: 5,
  P: 7,
  R: 9,
  S: 2,
  T: 3,
  U: 4,
  V: 5,
  W: 6,
  X: 7,
  Y: 8,
  Z: 9,
};
const WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2];

export type VinCheck =
  | { status: "empty" }
  | { status: "incomplete"; length: number }
  | { status: "invalid"; message: string }
  | { status: "valid"; vin: string };

export function cleanVin(raw: string): string {
  return raw.replace(/[\s-]/g, "").toUpperCase();
}

export function checkVin(raw: string): VinCheck {
  const vin = cleanVin(raw);
  if (vin.length === 0) return { status: "empty" };
  if (/[IOQ]/.test(vin)) {
    return { status: "invalid", message: "VINs never use the letters I, O or Q." };
  }
  if (/[^A-Z0-9]/.test(vin)) {
    return { status: "invalid", message: "A VIN only has letters and numbers." };
  }
  if (vin.length < 17) return { status: "incomplete", length: vin.length };
  if (vin.length > 17) {
    return { status: "invalid", message: "A VIN is 17 characters long." };
  }
  if (vin[8] !== checkDigit(vin)) {
    return { status: "invalid", message: "That VIN doesn't add up. Check it for typos." };
  }
  return { status: "valid", vin };
}

// Position 9 is computed from the other 16 characters.
function checkDigit(vin: string): string {
  let total = 0;
  for (let i = 0; i < 17; i++) {
    const char = vin[i];
    const value = char >= "0" && char <= "9" ? Number(char) : VALUES[char];
    total += value * WEIGHTS[i];
  }
  const remainder = total % 11;
  return remainder === 10 ? "X" : String(remainder);
}
