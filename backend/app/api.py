import asyncio
import math
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api_models import (
    AnalysisMeta,
    AnalyzeResponse,
    EstimateResponse,
    PriceRequest,
    SharedEstimate,
    SharedEstimateBody,
    SharedPhoto,
    ShareRequest,
)
from app.config import Settings
from app.detectors import DamageDetector, Detection, DetectionError
from app.images import InvalidImageError, PreparedImage, prepare_image
from app.limits import RateLimiter, client_ip
from app.merge import is_usable, merge_damages, merge_summaries
from app.pricing import CostBook, DamageInput, Estimate, build_estimate
from app.regions import InvalidPostalCodeError, province_for_postal_code
from app.schemas import DamageReport
from app.store import Store
from app.vehicles import (
    BodySize,
    InvalidVinError,
    Vehicle,
    VehicleTier,
    VinDecoder,
    VinLookupError,
    VinNotFoundError,
    normalize_vin,
)

router = APIRouter(prefix="/api")

_SIZE_LABELS = {BodySize.CAR: "car", BodySize.SUV: "SUV", BodySize.TRUCK: "truck"}


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_detector(request: Request) -> DamageDetector:
    return request.app.state.detector


def get_vin_decoder(request: Request) -> VinDecoder:
    return request.app.state.vin_decoder


def get_cost_book(request: Request) -> CostBook:
    return request.app.state.cost_book


def get_store(request: Request) -> Store:
    return request.app.state.store


def rate_limited(limiter_name: str) -> Callable[[Request], None]:
    """A dependency that turns away visitors who have used up one of the app's rate limits."""

    def check(request: Request) -> None:
        limiter: RateLimiter = getattr(request.app.state, limiter_name)
        settings: Settings = request.app.state.settings
        wait = limiter.retry_after(client_ip(request, settings.proxy_hops))
        if wait is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "You've made a lot of requests. Try again in a little while.",
                headers={"Retry-After": str(math.ceil(wait))},
            )

    return check


SettingsDep = Annotated[Settings, Depends(get_settings)]
DetectorDep = Annotated[DamageDetector, Depends(get_detector)]
VinDecoderDep = Annotated[VinDecoder, Depends(get_vin_decoder)]
CostBookDep = Annotated[CostBook, Depends(get_cost_book)]
StoreDep = Annotated[Store, Depends(get_store)]
ImageUpload = Annotated[UploadFile, File(description="Photo of the vehicle: JPEG, PNG or WebP.")]
AnalysisLimit = Depends(rate_limited("analysis_limiter"))
ShareLimit = Depends(rate_limited("share_limiter"))


@router.get("/health")
async def health(detector: DetectorDep) -> dict[str, str]:
    return {"status": "ok", "detector": detector.name}


@router.post("/analyze", dependencies=[AnalysisLimit])
async def analyze(
    image: ImageUpload, settings: SettingsDep, detector: DetectorDep, store: StoreDep
) -> AnalyzeResponse:
    """Detect visible damage in one photo of a vehicle."""
    prepared = await _read_image(image, settings)
    return await _analyze(prepared, detector, store, settings)


@router.post("/estimate", dependencies=[AnalysisLimit])
async def estimate(
    images: Annotated[
        list[UploadFile],
        File(description="One or more photos of the same vehicle: JPEG, PNG or WebP."),
    ],
    settings: SettingsDep,
    detector: DetectorDep,
    vin_decoder: VinDecoderDep,
    cost_book: CostBookDep,
    store: StoreDep,
    vin: Annotated[str | None, Form()] = None,
    postal_code: Annotated[str | None, Form()] = None,
    vehicle_size: Annotated[BodySize | None, Form()] = None,
    vehicle_tier: Annotated[VehicleTier | None, Form()] = None,
) -> EstimateResponse:
    """Detect damage in photos of one vehicle and price the repairs."""
    # Check the cheap inputs before paying for the photo analysis.
    vin = _parse_vin(vin)
    region_notes = _region_notes(postal_code, cost_book)
    if len(images) > settings.max_photos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Upload at most {settings.max_photos} photos at a time.",
        )
    prepared = [await _read_image(image, settings) for image in images]

    *photos, (vehicle, vehicle_notes) = await asyncio.gather(
        *(_analyze(image, detector, store, settings) for image in prepared),
        _lookup_vehicle(vin_decoder, vin, vehicle_size, vehicle_tier),
    )
    reports = [photo.report for photo in photos]
    damages = merge_damages(reports)

    priced = None
    if any(is_usable(report) for report in reports):
        priced = build_estimate(
            [DamageInput(**damage.model_dump(include=_PRICED_FIELDS)) for damage in damages],
            vehicle,
            cost_book,
            notes=[*region_notes, *vehicle_notes],
        )
    return EstimateResponse(
        photos=photos, damages=damages, summary=merge_summaries(reports), estimate=priced
    )


@router.post("/price")
async def price(
    request: PriceRequest, vin_decoder: VinDecoderDep, cost_book: CostBookDep
) -> Estimate:
    """Price a list of damage without a photo, e.g. after the user corrects the detector."""
    vin = _parse_vin(request.vin)
    region_notes = _region_notes(request.postal_code, cost_book)
    vehicle, vehicle_notes = await _lookup_vehicle(
        vin_decoder, vin, request.vehicle_size, request.vehicle_tier
    )
    return build_estimate(
        request.damages, vehicle, cost_book, notes=[*region_notes, *vehicle_notes]
    )


@router.get("/vehicles/{vin}")
async def decode_vin(vin: str, vin_decoder: VinDecoderDep) -> Vehicle:
    """Look up a vehicle by VIN."""
    try:
        return await vin_decoder.decode(_parse_vin(vin))
    except VinNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except VinLookupError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/shares", status_code=status.HTTP_201_CREATED, dependencies=[ShareLimit])
