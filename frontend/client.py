"""Frontend <-> backend gateway.

BLINDSPOT_MODE=local (default): calls the service layer in-process - one command to run everything.
BLINDSPOT_MODE=api            : talks to the FastAPI backend over HTTP (used by Docker Compose).
Both expose the same methods and raise ``ClientError`` with a user-readable message."""
from __future__ import annotations

import json
from typing import Any

from config.settings import settings


class ClientError(Exception):
    """User-facing error (shown in the UI as a message, never as a traceback)."""


class LocalClient:
    mode = "local"

    def __init__(self):
        from backend.services import analysis, companies, datasets
        from database.connection import init_db

        self._a, self._c, self._d = analysis, companies, datasets
        init_db()
        analysis.recover_stale_sessions()

    def _call(self, fn, *args, **kwargs):
        from backend.services.companies import Conflict, NotFound
        from backend.services.pipeline import PipelineError
        from ml.ingestion import IngestionError

        try:
            return fn(*args, **kwargs)
        except (NotFound, Conflict, IngestionError, PipelineError, ValueError) as exc:
            raise ClientError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ClientError(f"Unexpected error: {type(exc).__name__}: {exc}") from exc

    def health(self) -> dict: return {"status": "ok", "mode": "local"}
    def list_companies(self): return self._call(self._c.list_companies)
    def create_company(self, name, industry=None, description=None): return self._call(self._c.create_company, name, industry, description)
    def delete_company(self, cid): return self._call(self._c.delete_company, cid)
    def list_datasets(self, cid): return self._call(self._d.list_datasets, cid)
    def preview_upload(self, content, filename, kind, mapping=None): return self._call(self._d.preview_upload, content, filename, kind, mapping)
    def upload_dataset(self, cid, kind, content, filename, mapping=None, name=None): return self._call(self._d.ingest_file, cid, kind, content, filename, mapping, name)
    def add_text(self, cid, kind, text, source="manual_entry", name=None): return self._call(self._d.ingest_text, cid, kind, text, source, name)
    def add_url(self, cid, kind, url): return self._call(self._d.ingest_url, cid, kind, url)
    def load_sample(self, cid): return self._call(self._d.load_sample, cid)
    def dataset_records(self, did, limit=200): return self._call(self._d.dataset_records, did, limit)
    def delete_dataset(self, did): return self._call(self._d.delete_dataset, did)
    def start_analysis(self, cid, customer_ids=None, company_ids=None, scoring=None): return self._call(self._a.start_analysis, cid, customer_ids, company_ids, scoring)
    def analysis_status(self, sid): return self._call(self._a.session_status, sid)
    def list_analyses(self, cid): return self._call(self._a.list_sessions, cid)
    def get_bundle(self, sid): return self._call(self._a.get_bundle, sid)
    def delete_analysis(self, sid): return self._call(self._a.delete_session, sid)
    def topic_conversations(self, sid, tid, limit=300): return self._call(self._a.topic_conversations, sid, tid, limit)
    def rescore(self, sid, config, persist=False): return self._call(self._a.rescore_session, sid, config, persist)

    def get_scoring_config(self):
        from config.settings import load_scoring_config
        return load_scoring_config().to_dict()

    def save_scoring_config(self, cfg: dict):
        from config.settings import ScoringConfig, save_scoring_config
        new = ScoringConfig.from_dict(cfg)
        save_scoring_config(new)
        return new.to_dict()


class ApiClient:
    mode = "api"

    def __init__(self, base_url: str):
        import requests

        self._r = requests
        self.base = base_url.rstrip("/")

    def _req(self, method: str, path: str, **kw) -> Any:
        try:
            resp = self._r.request(method, self.base + path, timeout=kw.pop("timeout", 120), **kw)
        except self._r.ConnectionError as exc:
            raise ClientError(f"Cannot reach the backend at {self.base}. Is it running? (uvicorn backend.main:app)") from exc
        except self._r.Timeout as exc:
            raise ClientError("The backend took too long to respond.") from exc
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise ClientError(str(detail))
        return None if resp.status_code == 204 or not resp.content else resp.json()

    def health(self): return self._req("GET", "/health", timeout=5)
    def list_companies(self): return self._req("GET", "/companies")
    def create_company(self, name, industry=None, description=None): return self._req("POST", "/companies", json={"name": name, "industry": industry, "description": description})
    def delete_company(self, cid): return self._req("DELETE", f"/companies/{cid}")
    def list_datasets(self, cid): return self._req("GET", f"/companies/{cid}/datasets")
    def preview_upload(self, content, filename, kind, mapping=None):
        return self._req("POST", "/datasets/preview", files={"file": (filename, content)}, data={"kind": kind, "mapping": json.dumps(mapping) if mapping else ""})
    def upload_dataset(self, cid, kind, content, filename, mapping=None, name=None):
        return self._req("POST", f"/companies/{cid}/datasets/upload", files={"file": (filename, content)},
                         data={"kind": kind, "mapping": json.dumps(mapping) if mapping else "", "name": name or ""})
    def add_text(self, cid, kind, text, source="manual_entry", name=None): return self._req("POST", f"/companies/{cid}/datasets/text", json={"kind": kind, "text": text, "source": source, "name": name})
    def add_url(self, cid, kind, url): return self._req("POST", f"/companies/{cid}/datasets/url", json={"kind": kind, "url": url})
    def load_sample(self, cid): return self._req("POST", f"/companies/{cid}/datasets/sample")
    def dataset_records(self, did, limit=200): return self._req("GET", f"/datasets/{did}/records", params={"limit": limit})
    def delete_dataset(self, did): return self._req("DELETE", f"/datasets/{did}")
    def start_analysis(self, cid, customer_ids=None, company_ids=None, scoring=None):
        return self._req("POST", f"/companies/{cid}/analyses", json={"customer_source_ids": customer_ids, "company_source_ids": company_ids, "scoring": scoring})["session_id"]
    def analysis_status(self, sid): return self._req("GET", f"/analyses/{sid}/status")
    def list_analyses(self, cid): return self._req("GET", f"/companies/{cid}/analyses")
    def get_bundle(self, sid): return self._req("GET", f"/analyses/{sid}", timeout=300)
    def delete_analysis(self, sid): return self._req("DELETE", f"/analyses/{sid}")
    def topic_conversations(self, sid, tid, limit=300): return self._req("GET", f"/analyses/{sid}/topics/{tid}/conversations", params={"limit": limit})
    def rescore(self, sid, config, persist=False): return self._req("POST", f"/analyses/{sid}/rescore", json={"config": config, "persist": persist})
    def get_scoring_config(self): return self._req("GET", "/config/scoring")
    def save_scoring_config(self, cfg): return self._req("PUT", "/config/scoring", json=cfg)


def build_client():
    if settings.frontend_mode == "api":
        return ApiClient(settings.api_url)
    return LocalClient()
