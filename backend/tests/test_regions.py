import pytest

from app.regions import InvalidPostalCodeError, province_for_postal_code


@pytest.mark.parametrize(
    ("postal_code", "province"),
    [
        ("M5V 2T6", "Ontario"),
        (" m5v2t6 ", "Ontario"),
        ("K1A 0B1", "Ontario"),
        ("V6B 1A1", "British Columbia"),
        ("H2X 1Y4", "Quebec"),
    ],
)
def test_province_from_postal_code(postal_code, province):
    assert province_for_postal_code(postal_code) == province


@pytest.mark.parametrize("postal_code", ["12345", "D1A 1A1", "M5V 2T", "M5V-2T6"])
def test_invalid_postal_codes_are_rejected(postal_code):
    with pytest.raises(InvalidPostalCodeError):
        province_for_postal_code(postal_code)
