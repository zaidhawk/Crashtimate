import anthropic

from app.config import Settings
from app.detectors.base import DamageDetector, Detection, DetectionError
from app.detectors.claude import ClaudeDamageDetector
from app.detectors.mock import MockDamageDetector

__all__ = [
    "ClaudeDamageDetector",
    "DamageDetector",
    "Detection",
    "DetectionError",
    "MockDamageDetector",
    "build_detector",
]


def build_detector(settings: Settings) -> DamageDetector:
    if settings.detector == "mock":
        return MockDamageDetector()

    key = settings.anthropic_api_key
    client = anthropic.AsyncAnthropic(api_key=key.get_secret_value() if key else None)
    return ClaudeDamageDetector(client, model=settings.claude_model, effort=settings.claude_effort)
