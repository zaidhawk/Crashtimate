from app.detectors.base import Detection
from app.images import PreparedImage
from app.schemas import (
    BoundingBox,
    DamageItem,
    DamageReport,
    DamageType,
    ImageQuality,
    Panel,
    Severity,
    ViewAngle,
)

SAMPLE_REPORT = DamageReport(
    is_vehicle=True,
    image_quality=ImageQuality.GOOD,
    view=ViewAngle.FRONT_LEFT,
    damages=[
        DamageItem(
            panel=Panel.LEFT_FRONT_FENDER,
            damage_type=DamageType.DENT,
            severity=Severity.MODERATE,
            description="Creased dent above the wheel arch, about the size of a hand.",
            confidence=0.9,
            box=BoundingBox(x_min=0.52, y_min=0.38, x_max=0.71, y_max=0.6),
        ),
        DamageItem(
            panel=Panel.FRONT_BUMPER,
            damage_type=DamageType.SCRATCH,
            severity=Severity.MINOR,
            description="Light scuffing on the left corner of the bumper cover.",
            confidence=0.75,
            box=BoundingBox(x_min=0.18, y_min=0.62, x_max=0.4, y_max=0.78),
        ),
        DamageItem(
            panel=Panel.LEFT_HEADLIGHT,
            damage_type=DamageType.LAMP_BROKEN,
            severity=Severity.SEVERE,
            description="Headlight lens is cracked through and partly missing.",
            confidence=0.85,
            box=BoundingBox(x_min=0.3, y_min=0.44, x_max=0.47, y_max=0.56),
        ),
    ],
    summary=(
        "The front left corner took a moderate impact: the fender is dented, the headlight "
        "is broken and the bumper is scuffed. The headlight mounts and fender liner may also "
        "be damaged, which a shop would confirm in person."
    ),
)


class MockDamageDetector:
    """Returns the same sample report for every photo. Used in tests and frontend work."""

    name = "mock"

    async def detect(self, image: PreparedImage) -> Detection:
        return Detection(report=SAMPLE_REPORT, model=None)

    async def aclose(self) -> None:
        pass
