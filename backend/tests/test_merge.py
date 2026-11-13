from app.detectors.mock import SAMPLE_REPORT
from app.merge import merge_damages, merge_summaries
from app.schemas import (
    DamageItem,
    DamageReport,
    DamageType,
    ImageQuality,
    Panel,
    Severity,
    ViewAngle,
)


def item(panel=Panel.HOOD, damage_type=DamageType.DENT, severity=Severity.MINOR, confidence=0.8):
    return DamageItem(
        panel=panel,
        damage_type=damage_type,
        severity=severity,
        description="",
        confidence=confidence,
        box=None,
    )


def report(*damages, summary="Summary.", is_vehicle=True, quality=ImageQuality.GOOD):
    return DamageReport(
        is_vehicle=is_vehicle,
        image_quality=quality,
        view=ViewAngle.FRONT,
        damages=list(damages),
        summary=summary,
    )


def keys(damages):
    return [(d.panel, d.damage_type, d.severity, d.photo) for d in damages]


def test_one_photo_passes_through_in_order():
    merged = merge_damages([SAMPLE_REPORT])

    assert [d.model_dump(exclude={"photo"}) for d in merged] == [
        d.model_dump() for d in SAMPLE_REPORT.damages
    ]
    assert {d.photo for d in merged} == {0}


def test_same_damage_in_two_photos_is_counted_once_at_the_worse_severity():
    merged = merge_damages(
        [report(item(severity=Severity.MINOR)), report(item(severity=Severity.MODERATE))]
    )

    assert keys(merged) == [(Panel.HOOD, DamageType.DENT, Severity.MODERATE, 1)]


def test_equal_severity_keeps_the_more_confident_reading():
    merged = merge_damages([report(item(confidence=0.9)), report(item(confidence=0.6))])

    assert (merged[0].photo, merged[0].confidence) == (0, 0.9)


def test_different_damage_is_all_kept():
    merged = merge_damages(
        [
            report(item(), item(damage_type=DamageType.SCRATCH)),
            report(item(panel=Panel.ROOF)),
        ]
    )

    assert keys(merged) == [
        (Panel.HOOD, DamageType.DENT, Severity.MINOR, 0),
        (Panel.HOOD, DamageType.SCRATCH, Severity.MINOR, 0),
        (Panel.ROOF, DamageType.DENT, Severity.MINOR, 1),
    ]


def test_unusable_photos_are_ignored_but_keep_their_position():
    merged = merge_damages(
        [
            report(item(severity=Severity.SEVERE), quality=ImageQuality.UNUSABLE),
            report(item(), is_vehicle=False),
            report(item()),
        ]
    )

    assert keys(merged) == [(Panel.HOOD, DamageType.DENT, Severity.MINOR, 2)]


def test_summaries_join_usable_photos_without_repeats():
    reports = [
        report(summary="Front is dented."),
        report(summary="Too dark.", quality=ImageQuality.UNUSABLE),
        report(summary="Front is dented."),
        report(summary="Rear is fine."),
    ]

    assert merge_summaries(reports) == "Front is dented. Rear is fine."


def test_summary_explains_the_problem_when_nothing_is_usable():
    reports = [
        report(summary="That is a dog.", is_vehicle=False),
        report(summary="Too dark.", quality=ImageQuality.UNUSABLE),
    ]

    assert merge_summaries(reports) == "That is a dog."
    assert merge_summaries([]) == ""
