import base64
import logging

import anthropic
from pydantic import ValidationError

from app.detectors.base import Detection, DetectionError
from app.detectors.prompt import SYSTEM_PROMPT, USER_PROMPT
from app.images import PreparedImage
from app.schemas import DamageReport

logger = logging.getLogger(__name__)

# Lets the API retry on Anthropic's recommended fallback model if a safety classifier
# declines a request (false positives happen), instead of failing the upload.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeDamageDetector:
    """Sends the photo to Claude and gets back a DamageReport via structured outputs."""

    name = "claude"

    def __init__(self, client: anthropic.AsyncAnthropic, *, model: str, effort: str) -> None:
        self._client = client
        self._model = model
        self._effort = effort
        self.cache_key = f"claude:{model}:{effort}"

    async def detect(self, image: PreparedImage) -> Detection:
        image_b64 = base64.standard_b64encode(image.data).decode("ascii")
        try:
            response = await self._client.beta.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image.media_type,
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": USER_PROMPT},
                        ],
                    }
                ],
                output_config={"effort": self._effort},
                output_format=DamageReport,
                fallbacks="default",
                betas=[FALLBACK_BETA],
            )
        except anthropic.RateLimitError as exc:
            raise DetectionError(
                "The damage analysis service is busy. Try again in a minute.", retryable=True
            ) from exc
        except anthropic.APIStatusError as exc:
            logger.error("Claude API error %s: %s", exc.status_code, exc.message)
            raise DetectionError(
                "The damage analysis service returned an error.", retryable=exc.status_code >= 500
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise DetectionError(
                "Could not reach the damage analysis service.", retryable=True
            ) from exc
        except ValidationError as exc:
            logger.error("Claude returned a report that failed validation: %s", exc)
            raise DetectionError("The damage analysis came back malformed.") from exc

        if response.stop_reason == "refusal":
            raise DetectionError("This photo could not be analyzed.")
        if response.stop_reason == "max_tokens":
            raise DetectionError("The damage analysis was cut off before it finished.")
        if response.parsed_output is None:
            raise DetectionError("The damage analysis came back empty.")

        usage = getattr(response, "usage", None)
        return Detection(
            report=response.parsed_output,
            model=response.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    async def aclose(self) -> None:
        await self._client.close()
