import pytest
from pydantic import ValidationError

from app.detectors.mock import SAMPLE_REPORT
from app.schemas import BoundingBox, DamageItem, DamageReport


def test_box_with_swapped_corners_is_reordered():
    box = BoundingBox(x_min=0.8, y_min=0.9, x_max=0.2, y_max=0.1)

    assert (box.x_min, box.y_min, box.x_max, box.y_max) == (0.2, 0.1, 0.8, 0.9)


def test_box_outside_the_image_is_rejected():
    with pytest.raises(ValidationError):
        BoundingBox(x_min=0, y_min=0, x_max=1.5, y_max=1)


def test_confidence_outside_zero_to_one_is_rejected():
    item = SAMPLE_REPORT.damages[0].model_dump()
    item["confidence"] = 1.2

    with pytest.raises(ValidationError):
        DamageItem.model_validate(item)


def test_unknown_panel_is_rejected():
    item = SAMPLE_REPORT.damages[0].model_dump()
    item["panel"] = "flux_capacitor"

    with pytest.raises(ValidationError):
        DamageItem.model_validate(item)


def test_report_round_trips_through_json():
    assert DamageReport.model_validate_json(SAMPLE_REPORT.model_dump_json()) == SAMPLE_REPORT


def test_every_field_is_required_so_the_model_always_fills_it_in():
    schema = DamageReport.model_json_schema()

    assert set(schema["required"]) == set(schema["properties"])
    item_schema = schema["$defs"]["DamageItem"]
    assert set(item_schema["required"]) == set(item_schema["properties"])
