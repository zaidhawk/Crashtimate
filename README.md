# Crashtimate

Upload a photo of a damaged car and get an itemized repair estimate.

A vision model describes the damage (which panel, what kind, how bad) as structured JSON.
A deterministic pricing engine then prices it the way body shop estimating software does:
labor operations, regional labor rates, parts and paint materials.

> **Status:** Phase 1 of 5. The backend detects damage; pricing, the web app and the
> accuracy evaluation are next. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Stack

- **Backend:** Python 3.12, FastAPI, Pydantic, Pillow
- **Vision:** Claude (Anthropic API) with structured outputs, behind a `DamageDetector`
  interface, plus a mock detector so tests and CI run without an API key
- **Tooling:** pytest, ruff, GitHub Actions

## Run the backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # set CRASHTIMATE_DETECTOR=claude and ANTHROPIC_API_KEY for real analysis
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs to try `POST /api/analyze` with a photo.

## Test

```bash
cd backend
pytest
ruff check . && ruff format --check .
```

## API

`POST /api/analyze` (multipart, field `image`: JPEG, PNG or WebP up to 10 MB)

```json
{
  "report": {
    "is_vehicle": true,
    "image_quality": "good",
    "view": "front_left",
    "damages": [
      {
        "panel": "left_front_fender",
        "damage_type": "dent",
        "severity": "moderate",
        "description": "Creased dent above the wheel arch, about the size of a hand.",
        "confidence": 0.9,
        "box": { "x_min": 0.52, "y_min": 0.38, "x_max": 0.71, "y_max": 0.6 }
      }
    ],
    "summary": "The front left corner took a moderate impact..."
  },
  "meta": {
    "detector": "claude",
    "model": "claude-opus-5-5",
    "image_sha256": "…",
    "image_width": 1568,
    "image_height": 1045,
    "elapsed_ms": 5400
  }
}
```

Left and right are the vehicle's own sides, as seen from the driver's seat. Damage types
match the six categories of the [CarDD](https://cardd-ustc.github.io/) dataset.
