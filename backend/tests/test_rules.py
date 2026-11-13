import pytest

from app.pricing.costbook import PanelCategory
from app.pricing.rules import Sublet, Unpriced, Work, WorkKind, plan_work
from app.schemas import DamageType, Panel, Severity

BODY, BUMPER, LAMP, GLASS, WHEEL, MIRROR, GRILLE = (
    PanelCategory.BODY,
    PanelCategory.BUMPER,
    PanelCategory.LAMP,
    PanelCategory.GLASS,
    PanelCategory.WHEEL,
    PanelCategory.MIRROR,
    PanelCategory.GRILLE,
)
DENT, SCRATCH, CRACK = DamageType.DENT, DamageType.SCRATCH, DamageType.CRACK
MINOR, MODERATE, SEVERE = Severity.MINOR, Severity.MODERATE, Severity.SEVERE


@pytest.mark.parametrize(
    ("panel", "category", "damage_type", "severity", "expected"),
    [
        (Panel.HOOD, BODY, SCRATCH, MINOR, Work(WorkKind.POLISH)),
        (Panel.HOOD, BODY, SCRATCH, MODERATE, Work(WorkKind.REPAIR, MINOR, refinish=True)),
        (Panel.HOOD, BODY, SCRATCH, SEVERE, Work(WorkKind.REPAIR, MODERATE, refinish=True)),
        (Panel.HOOD, BODY, DENT, MINOR, Work(WorkKind.PAINTLESS_REPAIR)),
        (Panel.HOOD, BODY, DENT, MODERATE, Work(WorkKind.REPAIR, MODERATE, refinish=True)),
        (Panel.HOOD, BODY, DENT, SEVERE, Work(WorkKind.REPLACE)),
        (Panel.HOOD, BODY, CRACK, MINOR, Work(WorkKind.REPAIR, MINOR, refinish=True)),
        (Panel.FRONT_BUMPER, BUMPER, DENT, MINOR, Work(WorkKind.REPAIR, MINOR)),
        (Panel.FRONT_BUMPER, BUMPER, CRACK, SEVERE, Work(WorkKind.REPLACE)),
        (
            Panel.LEFT_HEADLIGHT,
            LAMP,
            SCRATCH,
            MINOR,
            Work(WorkKind.POLISH, sublet=Sublet.LENS_RESTORATION),
        ),
        (Panel.LEFT_HEADLIGHT, LAMP, DENT, MINOR, Work(WorkKind.REPLACE)),
        (
            Panel.WINDSHIELD,
            GLASS,
            CRACK,
            MINOR,
            Work(WorkKind.REPAIR, sublet=Sublet.WINDSHIELD_CHIP_REPAIR),
        ),
        (Panel.LEFT_SIDE_GLASS, GLASS, CRACK, MINOR, Work(WorkKind.REPLACE)),
        (
            Panel.LEFT_MIRROR,
            MIRROR,
            DamageType.GLASS_SHATTER,
            SEVERE,
            Work(WorkKind.REPAIR, sublet=Sublet.MIRROR_GLASS),
        ),
        (Panel.GRILLE, GRILLE, DENT, MINOR, Work(WorkKind.REPLACE)),
        (
            Panel.LEFT_FRONT_WHEEL,
            WHEEL,
            DamageType.TIRE_FLAT,
            MINOR,
            Work(WorkKind.REPAIR, sublet=Sublet.TIRE_REPAIR, component="tire"),
        ),
        (
            Panel.LEFT_FRONT_WHEEL,
            WHEEL,
            DENT,
            MODERATE,
            Work(WorkKind.REPAIR, sublet=Sublet.WHEEL_STRAIGHTEN),
        ),
        (Panel.LEFT_FRONT_WHEEL, WHEEL, CRACK, MINOR, Work(WorkKind.REPLACE)),
    ],
)
def test_work_for_damage(panel, category, damage_type, severity, expected):
    assert plan_work(panel, category, damage_type, severity) == expected


@pytest.mark.parametrize(
    ("panel", "category", "damage_type"),
    [
        (Panel.HOOD, BODY, DamageType.TIRE_FLAT),
        (Panel.WINDSHIELD, GLASS, DENT),
        (Panel.GRILLE, GRILLE, DamageType.GLASS_SHATTER),
        (Panel.LEFT_FRONT_WHEEL, WHEEL, DamageType.LAMP_BROKEN),
    ],
)
def test_impossible_damage_is_not_priced(panel, category, damage_type):
    result = plan_work(panel, category, damage_type, MODERATE)

    assert isinstance(result, Unpriced)
    assert "doesn't make sense" in result.reason


def test_light_scratches_on_glass_are_left_alone():
    result = plan_work(Panel.WINDSHIELD, GLASS, SCRATCH, MINOR)

    assert isinstance(result, Unpriced)
    assert "aren't worth repairing" in result.reason
