import type { BodySize, DamageType, Operation, Panel, Severity } from "./types";

// Record<Panel, ...> makes the build fail if the API gains a panel this list doesn't have.
const PANEL_GROUPS: Record<Panel, string> = {
  front_bumper: "Front",
  grille: "Front",
  hood: "Front",
  left_headlight: "Front",
  right_headlight: "Front",
  windshield: "Front",
  left_front_fender: "Left side",
  left_front_door: "Left side",
  left_rear_door: "Left side",
  left_quarter_panel: "Left side",
  left_rocker: "Left side",
  left_mirror: "Left side",
  left_side_glass: "Left side",
  right_front_fender: "Right side",
  right_front_door: "Right side",
  right_rear_door: "Right side",
  right_quarter_panel: "Right side",
  right_rocker: "Right side",
  right_mirror: "Right side",
  right_side_glass: "Right side",
  rear_bumper: "Rear",
  trunk: "Rear",
  left_taillight: "Rear",
  right_taillight: "Rear",
  rear_window: "Rear",
  roof: "Top",
  left_front_wheel: "Wheels",
  right_front_wheel: "Wheels",
  left_rear_wheel: "Wheels",
  right_rear_wheel: "Wheels",
};

export const PANELS = Object.keys(PANEL_GROUPS) as Panel[];

/** Panels grouped by where they are on the vehicle, for the panel picker. */
export const PANEL_OPTIONS: { group: string; panels: Panel[] }[] = [
  ...new Set(Object.values(PANEL_GROUPS)),
].map((group) => ({
  group,
  panels: PANELS.filter((panel) => PANEL_GROUPS[panel] === group),
}));

export const DAMAGE_TYPE_LABELS: Record<DamageType, string> = {
  dent: "Dent",
  scratch: "Scratch",
  crack: "Crack",
  glass_shatter: "Shattered glass",
  lamp_broken: "Broken lamp",
  tire_flat: "Flat tire",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  minor: "Minor",
  moderate: "Moderate",
  severe: "Severe",
};

export const SEVERITY_HINTS: Record<Severity, string> = {
  minor: "Cosmetic: light scratches, small dings",
  moderate: "Needs body work and repainting",
  severe: "The part likely needs replacing",
};

export const OPERATION_LABELS: Record<Operation, string> = {
  replace: "Replace",
  repair: "Repair",
  paintless_repair: "Paintless repair",
  polish: "Polish",
  refinish: "Refinish",
  blend: "Blend",
  calibrate: "Calibrate",
};

export const BODY_SIZE_LABELS: Record<BodySize, string> = {
  car: "Car",
  suv: "SUV or minivan",
  truck: "Pickup or van",
};

export const DAMAGE_TYPES = Object.keys(DAMAGE_TYPE_LABELS) as DamageType[];
export const SEVERITIES = Object.keys(SEVERITY_LABELS) as Severity[];
export const BODY_SIZES = Object.keys(BODY_SIZE_LABELS) as BodySize[];

/** "left_front_fender" → "Left front fender" */
export function panelLabel(panel: Panel): string {
  const words = panel.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
