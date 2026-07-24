import numpy as np
import pytest

from prices.enrich import embedding

# A small fake ensemble: three blocks of distinct width, so the concat geometry
# (order, per-block L2, total width) is checkable without the heavy mlx models.
BLOCKS = [
    {"tag": "a", "backend": "st", "model": "model-a", "seq": 48},
    {"tag": "b", "backend": "mlx", "model": "model-b", "seq": 512},
    {"tag": "c", "backend": "mlx", "model": "model-c", "seq": 512},
]
DIMS = {"model-a": 4, "model-b": 8, "model-c": 16}
TOTAL = sum(DIMS.values())


def _fake_block(model_id, names):
    """Deterministic per-(model, name) unit vector of the model's own width."""
    out = []
    for n in names:
        rng = np.random.default_rng(abs(hash((model_id, n))) % (2**32))
        v = rng.standard_normal(DIMS[model_id]).astype(np.float32)
        out.append(v / np.linalg.norm(v))
    return np.vstack(out).astype(np.float32)


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(embedding.config, "CLASSIFIER_EMBED_CACHE_DIR", tmp_path)
    monkeypatch.setattr(embedding.config, "CLASSIFIER_EMBED_ENSEMBLE", BLOCKS)
    calls = {"n": 0}

    def counting(block, names):
        calls["n"] += 1
        return _fake_block(block["model"], names)

    monkeypatch.setattr(embedding, "_encode_block", counting)
    yield tmp_path, calls


@pytest.mark.unit
def test_empty_returns_empty(isolated_cache):
    _, calls = isolated_cache
    out = embedding.embed_names([])
    assert out.shape == (0, 0)
    assert calls["n"] == 0


@pytest.mark.unit
def test_concat_width_and_per_block_l2(isolated_cache):
    names = ["jasmine rice 5kg", "coca cola 1.5l"]
    out = embedding.embed_names(names)
    assert out.shape == (2, TOTAL)
    # each block sub-vector stays unit-norm (no global renorm across blocks)
    np.testing.assert_allclose(np.linalg.norm(out[:, 0:4], axis=1), 1.0, rtol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(out[:, 4:12], axis=1), 1.0, rtol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(out[:, 12:28], axis=1), 1.0, rtol=1e-5)
    # full vector norm is sqrt(n_blocks), NOT 1 — blocks are concatenated, not merged
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), np.sqrt(3.0), rtol=1e-5)


@pytest.mark.unit
def test_block_order_matches_config(isolated_cache):
    name = "arabica coffee 250g"
    out = embedding.embed_names([name])
    # block 0 occupies the first DIMS['model-a'] columns, in config order
    # (allclose, not equal: the defensive per-block renorm adds ~1e-7 fp drift)
    np.testing.assert_allclose(
        out[0, 0:4], _fake_block("model-a", [name])[0], rtol=1e-5
    )
    np.testing.assert_allclose(
        out[0, 4:12], _fake_block("model-b", [name])[0], rtol=1e-5
    )
    np.testing.assert_allclose(
        out[0, 12:28], _fake_block("model-c", [name])[0], rtol=1e-5
    )


@pytest.mark.unit
def test_row_alignment_and_dedup(isolated_cache):
    names = ["jasmine rice 5kg", "coca cola 1.5l", "jasmine rice 5kg"]
    out = embedding.embed_names(names)
    assert out.shape == (3, TOTAL)
    np.testing.assert_array_equal(out[0], out[2])


@pytest.mark.unit
def test_cache_hit_skips_backend(isolated_cache):
    _, calls = isolated_cache
    names = ["arabica coffee 250g", "green tea 100 bags"]
    embedding.embed_names(names)
    assert calls["n"] == len(BLOCKS)  # one encode per block, first pass
    embedding.embed_names(names)
    assert calls["n"] == len(BLOCKS)  # fully cached -> no further backend calls


@pytest.mark.unit
def test_cache_persists_across_fresh_read(isolated_cache):
    _, calls = isolated_cache
    first = embedding.embed_names(["sardines in oil 155g"])
    calls["n"] = 0
    second = embedding.embed_names(["sardines in oil 155g"])
    assert calls["n"] == 0  # served from the per-block .npz on disk
    np.testing.assert_array_equal(first, second)
