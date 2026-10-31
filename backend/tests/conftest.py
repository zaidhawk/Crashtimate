import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.detectors import DamageDetector
from app.main import create_app


def make_image(
    width: int = 640, height: int = 480, fmt: str = "JPEG", mode: str = "RGB", **save_kwargs
) -> bytes:
    color = (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30)
    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, fmt, **save_kwargs)
    return buf.getvalue()


def mock_settings(**overrides) -> Settings:
    """Settings that ignore the developer's local .env file."""
    return Settings(_env_file=None, **{"detector": "mock", **overrides})


@pytest.fixture
def make_client():
    clients: list[TestClient] = []

    def _make(detector: DamageDetector | None = None, **settings) -> TestClient:
        client = TestClient(create_app(mock_settings(**settings), detector))
        client.__enter__()  # runs the app lifespan
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
