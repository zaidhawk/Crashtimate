"use client";

import { type FormEvent, type ReactNode, useRef, useState } from "react";

import { ApiError, estimateFromPhotos, priceDamages, saveEstimate } from "@/lib/api";
import { priceRequest, shareRequest } from "@/lib/estimate";
import type { Damage, Estimate, PhotoAnalysis, VehicleOptions } from "@/lib/types";

import { EstimateView } from "./EstimateView";
import { MAX_PHOTOS, type PickedPhoto, PhotoPicker } from "./PhotoPicker";
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
      <div className="space-y-4">
        {demo && (
          <p className="notice no-print border-line-strong bg-signal-soft text-ink">
            <span className="font-semibold">Demo mode.</span> The server isn&apos;t connected to a
            vision model, so this shows sample damage rather than an analysis of your photo. The
            pricing is real.
          </p>
        )}
        {error && (
          <p role="alert" className="notice notice-error">
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
                <button type="button" className="btn btn-on-dark" onClick={startOver}>
                  New estimate
                </button>
                <button type="button" className="btn btn-on-dark" onClick={() => window.print()}>
                  Print or save PDF
                </button>
                <button
                  type="button"
                  className="btn btn-signal"
                  onClick={save}
                  disabled={share.status === "saving" || repricing}
                >
                  {share.status === "saving" ? "Saving…" : "Get a shareable link"}
                </button>
              </>
            }
          >
            {share.status === "saved" && (
              <div className="panel no-print border-ink p-4">
                <p className="text-sm font-medium">
                  Saved. Anyone with this link can see the estimate and photos for 30 days.
                </p>
                <div className="mt-3 flex gap-2">
                  <input
                    readOnly
                    className="field font-mono text-xs"
                    value={share.url}
                    aria-label="Link to this estimate"
                    onFocus={(event) => event.target.select()}
                  />
                  <button
                    type="button"
                    className="btn btn-primary shrink-0"
                    onClick={() => copyLink(share.url)}
                  >
                    {share.copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>
            )}
            {share.status === "failed" && (
              <p role="alert" className="notice notice-error no-print">
                {share.message}
              </p>
            )}
            <section className="panel no-print">
              <div className="panel-head">
                <h2 className="panel-title">Vehicle</h2>
              </div>
              <div className="p-5">
                <VehicleFields
                  options={options}
                  onChange={changeOptions}
                  lookup={vinLookup}
                  onLookupChange={setVinLookup}
                />
              </div>
            </section>
          </EstimateView>
        ) : (
          <div className="panel mx-auto max-w-xl p-8 text-center">
            <h2 className="text-xl font-semibold tracking-tight">We couldn&apos;t assess that</h2>
            <p className="mt-2 text-sm text-muted">{result.summary}</p>
            <p className="mt-2 text-sm text-muted">
              Try a sharper, closer photo of the damaged area in good light.
            </p>
            <button type="button" className="btn btn-primary mt-6" onClick={startOver}>
              Try other photos
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:grid-rows-[auto_1fr] lg:gap-x-16 lg:gap-y-12">
      <div className="lg:col-start-1 lg:row-start-1 lg:pt-4">{intro}</div>

      <form
        onSubmit={submit}
        className="panel lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-start"
      >
        <section>
          <div className="panel-head">
            <h2 className="panel-title">
              <span className="mr-2 font-mono text-muted">01</span>Photos of the damage
            </h2>
            <span className="text-xs text-muted">
              {photos.length} of {MAX_PHOTOS}
            </span>
          </div>
          <div className="p-5">
            <PhotoPicker photos={photos} onChange={setPhotos} />
          </div>
        </section>

        <section className="border-t border-line">
          <div className="panel-head">
            <h2 className="panel-title">
              <span className="mr-2 font-mono text-muted">02</span>About the vehicle
            </h2>
          </div>
          <div className="p-5">
            <VehicleFields
              options={options}
              onChange={setOptions}
              lookup={vinLookup}
              onLookupChange={setVinLookup}
            />
          </div>
        </section>

        <div className="space-y-3 rounded-b-lg border-t border-line bg-paper/60 p-5">
          {error && (
            <p role="alert" className="notice notice-error">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="btn btn-primary h-12 w-full text-base"
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
          <p className="text-center text-xs text-muted" aria-live="polite">
            {analysing
              ? "This usually takes 10 to 30 seconds."
              : "Photos are resized and stripped of location data before analysis."}
          </p>
        </div>
      </form>

      {outro && <div className="lg:col-start-1 lg:row-start-2">{outro}</div>}
    </div>
  );
}
