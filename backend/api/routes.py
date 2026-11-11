"""REST API (auto-documented at /docs). Routes are thin: validation + error mapping around backend.services."""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.schemas import (AnalysisRequest, AnalysisStarted, AnalysisStatus, CompanyCreate, CompanyOut, RescoreRequest,
                             ScoringConfigModel, TextIngest, UrlIngest)
from backend.services import analysis, companies, datasets
from backend.services.companies import Conflict, NotFound
from backend.services.pipeline import PipelineError
from config.logging_config import get_logger
from config.settings import ScoringConfig, load_scoring_config, save_scoring_config, settings
from ml.ingestion import IngestionError

log = get_logger(__name__)
router = APIRouter()


def _guard(fn, *args, **kwargs):
    """Run a service call and translate domain errors into HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (IngestionError, PipelineError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Unhandled API error")
        raise HTTPException(500, f"Internal error: {type(exc).__name__}: {exc}") from exc


def _not_in_public_mode():
    if settings.public_mode:
        raise HTTPException(403, "This action is disabled because the backend is running in PUBLIC_MODE.")


def _mapping(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        m = json.loads(raw)
        return m if isinstance(m, dict) else None
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "mapping must be a JSON object") from exc


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB.")
    return content


# ------------------------------------------------------------------ system
@router.get("/health", tags=["system"])
def health():
    return {"status": "ok", "embedding_backend": settings.embedding_backend, "database": settings.database_url.split("://")[0], "public_mode": settings.public_mode}


@router.get("/config/scoring", response_model=ScoringConfigModel, tags=["system"])
def get_scoring_config():
    return load_scoring_config().to_dict()


@router.put("/config/scoring", response_model=ScoringConfigModel, tags=["system"])
def put_scoring_config(cfg: ScoringConfigModel):
    _not_in_public_mode()
    new = ScoringConfig.from_dict(cfg.model_dump())
    save_scoring_config(new)
    return new.to_dict()


# ------------------------------------------------------------------ companies
@router.post("/companies", response_model=CompanyOut, status_code=201, tags=["companies"])
def create_company(body: CompanyCreate):
    return _guard(companies.create_company, body.name, body.industry, body.description)


@router.get("/companies", response_model=list[CompanyOut], tags=["companies"])
def list_companies():
    return _guard(companies.list_companies)


@router.get("/companies/{company_id}", response_model=CompanyOut, tags=["companies"])
def get_company(company_id: int):
    return _guard(companies.get_company, company_id)


@router.delete("/companies/{company_id}", status_code=204, tags=["companies"])
def delete_company(company_id: int):
    _not_in_public_mode()
    _guard(companies.delete_company, company_id)


# ------------------------------------------------------------------ datasets
@router.post("/datasets/preview", tags=["datasets"])
async def preview_dataset(file: UploadFile = File(...), kind: str = Form(...), mapping: str | None = Form(None)):
    content = await _read_upload(file)
    return _guard(datasets.preview_upload, content, file.filename or "upload", kind, _mapping(mapping))


@router.get("/companies/{company_id}/datasets", tags=["datasets"])
def list_datasets(company_id: int):
    return _guard(datasets.list_datasets, company_id)


@router.post("/companies/{company_id}/datasets/upload", status_code=201, tags=["datasets"])
async def upload_dataset(company_id: int, file: UploadFile = File(...), kind: str = Form(...),
                         mapping: str | None = Form(None), name: str | None = Form(None)):
    content = await _read_upload(file)
    return _guard(datasets.ingest_file, company_id, kind, content, file.filename or "upload", _mapping(mapping), name)


@router.post("/companies/{company_id}/datasets/text", status_code=201, tags=["datasets"])
def add_text(company_id: int, body: TextIngest):
    return _guard(datasets.ingest_text, company_id, body.kind, body.text, body.source, body.name)


@router.post("/companies/{company_id}/datasets/url", status_code=201, tags=["datasets"])
def add_url(company_id: int, body: UrlIngest):
    return _guard(datasets.ingest_url, company_id, body.kind, body.url)


@router.post("/companies/{company_id}/datasets/sample", tags=["datasets"])
def load_sample(company_id: int):
    return _guard(datasets.load_sample, company_id)


@router.get("/datasets/{dataset_id}/records", tags=["datasets"])
def dataset_records(dataset_id: int, limit: int = 200):
    return _guard(datasets.dataset_records, dataset_id, min(max(limit, 1), 1000))


@router.delete("/datasets/{dataset_id}", status_code=204, tags=["datasets"])
def delete_dataset(dataset_id: int):
    _guard(datasets.delete_dataset, dataset_id)


# ------------------------------------------------------------------ analyses
@router.post("/companies/{company_id}/analyses", response_model=AnalysisStarted, status_code=202, tags=["analysis"])
def start_analysis(company_id: int, body: AnalysisRequest | None = None):
    body = body or AnalysisRequest()
    sid = _guard(analysis.start_analysis, company_id, body.customer_source_ids, body.company_source_ids, body.scoring)
    return {"session_id": sid, "status": "running"}


@router.get("/companies/{company_id}/analyses", tags=["analysis"])
def list_analyses(company_id: int):
    return _guard(analysis.list_sessions, company_id)


@router.get("/analyses/{session_id}/status", response_model=AnalysisStatus, tags=["analysis"])
def analysis_status(session_id: int):
    return _guard(analysis.session_status, session_id)


@router.get("/analyses/{session_id}", tags=["analysis"], summary="Complete analysis bundle (all dashboard data)")
def analysis_bundle(session_id: int):
    return _guard(analysis.get_bundle, session_id)


@router.delete("/analyses/{session_id}", status_code=204, tags=["analysis"])
def delete_analysis(session_id: int):
    _guard(analysis.delete_session, session_id)


@router.get("/analyses/{session_id}/topics/{topic_id}/conversations", tags=["analysis"])
def topic_conversations(session_id: int, topic_id: int, limit: int = 300):
    return _guard(analysis.topic_conversations, session_id, topic_id, min(max(limit, 1), 1000))


@router.post("/analyses/{session_id}/rescore", tags=["analysis"], summary="Re-score with different weights (no NLP re-run)")
def rescore(session_id: int, body: RescoreRequest):
    return _guard(analysis.rescore_session, session_id, body.config, body.persist)
