# Crashtimate

Upload a photo of a damaged car and get an itemized repair estimate.

A vision model describes the damage (which panel, what kind, how bad) as structured JSON.
A deterministic pricing engine then prices it the way body shop estimating software does:
repair, replace, refinish and blend operations in labour hours, Ontario shop rates, parts,
paint materials and specialist work, all as low–high ranges with HST.

> **Status:** Phase 2 of 5. The backend detects and prices damage; the web app and the
> accuracy evaluation are next. See [docs/ROADMAP.md](docs/ROADMAP.md).

## How it works

- **Detection:** Claude reads the photo and returns a validated damage report: panels,
  damage types and severity, plus boxes marking where the damage is. A mock detector
  lets tests and CI run without an API key.
- **Pricing rules:** each damage becomes an operation. Light scratches are polished, small
  dents get paintless repair, moderate damage is repaired and repainted, and severe damage
  is replaced. Damage on the same panel is combined. Repainted panels share setup time, and
  neighbouring panels are blended so the colour matches.
- **Vehicle data:** an optional VIN is decoded through NHTSA's vPIC API. Luxury makes get
  luxury shop rates and parts prices, SUVs and trucks get bigger panels, and cars with
  lane cameras or radar get sensor calibration after nearby repairs.
- **Sourced numbers:** rates come from posted Ontario shop rate sheets, and every other
  number has a source or is marked as an assumption in
  [docs/cost-data.md](docs/cost-data.md). Calibration tests check estimates against
  published repair prices.

## Stack

- **Backend:** Python 3.12, FastAPI, Pydantic, Pillow, httpx
- **Vision:** Claude (Anthropic API) with structured outputs
- **Data:** cost book in TOML, validated on startup
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

Open http://localhost:8000/docs to try the API.

## Test

```bash
cd backend
pytest
ruff check . && ruff format --check .
```

## API

| Endpoint | What it does |
|---|---|
| `POST /api/estimate` | Photo (plus optional `vin` and `postal_code`) → damage report and itemized estimate |
| `POST /api/price` | JSON list of damage (plus optional VIN and postal code) → estimate. Used to re-price after the user corrects the detected damage, without another photo analysis. |
| `POST /api/analyze` | Photo → damage report only |
| `GET /api/vehicles/{vin}` | Year, make, model, body class and driver-assist features |

A trimmed `POST /api/estimate` response:

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
  "estimate": {
    "currency": "CAD",
    "region": "Ontario",
    "vehicle": { "year": 2019, "make": "HONDA", "model": "Civic", "tier": "standard", "size": "car" },
    "lines": [
      {
        "panel": "left_front_fender",
        "operation": "repair",
        "description": "Repair the left front fender (moderate dent)",
        "body_hours": { "low": 1.5, "high": 3.0 },
        "cost": { "low": 143, "high": 360 }
      },
      {
        "panel": "left_front_fender",
        "operation": "refinish",
        "description": "Refinish the left front fender",
        "refinish_hours": { "low": 2.2, "high": 2.2 },
        "cost": { "low": 293, "high": 348 }
      },
      {
        "panel": "hood",
        "operation": "blend",
        "description": "Blend the hood to match the new paint",
        "refinish_hours": { "low": 1.5, "high": 3.0 },
        "cost": { "low": 200, "high": 474 }
      }
    ],
    "totals": {
      "subtotal": { "low": 1103, "high": 3152 },
      "tax": { "low": 143, "high": 410 },
      "total": { "low": 1246, "high": 3562 }
    },
    "unpriced": [],
    "notes": ["This is an estimate to help you plan, not a quote. ..."]
  },
  "meta": { "detector": "claude", "model": "claude-opus-5-5", "elapsed_ms": 5400 }
}
```

Left and right are the vehicle's own sides, as seen from the driver's seat. Damage types
match the six categories of the [CarDD](https://cardd-ustc.github.io/) dataset.
