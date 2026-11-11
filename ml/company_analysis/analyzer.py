"""Module 6 - company communication analysis (done SEPARATELY from customer data).

Methodology (documented, nothing fabricated):
* Every company message is embedded (SBERT / TF-IDF fallback) and clustered into *themes*
  (KMeans on a SBERT + TF-IDF hybrid vector, k chosen by silhouette; labels = c-TF-IDF keywords).
* Theme share % = messages in the theme / all messages x 100 - i.e. the share of the company's
  communication volume that carries that theme.
* Promises / benefits / features are detected with transparent cue patterns and listed with the source message.
Customer-vs-company comparison happens later in ml.gap_analysis."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from ml.embeddings import Embedder, TfidfLsaEmbedder, l2_normalize
from ml.text_utils import top_keywords, truncate
from ml.topic_modeling import discover_topics

log = get_logger(__name__)

PROMISE_CUES = {
    "speed": re.compile(r"\b(fast\w*|quick\w*|instant\w*|lightning\w*|in \d+ days?|same day|next day|twice as fast|blazing|speedy|rapid\w*)\b", re.I),
    "price/offers": re.compile(r"\b(\d+% off|flat \d+%|discount\w*|sale|deals?|save|savings|cashback|coupon\w*|lowest price|offers?|price drop|free (delivery|shipping))\b", re.I),
    "trust/service": re.compile(r"\b(hassle[- ]free|always here|trust|secure|guarantee\w*|confidence|happiness|support|returns?|refunds?)\b", re.I),
    "quality/range": re.compile(r"\b(premium|verified|million|categories|catalogue|curated|best|top brands|new in|introducing|discover)\b", re.I),
    "rewards": re.compile(r"\b(points|rewards?|members?|plus|perks|exclusive)\b", re.I),
}
BENEFIT_CUES = re.compile(r"\b(save|earn|get|enjoy|free|bonus|cashback|faster|easier|smarter|unlock|access|never)\b", re.I)


@dataclass
class CompanyProfile:
    themes: list[dict] = field(default_factory=list)
    assignments: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    embeddings: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    promises: pd.DataFrame = field(default_factory=pd.DataFrame)
    keywords: list[tuple[str, int]] = field(default_factory=list)
    channel_mix: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def detect_promises(texts: list[str]) -> pd.DataFrame:
    rows = []
    for t in texts:
        kinds = [k for k, pat in PROMISE_CUES.items() if pat.search(t)]
        benefit = bool(BENEFIT_CUES.search(t))
        if kinds or benefit:
            rows.append({"text": t, "promise_types": kinds or ["general benefit"], "is_benefit": benefit})
    return pd.DataFrame(rows, columns=["text", "promise_types", "is_benefit"])


def analyze_company(records: pd.DataFrame, embedder: Embedder, max_themes: int = 6) -> CompanyProfile:
    prof = CompanyProfile()
    if records is None or len(records) == 0:
        prof.notes.append("No company communication records.")
        return prof
    texts = records["text_clean"].tolist()
    emb = embedder.encode(texts)
    prof.embeddings = emb
    # Theme clustering uses a HYBRID vector (SBERT + 0.7 x TF-IDF/LSA): SBERT alone groups short marketing slogans
    # partly by tone ("hype") rather than subject, while marketing themes are strongly keyword-driven.
    cluster_emb = emb
    if embedder.is_semantic and len(texts) >= 8:
        lsa = TfidfLsaEmbedder(n_components=16).fit(texts).encode(texts)
        cluster_emb = l2_normalize(np.hstack([emb, 0.7 * lsa]))
    res = discover_topics(texts, cluster_emb, use_bertopic=False, max_topics=max_themes, drop_common_terms=0.25)
    prof.assignments = res.assignments
    n = len(texts)
    for t in res.topics:
        member = np.where(res.assignments == t["topic_id"])[0]
        prof.themes.append({
            "theme_id": t["topic_id"], "label": t["label"], "keywords": t["keywords"], "n_messages": int(len(member)),
            "share_pct": round(len(member) / n * 100, 1),
            "examples": [truncate(texts[i], 160) for i in member[:3]],
            "sources": records.iloc[member]["source"].value_counts().head(3).to_dict() if "source" in records else {},
        })
    prof.themes.sort(key=lambda x: -x["n_messages"])
    prof.promises = detect_promises(texts)
    prof.keywords = _keyword_counts(records["text_keywords"].tolist() if "text_keywords" in records else texts)
    if "source" in records:
        prof.channel_mix = records["source"].value_counts().to_dict()
    prof.notes.extend(res.notes)
    if n < 10:
        prof.notes.append("Fewer than 10 company messages - themes and coverage are low-confidence.")
    log.info("Company profile: %d messages, %d themes", n, len(prof.themes))
    return prof


def _keyword_counts(texts: list[str], n: int = 25) -> list[tuple[str, int]]:
    from collections import Counter
    from ml.text_utils import content_words

    c: Counter = Counter()
    for t in texts:
        c.update(set(content_words(t)))
    return [(w, k) for w, k in c.most_common(n)]
