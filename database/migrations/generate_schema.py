"""Generate the reference SQL schema from the SQLAlchemy models (PostgreSQL + SQLite dialects).

    python database/migrations/generate_schema.py

The application creates tables automatically at start-up (``init_db``); these .sql files exist so a DBA can review or
apply the schema manually, e.g.  psql -f database/migrations/001_initial_schema.postgresql.sql"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy.dialects import postgresql, sqlite  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from database.models import Base  # noqa: E402


def render(dialect, title: str) -> str:
    out = [f"-- Business Blind Spot Detector - initial schema ({title})", "-- Generated from database/models.py - do not edit by hand.", ""]
    for table in Base.metadata.sorted_tables:
        out.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for idx in sorted(table.indexes, key=lambda i: i.name or ""):
            out.append(str(CreateIndex(idx).compile(dialect=dialect)).strip() + ";")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    here = Path(__file__).parent
    (here / "001_initial_schema.postgresql.sql").write_text(render(postgresql.dialect(), "PostgreSQL"))
    (here / "001_initial_schema.sqlite.sql").write_text(render(sqlite.dialect(), "SQLite"))
    print("Wrote", *(p.name for p in sorted(here.glob("*.sql"))))
