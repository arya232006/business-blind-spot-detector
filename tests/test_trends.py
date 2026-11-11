import numpy as np
import pandas as pd
import pytest

from config.settings import ScoringConfig
from ml.trend_detection import analyze_trends, choose_freq, robust_spikes, two_prop_z


def _data(n_days=84, seed=0, grow=True, volume_mult=1.0):
    rng = np.random.default_rng(seed)
    rows, rid = [], 0
    for d in range(n_days):
        date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=d)
        n_a = int(rng.poisson(1 + (4 * d / n_days if grow else 1)) * volume_mult)   # topic 0 growing (or flat)
        n_b = int(rng.poisson(2) * volume_mult)                                       # topic 1 flat
        for t, n in ((0, n_a), (1, n_b)):
            for _ in range(n):
                neg = rng.random() < (0.3 + 0.5 * d / n_days if (t == 0 and grow) else 0.4)
                rows.append((rid, date, t, -0.5 if neg else 0.5, "negative" if neg else "positive"))
                rid += 1
    df = pd.DataFrame(rows, columns=["record_id", "date", "topic_id", "compound", "label"])
    return df[["record_id", "date", "compound", "label"]], df[["record_id", "topic_id", "compound", "label"]]


def test_two_proportion_z():
    z, p = two_prop_z(40, 100, 20, 100)
    assert z > 2.5 and p < 0.01
    assert two_prop_z(10, 100, 10, 100) == (0.0, 1.0)
    assert two_prop_z(0, 0, 5, 10) == (0.0, 1.0)


def test_frequency_choice():
    assert choose_freq(10) == "D" and choose_freq(60) == "W" and choose_freq(400) == "M"


def test_growing_topic_detected_flat_topic_stable():
    cfg = ScoringConfig()
    rec, men = _data()
    res = analyze_trends(rec, men, [0, 1], cfg, {0: "growing", 1: "flat"})
    assert res.available
    s = res.topic_summary.set_index("topic_id")
    assert s.loc[0, "status"] in ("increasing", "emerging") and s.loc[0, "trend_score"] > 55
    # status is about SHARE of conversation: the flat topic loses share while topic 0 grows, so it must never look "increasing"
    assert s.loc[1, "status"] in ("stable", "declining") and s.loc[1, "trend_score"] <= 55
    assert any(e["topic_id"] == 0 for e in res.emerging)
    assert {"volume", "share", "neg_count", "volume_ma"} <= set(res.topic_series.columns)


def test_sample_volume_change_alone_is_not_a_trend():
    """Doubling the number of statements for EVERYTHING must not make a flat topic look like it is growing."""
    cfg = ScoringConfig()
    rec, men = _data(grow=False, volume_mult=1.0)
    rec2, men2 = _data(grow=False, volume_mult=1.0)
    men2 = pd.concat([men2, men2.assign(record_id=men2["record_id"] + 100000)])        # doubled volume in the whole period
    rec2 = pd.concat([rec2, rec2.assign(record_id=rec2["record_id"] + 100000)])
    res = analyze_trends(rec2, men2, [0, 1], cfg)
    assert (res.topic_summary["status"].isin(["stable", "declining", "increasing"])).all()
    assert abs(res.topic_summary.set_index("topic_id").loc[0, "trend_score"] - 50) < 15


def test_insufficient_history_is_unavailable_not_faked():
    cfg = ScoringConfig()
    rec, men = _data(n_days=5)
    res = analyze_trends(rec, men, [0, 1], cfg)
    assert not res.available and "unavailable" in res.reason.lower() and res.topic_summary.empty
    res2 = analyze_trends(rec.assign(date=pd.NaT), men, [0, 1], cfg)
    assert not res2.available


def test_robust_spike_detection():
    counts = pd.Series([1, 2, 1, 2, 1, 2, 12, 1, 2], index=pd.date_range("2026-01-05", periods=9, freq="W"))
    sp = robust_spikes(counts)
    assert len(sp) == 1 and sp.iloc[0]["count"] == 12
    assert robust_spikes(pd.Series([2, 2, 2, 2, 2, 2])).empty
    assert robust_spikes(pd.Series([1, 5])).empty
