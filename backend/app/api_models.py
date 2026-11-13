"""Request and response bodies of the HTTP API."""

from pydantic import BaseModel, Field

from app.pricing.models import DamageInput, Estimate
from app.schemas import DamageReport


class AnalysisMeta(BaseModel):
    detector: str
    model: str | None
    image_sha256: str
    image_width: int
    image_height: int
    elapsed_ms: int


class AnalyzeResponse(BaseModel):
    report: DamageReport
    meta: AnalysisMeta


class EstimateResponse(BaseModel):
    report: DamageReport
    estimate: Estimate | None = Field(
        description="Null when the photo isn't a usable photo of a vehicle."
    )
    meta: AnalysisMeta


class PriceRequest(BaseModel):
    damages: list[DamageInput] = Field(max_length=50)
    vin: str | None = None
    postal_code: str | None = None
