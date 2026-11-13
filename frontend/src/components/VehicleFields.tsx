"use client";

import { useRef } from "react";

import { ApiError, lookUpVin } from "@/lib/api";
import { vehicleName } from "@/lib/format";
import { BODY_SIZE_LABELS, BODY_SIZES } from "@/lib/labels";
import type { BodySize, VehicleOptions } from "@/lib/types";
import { checkVin, cleanVin } from "@/lib/vin";

/** Where the lookup of the typed VIN stands. Kept by the parent so it survives a re-mount. */
export type VinLookup =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "found"; name: string }
  | { status: "problem"; message: string };

interface Props {
  options: VehicleOptions;
  onChange: (options: VehicleOptions) => void;
  lookup: VinLookup;
  onLookupChange: (lookup: VinLookup) => void;
}

const POSTAL_CODE = /^[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d$/;

/** VIN (looked up as it's typed), or the vehicle type when there's no VIN, and postal code. */
export function VehicleFields({ options, onChange, lookup, onLookupChange: setLookup }: Props) {
  const pending = useRef<AbortController | null>(null);

  const vinCheck = checkVin(options.vin);
  const postalCode = options.postalCode.trim();
  const postalCodeLooksWrong = postalCode.length >= 6 && !POSTAL_CODE.test(postalCode);

  function changeVin(raw: string) {
    const vin = cleanVin(raw).slice(0, 17);
    onChange({ ...options, vin });

    pending.current?.abort();
    const check = checkVin(vin);
    if (check.status !== "valid") {
      setLookup({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setLookup({ status: "loading" });
    lookUpVin(check.vin, controller.signal)
      .then((vehicle) => {
        setLookup({ status: "found", name: vehicleName(vehicle) ?? "Vehicle found" });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        // A failed lookup doesn't block anything: the estimate falls back to the type below.
        const message =
          error instanceof ApiError && error.status === 404
            ? "We couldn't find that VIN. The vehicle type below will be used."
            : "The VIN lookup isn't responding. The vehicle type below will be used.";
        setLookup({ status: "problem", message });
      });
  }

  const vinDecoded = lookup.status === "found";

  return (
    <div className="space-y-4">
      <div>
        <label className="label" htmlFor="vin">
          VIN <span className="font-normal text-muted">(optional)</span>
        </label>
        <input
          id="vin"
          className="field font-mono uppercase placeholder:font-sans placeholder:normal-case"
          placeholder="17 characters, on the dashboard or driver's door"
          autoComplete="off"
          spellCheck={false}
          value={options.vin}
          onChange={(event) => changeVin(event.target.value)}
          aria-describedby="vin-status"
        />
        <p id="vin-status" className="hint" aria-live="polite">
          {vinCheck.status === "empty" &&
            "Prices parts and labour for your exact vehicle, and checks for sensors that need calibrating."}
          {vinCheck.status === "incomplete" && `${vinCheck.length} of 17 characters`}
          {vinCheck.status === "invalid" && <span className="text-severe">{vinCheck.message}</span>}
          {vinCheck.status === "valid" && lookup.status === "loading" && "Looking it up…"}
          {vinCheck.status === "valid" && lookup.status === "found" && (
            <span className="font-medium text-emerald-700">✓ {lookup.name}</span>
          )}
          {vinCheck.status === "valid" && lookup.status === "problem" && (
            <span className="text-amber-800">{lookup.message}</span>
          )}
        </p>
      </div>

      {!vinDecoded && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="vehicle-size">
              Vehicle type
            </label>
            <select
              id="vehicle-size"
              className="field"
              value={options.size}
              onChange={(event) => onChange({ ...options, size: event.target.value as BodySize })}
            >
              {BODY_SIZES.map((size) => (
                <option key={size} value={size}>
                  {BODY_SIZE_LABELS[size]}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2.5 self-end pb-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 accent-accent"
              checked={options.tier === "luxury"}
              onChange={(event) =>
                onChange({ ...options, tier: event.target.checked ? "luxury" : "standard" })
              }
            />
            Luxury brand (BMW, Lexus, Tesla…)
          </label>
        </div>
      )}

      <div>
        <label className="label" htmlFor="postal-code">
          Postal code <span className="font-normal text-muted">(optional)</span>
        </label>
        <input
          id="postal-code"
          className="field uppercase placeholder:normal-case sm:max-w-40"
          placeholder="M5V 2T6"
          autoComplete="postal-code"
          maxLength={7}
          value={options.postalCode}
          onChange={(event) => onChange({ ...options, postalCode: event.target.value })}
        />
        {postalCodeLooksWrong && (
          <p className="hint text-severe">Enter a Canadian postal code, like M5V 2T6.</p>
        )}
      </div>
    </div>
  );
}

/** Whether the form can be submitted: a half-typed VIN or postal code would be rejected. */
export function vehicleOptionsProblem(options: VehicleOptions): string | null {
  const vin = checkVin(options.vin);
  if (vin.status === "incomplete") return "Finish the VIN or clear it.";
  if (vin.status === "invalid") return vin.message;
  const postalCode = options.postalCode.trim();
  if (postalCode && !POSTAL_CODE.test(postalCode)) {
    return "Enter a Canadian postal code, like M5V 2T6, or clear it.";
  }
  return null;
}
