"""Module 4 - topic discovery (nothing is hard-coded: topics come from the uploaded data).

Primary   : BERTopic = SBERT embeddings -> UMAP -> HDBSCAN -> c-TF-IDF keywords.
Fallback  : KMeans on the same embeddings (k picked by silhouette) + our own c-TF-IDF. Used when the dataset is
            too small/uniform for density clustering, when BERTopic fails, or when USE_BERTOPIC=false.
Outliers (HDBSCAN's topic -1) are re-assigned to the nearest topic by embedding similarity when they are close
enough; the rest stay as -1 ('uncategorised') and are reported honestly."""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from config.logging_config import get_logger
from config.settings import settings
from ml.embeddings import l2_normalize, cosine_matrix
from ml.text_utils import STOPWORDS, truncate

log = get_logger(__name__)


@dataclass
class TopicModelResult:
    assignments: np.ndarray                      # topic id per document (-1 = uncategorised)
    topics: list[dict] = field(default_factory=list)  # topic_id, label, keywords, size, representative_docs
    centroids: dict[int, np.ndarray] = field(default_factory=dict)
    backend: str = "kmeans"
    notes: list[str] = field(default_factory=list)


def ctfidf_keywords(texts: Sequence[str], labels: np.ndarray, top_n: int = 8, drop_common: float | None = None) -> dict[int, list[str]]:
    """Class-based TF-IDF: treat each topic as one document, weight terms by tf * log(1 + avg_words / term_freq).
    Terms must appear in at least 2 documents (or 8%) of the topic, so one-off words never become a label.
    ``drop_common``: discard terms present in more than this fraction of ALL documents (brand names etc.)."""
    from sklearn.feature_extraction.text import CountVectorizer

    ids = sorted(t for t in set(labels.tolist()) if t != -1)
    if not ids:
        return {}
    docs = [" ".join(t for t, l in zip(texts, labels) if l == i) for i in ids]
    try:
        cv = CountVectorizer(stop_words=sorted(STOPWORDS), ngram_range=(1, 2), min_df=1, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']+\b")
        X = cv.fit_transform(docs).toarray().astype(float)
        cv_vocab = np.array(cv.get_feature_names_out())
    except ValueError:
        return {i: [] for i in ids}
    vocab = cv_vocab
    # per-topic document frequency of each (kept) term
    binary = (cv.transform(list(texts)).toarray() > 0)
    allowed = np.isin(np.array(cv.get_feature_names_out()), vocab)
    binary = binary[:, allowed]
    if drop_common is not None:
        common = binary.mean(axis=0) > drop_common
    else:
        common = np.zeros(binary.shape[1], dtype=bool)
    tf = X / np.maximum(X.sum(axis=1, keepdims=True), 1)
    avg_words = X.sum() / len(ids)
    idf = np.log(1 + avg_words / np.maximum(X.sum(axis=0), 1))
    out = {}
    for row, tid in enumerate(ids):
        order = np.argsort(-(tf[row] * idf))
        members = labels == tid
        need_df = max(2, int(np.ceil(0.08 * members.sum())))
        dfs = binary[members].sum(axis=0)
        picked: list[str] = []
        for j in order:
            term = vocab[j]
            if X[row, j] < 1:
                break
            if dfs[j] < need_df or common[j]:
                continue
            if any(term in p or p in term for p in picked):  # skip 'refund' when 'refund money' already chosen
                continue
            picked.append(term)
            if len(picked) >= top_n:
                break
        out[tid] = picked
    return out


def _kmeans(emb: np.ndarray, seed: int, k_max: int) -> np.ndarray:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n = len(emb)
    best, best_s = None, -1.0
    for k in range(2, max(3, min(k_max, n // 4)) + 1):
        if k >= n:
            break
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(emb)
        if len(set(labels)) < 2:
            continue
        s = silhouette_score(emb, labels, metric="cosine")
        # mild preference for more granular topics so a 2-cluster split does not always win
        s_adj = s + 0.004 * min(k, 12)
        if s_adj > best_s:
            best, best_s = labels, s_adj
    return best if best is not None else np.zeros(n, dtype=int)


def _bertopic(texts: list[str], emb: np.ndarray, min_topic_size: int, seed: int, max_topics: int):
    from bertopic import BERTopic
    from bertopic.representation import KeyBERTInspired  # noqa: F401  (kept for optional use)
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    n = len(texts)
    umap_model = UMAP(n_neighbors=max(2, min(15, n // 4)), n_components=min(5, max(2, n // 10)), min_dist=0.0,
                      metric="cosine", random_state=seed)
    hdb = HDBSCAN(min_cluster_size=min_topic_size, min_samples=max(1, min_topic_size // 3), metric="euclidean",
                  cluster_selection_method="eom", prediction_data=True)
    vec = CountVectorizer(stop_words=sorted(STOPWORDS), ngram_range=(1, 2), min_df=1,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']+\b")
    model = BERTopic(umap_model=umap_model, hdbscan_model=hdb, vectorizer_model=vec, calculate_probabilities=False,
                     verbose=False, nr_topics=None, top_n_words=8)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        topics, _ = model.fit_transform(texts, embeddings=emb)
        topics = np.array(topics)
        if len(set(topics) - {-1}) > max_topics:
            model.reduce_topics(texts, nr_topics=max_topics)
            topics = np.array(model.topics_)
    return model, topics


def discover_topics(
    texts: Sequence[str],
    embeddings: np.ndarray,
    min_topic_size: int | None = None,
    max_topics: int = 12,
    use_bertopic: bool | None = None,
    seed: int | None = None,
    reassign_outliers_above: float | None = None,
    drop_common_terms: float | None = None,
) -> TopicModelResult:
    texts = list(texts)
    n = len(texts)
    seed = settings.random_seed if seed is None else seed
    use_bertopic = settings.use_bertopic if use_bertopic is None else use_bertopic
    emb = l2_normalize(embeddings)
    res = TopicModelResult(assignments=np.full(n, -1, dtype=int))
    if n < 6:
        res.assignments = np.zeros(n, dtype=int)
        res.backend = "single-topic"
        res.notes.append("Too few records for topic discovery; all grouped into one topic.")
        labels = res.assignments
    else:
        min_topic_size = min_topic_size or max(5, int(round(n * 0.06)))
        labels, bt_model = None, None
        if use_bertopic and n >= 30:
            try:
                bt_model, labels = _bertopic(texts, emb, min_topic_size, seed, max_topics)
                n_topics = len(set(labels.tolist()) - {-1})
                outlier_share = float((labels == -1).mean())
                if n_topics < 2 or outlier_share > 0.6:
                    res.notes.append(f"BERTopic found {n_topics} topics with {outlier_share:.0%} outliers - used KMeans instead.")
                    labels, bt_model = None, None
                else:
                    res.backend = "bertopic"
            except Exception as exc:  # noqa: BLE001
                log.warning("BERTopic failed (%s); falling back to KMeans.", exc)
                res.notes.append(f"BERTopic failed ({type(exc).__name__}); used KMeans.")
                labels, bt_model = None, None
        if labels is None:
            labels = _kmeans(emb, seed, max_topics)
            res.backend = "kmeans"
        labels = np.asarray(labels, dtype=int)

        # re-assign outliers that are semantically close to an existing topic
        if (labels == -1).any():
            ids = sorted(set(labels.tolist()) - {-1})
            cents = np.vstack([l2_normalize(emb[labels == i].mean(axis=0, keepdims=True)) for i in ids])
            thr = reassign_outliers_above if reassign_outliers_above is not None else (0.30 if _is_dense(emb) else 0.10)
            for idx in np.where(labels == -1)[0]:
                sims = cosine_matrix(emb[idx:idx + 1], cents)[0]
                if sims.max() >= thr:
                    labels[idx] = ids[int(np.argmax(sims))]
        res.assignments = labels

    # ---- topic descriptions -------------------------------------------------
    ids = sorted(set(labels.tolist()) - {-1})
    kw = ctfidf_keywords(texts, labels, top_n=8, drop_common=drop_common_terms)
    for tid in ids:
        mask = labels == tid
        cent = l2_normalize(emb[mask].mean(axis=0, keepdims=True))[0]
        res.centroids[tid] = cent
        sims = emb[mask] @ cent
        member_idx = np.where(mask)[0]
        rep = [truncate(texts[member_idx[j]], 200) for j in np.argsort(-sims)[:3]]
        words = kw.get(tid, [])
        res.topics.append({
            "topic_id": int(tid),
            "label": ", ".join(words[:3]) if words else f"Topic {tid}",
            "keywords": words,
            "size": int(mask.sum()),
            "representative_docs": rep,
        })
    n_out = int((labels == -1).sum())
    if n_out:
        res.notes.append(f"{n_out} records could not be assigned to any topic (uncategorised).")
    log.info("Topic discovery backend=%s topics=%d outliers=%d", res.backend, len(ids), n_out)
    return res


def _is_dense(emb: np.ndarray) -> bool:
    """SBERT vectors are dense (all dims informative); LSA vectors are also dense but have lower cosine floors.
    Heuristic: mean pairwise similarity of a sample - higher means the thresholds can be stricter."""
    s = emb[: min(len(emb), 60)]
    m = (s @ s.T)
    return float(m[np.triu_indices_from(m, 1)].mean()) > 0.05
