"""Re-scoring from stored component values.

The expensive NLP never has to be re-run to change scoring weights: the pipeline stores every normalised component
(frequency/customers/sentiment/explicit scores, coverage_norm, similarity_norm, growth/negative-trend scores) and this
function recomputes importance, gap, trend, score, severity and classification for a given ScoringConfig.
Used by the pipeline itself AND by the dashboard's 'scoring weights' panel -> a single code path."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import ScoringConfig
from ml.gap_analysis import classify_topic, expectation_gap, CLASS_LABELS
from ml.scoring.engine import combine_trend, score_topics


def rescore_blind_spots(df: pd.DataFrame, cfg: ScoringConfig) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    w = cfg.normalised("w_frequency", "w_unique_customers", "w_sentiment", "w_explicit_requests")
    out["importance"] = (w["w_frequency"] * out["frequency_score"] + w["w_unique_customers"] * out["customers_score"]
                         + w["w_sentiment"] * out["sentiment_score"] + w["w_explicit_requests"] * out["explicit_score"]).clip(0, 100)
    out["gap"] = [expectation_gap(c, s, cfg) for c, s in zip(out["coverage_norm"], out["similarity_norm"])]
    trends = []
    for _, r in out.iterrows():
        enough = bool(r.get("trend_enough", False)) and pd.notna(r.get("growth_score"))
        trends.append(combine_trend(r["growth_score"], r["negative_trend_score"], cfg) if enough else None)
    out["trend"] = trends
    scored = score_topics(out[["topic_id", "importance", "gap", "trend"]], cfg)
    for col in ("trend_used", "trend_available", "score", "severity"):
        out[col] = scored[col].values
    out["classification"] = [
        classify_topic(r["importance"], r["gap"], r["neg_pct"], r["explicit_share_pct"], r["coverage_norm"], cfg)
        for _, r in out.iterrows()
    ]
    out["classification_label"] = out["classification"].map(CLASS_LABELS)
    out["rank"] = out["score"].rank(ascending=False, method="first").astype(int)
    return out.sort_values("score", ascending=False).reset_index(drop=True)
