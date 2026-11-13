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
   5. Save the estimate (SQLite locally, Postgres when deployed)
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
- [ ] Next.js + TypeScript + Tailwind
- [ ] Drag-and-drop / camera upload, optional VIN and postal code
- [ ] Results page: itemized table, cost range, damage boxes over the photo

### Phase 4: Accuracy evaluation
- [ ] Labeled image set (CarDD / Roboflow car-damage sets + hand-labeled panels)
- [ ] Eval script: per-damage-type precision/recall, panel accuracy, cost per request
- [ ] Model comparison table in the README

### Phase 5: Deploy and polish
- [ ] Dockerfile, backend on Render or Fly.io, frontend on Vercel
- [ ] Per-IP rate limiting, daily spend cap, cache results by image hash
- [ ] Save estimates (SQLite locally, Postgres when deployed) with shareable links
- [ ] README with demo GIF, architecture diagram and live link

### Stretch
- [ ] YOLOv8 segmentation model trained on CarDD for precise damage boxes
- [ ] PDF export of estimates
- [ ] Multiple photos merged into one estimate
