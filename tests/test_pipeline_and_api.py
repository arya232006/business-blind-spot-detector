import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.services.pipeline import FLAGGED, PipelineError, run_pipeline


def test_pipeline_end_to_end_on_demo_data(pipeline_result, cfg):
    r = pipeline_result
    assert r.overview["total_conversations"] > 100 and r.overview["total_company_messages"] >= 30
    assert r.overview["total_topics"] >= 3 and len(r.blind_spots) == r.overview["total_topics"]
    bs = r.blind_spots
    # every score is dynamically calculated from its components with the documented formula
    assert np.allclose(bs["score"], (bs["importance"] * bs["gap"] * bs["trend_used"] / 10000).round(2), atol=0.011)
    assert bs[["importance", "gap", "trend_used", "score"]].apply(lambda c: c.between(0, 100)).all().all()
    # every blind spot has supporting evidence (quotes + closest company messages)
    assert bs["evidence_quotes"].map(len).min() > 0 and bs["closest_company_messages"].map(len).min() > 0
    assert {"genuine_blind_spot", "unmet_operational_need", "negative_experience", "communication_gap", "misplaced_emphasis", "aligned"} >= set(bs["classification"])
    # the demo data was designed so that refunds/support are under-communicated and discounts over-communicated
    assert (bs["classification"].isin(FLAGGED)).any()
    assert bs.sort_values("coverage_norm").iloc[0]["coverage_norm"] < bs.sort_values("coverage_norm").iloc[-1]["coverage_norm"]
    assert not r.expectations.empty and r.expectations[r.expectations["kind"] == "inferred_expectation"]["is_inferred"].all()
    assert not r.recommendations.empty and r.meta["trend_available"]


def test_customer_and_company_are_analysed_separately_before_comparison(pipeline_result):
    assert "topic_id" in pipeline_result.customer and "topic_id" not in pipeline_result.company
    assert len(pipeline_result.company_themes) >= 2 and pipeline_result.company_themes["share_pct"].sum() == pytest.approx(100, abs=1)


def test_pipeline_errors_are_user_readable(sample_frames):
    cust, comp = sample_frames
    with pytest.raises(PipelineError, match="No customer data"):
        run_pipeline(cust.iloc[0:0], comp)
    with pytest.raises(PipelineError, match="No company"):
        run_pipeline(cust, comp.iloc[0:0])
    with pytest.raises(PipelineError, match="usable customer records"):
        run_pipeline(cust.head(3), comp)


def test_pipeline_without_dates_degrades_gracefully(sample_frames, cfg):
    cust, comp = sample_frames
    r = run_pipeline(cust.assign(date=pd.NaT), comp, cfg, use_llm=False)
    assert not r.meta["trend_available"] and not r.blind_spots["trend_available"].any()
    assert (r.blind_spots["trend_used"] == cfg.neutral_trend).all()      # documented neutral fallback, never an invented trend
    assert any("unavailable" in n.lower() for n in r.meta["notes"])


@pytest.fixture(scope="module")
def client():
    from backend.main import app

    with TestClient(app) as c:
        yield c


def _wait(client, sid, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = client.get(f"/analyses/{sid}/status").json()
        if st["status"] != "running":
            return st
        time.sleep(0.5)
    raise AssertionError("analysis did not finish")


def test_api_company_and_dataset_validation(client):
    r = client.post("/companies", json={"name": "ValCo"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post("/companies", json={"name": "ValCo"}).status_code == 409
    assert client.get("/companies/9999").status_code == 404
    assert client.post(f"/companies/{cid}/datasets/upload", files={"file": ("a.csv", b"")}, data={"kind": "customer"}).status_code == 422
    assert client.post(f"/companies/{cid}/datasets/upload", files={"file": ("a.csv", b"x,y\n1,2\n")}, data={"kind": "customer"}).status_code == 422
    assert client.post(f"/companies/{cid}/datasets/upload", files={"file": ("a.pdf", b"abc")}, data={"kind": "customer"}).status_code == 422
    ok = client.post(f"/companies/{cid}/datasets/upload", files={"file": ("a.csv", b"review,date\nrefund took too long,2026-01-01\n")}, data={"kind": "customer"})
    assert ok.status_code == 201 and ok.json()["n_records"] == 1
    assert client.post("/datasets/preview", files={"file": ("a.csv", b"review\nhello there world\n")}, data={"kind": "customer"}).json()["n_rows"] == 1
    assert client.post(f"/companies/{cid}/analyses").status_code == 202
    assert client.post(f"/companies/9999/analyses").status_code == 404


def test_api_full_workflow_and_company_isolation(client):
    a = client.post("/companies", json={"name": "IsoA"}).json()["id"]
    b = client.post("/companies", json={"name": "IsoB"}).json()["id"]
    assert client.post(f"/companies/{a}/datasets/sample").json()["loaded"] is True
    assert client.post(f"/companies/{a}/datasets/sample").json()["loaded"] is False      # idempotent
    sid = client.post(f"/companies/{a}/analyses").json()["session_id"]
    assert _wait(client, sid)["status"] == "completed"
    bundle = client.get(f"/analyses/{sid}").json()
    assert bundle["session"]["company_id"] == a and bundle["session"]["is_synthetic"] is True
    assert len(bundle["topics"]) >= 3 and len(bundle["blind_spots"]) == len(bundle["topics"]) and bundle["trend_series"]
    tid = bundle["topics"][0]["topic_id"]
    convs = client.get(f"/analyses/{sid}/topics/{tid}/conversations").json()
    assert convs and {"statement", "full_text", "aspect_label"} <= set(convs[0])
    # company B has no data and must not see company A's records or analyses
    assert client.get(f"/companies/{b}/datasets").json() == [] and client.get(f"/companies/{b}/analyses").json() == []
    sid_b = client.post(f"/companies/{b}/analyses").json()["session_id"]
    st = _wait(client, sid_b)
    assert st["status"] == "failed" and "No customer data" in st["error"]
    # re-scoring with other weights works without re-running NLP
    rs = client.post(f"/analyses/{sid}/rescore", json={"config": {"w_coverage": 1.0, "w_similarity": 0.0}}).json()
    assert rs["persisted"] is False and len(rs["blind_spots"]) == len(bundle["blind_spots"])
    assert client.get(f"/analyses/{sid}").json()["blind_spots"][0]["score"] == bundle["blind_spots"][0]["score"]  # preview did not persist
    assert client.post(f"/analyses/{sid}/rescore", json={"config": {"w_coverage": 1.0, "w_similarity": 0.0}, "persist": True}).json()["persisted"]
    assert client.delete(f"/analyses/{sid}").status_code == 204 and client.get(f"/analyses/{sid}").status_code == 404
    assert client.delete(f"/companies/{a}").status_code == 204


def test_api_scoring_config_roundtrip(client):
    cfg = client.get("/config/scoring").json()
    assert cfg["w_frequency"] == pytest.approx(0.30)
    assert client.put("/config/scoring", json={**cfg, "w_frequency": -1}).status_code == 422   # validated


def test_cors_only_for_explicit_origins_and_private_network_preflight(client):
    ok = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET", "Access-Control-Request-Private-Network": "true"}
    r = client.options("/companies", headers=ok)
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert r.headers.get("access-control-allow-private-network") == "true"
    evil = {**ok, "Origin": "https://evil.vercel.app"}
    r2 = client.options("/companies", headers=evil)
    assert "access-control-allow-origin" not in r2.headers and "access-control-allow-private-network" not in r2.headers
    assert client.get("/companies", headers={"Origin": "https://evil.vercel.app"}).headers.get("access-control-allow-origin") is None
