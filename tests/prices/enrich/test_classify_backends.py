"""The backend seam: who scores, at what grain, where it lands, and what trains.

The load-bearing test here is `test_the_country_keyed_backend_...`: HierLex scores
per (name, country) and the head per name, so a run that keys on the wrong one
hands every country the same verdict without raising anything.
"""

from pathlib import Path

import pandas as pd
import pytest

from prices.enrich import config
from prices.enrich.classifier import backends
from prices.enrich.stages import classify

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_denylist(monkeypatch):
    """The basis audit reads a gold parquet that has nothing to do with which
    backend scored the row."""
    monkeypatch.setattr(classify.audit, "_denylist_map", dict)


def products(rows) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "input_hash": f"h{i}",
                "product_name_original": name,
                "country": country,
                "category": "",
                "lang": "en",
                "details": "",
                "declared_coicop_codes": "",
            }
            for i, (name, country) in enumerate(rows)
        ]
    )


def stub(
    name,
    key_cols,
    scores,
    divisions=("01",),
    path=Path("stub.parquet"),
    fit=None,
    unembedded=(),
):
    frame = pd.DataFrame(scores)
    # A stub declaring only leaf/conf/accepted gets the two reporting columns
    # for free, mirroring the head backend: its top-1 IS its leaf, and its gate
    # score IS its confidence. Tests that care about them pass their own.
    if not frame.empty:
        if "leaf_top1" not in frame.columns:
            frame["leaf_top1"] = frame["leaf"]
        if "gate_score" not in frame.columns:
            frame["gate_score"] = frame["conf"]
    result = backends.ScoreResult(frame=frame, unembedded=frozenset(unembedded))
    return backends.Backend(
        name=name,
        key_cols=key_cols,
        classified_path=path,
        decisions_path=path.with_name(f"decisions_{path.name}"),
        divisions=divisions,
        score=lambda products, version=None, workers=1: result,
        fit=fit,
    )


def install(monkeypatch, backend):
    monkeypatch.setitem(backends.BACKENDS, backend.name, backend)
    return backend


# ---- the registry -------------------------------------------------------


def test_both_backends_are_registered():
    assert sorted(backends.BACKENDS) == ["head", "hierlex"]


def test_the_default_backend_comes_from_config(monkeypatch):
    monkeypatch.setattr(config, "CLASSIFIER_BACKEND", "head")
    assert backends.get().name == "head"


def test_an_unknown_backend_is_named_in_the_error():
    with pytest.raises(ValueError, match="nonesuch"):
        backends.get("nonesuch")


def test_each_backend_writes_its_own_file():
    """Otherwise scoring with one model destroys the other model's run."""
    assert (
        backends.get("head").classified_path != backends.get("hierlex").classified_path
    )


def test_the_two_backends_score_at_different_grains():
    assert backends.get("head").key_cols == ("product_name_original",)
    assert backends.get("hierlex").key_cols == ("product_name_original", "country")


# ---- the training placeholder -------------------------------------------


def test_hierlex_reports_itself_as_untrainable():
    assert backends.get("hierlex").trainable is False
    assert backends.get("head").trainable is True


def test_training_a_frozen_bundle_refuses_with_a_reason():
    with pytest.raises(NotImplementedError, match="frozen bundle"):
        backends.fit_backend("hierlex")


def test_training_a_trainable_backend_reaches_its_fit(monkeypatch):
    called = {}

    def fit(version):
        called["version"] = version
        return {"ok": 1}

    install(monkeypatch, stub("trainable", ("product_name_original",), [], fit=fit))
    assert backends.fit_backend("trainable", version="v9") == {"ok": 1}
    assert called["version"] == "v9"


def test_the_hierlex_adapter_absence_says_what_to_do_instead(monkeypatch):
    """It is not in this repo yet; the error has to be actionable, not an
    ImportError from three frames down."""

    def boom():
        raise RuntimeError(backends._HIERLEX_MISSING)

    monkeypatch.setattr(backends, "_hierlex", boom)
    with pytest.raises(RuntimeError, match="--backend head"):
        backends._score_hierlex(products([("rice", "fiji")]))


# ---- what the stage does with a backend ---------------------------------


