"""HierLex-Select production adapter tests.

The parity test is the load-bearing one: the bundle ships 20 input rows and the
output its author got for them, so scoring those rows through our embed store and
our batching must reproduce that file. It is what distinguishes "we run his
model" from "we run something like his model" — every categorical field has to
match exactly, and the scores only to embed-store rounding.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.enrich.hierlex import package

pytestmark = pytest.mark.integration

EXACT_COLS = (
    "assigned_coicop",
    "proposed_leaf",
    "is_fallback",
    "accepted",
    "parent_pred",
    "script",
)
NUMERIC_COLS = (
    "original_score",
    "raw_correctness_score",
    "calibrated_correctness_score",
    "parent_score",
)


@pytest.fixture(scope="module")
def bundle():
    if not package.available():
        pytest.skip("no HierLex bundle installed")
    return package.resolve()


def test_bundle_integrity(bundle):
    assert package.verify(bundle) == []


def test_embedding_recipe_matches_ours(bundle):
    from prices.enrich import config

    ours = [
        (b["tag"], b["dim"], float(b["weight"]))
        for b in config.CLASSIFIER_EMBED_ENSEMBLE
    ]
    his = [
        (f"{f.split('.')[0]}", int(d), float(w))
        for _, f, d, w in package.manifest(bundle)["embedding_specs"]
    ]
    assert [(d, w) for _, d, w in ours] == [(d, w) for _, d, w in his]
    assert [t for t, _, _ in ours] == [t for t, _, _ in his]


def test_reference_output_reproduces(bundle):
    """Score the bundle's own 20 sample rows out of our embed store."""
    from prices.enrich.hierlex import scorer, vectors

    inp = pd.read_csv(bundle / "examples" / "sample_input_20.csv")
    ref = pd.read_csv(bundle / "examples" / "sample_output_20.csv")
    names = inp["product_name"].astype(str)
    _, missing = vectors.split_by_store_coverage(names)
    if missing:
        pytest.skip(f"{len(missing)} sample names absent from the local embed store")

    s = scorer.load()
    got = s.score(
        names.to_numpy(),
        inp["country"].astype(str).to_numpy(),
        vectors.matrix_for_names(names),
        policy=str(ref["accept_policy"].iloc[0]),
    )

    for col in EXACT_COLS:
        assert (got[col].astype(str).values == ref[col].astype(str).values).all(), col
    for col in NUMERIC_COLS:
        delta = np.abs(got[col].values.astype(float) - ref[col].values.astype(float))
        # fp16 store vectors vs the author's fp32 gold vectors; ~5e-4 relative on
        # the unit vectors, which lands well under 1e-4 on the probabilities.
        assert delta.max() < 1e-4, f"{col}: max |delta| = {delta.max():.3e}"


def test_decide_rows_keys_on_name_and_country():
    """The (name, country) key must route a name to a per-country decision."""
    from prices.enrich.stages.classify import decide_rows

    products = pd.DataFrame(
        {
            "input_hash": ["h1", "h2"],
            "product_name_original": ["Rice 1kg", "Rice 1kg"],
            "category": [None, None],
            "country": ["japan", "peru"],
            "lang": ["en", "en"],
            "details": [None, None],
            "declared_coicop_codes": [None, None],
            "_hlx_country": ["japan", "peru"],
        }
    )
    key = ("Rice 1kg", "japan")
    other = ("Rice 1kg", "peru")
    out = decide_rows(
        products,
        {
            # (leaf, conf, accepted, leaf_top1, gate_score)
            key: ("01.1.1.1.0", 0.99, True, "01.1.1.1.0", 0.97),
            other: ("01.1.1.1.0", 0.10, False, "01.1.1.1.0", 0.20),
        },
        ("product_name_original", "_hlx_country"),
        frozenset(),
    )
    assert out.loc[0, "state"] == "classified"
    assert out.loc[0, "coicop_code"] == "01.1.1.1.0"
    assert out.loc[1, "state"] == "rejected"
    assert out.loc[1, "coicop_code"] is None


def test_decide_rows_default_keying_unchanged():
    """The name-keyed path callers already use must behave exactly as before."""
    from prices.enrich.stages.classify import decide_rows

    products = pd.DataFrame(
        {
            "input_hash": ["h1"],
            "product_name_original": ["Rice 1kg"],
            "category": [None],
            "country": ["japan"],
            "lang": ["en"],
            "details": [None],
            "declared_coicop_codes": [None],
        }
    )
    out = decide_rows(
        products,
        {("Rice 1kg",): ("01.1.1.1.0", 0.99, True, "01.1.1.1.0", 0.97)},
        ("product_name_original",),
        frozenset(),
    )
    assert out.loc[0, "state"] == "classified"
    assert out.loc[0, "leaf_top1"] == "01.1.1.1.0"
