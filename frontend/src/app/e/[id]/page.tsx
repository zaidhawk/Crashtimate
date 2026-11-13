import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { EstimateView } from "@/components/EstimateView";
import { PrintButton } from "@/components/PrintButton";
import { ApiError, getSharedEstimate, sharedPhotoUrl } from "@/lib/api";
import { formatCost, formatDate } from "@/lib/format";

// The page and its metadata both need the estimate; cache() makes that one request.
const loadEstimate = cache(async (id: string) => {
  try {
    return await getSharedEstimate(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export async function generateMetadata({ params }: PageProps<"/e/[id]">): Promise<Metadata> {
  const { id } = await params;
  const saved = await loadEstimate(id);
  if (!saved) return { title: "Estimate not found" };
  return {
    title: `Repair estimate: ${formatCost(saved.estimate.totals.total)}`,
    description: saved.summary,
    // Saved estimates are private to whoever has the link.
    robots: { index: false },
  };
}

export default async function SharedEstimatePage({ params }: PageProps<"/e/[id]">) {
  const { id } = await params;
  const saved = await loadEstimate(id);
  if (!saved) notFound();

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">Saved estimate from {formatDate(saved.created_at)}</p>
      <EstimateView
        photos={saved.photos.map((_, index) => ({ src: sharedPhotoUrl(id, index) }))}
        damages={saved.damages}
        summary={saved.summary}
        estimate={saved.estimate}
        actions={
          <>
            <PrintButton />
            <Link href="/" className="btn btn-primary">
              Estimate your own
            </Link>
          </>
        }
      />
    </div>
  );
}
