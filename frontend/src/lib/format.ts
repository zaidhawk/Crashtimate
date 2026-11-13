import type { CostRange, HoursRange, Vehicle } from "./types";

const dollars = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
  currencyDisplay: "narrowSymbol",
  maximumFractionDigits: 0,
});

export function formatMoney(amount: number): string {
  return dollars.format(amount);
}

/** "$1,246 – $3,562", or just "$125" when both ends are the same. */
export function formatCost(range: CostRange): string {
  if (range.low === range.high) return formatMoney(range.low);
  return `${formatMoney(range.low)} – ${formatMoney(range.high)}`;
}

/** "1.5 – 3.0 h" */
export function formatHours(range: HoursRange): string {
  if (range.low === range.high) return `${range.low.toFixed(1)} h`;
  return `${range.low.toFixed(1)} – ${range.high.toFixed(1)} h`;
}

/** "2019 Honda Civic" from NHTSA's upper-case make. Null when nothing is known. */
export function vehicleName(vehicle: Vehicle): string | null {
  const make = vehicle.make ? titleCase(vehicle.make) : null;
  const parts = [vehicle.year, make, vehicle.model].filter(Boolean);
  return parts.length > 0 ? parts.join(" ") : null;
}

// NHTSA sends makes in capitals. Short ones are usually initials (BMW, GMC), so they stay.
function titleCase(text: string): string {
  return text
    .split(/([\s-]+)/)
    .map((word) => (word.length <= 3 ? word : word.charAt(0) + word.slice(1).toLowerCase()))
    .join("");
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "long" }).format(new Date(iso));
}
