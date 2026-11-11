"""Module 3 - sentiment analysis.

1. VADER (baseline, always available): compound score in [-1, 1].
   label: positive >= 0.05, negative <= -0.05, otherwise neutral (standard VADER thresholds).
2. Optional Hugging Face transformer (USE_TRANSFORMER_SENTIMENT=true): contextual sentiment.
   Final score = mean(VADER compound, transformer signed score) so the lexicon baseline stays in the loop.
3. Aspect-based sentiment (see ``extract_aspect_mentions``): a review is split into clauses, every clause is
   scored separately and linked to a discovered topic, so 'camera amazing, but battery disappointing'
   yields camera=positive and battery=negative instead of one blended number."""
from __future__ import annotations

import re
import threading
from typing import Sequence

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config.logging_config import get_logger
from config.settings import settings
from ml.embeddings import Embedder, cosine_matrix
from ml.text_utils import STOPWORDS, split_clauses, tokens

log = get_logger(__name__)
POS_T, NEG_T = 0.05, -0.05
# Domain lexicon: VADER was built for general social text and scores customer-service complaints such as
# "waiting three days for a refund" as neutral. These valences (VADER scale -4..4) are added ONLY for words
# VADER does not already know, so its original behaviour is untouched. Documented in README.
DOMAIN_LEXICON = {
    "waiting": -1.0, "waited": -1.2, "delayed": -1.8, "delay": -1.3, "delays": -1.3, "late": -1.1, "forever": -1.4,
    "unresponsive": -2.2, "nobody": -0.9, "ignored": -1.8, "ignoring": -1.8, "stuck": -1.3, "pending": -0.7,
    "overcharged": -2.3, "charged": -0.4, "missing": -1.2, "lost": -1.4, "damaged": -2.0, "crashes": -1.8,
    "crashing": -1.8, "crashed": -1.8, "laggy": -1.6, "lag": -1.2, "slow": -1.3, "unhelpful": -2.0,
    "useless": -2.3, "chatbot": -0.3, "rude": -2.0, "scam": -2.8, "cancelled": -1.0, "canceled": -1.0,
    "rejected": -1.4, "wrong": -1.4, "broken": -1.9, "faulty": -1.9, "refund": -0.2, "disappointing": -2.0,
    "frustrating": -2.2, "mess": -1.6, "unacceptable": -2.4, "worse": -1.8, "terrible": -2.5, "awful": -2.5,
    "fast": 1.1, "quick": 1.2, "quickly": 1.2, "smooth": 1.5, "helpful": 1.9, "reliable": 1.7, "seamless": 1.7,
    "arrived": 0.3, "resolved": 1.6, "intuitive": 1.5, "fixed": 1.4,
}
_VADER = SentimentIntensityAnalyzer()
# In a customer-service setting "support"/"service" are neutral topic nouns, not praise
# (VADER scores "support" as +1.7, which flips "nobody responds to my support ticket" to positive).
DOMAIN_NEUTRAL_NOUNS = ("support", "service", "care")
for _w, _v in DOMAIN_LEXICON.items():
    _VADER.lexicon.setdefault(_w, _v)
for _w in DOMAIN_NEUTRAL_NOUNS:
    _VADER.lexicon[_w] = 0.0
_VADER_WORDS = set(_VADER.lexicon)
_PIPE = None
_PIPE_LOCK = threading.Lock()
_ASPECT_RE = re.compile(r"\b(?:the|my|their|its|your|our|this|that)\s+([a-z][a-z\-]+(?:\s+[a-z][a-z\-]+)?)", re.I)


def label_from_score(score: float, pos: float = POS_T, neg: float = NEG_T) -> str:
    if score >= pos:
        return "positive"
    if score <= neg:
        return "negative"
    return "neutral"


