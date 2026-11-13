from decimal import Decimal

import pytest

from app.pricing.span import ZERO, Span, whole_dollars


def test_builds_from_pairs_and_single_numbers():
    assert Span.of([85, 105]) == Span(Decimal(85), Decimal(105))
    assert Span.of(2.6) == Span(Decimal("2.6"), Decimal("2.6"))


def test_floats_convert_exactly():
    assert Span.of([0.1, 0.13]).high == Decimal("0.13")


@pytest.mark.parametrize("value", [[5, 1], [-1, 2], [1, 2, 3], "abc", True, float("nan")])
def test_rejects_bad_ranges(value):
    with pytest.raises(ValueError):
        Span.of(value)


def test_arithmetic_combines_low_and_high_ends():
    hours = Span.of([1.5, 3.0])
    rate = Span.of([85, 105])

    assert hours * rate == Span(Decimal("127.5"), Decimal("315.0"))
    assert hours + Span.of([0.5, 1.0]) == Span(Decimal("2.0"), Decimal("4.0"))
    assert hours * Decimal(2) == Span(Decimal("3.0"), Decimal("6.0"))
    assert sum([hours, hours], ZERO) == Span(Decimal("3.0"), Decimal("6.0"))


def test_whole_dollars_rounds_half_up():
    assert whole_dollars(Decimal("142.5")) == 143
    assert whole_dollars(Decimal("142.49")) == 142
