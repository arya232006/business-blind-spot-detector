"""Nearest-neighbour search over L2-normalised embeddings (inner product == cosine similarity).

Uses FAISS (``IndexFlatIP``, exact search) when available and transparently falls back to NumPy, so results are
identical either way. Used to find the company messages closest to each customer topic."""
from __future__ import annotations

import numpy as np

try:  # FAISS is an optional accelerator
    import faiss  # type: ignore

    _HAS_FAISS = True
except Exception:  # noqa: BLE001
    faiss = None
    _HAS_FAISS = False


class SemanticIndex:
    def __init__(self, vectors: np.ndarray):
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self.backend = "numpy"
        self._index = None
        if _HAS_FAISS and len(self.vectors):
            self._index = faiss.IndexFlatIP(self.vectors.shape[1])
            self._index.add(self.vectors)
            self.backend = "faiss"

    def search(self, queries: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Top-k (similarities, indices) per query row, sorted by descending similarity."""
        q = np.ascontiguousarray(queries, dtype=np.float32)
        n = len(self.vectors)
        k = max(0, min(k, n))
        if k == 0 or len(q) == 0:
            return np.zeros((len(q), 0), dtype=np.float32), np.zeros((len(q), 0), dtype=int)
        if self._index is not None:
            sims, idx = self._index.search(q, k)
            return np.nan_to_num(sims), idx
        sims = np.nan_to_num(q @ self.vectors.T)
        idx = np.argsort(-sims, axis=1)[:, :k]
        return np.take_along_axis(sims, idx, axis=1), idx
