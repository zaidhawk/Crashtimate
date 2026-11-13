"use client";

import { useRef, useState } from "react";

export const MAX_PHOTOS = 4;
const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

export interface PickedPhoto {
  file: File;
  /** Object URL for showing the photo before and after it's uploaded. */
  url: string;
}

interface Props {
  photos: PickedPhoto[];
  onChange: (photos: PickedPhoto[]) => void;
}

/** Drag-and-drop, file picker or phone camera, with thumbnails of what's been chosen. */
export function PhotoPicker({ photos, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function add(files: Iterable<File>) {
    const next = [...photos];
    let rejected: string | null = null;
    for (const file of files) {
      if (!ACCEPTED.includes(file.type)) {
        rejected = "Photos need to be JPEG, PNG or WebP.";
      } else if (file.size > MAX_BYTES) {
        rejected = `${file.name} is larger than 10 MB.`;
      } else if (next.length >= MAX_PHOTOS) {
        rejected = `You can add up to ${MAX_PHOTOS} photos.`;
      } else if (!next.some((p) => p.file.name === file.name && p.file.size === file.size)) {
        next.push({ file, url: URL.createObjectURL(file) });
      }
    }
    setProblem(rejected);
    onChange(next);
  }

  function remove(index: number) {
    URL.revokeObjectURL(photos[index].url);
    setProblem(null);
    onChange(photos.filter((_, i) => i !== index));
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          add(event.dataTransfer.files);
        }}
        className={`rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? "border-accent bg-accent-soft" : "border-stone-300 bg-surface"
        }`}
      >
        <svg
          className="mx-auto text-stone-400"
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.3l1-1.6A1 1 0 0 1 9.7 4h4.6a1 1 0 0 1 .9.4l1 1.6h1.3A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5z"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <circle cx="12" cy="12.5" r="3.25" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <p className="mt-3 font-medium">Drop photos of the damage here</p>
        <p className="mt-1 text-sm text-muted">
          Up to {MAX_PHOTOS} photos of the same vehicle. Different angles give a better estimate.
        </p>
        <button type="button" className="btn mt-4" onClick={() => input.current?.click()}>
          Choose photos or take one
        </button>
        {/* On phones this offers the camera as well as the photo library. */}
        <input
          ref={input}
          type="file"
          accept={ACCEPTED.join(",")}
          multiple
          className="sr-only"
          aria-label="Photos of the vehicle"
          onChange={(event) => {
            add(event.target.files ?? []);
            event.target.value = "";
          }}
        />
      </div>

      {problem && (
        <p role="alert" className="mt-2 text-sm text-severe">
          {problem}
        </p>
      )}

      {photos.length > 0 && (
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {photos.map((photo, index) => (
            <li
              key={photo.url}
              className="group relative aspect-4/3 overflow-hidden rounded-xl bg-stone-100"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={photo.url} alt={photo.file.name} className="h-full w-full object-cover" />
              <button
                type="button"
                aria-label={`Remove ${photo.file.name}`}
                onClick={() => remove(index)}
                className="absolute top-1.5 right-1.5 flex h-7 w-7 cursor-pointer items-center justify-center rounded-full bg-ink/75 text-white hover:bg-ink"
              >
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path
                    d="M3 3l10 10M13 3L3 13"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
