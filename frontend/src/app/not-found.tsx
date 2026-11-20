import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel mx-auto max-w-xl p-8 text-center">
      <h1 className="text-xl font-semibold tracking-tight">Nothing here</h1>
      <p className="mt-2 text-sm text-muted">
        That page or estimate doesn&apos;t exist. Saved estimates are deleted after 30 days.
      </p>
      <Link href="/" className="btn btn-primary mt-6">
        Start a new estimate
      </Link>
    </div>
  );
}
