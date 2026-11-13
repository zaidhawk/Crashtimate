"""Decide what work each piece of damage needs, the way a body shop estimator would."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from app.pricing.costbook import PanelCategory
from app.pricing.panels import panel_label
from app.schemas import DamageType, Panel, Severity

DENT, SCRATCH, CRACK = DamageType.DENT, DamageType.SCRATCH, DamageType.CRACK
MINOR, MODERATE, SEVERE = Severity.MINOR, Severity.MODERATE, Severity.SEVERE


class WorkKind(IntEnum):
    """Ordered by size of job. On one panel, the biggest job absorbs the smaller ones."""

    POLISH = 1
    PAINTLESS_REPAIR = 2
    REPAIR = 3
    REPLACE = 4


class Sublet(StrEnum):
    """Jobs a specialist does for a flat price. Values match the cost book's sublet fields."""

    WINDSHIELD_CHIP_REPAIR = "windshield_chip_repair"
    LENS_RESTORATION = "lens_restoration"
    MIRROR_GLASS = "mirror_glass"
    TIRE_REPAIR = "tire_repair"
    TIRE_REPLACE = "tire_replace"
    WHEEL_COSMETIC_REPAIR = "wheel_cosmetic_repair"
    WHEEL_STRAIGHTEN = "wheel_straighten"


@dataclass(frozen=True)
class Work:
    kind: WorkKind
    # For repairs done in the shop: which row of the repair-hours table applies.
    severity: Severity | None = None
    # Whether the panel has to be repainted afterwards.
    refinish: bool = False
    # Set when a specialist does the job for a flat price instead of shop labour.
    sublet: Sublet | None = None
    # Tires and rims are separate jobs even though both count as wheel damage.
    component: str = "panel"


@dataclass(frozen=True)
class Unpriced:
    reason: str


DAMAGE_LABELS = {
    DamageType.DENT: "dent",
    DamageType.SCRATCH: "scratch",
    DamageType.CRACK: "crack",
    DamageType.GLASS_SHATTER: "shattered glass",
    DamageType.LAMP_BROKEN: "broken lamp",
    DamageType.TIRE_FLAT: "flat tire",
}


def plan_work(
    panel: Panel, category: PanelCategory, damage_type: DamageType, severity: Severity
) -> Work | Unpriced:
    match category:
        case PanelCategory.BODY:
            work = _painted_panel(damage_type, severity, plastic=False)
        case PanelCategory.BUMPER:
            work = _painted_panel(damage_type, severity, plastic=True)
        case PanelCategory.MIRROR:
            work = _mirror(damage_type, severity)
        case PanelCategory.LAMP:
            work = _lamp(damage_type, severity)
        case PanelCategory.GRILLE:
            work = _grille(damage_type, severity)
        case PanelCategory.GLASS:
            work = _glass(damage_type, severity, chip_repairable=panel is Panel.WINDSHIELD)
        case PanelCategory.WHEEL:
            work = _wheel(damage_type, severity)
    if work is None:
        return Unpriced(
            f"{DAMAGE_LABELS[damage_type].capitalize()} on the {panel_label(panel)} "
            "doesn't make sense, so it wasn't priced."
        )
    return work


def _painted_panel(damage_type: DamageType, severity: Severity, *, plastic: bool) -> Work | None:
    if damage_type is SCRATCH:
        if severity is MINOR:
            return Work(WorkKind.POLISH)
        # Scratches are sanded and filled before painting; deep gouges take longer.
        return Work(WorkKind.REPAIR, MINOR if severity is MODERATE else MODERATE, refinish=True)
    if damage_type in (DENT, CRACK):
        if severity is SEVERE:
            return Work(WorkKind.REPLACE)
        if severity is MODERATE:
            return Work(WorkKind.REPAIR, MODERATE, refinish=True)
        if damage_type is CRACK:
            return Work(WorkKind.REPAIR, MINOR, refinish=True)
        # Small dents: metal can be pushed out without paint; plastic is reshaped with heat.
        return Work(WorkKind.REPAIR, MINOR) if plastic else Work(WorkKind.PAINTLESS_REPAIR)
    return None


def _mirror(damage_type: DamageType, severity: Severity) -> Work | None:
    if damage_type is DamageType.GLASS_SHATTER:
        return Work(WorkKind.REPAIR, sublet=Sublet.MIRROR_GLASS)
    paint_cap = Work(WorkKind.REPAIR, MINOR, refinish=True)
    if damage_type is SCRATCH:
        return Work(WorkKind.POLISH) if severity is MINOR else paint_cap
    if damage_type in (DENT, CRACK):
        return paint_cap if severity is MINOR else Work(WorkKind.REPLACE)
    if damage_type is DamageType.LAMP_BROKEN:
        return Work(WorkKind.REPLACE)
    return None


def _lamp(damage_type: DamageType, severity: Severity) -> Work | None:
    if damage_type is DamageType.TIRE_FLAT:
        return None
    if damage_type is SCRATCH and severity is MINOR:
        return Work(WorkKind.POLISH, sublet=Sublet.LENS_RESTORATION)
    # A cracked or broken lamp lets water in, so it's replaced as an assembly.
    return Work(WorkKind.REPLACE)


def _grille(damage_type: DamageType, severity: Severity) -> Work | None:
    if damage_type is SCRATCH and severity is MINOR:
        return Work(WorkKind.POLISH)
    if damage_type in (SCRATCH, DENT, CRACK):
        return Work(WorkKind.REPLACE)
    return None


def _glass(
    damage_type: DamageType, severity: Severity, *, chip_repairable: bool
) -> Work | Unpriced | None:
    if damage_type is DamageType.GLASS_SHATTER:
        return Work(WorkKind.REPLACE)
    if damage_type is CRACK:
        if severity is MINOR and chip_repairable:
            return Work(WorkKind.REPAIR, sublet=Sublet.WINDSHIELD_CHIP_REPAIR)
        return Work(WorkKind.REPLACE)
    if damage_type is SCRATCH:
        if severity is MINOR:
            return Unpriced("Light scratches on glass usually aren't worth repairing.")
        return Work(WorkKind.REPLACE)
    return None


def _wheel(damage_type: DamageType, severity: Severity) -> Work | None:
    if damage_type is DamageType.TIRE_FLAT:
        if severity is MINOR:
            return Work(WorkKind.REPAIR, sublet=Sublet.TIRE_REPAIR, component="tire")
        return Work(WorkKind.REPLACE, sublet=Sublet.TIRE_REPLACE, component="tire")
    if damage_type is CRACK or (damage_type in (SCRATCH, DENT) and severity is SEVERE):
        # A cracked rim isn't safe to weld and drive on.
        return Work(WorkKind.REPLACE)
    if damage_type is SCRATCH:
        return Work(WorkKind.REPAIR, sublet=Sublet.WHEEL_COSMETIC_REPAIR)
    if damage_type is DENT:
        return Work(WorkKind.REPAIR, sublet=Sublet.WHEEL_STRAIGHTEN)
    return None
