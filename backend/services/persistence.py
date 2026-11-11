"""Save / load analysis results. Pure translation between pipeline DataFrames and database rows."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.services.companies import NotFound
from backend.services.pipeline import AnalysisResult
from backend.services.serialization import to_jsonable, df_records
from database import models as M


def _rows(df: pd.DataFrame | None, model, extra: dict | None = None, rename: dict | None = None) -> list:
    if df is None or len(df) == 0:
        return []
    cols = {c.name for c in model.__table__.columns} - {"id"}
    out = []
    for rec in df.to_dict(orient="records"):
        if rename:
            rec = {rename.get(k, k): v for k, v in rec.items()}
        row = {k: v for k, v in rec.items() if k in cols}
        for k, v in list(row.items()):
            if isinstance(v, (pd.Timestamp,)):
                row[k] = None if pd.isna(v) else v.to_pydatetime()
            elif isinstance(v, (list, dict)):
                row[k] = to_jsonable(v)
            elif v is pd.NaT:
                row[k] = None
            else:
                row[k] = _scalar(v)
        row.update(extra or {})
        out.append(model(**row))
    return out


def _scalar(v: Any) -> Any:
    import numpy as np

    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and v != v:
        return None
    return v


def save_result(db: Session, session_id: int, res: AnalysisResult) -> None:
    sid = {"session_id": session_id}
    db.add_all(_rows(res.topics, M.DetectedTopic, sid))
    cust = res.customer.copy()
    cust["conversation_id"] = cust["db_id"] if "db_id" in cust else None
    db.add_all(_rows(cust, M.SentimentResult, sid))
    db.add_all(_rows(res.mentions, M.AspectSentiment, sid))
    db.add_all(_rows(res.expectations, M.CustomerExpectation, sid))
    db.add_all(_rows(res.company_themes, M.CompanyMessagingTheme, sid))
    db.add_all(_rows(res.blind_spots, M.BlindSpotResult, sid))
    db.add_all(_rows(res.recommendations, M.BusinessRecommendation, sid))
    t = res.trends
    metrics: list[M.TrendMetric] = []
    for kind, df in (("series", t.topic_series), ("overall", t.overall_series)):
        for rec in df_records(df):
            period = rec.pop("period", None)
            tid = rec.pop("topic_id", None)
            metrics.append(M.TrendMetric(session_id=session_id, topic_id=tid, kind=kind,
                                         period=datetime.fromisoformat(period) if period else None, payload=rec))
    for kind, df in (("summary", t.topic_summary), ("spike", t.spikes)):
        for rec in df_records(df):
            period = rec.pop("period", None)
            tid = rec.get("topic_id")
            metrics.append(M.TrendMetric(session_id=session_id, topic_id=tid, kind=kind,
                                         period=datetime.fromisoformat(period) if period else None, payload=rec))
    for rec in to_jsonable(t.emerging):
        metrics.append(M.TrendMetric(session_id=session_id, topic_id=rec.get("topic_id"), kind="emerging", payload=rec))
    db.add_all(metrics)


def _obj(o) -> dict:
    d = {}
    for c in o.__table__.columns:
        v = getattr(o, c.name)
        d[c.name] = v.isoformat() if isinstance(v, datetime) else v
    return d


def load_bundle(db: Session, session_id: int) -> dict:
    """Everything the dashboard needs for one analysis session, as JSON-safe dicts."""
    s = db.get(M.AnalysisSession, session_id)
    if s is None:
        raise NotFound(f"Analysis {session_id} not found.")

    def q(model, order=None):
        stmt = select(model).where(model.session_id == session_id)
        if order is not None:
            stmt = stmt.order_by(order)
        return [_obj(o) for o in db.scalars(stmt)]

    trend = {k: [] for k in ("series", "overall", "summary", "spike", "emerging")}
    for m in db.scalars(select(M.TrendMetric).where(M.TrendMetric.session_id == session_id)):
        row = dict(m.payload or {})
        if m.topic_id is not None:
            row.setdefault("topic_id", m.topic_id)
        if m.period is not None:
            row["period"] = m.period.isoformat()
        trend[m.kind].append(row)
    session = _obj(s)
    return {
        "session": session, "overview": s.overview or {}, "meta": s.meta or {},
        "customer": q(M.SentimentResult, M.SentimentResult.record_id),
        "mentions": q(M.AspectSentiment),
        "topics": q(M.DetectedTopic, M.DetectedTopic.topic_id),
        "expectations": q(M.CustomerExpectation),
        "company_themes": q(M.CompanyMessagingTheme, M.CompanyMessagingTheme.n_messages.desc()),
        "blind_spots": q(M.BlindSpotResult, M.BlindSpotResult.rank),
        "recommendations": q(M.BusinessRecommendation, M.BusinessRecommendation.blind_spot_score.desc()),
        "trend_series": trend["series"], "trend_overall": trend["overall"], "trend_summary": trend["summary"],
        "trend_spikes": trend["spike"], "trend_emerging": trend["emerging"],
    }


def delete_results(db: Session, session_id: int, models: list) -> None:
    for model in models:
        db.execute(delete(model).where(model.session_id == session_id))
