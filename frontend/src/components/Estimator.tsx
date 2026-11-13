"use client";

import { type FormEvent, type ReactNode, useRef, useState } from "react";

import { ApiError, estimateFromPhotos, priceDamages, saveEstimate } from "@/lib/api";
import { priceRequest, shareRequest } from "@/lib/estimate";
import type { Damage, Estimate, PhotoAnalysis, VehicleOptions } from "@/lib/types";

import { EstimateView } from "./EstimateView";
import { type PickedPhoto, PhotoPicker } from "./PhotoPicker";
import type { ViewerPhoto } from "./PhotoViewer";
import { VehicleFields, type VinLookup, vehicleOptionsProblem } from "./VehicleFields";

// Wait for the user to stop clicking before asking for a new price.
const REPRICE_DELAY_MS = 300;

const NO_VEHICLE: VehicleOptions = { vin: "", postalCode: "", size: "car", tier: "standard" };

interface Result {
  photos: PhotoAnalysis[];
  damages: Damage[];
  summary: string;
  estimate: Estimate | null;
}

type Share =
  | { status: "none" }
  | { status: "saving" }
  | { status: "saved"; url: string; copied: boolean }
  | { status: "failed"; message: string };

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Try again.";
}

function photoProblem(analysis: PhotoAnalysis): string | undefined {
  if (!analysis.report.is_vehicle) return "This doesn't look like a photo of a vehicle.";
  switch (analysis.report.image_quality) {
    case "unusable":
      return "Too dark, blurry or far away to assess.";
    case "poor":
      return "Low photo quality: some damage may have been missed.";
    default:
      return undefined;
  }
}

