import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.config import Settings
from app.detectors import DamageDetector, DetectionError
from app.images import InvalidImageError, prepare_image
from app.schemas import AnalysisMeta, AnalyzeResponse

router = APIRouter(prefix="/api")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_detector(request: Request) -> DamageDetector:
    return request.app.state.detector


SettingsDep = Annotated[Settings, Depends(get_settings)]
DetectorDep = Annotated[DamageDetector, Depends(get_detector)]


@router.get("/health")
async def health(detector: DetectorDep) -> dict[str, str]:
    return {"status": "ok", "detector": detector.name}


@router.post("/analyze")
async def analyze(
    image: Annotated[UploadFile, File(description="Photo of the vehicle: JPEG, PNG or WebP.")],
    settings: SettingsDep,
    detector: DetectorDep,
) -> AnalyzeResponse:
    """Detect visible damage in one photo of a vehicle."""
    limit = int(settings.max_upload_mb * 1024 * 1024)
    raw = await image.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"The image is larger than {settings.max_upload_mb:g} MB.",
        )

    try:
        prepared = prepare_image(raw, settings.max_image_edge)
    except InvalidImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    started = time.perf_counter()
    try:
        detection = await detector.detect(prepared)
    except DetectionError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, str(exc)) from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    return AnalyzeResponse(
        report=detection.report,
        meta=AnalysisMeta(
            detector=detector.name,
            model=detection.model,
            image_sha256=prepared.sha256,
            image_width=prepared.width,
            image_height=prepared.height,
            elapsed_ms=elapsed_ms,
        ),
    )
