import os
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


@pytest.fixture(autouse=True)
def union_target(tmp_path, monkeypatch) -> Path:
    """Keep the default products_input.parquet target inside tmp_path so no
    test can write into the real data tree."""
    target = tmp_path / "products_input.parquet"
    monkeypatch.setattr(prepare_shards.config, "PRODUCTS_INPUT_PARQUET", target)
    return target


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


def prepared_path_for(out_dir: Path, key: str) -> Path:
    return prepare_shards.prepared_path(key.split("/"), out_dir)


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


def test_countries_are_scheduled_largest_first(corpus, tmp_path, monkeypatch):
    seen = []

    def spy(country_shards, key, out_dir=None):
        seen.append((key, sum(s.size for s in country_shards)))
        return Path("/dev/null")

    monkeypatch.setattr(prepare_shards, "prepare_country", spy)
    monkeypatch.setattr(prepare_shards, "_prepare_one", lambda a: spy(a[0], a[1], a[2]))
    prepare_shards.run(root=corpus, out_dir=tmp_path / "sched", write_union=False)
    sizes = [size for _, size in seen]
    assert sizes == sorted(sizes, reverse=True)


def test_union_is_written_and_matches_the_country_parquets(
    corpus, tmp_path, union_target
):
    out_dir = tmp_path / "_prepared"
    paths = prepare_shards.run(root=corpus, out_dir=out_dir)
    assert union_target.exists()
    union = pd.read_parquet(union_target)
    pd.testing.assert_frame_equal(
        normalise(union), normalise(prepare_shards.read_prepared(paths))
    )


def test_a_scoped_rerun_overlays_rather_than_truncating(corpus, tmp_path, union_target):
    """The point of the slice-and-overlay loop: recomputing one country must
    leave every other country in products_input.parquet."""
    out_dir = tmp_path / "_prepared"
    prepare_shards.run(root=corpus, out_dir=out_dir)
    before = pd.read_parquet(union_target)

    prepare_shards.run(["eap/pacific/fiji"], root=corpus, out_dir=out_dir)
    after = pd.read_parquet(union_target)

    assert set(after["country"]) == set(before["country"])
    pd.testing.assert_frame_equal(normalise(after), normalise(before))


def test_an_unchanged_country_is_not_prepared_again(corpus, tmp_path):
    """The whole point: the second run recomputes nothing."""
    out_dir = tmp_path / "_prepared"
    first = prepare_shards.run(root=corpus, out_dir=out_dir)
    assert len(first) == 4
    stamps = {p: p.stat().st_mtime_ns for p in first}

    assert prepare_shards.run(root=corpus, out_dir=out_dir) == []
    assert {p: p.stat().st_mtime_ns for p in first} == stamps


def test_a_changed_shard_recomputes_its_whole_country(corpus, tmp_path):
    """Country, not source: `input_hash` falls back to (name, country,
    currency), so a changed source can move the median of a group whose other
    members did not change."""
    out_dir = tmp_path / "_prepared"
    prepare_shards.run(root=corpus, out_dir=out_dir)

    shard = corpus / "eap" / "pacific" / "fiji" / "shop_b.parquet"
    frame = shards.read_shard(shard)
    frame.loc[frame["product_name"] == "Rice 1kg", "price"] = "50"
    shards.write_shard(frame, shard)

    again = prepare_shards.run(root=corpus, out_dir=out_dir)
    assert [p.stem for p in again] == ["fiji"]

    fiji = pd.read_parquet(prepared_path_for(out_dir, "eap/pacific/fiji"))
    rice = fiji[fiji["product_name_original"] == "Rice 1kg"]
    # shop_a 10 and shop_b 50 are one URL-less group; the median moved with it.
    assert float(rice["price"].iloc[0]) == 30.0


