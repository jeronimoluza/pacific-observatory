"""A scoped classify run recomputes its countries and leaves the rest alone.

This is the property the per-country layout exists for: before it, fixing one
country meant rewriting a 37.4M-row decisions table, so `classify` could not
honour a selector at all.
"""

from pathlib import Path

import pandas as pd
import pytest

from prices.enrich.classifier import backends
from prices.enrich.stages import classify, decisions_store

from test_classify_backends import install, products, stub


@pytest.fixture(autouse=True)
def no_denylist(monkeypatch):
    monkeypatch.setattr(classify.audit, "_denylist_map", dict)


def corpus(tmp_path, rows) -> Path:
    in_path = tmp_path / "products_input.parquet"
    products(rows).to_parquet(in_path, index=False)
    return in_path


def shard_tree(tmp_path, entries) -> Path:
    """A `_per_source` tree, which is what a selector actually resolves against."""
    root = tmp_path / "_per_source"
    for region, subregion, country, source in entries:
        path = root / region / subregion / country / f"{source}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"x": [1]}).to_parquet(path, index=False)
    return root


def backend_for(monkeypatch, tmp_path, scores):
    return install(
        monkeypatch,
        stub(
            "scoped",
            ("product_name_original",),
            scores,
            path=tmp_path / "classified_scoped.parquet",
        ),
    )


def test_scoped_run_rewrites_only_its_country(monkeypatch, tmp_path):
    be = backend_for(
        monkeypatch,
        tmp_path,
        {
            "product_name_original": ["rice", "taro"],
            "leaf": ["01.1.1.1", "01.1.7.1"],
            "conf": [0.99, 0.99],
            "accepted": [True, True],
        },
    )
    in_path = corpus(tmp_path, [("rice", "fiji"), ("taro", "samoa")])
    root = shard_tree(
        tmp_path,
        [("eap", "pacific", "fiji", "shop"), ("eap", "pacific", "samoa", "shop")],
    )

    classify.run(in_path=in_path, backend=be.name)
    dec_root = decisions_store.parts_root(be.decisions_path)
    assert decisions_store.existing_countries(dec_root) == {"fiji", "samoa"}
    samoa_before = (dec_root / "samoa.parquet").read_bytes()

    # Re-run scoped to fiji only. Samoa's part must be byte-identical.
    summary = classify.run(
        in_path=in_path,
        backend=be.name,
        selectors=["eap/pacific/fiji"],
        shard_root=root,
    )
    assert summary["countries"] == ["fiji"]
    assert summary["decisions"] == 1
    assert (dec_root / "samoa.parquet").read_bytes() == samoa_before
    # And the union still holds both countries.
    assert sorted(decisions_store.read(be.decisions_path)["country"]) == [
        "fiji",
        "samoa",
    ]


def test_scoped_run_picks_up_a_changed_decision_for_its_country(monkeypatch, tmp_path):
    """The recomputed country must actually change, not just survive."""
    in_path = corpus(tmp_path, [("rice", "fiji"), ("taro", "samoa")])
    root = shard_tree(
        tmp_path,
        [("eap", "pacific", "fiji", "shop"), ("eap", "pacific", "samoa", "shop")],
    )
    accepted = {
        "product_name_original": ["rice", "taro"],
        "leaf": ["01.1.1.1", "01.1.7.1"],
        "conf": [0.99, 0.99],
        "accepted": [True, True],
    }
    be = backend_for(monkeypatch, tmp_path, accepted)
    classify.run(in_path=in_path, backend=be.name)

    rejected = dict(accepted, accepted=[False, False])
    be = backend_for(monkeypatch, tmp_path, rejected)
    classify.run(
        in_path=in_path,
        backend=be.name,
        selectors=["eap/pacific/fiji"],
        shard_root=root,
    )

    dec = decisions_store.read(be.decisions_path).set_index("country")
    assert dec.loc["fiji", "state"] == "rejected"
    assert dec.loc["samoa", "state"] == "classified"  # untouched by the scoped run


