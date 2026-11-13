"""Vehicle details from a VIN, using NHTSA's free vPIC decoder (https://vpic.nhtsa.dot.gov/api/)."""

import re
from enum import StrEnum

import httpx
from pydantic import BaseModel

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}"


class VehicleTier(StrEnum):
    STANDARD = "standard"
    LUXURY = "luxury"


class BodySize(StrEnum):
    CAR = "car"
    SUV = "suv"
    TRUCK = "truck"


class DriverAssist(BaseModel):
    """Sensors that need calibrating after some repairs.

    True if NHTSA lists the feature as standard, False if it doesn't apply, None if unknown
    (optional equipment, or no data).
    """

    adaptive_cruise: bool | None
    lane_departure_warning: bool | None
    lane_keep_assist: bool | None
    blind_spot_monitoring: bool | None


class Vehicle(BaseModel):
    """Defaults describe a typical car, used when there's no VIN to look up."""

    vin: str | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    body_class: str | None = None
    tier: VehicleTier = VehicleTier.STANDARD
    size: BodySize = BodySize.CAR
    driver_assist: DriverAssist | None = None


class InvalidVinError(ValueError):
    """The VIN is malformed. The message is safe to show to users."""


class VinNotFoundError(LookupError):
    """NHTSA has no vehicle for this VIN."""


class VinLookupError(Exception):
    """The VIN service couldn't be reached or sent back something unreadable."""


_VIN_PATTERN = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
_VIN_VALUES = {
    **{str(digit): digit for digit in range(10)},
    **dict(
        zip(
            "ABCDEFGHJKLMNPRSTUVWXYZ",
            (1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 7, 9, 2, 3, 4, 5, 6, 7, 8, 9),
            strict=True,
        )
    ),
}
_VIN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_vin(raw: str) -> str:
    """Return the VIN in upper case without spaces or dashes, or raise InvalidVinError."""
    vin = re.sub(r"[\s-]", "", raw).upper()
    if not _VIN_PATTERN.fullmatch(vin):
        raise InvalidVinError("A VIN is 17 letters and numbers, and never uses I, O or Q.")
    # Position 9 is a check digit computed from the others, which catches most typos.
    # Every vehicle sold in North America since 1981 has one.
    if vin[8] != _check_digit(vin):
        raise InvalidVinError("That VIN doesn't add up. Check it for typos.")
    return vin


def _check_digit(vin: str) -> str:
    total = sum(_VIN_VALUES[char] * weight for char, weight in zip(vin, _VIN_WEIGHTS, strict=True))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def body_size(body_class: str | None) -> BodySize:
    """Bucket NHTSA's body class (e.g. "Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle")."""
    text = (body_class or "").lower()
    if "pickup" in text or "truck" in text or ("van" in text and "minivan" not in text):
        return BodySize.TRUCK
    if any(word in text for word in ("sport utility", "crossover", "minivan", "multi-purpose")):
        return BodySize.SUV
    return BodySize.CAR


def make_key(make: str) -> str:
    """Compare makes ignoring case and punctuation: "Rolls-Royce" matches "ROLLS ROYCE"."""
    return re.sub(r"[^A-Z0-9]", "", make.upper())


def vehicle_tier(make: str | None, luxury_makes: frozenset[str]) -> VehicleTier:
    if make and make_key(make) in luxury_makes:
        return VehicleTier.LUXURY
    return VehicleTier.STANDARD


class VinDecoder:
    def __init__(
        self,
        client: httpx.AsyncClient,
        luxury_makes: frozenset[str],
        url: str = VPIC_DECODE_URL,
    ) -> None:
        self._client = client
        self._luxury_makes = luxury_makes
        self._url = url

    async def decode(self, vin: str) -> Vehicle:
        try:
            response = await self._client.get(self._url.format(vin=vin), params={"format": "json"})
            response.raise_for_status()
            result = response.json()["Results"][0]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise VinLookupError("The VIN lookup service isn't responding.") from exc
        if not isinstance(result, dict):
            raise VinLookupError("The VIN lookup service sent back something unexpected.")

        make = _text(result.get("Make"))
        if make is None:
            raise VinNotFoundError("No vehicle was found for that VIN.")
        body_class = _text(result.get("BodyClass"))
        return Vehicle(
            vin=vin,
            year=_year(result.get("ModelYear")),
            make=make,
            model=_text(result.get("Model")),
            trim=_text(result.get("Trim")),
            body_class=body_class,
            tier=vehicle_tier(make, self._luxury_makes),
            size=body_size(body_class),
            driver_assist=DriverAssist(
                adaptive_cruise=_feature(result.get("AdaptiveCruiseControl")),
                lane_departure_warning=_feature(result.get("LaneDepartureWarning")),
                lane_keep_assist=_feature(result.get("LaneKeepSystem")),
                blind_spot_monitoring=_feature(result.get("BlindSpotMon")),
            ),
        )


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _year(value: object) -> int | None:
    text = _text(value)
    return int(text) if text and text.isdigit() else None


def _feature(value: object) -> bool | None:
    match (_text(value) or "").lower():
        case "standard":
            return True
        case "not applicable":
            return False
        case _:
            return None
