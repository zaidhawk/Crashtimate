"use client";

export function PrintButton() {
  return (
    <button type="button" className="btn btn-on-dark" onClick={() => window.print()}>
      Print or save PDF
    </button>
  );
}
