import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import Settings, get_settings
from app.detectors import DamageDetector, build_detector
from app.limits import RateLimiter
from app.pricing import CostBook, load_cost_book
from app.store import Store
from app.vehicles import VinDecoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app(
    settings: Settings | None = None,
    detector: DamageDetector | None = None,
    vin_decoder: VinDecoder | None = None,
    cost_book: CostBook | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own settings, detector and VIN decoder."""
    settings = settings or get_settings()
    # Loaded up front so a broken cost book stops the app from starting.
    cost_book = cost_book or load_cost_book()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=settings.vin_lookup_timeout_seconds) as http:
            app.state.detector = detector or build_detector(settings)
            app.state.vin_decoder = vin_decoder or VinDecoder(
                http, cost_book.luxury_makes, settings.vpic_url
            )
            app.state.store = Store(settings.database_path)
            app.state.store.purge(timedelta(days=settings.retention_days))
            try:
                yield
            finally:
                app.state.store.close()
                await app.state.detector.aclose()

    app = FastAPI(title="Crashtimate API", version="0.3.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.cost_book = cost_book
    app.state.analysis_limiter = RateLimiter(settings.rate_limit_per_hour, 3600)
    app.state.share_limiter = RateLimiter(settings.share_rate_limit_per_hour, 3600)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
