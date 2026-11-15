"""Run a folder of photos through several Claude models and print what each one reported.

    python -m evals.compare ../../crash-photos --models claude-haiku-5-5 claude-opus-5-5

For unlabelled photos, where there is nothing to score against: the output puts each model's
damage list, priced estimate, time and cost side by side so a person can judge them. Results
are saved per model in `--out` (default: a `results` folder beside the photos) and photos
already there are skipped, so running it again costs nothing.
"""

import argparse
import asyncio
import statistics
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.config import Settings
from app.detectors import DamageDetector, build_detector
from app.pricing import CostBook, DamageInput, build_estimate, load_cost_book
from app.schemas import ImageQuality
from app.vehicles import Vehicle
from evals.dataset import Sample
from evals.run import Record, read_records, run

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# US dollars per million tokens (input, output), for the cost column.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def find_photos(folder: Path) -> list[Sample]:
    paths = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in PHOTO_SUFFIXES
    )
    return [Sample(image_id=path.name, path=path, labels=()) for path in paths]


async def compare(
    samples: Sequence[Sample],
    detectors: Mapping[str, DamageDetector],
    out_dir: Path,
    *,
    max_edge: int,
    concurrency: int = 2,
) -> dict[str, dict[str, Record]]:
    """Run every photo through every detector. Returns the latest record per photo, per name."""
    results: dict[str, dict[str, Record]] = {}
    for name, detector in detectors.items():
        out = out_dir / f"{name}.jsonl"
        await run(samples, detector, out, max_edge=max_edge, concurrency=concurrency)
        results[name] = {record.image_id: record for record in read_records(out)}
    return results


def cost(record: Record, model: str) -> float | None:
    """What the request cost in US dollars, if the model's price is known."""
    if model not in PRICES or record.input_tokens is None or record.output_tokens is None:
        return None
    input_price, output_price = PRICES[model]
    return (record.input_tokens * input_price + record.output_tokens * output_price) / 1_000_000


def render(
    samples: Sequence[Sample],
    results: Mapping[str, Mapping[str, Record]],
    models: Mapping[str, str],
    book: CostBook,
) -> str:
    """Markdown: a totals table, then one table per photo with a row per model.

    `models` maps each name in `results` to the model it ran, for looking up prices.
    """
    parts = [_totals_table(samples, results, models)]
    for item in samples:
        rows = ["| Model | Damage found | Estimate | Time | Cost |", "|---|---|---|---|---|"]
        for name, records in results.items():
            record = records.get(item.image_id)
            rows.append(
                f"| {name} | {_findings(record)} | {_estimate(record, book)} "
                f"| {_seconds(record)} | {_dollars(record and cost(record, models[name]))} |"
            )
        parts.append(f"### {item.image_id}\n\n" + "\n".join(rows))
    return "\n\n".join(parts) + "\n"


def _totals_table(
    samples: Sequence[Sample],
    results: Mapping[str, Mapping[str, Record]],
    models: Mapping[str, str],
) -> str:
    rows = [
        "| Model | Photos | Failed | Damage entries | Median time | Total cost | Cost per photo |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, records in results.items():
        done = [records[item.image_id] for item in samples if item.image_id in records]
        ok = [record for record in done if record.report is not None]
        costs = [cost(record, models[name]) for record in ok]
        known = [amount for amount in costs if amount is not None]
        total = sum(known) if known and len(known) == len(costs) else None
        median = statistics.median(record.elapsed_ms for record in ok) / 1000 if ok else None
        rows.append(
            f"| {name} | {len(done)} | {len(done) - len(ok)} "
            f"| {sum(len(record.report.damages) for record in ok)} "
            f"| {'n/a' if median is None else f'{median:.1f} s'} "
            f"| {_dollars(total)} | {_dollars(total / len(ok) if total is not None else None)} |"
        )
    return "\n".join(rows)


def _findings(record: Record | None) -> str:
    if record is None:
        return "not run"
    if record.report is None:
        return f"error: {record.error}"
    report = record.report
    if not report.is_vehicle:
        return "not a vehicle"
    if report.image_quality is ImageQuality.UNUSABLE:
        return "photo unusable"
    if not report.damages:
        return "no damage"
    return "<br>".join(
        f"{_words(damage.panel)}: {damage.severity.value} {_words(damage.damage_type)} "
        f"({damage.confidence:.0%})"
        for damage in report.damages
    )


def _estimate(record: Record | None, book: CostBook) -> str:
    if record is None or record.report is None or not record.report.damages:
        return "n/a"
    damages = [
        DamageInput(
            panel=damage.panel,
            damage_type=damage.damage_type,
            severity=damage.severity,
            confidence=damage.confidence,
        )
        for damage in record.report.damages
    ]
    total = build_estimate(damages, Vehicle(), book).totals.total
    return f"${total.low:,}–${total.high:,}"


def _seconds(record: Record | None) -> str:
    if record is None or record.report is None:
        return "n/a"
    return f"{record.elapsed_ms / 1000:.1f} s"


def _dollars(amount: float | None) -> str:
    return "n/a" if amount is None else f"${amount:.4f}"


def _words(value: str) -> str:
    return value.replace("_", " ")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("photos", type=Path, help="folder of photos")
    parser.add_argument("--models", nargs="+", default=["claude-haiku-5-5", "claude-opus-5-5"])
    parser.add_argument("--out", type=Path, help="results folder (default: <photos>/results)")
    parser.add_argument(
        "--max-photos", type=int, default=15, help="refuse to run on more photos than this"
    )
    parser.add_argument("--concurrency", type=int, default=2, help="photos analysed at once")
    args = parser.parse_args(argv)

    if not args.photos.is_dir():
        print(f"{args.photos} isn't a folder.", file=sys.stderr)
        return 1
    samples = find_photos(args.photos)
    if not samples:
        print(f"No photos (jpg, png or webp) in {args.photos}.", file=sys.stderr)
        return 1
    if len(samples) > args.max_photos:
        print(
            f"{len(samples)} photos is more than --max-photos {args.max_photos}. "
            "Raise it if you mean to pay for that many.",
            file=sys.stderr,
        )
        return 1

    settings = Settings()
    if settings.anthropic_api_key is None:
        print("ANTHROPIC_API_KEY isn't set in backend/.env.", file=sys.stderr)
        return 1

    # Results files are named after the model and effort, like the detector's cache key.
    models = {f"{model}-{settings.claude_effort}": model for model in args.models}
    detectors = {
        name: build_detector(settings.model_copy(update={"detector": "claude", "claude_model": m}))
        for name, m in models.items()
    }

    async def go() -> dict[str, dict[str, Record]]:
        try:
            return await compare(
                samples,
                detectors,
                args.out or args.photos / "results",
                max_edge=settings.max_image_edge,
                concurrency=args.concurrency,
            )
        finally:
            for detector in detectors.values():
                await detector.aclose()

    results = asyncio.run(go())
    sys.stdout.reconfigure(encoding="utf-8")
    print(render(samples, results, models, load_cost_book()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
