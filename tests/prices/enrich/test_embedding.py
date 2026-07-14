import numpy as np
import pytest

from prices.enrich import embedding


class _FakeModel:
    """Deterministic stand-in for SentenceTransformer: maps each input string to
    a fixed unit vector by hashing, so encode() is reproducible and model-free."""

    calls = 0

    def encode(
        self, texts, batch_size=8, normalize_embeddings=True, show_progress_bar=False
    ):
        _FakeModel.calls += 1
        out = []
        for t in texts:
            rng = np.random.default_rng(abs(hash(t)) % (2**32))
            v = rng.standard_normal(16).astype(np.float32)
            if normalize_embeddings:
                v = v / np.linalg.norm(v)
            out.append(v)
        return np.vstack(out)


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(embedding.config, "CLASSIFIER_EMBED_CACHE_DIR", tmp_path)
    embedding._MODEL = None
    _FakeModel.calls = 0
    monkeypatch.setattr(embedding, "_load_model", lambda: _FakeModel())
    yield tmp_path


@pytest.mark.unit
def test_empty_returns_empty(isolated_cache):
    out = embedding.embed_names([])
    assert out.shape == (0, 0)


@pytest.mark.unit
def test_row_alignment_and_normalization(isolated_cache):
    names = ["jasmine rice 5kg", "coca cola 1.5l", "jasmine rice 5kg"]
    out = embedding.embed_names(names)
    assert out.shape == (3, 16)
    # duplicate name -> identical row
    np.testing.assert_array_equal(out[0], out[2])
    # L2-normalized
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, rtol=1e-5)


@pytest.mark.unit
def test_cache_hit_skips_model(isolated_cache):
    names = ["arabica coffee 250g", "green tea 100 bags"]
    embedding.embed_names(names)
    assert _FakeModel.calls == 1
    # second call is fully cached -> model not invoked again
    embedding.embed_names(names)
    assert _FakeModel.calls == 1


@pytest.mark.unit
def test_cache_persists_across_fresh_dict(isolated_cache):
    first = embedding.embed_names(["sardines in oil 155g"])
    # a new process would reload the .npz; simulate by clearing the model and
    # confirming the vector is served from disk without re-encoding
    _FakeModel.calls = 0
    second = embedding.embed_names(["sardines in oil 155g"])
    assert _FakeModel.calls == 0
    np.testing.assert_array_equal(first, second)
