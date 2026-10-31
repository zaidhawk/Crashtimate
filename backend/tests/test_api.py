import hashlib
import os

from app.detectors import DetectionError
from app.detectors.mock import SAMPLE_REPORT
from tests.conftest import make_image


class FailingDetector:
    name = "failing"

    def __init__(self, retryable: bool):
        self.retryable = retryable

    async def detect(self, image):
        raise DetectionError("Something went wrong.", retryable=self.retryable)

    async def aclose(self):
        pass


def upload(client, data: bytes, filename: str = "car.jpg", content_type: str = "image/jpeg"):
    return client.post("/api/analyze", files={"image": (filename, data, content_type)})


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "detector": "mock"}


def test_analyze_returns_report_and_metadata(client):
    raw = make_image(3000, 2000)

    response = upload(client, raw)

    assert response.status_code == 200
    body = response.json()
    assert body["report"] == SAMPLE_REPORT.model_dump(mode="json")
    meta = body["meta"]
    assert meta["detector"] == "mock"
    assert meta["model"] is None
    assert meta["image_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (meta["image_width"], meta["image_height"]) == (1568, 1045)
    assert meta["elapsed_ms"] >= 0


def test_non_image_upload_is_rejected(client):
    response = upload(client, b"hello", filename="notes.txt", content_type="text/plain")

    assert response.status_code == 415
    assert "not a readable image" in response.json()["detail"]


def test_oversized_upload_is_rejected(make_client):
    client = make_client(max_upload_mb=0.01)

    response = upload(client, os.urandom(20_000))

    assert response.status_code == 413
    assert "0.01 MB" in response.json()["detail"]


def test_missing_file_is_a_validation_error(client):
    assert client.post("/api/analyze").status_code == 422


def test_retryable_detector_failure_is_503(make_client):
    client = make_client(detector=FailingDetector(retryable=True))

    response = upload(client, make_image())

    assert response.status_code == 503
    assert response.json()["detail"] == "Something went wrong."


def test_permanent_detector_failure_is_502(make_client):
    client = make_client(detector=FailingDetector(retryable=False))

    assert upload(client, make_image()).status_code == 502


def test_cors_allows_the_frontend_origin(client):
    response = client.options(
        "/api/analyze",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