def test_a_selector_matching_nothing_refuses_rather_than_wiping(monkeypatch, tmp_path):
    """An empty scope must not read as 'every country produced no rows'."""
    be = backend_for(monkeypatch, tmp_path, {})
    in_path = corpus(tmp_path, [("rice", "fiji")])
    root = shard_tree(tmp_path, [("eap", "pacific", "fiji", "shop")])

    with pytest.raises(RuntimeError, match="no shards match"):
        classify.run(
            in_path=in_path,
            backend=be.name,
            selectors=["ssa/western/ghana"],
            shard_root=root,
        )


def test_a_full_run_prunes_a_country_that_no_longer_has_rows(monkeypatch, tmp_path):
    """Full runs are authoritative; a stale part reads exactly like a live one."""
    be = backend_for(
        monkeypatch,
        tmp_path,
        {
            "product_name_original": ["rice", "taro"],
            "leaf": ["01.1.1.1", "01.1.7.1"],
            "conf": [0.99, 0.99],
            "accepted": [True, True],
        },
    )
    in_path = corpus(tmp_path, [("rice", "fiji"), ("taro", "samoa")])
    classify.run(in_path=in_path, backend=be.name)
    dec_root = decisions_store.parts_root(be.decisions_path)
    assert "samoa" in decisions_store.existing_countries(dec_root)

    # Samoa leaves the corpus entirely.
    products([("rice", "fiji")]).to_parquet(in_path, index=False)
    classify.run(in_path=in_path, backend=be.name)
    assert decisions_store.existing_countries(dec_root) == {"fiji"}


def test_a_scoped_run_never_prunes(monkeypatch, tmp_path):
    """Everything a scoped run did not write is out of scope, not stale."""
    be = backend_for(
        monkeypatch,
        tmp_path,
        {
            "product_name_original": ["rice", "taro"],
            "leaf": ["01.1.1.1", "01.1.7.1"],
            "conf": [0.99, 0.99],
            "accepted": [True, True],
        },
    )
    in_path = corpus(tmp_path, [("rice", "fiji"), ("taro", "samoa")])
    root = shard_tree(
        tmp_path,
        [("eap", "pacific", "fiji", "shop"), ("eap", "pacific", "samoa", "shop")],
    )
    classify.run(in_path=in_path, backend=be.name)

    classify.run(
        in_path=in_path,
        backend=be.name,
        selectors=["eap/pacific/fiji"],
        shard_root=root,
    )
    dec_root = decisions_store.parts_root(be.decisions_path)
    assert decisions_store.existing_countries(dec_root) == {"fiji", "samoa"}


def test_countries_for_resolves_a_source_selector_to_its_whole_country(tmp_path):
    """A selector names a source; prepare's input_hash grain is the country."""
    root = shard_tree(
        tmp_path,
        [
            ("eap", "pacific", "fiji", "shop_a"),
            ("eap", "pacific", "fiji", "shop_b"),
            ("eap", "pacific", "samoa", "shop_c"),
        ],
    )
    assert classify.countries_for(["**/shop_a"], root) == ["fiji"]
    assert classify.countries_for(None, root) is None


def test_scoped_classified_view_part_is_replaced_not_appended(monkeypatch, tmp_path):
    """Re-running one country must not double its rows in classified."""
    be = backend_for(
        monkeypatch,
        tmp_path,
        {
            "product_name_original": ["rice"],
            "leaf": ["01.1.1.1"],
            "conf": [0.99],
            "accepted": [True],
        },
    )
    in_path = corpus(tmp_path, [("rice", "fiji")])
    root = shard_tree(tmp_path, [("eap", "pacific", "fiji", "shop")])

    classify.run(in_path=in_path, backend=be.name)
    for _ in range(2):
        classify.run(
            in_path=in_path,
            backend=be.name,
            selectors=["eap/pacific/fiji"],
            shard_root=root,
        )
    assert len(decisions_store.read(be.classified_path)) == 1
    assert len(decisions_store.read(be.decisions_path)) == 1


def test_backends_registry_is_untouched_by_these_stubs():
    assert sorted(backends.BACKENDS) == ["head", "hierlex"]
