import pytest

from app.pricing import DamageInput, build_estimate
from app.pricing.engine import DISCLAIMER, LOW_CONFIDENCE_REASON, WHEEL_NOTE
from app.pricing.models import CostRange, HoursRange, Operation
from app.schemas import DamageType, Panel, Severity
from app.vehicles import BodySize, DriverAssist, Vehicle, VehicleTier

DENT, SCRATCH = DamageType.DENT, DamageType.SCRATCH
MINOR, MODERATE, SEVERE = Severity.MINOR, Severity.MODERATE, Severity.SEVERE
REPLACE, REPAIR, REFINISH, BLEND = (
    Operation.REPLACE,
    Operation.REPAIR,
    Operation.REFINISH,
    Operation.BLEND,
)


@pytest.fixture
def price(cost_book):
    def _price(*damages, vehicle: Vehicle | None = None, notes=()):
        inputs = [
            DamageInput(panel=panel, damage_type=damage_type, severity=severity)
            for panel, damage_type, severity in damages
        ]
        return build_estimate(inputs, vehicle or Vehicle(), cost_book, notes)

    return _price


def operations(estimate):
    return [(line.panel, line.operation) for line in estimate.lines]


def line(estimate, panel, operation):
    (found,) = [
        item for item in estimate.lines if item.panel is panel and item.operation is operation
    ]
    return found


def assist(**features) -> DriverAssist:
    defaults = dict.fromkeys(DriverAssist.model_fields, False)
    return DriverAssist(**{**defaults, **features})


def test_small_dent_gets_paintless_repair(price):
    estimate = price((Panel.LEFT_FRONT_DOOR, DENT, MINOR))

    assert operations(estimate) == [(Panel.LEFT_FRONT_DOOR, Operation.PAINTLESS_REPAIR)]
    assert estimate.totals.subtotal == CostRange(low=125, high=300)
    assert estimate.totals.tax == CostRange(low=16, high=39)
    assert estimate.totals.total == CostRange(low=141, high=339)


def test_moderate_dent_is_repaired_repainted_and_blended(price):
    estimate = price((Panel.LEFT_FRONT_DOOR, DENT, MODERATE))

    assert operations(estimate) == [
        (Panel.LEFT_FRONT_DOOR, REPAIR),
        (Panel.LEFT_FRONT_DOOR, REFINISH),
        (Panel.LEFT_FRONT_FENDER, BLEND),
        (Panel.LEFT_REAR_DOOR, BLEND),
    ]
    repair = line(estimate, Panel.LEFT_FRONT_DOOR, REPAIR)
    assert repair.body_hours == HoursRange(low=1.5, high=3.0)
    # 1.5–3.0 h at $85–$105 labour plus $10–$15 shop materials per hour.
    assert repair.cost == CostRange(low=143, high=360)
    assert line(estimate, Panel.LEFT_FRONT_DOOR, REFINISH).refinish_hours == HoursRange(
        low=2.6, high=2.6
    )
    # Blends charge 50–100% of the neighbour's refinish time.
    assert line(estimate, Panel.LEFT_FRONT_FENDER, BLEND).refinish_hours == HoursRange(
        low=1.1, high=2.2
    )


def test_replaced_panel_gets_part_labour_paint_and_blends(price):
    estimate = price((Panel.LEFT_FRONT_FENDER, DENT, SEVERE))

    assert operations(estimate) == [
        (Panel.LEFT_FRONT_FENDER, REPLACE),
        (Panel.LEFT_FRONT_FENDER, REFINISH),
        (Panel.HOOD, BLEND),
        (Panel.LEFT_FRONT_DOOR, BLEND),
    ]
    replace = line(estimate, Panel.LEFT_FRONT_FENDER, REPLACE)
    assert replace.parts == CostRange(low=120, high=350)
    assert replace.body_hours == HoursRange(low=1.5, high=2.5)


def test_neighbouring_repaints_share_setup_and_are_not_blended(price):
    estimate = price(
        (Panel.LEFT_FRONT_FENDER, DENT, MODERATE), (Panel.LEFT_FRONT_DOOR, DENT, MODERATE)
    )

    # The door is bigger, so it's painted at full time; the fender gets 0.4 h off.
    assert line(estimate, Panel.LEFT_FRONT_DOOR, REFINISH).refinish_hours.low == 2.6
    assert line(estimate, Panel.LEFT_FRONT_FENDER, REFINISH).refinish_hours.low == 1.8
    blended = {item.panel for item in estimate.lines if item.operation is BLEND}
    assert blended == {Panel.HOOD, Panel.LEFT_REAR_DOOR}


