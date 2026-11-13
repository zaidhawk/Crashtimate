"use client";

export default function SharedEstimateError({ reset }: { reset: () => void }) {
  return (
    <div className="card mx-auto max-w-xl p-6 text-center">
      <h1 className="text-xl font-semibold">We couldn&apos;t load that estimate</h1>
      <p className="mt-2 text-sm text-muted">
        The server didn&apos;t respond. Give it another try.
      </p>
      <button type="button" className="btn btn-primary mt-5" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
