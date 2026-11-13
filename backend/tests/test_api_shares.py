"""Multi-photo estimates, the analysis cache, limits and saved estimates."""

from app.detectors import Detection, MockDamageDetector
from app.detectors.mock import SAMPLE_REPORT
from app.schemas import (
    DamageItem,
    DamageReport,
    DamageType,
    ImageQuality,
    Panel,
    Severity,
    ViewAngle,
)
from tests.conftest import make_image

REAR_REPORT = DamageReport(
    is_vehicle=True,
    image_quality=ImageQuality.GOOD,
    view=ViewAngle.REAR,
    damages=[
        DamageItem(
            panel=Panel.REAR_BUMPER,
            damage_type=DamageType.CRACK,
            severity=Severity.MODERATE,
            description="Cracked on the right corner.",
            confidence=0.8,
            box=None,
        ),
        # Also visible in the front photo, but worse from this angle.
        DamageItem(
            panel=Panel.FRONT_BUMPER,
            damage_type=DamageType.SCRATCH,
            severity=Severity.MODERATE,
            description="Deep scratch.",
            confidence=0.7,
            box=None,
        ),
    ],
    summary="The rear bumper is cracked.",
)
BLURRY_REPORT = DamageReport(
    is_vehicle=True,
    image_quality=ImageQuality.UNUSABLE,
    view=ViewAngle.UNKNOWN,
    damages=[],
    summary="The photo is too blurry to assess.",
)


class ScriptedDetector(MockDamageDetector):
    """Returns the given reports in order, then repeats the last one."""

    def __init__(self, *reports: DamageReport):
        self.reports = list(reports) or [SAMPLE_REPORT]
        self.calls = 0

    async def detect(self, image):
        report = self.reports[min(self.calls, len(self.reports) - 1)]
        self.calls += 1
        return Detection(report=report, model=None)


def photo(shade: int) -> bytes:
    """Distinct image bytes per shade, so each has its own hash."""
    return make_image(width=320 + shade, height=240)


def post_estimate(client, *images: bytes, **form):
    return client.post(
        "/api/estimate",
        files=[("images", (f"car{i}.jpg", data, "image/jpeg")) for i, data in enumerate(images)],
        data=form,
    )


def share_body(estimate_response: dict, **extra) -> dict:
    return {
        "photos": [p["meta"]["image_sha256"] for p in estimate_response["photos"]],
        "damages": estimate_response["damages"],
        **extra,
    }


# Several photos


def test_damage_from_several_photos_is_merged_and_priced_once(make_client):
    client = make_client(detector=ScriptedDetector(SAMPLE_REPORT, REAR_REPORT))

    body = post_estimate(client, photo(0), photo(1)).json()

    assert len(body["photos"]) == 2
    merged = {(d["panel"], d["damage_type"]): d for d in body["damages"]}
    assert len(merged) == 4
    assert merged["front_bumper", "scratch"]["severity"] == "moderate"
    assert merged["front_bumper", "scratch"]["photo"] == 1
    assert merged["left_front_fender", "dent"]["photo"] == 0
    assert body["summary"].endswith("The rear bumper is cracked.")
    bumper_repairs = [
        line
        for line in body["estimate"]["lines"]
        if line["panel"] == "front_bumper" and line["operation"] == "repair"
    ]
    assert len(bumper_repairs) == 1


def test_an_unusable_photo_does_not_block_the_estimate(make_client):
    client = make_client(detector=ScriptedDetector(BLURRY_REPORT, SAMPLE_REPORT))

    body = post_estimate(client, photo(0), photo(1)).json()

    assert body["estimate"] is not None
    assert {d["photo"] for d in body["damages"]} == {1}
    assert body["photos"][0]["report"]["image_quality"] == "unusable"


def test_too_many_photos_are_rejected_before_analysis(make_client):
    detector = ScriptedDetector()
    client = make_client(detector=detector, max_photos=2)

    response = post_estimate(client, photo(0), photo(1), photo(2))

    assert response.status_code == 422
    assert "at most 2 photos" in response.json()["detail"]
    assert detector.calls == 0


def test_at_least_one_photo_is_required(client):
    assert client.post("/api/estimate", data={"postal_code": "M5V 2T6"}).status_code == 422


# Vehicle type without a VIN


def test_vehicle_type_is_used_when_there_is_no_vin(client):
    typical = post_estimate(client, photo(0)).json()["estimate"]

    picked = post_estimate(client, photo(0), vehicle_size="truck", vehicle_tier="luxury").json()[
        "estimate"
    ]

    assert (picked["vehicle"]["size"], picked["vehicle"]["tier"]) == ("truck", "luxury")
    assert picked["notes"][0].startswith("Priced as a typical luxury truck.")
    assert picked["totals"]["total"]["high"] > typical["totals"]["total"]["high"]


def test_price_endpoint_accepts_a_vehicle_type(client):
    damages = [{"panel": "hood", "damage_type": "dent", "severity": "severe"}]

    car = client.post("/api/price", json={"damages": damages}).json()
    suv = client.post("/api/price", json={"damages": damages, "vehicle_size": "suv"}).json()

    assert suv["vehicle"]["size"] == "suv"
    assert suv["totals"]["parts"]["high"] > car["totals"]["parts"]["high"]
    bad = client.post("/api/price", json={"damages": damages, "vehicle_size": "boat"})
    assert bad.status_code == 422


