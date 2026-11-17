# Crashtimate Roadmap

Upload a photo of a damaged car and get an itemized repair estimate.

## Core idea

The vision model only **describes** the damage (which panel, what kind, how bad).
A deterministic pricing engine **prices** it, the same way shop estimating software
does: labor operations (repair, replace, refinish, blend) × regional labor rate,
plus parts and paint materials. That keeps estimates explainable, testable and
consistent from one upload to the next.

```
[Next.js web app] ──photo + VIN/postal code──> [FastAPI]
                                                  │
   1. Validate + shrink the image (Pillow), strip EXIF
   2. VIN decode (NHTSA vPIC) → year/make/model/body → price tier
   3. Vision model → strict JSON validated by Pydantic:
        [{panel, damage_type, severity, box, confidence}]
   4. Pricing engine (pure Python, unit-tested):
        damage → operations → labor hours × regional rate + parts + paint
        → low–high range
   5. Cache the analysis and save shared estimates (SQLite)
                                                  │
[Results page] <── itemized estimate + damage boxes drawn on the photo
```

## Defaults

- Prices in **CAD**, Ontario labor rates.
- **Web app** (mobile-friendly, the upload button opens the phone camera).
- Vision model: **Claude Opus 5.5** behind a `DamageDetector` interface, with a
  mock detector so tests and CI never need an API key.

## Phases

### Phase 0: Setup
- [x] Monorepo layout: `backend/`, `frontend/`, `eval/`, `docs/`
- [x] `.gitignore`, `.env.example`, ruff lint/format config
- [x] GitHub Actions CI running lint + tests on every push

### Phase 1: Backend core
- [x] FastAPI app with `GET /api/health` and `POST /api/analyze`
- [x] Pydantic schemas for the damage report (panels, damage types, severity, boxes)
- [x] Image validation and preprocessing (size limits, EXIF orientation, resize, re-encode)
- [x] Claude vision detector using structured outputs
- [x] Mock detector for tests and frontend development
- [x] Handles "not a car" and "photo unusable"
- [x] pytest suite

### Phase 2: Cost data and pricing engine
- [x] Cost book (`ontario.toml`): labour rates, paint and shop materials, parts, hours, sublet prices
- [x] Rules: damage type × severity × panel → polish, paintless repair, repair, replace or sublet
- [x] Refinish with overlap deductions, blending of neighbouring panels
- [x] Luxury and vehicle-size pricing, driver-assist sensor calibration
- [x] VIN decoding via NHTSA vPIC, postal code → province
- [x] `POST /api/estimate` (photo → itemized low–high estimate with HST)
- [x] `POST /api/price` (re-price damage the user edited) and `GET /api/vehicles/{vin}`
- [x] `docs/cost-data.md` with sources, plus calibration tests against published prices

### Phase 3: Frontend
- [x] Next.js + TypeScript + Tailwind
- [x] Drag-and-drop / camera upload, optional VIN (looked up as it is typed) and postal code
- [x] Vehicle type picker for when there is no VIN
- [x] Results page: itemized table grouped by panel, cost range, damage boxes over the photo
- [x] Edit, remove or add damage and re-price without another photo analysis
- [x] TypeScript types generated from the API's OpenAPI schema, checked in CI
- [x] Unit tests (Vitest), ESLint, Prettier, frontend CI job

### Phase 4: Accuracy evaluation
- [x] Eval harness (`backend/evals/`): COCO loader, resumable runner, scoring, Markdown report
- [x] Per-damage-type precision/recall/F1, box location, panel accuracy, time and tokens per photo
- [x] Get the CarDD dataset (request form) and run it with a real API key (50 test photos, three models)
- [x] Model comparison table in the README
- [x] Label panels on a subset to measure panel accuracy (75 damages on the 50 CarDD photos)

### Phase 5: Deploy and polish
- [x] Per-IP rate limiting, daily analysis cap, cache results by image hash
- [x] Save estimates in SQLite with shareable links, deleted after 30 days
- [x] Dockerfiles, `docker-compose.yml`, Render blueprint, deploy guide
- [ ] Build and run the Docker images (written but not yet built)
- [x] Deploy: backend on Render, frontend on Vercel at crashtimate.zaidhaque.ca
- [ ] README demo GIF and live link

### Stretch
- [x] Multiple photos merged into one estimate
- [x] Print / save as PDF from the results page
- [ ] YOLOv8 segmentation model trained on CarDD for precise damage boxes
- [ ] Browser tests of the whole flow (Playwright)
- [ ] Postgres and Redis if it ever needs more than one server process
