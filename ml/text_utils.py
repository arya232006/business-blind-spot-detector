"""Small text helpers shared across modules (stopwords, clause splitting, keyphrases)."""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Sequence

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Negations are NOT removed even when stopword removal is requested - they flip sentiment.
NEGATIONS = {"no", "not", "never", "nor", "none", "nobody", "nothing", "cannot", "cant", "can't", "won't", "don't",
             "didn't", "doesn't", "isn't", "wasn't", "aren't", "couldn't", "wouldn't", "shouldn't", "hardly", "without"}
STOPWORDS = frozenset(w for w in ENGLISH_STOP_WORDS if w not in NEGATIONS) | {
    "app", "get", "got", "just", "really", "ve", "ll", "im", "ive", "also", "would", "could", "like", "one",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\s*,?\s+(?:but|however|although|though|yet|while|whereas)\s+|\s+—\s+|\s+-\s+", re.I)


def remove_stopwords(text: str) -> str:
    return " ".join(w for w in text.split() if w.lower().strip(".,!?;:'\"") not in STOPWORDS)


def split_clauses(text: str, min_chars: int = 8) -> list[str]:
    """Split a review into clauses so different aspects can receive different sentiment.
    'The camera is amazing, but the battery is disappointing.' -> 2 clauses."""
    parts = [p.strip(" ,;") for p in _CLAUSE_SPLIT.split(text or "") if p and p.strip(" ,;")]
    parts = [p for p in parts if len(p) >= min_chars]
    return parts or ([text.strip()] if text and text.strip() else [])


def tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def content_words(text: str) -> list[str]:
    return [w for w in tokens(text) if w not in STOPWORDS and len(w) > 2]


def top_keywords(texts: Iterable[str], n: int = 8, ngram: bool = True) -> list[str]:
    """Frequency-based keyword/phrase extraction (unigrams + bigrams) used for labelling."""
    uni, bi = Counter(), Counter()
    for t in texts:
        cw = content_words(t)
        uni.update(set(cw))
        if ngram:
            toks = [w for w in tokens(t)]
            for a, b in zip(toks, toks[1:]):
                if a not in STOPWORDS and b not in STOPWORDS and len(a) > 2 and len(b) > 2:
                    bi[f"{a} {b}"] += 1
    ranked = [(k, v * 1.5) for k, v in bi.items() if v >= 2] + list(uni.items())
    ranked.sort(key=lambda kv: -kv[1])
    out: list[str] = []
    for k, _ in ranked:
        if any(k in o or o in k for o in out):
            continue
        out.append(k)
        if len(out) >= n:
            break
    return out


def truncate(text: str, n: int = 220) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def safe_pct(num: float, den: float) -> float:
    return float(num) / float(den) * 100.0 if den else 0.0


def first_non_null(values: Sequence, default=None):
    for v in values:
        if v is not None and v == v:
            return v
    return default
