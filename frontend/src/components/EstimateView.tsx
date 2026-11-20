"use client";

import { type ReactNode, useState } from "react";

import { DAMAGE_TYPE_LABELS, SEVERITY_LABELS, panelLabel } from "@/lib/labels";
import type { Damage, Estimate } from "@/lib/types";

import { DamageEditor } from "./DamageEditor";
import { EstimateHeadline, EstimateNotes, EstimateTable, EstimateTotals } from "./EstimateTable";
import { PhotoViewer, SEVERITY_DOT, type ViewerPhoto } from "./PhotoViewer";

interface Props {
  photos: ViewerPhoto[];
  damages: Damage[];
  summary: string;
  estimate: Estimate;
  /** Leave out to show the damage read-only, as on a saved estimate. */
  onDamagesChange?: (damages: Damage[]) => void;
  /** True while a corrected estimate is on its way, to dim the stale numbers. */
  updating?: boolean;
  /** Buttons shown beside the total. */
  actions?: ReactNode;
  /** Extra content above the damage list, e.g. the vehicle fields. */
  children?: ReactNode;
}

/** The results layout, shared by a fresh estimate and a saved one. */
export function EstimateView({
  photos,
  damages,
  summary,
  estimate,
  onDamagesChange,
  updating = false,
  actions,
  children,
}: Props) {
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const stale = updating ? "opacity-50 transition-opacity" : "transition-opacity";

  return (
    <div className="space-y-4">
      <div className="print-plain flex flex-col gap-6 rounded-lg bg-ink p-6 text-white sm:p-8 xl:flex-row xl:items-end xl:justify-between">
        <div className={stale} aria-busy={updating}>
          <EstimateHeadline estimate={estimate} />
        </div>
        {actions && <div className="no-print flex flex-wrap gap-2">{actions}</div>}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {photos.length > 0 && (
            <section className="panel overflow-hidden">
              <div className="bg-paper/60 p-3">
                <PhotoViewer
                  photos={photos}
                  damages={damages}
                  highlighted={highlighted}
                  onHighlight={setHighlighted}
                />
              </div>
              {summary && (
                <p className="border-t border-line px-5 py-4 text-sm leading-relaxed">{summary}</p>
              )}
            </section>
          )}

          {children}

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Damage</h2>
              <span className="text-xs text-muted tabular-nums">
                {damages.length} {damages.length === 1 ? "item" : "items"}
              </span>
            </div>
            <div className="p-5">
              {onDamagesChange ? (
                <>
                  <p className="mb-4 text-sm text-muted">
                    Something wrong or missing? Fix it here and the price updates.
                  </p>
                  <DamageEditor
                    damages={damages}
                    onChange={onDamagesChange}
                    highlighted={highlighted}
                    onHighlight={setHighlighted}
                  />
                </>
              ) : (
                <DamageList
                  damages={damages}
                  highlighted={highlighted}
                  onHighlight={setHighlighted}
                />
              )}
            </div>
          </section>
        </div>

        <div className={`space-y-4 ${stale}`}>
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Itemized estimate</h2>
              <span className="text-xs text-muted">By panel</span>
            </div>
            <div className="p-5">
              <EstimateTable estimate={estimate} />
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Totals</h2>
            </div>
            <div className="p-5">
              <EstimateTotals estimate={estimate} />
            </div>
          </section>
          <EstimateNotes estimate={estimate} />
        </div>
      </div>
    </div>
  );
}

function DamageList({
  damages,
  highlighted,
  onHighlight,
}: {
  damages: Damage[];
  highlighted: number | null;
  onHighlight: (index: number | null) => void;
}) {
  if (damages.length === 0) {
    return <p className="text-sm text-muted">No damage was listed.</p>;
  }
  return (
    <ul className="space-y-2">
      {damages.map((damage, index) => (
        <li
          key={index}
          onMouseEnter={() => onHighlight(index)}
          onMouseLeave={() => onHighlight(null)}
          className={`flex items-start gap-3 rounded-md border p-3 transition-colors ${
            highlighted === index ? "border-ink bg-signal-soft" : "border-line"
          }`}
        >
          <span
            className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded font-mono text-xs font-medium text-white ${SEVERITY_DOT[damage.severity]}`}
          >
            {index + 1}
          </span>
          <div className="text-sm">
            <p className="font-medium">
              {panelLabel(damage.panel)} · {SEVERITY_LABELS[damage.severity]}{" "}
              {DAMAGE_TYPE_LABELS[damage.damage_type].toLowerCase()}
            </p>
            <p className="mt-0.5 text-muted">{damage.description}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
