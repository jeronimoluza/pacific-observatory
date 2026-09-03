import pandas as pd
import pytest

from prices.build import aggregate
from prices.enrich import shards

pytestmark = pytest.mark.unit


def obs_frame(country, price, n=2):
    return pd.DataFrame(
        {
            "country": [country] * n,
            "coicop_code": ["01.1.1.1"] * n,
            "standard_unit": ["kg"] * n,
            "unit_value_usd": [price] * n,
            "observation_date": [pd.Timestamp("2026-01-02")] * n,
        }
    )


def raw_frame(country, source, region="eap", subregion="pacific"):
    return pd.DataFrame(
        {
            "product_name": [f"Rice {country}"],
            "price": ["10"],
            "currency": ["FJD"],
            "country": [country],
            "source": [source],
            "date": ["2026-01-02T10:00:00Z"],
            "product_url": [f"https://{source}/rice"],
            "region": [region],
            "subregion": [subregion],
        }
    )


def test_overlay_replaces_only_the_recomputed_countries(tmp_path):
    existing = pd.concat(
        [obs_frame("fiji", 1.0), obs_frame("tonga", 2.0), obs_frame("samoa", 3.0)],
        ignore_index=True,
    )
    path = tmp_path / "observations.parquet"
    existing.to_parquet(path, index=False)

    fresh = obs_frame("fiji", 9.0, n=3)
    out = aggregate.overlay_observations(fresh, path)

    assert sorted(out["country"].unique()) == ["fiji", "samoa", "tonga"]
    # fiji's old two rows are gone, replaced by the three fresh ones
    assert (out["country"] == "fiji").sum() == 3
    assert set(out.loc[out["country"] == "fiji", "unit_value_usd"]) == {9.0}
    # every other country is carried through untouched
    assert set(out.loc[out["country"] == "tonga", "unit_value_usd"]) == {2.0}
    assert (out["country"] == "samoa").sum() == 2


def test_overlay_without_an_existing_frame_is_the_fresh_rows(tmp_path):
    fresh = obs_frame("fiji", 9.0)
    out = aggregate.overlay_observations(fresh, tmp_path / "missing.parquet")
    pd.testing.assert_frame_equal(out, fresh)


def test_overlay_of_nothing_leaves_the_existing_frame_alone(tmp_path):
    path = tmp_path / "observations.parquet"
    obs_frame("fiji", 1.0).to_parquet(path, index=False)
    out = aggregate.overlay_observations(pd.DataFrame(), path)
    assert out.empty


def test_a_full_rebuild_of_every_country_equals_the_unscoped_frame(tmp_path):
    """Overlaying every country is the identity on the row set — the scoped and
    unscoped paths cannot disagree about what the corpus contains."""
    countries = ["fiji", "tonga", "samoa"]
    existing = pd.concat([obs_frame(c, 1.0) for c in countries], ignore_index=True)
    path = tmp_path / "observations.parquet"
    existing.to_parquet(path, index=False)

    fresh = pd.concat([obs_frame(c, 5.0) for c in countries], ignore_index=True)
    out = aggregate.overlay_observations(fresh, path)
    assert len(out) == len(fresh)
    assert set(out["unit_value_usd"]) == {5.0}


@pytest.fixture
def shard_root(tmp_path):
    for country, source in [("fiji", "shop_a"), ("tonga", "shop_b")]:
        shards.write_shard(
            raw_frame(country, source),
            tmp_path / "eap" / "pacific" / country / f"{source}.parquet",
        )
    return tmp_path


def test_shard_chunks_carry_the_columns_observations_needs(shard_root):
    chunks = list(aggregate._iter_shard_chunks(root=shard_root))
    assert len(chunks) == 2
    assert set(chunks[0].columns) == set(aggregate.RAW_OBSERVATION_COLS)
    assert chunks[0]["input_hash"].notna().all()


def test_shard_chunks_honour_a_selector(shard_root):
    chunks = list(aggregate._iter_shard_chunks(["eap/pacific/fiji"], shard_root))
    assert len(chunks) == 1
    assert set(chunks[0]["country"]) == {"fiji"}


def test_chunks_come_from_the_shards_when_there_are_any(shard_root):
    it = aggregate._observation_chunks(None, None, shard_root)
    assert sum(len(c) for c in it) == 2


def test_chunks_fall_back_to_the_monolith_when_there_are_no_shards(tmp_path):
    monolith = tmp_path / "raw_prices.csv"
    shards.coerce(raw_frame("fiji", "shop_a")).to_csv(monolith, index=False)
    it = aggregate._observation_chunks(monolith, None, tmp_path / "no_shards")
    frames = list(it)
    assert sum(len(f) for f in frames) == 1
    assert "input_hash" in frames[0].columns


def test_a_selector_forces_the_shards_even_over_a_monolith(tmp_path, shard_root):
    monolith = tmp_path / "raw_prices.csv"
    shards.coerce(raw_frame("samoa", "shop_z")).to_csv(monolith, index=False)
    it = aggregate._observation_chunks(monolith, ["eap/pacific/tonga"], shard_root)
    rows = pd.concat(list(it), ignore_index=True)
    assert set(rows["country"]) == {"tonga"}


def test_join_chunk_uses_the_stored_hash_rather_than_rehashing(shard_root, monkeypatch):
    chunk = next(iter(aggregate._iter_shard_chunks(["eap/pacific/fiji"], shard_root)))
    monkeypatch.setattr(aggregate, "EAP_COUNTRIES", frozenset({"fiji"}))

    def explode(*args, **kwargs):
        raise AssertionError("input_hash was recomputed despite being in the shard")

    monkeypatch.setattr(aggregate, "input_hash", explode)
    cache = pd.DataFrame({"input_hash": list(chunk["input_hash"]), "coicop_code": ["01.1.1.1"]})
    joined = aggregate._join_chunk(chunk, cache)
    assert len(joined) == 1
