import asyncio
import json

import pytest

from app.detectors import Detection, DetectionError, MockDamageDetector
from app.detectors.mock import SAMPLE_REPORT
from app.schemas import (
    BoundingBox,
    DamageItem,
    DamageReport,
    DamageType,
    ImageQuality,
    Panel,
    Severity,
    ViewAngle,
)
from evals import add_panels as add_panels_module
from evals import compare as compare_module
from evals import report as report_module
from evals.dataset import Box, DatasetError, Label, load_coco, sample
from evals.metrics import Counts, iou, score
from evals.report import render, summarize
from evals.run import Record, read_records, run
from tests.conftest import make_image, mock_settings

DENT, SCRATCH, CRACK = DamageType.DENT, DamageType.SCRATCH, DamageType.CRACK


def damage(damage_type=DENT, box=(0.1, 0.1, 0.5, 0.5), panel=Panel.HOOD):
    return DamageItem(
        panel=panel,
        damage_type=damage_type,
        severity=Severity.MODERATE,
        description="",
        confidence=0.9,
        box=BoundingBox(x_min=box[0], y_min=box[1], x_max=box[2], y_max=box[3]) if box else None,
    )


def report(*damages, is_vehicle=True, quality=ImageQuality.GOOD):
    return DamageReport(
        is_vehicle=is_vehicle,
        image_quality=quality,
        view=ViewAngle.FRONT,
        damages=list(damages),
        summary="",
    )


def label(damage_type=DENT, box=(0.1, 0.1, 0.5, 0.5), panel=None):
    return Label(damage_type, Box(*box), panel)


# Metrics


def test_iou():
    assert iou(Box(0, 0, 1, 1), Box(0, 0, 1, 1)) == 1
    assert iou(Box(0, 0, 0.5, 0.5), Box(0.5, 0.5, 1, 1)) == 0
    # Two unit-width boxes sharing half their area: 0.5 / 1.5
    assert iou(Box(0, 0, 0.5, 1), Box(0.25, 0, 0.75, 1)) == pytest.approx(1 / 3)
    assert iou(Box(0.2, 0.2, 0.2, 0.2), Box(0.2, 0.2, 0.2, 0.2)) == 0


def test_counts_ratios():
    counts = Counts(tp=6, fp=2, fn=4)

    assert counts.precision == 0.75
    assert counts.recall == 0.6
    assert counts.f1 == pytest.approx(2 * 0.75 * 0.6 / (0.75 + 0.6))
    assert counts.support == 10
    assert Counts().precision is None and Counts().recall is None and Counts().f1 is None


def test_damage_types_are_scored_per_photo():
    scores = score(
        [
            ([label(DENT), label(DENT), label(SCRATCH)], report(damage(DENT), damage(CRACK))),
            ([label(SCRATCH)], report(damage(SCRATCH))),
            ([], report()),
        ]
    )

    assert scores.images == 3
    # Two labelled dents in one photo are one "this photo has a dent".
    assert scores.per_type[DENT] == Counts(tp=1)
    assert scores.per_type[SCRATCH] == Counts(tp=1, fn=1)
    assert scores.per_type[CRACK] == Counts(fp=1)
    assert scores.micro == Counts(tp=2, fp=1, fn=1)
    assert scores.exact_matches == 2
    assert scores.exact_match_rate == pytest.approx(2 / 3)
    # dent 1.0, scratch 2/3, crack 0.0; types that never come up are left out.
    assert scores.macro_f1 == pytest.approx((1 + 2 / 3 + 0) / 3)


def test_boxes_are_matched_by_type_and_overlap():
    labels = [
        label(DENT, (0.1, 0.1, 0.5, 0.5)),
        label(DENT, (0.6, 0.6, 0.9, 0.9)),  # nothing predicted here
        label(SCRATCH, (0.1, 0.1, 0.5, 0.5)),  # a dent box overlaps, but the type is wrong
    ]
    predicted = report(
        damage(DENT, (0.12, 0.12, 0.5, 0.5)),
        damage(DENT, (0.0, 0.8, 0.1, 0.9)),  # on nothing
        damage(CRACK, None),  # no box: can't be placed, so it's left out
    )

    scores = score([(labels, predicted)])

    assert scores.labels_located == Counts(tp=1, fn=2)
    assert scores.boxes_placed == Counts(tp=1, fp=1)


