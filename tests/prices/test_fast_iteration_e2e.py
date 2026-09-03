"""End to end: a fix in one country reaches the build without rebuilding the rest.

Walks the real stages — concatenate, prepare, build — over a miniature corpus,
then changes one source and re-runs scoped to that country. The assertion that
matters is the last one: the rebuilt frame still carries every other country.

FX is stubbed. It reads an external rate table rather than anything derived
from the corpus, so it has no bearing on whether scoping is correct, and it is
covered by its own tests.
"""

import json

import pandas as pd
import pytest

from prices import partition
from prices.build import aggregate
from prices.enrich import config as enrich_config
from prices.enrich import prepare_shards
from prices.enrich.stages import concatenate

pytestmark = pytest.mark.unit

CORPUS = {
    ("eap", "pacific", "fiji", "shop_a"): [("Rice 1kg", "10.00")],
    ("eap", "pacific", "fiji", "shop_b"): [("Flour 2kg", "8.00")],
    ("eap", "pacific", "tonga", "shop_c"): [("Rice 1kg", "12.00")],
    ("eap", "pacific", "samoa", "shop_d"): [("Sugar 1kg", "5.00")],
}


def write_source(data_root, region, subregion, country, source, items):
    path = data_root / region / subregion / country / source / "raw_items" / "a.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for name, price in items:
            fh.write(
                json.dumps(
                    {
                        "product_name": name,
                        "price": price,
                        "currency": "FJD",
                        "scraped_at_utc": "2026-01-02T10:00:00Z",
                        "url": f"https://{source}/{name.split()[0].lower()}",
                        "product_id": name,
                        "category": "",
                        "details": "",
                    }
                )
                + "\n"
            )


def stub_fx(df):
    out = df.copy()
    out["fx_rate"] = 1.0
    out["price_usd"] = out["price_local"]
    return out


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    data_root = tmp_path / "data" / "prices"
    per_source = tmp_path / "outputs" / "prices" / "raw" / "_per_source"
    build_dir = tmp_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    for (region, sub, country, source), items in CORPUS.items():
        write_source(data_root, region, sub, country, source, items)

    monkeypatch.setattr(concatenate, "DATA_PRICES_ROOT", data_root)
    monkeypatch.setattr(concatenate, "PER_SOURCE_DIR", per_source)
    monkeypatch.setattr(concatenate, "RAW_CSV", tmp_path / "raw_prices.csv")
    monkeypatch.setattr(concatenate, "STATE_FILE", tmp_path / ".state.json")
    monkeypatch.setattr(concatenate, "_channel_for", lambda c, s: "retail")
    monkeypatch.setattr(concatenate, "_classifier_csv_map", dict)

    monkeypatch.setattr(partition, "PER_SOURCE_DIR", per_source)
    monkeypatch.setattr(prepare_shards, "PREPARED_DIR", tmp_path / "_prepared")
    products_input = tmp_path / "products_input.parquet"
    monkeypatch.setattr(enrich_config, "PRODUCTS_INPUT_PARQUET", products_input)
    monkeypatch.setattr(prepare_shards.config, "PRODUCTS_INPUT_PARQUET", products_input)

    monkeypatch.setattr(aggregate, "partition", partition)
    monkeypatch.setattr(aggregate, "BUILD_DIR", build_dir)
    monkeypatch.setattr(
        aggregate, "OBSERVATIONS_PARQUET", build_dir / "observations.parquet"
    )
    monkeypatch.setattr(aggregate, "attach_fx_and_usd", stub_fx)
    monkeypatch.setattr(aggregate, "FX_HISTORY_FLOOR", pd.Timestamp("2020-01-01"))
    return {
        "data_root": data_root,
        "per_source": per_source,
        "products_input": products_input,
        "observations": build_dir / "observations.parquet",
    }


