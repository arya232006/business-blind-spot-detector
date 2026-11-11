import numpy as np
import pytest

from ml.embeddings import TfidfLsaEmbedder, cosine_matrix, get_embedder, l2_normalize


def test_vectors_are_unit_length_and_finite():
    e = TfidfLsaEmbedder(n_components=4).fit(["refund slow money", "delivery late parcel", "support chatbot human", "app crash screen"] * 3)
    v = e.encode(["refund money", "completely unknown words xyz", "late parcel"])
    assert np.isfinite(v).all() and np.allclose(np.linalg.norm(v, axis=1), 1, atol=1e-5)  # unknown text must not give a zero vector


def test_cosine_matrix_shapes_and_empty():
    a = l2_normalize(np.random.rand(3, 5)); b = l2_normalize(np.random.rand(4, 5))
    assert cosine_matrix(a, b).shape == (3, 4) and cosine_matrix(a[:0], b).shape == (0, 4)


def test_fallback_when_backend_is_tfidf():
    assert not get_embedder("tfidf", ["some text here", "more text there", "other words"]).is_semantic


def test_sbert_understands_paraphrase_without_shared_keywords():
    """The core requirement: 'seamless assistance' (company) relates to 'difficulty reaching support' (customers)."""
    emb = get_embedder("sbert")
    if not emb.is_semantic:
        pytest.skip("SBERT model not available offline")
    v = emb.encode(["We offer seamless assistance whenever you need help", "It is really difficult to reach customer support",
                    "Huge discounts on electronics this weekend"])
    related, unrelated = float(v[0] @ v[1]), float(v[2] @ v[1])
    assert related > unrelated + 0.1


def test_semantic_index_matches_numpy_bruteforce():
    from ml.semantic_search import SemanticIndex

    rng = np.random.default_rng(0)
    docs = l2_normalize(rng.normal(size=(40, 16))); qs = l2_normalize(rng.normal(size=(5, 16)))
    sims, idx = SemanticIndex(docs).search(qs, 3)
    brute = qs @ docs.T
    assert np.array_equal(idx, np.argsort(-brute, axis=1)[:, :3]) and np.allclose(sims, np.sort(brute, axis=1)[:, ::-1][:, :3], atol=1e-5)
    assert SemanticIndex(docs).search(qs, 100)[1].shape == (5, 40)           # k is capped at corpus size
    assert SemanticIndex(docs[:0]).search(qs, 3)[1].shape == (5, 0)