async def create_share(
    request: ShareRequest, vin_decoder: VinDecoderDep, cost_book: CostBookDep, store: StoreDep
) -> SharedEstimate:
    """Save an estimate so it can be opened again from a link.

    The client sends the damage (possibly corrected by the user), not prices. The server
    prices it again, so a saved estimate always shows numbers this app calculated.
    """
    vin = _parse_vin(request.vin)
    region_notes = _region_notes(request.postal_code, cost_book)

    photos: list[SharedPhoto] = []
    reports: list[DamageReport] = []
    for sha256 in request.photos:
        photo = store.get_photo(sha256)
        analysis = store.latest_analysis(sha256)
        if photo is None or analysis is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "One of the photos is no longer stored. Upload it again to save the estimate.",
            )
        photos.append(SharedPhoto(width=photo.width, height=photo.height))
        reports.append(DamageReport.model_validate_json(analysis.report))

    vehicle, vehicle_notes = await _lookup_vehicle(
        vin_decoder, vin, request.vehicle_size, request.vehicle_tier
    )
    body = SharedEstimateBody(
        photos=photos,
        damages=request.damages,
        summary=merge_summaries(reports),
        estimate=build_estimate(
            [
                DamageInput(**damage.model_dump(include=_PRICED_FIELDS))
                for damage in request.damages
            ],
            vehicle,
            cost_book,
            notes=[*region_notes, *vehicle_notes],
        ),
    )
    saved = store.create_share(body.model_dump_json(), request.photos)
    return SharedEstimate(id=saved.id, created_at=saved.created_at, **body.model_dump())


@router.get("/shares/{share_id}")
async def get_share(share_id: str, store: StoreDep) -> SharedEstimate:
    saved = store.get_share(share_id)
    if saved is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "That estimate doesn't exist or has expired."
        )
    body = SharedEstimateBody.model_validate_json(saved.payload)
    return SharedEstimate(id=saved.id, created_at=saved.created_at, **body.model_dump())


@router.get("/shares/{share_id}/photos/{position}", response_class=Response)
async def get_share_photo(share_id: str, position: int, store: StoreDep) -> Response:
    photo = store.get_share_photo(share_id, position)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That photo doesn't exist or has expired.")
    return Response(
        photo.data,
        media_type="image/jpeg",
        # A saved estimate's photos never change, so browsers can keep them.
        headers={"Cache-Control": "private, max-age=86400, immutable"},
    )


_PRICED_FIELDS = set(DamageInput.model_fields)


async def _read_image(image: UploadFile, settings: Settings) -> PreparedImage:
    limit = int(settings.max_upload_mb * 1024 * 1024)
    raw = await image.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"The image is larger than {settings.max_upload_mb:g} MB.",
        )
    try:
        # Decoding and resizing a large photo takes long enough to hold up other requests.
        return await asyncio.to_thread(prepare_image, raw, settings.max_image_edge)
    except InvalidImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc


async def _analyze(
    image: PreparedImage, detector: DamageDetector, store: Store, settings: Settings
) -> AnalyzeResponse:
    """Run the detector on a photo, or reuse the stored result if it has seen this photo."""
    started = time.perf_counter()
    cached = store.get_analysis(image.sha256, detector.cache_key)
    if cached is not None:
        report, model = DamageReport.model_validate_json(cached.report), cached.model
    else:
        if not store.reserve_analysis(settings.daily_analysis_limit):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Crashtimate has reached its daily limit for photo analysis. Try again tomorrow.",
            )
        detection = await _detect(detector, image)
        report, model = detection.report, detection.model
        store.save_photo(image.sha256, image.data, image.width, image.height)
        store.save_analysis(image.sha256, detector.cache_key, report.model_dump_json(), model)

    return AnalyzeResponse(
        report=report,
        meta=AnalysisMeta(
            detector=detector.name,
            model=model,
            image_sha256=image.sha256,
            image_width=image.width,
            image_height=image.height,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            cached=cached is not None,
        ),
    )


async def _detect(detector: DamageDetector, image: PreparedImage) -> Detection:
    try:
        return await detector.detect(image)
    except DetectionError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, str(exc)) from exc


def _parse_vin(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    try:
        return normalize_vin(raw)
    except InvalidVinError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _region_notes(postal_code: str | None, cost_book: CostBook) -> list[str]:
    if postal_code is None or not postal_code.strip():
        return []
    try:
        province = province_for_postal_code(postal_code)
    except InvalidPostalCodeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if province == cost_book.region:
        return []
    return [f"Labour rates come from {cost_book.region} shops, so prices in {province} may differ."]


async def _lookup_vehicle(
    vin_decoder: VinDecoder,
    vin: str | None,
    size: BodySize | None = None,
    tier: VehicleTier | None = None,
) -> tuple[Vehicle, list[str]]:
    """Find the vehicle, falling back to a typical one so a failed lookup never blocks a price.

    Without a VIN that decodes, the size and tier the user picked are used instead.
    """
    typical = Vehicle(vin=vin, size=size or BodySize.CAR, tier=tier or VehicleTier.STANDARD)
    luxury = "luxury " if typical.tier is VehicleTier.LUXURY else ""
    kind = f"a typical {luxury}{_SIZE_LABELS[typical.size]}"
    if vin is None:
        return typical, [f"Priced as {kind}. Add the VIN for pricing specific to your vehicle."]
    try:
        return await vin_decoder.decode(vin), []
    except VinNotFoundError:
        return typical, [f"We couldn't find that VIN, so this is priced as {kind}."]
    except VinLookupError:
        return typical, [f"The VIN lookup service didn't respond, so this is priced as {kind}."]
