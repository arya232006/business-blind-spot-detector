"""Module 8 - Blind Spot Scoring Engine (fully deterministic, no ML models involved).

    Blind Spot Score = Customer Importance x Expectation Gap x Issue Trend / 100^2        (0-100)

All three components are normalised to 0-100 first:

Customer Importance (0-100), weights configurable
    frequency        100 x mentions / max mentions over topics
    unique customers 100 x distinct customers / max over topics
    sentiment        100 x (0.7 x negative-share + 0.3 x min(1, mean negative intensity / 0.5))
    explicit         min(100, 100 x share of statements that are explicit requests/expectations/unmet needs / 30%)
Expectation Gap (0-100)     = w_cov (100 - coverage_norm) + w_sim (100 - similarity_norm)   (see ml.gap_analysis)
Issue Trend (0-100)         50 = no change, 100 = strongly rising + more negative, 0 = strongly falling (ml.trend_detection)
                            If history is insufficient the neutral fallback (cfg.neutral_trend, default 50) is used and the
                            result is flagged ``trend_available = False``. The trend is clipped below at cfg.trend_floor so a
                            fading issue is down-weighted but never silently erased.

Worked example: importance 85, gap 90, trend 80  ->  85 x 90 x 80 / 10000 = 61.2  -> 'High'.
Severity: 0-20 Low, 21-40 Moderate, 41-60 Significant, 61-80 High, 81-100 Critical."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import ScoringConfig

SEVERITY_BANDS = [(20, "Low"), (40, "Moderate"), (60, "Significant"), (80, "High"), (100, "Critical")]
SEVERITY_ORDER = [b for _, b in SEVERITY_BANDS]


def severity_label(score: float) -> str:
    for upper, name in SEVERITY_BANDS:
        if score <= upper:
            return name
    return "Critical"


def blind_spot_score(importance: float, gap: float, trend: float) -> float:
    """Core formula. Inputs are clipped to 0-100; output is 0-100."""
    i, g, t = (float(np.clip(v, 0, 100)) for v in (importance, gap, trend))
    return round(i * g * t / 10000.0, 2)


def customer_importance_components(stats: pd.DataFrame, cfg: ScoringConfig) -> pd.DataFrame:
    """stats needs per topic: topic_id, mentions, unique_customers, negative_pct, neg_intensity, explicit_share_pct.
    Returns the frame with the four component scores and the weighted 'importance' (all 0-100)."""
    s = stats.copy()
    if s.empty:
        return s.assign(frequency_score=[], customers_score=[], sentiment_score=[], explicit_score=[], importance=[])
    mx_m = max(float(s["mentions"].max()), 1.0)
    mx_c = max(float(s["unique_customers"].max()), 1.0)
    s["frequency_score"] = 100 * s["mentions"] / mx_m
    s["customers_score"] = 100 * s["unique_customers"] / mx_c
    s["sentiment_score"] = 100 * (0.7 * s["negative_pct"] / 100 + 0.3 * np.minimum(1, s["neg_intensity"] / 0.5))
    s["explicit_score"] = np.minimum(100, 100 * (s["explicit_share_pct"] / 100) / 0.30)
    w = cfg.normalised("w_frequency", "w_unique_customers", "w_sentiment", "w_explicit_requests")
    s["importance"] = (w["w_frequency"] * s["frequency_score"] + w["w_unique_customers"] * s["customers_score"]
                       + w["w_sentiment"] * s["sentiment_score"] + w["w_explicit_requests"] * s["explicit_score"]).clip(0, 100)
    return s


def combine_trend(growth_score: float, negative_trend_score: float, cfg: ScoringConfig) -> float:
    """Issue-trend score (0-100, 50 = unchanged) from the volume-growth and negative-sentiment components."""
    w = cfg.normalised("w_volume_trend", "w_negative_trend")
    return float(np.clip(w["w_volume_trend"] * growth_score + w["w_negative_trend"] * negative_trend_score, 0, 100))


def effective_trend(trend: float | None, cfg: ScoringConfig) -> tuple[float, bool]:
    """(value used in the formula, trend_available)."""
    if trend is None or (isinstance(trend, float) and np.isnan(trend)):
        return float(cfg.neutral_trend), False
    return float(max(cfg.trend_floor, min(100.0, trend))), True


def score_topics(components: pd.DataFrame, cfg: ScoringConfig) -> pd.DataFrame:
    """components: topic_id, importance, gap, trend (None allowed). Adds trend_used, trend_available, score, severity."""
    out = components.copy()
    used, avail, scores = [], [], []
    for _, r in out.iterrows():
        t, ok = effective_trend(r.get("trend"), cfg)
        used.append(t)
        avail.append(ok)
        scores.append(blind_spot_score(r["importance"], r["gap"], t))
    out["trend_used"], out["trend_available"], out["score"] = used, avail, scores
    out["severity"] = out["score"].map(severity_label)
    return out