def test_one_predicted_box_can_cover_several_labels():
    labels = [label(SCRATCH, (0.1, 0.1, 0.5, 0.3)), label(SCRATCH, (0.1, 0.3, 0.5, 0.5))]

    scores = score([(labels, report(damage(SCRATCH, (0.1, 0.1, 0.5, 0.5))))])

    assert scores.labels_located == Counts(tp=2)
    assert scores.boxes_placed == Counts(tp=1)


def test_iou_threshold_is_configurable():
    sample_ = [([label(DENT, (0, 0, 0.5, 1))], report(damage(DENT, (0.25, 0, 0.75, 1))))]

    assert score(sample_, iou_threshold=0.3).labels_located.tp == 1
    assert score(sample_, iou_threshold=0.5).labels_located.tp == 0


def test_panel_accuracy_uses_located_labels_that_name_a_panel():
    labels = [
        label(DENT, (0.1, 0.1, 0.5, 0.5), Panel.HOOD),
        label(SCRATCH, (0.5, 0.5, 0.9, 0.9), Panel.ROOF),
        label(CRACK, (0.0, 0.0, 0.1, 0.1), Panel.TRUNK),  # not located, so not checked
    ]
    predicted = report(
        damage(DENT, (0.1, 0.1, 0.5, 0.5), Panel.HOOD),
        damage(SCRATCH, (0.5, 0.5, 0.9, 0.9), Panel.TRUNK),
    )

    scores = score([(labels, predicted)])

    assert (scores.panels_right, scores.panels_checked) == (1, 2)
    assert scores.panel_accuracy == 0.5
    assert score([([label()], report(damage()))]).panel_accuracy is None


# Dataset


def write_coco(tmp_path, **overrides):
    coco = {
        "images": [
            {"id": 1, "file_name": "a.jpg", "width": 1000, "height": 500},
            {"id": 2, "file_name": "b.jpg", "width": 800, "height": 600},
        ],
        "categories": [{"id": 1, "name": "dent"}, {"id": 4, "name": "Glass Shatter"}],
        "annotations": [
            {"id": 10, "image_id": 1, "category_id": 1, "bbox": [100, 50, 400, 200]},
            {
                "id": 11,
                "image_id": 1,
                "category_id": 4,
                "bbox": [900, 400, 200, 200],
                "attributes": {"panel": "windshield"},
            },
        ],
        **overrides,
    }
    path = tmp_path / "annotations.json"
    path.write_text(json.dumps(coco), encoding="utf-8")
    return path


def test_load_coco_converts_boxes_to_fractions(tmp_path):
    first, second = load_coco(write_coco(tmp_path), tmp_path / "images")

    assert first.image_id == "1"
    assert first.path == tmp_path / "images" / "a.jpg"
    assert first.labels[0] == Label(DENT, Box(0.1, 0.1, 0.5, 0.5))
    # Category names are matched loosely, and boxes are clipped to the image.
    assert first.labels[1] == Label(
        DamageType.GLASS_SHATTER, Box(0.9, 0.8, 1.0, 1.0), Panel.WINDSHIELD
    )
    assert second.labels == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"categories": [{"id": 1, "name": "rust"}, {"id": 4, "name": "dent"}]},
        {
            "annotations": [
                {"id": 1, "image_id": 1, "category_id": 1, "bbox": [0, 0, 1, 1], "panel": "wing"}
            ]
        },
        {"annotations": [{"id": 1, "image_id": 9, "category_id": 1, "bbox": [0, 0, 1, 1]}]},
        {"images": "oops"},
    ],
    ids=["unknown category", "unknown panel", "unknown image", "wrong shape"],
)
def test_load_coco_rejects_bad_files(tmp_path, overrides):
    with pytest.raises(DatasetError):
        load_coco(write_coco(tmp_path, **overrides), tmp_path)


def test_sample_is_repeatable(tmp_path):
    samples = load_coco(write_coco(tmp_path), tmp_path) * 10

    assert sample(samples, 5, seed=1) == sample(samples, 5, seed=1)
    assert len(sample(samples, 5, seed=1)) == 5
    assert sample(samples, None, seed=1) is samples
    assert sample(samples, 100, seed=1) is samples


