import numpy as np
import pytest

from ml.embeddings import TfidfLsaEmbedder
from ml.sentiment import analyze_documents, aspect_term, extract_aspect_mentions, label_from_score, overall_sentiment, vader_score
from ml.text_utils import split_clauses


def test_vader_baseline_polarity():
    assert vader_score("This is great, I love it") > 0.5
    assert vader_score("This is terrible and awful") < -0.5


def test_label_thresholds():
    assert label_from_score(0.05) == "positive" and label_from_score(-0.05) == "negative" and label_from_score(0.0) == "neutral"


@pytest.mark.parametrize("text", ["I've been waiting three days for a refund.", "Support promised a callback and never called.",
                                  "Nobody responds when I raise a support ticket.", "Fast delivery? Mine took 11 days and there was no update."])
def test_domain_rules_catch_implicit_complaints(text):
    assert vader_score(text) < -0.05


def test_support_noun_is_not_praise():
    assert vader_score("I contacted support yesterday") == 0.0


def test_strong_praise_not_overridden():
    assert vader_score("Great quality, I never had a problem and it arrived quickly. Love it!") > 0.5


def test_document_summary_percentages_add_up():
    df = analyze_documents(["great product", "awful delay", "it arrived", "terrible support", "love it"], use_transformer=False)
    s = overall_sentiment(df)
    assert s["n"] == 5 and abs(s["positive_pct"] + s["negative_pct"] + s["neutral_pct"] - 100) < 1e-9


def test_clause_split_separates_aspects():
    parts = split_clauses("The phone camera is amazing, but the battery backup is disappointing.")
    assert len(parts) == 2 and "camera" in parts[0] and "battery" in parts[1]


def test_aspect_based_sentiment_gives_different_sentiment_per_aspect():
    mixed = "The phone camera is amazing, but the battery backup is disappointing."
    camera_docs = ["The camera photos are excellent and beautiful", "Camera is great, photos look amazing", "Love the camera quality and photos",
                   "Amazing camera, the photos are sharp"]
    battery_docs = ["Battery drains quickly, terrible battery life", "The battery died, disappointing backup", "Battery backup is awful",
                    "Poor battery, it drains by noon"]
    texts = [mixed] + camera_docs + battery_docs
    emb = TfidfLsaEmbedder(n_components=8).fit(texts)
    vecs = emb.encode(texts)

    def centroid(idx):
        c = vecs[idx].mean(axis=0)
        return c / np.linalg.norm(c)

    centroids = np.vstack([centroid([1, 2, 3, 4]), centroid([5, 6, 7, 8])])  # like the pipeline: mean of member docs
    doc_topics = [0] + [0] * 4 + [1] * 4
    m = extract_aspect_mentions(texts, list(range(len(texts))), doc_topics, emb, [0, 1], centroids, {0: ["camera"], 1: ["battery"]})
    first = m[m["record_id"] == 0]
    by_topic = dict(zip(first["topic_id"], first["label"]))
    assert by_topic.get(0) == "positive" and by_topic.get(1) == "negative"
    assert set(first["aspect"]) >= {"camera", "battery"}


def test_aspect_term_prefers_topic_keyword():
    assert aspect_term("the battery backup is disappointing", ["battery"]) == "battery"
    assert aspect_term("the battery backup is disappointing") == "battery backup"