def test_a_deleted_prepared_parquet_is_rebuilt(corpus, tmp_path):
    out_dir = tmp_path / "_prepared"
    prepare_shards.run(root=corpus, out_dir=out_dir)
    prepared_path_for(out_dir, "eap/pacific/tonga").unlink()
    assert [p.stem for p in prepare_shards.run(root=corpus, out_dir=out_dir)] == [
        "tonga"
    ]


def test_force_prepares_everything_again(corpus, tmp_path):
    out_dir = tmp_path / "_prepared"
    prepare_shards.run(root=corpus, out_dir=out_dir)
    assert len(prepare_shards.run(root=corpus, out_dir=out_dir, force=True)) == 4


def test_a_scoped_run_does_not_invalidate_the_countries_it_skipped(corpus, tmp_path):
    """A selector-excluded country keeps its state entry, or the next unscoped
    run redoes every country the selector happened to miss."""
    out_dir = tmp_path / "_prepared"
    prepare_shards.run(root=corpus, out_dir=out_dir)
    prepare_shards.run(["eap/pacific/fiji"], root=corpus, out_dir=out_dir, force=True)
    assert prepare_shards.run(root=corpus, out_dir=out_dir) == []


def test_a_failed_run_caches_nothing_as_done(corpus, tmp_path, monkeypatch):
    """A run that dies must leave every country to be prepared again, so the
    state has to be written from what finished rather than from what started."""
    out_dir = tmp_path / "_prepared"

    def boom(args):
        raise RuntimeError("worker died")

    monkeypatch.setattr(prepare_shards, "_prepare_one", boom)
    with pytest.raises(RuntimeError):
        prepare_shards.run(root=corpus, out_dir=out_dir)
    monkeypatch.undo()

    assert len(prepare_shards.run(root=corpus, out_dir=out_dir)) == 4


def test_union_of_nothing_writes_nothing(tmp_path, union_target):
    assert prepare_shards.write_products_input(tmp_path / "empty") is None
    assert not union_target.exists()


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


def test_declared_unit_survives_the_read(tmp_path):
    """`unit` has to be IN PREPARE_COLUMNS or prepare never sees it.

    71b1e9ef fixed the writer half of this -- `unit` reaches the shard on disk.
    It did not fix the reader: `prepare_country` passes this allowlist to
    `read_shards`, so a column the tuple omits is simply not requested, and
    `_derive` then fills it with "" (prepare.py:213). Every downstream consumer
    still ran clean, which is why it went unnoticed twice: the declared-unit
    fallback in classify (`parse_declared_unit`) got an empty string for every
    production row and quietly contributed nothing.
    """
    frame = pd.DataFrame(rows("india", "sar", "south_asia", "agmarknet", [
        ("Onion", "2500", ""),
    ]))
    frame["unit"] = "quintal (100 kg)"
    shard = shards.write_shard(
        frame, tmp_path / "sar" / "south_asia" / "india" / "agmarknet.parquet"
    )
    raw = shards.read_shard(shard, columns=list(prepare_shards.PREPARE_COLUMNS))
    assert list(prepare_input(raw)["unit"]) == ["quintal (100 kg)"]


# ---------------------------------------------------------------------------
# A country too big to hold: the shuffle
# ---------------------------------------------------------------------------


@pytest.fixture
def bulk_corpus(tmp_path: Path) -> Path:
    """One country, three sources, 1,800 rows. Two thirds of them carry no URL,
    so the (name, country, currency) fallback key is what groups them, and the
    same names recur across all three sources, so a group spans shards. Enough
    distinct hashes that they land in most of the 64 buckets, which is what
    makes the ORDER of the buckets observable."""
    root = tmp_path / "bulk"
    for si, source in enumerate(("alpha", "beta", "gamma")):
        specs = []
        for i in range(600):
            name = f"Product {i % 220}"
            url = f"https://{source}/p/{i % 190}" if i % 3 == 0 else ""
            specs.append((name, str(10 + (i * 7 + si) % 90), url))
        shards.write_shard(
            pd.DataFrame(rows("japan", "eap", "east_asia", source, specs)),
            root / "eap" / "east_asia" / "japan" / f"{source}.parquet",
        )
    return root


