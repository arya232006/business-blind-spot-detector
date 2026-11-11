import numpy as np
import pytest

from config.settings import ScoringConfig
from ml.embeddings import l2_normalize
from ml.gap_analysis import classify_topic, compute_coverage, expectation_gap


def _vec(*xs):
    return l2_normalize(np.array([xs], dtype=float))[0]


def test_coverage_follows_semantic_alignment_not_keywords():
    centroids = np.vstack([_vec(1, 0, 0), _vec(0, 1, 0), _vec(0, 0, 1)])  # discounts, support, refunds
    msgs = np.vstack([_vec(1, .05, 0)] * 6 + [_vec(.1, 1, 0)] * 1 + [_vec(.2, .1, .1)])
    texts = [f"m{i}" for i in range(len(msgs))]
    cov, off = compute_coverage(msgs, texts, [0, 1, 2], centroids, semantic=True)
    c = cov.set_index("topic_id")
    assert c.loc[0, "coverage_norm"] == 100 and c.loc[0, "coverage_norm"] > c.loc[1, "coverage_norm"] > c.loc[2, "coverage_norm"]
    assert c.loc[2, "coverage_norm"] < 15
    assert 0 <= off <= 1 and cov["coverage_share"].sum() <= 1.0001
    assert len(c.loc[1, "top_messages"]) == 3 and c.loc[1, "top_messages"][0]["similarity"] >= c.loc[1, "top_messages"][1]["similarity"]


def test_offtopic_messages_excluded_from_coverage():
    centroids = np.vstack([_vec(1, 0), _vec(0, 1)])
    msgs = np.vstack([_vec(-1, -1)] * 4)  # unrelated to both topics
    cov, off = compute_coverage(msgs, list("abcd"), [0, 1], centroids, semantic=True)
    assert off == 1.0 and cov["coverage_share"].sum() == 0


def test_no_company_messages_means_zero_coverage():
    cov, off = compute_coverage(np.zeros((0, 2)), [], [0, 1], np.vstack([_vec(1, 0), _vec(0, 1)]))
    assert (cov["coverage_norm"] == 0).all() and off == 1.0


def test_gap_weights_configurable_and_bounded():
    cfg = ScoringConfig()
    assert expectation_gap(0, 0, cfg) == 100 and expectation_gap(100, 100, cfg) == 0
    assert expectation_gap(0, 100, ScoringConfig(w_coverage=1, w_similarity=0)) == 100
    assert expectation_gap(0, 100, ScoringConfig(w_coverage=0, w_similarity=1)) == 0


@pytest.mark.parametrize("kwargs,expected", [
    (dict(importance=80, gap=90, neg_pct=70, explicit_share=5, coverage_norm=5), "genuine_blind_spot"),
    (dict(importance=80, gap=60, neg_pct=70, explicit_share=5, coverage_norm=40), "negative_experience"),   # company DOES talk about it
    (dict(importance=80, gap=10, neg_pct=70, explicit_share=5, coverage_norm=90), "negative_experience"),
    (dict(importance=70, gap=80, neg_pct=60, explicit_share=40, coverage_norm=5), "unmet_operational_need"),
    (dict(importance=45, gap=70, neg_pct=10, explicit_share=0, coverage_norm=20), "communication_gap"),
    (dict(importance=20, gap=0, neg_pct=5, explicit_share=0, coverage_norm=100), "misplaced_emphasis"),
    (dict(importance=45, gap=5, neg_pct=12, explicit_share=0, coverage_norm=100), "misplaced_emphasis"),   # promoted far beyond its importance
    (dict(importance=70, gap=10, neg_pct=12, explicit_share=0, coverage_norm=100), "aligned"),
    (dict(importance=10, gap=10, neg_pct=10, explicit_share=0, coverage_norm=30), "aligned"),
])
def test_classification_distinguishes_the_four_concepts(kwargs, expected):
    assert classify_topic(cfg=ScoringConfig(), **kwargs) == expected
