"""Inputs and outputs of the pricing engine."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.pricing.span import Span, whole_dollars
from app.schemas import DamageType, Panel, Severity
from app.vehicles import Vehicle


class Operation(StrEnum):
    REPLACE = "replace"
    REPAIR = "repair"
    PAINTLESS_REPAIR = "paintless_repair"
    POLISH = "polish"
    REFINISH = "refinish"
    BLEND = "blend"
    CALIBRATE = "calibrate"


class DamageInput(BaseModel):
    """One piece of damage to price. The detector's DamageItem carries the same fields."""

    panel: Panel
    damage_type: DamageType
    severity: Severity
    confidence: float = Field(default=1.0, ge=0, le=1)


class CostRange(BaseModel):
    """Whole dollars."""

    low: int
    high: int

    @classmethod
    def from_span(cls, span: Span) -> "CostRange":
        return cls(low=whole_dollars(span.low), high=whole_dollars(span.high))


class HoursRange(BaseModel):
    low: float
    high: float

    @classmethod
    def from_span(cls, span: Span) -> "HoursRange":
        return cls(low=round(float(span.low), 1), high=round(float(span.high), 1))


class EstimateLine(BaseModel):
    panel: Panel
    operation: Operation
    description: str
    body_hours: HoursRange | None
    refinish_hours: HoursRange | None
    parts: CostRange | None
    sublet: CostRange | None = Field(description="Flat-price work done by a specialist.")
    cost: CostRange = Field(description="Everything on this line, before tax.")


class EstimateTotals(BaseModel):
    body_hours: HoursRange
    refinish_hours: HoursRange
    body_labour: CostRange
    shop_materials: CostRange
    refinish_labour: CostRange
    paint_materials: CostRange
    parts: CostRange
    sublet: CostRange
    subtotal: CostRange
    tax: CostRange
    total: CostRange


class HourlyRates(BaseModel):
    body_labour: CostRange
    refinish_labour: CostRange
    paint_materials: CostRange = Field(description="Per paint labour hour.")
    shop_materials: CostRange = Field(description="Per body labour hour.")


class UnpricedDamage(BaseModel):
    panel: Panel
    damage_type: DamageType
    severity: Severity
    reason: str


class Estimate(BaseModel):
    currency: str
    region: str
    tax_name: str
    vehicle: Vehicle
    hourly_rates: HourlyRates
    lines: list[EstimateLine] = Field(description="Rounded to the dollar one by one.")
    totals: EstimateTotals
    unpriced: list[UnpricedDamage]
    notes: list[str]
