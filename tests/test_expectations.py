import pandas as pd
import pytest

from ml.embeddings import TfidfLsaEmbedder
from ml.expectation_detection import classify_statement, detect_expectations, infer_expectations


@pytest.mark.parametrize("text,compound,expected", [
    ("Please add a dark mode option", 0.3, "feature_request"),
    ("I wish the app allowed saving multiple addresses", 0.1, "feature_request"),
    ("I only wanted my money back", -0.2, "explicit_expectation"),
    ("Refund was promised in 5 days", -0.1, "explicit_expectation"),
    ("There is no phone number anywhere", -0.3, "unmet_need"),
    ("Nobody responds when I raise a ticket", 0.0, "complaint"),
    ("The delivery was a disaster", -0.6, "complaint"),
])
def test_statement_signals(text, compound, expected):
    assert expected in classify_statement(text, compound)


def test_neutral_praise_has_no_signals():
    assert classify_statement("Delivery was on time", 0.4) == []


def test_inferred_expectations_from_complaints():
    complaints = ["I've been waiting three days for a refund", "Refund took forever", "Nobody replied to my ticket",
                  "It takes forever to speak to an actual person", "I cannot reach a human agent, the chatbot is useless"]
    labels = [p for p, _ in infer_expectations(complaints, top_k=4, min_share=0.2)]
    assert any("faster" in p for p in labels) and any("human" in p for p in labels)
    assert infer_expectations([]) == []


def _mentions():
    rows = [
        (0, "Please add a dark mode option", 0.3), (1, "Would love a wishlist feature", 0.2),
        (2, "Nobody responds when I raise a support ticket", -0.35), (3, "The chatbot never solves anything", -0.35),
        (4, "It takes forever to speak to an actual human", -0.34), (5, "Support ticket closed without any reply", -0.35),
        (6, "There is no phone number anywhere", -0.55), (7, "Support is slow, I expect a reply within a day", -0.3),
    ]
    m = pd.DataFrame(rows, columns=["record_id", "clause", "compound"])
    m["topic_id"] = [0, 0, 1, 1, 1, 1, 1, 1]
    m["label"] = ["positive", "positive"] + ["negative"] * 6
    m["date"] = pd.date_range("2026-01-01", periods=8, freq="7D")
    m["customer_id"] = ["a", "b", "c", "d", "e", "f", "g", "c"]
    records = m[["record_id", "customer_id", "date"]].assign(text_clean=m["clause"])
    return m, records


def test_detect_expectations_marks_inferred_and_keeps_explicit_separate():
    m, records = _mentions()
    topics = [{"topic_id": 0, "label": "features"}, {"topic_id": 1, "label": "support"}]
    emb = TfidfLsaEmbedder(n_components=6).fit(m["clause"].tolist())
    out = detect_expectations(m, records, topics, emb)
    assert set(out["kind"]) >= {"feature_request", "complaint", "inferred_expectation", "unmet_need"}
    inferred = out[out["kind"] == "inferred_expectation"]
    assert len(inferred) and inferred["is_inferred"].all() and inferred["summary"].str.startswith("INFERRED").all()
    explicit = out[out["kind"].isin(["feature_request", "unmet_need", "explicit_expectation"])]
    assert (~explicit["is_inferred"]).all()
    assert all(len(e) > 0 for e in out["evidence"])  # every insight carries supporting quotes
    rec = out[out["kind"] == "recurring_frustration"]
    assert len(rec) == 0 or rec["topic_id"].eq(1).all()


def test_empty_mentions_returns_empty_frame():
    out = detect_expectations(pd.DataFrame(), pd.DataFrame(), [], TfidfLsaEmbedder())
    assert out.empty and "kind" in out