/** The whole flow: pick photos, wait for the analysis, then review and correct the estimate. */
export function Estimator({ intro, outro }: { intro?: ReactNode; outro?: ReactNode }) {
  const [photos, setPhotos] = useState<PickedPhoto[]>([]);
  const [options, setOptions] = useState<VehicleOptions>(NO_VEHICLE);
  const [vinLookup, setVinLookup] = useState<VinLookup>({ status: "idle" });
  const [analysing, setAnalysing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [repricing, setRepricing] = useState(false);
  const [share, setShare] = useState<Share>({ status: "none" });

  const repriceTimer = useRef<number | undefined>(undefined);
  const repriceRequest = useRef<AbortController | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problem = vehicleOptionsProblem(options);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setAnalysing(true);
    try {
      const response = await estimateFromPhotos(
        photos.map((photo) => photo.file),
        options,
      );
      setResult(response);
      window.scrollTo({ top: 0 });
    } catch (caught) {
      setError(message(caught));
    } finally {
      setAnalysing(false);
    }
  }

  /** Ask the server to price the current damage again. The photo isn't analysed again. */
  function reprice(damages: Damage[], vehicle: VehicleOptions) {
    window.clearTimeout(repriceTimer.current);
    repriceRequest.current?.abort();
    setShare({ status: "none" });
    if (vehicleOptionsProblem(vehicle)) {
      // Mid-edit, e.g. a half-typed VIN. Price again once it's complete.
      setRepricing(false);
      return;
    }
    setRepricing(true);
    repriceTimer.current = window.setTimeout(async () => {
      const controller = new AbortController();
      repriceRequest.current = controller;
      try {
        const estimate = await priceDamages(priceRequest(damages, vehicle), controller.signal);
        setResult((current) => current && { ...current, estimate });
        setError(null);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(message(caught));
      }
      if (!controller.signal.aborted) setRepricing(false);
    }, REPRICE_DELAY_MS);
  }

  function changeDamages(damages: Damage[]) {
    setResult((current) => current && { ...current, damages });
    reprice(damages, options);
  }

  function changeOptions(next: VehicleOptions) {
    setOptions(next);
    if (result?.estimate) reprice(result.damages, next);
  }

  async function save() {
    if (!result) return;
    setShare({ status: "saving" });
    try {
      const hashes = result.photos.map((photo) => photo.meta.image_sha256);
      const saved = await saveEstimate(shareRequest(hashes, result.damages, options));
      const url = `${window.location.origin}/e/${saved.id}`;
      setShare({ status: "saved", url, copied: false });
    } catch (caught) {
      setShare({ status: "failed", message: message(caught) });
    }
  }

  async function copyLink(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setShare({ status: "saved", url, copied: true });
    } catch {
      // Clipboard access can be blocked; the link is on screen to copy by hand.
    }
  }

  function startOver() {
    window.clearTimeout(repriceTimer.current);
    repriceRequest.current?.abort();
    for (const photo of photos) URL.revokeObjectURL(photo.url);
    setPhotos([]);
    setResult(null);
    setError(null);
    setRepricing(false);
    setShare({ status: "none" });
  }

  if (result) {
    const viewerPhotos: ViewerPhoto[] = result.photos.map((analysis, index) => ({
      src: photos[index]?.url ?? "",
      problem: photoProblem(analysis),
    }));
    const demo = result.photos.some((photo) => photo.meta.detector === "mock");

    return (
      <div className="space-y-6">
        {demo && (
          <p className="no-print rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            <span className="font-semibold">Demo mode.</span> The server isn&apos;t connected to a
            vision model, so this shows sample damage rather than an analysis of your photo. The
            pricing is real.
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            {error}
          </p>
        )}

        {result.estimate ? (
          <EstimateView
            photos={viewerPhotos}
            damages={result.damages}
            summary={result.summary}
            estimate={result.estimate}
            onDamagesChange={changeDamages}
            updating={repricing}
            actions={
              <>
                <button type="button" className="btn" onClick={startOver}>
                  New estimate
                </button>
                <button type="button" className="btn" onClick={() => window.print()}>
                  Print or save PDF
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={save}
                  disabled={share.status === "saving" || repricing}
                >
                  {share.status === "saving" ? "Saving…" : "Get a shareable link"}
                </button>
              </>
            }
          >
            {share.status === "saved" && (
              <div className="card no-print border-emerald-200 bg-emerald-50 p-4">
                <p className="text-sm font-medium text-emerald-900">
                  Saved. Anyone with this link can see the estimate and photos for 30 days.
                </p>
                <div className="mt-2 flex gap-2">
                  <input
                    readOnly
                    className="field font-mono text-xs"
                    value={share.url}
                    aria-label="Link to this estimate"
                    onFocus={(event) => event.target.select()}
                  />
                  <button
                    type="button"
                    className="btn shrink-0"
                    onClick={() => copyLink(share.url)}
                  >
                    {share.copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>
            )}
            {share.status === "failed" && (
              <p
                role="alert"
                className="no-print rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              >
                {share.message}
              </p>
            )}
            <div className="card no-print p-5">
              <h2 className="mb-4 text-lg font-semibold">Vehicle</h2>
              <VehicleFields
                options={options}
                onChange={changeOptions}
                lookup={vinLookup}
                onLookupChange={setVinLookup}
              />
            </div>
          </EstimateView>
        ) : (
          <div className="card mx-auto max-w-xl p-6 text-center">
            <h2 className="text-xl font-semibold">We couldn&apos;t assess that</h2>
            <p className="mt-2 text-sm text-muted">{result.summary}</p>
            <p className="mt-2 text-sm text-muted">
              Try a sharper, closer photo of the damaged area in good light.
            </p>
            <button type="button" className="btn btn-primary mt-5" onClick={startOver}>
              Try other photos
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {intro}
      <form onSubmit={submit} className="mx-auto max-w-2xl space-y-6">
        <PhotoPicker photos={photos} onChange={setPhotos} />

        <div className="card p-5">
          <h2 className="mb-4 text-lg font-semibold">About the vehicle</h2>
          <VehicleFields
            options={options}
            onChange={setOptions}
            lookup={vinLookup}
            onLookupChange={setVinLookup}
          />
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          className="btn btn-primary w-full py-3 text-base"
          disabled={photos.length === 0 || analysing}
        >
          {analysing && (
            <svg
              className="animate-spin"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                cx="12"
                cy="12"
                r="9"
                stroke="currentColor"
                strokeOpacity="0.3"
                strokeWidth="3"
              />
              <path
                d="M21 12a9 9 0 0 0-9-9"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
          )}
          {analysing
            ? `Analysing ${photos.length === 1 ? "your photo" : `${photos.length} photos`}…`
            : "Get my estimate"}
        </button>
        {analysing && (
          <p className="text-center text-sm text-muted" aria-live="polite">
            This usually takes 10 to 30 seconds.
          </p>
        )}
      </form>
      {outro}
    </div>
  );
}
