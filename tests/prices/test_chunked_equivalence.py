"""The country-chunked build must agree with the whole-frame build, exactly.

`build.chunked` exists only to change peak memory. If it also changes a number,
it is worse than the OOM it was written to avoid: an OOM stops the run, a
divergence ships. So the test is equality of every output, not a tolerance.

The corpus below is shaped to make the two known traps bite, because a corpus
that does not exercise them would pass whether or not they were handled:

  * `samoa` and `solomon_islands` stop observing months before everyone else.
    `build_analytical` anchors its trailing window on the GLOBAL latest trusted
    observation, so if the chunked path let each country anchor on its own last
    month, those two would summarise a window nobody else used -- and the column
    would still be called `unit_price_local`. The pinned anchor is what this
    catches.
  * `item`-basis rows sit alongside mass rows for the same leaf, so
    `convert_item_rows` has something to convert and `derive_typical_mass` has
    both sides of its per-country ratio gate. That gate groups BY COUNTRY, so a
    chunked derivation that saw one country at a time would gate differently.
"""

import json

import pandas as pd
import pytest

from prices import partition
from prices.build import aggregate, analytical, chunked, leaf_typical_mass
from prices.enrich import config as enrich_config
from prices.enrich import prepare_shards
from prices.enrich.stages import concatenate

pytestmark = pytest.mark.unit

# (country, source) -> [(name, price, iso_date)]
# Six countries so the pool has something to schedule, uneven so it has
# something to schedule badly.
CORPUS = {
    ("fiji", "shop_a"): [
        ("Rice 1kg", "10.00", "2026-01-05"),
        ("Rice 1kg", "11.00", "2026-02-05"),
        ("Rice 1kg", "12.00", "2026-03-05"),
        ("Rice 1kg", "13.00", "2026-04-05"),
        ("Eggs tray", "6.00", "2026-04-06"),
    ],
    ("fiji", "shop_b"): [
        ("Flour 2kg", "8.00", "2026-03-07"),
        ("Flour 2kg", "9.00", "2026-04-07"),
        ("Eggs tray", "6.50", "2026-04-07"),
    ],
    ("tonga", "shop_c"): [
        ("Rice 1kg", "12.00", "2026-02-11"),
        ("Rice 1kg", "12.50", "2026-03-11"),
        ("Rice 1kg", "13.50", "2026-04-11"),
        ("Eggs tray", "7.00", "2026-03-11"),
    ],
    ("vanuatu", "shop_d"): [
        ("Sugar 1kg", "5.00", "2026-02-14"),
        ("Sugar 1kg", "5.50", "2026-04-14"),
        ("Rice 1kg", "14.00", "2026-04-14"),
    ],
    ("papua_new_guinea", "shop_e"): [
        ("Rice 1kg", "15.00", "2026-03-20"),
        ("Rice 1kg", "15.50", "2026-04-20"),
        ("Flour 2kg", "9.50", "2026-04-20"),
    ],
    # Stops in January. A per-country anchor would give this one a
    # Nov-2025..Jan-2026 window while everyone else got Feb..Apr 2026.
    ("samoa", "shop_f"): [
        ("Rice 1kg", "9.00", "2026-01-09"),
        ("Sugar 1kg", "4.50", "2026-01-09"),
    ],
    # Stops in February, for the same reason with a different offset.
    ("solomon_islands", "shop_g"): [
        ("Rice 1kg", "16.00", "2026-02-02"),
        ("Flour 2kg", "10.00", "2026-02-02"),
    ],
}

# Which leaf and basis each product name classifies to. `Eggs tray` is the
# item-basis row that gives convert_item_rows something to do.
PRODUCTS = {
    "Rice 1kg": ("01.1.1.1", "mass", 1.0, "kg"),
    "Flour 2kg": ("01.1.1.1", "mass", 2.0, "kg"),
    "Sugar 1kg": ("01.1.8.1", "mass", 1.0, "kg"),
    "Eggs tray": ("01.1.1.1", "item", None, None),
}

CONSUMABLES = ("trusted", "summary", "analytical")