def test_damage_on_one_panel_is_repaired_together(price):
    estimate = price(
        (Panel.LEFT_FRONT_DOOR, DENT, MODERATE), (Panel.LEFT_FRONT_DOOR, SCRATCH, MODERATE)
    )

    repair = line(estimate, Panel.LEFT_FRONT_DOOR, REPAIR)
    assert repair.body_hours == HoursRange(low=2.0, high=4.0)
    assert "moderate dent, moderate scratch" in repair.description
    assert len([item for item in estimate.lines if item.operation is REFINISH]) == 1


def test_small_dent_on_a_panel_being_repainted_is_fixed_in_the_same_repair(price):
    estimate = price(
        (Panel.LEFT_FRONT_DOOR, DENT, MINOR), (Panel.LEFT_FRONT_DOOR, SCRATCH, MODERATE)
    )

    assert Operation.PAINTLESS_REPAIR not in {item.operation for item in estimate.lines}
    assert line(estimate, Panel.LEFT_FRONT_DOOR, REPAIR).body_hours == HoursRange(low=1.0, high=2.0)


def test_replacement_absorbs_smaller_repairs_on_the_same_panel(price):
    estimate = price(
        (Panel.LEFT_FRONT_FENDER, DENT, SEVERE), (Panel.LEFT_FRONT_FENDER, SCRATCH, MODERATE)
    )

    fender_operations = {
        op for panel, op in operations(estimate) if panel is Panel.LEFT_FRONT_FENDER
    }
    assert fender_operations == {REPLACE, REFINISH}


def test_unpainted_bumper_repair_keeps_the_polish(price):
    estimate = price((Panel.FRONT_BUMPER, DENT, MINOR), (Panel.FRONT_BUMPER, SCRATCH, MINOR))

    assert operations(estimate) == [
        (Panel.FRONT_BUMPER, REPAIR),
        (Panel.FRONT_BUMPER, Operation.POLISH),
    ]


def test_tire_and_rim_are_separate_jobs(price):
    estimate = price(
        (Panel.LEFT_FRONT_WHEEL, DamageType.TIRE_FLAT, MODERATE),
        (Panel.LEFT_FRONT_WHEEL, SCRATCH, MINOR),
    )

    descriptions = [item.description for item in estimate.lines]
    assert descriptions == [
        "Replace the tire on the left front wheel",
        "Repair curb rash on the left front wheel",
    ]
    assert WHEEL_NOTE not in estimate.notes


def test_broken_wheel_is_replaced_and_suspension_flagged(price):
    estimate = price((Panel.LEFT_FRONT_WHEEL, DamageType.CRACK, SEVERE))

    assert line(estimate, Panel.LEFT_FRONT_WHEEL, REPLACE).parts == CostRange(low=200, high=800)
    assert WHEEL_NOTE in estimate.notes


def test_windshield_replacement_calibrates_a_known_lane_camera(price):
    vehicle = Vehicle(driver_assist=assist(lane_departure_warning=True))

    estimate = price((Panel.WINDSHIELD, DamageType.GLASS_SHATTER, SEVERE), vehicle=vehicle)

    assert operations(estimate) == [
        (Panel.WINDSHIELD, REPLACE),
        (Panel.WINDSHIELD, Operation.CALIBRATE),
    ]
    assert line(estimate, Panel.WINDSHIELD, REPLACE).sublet == CostRange(low=300, high=800)
    assert line(estimate, Panel.WINDSHIELD, Operation.CALIBRATE).sublet == CostRange(
        low=200, high=500
    )


def test_unknown_sensors_get_a_note_instead_of_a_charge(price):
    estimate = price((Panel.WINDSHIELD, DamageType.GLASS_SHATTER, SEVERE))

    assert Operation.CALIBRATE not in {item.operation for item in estimate.lines}
    assert any("calibrating" in note for note in estimate.notes)


def test_no_calibration_when_the_vehicle_has_no_sensors(price):
    estimate = price(
        (Panel.WINDSHIELD, DamageType.GLASS_SHATTER, SEVERE),
        vehicle=Vehicle(driver_assist=assist()),
    )

    assert Operation.CALIBRATE not in {item.operation for item in estimate.lines}
    assert not any("calibrating" in note for note in estimate.notes)


