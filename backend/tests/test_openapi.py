import json
from pathlib import Path

from app.main import app

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def test_frontend_schema_matches_the_api():
    """The frontend's TypeScript types are generated from this file, so it must stay current."""
    committed = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))

    assert committed == app.openapi(), "Run: python scripts/export_openapi.py"