# Cache and limits


def test_the_same_photo_is_only_analysed_once(make_client):
    detector = ScriptedDetector()
    client = make_client(detector=detector)

    first = post_estimate(client, photo(0)).json()
    second = post_estimate(client, photo(0)).json()
    post_estimate(client, photo(1))

    assert detector.calls == 2
    assert first["photos"][0]["meta"]["cached"] is False
    assert second["photos"][0]["meta"]["cached"] is True
    assert second["damages"] == first["damages"]
    assert second["estimate"] == first["estimate"]


def test_daily_limit_stops_new_analyses_but_not_cached_ones(make_client):
    detector = ScriptedDetector()
    client = make_client(detector=detector, daily_analysis_limit=1)

    assert post_estimate(client, photo(0)).status_code == 200
    blocked = post_estimate(client, photo(1))
    assert blocked.status_code == 503
    assert "daily limit" in blocked.json()["detail"]
    assert post_estimate(client, photo(0)).status_code == 200
    assert detector.calls == 1


def test_rate_limit_returns_429_with_retry_after(make_client):
    client = make_client(rate_limit_per_hour=2)

    assert post_estimate(client, photo(0)).status_code == 200
    assert post_estimate(client, photo(0)).status_code == 200
    limited = post_estimate(client, photo(0))

    assert limited.status_code == 429
    assert 0 < int(limited.headers["retry-after"]) <= 3600
    # Endpoints that cost nothing stay open.
    assert client.get("/api/health").status_code == 200


def test_rate_limit_is_per_visitor_behind_a_proxy(make_client):
    client = make_client(rate_limit_per_hour=1, proxy_hops=1)

    def upload(ip: str):
        return client.post(
            "/api/analyze",
            files={"image": ("car.jpg", photo(0), "image/jpeg")},
            headers={"X-Forwarded-For": ip},
        )

    assert upload("203.0.113.1").status_code == 200
    assert upload("203.0.113.1").status_code == 429
    assert upload("203.0.113.2").status_code == 200


# Saved estimates


def test_saved_estimate_can_be_opened_from_its_link(make_client):
    client = make_client(detector=ScriptedDetector(SAMPLE_REPORT, REAR_REPORT))
    estimated = post_estimate(client, photo(0), photo(1), postal_code="V6B 1A1").json()

    created = client.post("/api/shares", json=share_body(estimated, postal_code="V6B 1A1"))

    assert created.status_code == 201
    saved = created.json()
    assert saved["estimate"] == estimated["estimate"]
    assert saved["damages"] == estimated["damages"]
    assert saved["summary"] == estimated["summary"]
    assert saved["photos"] == [{"width": 320, "height": 240}, {"width": 321, "height": 240}]

    opened = client.get(f"/api/shares/{saved['id']}")
    assert opened.status_code == 200
    assert opened.json() == saved

    image = client.get(f"/api/shares/{saved['id']}/photos/1")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content[:2] == b"\xff\xd8"
    assert client.get(f"/api/shares/{saved['id']}/photos/2").status_code == 404


def test_saving_prices_the_users_corrections_on_the_server(client):
    estimated = post_estimate(client, photo(0)).json()
    kept = [d for d in estimated["damages"] if d["panel"] == "left_front_fender"]
    kept[0]["severity"] = "severe"

    saved = client.post("/api/shares", json=share_body(estimated) | {"damages": kept}).json()

    repriced = client.post(
        "/api/price",
        json={"damages": [{k: kept[0][k] for k in ("panel", "damage_type", "severity")}]},
    ).json()
    assert saved["estimate"] == repriced
    assert [line["operation"] for line in saved["estimate"]["lines"]][0] == "replace"


def test_saving_ignores_prices_sent_by_the_client(client):
    estimated = post_estimate(client, photo(0)).json()
    forged = share_body(estimated) | {"estimate": {"totals": {"total": {"low": 1, "high": 1}}}}

    saved = client.post("/api/shares", json=forged).json()

    assert saved["estimate"] == estimated["estimate"]


def test_saving_needs_photos_the_server_has_seen(client):
    estimated = post_estimate(client, photo(0)).json()

    unknown = client.post("/api/shares", json=share_body(estimated) | {"photos": ["0" * 64]})
    malformed = client.post("/api/shares", json=share_body(estimated) | {"photos": ["abc"]})

    assert unknown.status_code == 404
    assert "Upload it again" in unknown.json()["detail"]
    assert malformed.status_code == 422


def test_saving_rejects_bad_input(client):
    estimated = post_estimate(client, photo(0)).json()
    damage = estimated["damages"][0]

    wrong_photo = share_body(estimated) | {"damages": [damage | {"photo": 3}]}
    long_text = share_body(estimated) | {"damages": [damage | {"description": "x" * 301}]}
    bad_vin = share_body(estimated, vin="123")

    for body in (wrong_photo, long_text, bad_vin):
        assert client.post("/api/shares", json=body).status_code == 422


def test_unknown_share_is_404(client):
    response = client.get("/api/shares/doesnotexist")

    assert response.status_code == 404
    assert "expired" in response.json()["detail"]


def test_saving_is_rate_limited(make_client):
    client = make_client(share_rate_limit_per_hour=1)
    body = share_body(post_estimate(client, photo(0)).json())

    assert client.post("/api/shares", json=body).status_code == 201
    assert client.post("/api/shares", json=body).status_code == 429
