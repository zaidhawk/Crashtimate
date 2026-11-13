"""Map Canadian postal codes to provinces."""

import re

_POSTAL_CODE = re.compile(r"[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d")

# The first letter of a postal code identifies the province or territory.
_PROVINCES = {
    "A": "Newfoundland and Labrador",
    "B": "Nova Scotia",
    "C": "Prince Edward Island",
    "E": "New Brunswick",
    "G": "Quebec",
    "H": "Quebec",
    "J": "Quebec",
    "K": "Ontario",
    "L": "Ontario",
    "M": "Ontario",
    "N": "Ontario",
    "P": "Ontario",
    "R": "Manitoba",
    "S": "Saskatchewan",
    "T": "Alberta",
    "V": "British Columbia",
    "X": "the Northwest Territories or Nunavut",
    "Y": "Yukon",
}


class InvalidPostalCodeError(ValueError):
    """The message is safe to show to users."""


def province_for_postal_code(raw: str) -> str:
    code = raw.strip().upper()
    if not _POSTAL_CODE.fullmatch(code):
        raise InvalidPostalCodeError("Enter a Canadian postal code, like M5V 2T6.")
    return _PROVINCES[code[0]]
