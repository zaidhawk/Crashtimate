"use client";

import { useState } from "react";

import { DAMAGE_TYPE_LABELS, panelLabel } from "@/lib/labels";
import type { Damage, Severity } from "@/lib/types";

export interface ViewerPhoto {
  src: string;
  /** Why the photo couldn't be used, if it couldn't. */
  problem?: string;
}

const BOX_COLORS: Record<Severity, string> = {
  minor: "border-minor bg-minor/10",
  moderate: "border-moderate bg-moderate/10",
  severe: "border-severe bg-severe/10",
};

export const SEVERITY_DOT: Record<Severity, string> = {
  minor: "bg-minor",
  moderate: "bg-moderate",
  severe: "bg-severe",
};

interface Props {
  photos: ViewerPhoto[];
  damages: Damage[];
  /** Index into `damages` of the damage to emphasise, e.g. while its row is hovered. */
  highlighted: number | null;
  onHighlight: (index: number | null) => void;
}

/** The uploaded photos with a numbered box over each piece of damage. */
export function PhotoViewer({ photos, damages, highlighted, onHighlight }: Props) {
  const [selected, setSelected] = useState(0);
  // Follow the highlighted damage to the photo that shows it.
  const highlightedPhoto = highlighted === null ? undefined : damages[highlighted]?.photo;
  const current = Math.min(highlightedPhoto ?? selected, photos.length - 1);
  const photo = photos[current];
  if (!photo) return null;

  return (
    <div>
      <div className="relative mx-auto w-fit overflow-hidden rounded-xl bg-stone-100">
        {/* A plain <img>: the source is a local preview or the API, so there's nothing for
            next/image to optimise, and the overlay needs the image's exact rendered box. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={photo.src}
          alt={`Photo ${current + 1} of the vehicle`}
          className="block max-h-[70vh] w-auto max-w-full"
        />
        {damages.map((damage, index) =>
          damage.photo === current && damage.box ? (
            <button
              key={index}
              type="button"
              aria-label={`${index + 1}: ${DAMAGE_TYPE_LABELS[damage.damage_type]} on the ${panelLabel(damage.panel).toLowerCase()}`}
              onMouseEnter={() => onHighlight(index)}
              onMouseLeave={() => onHighlight(null)}
              onFocus={() => onHighlight(index)}
              onBlur={() => onHighlight(null)}
              className={`absolute rounded-md border-2 transition-shadow ${BOX_COLORS[damage.severity]} ${
                highlighted === index ? "z-10 shadow-[0_0_0_3px_rgb(255_255_255/0.9)]" : ""
              }`}
              style={{
                left: `${damage.box.x_min * 100}%`,
                top: `${damage.box.y_min * 100}%`,
                width: `${(damage.box.x_max - damage.box.x_min) * 100}%`,
                height: `${(damage.box.y_max - damage.box.y_min) * 100}%`,
              }}
            >
              <span
                className={`absolute -top-px -left-px rounded-br-md rounded-tl-sm px-1.5 py-0.5 text-xs leading-none font-semibold text-white ${SEVERITY_DOT[damage.severity]}`}
              >
                {index + 1}
              </span>
            </button>
          ) : null,
        )}
        {photo.problem && (
          <p className="absolute inset-x-0 bottom-0 bg-ink/80 px-3 py-2 text-sm text-white">
            {photo.problem}
          </p>
        )}
      </div>

      {photos.length > 1 && (
        <div className="no-print mt-3 flex justify-center gap-2">
          {photos.map((thumb, index) => (
            <button
              key={thumb.src}
              type="button"
              onClick={() => setSelected(index)}
              aria-label={`Show photo ${index + 1}`}
              aria-pressed={index === current}
              className={`h-14 w-20 cursor-pointer overflow-hidden rounded-lg border-2 ${
                index === current
                  ? "border-accent"
                  : "border-transparent opacity-70 hover:opacity-100"
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={thumb.src} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
