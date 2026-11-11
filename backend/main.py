"""FastAPI application.  Run:  uvicorn backend.main:app --reload --port 8000   ->  docs at http://localhost:8000/docs"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.services.analysis import recover_stale_sessions
from config.logging_config import get_logger, setup_logging
from config.settings import settings
from database.connection import init_db

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    n = recover_stale_sessions()
    if n:
        log.warning("Marked %d interrupted analyses as failed", n)
    log.info("Business Blind Spot Detector API ready")
    yield


app = FastAPI(
    title="Business Blind Spot Detector API",
    version="1.0.0",
    description=("Compare what customers say and expect with what a company communicates. Upload customer and company "
                 "datasets, run the NLP pipeline, and retrieve topics, expectations, blind spots, trends and recommendations."),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def allow_private_network(request, call_next):
    """A page served from a public origin (e.g. Vercel) calling this backend on localhost triggers Chrome's Private
    Network Access preflight, which must be answered with this header - but only for origins we explicitly allow."""
    response = await call_next(request)
    if (request.method == "OPTIONS" and request.headers.get("access-control-request-private-network") == "true"
            and request.headers.get("origin", "").rstrip("/") in settings.cors_origins):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


app.include_router(router)
