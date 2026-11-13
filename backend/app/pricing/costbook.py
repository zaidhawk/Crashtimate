"""The cost book: the labour rates, hours and prices the pricing engine reads.

The numbers live in data/ontario.toml so they can be reviewed and sourced without
touching code. docs/cost-data.md explains where each one comes from.
"""

import tomllib
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainValidator, field_validator, model_validator

from app.pricing.panels import PANEL_TYPES
from app.pricing.span import Span
from app.schemas import Panel, Severity
from app.vehicles import BodySize, VehicleTier, make_key

DEFAULT_COST_BOOK = Path(__file__).parent / "data" / "ontario.toml"

SpanField = Annotated[Span, PlainValidator(Span.of)]


class PanelCategory(StrEnum):
    BODY = "body"  # painted metal panels
    BUMPER = "bumper"  # painted plastic bumper covers
    MIRROR = "mirror"
    LAMP = "lamp"
    GRILLE = "grille"
    GLASS = "glass"
    WHEEL = "wheel"


class PanelSize(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


_REQUIRED_FIELDS = {
    PanelCategory.BODY: ("size", "refinish_hours", "replace_hours", "part_price"),
    PanelCategory.BUMPER: ("size", "refinish_hours", "replace_hours", "part_price"),
    PanelCategory.MIRROR: ("size", "refinish_hours", "replace_hours", "part_price"),
    PanelCategory.LAMP: ("replace_hours", "part_price"),
    PanelCategory.GRILLE: ("size", "replace_hours", "part_price"),
    PanelCategory.GLASS: ("replace_price",),
    PanelCategory.WHEEL: ("replace_hours", "part_price"),
}


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PanelSpec(_Section):
    category: PanelCategory
    size: PanelSize | None = None
    # Paint hours to refinish the whole outer panel. Zero for unpainted parts.
    refinish_hours: Decimal = Decimal(0)
    # Body labour to remove the old part and fit the new one.
    replace_hours: SpanField | None = None
    # Low end: certified aftermarket part. High end: dealer (OEM) part.
    part_price: SpanField | None = None
    # Glass: installed price from a glass shop, used instead of part price plus labour.
    replace_price: SpanField | None = None
    # Welded rather than bolted on, so replacing it means cutting and welding.
    welded: bool = False

    @property
    def painted(self) -> bool:
        return self.refinish_hours > 0

    @model_validator(mode="after")
    def _has_required_fields(self) -> "PanelSpec":
        missing = [name for name in _REQUIRED_FIELDS[self.category] if not getattr(self, name)]
        if missing:
            raise ValueError(f"{self.category} panels need {', '.join(missing)}")
        return self


class TierRates(_Section):
    body_labour: SpanField  # $ per body labour hour
    refinish_labour: SpanField  # $ per paint labour hour
    paint_materials: SpanField  # $ per paint labour hour
    shop_materials: SpanField  # $ per body labour hour
    parts_multiplier: Decimal
    lamp_parts_multiplier: Decimal


class SubletPrices(_Section):
    paintless_dent_repair: dict[PanelSize, SpanField]
    windshield_chip_repair: SpanField
    lens_restoration: SpanField
    mirror_glass: SpanField
    tire_repair: SpanField
    tire_replace: SpanField
    wheel_cosmetic_repair: SpanField
    wheel_straighten: SpanField
    sensor_calibration: SpanField


class CostBook(_Section):
    currency: str
    region: str
    tax_name: str
    tax_rate: Decimal
    luxury_makes: frozenset[str]
    blend_fraction: SpanField
    overlap_hours: Decimal
    rates: dict[VehicleTier, TierRates]
    size_multipliers: dict[BodySize, Decimal]
    repair_hours: dict[PanelSize, dict[Severity, SpanField]]
    polish_hours: dict[PanelSize, SpanField]
    sublet: SubletPrices
    panel_types: dict[str, PanelSpec]

    @field_validator("luxury_makes", mode="before")
    @classmethod
    def _normalize_makes(cls, makes: list[str]) -> frozenset[str]:
        return frozenset(make_key(make) for make in makes)

    @model_validator(mode="after")
    def _is_complete(self) -> "CostBook":
        _require_keys("rates", self.rates, VehicleTier)
        _require_keys("size_multipliers", self.size_multipliers, BodySize)
        _require_keys("repair_hours", self.repair_hours, PanelSize)
        for size, by_severity in self.repair_hours.items():
            _require_keys(f"repair_hours.{size}", by_severity, Severity)
        _require_keys("polish_hours", self.polish_hours, PanelSize)
        _require_keys("sublet.paintless_dent_repair", self.sublet.paintless_dent_repair, PanelSize)
        _require_keys("panel_types", self.panel_types, set(PANEL_TYPES.values()))
        return self

    def spec(self, panel: Panel) -> PanelSpec:
        return self.panel_types[PANEL_TYPES[panel]]


def _require_keys(section: str, table: dict, expected) -> None:
    missing = sorted(set(expected) - set(table))
    if missing:
        raise ValueError(f"[{section}] is missing {', '.join(missing)}")


def load_cost_book(path: Path = DEFAULT_COST_BOOK) -> CostBook:
    with path.open("rb") as file:
        return CostBook.model_validate(tomllib.load(file))
