import type {
  Estimate,
  EstimateResponse,
  PriceRequest,
  SharedEstimate,
  ShareRequest,
  Vehicle,
  VehicleOptions,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

/** A failed request, with a message that's fine to show to the user. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Pages rendered on the server may reach the API at a different address than browsers do,
// e.g. over Docker's internal network.
const SERVER_API_URL =
  typeof window === "undefined" ? process.env.API_URL_INTERNAL?.replace(/\/$/, "") : undefined;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${SERVER_API_URL ?? API_URL}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Couldn't reach the Crashtimate server. Check your connection.", null);
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

// FastAPI sends {"detail": "..."} for our errors and {"detail": [{msg, ...}]} for
// request-validation errors.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && typeof body.detail[0]?.msg === "string") {
      return body.detail[0].msg;
    }
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return `Something went wrong (error ${response.status}).`;
}

function json(body: unknown, signal?: AbortSignal): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  };
}

export function estimateFromPhotos(
  photos: File[],
  options: VehicleOptions,
): Promise<EstimateResponse> {
  const form = new FormData();
  for (const photo of photos) form.append("images", photo);
  if (options.vin.trim()) form.append("vin", options.vin.trim());
  if (options.postalCode.trim()) form.append("postal_code", options.postalCode.trim());
  form.append("vehicle_size", options.size);
  form.append("vehicle_tier", options.tier);
  return request("/api/estimate", { method: "POST", body: form });
}

export function priceDamages(body: PriceRequest, signal?: AbortSignal): Promise<Estimate> {
  return request("/api/price", json(body, signal));
}

export function lookUpVin(vin: string, signal?: AbortSignal): Promise<Vehicle> {
  return request(`/api/vehicles/${encodeURIComponent(vin)}`, { signal });
}

export function saveEstimate(body: ShareRequest): Promise<SharedEstimate> {
  return request("/api/shares", json(body));
}

export function getSharedEstimate(id: string): Promise<SharedEstimate> {
  return request(`/api/shares/${encodeURIComponent(id)}`, { cache: "no-store" });
}

export function sharedPhotoUrl(id: string, index: number): string {
  return `${API_URL}/api/shares/${encodeURIComponent(id)}/photos/${index}`;
}
