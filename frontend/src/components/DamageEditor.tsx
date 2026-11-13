"use client";

import { newDamage } from "@/lib/estimate";
import {
  DAMAGE_TYPE_LABELS,
  DAMAGE_TYPES,
  PANEL_OPTIONS,
  SEVERITIES,
  SEVERITY_HINTS,
  SEVERITY_LABELS,
  panelLabel,
} from "@/lib/labels";
import type { Damage, DamageType, Panel, Severity } from "@/lib/types";

import { SEVERITY_DOT } from "./PhotoViewer";

// Matches the backend: damage it's less sure about than this isn't priced.
const MIN_CONFIDENCE = 0.5;

interface Props {
  damages: Damage[];
  onChange: (damages: Damage[]) => void;
  highlighted: number | null;
  onHighlight: (index: number | null) => void;
}

/** The detected damage, which the user can correct, remove or add to. */
export function DamageEditor({ damages, onChange, highlighted, onHighlight }: Props) {
  function update(index: number, changes: Partial<Damage>) {
    onChange(damages.map((damage, i) => (i === index ? { ...damage, ...changes } : damage)));
  }

  return (
    <div>
      {damages.length === 0 && (
        <p className="text-sm text-muted">
          No damage listed. Add any damage you can see and it will be priced.
        </p>
      )}
      <ul className="space-y-3">
        {damages.map((damage, index) => (
          <li
            key={index}
            onMouseEnter={() => onHighlight(index)}
            onMouseLeave={() => onHighlight(null)}
            className={`rounded-xl border p-3 transition-colors ${
              highlighted === index ? "border-accent bg-accent-soft" : "border-line"
            }`}
          >
            <div className="flex items-start gap-3">
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold text-white ${SEVERITY_DOT[damage.severity]}`}
              >
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">{damage.description}</p>
                {damage.confidence < MIN_CONFIDENCE ? (
                  <p className="mt-1 text-xs text-amber-800">
                    The analysis wasn&apos;t sure about this one, so it isn&apos;t priced.{" "}
                    <button
                      type="button"
                      className="cursor-pointer font-medium underline"
                      onClick={() => update(index, { confidence: 1 })}
                    >
                      It&apos;s real, price it
                    </button>
                  </p>
                ) : (
                  damage.confidence < 1 && (
                    <p className="mt-1 text-xs text-muted">
                      {Math.round(damage.confidence * 100)}% confident
                    </p>
                  )
                )}
              </div>
              <button
                type="button"
                aria-label={`Remove damage ${index + 1}`}
                title="Remove"
                onClick={() => onChange(damages.filter((_, i) => i !== index))}
                className="no-print -mt-1 -mr-1 cursor-pointer rounded-md p-1.5 text-muted hover:bg-stone-100 hover:text-severe"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path
                    d="M4 4l8 8M12 4l-8 8"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2">
              <select
                aria-label={`Panel for damage ${index + 1}`}
                className="field"
                value={damage.panel}
                onChange={(event) => update(index, { panel: event.target.value as Panel })}
              >
                {PANEL_OPTIONS.map(({ group, panels }) => (
                  <optgroup key={group} label={group}>
                    {panels.map((panel) => (
                      <option key={panel} value={panel}>
                        {panelLabel(panel)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <select
                aria-label={`Type of damage ${index + 1}`}
                className="field"
                value={damage.damage_type}
                onChange={(event) =>
                  update(index, { damage_type: event.target.value as DamageType })
                }
              >
                {DAMAGE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {DAMAGE_TYPE_LABELS[type]}
                  </option>
                ))}
              </select>
            </div>

            <div
              role="radiogroup"
              aria-label={`Severity of damage ${index + 1}`}
              className="mt-2 grid grid-cols-3 gap-1 rounded-lg bg-stone-100 p-1"
            >
              {SEVERITIES.map((severity: Severity) => (
                <button
                  key={severity}
                  type="button"
                  role="radio"
                  aria-checked={damage.severity === severity}
                  title={SEVERITY_HINTS[severity]}
                  onClick={() => update(index, { severity })}
                  className={`cursor-pointer rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                    damage.severity === severity
                      ? "bg-surface text-ink shadow-sm"
                      : "text-muted hover:text-ink"
                  }`}
                >
                  {SEVERITY_LABELS[severity]}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="btn no-print mt-3 w-full"
        onClick={() => onChange([...damages, newDamage()])}
      >
        + Add damage
      </button>
    </div>
  );
}
