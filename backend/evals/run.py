"""Run a detector over a labelled photo set and save what it reported for each photo.

    python -m evals.run --annotations data/annotations.json --images data/images \\
        --out ../eval/results/opus-5-5-medium.jsonl --limit 200

The detector comes from the same settings as the API (CRASHTIMATE_DETECTOR,
CRASHTIMATE_CLAUDE_MODEL, CRASHTIMATE_CLAUDE_EFFORT, ANTHROPIC_API_KEY). Results are appended
one JSON line per photo as they finish, and photos already in the file are skipped, so an
interrupted run picks up where it stopped without paying for the same photo twice.
"""

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from app.config import Settings
from app.detectors import DamageDetector, DetectionError, build_detector
from app.images import InvalidImageError, prepare_image
from app.schemas import DamageReport
from evals.dataset import DatasetError, Sample, load_coco, sample


class Record(BaseModel):
    """One photo's outcome: either a report or an error."""

    image_id: str
    detector: str
    model: str | None = None
    elapsed_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    report: DamageReport | None = None
    error: str | None = None


def read_records(path: Path) -> list[Record]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Record.model_validate_json(line) for line in lines if line.strip()]


async def evaluate_sample(item: Sample, detector: DamageDetector, max_edge: int) -> Record:
    try:
        image = await asyncio.to_thread(lambda: prepare_image(item.path.read_bytes(), max_edge))
    except (OSError, InvalidImageError) as exc:
        return Record(image_id=item.image_id, detector=detector.cache_key, error=str(exc))

    started = time.perf_counter()
    try:
        detection = await detector.detect(image)
    except DetectionError as exc:
        return Record(image_id=item.image_id, detector=detector.cache_key, error=str(exc))
    return Record(
        image_id=item.image_id,
        detector=detector.cache_key,
        model=detection.model,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        input_tokens=detection.input_tokens,
        output_tokens=detection.output_tokens,
        report=detection.report,
    )


async def run(
    samples: Sequence[Sample],
    detector: DamageDetector,
    out: Path,
    *,
    max_edge: int,
    concurrency: int = 4,
) -> list[Record]:
    """Evaluate every sample not already in `out`, a few at a time. Returns the new records."""
    done = {record.image_id for record in read_records(out) if record.error is None}
    todo = [item for item in samples if item.image_id not in done]
    out.parent.mkdir(parents=True, exist_ok=True)

    limiter = asyncio.Semaphore(concurrency)
    records: list[Record] = []

    async def one(item: Sample) -> None:
        async with limiter:
            record = await evaluate_sample(item, detector, max_edge)
        records.append(record)
        # Written as each photo finishes, so nothing is lost if the run is interrupted.
        with out.open("a", encoding="utf-8") as file:
            file.write(record.model_dump_json() + "\n")
        status = f"error: {record.error}" if record.error else f"{record.elapsed_ms} ms"
        print(f"[{len(records)}/{len(todo)}] {item.path.name}: {status}", file=sys.stderr)

    await asyncio.gather(*(one(item) for item in todo))
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--annotations", type=Path, required=True, help="COCO annotations JSON")
    parser.add_argument("--images", type=Path, required=True, help="folder holding the photos")
    parser.add_argument("--out", type=Path, required=True, help="results file (JSON lines)")
    parser.add_argument("--limit", type=int, help="evaluate a random subset of this many photos")
    parser.add_argument("--seed", type=int, default=0, help="which random subset (default 0)")
    parser.add_argument("--concurrency", type=int, default=4, help="photos analysed at once")
    args = parser.parse_args(argv)

    try:
        samples = sample(load_coco(args.annotations, args.images), args.limit, args.seed)
    except (OSError, DatasetError) as exc:
        print(f"Couldn't load the dataset: {exc}", file=sys.stderr)
        return 1

    settings = Settings()
    detector = build_detector(settings)

    async def go() -> list[Record]:
        try:
            return await run(
                samples,
                detector,
                args.out,
                max_edge=settings.max_image_edge,
                concurrency=args.concurrency,
            )
        finally:
            await detector.aclose()

    records = asyncio.run(go())
    failed = sum(record.error is not None for record in records)
    print(
        json.dumps({"evaluated": len(records), "failed": failed, "out": str(args.out)}),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