# Runner and report


class FlakyDetector(MockDamageDetector):
    """Fails on the photos whose turn it is to fail."""

    def __init__(self, failures: set[int] = frozenset()):
        self.failures = failures
        self.calls = 0

    async def detect(self, image):
        self.calls += 1
        if self.calls in self.failures:
            raise DetectionError("The service is busy.", retryable=True)
        return Detection(SAMPLE_REPORT, model="test-model", input_tokens=1000, output_tokens=200)


@pytest.fixture
def dataset(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.jpg").write_bytes(make_image())
    (images / "b.jpg").write_bytes(make_image(width=320))
    return load_coco(write_coco(tmp_path), images)


def test_run_saves_a_record_per_photo(dataset, tmp_path):
    out = tmp_path / "results" / "run.jsonl"

    records = asyncio.run(run(dataset, FlakyDetector(), out, max_edge=1568))

    assert {record.image_id for record in records} == {"1", "2"}
    saved = read_records(out)
    assert len(saved) == 2
    assert saved[0].report == SAMPLE_REPORT
    assert (saved[0].model, saved[0].input_tokens, saved[0].output_tokens) == (
        "test-model",
        1000,
        200,
    )


def test_run_resumes_and_retries_only_what_failed(dataset, tmp_path):
    out = tmp_path / "run.jsonl"
    asyncio.run(run(dataset, FlakyDetector(failures={1}), out, max_edge=1568, concurrency=1))
    assert [record.error for record in read_records(out)] == ["The service is busy.", None]

    retry = FlakyDetector()
    records = asyncio.run(run(dataset, retry, out, max_edge=1568))

    assert retry.calls == 1
    assert [record.image_id for record in records] == ["1"]
    assert asyncio.run(run(dataset, retry, out, max_edge=1568)) == []


def test_run_records_unreadable_photos_as_errors(dataset, tmp_path):
    dataset[1].path.write_bytes(b"not an image")
    detector = FlakyDetector()

    records = asyncio.run(run(dataset, detector, tmp_path / "run.jsonl", max_edge=1568))

    assert detector.calls == 1
    assert sorted(record.error or "" for record in records) == [
        "",
        "The file is not a readable image.",
    ]


def test_summary_and_report(dataset):
    labels = {item.image_id: item.labels for item in dataset}
    hit = report(damage(DENT, (0.1, 0.1, 0.5, 0.5)), damage(DamageType.GLASS_SHATTER, None))
    records = [
        Record(image_id="1", detector="x", error="busy"),
        # The retry of photo 1 replaces the failed attempt.
        Record(
            image_id="1",
            detector="x",
            report=hit,
            elapsed_ms=4000,
            input_tokens=1500,
            output_tokens=500,
        ),
        Record(
            image_id="2",
            detector="x",
            report=report(is_vehicle=False),
            elapsed_ms=2000,
            input_tokens=500,
            output_tokens=100,
        ),
        Record(image_id="not-in-dataset", detector="x", report=hit),
    ]

    summary = summarize("opus", records, labels)

    assert summary.scores.images == 2
    assert summary.scores.micro == Counts(tp=2)
    assert summary.scores.labels_located == Counts(tp=1, fn=1)
    assert (summary.errors, summary.declined) == (0, 1)
    assert (summary.median_ms, summary.p95_ms) == (3000, 4000)
    assert (summary.input_tokens, summary.output_tokens) == (1000, 300)
    # (1000 x $5 + 300 x $25) per million tokens
    assert summary.cost_per_photo(5, 25) == pytest.approx(0.0125)
    assert summary.cost_per_photo(None, None) is None

    text = render([summary], 0.3, input_price=5, output_price=25)
    assert (
        "| opus | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% "
        "| 50.0% | 100.0% | n/a | 3.0 s | $0.0125 |" in text
    )
    assert "| glass shatter | 1 | 100.0% | 100.0% | 100.0% |" in text
    assert "| crack | 0 | n/a | n/a | n/a |" in text
    assert "1000 input and 300 output tokens per photo" in text


def test_report_command_prints_a_table(dataset, tmp_path, capsys):
    out = tmp_path / "mock.jsonl"
    asyncio.run(run(dataset, FlakyDetector(), out, max_edge=1568))

    exit_code = report_module.main([str(out), "--annotations", str(tmp_path / "annotations.json")])

    assert exit_code == 0
    printed = capsys.readouterr().out
    assert "| mock | 2 |" in printed
    assert "### mock" in printed


def test_report_command_fails_cleanly_without_a_dataset(tmp_path, capsys):
    assert report_module.main(["x.jsonl", "--annotations", str(tmp_path / "missing.json")]) == 1
    assert "Couldn't load the dataset" in capsys.readouterr().err


# Model comparison


@pytest.fixture
def photos(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "b.PNG").write_bytes(make_image(fmt="PNG"))
    (folder / "a.jpg").write_bytes(make_image())
    (folder / "notes.txt").write_text("not a photo")
    return folder


def test_compare_runs_each_photo_once_per_model(photos, tmp_path, cost_book):
    samples = compare_module.find_photos(photos)
    assert [item.image_id for item in samples] == ["a.jpg", "b.PNG"]

    detectors = {"haiku": FlakyDetector(), "opus": FlakyDetector(failures={2})}
    out = tmp_path / "results"
    # One at a time, so which photo hits the failure is predictable.
    results = asyncio.run(
        compare_module.compare(samples, detectors, out, max_edge=1568, concurrency=1)
    )

    assert results["opus"]["b.PNG"].error == "The service is busy."
    # A second run only retries the photo that failed.
    asyncio.run(compare_module.compare(samples, detectors, out, max_edge=1568))
    assert (detectors["haiku"].calls, detectors["opus"].calls) == (2, 3)

    models = {"haiku": "claude-haiku-5-5", "opus": "unknown-model"}
    text = compare_module.render(samples, results, models, cost_book)
    # (1000 x $0.10 + 200 x $0.50) per million tokens, for each of two photos
    assert "| haiku | 2 | 0 | 6 |" in text
    assert "| $0.0004 | $0.0002 |" in text
    assert "| opus | 2 | 1 | 3 |" in text
    assert "### b.PNG" in text
    assert "left front fender: moderate dent (90%)" in text
    assert "| opus | error: The service is busy. | n/a | n/a | n/a |" in text


def test_compare_command_checks_before_spending(photos, tmp_path, capsys, monkeypatch):
    assert compare_module.main([str(tmp_path / "missing")]) == 1
    assert compare_module.main([str(photos), "--max-photos", "1"]) == 1
    monkeypatch.setattr(compare_module, "Settings", mock_settings)
    assert compare_module.main([str(photos)]) == 1
    errors = capsys.readouterr().err
    assert "isn't a folder" in errors
    assert "more than --max-photos 1" in errors
    assert "ANTHROPIC_API_KEY isn't set" in errors


def _coco_with_two_annotations():
    return {
        "categories": [{"id": 1, "name": "dent"}],
        "images": [{"id": 7, "width": 100, "height": 100, "file_name": "a.jpg"}],
        "annotations": [
            {"id": 1, "image_id": 7, "category_id": 1, "bbox": [0, 0, 50, 50]},
            {"id": 2, "image_id": 7, "category_id": 1, "bbox": [50, 50, 50, 50]},
        ],
    }


def test_add_panels_labels_only_the_annotations_it_names(tmp_path):
    annotations, panels, out = (tmp_path / name for name in ("a.json", "p.json", "out.json"))
    annotations.write_text(json.dumps(_coco_with_two_annotations()), encoding="utf-8")
    panels.write_text(json.dumps({"2": "left_front_door"}), encoding="utf-8")

    args = ["--annotations", str(annotations), "--panels", str(panels), "--out", str(out)]
    assert add_panels_module.main(args) == 0

    [sample_] = load_coco(out, tmp_path)
    assert [label.panel for label in sample_.labels] == [None, Panel.LEFT_FRONT_DOOR]


@pytest.mark.parametrize("panels", [{"2": "left_door"}, {"99": "hood"}])
def test_add_panels_rejects_unknown_panels_and_ids(panels):
    with pytest.raises(ValueError):
        add_panels_module.add_panels(_coco_with_two_annotations(), panels)
