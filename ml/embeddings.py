"""Embedding service shared by every semantic component.

Primary backend : SentenceTransformer (SBERT) - ``all-MiniLM-L6-v2`` by default.
Fallback backend: TF-IDF + truncated SVD (LSA). Fully offline and light, used automatically
                  when SBERT cannot be loaded (no internet for the first download, no torch ...)
                  or when ``EMBEDDING_BACKEND=tfidf``.

All vectors are L2-normalised, so cosine similarity == dot product.
The loaded model is cached at module level (``get_embedder``)."""
from __future__ import annotations

import threading
from typing import Sequence

import numpy as np

from config.logging_config import get_logger
from config.settings import settings

log = get_logger(__name__)
_LOCK = threading.Lock()
_CACHE: dict[str, "Embedder"] = {}


def l2_normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms


class Embedder:
    """Common interface. ``fit`` is a no-op for SBERT, learns the vocabulary for TF-IDF."""

    name = "base"
    is_semantic = True

    def fit(self, texts: Sequence[str]) -> "Embedder":
        return self

    def encode(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class SBertEmbedder(Embedder):
    is_semantic = True

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.name = f"sbert:{model_name}"
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if len(texts) == 0:
            return np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        emb = self.model.encode(list(texts), batch_size=64, show_progress_bar=False, convert_to_numpy=True)
        return l2_normalize(emb)


class TfidfLsaEmbedder(Embedder):
    """Lightweight lexical-semantic fallback. Captures co-occurrence (LSA) but NOT true
    paraphrase similarity - documented as a limitation. Must be fitted on the corpus
    (customer + company text together so both live in one space)."""

    is_semantic = False
    name = "tfidf-lsa"

    def __init__(self, n_components: int = 64):
        self.n_components = n_components
        self.vectorizer = None
        self.svd = None

    def fit(self, texts: Sequence[str]) -> "TfidfLsaEmbedder":
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=20000
        )
        mat = self.vectorizer.fit_transform(list(texts))
        k = max(2, min(self.n_components, mat.shape[0] - 1, mat.shape[1] - 1))
        self.svd = TruncatedSVD(n_components=k, random_state=settings.random_seed).fit(mat)
        return self

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self.vectorizer is None:
            self.fit(texts)
        mat = self.vectorizer.transform(list(texts))
        vecs = np.nan_to_num(self.svd.transform(mat)).astype(np.float32)
        # Text with no vocabulary overlap maps to the zero vector, which breaks cosine clustering. Give such rows a
        # neutral uniform direction (they are 'unknown', equally unrelated to every topic).
        zero = np.linalg.norm(vecs, axis=1) < 1e-9
        if zero.any():
            vecs[zero] = 1.0 / np.sqrt(vecs.shape[1])
        return l2_normalize(vecs)


def get_embedder(backend: str | None = None, fit_texts: Sequence[str] | None = None) -> Embedder:
    """Return a cached embedder. TF-IDF embedders are re-fitted on ``fit_texts`` each call
    (they are corpus specific); SBERT models are loaded once per process."""
    backend = (backend or settings.embedding_backend).lower()
    if backend == "sbert":
        key = f"sbert:{settings.embedding_model}"
        with _LOCK:
            if key in _CACHE:
                return _CACHE[key]
            try:
                emb = SBertEmbedder(settings.embedding_model)
                _CACHE[key] = emb
                log.info("Loaded SBERT embedder %s", settings.embedding_model)
                return emb
            except Exception as exc:  # noqa: BLE001 - any load failure triggers the fallback
                log.warning("SBERT unavailable (%s). Falling back to TF-IDF/LSA embeddings.", exc)
    emb = TfidfLsaEmbedder()
    if fit_texts is not None:
        emb.fit(fit_texts)
    return emb


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between rows of ``a`` and ``b`` (both assumed L2-normalised)."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    return np.asarray(a, dtype=np.float32) @ np.asarray(b, dtype=np.float32).T
