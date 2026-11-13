"""Score saved evaluation runs and print the results as Markdown tables.

    python -m evals.report ../eval/results/*.jsonl --annotations data/annotations.json \\
        --input-price 5 --output-price 25

Give one results file per model to get a comparison table. Prices are in US dollars per
million tokens; leave them out to report tokens only.
"""

import argparse
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.schemas import DamageType
from evals.dataset import DatasetError, Label, load_coco
from evals.metrics import DEFAULT_IOU_THRESHOLD, Scores, score
from evals.run import Record, read_records


@dataclass
class RunSummary:
    name: str
    scores: Scores
    errors: int
    # Photos the detector said weren't a vehicle or were too poor to assess.
    declined: int
    median_ms: float | None
    p95_ms: float | None
    input_tokens: float | None
    output_tokens: float | None

    def cost_per_photo(self, input_price: float | None, output_price: float | None) -> float | None:
        if None in (input_price, output_price, self.input_tokens, self.output_tokens):
            return None
        return (self.input_tokens * input_price + self.output_tokens * output_price) / 1_000_000


def summarize(
    name: str,
    records: Sequence[Record],
    labels: dict[str, tuple[Label, ...]],
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> RunSummary:
    """Score one run. If a photo appears more than once (a retry), the last attempt counts."""
    latest = {record.image_id: record for record in records if record.image_id in labels}
    scored = [record for record in latest.values() if record.report is not None]
    times = sorted(record.elapsed_ms for record in scored)
    return RunSummary(
        name=name,
        scores=score(
            ((labels[record.image_id], record.report) for record in scored), iou_threshold
        ),
        errors=len(latest) - len(scored),
        declined=sum(
            not record.report.is_vehicle or record.report.image_quality == "unusable"
            for record in scored
        ),
        median_ms=statistics.median(times) if times else None,
        p95_ms=times[min(len(times) - 1, round(0.95 * (len(times) - 1)))] if times else None,
        input_tokens=_mean([record.input_tokens for record in scored]),
        output_tokens=_mean([record.output_tokens for record in scored]),
    )


def comparison_table(
    runs: Sequence[RunSummary], input_price: float | None = None, output_price: float | None = None
) -> str:
    """One row per run: the headline numbers side by side."""
    header = (
        "| Run | Photos | Precision | Recall | F1 (micro) | F1 (macro) | Exact match "
        "| Labels located | Boxes on a label | Panel accuracy | Median time | Cost per photo |"
    )
    rows = [header, "|" + "---|" * 12]
    for run in runs:
        scores = run.scores
        cost = run.cost_per_photo(input_price, output_price)
        rows.append(
            "| "
            + " | ".join(
                [
                    run.name,
                    str(scores.images),
                    _percent(scores.micro.precision),
                    _percent(scores.micro.recall),
                    _percent(scores.micro.f1),
                    _percent(scores.macro_f1),
                    _percent(scores.exact_match_rate),
                    _percent(scores.labels_located.recall),
                    _percent(scores.boxes_placed.precision),
                    _percent(scores.panel_accuracy),
                    "n/a" if run.median_ms is None else f"{run.median_ms / 1000:.1f} s",
                    "n/a" if cost is None else f"${cost:.4f}",
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def per_type_table(run: RunSummary) -> str:
    rows = ["| Damage type | Photos with it | Precision | Recall | F1 |", "|---|---|---|---|---|"]
    for damage_type in DamageType:
        counts = run.scores.per_type[damage_type]
        rows.append(
            f"| {damage_type.value.replace('_', ' ')} | {counts.support} "
            f"| {_percent(counts.precision)} | {_percent(counts.recall)} | {_percent(counts.f1)} |"
        )
    return "\n".join(rows)


def render(
    runs: Sequence[RunSummary],
    iou_threshold: float,
    input_price: float | None = None,
    output_price: float | None = None,
) -> str:
    parts = [comparison_table(runs, input_price, output_price)]
    for run in runs:
        details = [f"{run.errors} failed", f"{run.declined} declined as not assessable"]
        if run.input_tokens is not None and run.output_tokens is not None:
            details.append(
                f"{run.input_tokens:.0f} input and {run.output_tokens:.0f} output tokens per photo"
            )
        if run.p95_ms is not None:
            details.append(f"95% of photos within {run.p95_ms / 1000:.1f} s")
        parts.append(f"### {run.name}\n\n{', '.join(details)}.\n\n{per_type_table(run)}")
    parts.append(
        "Precision, recall and F1 are per photo: did the detector report each type of damage "
        "the photo is labelled with. A label is located when a predicted box of the same type "
        f"overlaps it with IoU of at least {iou_threshold:g}."
    )
    return "\n\n".join(parts) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("results", type=Path, nargs="+", help="results files from evals.run")
    parser.add_argument("--annotations", type=Path, required=True, help="COCO annotations JSON")
    parser.add_argument("--iou", type=float, default=DEFAULT_IOU_THRESHOLD)
    parser.add_argument("--input-price", type=float, help="USD per million input tokens")
    parser.add_argument("--output-price", type=float, help="USD per million output tokens")
    args = parser.parse_args(argv)

    try:
        # Image paths aren't needed for scoring, only the labels.
        samples = load_coco(args.annotations, Path("."))
    except (OSError, DatasetError) as exc:
        print(f"Couldn't load the dataset: {exc}", file=sys.stderr)
        return 1
    labels = {item.image_id: item.labels for item in samples}

    runs = [summarize(path.stem, read_records(path), labels, args.iou) for path in args.results]
    print(render(runs, args.iou, args.input_price, args.output_price))
    return 0


def _mean(values: Sequence[int | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
