"""Turn detected damage into an itemized repair estimate.

The estimate follows the structure of collision estimating software: each damaged panel
gets an operation (repair, replace, refinish, ...) measured in labour hours and charged at
the shop's hourly rates, plus parts, paint materials and specialist (sublet) work. Every
amount is a low–high range: the low end assumes aftermarket parts and lower shop rates,
the high end dealer parts and higher rates.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.pricing.costbook import CostBook, PanelCategory, PanelSpec
from app.pricing.models import (
    CostRange,
    DamageInput,
    Estimate,
    EstimateLine,
    EstimateTotals,
    HourlyRates,
    HoursRange,
    Operation,
    UnpricedDamage,
)
from app.pricing.panels import ADJACENT, PANEL_ORDER, panel_label
from app.pricing.rules import DAMAGE_LABELS, Sublet, Unpriced, Work, WorkKind, plan_work
from app.pricing.span import ZERO, Span, whole_dollars
from app.schemas import Panel, Severity
from app.vehicles import Vehicle

# Damage the detector is less sure about than this is listed but not priced.
MIN_CONFIDENCE = 0.5

DISCLAIMER = (
    "This is an estimate to help you plan, not a quote. Shops often find more damage "
    "once parts come off."
)
WHEEL_NOTE = (
    "A hit hard enough to bend or break a wheel can also damage the suspension. "
    "Have the alignment checked."
)
LOW_CONFIDENCE_REASON = (
    "The photo analysis wasn't confident about this damage, so it wasn't priced. "
    "Have a shop check it."
)

# Specialist prices that depend on the vehicle, the way part prices do.
_VEHICLE_PRICED_SUBLETS = {Sublet.MIRROR_GLASS, Sublet.TIRE_REPLACE}

_SUBLET_DESCRIPTIONS = {
    Sublet.WINDSHIELD_CHIP_REPAIR: "Repair the chip in the {panel}",
    Sublet.LENS_RESTORATION: "Restore the {panel} lens",
    Sublet.MIRROR_GLASS: "Replace the {panel} glass",
    Sublet.TIRE_REPAIR: "Patch the tire on the {panel}",
    Sublet.TIRE_REPLACE: "Replace the tire on the {panel}",
    Sublet.WHEEL_COSMETIC_REPAIR: "Repair curb rash on the {panel}",
    Sublet.WHEEL_STRAIGHTEN: "Straighten the {panel} rim",
}

# Driver-assist sensors that must be recalibrated after nearby repairs:
# (sensor, the repairs that disturb it, the features that mean the vehicle has it).
_CALIBRATIONS = (
    (
        "lane camera",
        {Panel.WINDSHIELD: {Operation.REPLACE}},
        ("lane_departure_warning", "lane_keep_assist"),
    ),
    (
        "front radar",
        {
            Panel.FRONT_BUMPER: {Operation.REPAIR, Operation.REPLACE},
            Panel.GRILLE: {Operation.REPLACE},
        },
        ("adaptive_cruise",),
    ),
    (
        "blind-spot radar",
        {Panel.REAR_BUMPER: {Operation.REPAIR, Operation.REPLACE}},
        ("blind_spot_monitoring",),
    ),
)

_OPERATION_ORDER = {operation: index for index, operation in enumerate(Operation)}


@dataclass(frozen=True)
class _Line:
    panel: Panel
    operation: Operation
    description: str
    body_hours: Span | None = None
    refinish_hours: Span | None = None
    parts: Span | None = None
    sublet: Span | None = None


def build_estimate(
    damages: Sequence[DamageInput],
    vehicle: Vehicle,
    book: CostBook,
    notes: Sequence[str] = (),
) -> Estimate:
    """Price the damage on one vehicle. `notes` are passed through to the estimate."""
    return _Estimator(book, vehicle).run(damages, notes)


class _Estimator:
    def __init__(self, book: CostBook, vehicle: Vehicle) -> None:
        self.book = book
        self.vehicle = vehicle
        self.rates = book.rates[vehicle.tier]
        self.size_factor = book.size_multipliers[vehicle.size]
        self.lines: list[_Line] = []
        self.unpriced: list[UnpricedDamage] = []
        self.notes: list[str] = []
        self.to_refinish: list[Panel] = []

    def run(self, damages: Sequence[DamageInput], notes: Sequence[str]) -> Estimate:
        for (panel, _component), planned in self._plan(damages).items():
            self._price_panel(panel, planned)
        self._refinish_and_blend()
        self._calibrate()
        return self._estimate([*notes, *dict.fromkeys(self.notes), DISCLAIMER])

    def _plan(
        self, damages: Sequence[DamageInput]
    ) -> dict[tuple[Panel, str], list[tuple[DamageInput, Work]]]:
        """Decide the work for each damage and group it by the part it applies to."""
        planned: dict[tuple[Panel, str], list[tuple[DamageInput, Work]]] = {}
        for damage in damages:
            if damage.confidence < MIN_CONFIDENCE:
                self._skip(damage, LOW_CONFIDENCE_REASON)
                continue
            spec = self.book.spec(damage.panel)
            work = plan_work(damage.panel, spec.category, damage.damage_type, damage.severity)
            if isinstance(work, Unpriced):
                self._skip(damage, work.reason)
            else:
                planned.setdefault((damage.panel, work.component), []).append((damage, work))
        return planned

    def _price_panel(self, panel: Panel, planned: list[tuple[DamageInput, Work]]) -> None:
        spec = self.book.spec(panel)
        works = [work for _, work in planned]
        match max(work.kind for work in works):
            case WorkKind.REPLACE:
                self._replace(panel, spec, next(w for w in works if w.kind is WorkKind.REPLACE))
            case WorkKind.REPAIR:
                self._repair(panel, spec, planned)
            case WorkKind.PAINTLESS_REPAIR:
                self._add(
                    panel,
                    Operation.PAINTLESS_REPAIR,
                    f"Paintless dent repair on the {panel_label(panel)}",
                    sublet=self.book.sublet.paintless_dent_repair[spec.size],
                )
            case WorkKind.POLISH:
                self._polish(panel, spec, works[0].sublet)

    def _replace(self, panel: Panel, spec: PanelSpec, work: Work) -> None:
        name = panel_label(panel)
        if work.sublet:
            self._add_sublet(panel, Operation.REPLACE, work.sublet)
            return
        if spec.category is PanelCategory.GLASS:
            price = spec.replace_price * self._parts_factor(spec)
            self._add(panel, Operation.REPLACE, f"Replace the {name} (glass shop)", sublet=price)
            return

        parts = spec.part_price * self._parts_factor(spec)
        self._add(
            panel,
            Operation.REPLACE,
            f"Replace the {name}",
            body_hours=spec.replace_hours,
            parts=parts,
        )
        if spec.painted:
            self.to_refinish.append(panel)
        if spec.welded:
            self.notes.append(
                f"Replacing the {name} means cutting out the old panel and welding in a new "
                "one. Shops often find more damage once it's opened up."
            )
        if spec.category is PanelCategory.WHEEL:
            self.notes.append(WHEEL_NOTE)

    def _repair(
        self, panel: Panel, spec: PanelSpec, planned: list[tuple[DamageInput, Work]]
    ) -> None:
        works = [work for _, work in planned]
        for sublet in dict.fromkeys(
            w.sublet for w in works if w.kind is WorkKind.REPAIR and w.sublet
        ):
            self._add_sublet(panel, Operation.REPAIR, sublet)
            if sublet is Sublet.WHEEL_STRAIGHTEN:
                self.notes.append(WHEEL_NOTE)

        # Shop repairs on one panel add up. A small dent on a panel that's being repainted
        # anyway is fixed in the same repair rather than paintlessly.
        in_shop = [
            (damage, work)
            for damage, work in planned
            if work.sublet is None and work.kind in (WorkKind.REPAIR, WorkKind.PAINTLESS_REPAIR)
        ]
        if in_shop:
            hours_by_severity = self.book.repair_hours[spec.size]
            hours = sum((hours_by_severity[w.severity or Severity.MINOR] for _, w in in_shop), ZERO)
            what = ", ".join(
                dict.fromkeys(f"{d.severity} {DAMAGE_LABELS[d.damage_type]}" for d, _ in in_shop)
            )
            self._add(
                panel,
                Operation.REPAIR,
                f"Repair the {panel_label(panel)} ({what})",
                body_hours=hours,
            )

        if any(work.refinish for work in works):
            self.to_refinish.append(panel)
        elif polish := next((w for w in works if w.kind is WorkKind.POLISH), None):
            self._polish(panel, spec, polish.sublet)

    def _polish(self, panel: Panel, spec: PanelSpec, sublet: Sublet | None) -> None:
        if sublet:
            self._add_sublet(panel, Operation.POLISH, sublet)
        else:
            self._add(
                panel,
                Operation.POLISH,
                f"Buff out light scratches on the {panel_label(panel)}",
                body_hours=self.book.polish_hours[spec.size],
            )

    def _refinish_and_blend(self) -> None:
        panels = list(dict.fromkeys(self.to_refinish))

        # The biggest panel is painted at full time. A panel next to one that's already
        # being painted shares its masking and setup, so it gets the overlap deduction.
        painted: set[Panel] = set()
        for panel in sorted(panels, key=lambda p: self.book.spec(p).refinish_hours, reverse=True):
            hours = self._refinish_hours(panel)
            if ADJACENT[panel] & painted:
                hours = _deduct_overlap(hours, self.book.overlap_hours)
            self._add(
                panel,
                Operation.REFINISH,
                f"Refinish the {panel_label(panel)}",
                refinish_hours=hours,
            )
            painted.add(panel)

        # Untouched neighbours are blended so the new paint fades into the old.
        for panel in panels:
            for neighbour in sorted(ADJACENT[panel] - painted, key=PANEL_ORDER.__getitem__):
                self._add(
                    neighbour,
                    Operation.BLEND,
                    f"Blend the {panel_label(neighbour)} to match the new paint",
                    refinish_hours=self._refinish_hours(neighbour) * self.book.blend_fraction,
                )
                painted.add(neighbour)

    def _calibrate(self) -> None:
        operations: dict[Panel, set[Operation]] = defaultdict(set)
        for line in self.lines:
            operations[line.panel].add(line.operation)

        assist = self.vehicle.driver_assist
        might_need_calibration = False
        for sensor, triggers, features in _CALIBRATIONS:
            panel = next((p for p, ops in triggers.items() if operations[p] & ops), None)
            if panel is None:
                continue
            has_feature = [getattr(assist, feature) for feature in features] if assist else [None]
            if True in has_feature:
                self._add(
                    panel,
                    Operation.CALIBRATE,
                    f"Calibrate the {sensor} after this repair",
                    sublet=self.book.sublet.sensor_calibration,
                )
            elif None in has_feature:
                might_need_calibration = True

        if might_need_calibration:
            price = CostRange.from_span(self.book.sublet.sensor_calibration)
            self.notes.append(
                "If this vehicle has driver-assist sensors (lane camera, radar cruise control or "
                "blind-spot monitoring), they may need calibrating after this repair, which adds "
                f"about ${price.low}–${price.high}."
            )

    def _estimate(self, notes: list[str]) -> Estimate:
        rates = self.rates
        body_hours = _total(line.body_hours for line in self.lines)
        refinish_hours = _total(line.refinish_hours for line in self.lines)
        categories = {
            "body_labour": body_hours * rates.body_labour,
            "shop_materials": body_hours * rates.shop_materials,
            "refinish_labour": refinish_hours * rates.refinish_labour,
            "paint_materials": refinish_hours * rates.paint_materials,
            "parts": _total(line.parts for line in self.lines),
            "sublet": _total(line.sublet for line in self.lines),
        }
        rounded = {name: CostRange.from_span(amount) for name, amount in categories.items()}
        subtotal = CostRange(
            low=sum(cost.low for cost in rounded.values()),
            high=sum(cost.high for cost in rounded.values()),
        )
        tax = CostRange(
            low=whole_dollars(subtotal.low * self.book.tax_rate),
            high=whole_dollars(subtotal.high * self.book.tax_rate),
        )

        first_seen: dict[Panel, int] = {}
        for line in self.lines:
            first_seen.setdefault(line.panel, len(first_seen))
        ordered = sorted(
            self.lines, key=lambda line: (first_seen[line.panel], _OPERATION_ORDER[line.operation])
        )

        return Estimate(
            currency=self.book.currency,
            region=self.book.region,
            tax_name=self.book.tax_name,
            vehicle=self.vehicle,
            hourly_rates=HourlyRates(
                body_labour=CostRange.from_span(rates.body_labour),
                refinish_labour=CostRange.from_span(rates.refinish_labour),
                paint_materials=CostRange.from_span(rates.paint_materials),
                shop_materials=CostRange.from_span(rates.shop_materials),
            ),
            lines=[self._line_out(line) for line in ordered],
            totals=EstimateTotals(
                body_hours=HoursRange.from_span(body_hours),
                refinish_hours=HoursRange.from_span(refinish_hours),
                **rounded,
                subtotal=subtotal,
                tax=tax,
                total=CostRange(low=subtotal.low + tax.low, high=subtotal.high + tax.high),
            ),
            unpriced=self.unpriced,
            notes=notes,
        )

    def _line_out(self, line: _Line) -> EstimateLine:
        rates = self.rates
        cost = ZERO
        if line.body_hours is not None:
            cost += line.body_hours * (rates.body_labour + rates.shop_materials)
        if line.refinish_hours is not None:
            cost += line.refinish_hours * (rates.refinish_labour + rates.paint_materials)
        cost += _total([line.parts, line.sublet])
        return EstimateLine(
            panel=line.panel,
            operation=line.operation,
            description=line.description,
            body_hours=_optional(HoursRange, line.body_hours),
            refinish_hours=_optional(HoursRange, line.refinish_hours),
            parts=_optional(CostRange, line.parts),
            sublet=_optional(CostRange, line.sublet),
            cost=CostRange.from_span(cost),
        )

    def _add(self, panel: Panel, operation: Operation, description: str, **amounts: Span) -> None:
        self.lines.append(_Line(panel, operation, description, **amounts))

    def _add_sublet(self, panel: Panel, operation: Operation, sublet: Sublet) -> None:
        price = getattr(self.book.sublet, sublet.value)
        if sublet in _VEHICLE_PRICED_SUBLETS:
            price = price * (self.rates.parts_multiplier * self.size_factor)
        description = _SUBLET_DESCRIPTIONS[sublet].format(panel=panel_label(panel))
        self._add(panel, operation, description, sublet=price)

    def _skip(self, damage: DamageInput, reason: str) -> None:
        self.unpriced.append(
            UnpricedDamage(
                panel=damage.panel,
                damage_type=damage.damage_type,
                severity=damage.severity,
                reason=reason,
            )
        )

    def _parts_factor(self, spec: PanelSpec) -> Decimal:
        if spec.category is PanelCategory.LAMP:
            return self.rates.lamp_parts_multiplier * self.size_factor
        return self.rates.parts_multiplier * self.size_factor

    def _refinish_hours(self, panel: Panel) -> Span:
        return Span.of(self.book.spec(panel).refinish_hours) * self.size_factor


def _total(amounts: Iterable[Span | None]) -> Span:
    return sum((amount for amount in amounts if amount is not None), ZERO)


def _optional(range_type: type[CostRange] | type[HoursRange], span: Span | None):
    return None if span is None else range_type.from_span(span)


def _deduct_overlap(hours: Span, overlap: Decimal) -> Span:
    """Take the overlap off, but never more than half of the panel's paint time."""
    return Span(max(hours.low - overlap, hours.low / 2), max(hours.high - overlap, hours.high / 2))
