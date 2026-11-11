import numpy as np
import pandas as pd
import pytest

from config.settings import ScoringConfig
from ml.scoring.engine import (blind_spot_score, combine_trend, customer_importance_components, effective_trend, score_topics,
                               severity_label)
from ml.scoring.rescore import rescore_blind_spots


def test_spec_worked_example():
    assert blind_spot_score(85, 90, 80) == 61.2
    assert severity_label(61.2) == "High"


@pytest.mark.parametrize("score,expected", [(0, "Low"), (20, "Low"), (20.5, "Moderate"), (40, "Moderate"), (41, "Significant"),
                                            (60, "Significant"), (61, "High"), (80, "High"), (81, "Critical"), (100, "Critical")])
def test_severity_bands(score, expected):
    assert severity_label(score) == expected


def test_score_is_clipped_and_bounded():
    assert blind_spot_score(150, 150, 150) == 100.0
    assert blind_spot_score(-5, 90, 80) == 0.0
    assert blind_spot_score(0, 100, 100) == 0.0


def test_trend_unavailable_uses_documented_neutral_fallback(cfg):
    value, ok = effective_trend(None, cfg)
    assert (value, ok) == (cfg.neutral_trend, False)
    value, ok = effective_trend(float("nan"), cfg)
    assert ok is False


def test_trend_floor_dampens_but_never_zeroes(cfg):
    value, ok = effective_trend(0.0, cfg)
    assert ok and value == cfg.trend_floor and value > 0


def test_weights_are_normalised():
    cfg = ScoringConfig(w_frequency=3, w_unique_customers=1, w_sentiment=0, w_explicit_requests=0)
    w = cfg.normalised("w_frequency", "w_unique_customers", "w_sentiment", "w_explicit_requests")
    assert pytest.approx(sum(w.values())) == 1.0 and w["w_frequency"] == 0.75


def _stats():
    return pd.DataFrame({"topic_id": [0, 1], "mentions": [60, 20], "unique_customers": [50, 10], "negative_pct": [80.0, 10.0],
                         "neg_intensity": [0.6, 0.05], "explicit_share_pct": [30.0, 0.0]})


def test_importance_orders_topics_sensibly(cfg):
    comps = customer_importance_components(_stats(), cfg)
    assert comps.loc[0, "importance"] > comps.loc[1, "importance"]
    assert comps["importance"].between(0, 100).all()
    assert comps.loc[0, "frequency_score"] == 100  # the most frequent topic defines the scale
    assert comps.loc[0, "explicit_score"] == 100


def test_score_topics_pipeline_matches_formula(cfg):
    comps = pd.DataFrame({"topic_id": [0, 1], "importance": [85.0, 50.0], "gap": [90.0, 20.0], "trend": [80.0, None]})
    out = score_topics(comps, cfg)
    assert out.loc[0, "score"] == 61.2 and out.loc[0, "severity"] == "High"
    assert bool(out.loc[1, "trend_available"]) is False and out.loc[1, "trend_used"] == cfg.neutral_trend
    assert out.loc[1, "score"] == blind_spot_score(50, 20, cfg.neutral_trend)


def test_combine_trend_bounds(cfg):
    assert combine_trend(50, 50, cfg) == 50
    assert 0 <= combine_trend(-100, -100, cfg) <= 100 and combine_trend(500, 500, cfg) == 100


def test_rescore_changes_with_weights_and_keeps_components(pipeline_result, cfg):
    bs = pipeline_result.blind_spots.drop(columns=["rank", "classification_label"], errors="ignore")
    base = rescore_blind_spots(bs, cfg)
    assert np.allclose(base.sort_values("topic_id")["score"].values, pipeline_result.blind_spots.sort_values("topic_id")["score"].values)
    only_cov = rescore_blind_spots(bs, ScoringConfig(w_coverage=1.0, w_similarity=0.0))
    merged = base.merge(only_cov, on="topic_id", suffixes=("_a", "_b"))
    assert not np.allclose(merged["gap_a"], merged["gap_b"])
    assert (only_cov["score"].between(0, 100)).all()
