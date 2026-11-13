"""Score damage reports against labels.

Three questions, from loosest to strictest:

1. Damage type, per photo: did the detector say the photo shows a dent, a scratch, ...?
   This is multi-label classification, scored with precision, recall and F1 per type.
2. Location: do the boxes land on the labelled damage? A label counts as found when a
   predicted box of the same type overlaps it enough (IoU at or above the threshold), and a
   predicted box counts as right when it overlaps a label of the same type that much.
   The detector draws one box per panel while CarDD labels every mark, so one prediction may
   match several labels and the threshold is deliberately loose.
3. Panel: when the labels name panels, did the matched prediction name the same one?
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.schemas import BoundingBox, DamageReport, DamageType
from evals.dataset import Box, Label

DEFAULT_IOU_THRESHOLD = 0.3


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fn)

    @property
    def f1(self) -> float | None:
        return _ratio(2 * self.tp, 2 * self.tp + self.fp + self.fn)

    @property
    def support(self) -> int:
        """How many times the thing being scored really occurs."""
        return self.tp + self.fn

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)


@dataclass
class Scores:
    images: int = 0
    # Photos where the predicted set of damage types is exactly the labelled set.
    exact_matches: int = 0
    per_type: dict[DamageType, Counts] = field(
        default_factory=lambda: {damage_type: Counts() for damage_type in DamageType}
    )
    # tp = labels found, fn = labels missed.
    labels_located: Counts = field(default_factory=Counts)
    # tp = predicted boxes on a label, fp = predicted boxes on nothing.
    boxes_placed: Counts = field(default_factory=Counts)
    panels_right: int = 0
    panels_checked: int = 0

    @property
    def micro(self) -> Counts:
        """All damage types pooled: common types weigh more."""
        return sum(self.per_type.values(), Counts())

    @property
    def macro_f1(self) -> float | None:
        """The plain average of each type's F1, over the types that occur or were predicted."""
        values = [counts.f1 for counts in self.per_type.values() if counts.f1 is not None]
        return sum(values) / len(values) if values else None

    @property
    def exact_match_rate(self) -> float | None:
        return _ratio(self.exact_matches, self.images)

    @property
    def panel_accuracy(self) -> float | None:
        return _ratio(self.panels_right, self.panels_checked)


def iou(a: Box | BoundingBox, b: Box | BoundingBox) -> float:
    """Intersection over union: 1 for identical boxes, 0 for boxes that don't touch."""
    width = min(a.x_max, b.x_max) - max(a.x_min, b.x_min)
    height = min(a.y_max, b.y_max) - max(a.y_min, b.y_min)
    if width <= 0 or height <= 0:
        return 0.0
    intersection = width * height
    union = _area(a) + _area(b) - intersection
    return intersection / union if union > 0 else 0.0


def score(
    samples: Iterable[tuple[Sequence[Label], DamageReport]],
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> Scores:
    scores = Scores()
    for labels, report in samples:
        scores.images += 1
        _score_types(scores, labels, report)
        _score_boxes(scores, labels, report, iou_threshold)
    return scores


def _score_types(scores: Scores, labels: Sequence[Label], report: DamageReport) -> None:
    truth = {label.damage_type for label in labels}
    predicted = {damage.damage_type for damage in report.damages}
    for damage_type in DamageType:
        counts = scores.per_type[damage_type]
        if damage_type in truth and damage_type in predicted:
            counts.tp += 1
        elif damage_type in predicted:
            counts.fp += 1
        elif damage_type in truth:
            counts.fn += 1
    scores.exact_matches += truth == predicted


def _score_boxes(
    scores: Scores, labels: Sequence[Label], report: DamageReport, threshold: float
) -> None:
    predictions = [damage for damage in report.damages if damage.box is not None]

    for label in labels:
        overlaps = [
            (iou(label.box, damage.box), damage)
            for damage in predictions
            if damage.damage_type is label.damage_type
        ]
        best_overlap, best = max(overlaps, key=lambda pair: pair[0], default=(0.0, None))
        if best is None or best_overlap < threshold:
            scores.labels_located.fn += 1
            continue
        scores.labels_located.tp += 1
        if label.panel is not None:
            scores.panels_checked += 1
            scores.panels_right += best.panel is label.panel

    for damage in predictions:
        on_a_label = any(
            label.damage_type is damage.damage_type and iou(label.box, damage.box) >= threshold
            for label in labels
        )
        if on_a_label:
            scores.boxes_placed.tp += 1
        else:
            scores.boxes_placed.fp += 1


def _area(box: Box | BoundingBox) -> float:
    return max(box.x_max - box.x_min, 0.0) * max(box.y_max - box.y_min, 0.0)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
