from pathlib import Path

import pytest

from prices import partition

pytestmark = pytest.mark.unit

TREE = [
    "ssa/southern/south_africa/agmarknet.csv",
    "ssa/southern/south_africa/shoprite.csv",
    "ssa/western/ghana/esoko.csv",
    "eap/pacific/fiji/rbf.csv",
    "eap/pacific/tonga/agmarknet.csv",
    "eap/south_east/indonesia/tokopedia.csv",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for rel in TREE:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("url_hash,product_name\n")
    return tmp_path


def keys(shards) -> set[str]:
    return {s.key for s in shards}


def test_iter_shards_reads_the_four_level_partition(root):
    shards = list(partition.iter_shards(root))
    assert len(shards) == len(TREE)
    one = next(s for s in shards if s.source == "esoko")
    assert (one.region, one.subregion, one.country) == ("ssa", "western", "ghana")
    assert one.key == "ssa/western/ghana/esoko"


def test_files_off_the_partition_depth_are_not_shards(root):
    (root / "stray.csv").write_text("x\n")
    deep = root / "ssa" / "southern" / "south_africa" / "extra"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "x.csv").write_text("x\n")
    assert len(list(partition.iter_shards(root))) == len(TREE)


def test_parquet_wins_over_csv_for_the_same_source(root):
    (root / "ssa" / "western" / "ghana" / "esoko.parquet").write_bytes(b"PAR1")
    shards = list(partition.iter_shards(root))
    assert len(shards) == len(TREE)
    esoko = next(s for s in shards if s.source == "esoko")
    assert esoko.path.suffix == ".parquet"


def test_no_selector_selects_everything(root):
    assert len(partition.select(None, root)) == len(TREE)
    assert len(partition.select([], root)) == len(TREE)


@pytest.mark.parametrize(
    "selector,expected",
    [
        (
            "ssa",
            {
                "ssa/southern/south_africa/agmarknet",
                "ssa/southern/south_africa/shoprite",
                "ssa/western/ghana/esoko",
            },
        ),
        (
            "ssa/southern",
            {
                "ssa/southern/south_africa/agmarknet",
                "ssa/southern/south_africa/shoprite",
            },
        ),
        ("ssa/western/ghana", {"ssa/western/ghana/esoko"}),
        ("ssa/western/ghana/esoko", {"ssa/western/ghana/esoko"}),
        (
            "**/agmarknet",
            {
                "ssa/southern/south_africa/agmarknet",
                "eap/pacific/tonga/agmarknet",
            },
        ),
        ("*/pacific", {"eap/pacific/fiji/rbf", "eap/pacific/tonga/agmarknet"}),
        ("*/*/ghana", {"ssa/western/ghana/esoko"}),
        ("eap/*/*/tokopedia", {"eap/south_east/indonesia/tokopedia"}),
    ],
)
def test_selector_depth_and_wildcards(root, selector, expected):
    assert keys(partition.select([selector], root)) == expected


def test_selectors_union(root):
    got = keys(partition.select(["ssa/western", "eap/pacific/fiji"], root))
    assert got == {"ssa/western/ghana/esoko", "eap/pacific/fiji/rbf"}


def test_selector_matching_nothing_returns_empty_not_everything(root):
    assert partition.select(["antarctica"], root) == []


def test_exact_four_segment_selector_does_not_match_a_sibling(root):
    got = keys(partition.select(["ssa/southern/south_africa/agmarknet"], root))
    assert got == {"ssa/southern/south_africa/agmarknet"}


def test_empty_selector_is_an_error():
    with pytest.raises(partition.SelectorError):
        partition.compile_selector("///")


def test_too_deep_selector_is_an_error():
    with pytest.raises(partition.SelectorError):
        partition.compile_selector("a/b/c/d/e")


@pytest.mark.parametrize(
    "flags,expected",
    [
        ((None, None, None), None),
        (("ssa", None, None), "ssa"),
        (("ssa", "western", None), "ssa/western"),
        (("ssa", "western", "ghana"), "ssa/western/ghana"),
        ((None, None, "ghana"), "*/*/ghana"),
        ((None, "pacific", None), "*/pacific"),
        (("eap", None, "fiji"), "eap/*/fiji"),
    ],
)
def test_selector_from_flags(flags, expected):
    assert partition.selector_from_flags(*flags) == expected


def test_flags_round_trip_through_select(root):
    selector = partition.selector_from_flags(country="ghana")
    assert keys(partition.select([selector], root)) == {"ssa/western/ghana/esoko"}


def test_order_longest_first_is_size_descending(root):
    (root / "eap" / "pacific" / "fiji" / "rbf.csv").write_text("x" * 5000)
    (root / "ssa" / "western" / "ghana" / "esoko.csv").write_text("x" * 500)
    ordered = partition.order_longest_first(partition.select(None, root))
    assert [s.source for s in ordered[:2]] == ["rbf", "esoko"]
    sizes = [s.size for s in ordered]
    assert sizes == sorted(sizes, reverse=True)


def test_underscore_directories_are_not_corpus(root):
    """A stage writing its output beneath the root must not read back as input
    on the next pass. `_`-prefixed dirs are scratch, as in concatenate's walk."""
    out = root / "_prepared" / "pacific" / "fiji" / "rbf.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("x\n")
    assert len(list(partition.iter_shards(root))) == len(TREE)


def test_group_by_country_keys_on_the_path_down_to_it(root):
    groups = partition.group_by(partition.select(None, root), "country")
    assert set(groups) == {
        ("ssa", "southern", "south_africa"),
        ("ssa", "western", "ghana"),
        ("eap", "pacific", "fiji"),
        ("eap", "pacific", "tonga"),
        ("eap", "south_east", "indonesia"),
    }
    assert {s.source for s in groups[("ssa", "southern", "south_africa")]} == {
        "agmarknet",
        "shoprite",
    }


def test_group_by_region_and_subregion(root):
    by_region = partition.group_by(partition.select(None, root), "region")
    assert set(by_region) == {("ssa",), ("eap",)}
    assert len(by_region[("eap",)]) == 3
    by_sub = partition.group_by(partition.select(None, root), "subregion")
    assert ("eap", "pacific") in by_sub


def test_group_by_unknown_level_is_an_error(root):
    with pytest.raises(partition.SelectorError):
        partition.group_by(partition.select(None, root), "continent")


def test_order_longest_first_is_deterministic_on_ties(root):
    ordered = partition.order_longest_first(partition.select(None, root))
    again = partition.order_longest_first(partition.select(None, root))
    assert [s.key for s in ordered] == [s.key for s in again]