def test_the_country_keyed_backend_can_disagree_between_countries(monkeypatch):
    """Same product name, two countries, two verdicts — the whole reason
    HierLex scores at pair grain."""
    be = install(
        monkeypatch,
        stub(
            "pairs",
            ("product_name_original", "country"),
            {
                "product_name_original": ["rice", "rice"],
                "country": ["fiji", "tonga"],
                "leaf": ["01.1.1.1", "01.1.1.2"],
                "conf": [0.99, 0.98],
                "accepted": [True, True],
            },
        ),
    )
    out = classify.classify_products(
        products([("rice", "fiji"), ("rice", "tonga")]), backend=be.name
    )
    assert sorted(out["coicop_code"]) == ["01.1.1.1", "01.1.1.2"]


def test_a_name_keyed_backend_gives_both_countries_the_same_verdict(monkeypatch):
    """The counterexample. Not a bug in the head — it is country-blind by
    construction — but it is why key_cols cannot be a constant."""
    be = install(
        monkeypatch,
        stub(
            "names",
            ("product_name_original",),
            {
                "product_name_original": ["rice"],
                "leaf": ["01.1.1.1"],
                "conf": [0.99],
                "accepted": [True],
            },
        ),
    )
    out = classify.classify_products(
        products([("rice", "fiji"), ("rice", "tonga")]), backend=be.name
    )
    assert list(out["coicop_code"]) == ["01.1.1.1", "01.1.1.1"]


def test_a_name_the_backend_never_scored_is_rejected_not_dropped(monkeypatch):
    be = install(
        monkeypatch,
        stub(
            "sparse",
            ("product_name_original",),
            {
                "product_name_original": ["rice"],
                "leaf": ["01.1.1.1"],
                "conf": [0.99],
                "accepted": [True],
            },
        ),
    )
    out = classify.classify_products(
        products([("rice", "fiji"), ("unscored", "fiji")]), backend=be.name
    )
    # rejected rows carry no code, so the division filter drops them from the
    # output — what matters is that the run does not raise on a missing key.
    assert list(out["coicop_code"]) == ["01.1.1.1"]


def test_an_empty_score_frame_rejects_everything(monkeypatch):
    be = install(monkeypatch, stub("empty", ("product_name_original",), []))
    out = classify.classify_products(products([("rice", "fiji")]), backend=be.name)
    assert out.empty


def test_the_backends_divisions_are_the_filter(monkeypatch):
    """hierlex feeds a build that consumes 01 and 02; the head PoC was 01 alone."""
    scores = {
        "product_name_original": ["rice", "beer"],
        "leaf": ["01.1.1.1", "02.1.1.0"],
        "conf": [0.99, 0.99],
        "accepted": [True, True],
    }
    rows = [("rice", "fiji"), ("beer", "fiji")]

    narrow = install(
        monkeypatch, stub("one", ("product_name_original",), scores, ("01",))
    )
    assert list(
        classify.classify_products(products(rows), backend=narrow.name)["coicop_code"]
    ) == ["01.1.1.1"]

    wide = install(
        monkeypatch, stub("two", ("product_name_original",), scores, ("01", "02"))
    )
    assert sorted(
        classify.classify_products(products(rows), backend=wide.name)["coicop_code"]
    ) == [
        "01.1.1.1",
        "02.1.1.0",
    ]


def test_run_writes_to_the_backends_own_path(monkeypatch, tmp_path):
    be = install(
        monkeypatch,
        stub(
            "written",
            ("product_name_original",),
            {
                "product_name_original": ["rice"],
                "leaf": ["01.1.1.1"],
                "conf": [0.99],
                "accepted": [True],
            },
            path=tmp_path / "classified_written.parquet",
        ),
    )
    in_path = tmp_path / "products_input.parquet"
    products([("rice", "fiji")]).to_parquet(in_path, index=False)

    classify.run(in_path=in_path, backend=be.name)
    assert be.classified_path.exists()
    assert list(pd.read_parquet(be.classified_path)["coicop_code"]) == ["01.1.1.1"]


def test_a_declared_narrow_code_still_bypasses_the_backend(monkeypatch):
    """The backend scores nothing, and the row is classified anyway.

    The declared code is a five-level taxonomy LEAF. Four-level codes look like
    codes and are not leaves, which is the whole point of the check below.
    """
    be = install(monkeypatch, stub("ignored", ("product_name_original",), []))
    df = products([("rice", "fiji")])
    df.loc[0, "declared_coicop_codes"] = "01.1.1.1.5"
    out = classify.classify_products(df, backend=be.name)
    assert list(out["state"]) == ["narrow_source"]
    assert list(out["coicop_code"]) == ["01.1.1.1.5"]