# Service-failure phrasing that carries negative meaning without any negative WORD ("never called", "no update",
# "took 11 days"). Plain VADER scores such statements neutral/positive ("promised a callback and never called" = +0.36).
# If one of these cues is present and the lexicon score is not clearly negative, the score is capped at IMPLICIT_NEG_SCORE.
# Strongly positive statements (>= 0.75) are left alone. Documented as a domain correction in the README.
_FAIL_VERBS = (r"received|called|replied|responded|answered|showed|came|solved|arrived|reached|credited|helped|got|fixed|resolved|"
               r"appeared|picked|responds|replies|answers|calls|refunded|processed|delivered|understand|works?|worked")
IMPLICIT_NEG = re.compile(
    rf"\b(never|nobody|no one|nothing)\b(?:\s+\w+){{0,3}}?\s+({_FAIL_VERBS})\b"
    r"|\b(not|n't|hasn't|haven't|didn't|did not|has not|have not|doesn't|does not|won't|could not|couldn't|cannot|can't)\s+(?:\w+\s+){0,2}?(resolved|received|credited|delivered|solved|fixed|reached|arrived|helped|working|refunded|responded|replied|answered|processed|understand|connect|show|apply|track|contact|find|reach)\b"
    r"|\bno (update|updates|response|reply|replies|explanation|timeline|refund|tracking|phone|number|way to|option|movement|help)\b"
    r"|\b(took|takes|taking)\s+(?:so |too |way too |forever |over |nearly |almost )?(long|ages|forever|\d+\s*(?:days?|weeks?|hours?))\b"
    r"|\bstill\s+(no|not|waiting|pending|nothing)\b|\b\d+\s*(?:days?|weeks?)\s+(?:late|and (?:counting|still))\b"
    r"|\bzero (repl\w+|respon\w+)|\b(closed|marked)\b[^.]{0,40}\b(without|automatically)\b", re.I)
IMPLICIT_NEG_SCORE = -0.35


def vader_score(text: str) -> float:
    text = text or ""
    score = float(_VADER.polarity_scores(text)["compound"])
    if score < 0.75 and score > IMPLICIT_NEG_SCORE and IMPLICIT_NEG.search(text):
        score = IMPLICIT_NEG_SCORE
    return score


def _get_transformer():
    global _PIPE
    with _PIPE_LOCK:
        if _PIPE is None:
            from transformers import pipeline

            log.info("Loading transformer sentiment model %s", settings.transformer_sentiment_model)
            _PIPE = pipeline("sentiment-analysis", model=settings.transformer_sentiment_model, truncation=True,
                             max_length=256)
    return _PIPE


def transformer_scores(texts: Sequence[str]) -> np.ndarray | None:
    """Signed scores in [-1, 1] from a HF model. Returns None if the model cannot be loaded."""
    try:
        pipe = _get_transformer()
        out = pipe(list(texts), batch_size=16)
    except Exception as exc:  # noqa: BLE001
        log.warning("Transformer sentiment unavailable (%s); using VADER only.", exc)
        return None
    scores = []
    for o in out:
        lab, p = str(o["label"]).lower(), float(o["score"])
        if "neu" in lab:
            scores.append(0.0)
        elif "pos" in lab or lab in {"label_2", "5 stars", "4 stars"}:
            scores.append(p if p >= 0.6 else 0.0)  # binary models have no neutral class: low confidence -> neutral
        else:
            scores.append(-p if p >= 0.6 else 0.0)
    return np.array(scores)


def analyze_documents(texts: Sequence[str], use_transformer: bool | None = None) -> pd.DataFrame:
    """Document-level sentiment. Columns: vader_compound, transformer_score, compound, label, model."""
    use_transformer = settings.use_transformer_sentiment if use_transformer is None else use_transformer
    vader = np.array([vader_score(t) for t in texts], dtype=float)
    tf = transformer_scores(texts) if (use_transformer and len(texts)) else None
    if tf is not None:
        compound, model = (vader + tf) / 2.0, f"vader+{settings.transformer_sentiment_model}"
    else:
        compound, model = vader, "vader"
    return pd.DataFrame({
        "vader_compound": vader,
        "transformer_score": tf if tf is not None else np.nan,
        "compound": compound,
        "label": [label_from_score(c) for c in compound],
        "model": model,
    })


