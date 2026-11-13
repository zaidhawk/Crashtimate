"""Request and response bodies of the HTTP API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.merge import DetectedDamage
from app.pricing.models import DamageInput, Estimate
from app.schemas import DamageReport
from app.vehicles import BodySize, VehicleTier

MAX_DAMAGES = 50
MAX_DESCRIPTION_LENGTH = 300

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class AnalysisMeta(BaseModel):
    detector: str
    model: str | None
    image_sha256: str
    image_width: int
    image_height: int
    elapsed_ms: int
    cached: bool = Field(description="True if this exact photo was analysed before.")


class AnalyzeResponse(BaseModel):
    report: DamageReport
    meta: AnalysisMeta


class EstimateResponse(BaseModel):
    photos: list[AnalyzeResponse] = Field(description="One analysis per uploaded photo.")
    damages: list[DetectedDamage] = Field(description="Damage from every photo, combined.")
    summary: str
    estimate: Estimate | None = Field(
        description="Null when none of the photos is a usable photo of a vehicle."
    )


class VehicleOptions(BaseModel):
    """What the client knows about the vehicle. The VIN wins when it can be decoded."""

    vin: str | None = None
    postal_code: str | None = None
    vehicle_size: BodySize | None = None
    vehicle_tier: VehicleTier | None = None


class PriceRequest(VehicleOptions):
    damages: list[DamageInput] = Field(max_length=MAX_DAMAGES)


class EditedDamage(DetectedDamage):
    description: str = Field(max_length=MAX_DESCRIPTION_LENGTH)


class ShareRequest(VehicleOptions):
    photos: list[Sha256] = Field(
        max_length=10, description="image_sha256 of each analysed photo, in display order."
    )
    damages: list[EditedDamage] = Field(max_length=MAX_DAMAGES)

    @model_validator(mode="after")
    def _damage_points_at_a_photo(self) -> "ShareRequest":
        if any(damage.photo >= max(len(self.photos), 1) for damage in self.damages):
            raise ValueError("A damage refers to a photo that isn't in the list.")
        return self


class SharedPhoto(BaseModel):
    width: int
    height: int


class SharedEstimateBody(BaseModel):
    """What gets stored for a saved estimate: a snapshot, so later price changes don't alter it."""

    photos: list[SharedPhoto]
    damages: list[DetectedDamage]
    summary: str
    estimate: Estimate


class SharedEstimate(SharedEstimateBody):
    id: str
    created_at: datetime
