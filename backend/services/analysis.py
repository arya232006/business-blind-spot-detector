"""Analysis jobs: create a session, run the pipeline (optionally in a background thread), persist results,
re-score with different weights."""
from __future__ import annotations

import threading
import traceback
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import select

from backend.services import datasets
from backend.services.companies import NotFound, Conflict
from backend.services.persistence import delete_results, load_bundle, save_result
from backend.services.pipeline import FLAGGED, PipelineError, run_pipeline, TOTAL_STEPS
from backend.services.serialization import df_records, to_jsonable
from config.logging_config import get_logger
from config.settings import ScoringConfig, load_scoring_config
from database import models as M
from database.connection import init_db, session_scope
from ml.recommendations import generate_recommendations
from ml.scoring.rescore import rescore_blind_spots

log = get_logger(__name__)
_STALE_AFTER = timedelta(minutes=30)
_THREADS: dict[int, threading.Thread] = {}


def recover_stale_sessions() -> int:
    """Sessions left 'running' by a crashed process are marked failed so the UI never waits forever."""
    init_db()
    n = 0
    with session_scope() as db:
        for s in db.scalars(select(M.AnalysisSession).where(M.AnalysisSession.status == "running")):
            if s.id not in _THREADS or not _THREADS[s.id].is_alive():
                s.status, s.error, s.finished_at = "failed", "Interrupted (the application restarted during analysis).", datetime.utcnow()
                n += 1
    return n


def create_session(company_id: int, customer_source_ids: list[int] | None = None,
                   company_source_ids: list[int] | None = None, scoring: dict | None = None) -> int:
    init_db()
    with session_scope() as db:
        if db.get(M.Company, company_id) is None:
            raise NotFound(f"Company {company_id} not found.")
        running = db.scalars(select(M.AnalysisSession).where(M.AnalysisSession.company_id == company_id,
                                                             M.AnalysisSession.status == "running")).first()
        if running and datetime.utcnow() - running.started_at < _STALE_AFTER and running.id in _THREADS and _THREADS[running.id].is_alive():
            raise Conflict("An analysis is already running for this company.")
        s = M.AnalysisSession(company_id=company_id, status="running", progress=0, message="Queued",
                              customer_source_ids=customer_source_ids, company_source_ids=company_source_ids,
                              meta={"scoring_config_requested": scoring or {}})
        db.add(s)
        db.flush()
        return s.id


def _set_progress(session_id: int, step: int, total: int, msg: str) -> None:
    with session_scope() as db:
        s = db.get(M.AnalysisSession, session_id)
        if s:
            s.progress, s.message = int(step / total * 100), msg


def execute_session(session_id: int) -> None:
    """Blocking: load data, run the whole pipeline, store results. Never raises - failures are stored on the session."""
    try:
        with session_scope() as db:
            s = db.get(M.AnalysisSession, session_id)
            company_id, c_ids, k_ids = s.company_id, s.customer_source_ids, s.company_source_ids
            requested = (s.meta or {}).get("scoring_config_requested") or {}
        cust = datasets.load_frame(company_id, "customer", c_ids)
        comp = datasets.load_frame(company_id, "company", k_ids)
        cfg = ScoringConfig.from_dict({**load_scoring_config().to_dict(), **requested})
        res = run_pipeline(cust, comp, cfg, progress=lambda i, t, m: _set_progress(session_id, i, t, m))
        with session_scope() as db:
            s = db.get(M.AnalysisSession, session_id)
            save_result(db, session_id, res)
            meta = {**res.meta, "promises": df_records(res.promises), "company_themes_n": len(res.company_themes)}
            s.overview, s.meta = to_jsonable(res.overview), to_jsonable(meta)
            s.n_customer, s.n_company = len(res.customer), len(res.company)
            s.is_synthetic = bool(cust["is_synthetic"].fillna(False).astype(bool).all()) if len(cust) else False
            s.status, s.progress, s.message, s.finished_at = "completed", 100, "Analysis complete", datetime.utcnow()
    except PipelineError as exc:
        _fail(session_id, str(exc))
    except Exception as exc:  # noqa: BLE001
        log.error("Analysis %s crashed:\n%s", session_id, traceback.format_exc())
        _fail(session_id, f"Unexpected error: {type(exc).__name__}: {exc}")


def _fail(session_id: int, message: str) -> None:
    log.warning("Analysis %s failed: %s", session_id, message)
    with session_scope() as db:
        s = db.get(M.AnalysisSession, session_id)
        if s:
            s.status, s.error, s.message, s.finished_at = "failed", message, "Failed", datetime.utcnow()


def start_analysis(company_id: int, customer_source_ids: list[int] | None = None,
                   company_source_ids: list[int] | None = None, scoring: dict | None = None, background: bool = True) -> int:
    sid = create_session(company_id, customer_source_ids, company_source_ids, scoring)
    if background:
        t = threading.Thread(target=execute_session, args=(sid,), daemon=True, name=f"analysis-{sid}")
        _THREADS[sid] = t
        t.start()
    else:
        execute_session(sid)
    return sid


def session_status(session_id: int) -> dict:
    with session_scope() as db:
        s = db.get(M.AnalysisSession, session_id)
        if s is None:
            raise NotFound(f"Analysis {session_id} not found.")
        return {"id": s.id, "company_id": s.company_id, "status": s.status, "progress": s.progress, "message": s.message,
                "error": s.error, "steps": TOTAL_STEPS}