def overall_sentiment(df: pd.DataFrame) -> dict:
    """Overall sentiment summary from a dataframe with 'compound' and 'label' columns."""
    n = len(df)
    if n == 0:
        return {"n": 0, "mean_compound": 0.0, "positive_pct": 0.0, "negative_pct": 0.0, "neutral_pct": 0.0}
    vc = df["label"].value_counts()
    return {
        "n": n,
        "mean_compound": float(df["compound"].mean()),
        "positive_pct": float(vc.get("positive", 0) / n * 100),
        "negative_pct": float(vc.get("negative", 0) / n * 100),
        "neutral_pct": float(vc.get("neutral", 0) / n * 100),
    }


def aspect_term(clause: str, topic_keywords: Sequence[str] = ()) -> str:
    """Pick a human-readable aspect for a clause: a topic keyword present in it, else the noun-ish phrase
    after a determiner ('the battery backup'), else the first non-sentiment content word."""
    low = clause.lower()
    for kw in topic_keywords:
        if kw and re.search(rf"\b{re.escape(kw.lower())}", low):
            return kw
    for m in _ASPECT_RE.finditer(clause):
        words = [w for w in m.group(1).lower().split() if w not in STOPWORDS and w not in _VADER_WORDS]
        if words:
            return " ".join(words[:2])
    for w in tokens(clause):
        if w not in STOPWORDS and w not in _VADER_WORDS and len(w) > 3:
            return w
    return "general"


def extract_aspect_mentions(
    texts: Sequence[str],
    record_ids: Sequence[int],
    doc_topics: Sequence[int],
    embedder: Embedder,
    topic_ids: Sequence[int],
    topic_centroids: np.ndarray,
    topic_keywords: dict[int, list[str]],
    min_sim: float | None = None,
) -> pd.DataFrame:
    """Aspect-level sentiment 'mentions': one row per (review clause, topic).

    * Single-clause reviews inherit the review's discovered topic.
    * Multi-clause reviews: each clause goes to the nearest topic centroid (cosine) when the similarity
      clears ``min_sim``; otherwise the clause falls back to the review's own topic.
    Columns: record_id, clause, aspect, topic_id, compound, label, similarity."""
    min_sim = min_sim if min_sim is not None else (0.25 if embedder.is_semantic else 0.15)
    rows, clause_texts, owners = [], [], []
    for rid, text, dtopic in zip(record_ids, texts, doc_topics):
        clauses = split_clauses(text)
        for c in clauses:
            owners.append((rid, dtopic, len(clauses)))
            clause_texts.append(c)
    if not clause_texts:
        return pd.DataFrame(columns=["record_id", "clause", "aspect", "topic_id", "compound", "label", "similarity"])
    emb = embedder.encode(clause_texts)
    sims = cosine_matrix(emb, topic_centroids) if len(topic_centroids) else np.zeros((len(clause_texts), 0))
    tid = list(topic_ids)
    for i, (clause, (rid, dtopic, nclauses)) in enumerate(zip(clause_texts, owners)):
        topic, sim = dtopic, float("nan")
        if nclauses > 1 and sims.shape[1]:
            j = int(np.argmax(sims[i]))
            if sims[i, j] >= min_sim:
                topic, sim = tid[j], float(sims[i, j])
        if topic is None or topic == -1:
            continue
        score = vader_score(clause)
        rows.append({
            "record_id": rid, "clause": clause, "aspect": aspect_term(clause, topic_keywords.get(topic, [])),
            "topic_id": int(topic), "compound": score, "label": label_from_score(score), "similarity": sim,
        })
    return pd.DataFrame(rows)