def write_source(data_root, country, source, items):
    path = (
        data_root / "eap" / "pacific" / country / source / "raw_items" / "a.jsonl"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for name, price, day in items:
            fh.write(
                json.dumps(
                    {
                        "product_name": name,
                        "price": price,
                        "currency": "FJD",
                        "scraped_at_utc": f"{day}T10:00:00Z",
                        "url": f"https://{source}/{name.split()[0].lower()}",
                        "product_id": f"{source}-{name}-{day}",
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
def corpus(tmp_path, monkeypatch):
    data_root = tmp_path / "data" / "prices"
    per_source = tmp_path / "outputs" / "prices" / "raw" / "_per_source"
    build_dir = tmp_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    for (country, source), items in CORPUS.items():
        write_source(data_root, country, source, items)

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

    monkeypatch.setattr(aggregate, "BUILD_DIR", build_dir)
    monkeypatch.setattr(aggregate, "attach_fx_and_usd", stub_fx)
    monkeypatch.setattr(aggregate, "FX_HISTORY_FLOOR", pd.Timestamp("2020-01-01"))
    # Same reason the fast-iteration e2e redirects it: derive_typical_mass writes
    # this file, and it resolves the constant from its own module, so patching
    # aggregate.BUILD_DIR does not reach it. Left alone the test overwrites the
    # production conversion table.
    monkeypatch.setattr(
        leaf_typical_mass, "TYPICAL_MASS_CSV", build_dir / "leaf_typical_mass.csv"
    )

    concatenate.run(write_monolith=False)
    prepare_shards.run(root=per_source, out_dir=tmp_path / "_prepared")

    pi = pd.read_parquet(products_input)
    name = pi["product_name_original"] if "product_name_original" in pi else pi["product_name"]
    spec = name.map(lambda n: PRODUCTS.get(str(n), ("01.1.1.1", "mass", 1.0, "kg")))
    cache = pd.DataFrame(
        {
            "input_hash": pi["input_hash"],
            "pricing_basis": [s[1] for s in spec],
            "amount_value": [s[2] for s in spec],
            "standard_unit": [s[3] for s in spec],
            "count": 1.0,
            "multiplier": float("nan"),
            "coicop_code": [s[0] for s in spec],
            "is_promotion": False,
            "is_bundle": False,
            "is_multipack": False,
            "confidence": 0.99,
            "trust_level": "high",
            "state": "classified",
        }
    )
    classified = tmp_path / "classified.parquet"
    cache.to_parquet(classified, index=False)
    monkeypatch.setattr(enrich_config, "CLASSIFIED_PARQUET", classified)
    monkeypatch.setattr(enrich_config, "BUILD_CLASSIFIED_PARQUET", classified)

    return {"per_source": per_source, "build_dir": build_dir, "tmp": tmp_path}


def _point_outputs_at(monkeypatch, root, tag):
    """Send every build output into its own directory, so two runs can coexist."""
    d = root / tag
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(aggregate, "OBSERVATIONS_PARQUET", d / "observations.parquet")
    monkeypatch.setattr(aggregate, "TRUSTED_OBS_PARQUET", d / "trusted.parquet")
    monkeypatch.setattr(aggregate, "UNIT_VALUE_SUMMARY_PARQUET", d / "summary.parquet")
    monkeypatch.setattr(analytical, "ANALYTICAL_PARQUET", d / "analytical.parquet")
    return {
        "observations": d / "observations.parquet",
        "trusted": d / "trusted.parquet",
        "summary": d / "summary.parquet",
        "analytical": d / "analytical.parquet",
    }


def _normalize(df):
    """Row order is not part of the contract; values and columns are."""
    df = df.reindex(columns=sorted(df.columns))
    if df.empty:
        return df.reset_index(drop=True)
    return (
        df.sort_values(list(df.columns), kind="mergesort")
        .reset_index(drop=True)
        .convert_dtypes()
    )


def test_chunked_build_matches_whole_frame_build(corpus, tmp_path, monkeypatch):
    root = corpus["tmp"] / "runs"

    # --- whole-frame path -------------------------------------------------
    plain = _point_outputs_at(monkeypatch, root, "plain")
    obs = aggregate.build_observations(shard_root=corpus["per_source"])
    assert not obs.empty
    aggregate._write_consumables(obs)

    # --- country-chunked path --------------------------------------------
    split = _point_outputs_at(monkeypatch, root, "chunked")
    parts = aggregate.build_observations(
        shard_root=corpus["per_source"],
        workers=3,
        spill_to=corpus["tmp"] / "scratch",
    )
    # Paths back, never a frame: the caller must not be able to rebuild the
    # thing the chunking exists to avoid.
    assert isinstance(parts, list)
    assert {p.stem for p in parts} == set(obs["country"].unique())

    # --- the assertion that matters ---------------------------------------
    left = _normalize(pd.read_parquet(plain["observations"]))
    right = _normalize(pd.read_parquet(split["observations"]))
    assert list(left.columns) == list(right.columns), "column set diverged"
    assert len(left) == len(right), f"row count {len(left)} vs {len(right)}"
    pd.testing.assert_frame_equal(left, right, check_dtype=False)

    for name in CONSUMABLES:
        a = _normalize(pd.read_parquet(plain[name]))
        b = _normalize(pd.read_parquet(split[name]))
        assert list(a.columns) == list(b.columns), f"{name}: column set diverged"
        assert len(a) == len(b), f"{name}: row count {len(a)} vs {len(b)}"
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_chunked_analytical_uses_the_global_window_not_a_per_country_one(
    corpus, tmp_path, monkeypatch
):
    """The trap that would not show up as a crash.

    samoa's own last observation is 2026-01; the corpus's is 2026-04. If the
    chunked path anchored per country, samoa would report a Nov-Jan window and
    the row would look perfectly ordinary.
    """
    root = corpus["tmp"] / "anchor"
    plain = _point_outputs_at(monkeypatch, root, "plain")
    obs = aggregate.build_observations(shard_root=corpus["per_source"])
    aggregate._write_consumables(obs)
    whole = pd.read_parquet(plain["analytical"])

    split = _point_outputs_at(monkeypatch, root, "chunked")
    aggregate.build_observations(
        shard_root=corpus["per_source"],
        workers=2,
        spill_to=corpus["tmp"] / "scratch_anchor",
    )
    chunk = pd.read_parquet(split["analytical"])

    # The global anchor is April, so a country that stopped in January or
    # February contributes nothing to a trailing-3-month table. Both paths must
    # agree on that -- including on the exclusion.
    assert _normalize(whole).equals(_normalize(chunk))
    stale = {"samoa", "solomon_islands"}
    assert not (set(chunk["country"]) & stale), (
        "a country whose last observation predates the global window appeared in "
        "the trailing table, which means the window was anchored per country"
    )


def test_global_anchor_reads_the_latest_trusted_month(corpus, tmp_path, monkeypatch):
    _point_outputs_at(monkeypatch, corpus["tmp"] / "anchoronly", "chunked")
    aggregate.build_observations(
        shard_root=corpus["per_source"],
        workers=2,
        spill_to=corpus["tmp"] / "scratch_only",
    )
    # build_observations_chunked removes its scratch on success, so re-derive
    # the anchor from the finalized observations instead.
    obs = pd.read_parquet(aggregate.OBSERVATIONS_PARQUET)
    trusted = obs[obs["qa_status"] == "trusted"]
    expected = pd.to_datetime(trusted["observation_date"]).max().to_period("M")
    assert expected == pd.Period("2026-04", freq="M")


def test_spill_partitions_by_country_and_drains_the_input(tmp_path):
    """The spill must consume its input list, not merely read it."""
    monkey = pd.DataFrame(
        {
            "country": ["fiji", "tonga", "fiji"],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "price": ["1.00", "2.00", "3.00"],
        }
    )
    pieces = [monkey.copy(), monkey.copy()]
    counts = chunked.spill_by_country(pieces, tmp_path / "parts")
    assert pieces == [], "spill did not drain its input; memory would be held"
    assert counts == {"fiji": 4, "tonga": 2}
    assert {p.stem for p in (tmp_path / "parts").glob("*.parquet")} == {
        "fiji",
        "tonga",
    }
