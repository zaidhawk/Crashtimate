"""Check estimates against published repair prices.

Many numbers in the cost book are assumptions (see docs/cost-data.md). These tests price
common repairs and check that the middle of each estimate falls inside a price range
published for that repair. US prices are converted at 1.38 CAD per USD. Estimates are
compared before tax.
"""

import pytest

from app.pricing import DamageInput, build_estimate
from app.schemas import DamageType, Panel, Severity
from app.vehicles import DriverAssist, Vehicle, VehicleTier

USD = 1.38

LANE_CAMERA = DriverAssist(
    adaptive_cruise=False,
    lane_departure_warning=True,
    lane_keep_assist=True,
    blind_spot_monitoring=False,
)

SCENARIOS = [
    pytest.param(
        [(Panel.LEFT_FRONT_DOOR, DamageType.DENT, Severity.MINOR)],
        Vehicle(),
        (75, 300),
        # experts.ca, May 2026: paintless dent repair runs $75–$300 per dent in Canada.
        id="door ding, paintless repair",
    ),
    pytest.param(
        [(Panel.WINDSHIELD, DamageType.GLASS_SHATTER, Severity.SEVERE)],
        Vehicle(driver_assist=LANE_CAMERA),
        (500, 1400),
        # Auto Glass Dixie (Ontario): $300–$600 glass plus $200–$400 calibration.
        # isure.ca: $900–$1,400 or more for a windshield with driver-assist sensors.
        id="windshield with lane camera",
    ),
    pytest.param(
        [(Panel.LEFT_HEADLIGHT, DamageType.LAMP_BROKEN, Severity.SEVERE)],
        Vehicle(),
        (300 * USD, 1000 * USD),
        # Synchrony, Sep 2025 (US): most assemblies cost several hundred dollars and labour
        # starts at $100 an hour; LED units run $600 to nearly $3,000.
        id="mainstream headlight",
    ),
    pytest.param(
        [(Panel.LEFT_HEADLIGHT, DamageType.LAMP_BROKEN, Severity.SEVERE)],
        Vehicle(tier=VehicleTier.LUXURY),
        (2000, 3700),
        # Collision Repair Magazine: Ontario drivers quoted $2,000 for a headlight, over
        # $3,500 for a Mercedes headlight and $7,400 for a pair on a Tesla Model S.
        id="luxury headlight",
    ),
    pytest.param(
        [(Panel.FRONT_BUMPER, DamageType.CRACK, Severity.SEVERE)],
        Vehicle(),
        (800 * USD, 2500 * USD),
        # Northwest Auto Collision, Dec 2025 (US): a full bumper replacement with paint
        # and labour runs $800 to $2,500 or more.
        id="front bumper replacement",
    ),
]


@pytest.mark.parametrize(("damages", "vehicle", "published"), SCENARIOS)
def test_estimate_lands_inside_published_range(cost_book, damages, vehicle, published):
    inputs = [
        DamageInput(panel=panel, damage_type=damage_type, severity=severity)
        for panel, damage_type, severity in damages
    ]
    subtotal = build_estimate(inputs, vehicle, cost_book).totals.subtotal
    published_low, published_high = published

    midpoint = (subtotal.low + subtotal.high) / 2
    assert published_low <= midpoint <= published_high, (
        f"estimate ${subtotal.low}–${subtotal.high} (middle ${midpoint:.0f}) vs "
        f"published ${published_low:.0f}–${published_high:.0f}"
    )