def classified_from(products_input, monkeypatch, tmp_path):
    """A classifier output keyed on the hashes prepare produced — the join the
    whole pipeline turns on."""
    pi = pd.read_parquet(products_input)
    cache = pd.DataFrame(
        {
            "input_hash": pi["input_hash"],
            "pricing_basis": "mass",
            "amount_value": 1.0,
            "standard_unit": "kg",
            "count": float("nan"),
            "multiplier": float("nan"),
            "coicop_code": "01.1.1.1",
            "is_promotion": False,
            "is_bundle": False,
            "is_multipack": False,
            "confidence": 0.99,
            "trust_level": "high",
            "state": "classified",
        }
    )
    path = tmp_path / "classified.parquet"
    cache.to_parquet(path, index=False)
    # BUILD_CLASSIFIED_PARQUET is what build reads: the ACTIVE backend's output,
    # which is classified_hierlex.parquet by default. Patching only the head's
    # constant left build looking at a file no test ever wrote.
    monkeypatch.setattr(enrich_config, "CLASSIFIED_PARQUET", path)
    monkeypatch.setattr(enrich_config, "BUILD_CLASSIFIED_PARQUET", path)
    return path


def test_concatenate_prepare_build_then_a_scoped_rebuild(
    pipeline, tmp_path, monkeypatch
):
    # 1. concatenate -> one parquet shard per source, each carrying input_hash
    concatenate.run(write_monolith=False)
    shard_keys = {s.key for s in partition.select(None, pipeline["per_source"])}
    assert shard_keys == {
        "eap/pacific/fiji/shop_a",
        "eap/pacific/fiji/shop_b",
        "eap/pacific/tonga/shop_c",
        "eap/pacific/samoa/shop_d",
    }

    # 2. prepare -> one parquet per country, unioned into products_input
    prepare_shards.run(root=pipeline["per_source"], out_dir=tmp_path / "_prepared")
    pi = pd.read_parquet(pipeline["products_input"])
    assert set(pi["country"]) == {"fiji", "tonga", "samoa"}
    assert pi["input_hash"].notna().all()

    # 3. build -> observations covering every country
    classified_from(pipeline["products_input"], monkeypatch, tmp_path)
    full = aggregate.build_observations(shard_root=pipeline["per_source"])
    assert set(full["country"]) == {"fiji", "tonga", "samoa"}
    fiji_before = full[full["country"] == "fiji"]["price_local"].tolist()
    assert sorted(fiji_before) == [8.0, 10.0]
    tonga_before = full[full["country"] == "tonga"]["price_local"].tolist()

    # 4. a fix lands in one source only
    write_source(
        pipeline["data_root"],
        "eap",
        "pacific",
        "fiji",
        "shop_a",
        [("Rice 1kg", "99.00")],
    )
    concatenate.run(write_monolith=False, selectors=["eap/pacific/fiji"])
    prepare_shards.run(
        ["eap/pacific/fiji"],
        root=pipeline["per_source"],
        out_dir=tmp_path / "_prepared",
    )
    classified_from(pipeline["products_input"], monkeypatch, tmp_path)

    # 5. scoped rebuild -> fiji changes, nothing else is lost
    after = aggregate.build_observations(
        selectors=["eap/pacific/fiji"],
        shard_root=pipeline["per_source"],
        overlay=True,
    )
    assert set(after["country"]) == {"fiji", "tonga", "samoa"}
    assert sorted(after[after["country"] == "fiji"]["price_local"]) == [8.0, 99.0]
    assert after[after["country"] == "tonga"]["price_local"].tolist() == tonga_before
    assert (after["country"] == "samoa").sum() == 1


def test_a_scoped_rebuild_without_overlay_would_lose_the_other_countries(
    pipeline, tmp_path, monkeypatch
):
    """The counterexample the overlay exists to prevent."""
    concatenate.run(write_monolith=False)
    prepare_shards.run(root=pipeline["per_source"], out_dir=tmp_path / "_prepared")
    classified_from(pipeline["products_input"], monkeypatch, tmp_path)
    aggregate.build_observations(shard_root=pipeline["per_source"])

    narrow = aggregate.build_observations(
        selectors=["eap/pacific/fiji"],
        shard_root=pipeline["per_source"],
        overlay=False,
    )
    assert set(narrow["country"]) == {"fiji"}
