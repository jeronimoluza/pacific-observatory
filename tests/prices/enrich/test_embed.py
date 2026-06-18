"""Smoke tests for tier (b) embedding backends.

Gemini test runs only when GOOGLE_API_KEY/GEMINI_API_KEY is set.
e5 test runs only when sentence-transformers is installed.
Both backends are exercised offline via the cache layer so a normal
pytest run requires neither.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from prices.enrich import config, embed


def test_cache_key_distinguishes_backend_and_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EMBED_CACHE_PATH", tmp_path / "cache.npz")
    a = embed._cache_key("passage: x", "gemini", 768)
    b = embed._cache_key("query: x", "gemini", 768)
    c = embed._cache_key("passage: x", "e5", 768)
    d = embed._cache_key("passage: x", "gemini", 256)
    assert len({a, b, c, d}) == 4


def test_cache_hit_skips_backend(monkeypatch, tmp_path):
    """A second call for the same prefixed text must NOT re-invoke the backend."""
    monkeypatch.setattr(config, "EMBED_CACHE_PATH", tmp_path / "cache.npz")
    monkeypatch.setattr(config, "EMBED_DIM", 4)
    monkeypatch.setattr(config, "EMBED_BACKEND", "gemini")

    calls = {"n": 0}

    def fake_gemini(texts, dim):
        calls["n"] += 1
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(embed, "_embed_gemini", fake_gemini)

    embed.embed_texts(["passage: apple"])
    embed.embed_texts(["passage: apple"])
    assert calls["n"] == 1  # cache hit on second call


def test_prefix_discipline_passes_through(monkeypatch, tmp_path):
    """`embed_texts` does not prepend prefixes — the caller must. Verify the
    backend receives exactly what was passed in."""
    monkeypatch.setattr(config, "EMBED_CACHE_PATH", tmp_path / "cache.npz")
    monkeypatch.setattr(config, "EMBED_DIM", 4)
    monkeypatch.setattr(config, "EMBED_BACKEND", "gemini")

    received: list[list[str]] = []

    def fake_gemini(texts, dim):
        received.append(list(texts))
        return [[0.0] * dim for _ in texts]

    monkeypatch.setattr(embed, "_embed_gemini", fake_gemini)
    embed.embed_texts(["passage: foo", "query: bar"])
    assert received == [["passage: foo", "query: bar"]]


@pytest.mark.skipif(
    not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")),
    reason="GOOGLE_API_KEY / GEMINI_API_KEY not set",
)
def test_gemini_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EMBED_CACHE_PATH", tmp_path / "cache.npz")
    arr = embed.embed_texts(
        ["passage: apple", "passage: orange"], backend="gemini", dim=768
    )
    assert arr.shape == (2, 768)
    assert arr.dtype == np.float32


@pytest.mark.skipif(
    pytest.importorskip("sentence_transformers", reason="sentence_transformers missing")
    is None,
    reason="sentence_transformers missing",
)
def test_e5_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EMBED_CACHE_PATH", tmp_path / "cache.npz")
    arr = embed.embed_texts(["passage: apple", "query: apple"], backend="e5", dim=384)
    assert arr.shape == (2, 384)
