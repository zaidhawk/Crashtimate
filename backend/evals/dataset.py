"""Load a labelled photo set in COCO format, which is how CarDD is published."""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from app.schemas import DamageType, Panel


class DatasetError(ValueError):
    pass


@dataclass(frozen=True)
class Box:
    """Fractions of the image size, like the detector's BoundingBox."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def area(self) -> float:
        return max(self.x_max - self.x_min, 0.0) * max(self.y_max - self.y_min, 0.0)


@dataclass(frozen=True)
class Label:
    damage_type: DamageType
    box: Box
    # CarDD doesn't label panels. Hand-labelled sets can add one per annotation.
    panel: Panel | None = None


@dataclass(frozen=True)
class Sample:
    image_id: str
    path: Path
    labels: tuple[Label, ...]


def load_coco(annotations: Path, images_dir: Path) -> list[Sample]:
    """Read a COCO annotations file. Categories are matched to damage types by name.

    Category names are compared ignoring case, spaces and dashes, so CarDD's "glass shatter"
    is DamageType.GLASS_SHATTER. An annotation may carry a "panel" (or attributes.panel)
    naming one of our panels. Photos with no annotations are kept: they show no damage.
    """
    try:
        coco = json.loads(annotations.read_text(encoding="utf-8"))
        categories = {
            category["id"]: _damage_type(category["name"]) for category in coco["categories"]
        }
        labels: dict[object, list[Label]] = {image["id"]: [] for image in coco["images"]}
        sizes = {image["id"]: (image["width"], image["height"]) for image in coco["images"]}
        for annotation in coco["annotations"]:
            width, height = sizes[annotation["image_id"]]
            x, y, box_width, box_height = annotation["bbox"]
            labels[annotation["image_id"]].append(
                Label(
                    damage_type=categories[annotation["category_id"]],
                    box=Box(
                        x_min=_clamp(x / width),
                        y_min=_clamp(y / height),
                        x_max=_clamp((x + box_width) / width),
                        y_max=_clamp((y + box_height) / height),
                    ),
                    panel=_panel(annotation),
                )
            )
        return [
            Sample(
                image_id=str(image["id"]),
                path=images_dir / image["file_name"],
                labels=tuple(labels[image["id"]]),
            )
            for image in coco["images"]
        ]
    except (KeyError, TypeError, ZeroDivisionError, json.JSONDecodeError) as exc:
        raise DatasetError(
            f"{annotations} isn't a readable COCO annotations file: {exc!r}"
        ) from exc


def sample(samples: list[Sample], limit: int | None, seed: int) -> list[Sample]:
    """A repeatable random subset, so runs of different models see the same photos."""
    if limit is None or limit >= len(samples):
        return samples
    return random.Random(seed).sample(samples, limit)


def _damage_type(name: str) -> DamageType:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return DamageType(key)
    except ValueError:
        known = ", ".join(DamageType)
        raise DatasetError(f"Unknown damage category {name!r}. Expected one of: {known}.") from None


def _panel(annotation: dict) -> Panel | None:
    name = annotation.get("panel") or (annotation.get("attributes") or {}).get("panel")
    if not name:
        return None
    try:
        return Panel(name)
    except ValueError:
        raise DatasetError(
            f"Unknown panel {name!r} in annotation {annotation.get('id')}."
        ) from None


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)
