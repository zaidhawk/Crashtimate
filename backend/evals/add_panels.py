"""Add panel labels to a COCO annotations file, so panel accuracy can be scored.

    python -m evals.add_panels --annotations data/annotations.json \\
        --panels ../eval/cardd_panel_labels.json --out ../eval/annotations-panels.json

CarDD doesn't say which panel a damage is on. The panels file fills that in for some
annotations: a JSON object mapping annotation id to one of the panel names in
`app/schemas.py`. Annotations it doesn't mention are left without a panel.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.schemas import Panel


def add_panels(coco: dict, panels: dict[str, str]) -> int:
    """Set "panel" on each annotation named in `panels`. Returns how many were labelled."""
    unknown = sorted(set(panels.values()) - set(Panel))
    if unknown:
        raise ValueError(f"Unknown panel names: {', '.join(unknown)}.")
    ids = {str(annotation["id"]) for annotation in coco["annotations"]}
    missing = sorted(set(panels) - ids)
    if missing:
        raise ValueError(f"No annotation with id: {', '.join(missing)}.")
    for annotation in coco["annotations"]:
        panel = panels.get(str(annotation["id"]))
        if panel is not None:
            annotation["panel"] = panel
    return len(panels)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--annotations", type=Path, required=True, help="COCO annotations JSON")
    parser.add_argument("--panels", type=Path, required=True, help="annotation id -> panel JSON")
    parser.add_argument("--out", type=Path, required=True, help="where to write the result")
    args = parser.parse_args(argv)

    try:
        coco = json.loads(args.annotations.read_text(encoding="utf-8"))
        labelled = add_panels(coco, json.loads(args.panels.read_text(encoding="utf-8")))
    except (OSError, KeyError, ValueError) as exc:
        print(f"Couldn't add the panels: {exc}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(coco), encoding="utf-8")
    print(f"Labelled {labelled} annotations with a panel.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
