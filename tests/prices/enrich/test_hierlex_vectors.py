"""Block width is checked per block, so a mis-sized store tag names itself."""

from __future__ import annotations

import numpy as np
import pytest

from prices.enrich import config
from prices.enrich.classifier import embed_store
from prices.enrich.hierlex import vectors

ENSEMBLE = [
    {"tag": "a", "dim": 4, "weight": 1.0, "backend": "store"},
    {"tag": "b", "dim": 3, "weight": 1.0, "backend": "store"},
]


def _patch(monkeypatch, widths):
    monkeypatch.setattr(config, "CLASSIFIER_EMBED_ENSEMBLE", ENSEMBLE)
    monkeypatch.setattr(
        embed_store,
        "gather",
        lambda tag, b, names: np.ones((len(names), widths[tag]), dtype=np.float32),
    )


def test_matrix_for_bucket_concatenates_declared_widths(monkeypatch):
    _patch(monkeypatch, {"a": 4, "b": 3})
    out = vectors.matrix_for_bucket(0, ["x", "y"])
    assert out.shape == (2, 7)


def test_matrix_for_bucket_names_the_mis_sized_block(monkeypatch):
    # The tag is a directory name, so a store rebuilt with a different model
    # keeps the tag and changes the width. hstack would accept it: the blocks
    # still share a row count, and only the total is wrong.
    _patch(monkeypatch, {"a": 4, "b": 1024})
    with pytest.raises(ValueError) as e:
        vectors.matrix_for_bucket(0, ["x", "y"])
    assert "'b'" in str(e.value)
    assert "1024" in str(e.value)
    assert "3" in str(e.value)
