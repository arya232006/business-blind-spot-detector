import pandas as pd

from ml.recommendations import categorize_topics, extract_wait_days, generate_recommendations


def _bs():
    ev = [{"record_id": 1, "text": "Waited 12 days for my refund", "compound": -.5, "date": "2026-10-01"},
          {"record_id": 2, "text": "Still no refund after 2 weeks", "compound": -.6, "date": "2026-10-02"}]
    base = dict(keywords=["refund"], trend_status="increasing", evidence_quotes=ev, closest_company_messages=[], mentions=60,
                unique_customers=50, neg_pct=70.0, share_pct=40.0, coverage_norm=5.0)
    return pd.DataFrame([
        dict(topic_id=0, topic_label="refund, money", classification="genuine_blind_spot", severity="High", score=65.0, importance=85.0, **base),
        dict(topic_id=1, topic_label="discounts", classification="misplaced_emphasis", severity="Low", score=0.5, importance=20.0, **{**base, "coverage_norm": 100.0}),
        dict(topic_id=2, topic_label="app speed", classification="aligned", severity="Low", score=1.0, importance=30.0, **base),
    ])


def test_extract_wait_days():
    assert extract_wait_days(["Waited 12 days", "took 2 weeks", "no numbers here"]) == [12.0, 14.0]


def test_recommendations_are_grounded_and_complete():
    recs = generate_recommendations(_bs(), pd.DataFrame(), {0: "Operational", 1: "Communication", 2: "Product"})
    assert not recs.empty and "app speed" not in set(recs["topic_label"])           # aligned topics get no recommendation
    top = recs[recs["topic_label"] == "refund, money"]
    assert set(top["category"]) == {"Operational", "Communication"}
    p = top[top["category"] == "Operational"].iloc[0]
    assert p["priority"].startswith("P0") and p["blind_spot_score"] == 65.0         # High severity + increasing -> bumped up
    assert "70%" in p["problem"] and "60 statements" in p["problem"] and "median of 13 days" in p["problem"]
    assert len(p["evidence"]) == 2 and "forecast" in p["expected_impact"]
    for col in ("problem", "suggested_action", "expected_impact", "priority", "severity", "blind_spot_score", "evidence"):
        assert recs[col].notna().all()
    assert (recs[recs["topic_label"] == "discounts"]["category"] == "Communication").all()


def test_empty_input():
    assert generate_recommendations(pd.DataFrame(), pd.DataFrame(), {}).empty


def test_categorisation_rules():
    cats = categorize_topics([{"topic_id": 0, "label": "support, ticket, agent", "keywords": []},
                              {"topic_id": 1, "label": "refund, delivery, payment", "keywords": []},
                              {"topic_id": 2, "label": "app, crash, screen", "keywords": []}], None)
    assert cats == {0: "Customer Support", 1: "Operational", 2: "Product"}