def whole_frame_prepare(root: Path, key: str) -> pd.DataFrame:
    return prepare_input(
        shards.read_shards(
            partition.select([key], root), columns=list(prepare_shards.PREPARE_COLUMNS)
        )
    )


def test_a_shuffled_country_is_the_whole_frame_run_row_for_row(bulk_corpus, tmp_path):
    """The equality the shuffle exists to preserve, POSITIONALLY and at the
    same dtypes -- not merely the same set of groups. Buckets are ascending
    ranges of `input_hash`, so pass 2 emits them in the order one whole-frame
    `groupby` would have; a modulo shuffle puts the same rows in an order of
    its own."""
    key = ("eap", "east_asia", "japan")
    out_dir = tmp_path / "_prepared"
    prepare_shards.prepare_country(
        partition.select(["/".join(key)], bulk_corpus), key, out_dir, stream_above=0
    )
    got = pd.read_parquet(prepare_shards.prepared_path(key, out_dir))
    expected = whole_frame_prepare(bulk_corpus, "/".join(key))
    assert len(got) > 200  # or the ordering claim is untested
    pd.testing.assert_frame_equal(got, expected)


def test_a_group_spanning_shards_still_takes_one_median_through_the_shuffle(
    bulk_corpus, tmp_path
):
    """The property that rules out sharding by source, restated for buckets: a
    URL-less product sold by all three sources is ONE row whose price is the
    median of the three, and the bucket it lands in has to hold all of them."""
    key = ("eap", "east_asia", "japan")
    out_dir = tmp_path / "_prepared"
    prepare_shards.prepare_country(
        partition.select(["/".join(key)], bulk_corpus), key, out_dir, stream_above=0
    )
    got = pd.read_parquet(prepare_shards.prepared_path(key, out_dir))
    urlless = got[got["product_url"].eq("") & got["n_rows"].gt(1)]
    assert not urlless.empty
    expected = whole_frame_prepare(bulk_corpus, "/".join(key))
    merged = urlless.merge(expected, on="input_hash", suffixes=("_got", "_exp"))
    assert len(merged) == len(urlless)
    assert (merged["price_got"] == merged["price_exp"]).all()
    assert (merged["n_rows_got"] == merged["n_rows_exp"]).all()


def test_the_threshold_decides_which_countries_are_shuffled(bulk_corpus, monkeypatch):
    """Japan is 4.64 GB of shard over 52M rows and ~1 KB per row resident; it
    has to take the shuffle and the 197 small countries have to not, because
    the shuffle round-trips every raw row through disk."""
    key = ("eap", "east_asia", "japan")
    group = partition.select(["/".join(key)], bulk_corpus)
    calls = []
    real = prepare_shards.prepare_input_streaming
    monkeypatch.setattr(
        prepare_shards,
        "prepare_input_streaming",
        lambda *a, **kw: (calls.append(1), real(*a, **kw))[1],
    )
    out_dir = bulk_corpus / "_prepared"
    prepare_shards.prepare_country(group, key, out_dir, stream_above=1 << 40)
    assert calls == []
    prepare_shards.prepare_country(group, key, out_dir, stream_above=0)
    assert calls == [1]


def test_the_shuffle_scratch_is_a_sibling_of_the_prepared_tree(tmp_path):
    """`write_products_input` unions every parquet under the prepared tree, so
    a part left behind by a worker that died mid-shuffle must not be in it."""
    out_dir = tmp_path / "_prepared"
    spill = prepare_shards._spill_dir(out_dir, ("eap", "east_asia", "japan"))
    assert out_dir not in spill.parents


