import copy
import tomllib
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.pricing.costbook import DEFAULT_COST_BOOK, CostBook
from app.pricing.rules import Sublet
from app.schemas import Panel


@pytest.fixture(scope="module")
def raw_book() -> dict:
    with DEFAULT_COST_BOOK.open("rb") as file:
        return tomllib.load(file)


def test_every_panel_has_a_spec(cost_book):
    for panel in Panel:
        assert cost_book.spec(panel)


def test_every_sublet_has_a_price(cost_book):
    for sublet in Sublet:
        assert getattr(cost_book.sublet, sublet.value)


def test_numbers_are_exact_decimals(cost_book):
    assert cost_book.tax_rate == Decimal("0.13")
    assert cost_book.overlap_hours == Decimal("0.4")


def test_luxury_makes_ignore_case_and_punctuation(cost_book):
    assert "MERCEDESBENZ" in cost_book.luxury_makes
    assert "ROLLSROYCE" in cost_book.luxury_makes


def edited(raw: dict, edit) -> dict:
    book = copy.deepcopy(raw)
    edit(book)
    return book


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda b: b["rates"].pop("luxury"), "missing luxury"),
        (lambda b: b["panel_types"]["hood"].pop("part_price"), "need part_price"),
        (lambda b: b["panel_types"].pop("wheel"), "missing wheel"),
        (lambda b: b["repair_hours"]["small"].pop("severe"), "missing severe"),
        (lambda b: b["rates"]["standard"].update(body_labour=[105, 85]), "Invalid range"),
        (lambda b: b["panel_types"]["hood"].update(part_prise=[1, 2]), "Extra inputs"),
    ],
)
def test_broken_books_are_rejected(raw_book, edit, message):
    with pytest.raises(ValidationError, match=message):
        CostBook.model_validate(edited(raw_book, edit))
