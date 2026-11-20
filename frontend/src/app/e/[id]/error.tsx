"use client";

export default function SharedEstimateError({ reset }: { reset: () => void }) {
  return (
    <div className="panel mx-auto max-w-xl p-8 text-center">
      <h1 className="text-xl font-semibold tracking-tight">We couldn&apos;t load that estimate</h1>
      <p className="mt-2 text-sm text-muted">
        The server didn&apos;t respond. Give it another try.
      </p>
      <button type="button" className="btn btn-primary mt-6" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
