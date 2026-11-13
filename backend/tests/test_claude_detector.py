import asyncio
import base64
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from app.detectors import (
    ClaudeDamageDetector,
    DetectionError,
    MockDamageDetector,
    build_detector,
)
from app.detectors.claude import FALLBACK_BETA
from app.detectors.mock import SAMPLE_REPORT
from app.images import prepare_image
from app.schemas import DamageReport
from tests.conftest import make_image, mock_settings


class FakeMessages:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, messages: FakeMessages):
        self.beta = SimpleNamespace(messages=messages)
        self.closed = False

    async def close(self):
        self.closed = True


def response(stop_reason="end_turn", parsed_output=SAMPLE_REPORT, model="claude-opus-5-5"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=parsed_output,
        model=model,
        usage=SimpleNamespace(input_tokens=1800, output_tokens=450),
    )


def api_error(cls, status_code: int):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx2.Response(status_code, request=request), body=None)


def run_detect(messages: FakeMessages):
    detector = ClaudeDamageDetector(FakeClient(messages), model="claude-opus-5-5", effort="medium")
    image = prepare_image(make_image(), max_edge=1568)
    return asyncio.run(detector.detect(image)), image


def test_sends_the_photo_and_returns_the_parsed_report():
    messages = FakeMessages(response(model="claude-opus-5-5"))

    detection, image = run_detect(messages)

    assert detection.report == SAMPLE_REPORT
    assert detection.model == "claude-opus-5-5"

    (call,) = messages.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is DamageReport
    assert call["output_config"] == {"effort": "medium"}
    assert call["fallbacks"] == "default"
    assert call["betas"] == [FALLBACK_BETA]

    image_block, text_block = call["messages"][0]["content"]
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert base64.standard_b64decode(image_block["source"]["data"]) == image.data
    assert text_block["type"] == "text"


def test_reports_token_usage_and_a_cache_key_tied_to_the_settings():
    detection, _ = run_detect(FakeMessages(response()))
    detector = ClaudeDamageDetector(FakeClient(FakeMessages()), model="m", effort="high")

    assert (detection.input_tokens, detection.output_tokens) == (1800, 450)
    assert detector.cache_key == "claude:m:high"


def test_reports_the_model_that_actually_answered():
    detection, _ = run_detect(FakeMessages(response(model="claude-opus-4-8")))

    assert detection.model == "claude-opus-4-8"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_incomplete_responses_raise(stop_reason):
    with pytest.raises(DetectionError) as exc_info:
        run_detect(FakeMessages(response(stop_reason=stop_reason)))

    assert not exc_info.value.retryable


def test_missing_parsed_output_raises():
    with pytest.raises(DetectionError, match="empty"):
        run_detect(FakeMessages(response(parsed_output=None)))


def test_invalid_report_raises():
    try:
        DamageReport.model_validate_json("{}")
    except ValidationError as exc:
        validation_error = exc

    with pytest.raises(DetectionError, match="malformed"):
        run_detect(FakeMessages(error=validation_error))


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (api_error(anthropic.RateLimitError, 429), True),
        (api_error(anthropic.InternalServerError, 500), True),
        (api_error(anthropic.AuthenticationError, 401), False),
        (api_error(anthropic.BadRequestError, 400), False),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), True),
    ],
)
def test_api_errors_become_detection_errors(error, retryable):
    with pytest.raises(DetectionError) as exc_info:
        run_detect(FakeMessages(error=error))

    assert exc_info.value.retryable is retryable


def test_aclose_closes_the_client():
    client = FakeClient(FakeMessages())
    detector = ClaudeDamageDetector(client, model="claude-opus-5-5", effort="medium")

    asyncio.run(detector.aclose())

    assert client.closed


def test_build_detector_picks_the_configured_detector():
    assert isinstance(build_detector(mock_settings()), MockDamageDetector)

    detector = build_detector(
        mock_settings(detector="claude", ANTHROPIC_API_KEY="sk-ant-test", claude_effort="low")
    )
    assert isinstance(detector, ClaudeDamageDetector)
    assert detector._effort == "low"
    asyncio.run(detector.aclose())