def list_sessions(company_id: int) -> list[dict]:
    init_db()
    with session_scope() as db:
        out = []
        for s in db.scalars(select(M.AnalysisSession).where(M.AnalysisSession.company_id == company_id)
                            .order_by(M.AnalysisSession.started_at.desc())):
            ov = s.overview or {}
            out.append({"id": s.id, "status": s.status, "started_at": s.started_at.isoformat(),
                        "finished_at": s.finished_at.isoformat() if s.finished_at else None, "n_customer": s.n_customer,
                        "n_company": s.n_company, "is_synthetic": s.is_synthetic, "error": s.error,
                        "total_topics": ov.get("total_topics"), "total_blind_spots": ov.get("total_blind_spots"),
                        "avg_blind_spot_score": ov.get("avg_blind_spot_score"), "overall_sentiment": ov.get("overall_sentiment"),
                        "runtime_seconds": (s.meta or {}).get("runtime_seconds")})
        return out


def get_bundle(session_id: int) -> dict:
    with session_scope() as db:
        return to_jsonable(load_bundle(db, session_id))


def delete_session(session_id: int) -> None:
    with session_scope() as db:
        s = db.get(M.AnalysisSession, session_id)
        if s is None:
            raise NotFound(f"Analysis {session_id} not found.")
        db.delete(s)


def topic_conversations(session_id: int, topic_id: int, limit: int = 300) -> list[dict]:
    """The customer statements behind one topic (for click-through inspection)."""
    with session_scope() as db:
        rows = db.execute(
            select(M.AspectSentiment, M.SentimentResult).join(
                M.SentimentResult, (M.SentimentResult.session_id == M.AspectSentiment.session_id)
                & (M.SentimentResult.record_id == M.AspectSentiment.record_id))
            .where(M.AspectSentiment.session_id == session_id, M.AspectSentiment.topic_id == topic_id)
            .order_by(M.AspectSentiment.compound).limit(limit)).all()
        return to_jsonable([{
            "record_id": a.record_id, "statement": a.clause, "aspect": a.aspect, "aspect_sentiment": a.compound,
            "aspect_label": a.label, "full_text": r.text_original, "document_sentiment": r.compound,
            "source": r.source, "date": r.date, "customer_id": r.customer_id, "signals": a.signals,
        } for a, r in rows])


# ----------------------------------------------------------------------------------- re-scoring
def rescore_session(session_id: int, config_overrides: dict, persist: bool = False) -> dict:
    """Recompute importance/gap/trend/score/severity/classification + recommendations with new scoring weights
    from the stored components (no NLP re-run). ``persist=True`` overwrites the stored results."""
    with session_scope() as db:
        s = db.get(M.AnalysisSession, session_id)
        if s is None:
            raise NotFound(f"Analysis {session_id} not found.")
        if s.status != "completed":
            raise ValueError("Only completed analyses can be re-scored.")
        base = ScoringConfig.from_dict((s.meta or {}).get("scoring_config"))
        cfg = ScoringConfig.from_dict({**base.to_dict(), **(config_overrides or {})})
        bs_rows = db.scalars(select(M.BlindSpotResult).where(M.BlindSpotResult.session_id == session_id)).all()
        bs = pd.DataFrame([{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in bs_rows])
        exp = pd.DataFrame([{c.name: getattr(r, c.name) for c in r.__table__.columns}
                            for r in db.scalars(select(M.CustomerExpectation).where(M.CustomerExpectation.session_id == session_id))])
        cat = {t.topic_id: t.category for t in db.scalars(select(M.DetectedTopic).where(M.DetectedTopic.session_id == session_id))}
    scored = rescore_blind_spots(bs.drop(columns=["id", "session_id"]), cfg)
    scored["trend_status"] = scored["trend_status"]
    recs = generate_recommendations(scored, exp if len(exp) else None, cat)
    flagged = scored[scored["classification"].isin(FLAGGED) & (scored["score"] >= cfg.min_score)]
    summary = {"total_blind_spots": int(len(flagged)), "avg_blind_spot_score": float(flagged["score"].mean()) if len(flagged) else 0.0,
               "genuine_blind_spots": int((scored["classification"] == "genuine_blind_spot").sum())}
    if persist:
        with session_scope() as db:
            from backend.services.persistence import _rows
            delete_results(db, session_id, [M.BlindSpotResult, M.BusinessRecommendation])
            db.add_all(_rows(scored, M.BlindSpotResult, {"session_id": session_id}))
            db.add_all(_rows(recs, M.BusinessRecommendation, {"session_id": session_id}))
            for t in db.scalars(select(M.DetectedTopic).where(M.DetectedTopic.session_id == session_id)):
                row = scored[scored["topic_id"] == t.topic_id]
                if len(row):
                    t.importance, t.score, t.severity, t.classification = (float(row.iloc[0]["importance"]), float(row.iloc[0]["score"]),
                                                                          row.iloc[0]["severity"], row.iloc[0]["classification"])
            s = db.get(M.AnalysisSession, session_id)
            s.overview = {**(s.overview or {}), **summary}
            s.meta = {**(s.meta or {}), "scoring_config": cfg.to_dict()}
    return to_jsonable({"config": cfg.to_dict(), "blind_spots": df_records(scored), "recommendations": df_records(recs),
                        "summary": summary, "persisted": persist})
