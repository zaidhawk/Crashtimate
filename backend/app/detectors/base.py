from dataclasses import dataclass
from typing import Protocol

from app.images import PreparedImage
from app.schemas import DamageReport


@dataclass(frozen=True)
class Detection:
    report: DamageReport
    # The model that produced the report, if any. Can differ from the requested model
    # when a server-side fallback handled the request.
    model: str | None


class DetectionError(Exception):
    """The detector could not produce a report. The message is safe to show to users."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class DamageDetector(Protocol):
    name: str

    async def detect(self, image: PreparedImage) -> Detection: ...

    async def aclose(self) -> None: ...
