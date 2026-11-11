"""FastAPI application.  Run:  uvicorn backend.main:app --reload --port 8000   ->  docs at http://localhost:8000/docs"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.services.analysis import recover_stale_sessions
from config.logging_config import get_logger, setup_logging
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
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