def test_a_leftover_shuffle_part_is_not_unioned_into_products_input(
    bulk_corpus, tmp_path, union_target
):
    key = ("eap", "east_asia", "japan")
    out_dir = tmp_path / "_prepared"
    prepare_shards.prepare_country(
        partition.select(["/".join(key)], bulk_corpus), key, out_dir, stream_above=0
    )
    clean = len(pd.read_parquet(prepare_shards.write_products_input(out_dir)))

    spill = prepare_shards._spill_dir(out_dir, key)
    spill.mkdir(parents=True, exist_ok=True)
    pd.read_parquet(prepare_shards.prepared_path(key, out_dir)).to_parquet(
        spill / "part_000_0000.parquet", index=False
    )
    assert len(pd.read_parquet(prepare_shards.write_products_input(out_dir))) == clean


# ---------------------------------------------------------------------------
# A dead worker must not throw away the countries that finished
# ---------------------------------------------------------------------------


def _raise_on_fiji(args):
    """Module level so a forked worker resolves it by name."""
    if args[1][-1] == "fiji":
        raise RuntimeError("worker died")
    return prepare_shards.prepare_country(*args)


# Set in the parent before the pool forks, so the workers inherit it.
_KILL_COUNTRY = ""


def _kill_the_pool(args):
    """What japan actually did: the kernel took the worker, not an exception,
    so the pool broke. Note what that costs even after the fix -- every future
    still IN FLIGHT comes back BrokenProcessPool too, so only the countries
    that had already finished survive. That is the 205 of 210 case, not 210."""
    if args[1][-1] == _KILL_COUNTRY:
        os._exit(1)
    return prepare_shards.prepare_country(*args)


def test_a_failing_country_does_not_discard_the_ones_that_finished(
    corpus, tmp_path, monkeypatch
):
    out_dir = tmp_path / "_prepared"
    monkeypatch.setattr(prepare_shards, "_prepare_one", _raise_on_fiji)
    with pytest.raises(partition.PartialFailure):
        prepare_shards.run(root=corpus, out_dir=out_dir, workers=4)
    monkeypatch.undo()

    state = prepare_shards._load_state(out_dir)
    assert "eap/pacific/fiji" not in state
    assert sorted(state) == [
        "eap/pacific/tonga",
        "ssa/southern/south_africa",
        "ssa/western/ghana",
    ]
    assert [p.stem for p in prepare_shards.run(root=corpus, out_dir=out_dir)] == ["fiji"]


def test_a_broken_pool_does_not_discard_the_countries_that_finished(
    corpus, tmp_path, monkeypatch
):
    """The failure that lost 210 countries. The smallest country is scheduled
    last, so with two workers the others have finished and been recorded before
    it takes the pool down."""
    global _KILL_COUNTRY
    groups = partition.group_by(partition.select(None, corpus), "country")
    smallest = min(groups, key=lambda k: sum(s.size for s in groups[k]))
    _KILL_COUNTRY = smallest[-1]

    out_dir = tmp_path / "_prepared"
    monkeypatch.setattr(prepare_shards, "_prepare_one", _kill_the_pool)
    with pytest.raises(partition.PartialFailure):
        prepare_shards.run(root=corpus, out_dir=out_dir, workers=2)
    monkeypatch.undo()

    state = prepare_shards._load_state(out_dir)
    assert "/".join(smallest) not in state
    assert len(state) >= 2

    again = [p.stem for p in prepare_shards.run(root=corpus, out_dir=out_dir)]
    assert smallest[-1] in again
    assert len(again) == len(groups) - len(state)


def test_a_run_that_lost_a_country_does_not_write_the_union(
    corpus, tmp_path, monkeypatch, union_target
):
    """It must not look like a clean success: a union built over a tree with a
    country missing -- or holding that country's PREVIOUS parquet -- is what
    the next stage would read as complete."""
    monkeypatch.setattr(prepare_shards, "_prepare_one", _raise_on_fiji)
    with pytest.raises(partition.PartialFailure):
        prepare_shards.run(root=corpus, out_dir=tmp_path / "_prepared", workers=4)
    assert not union_target.exists()
