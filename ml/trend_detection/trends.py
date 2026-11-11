"""Module 9 - trend detection (time-series on customer statements).

Why share-based and significance-tested?  A topic can 'grow' in raw volume simply because more data arrived in
a period. So every volume trend is computed on the topic's SHARE of all statements in the period and checked with
a two-proportion z-test; weak evidence is shrunk toward neutral (confidence = min(1, |z|/1.96)).

Windows   : 'recent' = last third of the dated time span, 'history' = everything before it.
Buckets   : day (<=21 days of data), week (<=150 days), month (longer) - chosen automatically.
Moving avg: 3-bucket moving average of volume and of negative count.
Spikes    : robust (median/MAD) z-score on negative counts per bucket, flagged when z >= 2.5 and count >= 3.
Trend score (0-100, 50 = no change):
    growth  = 50 + 25 * clip(log2((recent_share+e)/(history_share+e)), -2, 2)        damped by confidence
    neg     = 50 + 100 * (recent_negative_rate - history_negative_rate)               damped by confidence
    trend   = w_volume * growth + w_negative * neg          (weights from ScoringConfig)
Insufficient history (too few dated records / topic mentions) => trend is None ('unavailable'), never faked."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from config.logging_config import get_logger
from config.settings import ScoringConfig
from ml.scoring.engine import combine_trend

log = get_logger(__name__)


@dataclass
class TrendResult:
    available: bool = False
    reason: str = ""
    freq: str = "W"
    recent_start: pd.Timestamp | None = None
    topic_series: pd.DataFrame = field(default_factory=pd.DataFrame)
    overall_series: pd.DataFrame = field(default_factory=pd.DataFrame)
    topic_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    spikes: pd.DataFrame = field(default_factory=pd.DataFrame)
    emerging: list[dict] = field(default_factory=list)


def two_prop_z(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float]:
    """z-statistic and two-sided p-value for H0: p1 == p2. Returns (0, 1) when undefined."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0
    p = (x1 + x2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (x1 / n1 - x2 / n2) / se
    return float(z), float(2 * stats.norm.sf(abs(z)))


def choose_freq(span_days: float) -> str:
    return "D" if span_days <= 21 else ("W" if span_days <= 150 else "M")


def _period_start(s: pd.Series, freq: str) -> pd.Series:
    return s.dt.to_period({"D": "D", "W": "W", "M": "M"}[freq]).dt.start_time


def robust_spikes(counts: pd.Series, min_count: int = 3, z_thr: float = 2.5) -> pd.DataFrame:
    """Flag buckets whose count is anomalously high versus the series' own median (modified z-score)."""
    if len(counts) < 4:
        return pd.DataFrame(columns=["period", "count", "z"])
    med = float(np.median(counts))
    mad = float(np.median(np.abs(counts - med)))
    if mad == 0:
        sd = float(np.std(counts))
        z = (counts - med) / sd if sd > 0 else counts * 0
    else:
        z = 0.6745 * (counts - med) / mad
    sel = (z >= z_thr) & (counts >= min_count)
    return pd.DataFrame({"period": counts.index[sel], "count": counts[sel].values, "z": z[sel].values})


def analyze_trends(records: pd.DataFrame, mentions: pd.DataFrame, topic_ids: list[int], cfg: ScoringConfig,
                   topic_labels: dict[int, str] | None = None, recent_fraction: float = 1 / 3) -> TrendResult:
    """records: record_id, date, compound, label.  mentions: record_id, topic_id, compound, label (+date merged here)."""
    res = TrendResult()
    topic_labels = topic_labels or {}
    dated = records.dropna(subset=["date"]) if "date" in records else records.iloc[0:0]
    if len(dated) < cfg.min_records_for_trend:
        res.reason = (f"Trend analysis unavailable: only {len(dated)} records have valid dates "
                      f"(minimum {cfg.min_records_for_trend}). A neutral trend value is used for scoring.")
        return res
    t0, t1 = dated["date"].min(), dated["date"].max()
    span = (t1 - t0).total_seconds() / 86400
    if span < 7:
        res.reason = f"Trend analysis unavailable: records cover only {span:.1f} days (need at least 7)."
        return res

    res.available, res.freq = True, choose_freq(span)
    res.recent_start = t1 - (t1 - t0) * recent_fraction
    m = mentions.merge(dated[["record_id", "date"]], on="record_id", how="inner")
    m["period"] = _period_start(m["date"], res.freq)
    d = dated.assign(period=_period_start(dated["date"], res.freq))
    all_periods = pd.date_range(d["period"].min(), d["period"].max(), freq={"D": "D", "W": "W-MON", "M": "MS"}[res.freq])
    if len(all_periods) < 3:
        res.available, res.reason = False, "Trend analysis unavailable: fewer than 3 time buckets."
        return res

    # overall series (document level)
    ov = d.groupby("period").agg(volume=("record_id", "count"), avg_sentiment=("compound", "mean"),
                                 negative=("label", lambda s: int((s == "negative").sum()))).reindex(all_periods)
    ov["volume"] = ov["volume"].fillna(0)
    ov["negative"] = ov["negative"].fillna(0)
    ov["negative_share"] = np.where(ov["volume"] > 0, ov["negative"] / ov["volume"].replace(0, np.nan) * 100, np.nan)
    ov["volume_ma"] = ov["volume"].rolling(3, min_periods=1).mean()
    ov["sentiment_ma"] = ov["avg_sentiment"].rolling(3, min_periods=1).mean()
    res.overall_series = ov.rename_axis("period").reset_index()

    tot_period = m.groupby("period").size().reindex(all_periods).fillna(0)
    is_recent = m["date"] >= res.recent_start
    tot_recent, tot_hist = int(is_recent.sum()), int((~is_recent).sum())

    series_rows, summ_rows, spike_rows = [], [], []
    for tid in topic_ids:
        g = m[m["topic_id"] == tid]
        ser = g.groupby("period").agg(volume=("record_id", "count"), avg_sentiment=("compound", "mean"),
                                      neg_count=("label", lambda s: int((s == "negative").sum()))).reindex(all_periods)
        ser["volume"] = ser["volume"].fillna(0)
        ser["neg_count"] = ser["neg_count"].fillna(0)
        ser["share"] = np.where(tot_period > 0, ser["volume"] / tot_period.replace(0, np.nan) * 100, np.nan)
        ser["neg_share"] = np.where(ser["volume"] > 0, ser["neg_count"] / ser["volume"].replace(0, np.nan) * 100, np.nan)
        ser["volume_ma"] = ser["volume"].rolling(3, min_periods=1).mean()
        ser["neg_ma"] = ser["neg_count"].rolling(3, min_periods=1).mean()
        ser.insert(0, "topic_id", tid)
        series_rows.append(ser.rename_axis("period").reset_index())

        gr, gh = g[g["date"] >= res.recent_start], g[g["date"] < res.recent_start]
        rn, hn = len(gr), len(gh)
        r_share = rn / tot_recent if tot_recent else 0.0
        h_share = hn / tot_hist if tot_hist else 0.0
        z, p = two_prop_z(rn, tot_recent, hn, tot_hist)
        conf = min(1.0, abs(z) / 1.96)
        eps = 0.5 / max(tot_hist, 1)
        g_log = float(np.clip(np.log2((r_share + eps) / (h_share + eps)), -2, 2))
        growth = 50 + 25 * g_log * conf
        r_neg = int((gr["label"] == "negative").sum()); h_neg = int((gh["label"] == "negative").sum())
        neg_ok = rn >= 3 and hn >= 3
        r_rate = r_neg / rn if rn else np.nan
        h_rate = h_neg / hn if hn else np.nan
        nz, npv = two_prop_z(r_neg, rn, h_neg, hn) if neg_ok else (0.0, 1.0)
        nconf = min(1.0, abs(nz) / 1.96)
        neg_delta = (r_rate - h_rate) if neg_ok else 0.0
        neg_score = float(np.clip(50 + 100 * neg_delta * nconf, 0, 100))
        enough = (rn + hn) >= 8
        trend = combine_trend(growth, neg_score, cfg) if enough else None
        change_pct = ((r_share - h_share) / h_share * 100) if h_share > 0 else None

        status = "insufficient data"
        if enough:
            if hn <= 1 and rn >= 3:
                status = "emerging"
            elif p < 0.10 and r_share > h_share:
                status = "increasing"
            elif p < 0.10 and r_share < h_share:
                status = "declining"
            else:
                status = "stable"
        slope = np.nan
        gd = g.dropna(subset=["date"])
        if len(gd) >= 8 and gd["date"].nunique() > 2:
            x = (gd["date"] - t0).dt.total_seconds() / 86400
            lr = stats.linregress(x, gd["compound"])
            slope = float(lr.slope * 7)  # change in compound per week
        summ_rows.append({
            "topic_id": tid, "topic_label": topic_labels.get(tid, str(tid)), "status": status, "trend_score": trend,
            "growth_score": growth, "negative_trend_score": neg_score, "trend_enough": bool(enough), "recent_n": rn, "history_n": hn,
            "recent_share_pct": r_share * 100, "history_share_pct": h_share * 100, "volume_change_pct": change_pct,
            "volume_p_value": p, "recent_negative_pct": None if np.isnan(r_rate) else r_rate * 100,
            "history_negative_pct": None if np.isnan(h_rate) else h_rate * 100, "negative_delta_pct": neg_delta * 100,
            "negative_p_value": npv, "confidence": conf, "sentiment_slope_per_week": slope,
        })
        sp = robust_spikes(ser["neg_count"])
        for _, r in sp.iterrows():
            spike_rows.append({"topic_id": tid, "topic_label": topic_labels.get(tid, str(tid)),
                               "period": r["period"], "negative_count": int(r["count"]), "z_score": float(r["z"])})

    res.topic_series = pd.concat(series_rows, ignore_index=True) if series_rows else pd.DataFrame()
    res.topic_summary = pd.DataFrame(summ_rows)
    res.spikes = pd.DataFrame(spike_rows, columns=["topic_id", "topic_label", "period", "negative_count", "z_score"])
    for _, r in res.topic_summary.iterrows():
        neg_now = r["recent_negative_pct"]
        if r["status"] in ("emerging", "increasing") and (neg_now or 0) >= 40:
            res.emerging.append({
                "topic_id": int(r["topic_id"]), "topic_label": r["topic_label"], "status": r["status"],
                "reason": (f"{r['recent_share_pct']:.0f}% of recent statements vs {r['history_share_pct']:.0f}% earlier "
                           f"(p={r['volume_p_value']:.3f}); {neg_now:.0f}% negative lately."),
                "recent_n": int(r["recent_n"]), "history_n": int(r["history_n"]),
                "volume_change_pct": None if pd.isna(r["volume_change_pct"]) else float(r["volume_change_pct"]),
            })
    log.info("Trends: freq=%s topics=%d emerging=%d spikes=%d", res.freq, len(topic_ids), len(res.emerging), len(res.spikes))
    return res
