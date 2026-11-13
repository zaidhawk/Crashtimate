import asyncio
import json

import httpx
import pytest

from app.vehicles import (
    BodySize,
    InvalidVinError,
    VehicleTier,
    VinDecoder,
    VinLookupError,
    VinNotFoundError,
    body_size,
    normalize_vin,
    vehicle_tier,
)
from tests.conftest import CIVIC_VIN, OTHER_VIN

# Trimmed from a real vPIC DecodeVinValues response.
VPIC_RESULT = {
    "Make": "HONDA",
    "Model": "Civic",
    "ModelYear": "2019",
    "Trim": "",
    "BodyClass": "Sedan/Saloon",
    "AdaptiveCruiseControl": "Standard",
    "LaneDepartureWarning": "Standard",
    "LaneKeepSystem": "Not Applicable",
    "BlindSpotMon": "Optional",
    "ErrorCode": "0",
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (CIVIC_VIN, CIVIC_VIN),
        ("1hgcm8 2633-a004352", CIVIC_VIN),
        (OTHER_VIN, OTHER_VIN),  # check digit X
        ("11111111111111111", "11111111111111111"),
    ],
)
def test_valid_vins_are_normalized(raw, expected):
    assert normalize_vin(raw) == expected


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("1HGCM82633A00435", "17 letters"),
        ("1HGCM82633AO04352", "never uses I, O or Q"),
        ("1HGCM82643A004352", "Check it for typos"),
    ],
)
def test_invalid_vins_are_rejected(raw, message):
    with pytest.raises(InvalidVinError, match=message):
        normalize_vin(raw)


@pytest.mark.parametrize(
    ("body_class", "expected"),
    [
        ("Sedan/Saloon", BodySize.CAR),
        ("Hatchback/Liftback/Notchback", BodySize.CAR),
        ("Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)", BodySize.SUV),
        ("Crossover Utility Vehicle (CUV)", BodySize.SUV),
        ("Minivan", BodySize.SUV),
        ("Pickup", BodySize.TRUCK),
        ("Cargo Van", BodySize.TRUCK),
        (None, BodySize.CAR),
    ],
)
def test_body_size(body_class, expected):
    assert body_size(body_class) == expected


def test_vehicle_tier(cost_book):
    luxury = cost_book.luxury_makes

    assert vehicle_tier("MERCEDES-BENZ", luxury) is VehicleTier.LUXURY
    assert vehicle_tier("ROLLS ROYCE", luxury) is VehicleTier.LUXURY
    assert vehicle_tier("HONDA", luxury) is VehicleTier.STANDARD
    assert vehicle_tier(None, luxury) is VehicleTier.STANDARD


def decode(handler, vin: str = CIVIC_VIN, luxury_makes=frozenset({"TESLA"})):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await VinDecoder(client, luxury_makes).decode(vin)

    return asyncio.run(run())


def respond_with(result: dict | None, status_code: int = 200):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = {"Count": 1, "Results": [result] if result is not None else []}
        return httpx.Response(status_code, json=body)

    return handler, requests


def test_decodes_vehicle_details_and_driver_assist():
    handler, requests = respond_with(VPIC_RESULT)

    vehicle = decode(handler)

    assert (vehicle.vin, vehicle.year, vehicle.make, vehicle.model) == (
        CIVIC_VIN,
        2019,
        "HONDA",
        "Civic",
    )
    assert vehicle.trim is None
    assert (vehicle.tier, vehicle.size) == (VehicleTier.STANDARD, BodySize.CAR)
    assist = vehicle.driver_assist
    assert assist.adaptive_cruise is True
    assert assist.lane_keep_assist is False
    assert assist.blind_spot_monitoring is None  # optional equipment: unknown for this car

    (request,) = requests
    assert request.url.path.endswith(f"/DecodeVinValues/{CIVIC_VIN}")
    assert request.url.params["format"] == "json"


def test_luxury_suv():
    result = {**VPIC_RESULT, "Make": "TESLA", "BodyClass": "Sport Utility Vehicle (SUV)"}

    vehicle = decode(respond_with(result)[0])

    assert (vehicle.tier, vehicle.size) == (VehicleTier.LUXURY, BodySize.SUV)


def test_unknown_vin_raises_not_found():
    with pytest.raises(VinNotFoundError):
        decode(respond_with({**VPIC_RESULT, "Make": ""})[0])


def raise_connect_error(request):
    raise httpx.ConnectError("offline", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        respond_with(VPIC_RESULT, status_code=500)[0],
        respond_with(None)[0],
        lambda request: httpx.Response(200, text="<html>maintenance</html>"),
        lambda request: httpx.Response(200, content=json.dumps({"Results": "nope"})),
        raise_connect_error,
    ],
    ids=["server error", "no results", "not json", "wrong shape", "offline"],
)
def test_service_problems_raise_lookup_error(handler):
    with pytest.raises(VinLookupError):
        decode(handler)
