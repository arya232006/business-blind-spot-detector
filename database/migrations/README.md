# Database migrations

Tables are created automatically on start-up (`database.connection.init_db`, idempotent `CREATE TABLE IF NOT EXISTS`
semantics through SQLAlchemy). The reference DDL is generated from `database/models.py`:

```bash
python database/migrations/generate_schema.py   # rewrites the two .sql files
psql "$DATABASE_URL_PSQL" -f database/migrations/001_initial_schema.postgresql.sql   # optional manual apply
```

Schema changes during development: add a new numbered migration file here and document it. The project does not use
Alembic to keep the student-project stack small; if you outgrow `create_all`, `alembic init` can be pointed at
`database.models.Base.metadata` without any other change.
