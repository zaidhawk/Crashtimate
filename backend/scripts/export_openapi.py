"""Write the API schema to frontend/openapi.json, which the frontend's types are generated from.

Run from backend/ after changing the API:  python scripts/export_openapi.py
A test fails if the committed file is out of date.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
