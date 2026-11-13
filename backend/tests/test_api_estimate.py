import pytest

from app.detectors import Detection, MockDamageDetector
from app.schemas import DamageReport, ImageQuality, ViewAngle
from app.vehicles import DriverAssist, Vehicle, VehicleTier, VinLookupError
from tests.conftest import CIVIC_VIN, FakeVinDecoder, make_image

LUXURY_CAR = Vehicle(
    vin=CIVIC_VIN,
    year=2021,
    make="BMW",
    model="330i",
    tier=VehicleTier.LUXURY,
    driver_assist=DriverAssist(
        adaptive_cruise=True,
        lane_departure_warning=True,
        lane_keep_assist=True,
        blind_spot_monitoring=True,
    ),
)


class CountingDetector(MockDamageDetector):
    def __init__(self, report: DamageReport | None = None):
        self.report = report
        self.calls = 0

    async def detect(self, image):
        self.calls += 1
        if self.report:
            return Detection(report=self.report, model=None)
        return await super().detect(image)


def post_estimate(client, images=None, **form):
    return client.post(
        "/api/estimate",
        files=[("images", ("car.jpg", image, "image/jpeg")) for image in images or [make_image()]],
        data={key: value for key, value in form.items() if value is not None},
    )


def test_estimate_prices_the_detected_damage_for_the_vin(make_client):
    decoder = FakeVinDecoder({CIVIC_VIN: LUXURY_CAR})
    client = make_client(vin_decoder=decoder)

    response = post_estimate(client, vin=" 1hgcm82633a004352 ", postal_code="M5V 2T6")

    assert response.status_code == 200
    body = response.json()
    assert decoder.calls == [CIVIC_VIN]
    estimate = body["estimate"]
    assert estimate["vehicle"]["make"] == "BMW"
    assert estimate["hourly_rates"]["body_labour"] == {"low": 100, "high": 135}
    panels = {line["panel"] for line in estimate["lines"]}
    assert {"left_front_fender", "front_bumper", "left_headlight"} <= panels
    assert estimate["totals"]["total"]["low"] > 0
    assert len(body["damages"]) == 3
    assert body["photos"][0]["meta"]["detector"] == "mock"


def test_estimate_without_a_vin_prices_a_typical_car(client):
    estimate = post_estimate(client).json()["estimate"]

    assert estimate["vehicle"]["tier"] == "standard"
    assert estimate["notes"][0].startswith("Priced as a typical car")


def test_bad_vin_is_rejected_before_the_photo_is_analyzed(make_client):
    detector = CountingDetector()
    client = make_client(detector=detector)

    response = post_estimate(client, vin="NOT-A-VIN")

    assert response.status_code == 422
    assert "17 letters" in response.json()["detail"]
    assert detector.calls == 0


def test_bad_postal_code_is_rejected(client):
    response = post_estimate(client, postal_code="90210")

    assert response.status_code == 422
    assert "postal code" in response.json()["detail"]


def test_postal_code_outside_ontario_adds_a_note(client):
    notes = post_estimate(client, postal_code="V6B 1A1").json()["estimate"]["notes"]

    assert any("British Columbia" in note for note in notes)


@pytest.mark.parametrize(
    ("decoder", "note"),
    [
        (FakeVinDecoder(), "couldn't find that VIN"),
        (FakeVinDecoder(error=VinLookupError("down")), "didn't respond"),
    ],
)
def test_vin_lookup_problems_fall_back_to_a_typical_car(make_client, decoder, note):
    client = make_client(vin_decoder=decoder)

    response = post_estimate(client, vin=CIVIC_VIN)

    assert response.status_code == 200
    estimate = response.json()["estimate"]
    assert estimate["vehicle"] == Vehicle(vin=CIVIC_VIN).model_dump(mode="json")
    assert any(note in text for text in estimate["notes"])


def test_no_estimate_when_the_photo_is_not_a_vehicle(make_client):
    report = DamageReport(
        is_vehicle=False,
        image_quality=ImageQuality.GOOD,
        view=ViewAngle.UNKNOWN,
        damages=[],
        summary="This photo shows a dog, not a vehicle.",
    )
    client = make_client(detector=CountingDetector(report))

    body = post_estimate(client).json()

    assert body["estimate"] is None
    assert body["damages"] == []
    assert body["summary"] == "This photo shows a dog, not a vehicle."
    assert body["photos"][0]["report"]["is_vehicle"] is False


def test_price_endpoint_prices_edited_damage(client):
    response = client.post(
        "/api/price",
        json={
            "damages": [
                {"panel": "left_front_door", "damage_type": "dent", "severity": "minor"},
            ],
            "postal_code": "M5V 2T6",
        },
    )

    assert response.status_code == 200
    estimate = response.json()
    assert [line["operation"] for line in estimate["lines"]] == ["paintless_repair"]
    assert estimate["totals"]["subtotal"] == {"low": 125, "high": 300}


@pytest.mark.parametrize(
    "body",
    [
        {"damages": [{"panel": "flux_capacitor", "damage_type": "dent", "severity": "minor"}]},
        {"damages": [{"panel": "hood", "damage_type": "dent", "severity": "minor"}] * 51},
        {"damages": [], "vin": "123"},
    ],
    ids=["unknown panel", "too many damages", "bad vin"],
)
def test_price_endpoint_rejects_bad_input(client, body):
    assert client.post("/api/price", json=body).status_code == 422


def test_vehicle_lookup(make_client):
    client = make_client(vin_decoder=FakeVinDecoder({CIVIC_VIN: LUXURY_CAR}))

    response = client.get(f"/api/vehicles/{CIVIC_VIN.lower()}")

    assert response.status_code == 200
    assert response.json()["model"] == "330i"


@pytest.mark.parametrize(
    ("decoder", "vin", "status_code"),
    [
        (FakeVinDecoder(), CIVIC_VIN, 404),
        (FakeVinDecoder(error=VinLookupError("down")), CIVIC_VIN, 503),
        (FakeVinDecoder(), "1HGCM82643A004352", 422),
    ],
    ids=["not found", "service down", "bad check digit"],
)
def test_vehicle_lookup_errors(make_client, decoder, vin, status_code):
    client = make_client(vin_decoder=decoder)

    assert client.get(f"/api/vehicles/{vin}").status_code == status_code