def test_a_declared_code_that_is_not_a_leaf_falls_through_to_the_backend(monkeypatch):
    """A source may declare a parent node. That is not a classification.

    `01.1.1.5` is a real branch of the taxonomy and a plausible-looking code,
    but products do not live at that depth. Short-circuiting on it writes a
    non-leaf into `coicop_code`, where every consumer downstream assumes a leaf.
    69 source configs declared codes at this depth and were corrected; this is
    the half of the fix that stops the next one from landing.
    """
    be = install(
        monkeypatch,
        stub(
            "fallthrough",
            ("product_name_original",),
            {
                "product_name_original": ["rice"],
                "leaf": ["01.1.1.1.1"],
                "conf": [0.99],
                "accepted": [True],
            },
        ),
    )
    df = products([("rice", "fiji")])
    df.loc[0, "declared_coicop_codes"] = "01.1.1.5"
    out = classify.classify_products(df, backend=be.name)
    assert list(out["state"]) == ["classified"]
    assert list(out["coicop_code"]) == ["01.1.1.1.1"]


def test_declared_codes_arrive_pipe_joined_and_must_be_parsed(monkeypatch):
    """prepare serializes the list; is_narrow over the raw string iterates
    characters and silently declares nothing narrow."""
    be = install(monkeypatch, stub("ignored2", ("product_name_original",), []))
    df = products([("rice", "fiji")])
    # The same leaf twice: `parse_codes` collapses it to one code that resolves
    # to itself. Left as a raw string, `is_narrow` would iterate CHARACTERS and
    # find nothing narrow — which is the regression this guards.
    df.loc[0, "declared_coicop_codes"] = "01.1.1.1.5|01.1.1.1.5"
    out = classify.classify_products(df, backend=be.name)
    assert list(out["state"]) == ["narrow_source"]
    assert list(out["coicop_code"]) == ["01.1.1.1.5"]


def test_two_unrelated_declared_codes_are_not_narrow(monkeypatch):
    be = install(monkeypatch, stub("ignored3", ("product_name_original",), []))
    df = products([("rice", "fiji")])
    df.loc[0, "declared_coicop_codes"] = "01.1.1|04.1.1"
    out = classify.classify_products(df, backend=be.name)
    assert out.empty  # rejected, so no code, so filtered out


def test_a_name_with_no_vector_is_unembedded_not_rejected(monkeypatch):
    """The coverage denominator depends on telling these two apart.

    A name the store has no vector for was never scored — a sourcing/embedding
    backlog item. A name the model saw and refused is a model verdict. Both end
    up with no coicop_code, so if they share a state the report cannot say
    whether coverage is limited by the model or by the pipeline feeding it.
    """
    be = install(
        monkeypatch,
        stub(
            "gappy",
            ("product_name_original",),
            {
                "product_name_original": ["scored"],
                "leaf": ["01.1.1.1.0"],
                "conf": [0.2],
                "accepted": [False],
            },
            unembedded=("novec",),
        ),
    )
    out = classify.decide_products(
        products([("scored", "fiji"), ("novec", "fiji")]), backend=be.name
    )
    state = dict(zip(out["input_hash"], out["state"]))
    assert state["h0"] == "rejected"
    assert state["h1"] == "unembedded"


def test_the_decisions_table_keeps_every_row_the_view_drops(monkeypatch):
    """`classified` is a filtered view; `decisions` is the population."""
    be = install(
        monkeypatch,
        stub(
            "narrowview",
            ("product_name_original",),
            {
                "product_name_original": ["kept", "dropped"],
                "leaf": ["01.1.1.1.0", "07.2.1.1.0"],
                "conf": [0.9, 0.9],
                "accepted": [True, True],
            },
        ),
    )
    rows = products([("kept", "fiji"), ("dropped", "fiji")])
    decisions = classify.decide_products(rows, backend=be.name)
    view = classify.classified_view(decisions, be.divisions)
    assert len(decisions) == 2
    assert len(view) == 1
    assert set(decisions["coicop_code"]) == {"01.1.1.1.0", "07.2.1.1.0"}