def test_one_radar_calibration_covers_bumper_and_grille(price):
    vehicle = Vehicle(driver_assist=assist(adaptive_cruise=True))

    estimate = price(
        (Panel.FRONT_BUMPER, DENT, SEVERE),
        (Panel.GRILLE, DamageType.CRACK, MODERATE),
        vehicle=vehicle,
    )

    calibrations = [item for item in estimate.lines if item.operation is Operation.CALIBRATE]
    assert [item.description for item in calibrations] == [
        "Calibrate the front radar after this repair"
    ]


def test_rear_bumper_repair_calibrates_blind_spot_radar(price):
    vehicle = Vehicle(driver_assist=assist(blind_spot_monitoring=True))

    estimate = price((Panel.REAR_BUMPER, SCRATCH, MODERATE), vehicle=vehicle)

    assert line(estimate, Panel.REAR_BUMPER, Operation.CALIBRATE)


def test_impossible_and_doubtful_damage_is_listed_but_not_priced(cost_book):
    damages = [
        DamageInput(panel=Panel.HOOD, damage_type=DamageType.TIRE_FLAT, severity=MINOR),
        DamageInput(panel=Panel.ROOF, damage_type=DENT, severity=MODERATE, confidence=0.3),
    ]

    estimate = build_estimate(damages, Vehicle(), cost_book)

    assert estimate.lines == []
    assert [item.panel for item in estimate.unpriced] == [Panel.HOOD, Panel.ROOF]
    assert "doesn't make sense" in estimate.unpriced[0].reason
    assert estimate.unpriced[1].reason == LOW_CONFIDENCE_REASON


def test_luxury_vehicles_use_luxury_rates_and_parts(price):
    vehicle = Vehicle(tier=VehicleTier.LUXURY)

    estimate = price(
        (Panel.LEFT_FRONT_FENDER, DENT, SEVERE),
        (Panel.LEFT_HEADLIGHT, DamageType.LAMP_BROKEN, SEVERE),
        vehicle=vehicle,
    )

    assert estimate.hourly_rates.body_labour == CostRange(low=100, high=135)
    assert line(estimate, Panel.LEFT_FRONT_FENDER, REPLACE).parts == CostRange(low=240, high=700)
    assert line(estimate, Panel.LEFT_HEADLIGHT, REPLACE).parts == CostRange(low=600, high=3600)


def test_bigger_vehicles_have_bigger_parts_and_more_paint(price):
    estimate = price((Panel.LEFT_FRONT_FENDER, DENT, SEVERE), vehicle=Vehicle(size=BodySize.SUV))

    assert line(estimate, Panel.LEFT_FRONT_FENDER, REPLACE).parts == CostRange(low=138, high=403)
    assert line(estimate, Panel.LEFT_FRONT_FENDER, REFINISH).refinish_hours.low == 2.5


def test_welded_panel_replacement_warns_about_hidden_damage(price):
    estimate = price((Panel.LEFT_QUARTER_PANEL, DENT, SEVERE))

    assert any("welding" in note for note in estimate.notes)


def test_totals_add_up(price):
    estimate = price(
        (Panel.LEFT_FRONT_FENDER, DENT, MODERATE),
        (Panel.FRONT_BUMPER, SCRATCH, MINOR),
        (Panel.LEFT_HEADLIGHT, DamageType.LAMP_BROKEN, SEVERE),
        (Panel.WINDSHIELD, DamageType.CRACK, MINOR),
    )
    totals = estimate.totals
    categories = [
        totals.body_labour,
        totals.shop_materials,
        totals.refinish_labour,
        totals.paint_materials,
        totals.parts,
        totals.sublet,
    ]

    for end in ("low", "high"):
        subtotal = getattr(totals.subtotal, end)
        assert subtotal == sum(getattr(cost, end) for cost in categories)
        assert getattr(totals.tax, end) == round(subtotal * 0.13)
        assert getattr(totals.total, end) == subtotal + getattr(totals.tax, end)
        # Lines are rounded one by one, so they can drift a dollar each from the subtotal.
        line_sum = sum(getattr(item.cost, end) for item in estimate.lines)
        assert abs(line_sum - subtotal) <= len(estimate.lines)


def test_no_damage_means_a_zero_estimate_with_notes(price):
    estimate = price(notes=["Priced as a typical car."])

    assert estimate.lines == []
    assert estimate.totals.total == CostRange(low=0, high=0)
    assert estimate.notes == ["Priced as a typical car.", DISCLAIMER]


@pytest.mark.parametrize("panel", list(Panel))
def test_every_combination_of_panel_and_damage_can_be_priced(price, panel):
    for damage_type in DamageType:
        for severity in Severity:
            estimate = price((panel, damage_type, severity))
            assert estimate.lines or estimate.unpriced
