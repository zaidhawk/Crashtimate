import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api_models import AnalysisMeta, AnalyzeResponse, EstimateResponse, PriceRequest
from app.config import Settings
from app.detectors import DamageDetector, Detection, DetectionError
from app.images import InvalidImageError, PreparedImage, prepare_image
from app.pricing import CostBook, DamageInput, Estimate, build_estimate
from app.regions import InvalidPostalCodeError, province_for_postal_code
from app.schemas import ImageQuality
from app.vehicles import (
    InvalidVinError,
    Vehicle,
    VinDecoder,
    VinLookupError,
    VinNotFoundError,
    normalize_vin,
)

router = APIRouter(prefix="/api")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_detector(request: Request) -> DamageDetector:
    return request.app.state.detector


def get_vin_decoder(request: Request) -> VinDecoder:
    return request.app.state.vin_decoder


def get_cost_book(request: Request) -> CostBook:
    return request.app.state.cost_book


SettingsDep = Annotated[Settings, Depends(get_settings)]
DetectorDep = Annotated[DamageDetector, Depends(get_detector)]
VinDecoderDep = Annotated[VinDecoder, Depends(get_vin_decoder)]
CostBookDep = Annotated[CostBook, Depends(get_cost_book)]
ImageUpload = Annotated[UploadFile, File(description="Photo of the vehicle: JPEG, PNG or WebP.")]


@router.get("/health")
async def health(detector: DetectorDep) -> dict[str, str]:
    return {"status": "ok", "detector": detector.name}


@router.post("/analyze")
async def analyze(
    image: ImageUpload, settings: SettingsDep, detector: DetectorDep
) -> AnalyzeResponse:
    """Detect visible damage in one photo of a vehicle."""
    prepared = await _read_image(image, settings)
    started = time.perf_counter()
    detection = await _detect(detector, prepared)
    return AnalyzeResponse(
        report=detection.report, meta=_meta(detector, detection, prepared, started)
    )


@router.post("/estimate")
async def estimate(
    image: ImageUpload,
    settings: SettingsDep,
    detector: DetectorDep,
    vin_decoder: VinDecoderDep,
    cost_book: CostBookDep,
    vin: Annotated[str | None, Form()] = None,
    postal_code: Annotated[str | None, Form()] = None,
) -> EstimateResponse:
    """Detect damage in a photo and price the repairs."""
    # Check the cheap inputs before paying for the photo analysis.
    vin = _parse_vin(vin)
    region_notes = _region_notes(postal_code, cost_book)
    prepared = await _read_image(image, settings)

    started = time.perf_counter()
    detection, (vehicle, vehicle_notes) = await asyncio.gather(
        _detect(detector, prepared), _lookup_vehicle(vin_decoder, vin)
    )
    meta = _meta(detector, detection, prepared, started)

    report = detection.report
    if not report.is_vehicle or report.image_quality is ImageQuality.UNUSABLE:
        return EstimateResponse(report=report, estimate=None, meta=meta)

    damages = [
        DamageInput(
            panel=item.panel,
            damage_type=item.damage_type,
            severity=item.severity,
            confidence=item.confidence,
        )
        for item in report.damages
    ]
    priced = build_estimate(damages, vehicle, cost_book, notes=[*region_notes, *vehicle_notes])
    return EstimateResponse(report=report, estimate=priced, meta=meta)


@router.post("/price")
async def price(
    request: PriceRequest, vin_decoder: VinDecoderDep, cost_book: CostBookDep
) -> Estimate:
    """Price a list of damage without a photo, e.g. after the user corrects the detector."""
    vin = _parse_vin(request.vin)
    region_notes = _region_notes(request.postal_code, cost_book)
    vehicle, vehicle_notes = await _lookup_vehicle(vin_decoder, vin)
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


async def _read_image(image: UploadFile, settings: Settings) -> PreparedImage:
    limit = int(settings.max_upload_mb * 1024 * 1024)
    raw = await image.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"The image is larger than {settings.max_upload_mb:g} MB.",
        )
    try:
        return prepare_image(raw, settings.max_image_edge)
    except InvalidImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc


async def _detect(detector: DamageDetector, image: PreparedImage) -> Detection:
    try:
        return await detector.detect(image)
    except DetectionError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, str(exc)) from exc


def _meta(
    detector: DamageDetector, detection: Detection, image: PreparedImage, started: float
) -> AnalysisMeta:
    return AnalysisMeta(
        detector=detector.name,
        model=detection.model,
        image_sha256=image.sha256,
        image_width=image.width,
        image_height=image.height,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )


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


async def _lookup_vehicle(vin_decoder: VinDecoder, vin: str | None) -> tuple[Vehicle, list[str]]:
    """Find the vehicle, falling back to a typical car so a failed lookup never blocks a price."""
    if vin is None:
        return Vehicle(), ["Priced as a typical car. Add the VIN for pricing specific to your car."]
    try:
        return await vin_decoder.decode(vin), []
    except VinNotFoundError:
        return Vehicle(vin=vin), ["We couldn't find that VIN, so this is priced as a typical car."]
    except VinLookupError:
        return Vehicle(vin=vin), [
            "The VIN lookup service didn't respond, so this is priced as a typical car."
        ]
