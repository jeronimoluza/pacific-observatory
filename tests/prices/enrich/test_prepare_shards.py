from pathlib import Path

import pandas as pd
import pytest

from prices import partition
from prices.enrich import prepare_shards, shards
from prices.enrich.stages.prepare import prepare_input

pytestmark = pytest.mark.unit


def rows(country, region, subregion, source, specs):
    """specs = [(name, price, url), ...]"""
    return [
        {
            "url_hash": None,
            "product_name": name,
            "price": price,
            "currency": "USD",
            "country": country,
            "source": source,
            "date": "2026-01-02T10:00:00Z",
            "product_url": url,
            "product_id": None,
            "region": region,
            "subregion": subregion,
            "wayback": False,
            "channel": "retail",
            "category": "",
            "details": "",
        }
        for name, price, url in specs
    ]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Two regions, four countries, two sources per country. Within a country
    the same URL-less product name appears in both sources at different prices
    — the case the global groupby collapses to one median row."""
    tree = {
        ("eap", "pacific", "fiji", "shop_a"): [
            ("Rice 1kg", "10", ""),
            ("Milk 1L", "4", "https://a/milk"),
        ],
        ("eap", "pacific", "fiji", "shop_b"): [
            ("Rice 1kg", "30", ""),
            ("Bread", "2", "https://b/bread"),
        ],
        ("eap", "pacific", "tonga", "shop_c"): [
            ("Rice 1kg", "12", ""),
            ("Rice 1kg", "18", ""),
        ],
        ("ssa", "western", "ghana", "esoko"): [
            ("Yam 1kg", "5", "https://e/yam"),
        ],
        ("ssa", "western", "ghana", "melcom"): [
            ("Yam 1kg", "7", "https://e/yam"),
        ],
        ("ssa", "southern", "south_africa", "shoprite"): [
            ("Maize 2kg", "20", ""),
        ],
    }
    root = tmp_path / "corpus"
    for (region, subregion, country, source), specs in tree.items():
        frame = pd.DataFrame(rows(country, region, subregion, source, specs))
        shards.write_shard(
            frame, root / region / subregion / country / f"{source}.parquet"
        )
    return root


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("input_hash", ignore_index=True)[
        ["input_hash", "product_name_original", "country", "price", "n_rows"]
    ]


def global_prepare(root: Path) -> pd.DataFrame:
    raw = shards.read_shards(
        partition.select(None, root), columns=list(prepare_shards.PREPARE_COLUMNS)
    )
    return prepare_input(raw)


def test_country_grain_reproduces_the_global_run_exactly(corpus, tmp_path):
    out_dir = tmp_path / "_prepared"
    paths = prepare_shards.run(root=corpus, out_dir=out_dir)
    sharded = prepare_shards.read_prepared(paths)
    expected = global_prepare(corpus)

    pd.testing.assert_frame_equal(
        normalise(sharded), normalise(expected), check_dtype=False
    )


def test_source_grain_would_not_have(corpus):
    """The reason the grain is country. Splitting by source leaves Fiji's two
    Rice rows uncollapsed, so the slice reports 10 and 30 where the full run
    reports one row at 20."""
    per_source = pd.concat(
        [
            prepare_input(
                shards.read_shards([s], columns=list(prepare_shards.PREPARE_COLUMNS))
            )
            for s in partition.select(None, corpus)
        ],
        ignore_index=True,
    )
    expected = global_prepare(corpus)
    assert len(per_source) > len(expected)

    fiji_rice = per_source[
        per_source["country"].eq("fiji")
        & per_source["product_name_original"].eq("Rice 1kg")
    ]
    assert sorted(fiji_rice["price"]) == [10.0, 30.0]
    global_rice = expected[
        expected["country"].eq("fiji")
        & expected["product_name_original"].eq("Rice 1kg")
    ]
    assert list(global_rice["price"]) == [20.0]
    assert list(global_rice["n_rows"]) == [2]


def test_one_parquet_per_country_at_the_partition_path(corpus, tmp_path):
    out_dir = tmp_path / "_prepared"
    paths = prepare_shards.run(root=corpus, out_dir=out_dir)
    assert sorted(p.relative_to(out_dir).as_posix() for p in paths) == [
        "eap/pacific/fiji.parquet",
        "eap/pacific/tonga.parquet",
        "ssa/southern/south_africa.parquet",
        "ssa/western/ghana.parquet",
    ]


def test_selector_limits_which_countries_are_written(corpus, tmp_path):
    out_dir = tmp_path / "_prepared"
    paths = prepare_shards.run(["ssa"], root=corpus, out_dir=out_dir)
    assert sorted(p.stem for p in paths) == ["ghana", "south_africa"]
    assert not (out_dir / "eap").exists()


def test_a_slice_matches_the_full_run_for_the_rows_it_touches(corpus, tmp_path):
    full = prepare_shards.read_prepared(
        prepare_shards.run(root=corpus, out_dir=tmp_path / "full")
    )
    slice_ = prepare_shards.read_prepared(
        prepare_shards.run(
            ["eap/pacific/fiji"], root=corpus, out_dir=tmp_path / "slice"
        )
    )
    overlapping = full[full["input_hash"].isin(slice_["input_hash"])]
    pd.testing.assert_frame_equal(
        normalise(slice_), normalise(overlapping), check_dtype=False
    )


def test_selector_matching_nothing_writes_nothing(corpus, tmp_path):
    assert prepare_shards.run(["antarctica"], root=corpus, out_dir=tmp_path / "x") == []


def test_workers_do_not_change_the_result(corpus, tmp_path):
    one = prepare_shards.read_prepared(
        prepare_shards.run(root=corpus, out_dir=tmp_path / "one", workers=1)
    )
    many = prepare_shards.read_prepared(
        prepare_shards.run(root=corpus, out_dir=tmp_path / "many", workers=3)
    )
    pd.testing.assert_frame_equal(normalise(one), normalise(many), check_dtype=False)


def test_countries_are_scheduled_largest_first(corpus, monkeypatch):
    seen = []

    def spy(country_shards, key, out_dir=None):
        seen.append((key, sum(s.size for s in country_shards)))
        return Path("/dev/null")

    monkeypatch.setattr(prepare_shards, "prepare_country", spy)
    monkeypatch.setattr(prepare_shards, "_prepare_one", lambda a: spy(a[0], a[1], a[2]))
    prepare_shards.run(root=corpus)
    sizes = [size for _, size in seen]
    assert sizes == sorted(sizes, reverse=True)


def test_cross_country_urls_are_empty_on_a_clean_corpus(corpus):
    assert prepare_shards.find_cross_country_urls(root=corpus).empty


def test_cross_country_urls_are_reported_when_planted(corpus):
    """The one input on which the country grain differs from the global run —
    and which the global run already handles by picking a country arbitrarily."""
    frame = pd.DataFrame(
        rows("tonga", "eap", "pacific", "shop_c", [("Yam 1kg", "9", "https://e/yam")])
    )
    shards.write_shard(frame, corpus / "eap" / "pacific" / "tonga" / "extra.parquet")
    conflicts = prepare_shards.find_cross_country_urls(root=corpus)
    assert list(conflicts["product_url"]) == ["https://e/yam"]
    assert conflicts["countries"].iloc[0] == "ghana|tonga"
