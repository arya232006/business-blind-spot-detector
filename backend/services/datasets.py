"""Data collection services: preview / validate / store customer and company datasets."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

from backend.services.companies import NotFound
from backend.services.serialization import df_records, to_jsonable
from config.logging_config import get_logger
from config.settings import settings
from database import models as M
from database.connection import init_db, session_scope
from ml.ingestion import (IngestionError, STANDARD_COLUMNS, detect_mapping, extract_url, from_manual_text,
                          parse_tabular, standardize)

log = get_logger(__name__)
KINDS = ("customer", "company")


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError("kind must be 'customer' or 'company'")


def _source_type(filename: str) -> str:
    f = (filename or "").lower()
    return "excel" if f.endswith((".xlsx", ".xls", ".xlsm")) else "txt" if f.endswith(".txt") else "csv"


def preview_upload(content: bytes, filename: str, kind: str, mapping: dict | None = None, n: int = 15) -> dict:
    """Parse + validate WITHOUT saving. Returns detected column mapping, a preview and the validation report."""
    _check_kind(kind)
    raw = parse_tabular(content, filename)
    std, rep = standardize(raw, kind, mapping=mapping, default_source=Path(filename).stem or "upload")
    return {
        "columns": [str(c) for c in raw.columns], "detected_mapping": detect_mapping(list(raw.columns)),
        "mapping_used": rep.mapping, "preview": df_records(std.head(n)), "n_rows": int(len(std)),
        "report": rep.to_dict(),
    }


def _save(company_id: int, kind: str, std: pd.DataFrame, source_type: str, name: str, filename: str | None,
          report: dict | None, origin_url: str | None = None, is_synthetic: bool = False) -> dict:
    if std is None or len(std) == 0:
        raise IngestionError("The dataset has no valid records to save.")
    init_db()
    with session_scope() as db:
        if db.get(M.Company, company_id) is None:
            raise NotFound(f"Company {company_id} not found.")
        src = M.DataSource(company_id=company_id, kind=kind, source_type=source_type, name=name, filename=filename,
                           origin_url=origin_url, is_synthetic=is_synthetic, n_records=len(std), validation=to_jsonable(report))
        db.add(src)
        db.flush()
        rows = []
        synth = std["is_synthetic"].astype(bool) if "is_synthetic" in std else pd.Series(is_synthetic, index=std.index)
        for (_, r), is_syn in zip(std.iterrows(), synth):
            common = dict(company_id=company_id, data_source_id=src.id, text=str(r["text"]), source=_none(r["source"]),
                          date=None if pd.isna(r["date"]) else pd.Timestamp(r["date"]).to_pydatetime(),
                          category=_none(r["category"]), extra=to_jsonable(r["metadata"]) if isinstance(r["metadata"], dict) else None,
                          is_synthetic=bool(is_syn) or is_synthetic)
            if kind == "customer":
                rows.append(M.CustomerConversation(**common, customer_id=_none(r["customer_id"]),
                                                   rating=None if pd.isna(r["rating"]) else float(r["rating"])))
            else:
                rows.append(M.CompanyCommunication(**common))
        db.add_all(rows)
        log.info("Saved dataset %s (%s, %d records) for company %s", src.id, kind, len(rows), company_id)
        return _src_dict(src)


def _none(v):
    return None if v is None or (isinstance(v, float) and v != v) or str(v) in ("None", "nan", "NaT") else str(v)


def _src_dict(s: M.DataSource) -> dict:
    return {"id": s.id, "company_id": s.company_id, "kind": s.kind, "source_type": s.source_type, "name": s.name,
            "filename": s.filename, "origin_url": s.origin_url, "is_synthetic": s.is_synthetic,
            "n_records": s.n_records, "created_at": s.created_at.isoformat(), "validation": s.validation}


def ingest_file(company_id: int, kind: str, content: bytes, filename: str, mapping: dict | None = None,
                name: str | None = None) -> dict:
    _check_kind(kind)
    raw = parse_tabular(content, filename)
    std, rep = standardize(raw, kind, mapping=mapping, default_source=Path(filename).stem or "upload")
    if not rep.ok:
        raise IngestionError("; ".join(rep.errors) or "Dataset failed validation.")
    return _save(company_id, kind, std, _source_type(filename), name or filename, filename, rep.to_dict())


def ingest_text(company_id: int, kind: str, text: str, source: str = "manual_entry", name: str | None = None) -> dict:
    _check_kind(kind)
    std, rep = from_manual_text(text, kind, source=source)
    if not rep.ok:
        raise IngestionError("; ".join(rep.errors))
    return _save(company_id, kind, std, "manual", name or f"Manual entry ({len(std)} records)", None, rep.to_dict())


def ingest_url(company_id: int, kind: str, url: str) -> dict:
    _check_kind(kind)
    std, rep = extract_url(url, kind)
    return _save(company_id, kind, std, "url", f"Web page: {url[:120]}", None, rep.to_dict(), origin_url=url)


def load_sample(company_id: int) -> dict:
    """Load the synthetic NovaCart demo datasets into a company (idempotent)."""
    init_db()
    with session_scope() as db:
        existing = db.scalars(select(M.DataSource).where(M.DataSource.company_id == company_id,
                                                         M.DataSource.source_type == "sample")).all()
        if len(existing) >= 2:
            return {"loaded": False, "message": "Sample datasets are already loaded for this company.",
                    "datasets": [_src_dict(s) for s in existing]}
    made = []
    for kind, path in (("customer", settings.sample_customer_csv), ("company", settings.sample_company_csv)):
        if not path.exists():
            raise IngestionError(f"Sample file missing: {path.name}. Run: python data/generate_sample_data.py")
        raw = pd.read_csv(path)
        std, rep = standardize(raw, kind, default_source="sample")
        made.append(_save(company_id, kind, std, "sample", f"[SYNTHETIC DEMO] NovaCart {kind} data", path.name,
                          rep.to_dict(), is_synthetic=True))
    return {"loaded": True, "message": "Synthetic NovaCart demo data loaded.", "datasets": made}


def list_datasets(company_id: int) -> list[dict]:
    init_db()
    with session_scope() as db:
        return [_src_dict(s) for s in db.scalars(select(M.DataSource).where(M.DataSource.company_id == company_id)
                                                 .order_by(M.DataSource.created_at.desc()))]


def dataset_records(dataset_id: int, limit: int = 200) -> list[dict]:
    with session_scope() as db:
        s = db.get(M.DataSource, dataset_id)
        if s is None:
            raise NotFound(f"Dataset {dataset_id} not found.")
        model = M.CustomerConversation if s.kind == "customer" else M.CompanyCommunication
        rows = db.scalars(select(model).where(model.data_source_id == dataset_id).limit(limit)).all()
        return [{"text": r.text, "source": r.source, "date": r.date.isoformat() if r.date else None, "category": r.category,
                 **({"customer_id": r.customer_id} if s.kind == "customer" else {})} for r in rows]


def delete_dataset(dataset_id: int) -> None:
    with session_scope() as db:
        s = db.get(M.DataSource, dataset_id)
        if s is None:
            raise NotFound(f"Dataset {dataset_id} not found.")
        db.delete(s)


def load_frame(company_id: int, kind: str, source_ids: list[int] | None = None) -> pd.DataFrame:
    """Records of a company's datasets as a standard dataframe (+ db_id). Never crosses company boundaries."""
    model = M.CustomerConversation if kind == "customer" else M.CompanyCommunication
    with session_scope() as db:
        stmt = select(model).where(model.company_id == company_id)
        if source_ids:
            stmt = stmt.where(model.data_source_id.in_(source_ids))
        rows = db.scalars(stmt).all()
        data = [{"db_id": r.id, "text": r.text, "source": r.source, "date": r.date, "category": r.category,
                 "customer_id": getattr(r, "customer_id", None), "rating": getattr(r, "rating", None),
                 "metadata": r.extra or {}, "data_source_id": r.data_source_id, "is_synthetic": r.is_synthetic} for r in rows]
    df = pd.DataFrame(data, columns=["db_id", *STANDARD_COLUMNS, "data_source_id", "is_synthetic"])
    df["date"] = pd.to_datetime(df["date"])
    return df
