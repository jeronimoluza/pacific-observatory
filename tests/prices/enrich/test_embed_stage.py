"""The embed stage: what is missing, embedded here, or staged for a fleet.

The assertion that matters most is `test_staging_rents_nothing` — the runpod
path bills by the hour, so it has to stop at "here is the command".
"""

import numpy as np
import pandas as pd
import pytest

from prices import partition
from prices.enrich import prepare_shards, shards
from prices.enrich.classifier import embed_store
from prices.enrich.stages import embed

pytestmark = pytest.mark.unit


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Two countries prepared, plus an empty store to fill."""
    monkeypatch.setattr(embed_store, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(embed, "STAGE_DIR", tmp_path / "staging")

    per_source = tmp_path / "_per_source"
    for country, source, names in [
        ("fiji", "shop_a", ["Rice 1kg", "Flour 2kg"]),
        ("tonga", "shop_c", ["Sugar 1kg"]),
    ]:
        shards.write_shard(
            pd.DataFrame({"product_name": names, "country": [country] * len(names)}),
            per_source / "eap" / "pacific" / country / f"{source}.parquet",
        )
    monkeypatch.setattr(partition, "PER_SOURCE_DIR", per_source)

    prepared = tmp_path / "_prepared"
    monkeypatch.setattr(prepare_shards, "PREPARED_DIR", prepared)
    for country, names in [
        ("fiji", ["Rice 1kg", "Flour 2kg"]),
        ("tonga", ["Sugar 1kg"]),
    ]:
        path = prepared / "eap" / "pacific" / f"{country}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"product_name_original": names}).to_parquet(path, index=False)
    return tmp_path


def test_the_universe_is_every_name_in_scope(corpus):
    frame = embed.universe()
    assert sorted(frame["product_name_original"]) == [
        "Flour 2kg",
        "Rice 1kg",
        "Sugar 1kg",
    ]


def test_a_selector_narrows_the_universe_to_one_country(corpus):
    frame = embed.universe(["eap/pacific/fiji"])
    assert sorted(frame["product_name_original"]) == ["Flour 2kg", "Rice 1kg"]


def test_every_name_carries_the_bucket_it_hashes_to(corpus):
    frame = embed.universe()
    for name, bucket in zip(frame["product_name_original"], frame["bucket"]):
        assert bucket == embed_store.bucket_of(name)


def test_a_name_appears_once_however_many_rows_it_has(corpus, monkeypatch):
    path = corpus / "_prepared" / "eap" / "pacific" / "fiji.parquet"
    pd.DataFrame({"product_name_original": ["Rice 1kg"] * 5}).to_parquet(
        path, index=False
    )
    frame = embed.universe(["eap/pacific/fiji"])
    assert list(frame["product_name_original"]) == ["Rice 1kg"]


def test_missing_is_reported_per_block(corpus, monkeypatch):
    """A run that died between blocks leaves a store that is useless and looks
    nearly complete, so one aggregate number would hide it."""
    monkeypatch.setattr(
        embed.config,
        "CLASSIFIER_EMBED_ENSEMBLE",
        [{"tag": "a"}, {"tag": "b"}],
    )
    names = ["Rice 1kg", "Flour 2kg"]
    embed_store.append(
        "a", embed_store.bucket_of(names[0]), [names[0]], np.zeros((1, 4), np.float16)
    )
    assert embed.missing(names) == {"a": 1, "b": 2}


def test_nothing_missing_short_circuits_before_any_backend(corpus, monkeypatch):
    monkeypatch.setattr(embed, "missing", lambda names, tags=None: {"a": 0})
    monkeypatch.setattr(
        embed, "run_local", lambda names: pytest.fail("should not have embedded")
    )
    out = embed.run(backend="local")
    assert out["missing"] == {"a": 0}


def test_local_embeds_exactly_the_names_in_scope(corpus, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        embed.batch_embed, "_build_store", lambda by_bucket: seen.update(by_bucket)
    )
    monkeypatch.setattr(embed, "missing", lambda names, tags=None: {"a": len(names)})
    embed.run(backend="local", selectors=["eap/pacific/tonga"])
    assert [n for names in seen.values() for n in names] == ["Sugar 1kg"]


def test_staging_rents_nothing(corpus, monkeypatch):
    """Pods bill from the moment they exist. Staging writes files and prints."""
    monkeypatch.setattr(embed, "missing", lambda names, tags=None: {"a": 3})
    out = embed.run(backend="runpod", pods=4)
    assert out["universe"].exists()
    assert out["pods"] == 4
    assert any("plan.py --pods 4" in c for c in out["commands"])
    assert not any("runpodctl" in c or "create-pod" in c for c in out["commands"])


def test_the_staged_universe_is_what_the_fleet_partitions_on(corpus, monkeypatch):
    monkeypatch.setattr(embed, "missing", lambda names, tags=None: {"a": 3})
    out = embed.run(backend="runpod", selectors=["eap/pacific/fiji"])
    staged = pd.read_parquet(out["universe"])
    assert sorted(staged.columns) == ["bucket", "product_name_original"]
    assert sorted(staged["product_name_original"]) == ["Flour 2kg", "Rice 1kg"]


def test_an_unknown_backend_is_refused(corpus, monkeypatch):
    monkeypatch.setattr(embed, "missing", lambda names, tags=None: {"a": 3})
    with pytest.raises(ValueError, match="nonesuch"):
        embed.run(backend="nonesuch")


def test_an_empty_corpus_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(partition, "PER_SOURCE_DIR", tmp_path / "nothing")
    monkeypatch.setattr(prepare_shards, "PREPARED_DIR", tmp_path / "nothing")
    monkeypatch.setattr(
        embed.config, "PRODUCTS_INPUT_PARQUET", tmp_path / "missing.parquet"
    )
    assert embed.universe().empty
