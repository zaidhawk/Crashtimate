# Crashtimate

[![CI](https://github.com/zaidhawk/Crashtimate/actions/workflows/ci.yml/badge.svg)](https://github.com/zaidhawk/Crashtimate/actions/workflows/ci.yml)

Upload photos of a damaged car and get an itemized repair estimate in Canadian dollars.

A vision model describes the damage (which panel, what kind, how bad) as structured JSON.
A deterministic pricing engine then prices it the way body shop estimating software does:
repair, replace, refinish and blend operations in labour hours, Ontario shop rates, parts,
paint materials and specialist work, all as low–high ranges with HST.

Keeping those two jobs apart is the main design decision. The model never produces a
price, so every dollar on an estimate can be traced to a rule and a sourced number, the
same photo always gets the same price, and the pricing is covered by ordinary unit tests.

> **Status:** the web app, API, pricing engine and evaluation harness are built and tested.
> Three models have been scored on the CarDD dataset ([results](#results-on-cardd)).
> Not done yet: a live deployment. See [docs/ROADMAP.md](docs/ROADMAP.md).

## What it does

- **Photos in, estimate out.** Drop in up to four photos of the same car, or take one with
  a phone camera. Damage seen from several angles is combined and counted once.
- **Boxes on the damage.** Each piece of damage is numbered and outlined on the photo, and
  colour-coded by severity.
- **You can correct it.** Change the panel, the type or the severity, remove a false
  alarm, or add damage the model missed. The price updates straight away without paying
  for another photo analysis.
- **Priced for your vehicle.** A VIN is decoded through NHTSA's free vPIC service as you
  type. Luxury makes get luxury rates and parts prices, SUVs and trucks get bigger panels,
  and cars with lane cameras or radar get sensor calibration after nearby repairs. Without
  a VIN you pick the vehicle type yourself.
- **Shareable links.** Save an estimate and send the link to a shop or an insurer. The
  page also prints cleanly, or saves as a PDF.

## How it works

```
[Next.js web app] ── photos + VIN / postal code ──> [FastAPI]
                                                       │
   1. Validate and shrink each photo (Pillow); re-encoding strips GPS data
   2. Reuse the stored analysis if this exact photo was seen before (SHA-256)
   3. Otherwise ask the vision model for JSON checked against a Pydantic schema:
        [{panel, damage_type, severity, box, confidence}]
   4. Merge the damage from all photos
   5. Decode the VIN (NHTSA vPIC) → year, make, model, body size, driver-assist sensors
   6. Pricing engine (pure Python):
        damage → operations → labour hours × shop rate + parts + paint → low–high range
                                                       │
[Results page] <── itemized estimate + damage boxes ───┘
```

- **Detection:** Claude reads each photo and returns a validated damage report. A mock
  detector returns sample damage so the tests, CI and local development never need an API
  key.
- **Pricing rules:** light scratches are polished, small dents get paintless repair,
  moderate damage is repaired and repainted, and severe damage is replaced. Damage on the
  same panel is combined. Repainted panels share setup time, and neighbouring panels are
  blended so the colour matches.
- **Sourced numbers:** rates come from posted Ontario shop rate sheets, and every other
  number has a source or is marked as an assumption in
  [docs/cost-data.md](docs/cost-data.md). Calibration tests check estimates against
  published repair prices.
- **Typed end to end:** the frontend's TypeScript types are generated from the API's
  OpenAPI schema, and CI fails if they fall out of date.

## Guarding the bill

The vision model is the only part that costs money, so the API protects it:

- **Cache by photo hash.** The same photo is never analysed twice.
- **Cheap checks first.** A bad VIN or postal code is rejected before the model is called.
- **Rate limit per visitor**, using a sliding window. Behind a proxy it reads the
  visitor's address from `X-Forwarded-For`, trusting only the entries our own proxy added.
- **Daily cap** on paid analyses across all visitors.
- **Saved estimates are priced on the server.** The browser sends the damage, never the
  prices, so a shared link always shows numbers this app calculated.
- **Retention.** Photos, analyses and saved estimates are deleted after 30 days.

## Stack

- **Backend:** Python 3.12, FastAPI, Pydantic, Pillow, httpx, SQLite
- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS
- **Vision:** Claude (Anthropic API) with structured outputs
- **Data:** cost book in TOML, validated on startup
- **Tooling:** pytest, ruff, Vitest, ESLint, Prettier, GitHub Actions, Docker

## Run it

Start the API (demo mode by default, no API key needed):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # set CRASHTIMATE_DETECTOR=claude and ANTHROPIC_API_KEY for real analysis
uvicorn app.main:app --reload
```

Start the web app in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The API's own docs are at http://localhost:8000/docs.

Or run both with Docker: `docker compose up --build`.

## Test

```bash
cd backend
pytest
ruff check . && ruff format --check .
```

```bash
cd frontend
npm test
npm run lint && npm run typecheck
```

## API

| Endpoint | What it does |
|---|---|
| `POST /api/estimate` | One to four photos (`images`), plus optional `vin`, `postal_code`, `vehicle_size` and `vehicle_tier` → per-photo reports, merged damage and an itemized estimate |
| `POST /api/price` | JSON list of damage → estimate. Used to re-price after the user corrects the detected damage, without another photo analysis. |
| `POST /api/shares` | Save an estimate (photo hashes plus the damage) and get an id for a shareable link |
| `GET /api/shares/{id}` | A saved estimate. Its photos are at `/api/shares/{id}/photos/{n}`. |
| `POST /api/analyze` | One photo → damage report only |
| `GET /api/vehicles/{vin}` | Year, make, model, body class and driver-assist features |

A trimmed `POST /api/estimate` response:

```json
{
  "photos": [
    {
      "report": { "is_vehicle": true, "image_quality": "good", "view": "front_left", "...": "..." },
      "meta": { "detector": "claude", "model": "claude-opus-5-5", "elapsed_ms": 5400, "cached": false }
    }
  ],
  "damages": [
    {
      "panel": "left_front_fender",
      "damage_type": "dent",
      "severity": "moderate",
      "description": "Creased dent above the wheel arch, about the size of a hand.",
      "confidence": 0.9,
      "box": { "x_min": 0.52, "y_min": 0.38, "x_max": 0.71, "y_max": 0.6 },
      "photo": 0
    }
  ],
  "summary": "The front left corner took a moderate impact...",
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
  }
}
```

Left and right are the vehicle's own sides, as seen from the driver's seat. Damage types
match the six categories of the [CarDD](https://cardd-ustc.github.io/) dataset.

## Accuracy evaluation

`backend/evals/` scores a detector against a labelled photo set in COCO format (such as
CarDD): precision, recall and F1 per damage type, how well the boxes land on the labelled
damage, and time and tokens per photo. Runs are resumable and can be compared side by side
across models. See [eval/README.md](eval/README.md).

### Results on CarDD

Three models on the same 50 photos, drawn at random (seed 0) from CarDD's 374-photo test
split, 115 labelled damages, effort `medium`, November 2026:

| Model | Precision | Recall | F1 | Labels located | Panel accuracy | Median time | Cost per photo (USD) |
|---|---|---|---|---|---|---|---|
| Claude Haiku 5.5 | 78.6% | 89.2% | 83.5% | 44.3% | 82.1% (32 of 39) | 7.5 s | $0.0009 |
| Claude Sonnet 5.5 | 75.8% | 97.3% | 85.2% | 51.3% | 90.2% (37 of 41) | 4.6 s | $0.0126 |
| Claude Opus 5.5 | 75.3% | 94.6% | 83.8% | 47.8% | 97.3% (36 of 37) | 10.6 s | $0.0307 |

What the numbers say:

- **The three models are tied on naming the type of damage.** With 50 photos, a gap of a
  couple of points is within noise. Sonnet matches Opus at 41% of the cost and less than
  half the wait; Haiku gets there at 3% of the cost but misses more damage (lower recall).
- **Recall is high and precision is lower.** The models rarely miss labelled damage, and
  about one reported damage type in four is not in the labels.
- **Boxes are the weak point.** Only about half of the labelled damages have a predicted
  box of the same type on them, even at a loose overlap threshold (IoU 0.3). Part of that
  is by design, since the detector draws one box per panel while CarDD labels every mark.
- **Panel accuracy is where the models separate.** CarDD has no panel labels, so panels
  were labelled for this project on 75 of the 115 damages, before looking at any model's
  answers ([eval/cardd_panel_labels.json](eval/cardd_panel_labels.json)). The other 40
  are close-ups where the panel or the side of the car can't be told. When a model's box
  lands on a labelled damage, Opus names the right panel 36 times out of 37, Sonnet 37 of
  41 and Haiku 32 of 39. The panel decides the price, so the app defaults to Opus; the
  sample is small, and Sonnet is a setting away if cost matters more.
- **What this does not measure:** severity, which CarDD does not label.

## Deploying

The API ships as a Docker image with a Render blueprint (`render.yaml`), and the web app
is set up for Vercel. Steps are in [docs/DEPLOY.md](docs/DEPLOY.md).
