"""Module 7 - semantic gap analysis & blind-spot classification.

Customer topics and company messages live in the SAME embedding space, so 'seamless assistance' (company) and
'difficulty reaching support' (customers) are recognised as related without sharing keywords.

Company COVERAGE of a customer topic (documented method)
---------------------------------------------------------
For each company message m and customer topic t: sim(m,t) = cosine(embedding(m), centroid(t)).
* A message is *off-topic* for all customer topics if max_t sim(m,t) < ``off_topic_floor`` (e.g. 'Your trust matters').
* Otherwise its attention is split over topics with a softmax over similarities (temperature ``temperature``):
      p(t|m) = softmax_t( sim(m,t) / T )
* coverage_share(t) = mean over ALL messages of p(t|m) x [m is on-topic]   -> share of company communication
  that speaks to topic t.   coverage_norm(t) = 100 x coverage_share(t) / max_t coverage_share(t).
Semantic similarity(t) = mean of the 3 highest sim(m,t) over messages (is there ANY message about this topic?),
min-max normalised to 0-100 across topics.

Expectation gap = w_cov x (100 - coverage_norm) + w_sim x (100 - similarity_norm)      (weights configurable)

Classification (a lack of marketing coverage does NOT prove a missing operational capability, so we separate)
------------------------------------------------------------------------------------------------------------
genuine_blind_spot        high importance + clearly negative + low coverage + persistent/rising (or recurring)
unmet_operational_need    negative and dominated by explicit unmet-need / request / expectation statements
negative_experience       negative, but the company DOES communicate about it (promise vs reality mismatch)
communication_gap         customers discuss it (not mainly negatively) but the company hardly mentions it
misplaced_emphasis        company covers it heavily while customers rank it low
aligned                   none of the above"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import ScoringConfig
from ml.embeddings import cosine_matrix
from ml.semantic_search import SemanticIndex
from ml.text_utils import truncate

CLASS_LABELS = {
    "genuine_blind_spot": "Genuine blind spot",
    "unmet_operational_need": "Unmet operational need",
    "negative_experience": "Negative customer experience",
    "communication_gap": "Communication gap",
    "misplaced_emphasis": "Misplaced emphasis",
    "aligned": "Aligned / low priority",
}
CLASS_EXPLANATIONS = {
    "genuine_blind_spot": "Customers care a lot and are unhappy, but company communication barely touches the topic and the issue persists or is growing.",
    "unmet_operational_need": "Customers are explicitly asking for, or unable to do, something. This is an operational/product gap that messaging alone will not fix.",
    "negative_experience": "The company does talk about this topic, yet customers report bad experiences - a possible promise-versus-reality mismatch.",
    "communication_gap": "Customers discuss this topic mostly without hostility but the company says little about it - a messaging opportunity rather than a failure.",
    "misplaced_emphasis": "The company communicates heavily about this topic, but it ranks low in customer priorities.",
    "aligned": "Company attention and customer attention are in reasonable balance.",
}
CAVEAT = ("Low company coverage shows a communication gap; it does not by itself prove the company lacks the "
          "corresponding operational capability.")


def _softmax(x: np.ndarray, t: float) -> np.ndarray:
    z = x / t
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def compute_coverage(
    company_emb: np.ndarray,
    company_texts: list[str],
    topic_ids: list[int],
    centroids: np.ndarray,
    semantic: bool = True,
    off_topic_floor: float | None = None,
    temperature: float | None = None,
) -> tuple[pd.DataFrame, float]:
    """Return (per-topic coverage dataframe, share of company messages that are off-topic)."""
    off_topic_floor = off_topic_floor if off_topic_floor is not None else (0.22 if semantic else 0.10)
    temperature = temperature if temperature is not None else (0.05 if semantic else 0.08)
    k, n = len(topic_ids), len(company_texts)
    cols = ["topic_id", "coverage_share", "coverage_norm", "similarity", "similarity_norm", "top_messages"]
    if n == 0 or k == 0:
        return pd.DataFrame({"topic_id": topic_ids, "coverage_share": 0.0, "coverage_norm": 0.0, "similarity": 0.0,
                             "similarity_norm": 0.0, "top_messages": [[] for _ in topic_ids]}, columns=cols), 1.0
    sims = np.nan_to_num(cosine_matrix(company_emb, centroids))  # (n_msgs, k)
    on_topic = sims.max(axis=1) >= off_topic_floor
    p = _softmax(sims, temperature) * on_topic[:, None]
    share = p.sum(axis=0) / n
    # FAISS exact search: the 3 company messages closest to each customer-topic centroid
    top_sims, top_idx = SemanticIndex(company_emb).search(centroids, 3)
    top3 = top_sims.mean(axis=1)
    cov_norm = share / share.max() * 100 if share.max() > 0 else np.zeros(k)
    if k > 1 and np.ptp(top3) > 1e-9:
        sim_norm = (top3 - top3.min()) / np.ptp(top3) * 100
    else:
        sim_norm = np.full(k, 50.0)
    tops = [[{"text": truncate(company_texts[i], 160), "similarity": round(float(sv), 3)} for sv, i in zip(top_sims[j], top_idx[j])]
            for j in range(k)]
    df = pd.DataFrame({"topic_id": topic_ids, "coverage_share": share, "coverage_norm": cov_norm,
                       "similarity": top3, "similarity_norm": sim_norm, "top_messages": tops})
    return df, float(1 - on_topic.mean())


def expectation_gap(coverage_norm: float, similarity_norm: float, cfg: ScoringConfig) -> float:
    w = cfg.normalised("w_coverage", "w_similarity")
    return float(np.clip(w["w_coverage"] * (100 - coverage_norm) + w["w_similarity"] * (100 - similarity_norm), 0, 100))


def classify_topic(
    importance: float, gap: float, neg_pct: float, explicit_share: float, coverage_norm: float, cfg: ScoringConfig,
) -> str:
    """Rule-based classification (see module docstring); all inputs are on the 0-100 scale.

    1. negative + explicit unmet-need/request statements dominate      -> unmet_operational_need
    2. important + negative + large expectation gap
         company barely mentions it (coverage < cfg.low_coverage)     -> genuine_blind_spot
         company does talk about it                                    -> negative_experience
    3. important + negative, gap small (company covers it)             -> negative_experience
    4. not mainly negative + large gap + non-trivial importance        -> communication_gap
    5. company covers it heavily (coverage >= 50) and far beyond its customer
       importance (coverage - importance >= cfg.min_emphasis_gap)       -> misplaced_emphasis
    Persistence/growth of an issue affects the SCORE (trend component) and recommendation priority, not the class."""
    if neg_pct >= 30 and explicit_share >= 25 and importance >= cfg.min_importance:
        return "unmet_operational_need"
    if neg_pct >= 40 and importance >= cfg.min_importance:
        if gap >= cfg.min_gap and coverage_norm < cfg.low_coverage:
            return "genuine_blind_spot"
        return "negative_experience"
    if neg_pct < 40 and gap >= cfg.min_gap and importance >= 25:
        return "communication_gap"
    if coverage_norm >= 50 and coverage_norm - importance >= cfg.min_emphasis_gap:
        return "misplaced_emphasis"
    return "aligned"
