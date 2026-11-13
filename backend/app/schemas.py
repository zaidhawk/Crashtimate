"""Data shapes shared by the detectors and the API.

DamageReport doubles as the structured-output schema sent to the vision model, so the
field descriptions below are instructions the model reads.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Panel(StrEnum):
    """Exterior parts we can price. Left/right are the vehicle's own (driver's) left/right."""

    FRONT_BUMPER = "front_bumper"
    REAR_BUMPER = "rear_bumper"
    GRILLE = "grille"
    HOOD = "hood"
    ROOF = "roof"
    TRUNK = "trunk"
    LEFT_FRONT_FENDER = "left_front_fender"
    RIGHT_FRONT_FENDER = "right_front_fender"
    LEFT_FRONT_DOOR = "left_front_door"
    RIGHT_FRONT_DOOR = "right_front_door"
    LEFT_REAR_DOOR = "left_rear_door"
    RIGHT_REAR_DOOR = "right_rear_door"
    LEFT_QUARTER_PANEL = "left_quarter_panel"
    RIGHT_QUARTER_PANEL = "right_quarter_panel"
    LEFT_ROCKER = "left_rocker"
    RIGHT_ROCKER = "right_rocker"
    LEFT_MIRROR = "left_mirror"
    RIGHT_MIRROR = "right_mirror"
    LEFT_HEADLIGHT = "left_headlight"
    RIGHT_HEADLIGHT = "right_headlight"
    LEFT_TAILLIGHT = "left_taillight"
    RIGHT_TAILLIGHT = "right_taillight"
    WINDSHIELD = "windshield"
    REAR_WINDOW = "rear_window"
    LEFT_SIDE_GLASS = "left_side_glass"
    RIGHT_SIDE_GLASS = "right_side_glass"
    LEFT_FRONT_WHEEL = "left_front_wheel"
    RIGHT_FRONT_WHEEL = "right_front_wheel"
    LEFT_REAR_WHEEL = "left_rear_wheel"
    RIGHT_REAR_WHEEL = "right_rear_wheel"


class DamageType(StrEnum):
    """Matches the six categories of the CarDD dataset so the eval set can score it directly."""

    DENT = "dent"
    SCRATCH = "scratch"
    CRACK = "crack"
    GLASS_SHATTER = "glass_shatter"
    LAMP_BROKEN = "lamp_broken"
    TIRE_FLAT = "tire_flat"


class Severity(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class ImageQuality(StrEnum):
    GOOD = "good"
    POOR = "poor"
    UNUSABLE = "unusable"


class ViewAngle(StrEnum):
    FRONT = "front"
    REAR = "rear"
    LEFT = "left"
    RIGHT = "right"
    FRONT_LEFT = "front_left"
    FRONT_RIGHT = "front_right"
    REAR_LEFT = "rear_left"
    REAR_RIGHT = "rear_right"
    CLOSE_UP = "close_up"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    """Damage location as fractions of the image size (0 = left/top edge, 1 = right/bottom)."""

    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _order_corners(self) -> "BoundingBox":
        # Models occasionally swap corners; fix it rather than rejecting the whole report.
        if self.x_min > self.x_max:
            self.x_min, self.x_max = self.x_max, self.x_min
        if self.y_min > self.y_max:
            self.y_min, self.y_max = self.y_max, self.y_min
        return self


class DamageItem(BaseModel):
    panel: Panel
    damage_type: DamageType
    severity: Severity
    description: str = Field(description="One short sentence describing the damage.")
    confidence: float = Field(
        ge=0, le=1, description="How sure you are this damage is real and correctly classified."
    )
    box: BoundingBox | None = Field(description="Where the damage is, or null if unclear.")


class DamageReport(BaseModel):
    is_vehicle: bool = Field(description="False if the photo does not show a vehicle.")
    image_quality: ImageQuality = Field(
        description="unusable if too dark, blurry or distant to assess damage."
    )
    view: ViewAngle = Field(description="Which side of the vehicle the photo shows.")
    damages: list[DamageItem] = Field(
        description="One entry per damaged panel per damage type. Empty if no visible damage."
    )
    summary: str = Field(
        description="Two or three sentences for the car owner, including any suspected hidden "
        "damage that cannot be confirmed from the photo."
    )
