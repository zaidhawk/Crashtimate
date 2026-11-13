import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.detectors import DamageDetector
from app.main import create_app
from app.pricing import CostBook, load_cost_book
from app.vehicles import Vehicle, VinNotFoundError

# Real VINs with valid check digits.
CIVIC_VIN = "1HGCM82633A004352"
OTHER_VIN = "1M8GDM9AXKP042788"


def make_image(
    width: int = 640, height: int = 480, fmt: str = "JPEG", mode: str = "RGB", **save_kwargs
) -> bytes:
    color = (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30)
    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, fmt, **save_kwargs)
    return buf.getvalue()


def mock_settings(**overrides) -> Settings:
    """Settings that ignore the developer's local .env file."""
    return Settings(
        _env_file=None, **{"detector": "mock", "database_path": ":memory:", **overrides}
    )


class FakeVinDecoder:
    def __init__(self, vehicles: dict[str, Vehicle] | None = None, error: Exception | None = None):
        self.vehicles = vehicles or {}
        self.error = error
        self.calls: list[str] = []

    async def decode(self, vin: str) -> Vehicle:
        self.calls.append(vin)
        if self.error:
            raise self.error
        if vin not in self.vehicles:
            raise VinNotFoundError("No vehicle was found for that VIN.")
        return self.vehicles[vin]


@pytest.fixture(scope="session")
def cost_book() -> CostBook:
    return load_cost_book()


@pytest.fixture
def make_client():
    clients: list[TestClient] = []

    def _make(
        detector: DamageDetector | None = None,
        vin_decoder: FakeVinDecoder | None = None,
        **settings,
    ) -> TestClient:
        app = create_app(mock_settings(**settings), detector, vin_decoder or FakeVinDecoder())
        client = TestClient(app)
        client.__enter__()  # runs the app lifespan
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
