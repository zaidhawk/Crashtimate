"""Low–high ranges for hours, rates and prices."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any) -> Decimal:
    """Convert a number to Decimal, going through str so 0.13 stays exactly 0.13."""
    if isinstance(value, bool):
        raise ValueError(f"Expected a number, got {value!r}")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Expected a number, got {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Expected a finite number, got {value!r}")
    return number


def whole_dollars(amount: Decimal) -> int:
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Span:
    """A non-negative range. Adding or multiplying spans combines the low and high ends."""

    low: Decimal
    high: Decimal

    def __post_init__(self) -> None:
        if self.low < 0 or self.low > self.high:
            raise ValueError(f"Invalid range: {self.low} to {self.high}")

    @classmethod
    def of(cls, value: Any) -> "Span":
        """Build a span from a Span, a single number, or a [low, high] pair."""
        if isinstance(value, Span):
            return value
        if isinstance(value, list | tuple):
            if len(value) != 2:
                raise ValueError("A range needs exactly two numbers: [low, high]")
            return cls(to_decimal(value[0]), to_decimal(value[1]))
        number = to_decimal(value)
        return cls(number, number)

    def __add__(self, other: "Span") -> "Span":
        return Span(self.low + other.low, self.high + other.high)

    def __mul__(self, other: "Span | Decimal | int") -> "Span":
        other = Span.of(other)
        return Span(self.low * other.low, self.high * other.high)

    __rmul__ = __mul__


ZERO = Span(Decimal(0), Decimal(0))
