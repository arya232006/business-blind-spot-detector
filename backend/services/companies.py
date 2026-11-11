"""Company CRUD. Every dataset and analysis is scoped to exactly one company."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from database import models as M
from database.connection import init_db, session_scope


class NotFound(LookupError):
    pass


class Conflict(ValueError):
    pass


def _dict(c: M.Company, n_sessions: int = 0, n_sources: int = 0) -> dict:
    return {"id": c.id, "name": c.name, "industry": c.industry, "description": c.description,
            "created_at": c.created_at.isoformat(), "n_analyses": n_sessions, "n_datasets": n_sources}


def create_company(name: str, industry: str | None = None, description: str | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Company name is required.")
    init_db()
    with session_scope() as db:
        c = M.Company(name=name, industry=(industry or None), description=(description or None))
        db.add(c)
        try:
            db.flush()
        except IntegrityError as exc:
            raise Conflict(f"A company named '{name}' already exists.") from exc
        return _dict(c)


def list_companies() -> list[dict]:
    init_db()
    with session_scope() as db:
        out = []
        for c in db.scalars(select(M.Company).order_by(M.Company.name)):
            ns = db.scalar(select(func.count()).select_from(M.AnalysisSession).where(M.AnalysisSession.company_id == c.id)) or 0
            nd = db.scalar(select(func.count()).select_from(M.DataSource).where(M.DataSource.company_id == c.id)) or 0
            out.append(_dict(c, ns, nd))
        return out


def get_company(company_id: int) -> dict:
    with session_scope() as db:
        c = db.get(M.Company, company_id)
        if c is None:
            raise NotFound(f"Company {company_id} not found.")
        return _dict(c)


def delete_company(company_id: int) -> None:
    with session_scope() as db:
        c = db.get(M.Company, company_id)
        if c is None:
            raise NotFound(f"Company {company_id} not found.")
        db.delete(c)  # cascades to data sources, conversations and analyses
