"""Combine the damage reports from several photos of one vehicle."""

from collections.abc import Sequence

from pydantic import Field

from app.schemas import DamageItem, DamageReport, DamageType, ImageQuality, Panel, Severity

_SEVERITY_RANK = {Severity.MINOR: 0, Severity.MODERATE: 1, Severity.SEVERE: 2}


class DetectedDamage(DamageItem):
    photo: int = Field(default=0, ge=0, description="Which photo shows it (index into photos).")


def is_usable(report: DamageReport) -> bool:
    return report.is_vehicle and report.image_quality is not ImageQuality.UNUSABLE


def merge_damages(reports: Sequence[DamageReport]) -> list[DetectedDamage]:
    """One list of damage from several photos, without counting anything twice.

    Two photos of the same corner both show the same dent. Damage of the same type on the
    same panel is treated as one piece of damage, keeping the worse reading (then the more
    confident one), because a clearer angle shows more. Unusable photos are ignored.
    """
    merged: dict[tuple[Panel, DamageType], DetectedDamage] = {}
    for index, report in enumerate(reports):
        if not is_usable(report):
            continue
        for item in report.damages:
            key = (item.panel, item.damage_type)
            kept = merged.get(key)
            if kept is None or _rank(item) > _rank(kept):
                merged[key] = DetectedDamage(**item.model_dump(), photo=index)
    return list(merged.values())


def merge_summaries(reports: Sequence[DamageReport]) -> str:
    usable = [report.summary for report in reports if is_usable(report)]
    # With nothing usable, the first photo's summary says what went wrong.
    summaries = usable or [report.summary for report in reports[:1]]
    return " ".join(dict.fromkeys(summaries))


def _rank(item: DamageItem) -> tuple[int, float]:
    return _SEVERITY_RANK[item.severity], item.confidence
