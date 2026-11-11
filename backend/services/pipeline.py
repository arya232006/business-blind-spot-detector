"""Analysis pipeline orchestrator: two datasets in -> complete analysis out, in one call.

Pure computation (no database): returns an ``AnalysisResult``; persistence lives in backend.services.persistence.
Steps (each reported through ``progress(step, total, message)``):
 1 validate  2 preprocess  3 embeddings  4 sentiment  5 topics  6 aspect sentiment  7 expectations
 8 company analysis  9 semantic comparison  10 trends  11 scoring  12 recommendations"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from config.settings import ScoringConfig, load_scoring_config, settings
from ml.company_analysis import analyze_company, CompanyProfile
from ml.embeddings import get_embedder
from ml.expectation_detection import detect_expectations
from ml.expectation_detection.detector import classify_statement
from ml.gap_analysis import compute_coverage
from ml.preprocessing import preprocess
from ml.recommendations import categorize_topics, enhance_recommendations, generate_recommendations
from ml.scoring.engine import customer_importance_components
from ml.scoring.rescore import rescore_blind_spots
from ml.sentiment import analyze_documents, extract_aspect_mentions, overall_sentiment
from ml.topic_modeling import discover_topics
from ml.text_utils import truncate
from ml.trend_detection import analyze_trends, TrendResult

log = get_logger(__name__)
TOTAL_STEPS = 12
ProgressFn = Callable[[int, int, str], None]
FLAGGED = {"genuine_blind_spot", "unmet_operational_need", "negative_experience", "communication_gap"}
EXPLICIT_SIGNALS = {"explicit_expectation", "feature_request", "unmet_need"}


class PipelineError(ValueError):
    """User-facing pipeline failure (bad/insufficient data)."""


@dataclass
class AnalysisResult:
    customer: pd.DataFrame = field(default_factory=pd.DataFrame)
    company: pd.DataFrame = field(default_factory=pd.DataFrame)
    topics: pd.DataFrame = field(default_factory=pd.DataFrame)
    mentions: pd.DataFrame = field(default_factory=pd.DataFrame)
    expectations: pd.DataFrame = field(default_factory=pd.DataFrame)
    company_themes: pd.DataFrame = field(default_factory=pd.DataFrame)
    promises: pd.DataFrame = field(default_factory=pd.DataFrame)
    blind_spots: pd.DataFrame = field(default_factory=pd.DataFrame)
    trends: TrendResult = field(default_factory=TrendResult)
    recommendations: pd.DataFrame = field(default_factory=pd.DataFrame)
    overview: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


def _noop(*_a, **_k) -> None:
    return None


def run_pipeline(customer_df: pd.DataFrame, company_df: pd.DataFrame, cfg: ScoringConfig | None = None,
                 progress: ProgressFn | None = None, use_llm: bool = True) -> AnalysisResult:
    cfg = cfg or load_scoring_config()
    progress = progress or _noop
    t_start = time.time()
    res = AnalysisResult()
    notes: list[str] = []

    # 1 ---- validate ---------------------------------------------------------------------------------
    progress(1, TOTAL_STEPS, "Validating datasets")
    if customer_df is None or len(customer_df) == 0:
        raise PipelineError("No customer data. Upload or enter customer conversations first.")
    if company_df is None or len(company_df) == 0:
        raise PipelineError("No company communication data. Upload or enter company messages first.")

    # 2 ---- preprocess ---------------------------------------------------------------------------------
    progress(2, TOTAL_STEPS, "Cleaning and preprocessing text")
    cust, cust_rep = preprocess(customer_df)
    comp, comp_rep = preprocess(company_df, min_words=3, english_only=True)
    if len(cust) < 5:
        raise PipelineError(f"Only {len(cust)} usable customer records after cleaning (need at least 5). "
                            f"Removed: {cust_rep.to_dict()}")
    if len(comp) < 1:
        raise PipelineError("No usable company messages after cleaning.")
    if len(cust) < 30:
        notes.append(f"Only {len(cust)} customer records: topic detection falls back to KMeans and results are low-confidence.")
    if len(comp) < 10:
        notes.append(f"Only {len(comp)} company messages: coverage estimates are low-confidence.")
    if "customer_id" not in cust or cust["customer_id"].isna().all():
        notes.append("No customer IDs provided - every record is counted as a distinct customer.")

    # 3 ---- embeddings -------------------------------------------------------------------------------
    progress(3, TOTAL_STEPS, "Loading embedding model and encoding text")
    embedder = get_embedder(fit_texts=cust["text_clean"].tolist() + comp["text_clean"].tolist())
    cust_emb = embedder.encode(cust["text_clean"].tolist())
    if not embedder.is_semantic:
        notes.append("Offline TF-IDF/LSA embeddings were used (SBERT unavailable): semantic matching is weaker than SBERT.")

    # 4 ---- sentiment -----------------------------------------------------------------------------------
    progress(4, TOTAL_STEPS, "Analysing sentiment (VADER" + (" + transformer)" if settings.use_transformer_sentiment else ")"))
    sent = analyze_documents(cust["text_clean"].tolist())
    cust = pd.concat([cust.reset_index(drop=True), sent], axis=1)

    # 5 ---- topics ---------------------------------------------------------------------------------------
    progress(5, TOTAL_STEPS, "Discovering topics")
    tm = discover_topics(cust["text_clean"].tolist(), cust_emb)
    notes.extend(tm.notes)
    cust["topic_id"] = tm.assignments
    if not tm.topics:
        raise PipelineError("No topics could be discovered from the customer data.")
    topic_ids = [t["topic_id"] for t in tm.topics]
    centroids = np.vstack([tm.centroids[i] for i in topic_ids])
    kw = {t["topic_id"]: t["keywords"] for t in tm.topics}
    label_of = {t["topic_id"]: t["label"] for t in tm.topics}

    # 6 ---- aspect-level sentiment -------------------------------------------------------------------
    progress(6, TOTAL_STEPS, "Aspect-based sentiment per topic")
    mentions = extract_aspect_mentions(cust["text_clean"].tolist(), cust["record_id"].tolist(), cust["topic_id"].tolist(),
                                       embedder, topic_ids, centroids, kw)
    if mentions.empty:
        raise PipelineError("No topic mentions could be extracted from the customer data.")
    mentions = mentions.merge(cust[["record_id", "date", "customer_id", "source"]], on="record_id", how="left")
    mentions["signals"] = [classify_statement(c, s) for c, s in zip(mentions["clause"], mentions["compound"])]
    mentions["explicit"] = mentions["signals"].map(lambda s: bool(EXPLICIT_SIGNALS & set(s)))

    # 7 ---- expectations -------------------------------------------------------------------------------
    progress(7, TOTAL_STEPS, "Detecting customer needs and expectations")
    expectations = detect_expectations(mentions, cust, tm.topics, embedder)

    # 8 ---- company communication ------------------------------------------------------------------
    progress(8, TOTAL_STEPS, "Analysing company communication")
    profile: CompanyProfile = analyze_company(comp, embedder)
    notes.extend(profile.notes)

    # 9 ---- semantic comparison --------------------------------------------------------------------
    progress(9, TOTAL_STEPS, "Comparing customer expectations with company messaging (semantic gap)")
    coverage, offtopic_share = compute_coverage(profile.embeddings, comp["text_clean"].tolist(), topic_ids, centroids,
                                                semantic=embedder.is_semantic)

    # 10 ---- trends --------------------------------------------------------------------------------------
    progress(10, TOTAL_STEPS, "Detecting trends and emerging issues")
    trends = analyze_trends(cust[["record_id", "date", "compound", "label"]], mentions[["record_id", "topic_id", "compound", "label"]],
                            topic_ids, cfg, label_of)
    if not trends.available:
        notes.append(trends.reason)

    # 11 ---- scoring ---------------------------------------------------------------------------------------
    progress(11, TOTAL_STEPS, "Scoring blind spots")
    topic_stats = _topic_stats(mentions, tm.topics, trends, cust)
    comps = customer_importance_components(topic_stats, cfg)
    bs = _assemble_blind_spots(comps, coverage, trends, expectations, mentions, label_of, kw)
    bs = rescore_blind_spots(bs, cfg)
    topics_df = comps.merge(bs[["topic_id", "importance", "score", "severity", "classification"]].rename(
        columns={"importance": "importance_rescored"}), on="topic_id", how="left")
    topics_df["importance"] = topics_df["importance_rescored"]
    topics_df = topics_df.drop(columns=["importance_rescored"])

    # 12 ---- recommendations -------------------------------------------------------------------------
    progress(12, TOTAL_STEPS, "Generating recommendations")
    cat_map = categorize_topics(tm.topics, embedder)
    recs = generate_recommendations(bs, expectations, cat_map)
    if use_llm:
        recs = enhance_recommendations(recs)

    # ---- assemble result ----------------------------------------------------------------------------
    res.customer = cust
    res.company = comp
    res.topics = topics_df.merge(pd.DataFrame(tm.topics)[["topic_id", "label", "keywords", "representative_docs"]], on="topic_id")
    res.topics["category"] = res.topics["topic_id"].map(cat_map)
    res.mentions, res.expectations, res.blind_spots, res.trends, res.recommendations = mentions, expectations, bs, trends, recs
    res.company_themes = pd.DataFrame(profile.themes)
    res.promises = profile.promises
    flagged = bs[bs["classification"].isin(FLAGGED) & (bs["score"] >= cfg.min_score)]
    sent_sum = overall_sentiment(cust)
    res.overview = {
        "total_conversations": int(len(cust)), "total_company_messages": int(len(comp)), "total_topics": int(len(tm.topics)),
        "total_blind_spots": int(len(flagged)),
        "genuine_blind_spots": int((bs["classification"] == "genuine_blind_spot").sum()),
        "total_emerging_issues": int(len(trends.emerging)),
        "overall_sentiment": sent_sum["mean_compound"], "positive_pct": sent_sum["positive_pct"],
        "negative_pct": sent_sum["negative_pct"], "neutral_pct": sent_sum["neutral_pct"],
        "avg_blind_spot_score": float(flagged["score"].mean()) if len(flagged) else 0.0,
        "uncategorised_conversations": int((cust["topic_id"] == -1).sum()),
        "offtopic_company_share_pct": round(offtopic_share * 100, 1),
    }
    res.meta = {
        "embedding_backend": embedder.name, "semantic_embeddings": embedder.is_semantic, "topic_backend": tm.backend,
        "sentiment_model": str(sent["model"].iloc[0]), "scoring_config": cfg.to_dict(), "notes": notes,
        "preprocess_customer": cust_rep.to_dict(), "preprocess_company": comp_rep.to_dict(),
        "trend_available": bool(trends.available), "trend_freq": trends.freq, "trend_reason": trends.reason,
        "recent_start": None if trends.recent_start is None else str(trends.recent_start),
        "runtime_seconds": round(time.time() - t_start, 1), "llm_used": bool(len(recs) and recs["llm_enhanced"].any()),
        "company_channel_mix": profile.channel_mix, "company_keywords": profile.keywords,
        "topic_notes": tm.notes,
    }
    log.info("Pipeline finished in %.1fs: %s", time.time() - t_start, res.overview)
    return res


# --------------------------------------------------------------------------------------------------------
def _topic_stats(mentions: pd.DataFrame, topics: list[dict], trends: TrendResult, cust: pd.DataFrame) -> pd.DataFrame:
    total_mentions = max(len(mentions), 1)
    rows = []
    summ = trends.topic_summary.set_index("topic_id") if len(trends.topic_summary) else pd.DataFrame()
    for t in topics:
        g = mentions[mentions["topic_id"] == t["topic_id"]]
        n = len(g)
        if n == 0:
            continue
        cust_ids = g["customer_id"].dropna().astype(str).unique()
        # records without a customer id count as individual customers
        n_anon = int(g["customer_id"].isna().sum())
        vc = g["label"].value_counts()
        rows.append({
            "topic_id": t["topic_id"], "mentions": n, "conversations": int(g["record_id"].nunique()),
            "unique_customers": int(len(cust_ids) + n_anon),
            "share_pct": n / total_mentions * 100,
            "avg_sentiment": float(g["compound"].mean()),
            "positive_pct": float(vc.get("positive", 0) / n * 100), "negative_pct": float(vc.get("negative", 0) / n * 100),
            "neutral_pct": float(vc.get("neutral", 0) / n * 100),
            "neg_intensity": float(np.clip(-g["compound"], 0, 1).mean()),
            "explicit_share_pct": float(g["explicit"].mean() * 100),
            "volume_change_pct": (None if (len(summ) == 0 or t["topic_id"] not in summ.index or pd.isna(summ.loc[t["topic_id"], "volume_change_pct"]))
                                  else float(summ.loc[t["topic_id"], "volume_change_pct"])),
            "trend_status": (summ.loc[t["topic_id"], "status"] if len(summ) and t["topic_id"] in summ.index else "unavailable"),
        })
    return pd.DataFrame(rows)


def _assemble_blind_spots(comps, coverage, trends, expectations, mentions, label_of, kw) -> pd.DataFrame:
    df = comps.merge(coverage, on="topic_id", how="left")
    if len(trends.topic_summary):
        df = df.merge(trends.topic_summary[["topic_id", "growth_score", "negative_trend_score", "trend_enough"]], on="topic_id", how="left")
    else:
        df["growth_score"], df["negative_trend_score"], df["trend_enough"] = np.nan, np.nan, False
    df["trend_enough"] = df["trend_enough"].fillna(False).astype(bool)
    df["topic_label"] = df["topic_id"].map(label_of)
    df["keywords"] = df["topic_id"].map(kw)
    recurring = set(expectations.loc[expectations["kind"] == "recurring_frustration", "topic_id"]) if len(expectations) else set()
    df["recurring"] = df["topic_id"].isin(recurring)
    neg = df.set_index("topic_id")["negative_pct"]
    df["neg_pct"] = df["topic_id"].map(neg)
    ev = {}
    for tid, g in mentions.groupby("topic_id"):
        pick = g.sort_values("compound").head(5)
        ev[tid] = [{"record_id": int(r.record_id), "text": truncate(r.clause, 240), "compound": round(float(r.compound), 3),
                    "date": None if pd.isna(r.date) else pd.Timestamp(r.date).strftime("%Y-%m-%d")} for r in pick.itertuples()]
    df["evidence_quotes"] = df["topic_id"].map(ev)
    df["closest_company_messages"] = df["top_messages"]
    return df.drop(columns=["top_messages"])
